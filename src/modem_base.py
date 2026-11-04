import numpy as np
import sounddevice as sd
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
import time  # добавлен импорт
# ================== Константы ==================
FS = 44100
BIT_DURATION = 0.01
CHUNK_SIZE = int(FS * BIT_DURATION)

FREQ_0 = 4400
FREQ_1 = 8800

PREAMBLE = "10" * 16
START_SEQ = "11110000"
END_SEQ = "00001111"

ENERGY_THRESHOLD = 0.05
SYNC_THRESHOLD = 0.8

# ========== Преобразование текст <-> биты ==========
def text_to_bits(text):
    return ''.join(format(ord(c), '08b') for c in text)

def bits_to_text(bits):
    chars = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        if len(byte) == 8:
            chars.append(chr(int(byte, 2)))
    return "".join(chars)

# ========== Манчестерское кодирование ==========
def manchester_encode(bits):
    encoded = ""
    for b in bits:
        if b == "0":
            encoded += "01"
        else:
            encoded += "10"
    return encoded

def manchester_decode(bits):
    decoded = ""
    for i in range(0, len(bits), 2):
        pair = bits[i:i+2]
        if pair == "01":
            decoded += "0"
        elif pair == "10":
            decoded += "1"
    return decoded

# ========== CRC16 ==========
def crc16(bits):
    crc = 0xFFFF
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        if len(byte) < 8:
            break
        crc ^= int(byte, 2)
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return format(crc, "016b")

# ========== Генерация тона ==========
def generate_tone(freq, duration):
    t = np.linspace(0, duration, int(FS * duration), False)
    fade_length = int(0.01 * FS)
    tone = 0.8 * np.sin(2 * np.pi * freq * t)
    if len(tone) > 2 * fade_length:
        fade_in = np.linspace(0, 1, fade_length)
        fade_out = np.linspace(1, 0, fade_length)
        tone[:fade_length] *= fade_in
        tone[-fade_length:] *= fade_out
    return tone

def bits_to_signal(bits):
    signal = []
    for bit in bits:
        freq = FREQ_1 if bit == "1" else FREQ_0
        tone = generate_tone(freq, BIT_DURATION)
        signal.extend(tone)
    return np.array(signal)

# ========== Фильтры ==========
def design_filter(lowcut, highcut, fs, order=5):
    """Создает полосовой фильтр Баттерворта"""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def apply_filter(data, lowcut, highcut, fs):
    b, a = design_filter(lowcut, highcut, fs)
    return filtfilt(b, a, data)

# ========== Алгоритм Герцеля ==========
def goertzel(samples, target_freq):
    n = len(samples)
    k = int(0.5 + (n * target_freq) / FS)
    w = (2.0 * np.pi / n) * k
    cosine = np.cos(w)
    coeff = 2 * cosine
    q0, q1, q2 = 0, 0, 0
    for sample in samples:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0

    return q1*q1 + q2*q2 - q1*q2*coeff

def enhanced_goertzel(samples, target_freq):
    filtered = apply_filter(samples, target_freq - 120, target_freq + 120, FS)
    return goertzel(filtered, target_freq)

# ========== Детектирование бита ==========
def detect_bit(chunk):
    p0 = goertzel(chunk, FREQ_0)
    p1 = goertzel(chunk, FREQ_1)
    return "1" if p1 > p0 else "0"

def detect_bit_enhanced(chunk):
    energy = np.sum(np.abs(chunk))
    if energy < ENERGY_THRESHOLD * len(chunk):
        return None
    p0 = enhanced_goertzel(chunk, FREQ_0)
    p1 = enhanced_goertzel(chunk, FREQ_1)
    ratio = max(p1, p0) / (min(p1, p0) + 1e-10)
    if ratio < 1.5:
        return None
    return "1" if p1 > p0 else "0"

# ========== Поиск синхронизации ==========
def find_sync_point(signal, template):
    template_signal = bits_to_signal(template)
    correlation = np.correlate(signal, template_signal, mode='valid')
    if len(correlation) > 0 and np.max(np.abs(correlation)) > 0:
        correlation /= np.max(np.abs(correlation))
    if len(correlation) > 0:
        peak_idx = np.argmax(np.abs(correlation))
        peak_value = np.abs(correlation[peak_idx])

        if peak_value > SYNC_THRESHOLD:
            return peak_idx
    return -1

# ========== Анализ записанного сигнала ==========
def analyze_recording(recording):
    print("\n" + "="*50)
    print("ANALYZING RECORDING")
    print("="*50)

    time_axis = np.arange(len(recording)) / FS

    # --- Figure 0: Original Signal ---
    plt.figure(0, figsize=(12, 4))
    plt.plot(time_axis, recording)
    plt.title("Original Signal", fontsize=14)
    plt.xlabel("Time (s)", fontsize=14)
    plt.ylabel("Amplitude", fontsize=14)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.grid(True)

    # --- Figure 1: Spectrogram ---
    plt.figure(1, figsize=(12, 4))
    plt.specgram(recording, Fs=FS, NFFT=1024, noverlap=512)
    plt.title("Spectrogram", fontsize=14)
    plt.xlabel("Time (s)", fontsize=14)
    plt.ylabel("Frequency (Hz)", fontsize=14)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)

    # --- Детектирование битов ---
    chunk_size = CHUNK_SIZE
    chunks = len(recording) // chunk_size
    bits = []
    energies = []
    goertzel_results = []
    for i in range(chunks):
        chunk = recording[i*chunk_size:(i+1)*chunk_size]
        p0 = goertzel(chunk, FREQ_0)
        p1 = goertzel(chunk, FREQ_1)
        energy = np.sum(np.abs(chunk))
        energies.append(energy)
        goertzel_results.append((p0, p1))
        bits.append("1" if p1 > p0 else "0")

    # --- Figure 2: Chunk Energy ---
    plt.figure(2, figsize=(12, 4))
    plt.plot(energies)
    plt.title(f"Chunk Energy (detected bits: {''.join(bits[:50])}...)", fontsize=14)
    plt.xlabel("Chunk number", fontsize=14)
    plt.ylabel("Energy", fontsize=14)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.grid(True)

    # --- Figure 3: Детальный вид фрагмента ---
    bits_str = ''.join(bits)
    pos = bits_str.find(PREAMBLE)
    if pos != -1:
        start_chunk = pos
        print(f"Showing fragment around preamble at chunk {pos}")
    else:
        start_chunk = int(1.0 * FS / chunk_size)
        print(f"Preamble not found, showing fragment starting from ~1 second (chunk {start_chunk})")

    num_chunks_to_show = min(6, chunks - start_chunk)
    if num_chunks_to_show <= 0:
        print("Not enough chunks to show fragment")
        plt.figure(3, figsize=(12, 4))
        plt.text(0.5, 0.5, "Not enough chunks to show fragment", ha='center', va='center', fontsize=14)
        plt.title("Zoom fragment (insufficient data)", fontsize=14)
    else:
        start_sample = start_chunk * chunk_size
        end_sample = (start_chunk + num_chunks_to_show) * chunk_size
        time_fragment = time_axis[start_sample:end_sample]
        signal_fragment = recording[start_sample:end_sample]

        plt.figure(3, figsize=(12, 4))
        plt.plot(time_fragment, signal_fragment)
        plt.title(f"Zoom: chunks {start_chunk} to {start_chunk + num_chunks_to_show - 1} (bits around preamble)", fontsize=14)
        plt.xlabel("Time (s)", fontsize=14)
        plt.ylabel("Amplitude", fontsize=14)
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
        plt.grid(True)

        for i in range(num_chunks_to_show):
            chunk_start = (start_chunk + i) * chunk_size / FS
            chunk_end = (start_chunk + i + 1) * chunk_size / FS
            plt.axvspan(chunk_start, chunk_end, alpha=0.2, color='gray')
            mid_time = (chunk_start + chunk_end) / 2
            bit_label = bits[start_chunk + i]
            plt.text(mid_time, max(signal_fragment) * 0.9, bit_label,
                     ha='center', va='top', fontsize=14, color='red',
                     bbox=dict(facecolor='white', alpha=0.7))

    plt.show()

    # --- Анализ битовой строки (как и раньше) ---
    print(f"\nDetected {len(bits)} bits")
    if PREAMBLE in bits_str:
        pos = bits_str.find(PREAMBLE)
        print(f"Preamble found at bit position {pos}")
        print(f"Context: ...{bits_str[max(0, pos-20):pos+len(PREAMBLE)+20]}...")
    else:
        print("Preamble not found")

    return bits_str


def create_message_signal(text):
    """Генерирует полный сигнал для текстового сообщения (с преамбулой и служебными полями)."""
    data_bits = text_to_bits(text)
    length_bits = format(len(data_bits), "016b")
    crc = crc16(data_bits)
    frame = START_SEQ + length_bits + data_bits + crc + END_SEQ
    encoded = PREAMBLE + manchester_encode(frame)
    signal = bits_to_signal(encoded)
    return signal


def record_and_analyze(duration=10):
    print(f"Recording {duration} seconds for analysis...")
    recording = sd.rec(int(duration * FS), samplerate=FS, channels=1, dtype='float32')
    sd.wait()
    recording = recording[:, 0]
    np.save("last_recording.npy", recording)
    print("Recording saved to last_recording.npy")
    analyze_recording(recording)

def analyze_signal_from_image(image_data):
    print("Analyzing signal from image...")
    print(f"Raw data: {image_data[:200]}...")
    if PREAMBLE in image_data:
        print(f"Preamble found at position {image_data.find(PREAMBLE)}")
    else:
        print("Preamble not found")
    ones = image_data.count('1')
    zeros = image_data.count('0')
    if ones + zeros > 0:
        print(f"Bit distribution: 1s={ones}, 0s={zeros}, ratio={ones/(ones+zeros):.2f}")
    return image_data


# ========== Отправка файла ==========
def file_to_bits(filename):
    """Читает файл и возвращает битовую строку."""
    with open(filename, 'rb') as f:
        data = f.read()
    bits = ''.join(format(byte, '08b') for byte in data)
    return bits

def bits_to_file(bits, filename):
    """Сохраняет битовую строку в файл."""
    bytes_list = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i+8]
        if len(byte_bits) == 8:
            bytes_list.append(int(byte_bits, 2))
    with open(filename, 'wb') as f:
        f.write(bytes(bytes_list))


def process_received_file_bits(data_bits, output_prefix="received_"):
    if len(data_bits) < 16:
        print("Слишком короткие данные")
        return None
    len_name = int(data_bits[:16], 2)
    if len(data_bits) < 16 + len_name:
        print("Недостаточно данных для имени")
        return None
    name_bits = data_bits[16:16+len_name]
    file_bits = data_bits[16+len_name:]
    original_name = bits_to_text(name_bits)
    output_filename = output_prefix + original_name
    bits_to_file(file_bits, output_filename)
    print(f"Файл сохранён как received_{original_name}")
    return output_filename