import sys
import sounddevice as sd
import time
import os
import numpy as np
from .modem_base import *

# ========== Воспроизведение (стандартное) ==========
def play_signal(signal):
    sd.play(signal, FS)
    sd.wait()

# ========== Общая функция отправки данных ==========
def send_data(data_bits, description="data"):
    length_bits = format(len(data_bits), "016b")
    crc_bits = crc16(data_bits)
    frame = START_SEQ + length_bits + data_bits + crc_bits + END_SEQ
    encoded = PREAMBLE + manchester_encode(frame)
    signal = bits_to_signal(encoded)
    silence = np.zeros(int(FS * 0.5))
    signal = np.concatenate((signal, silence))
    print(f"Sending {description}...")
    play_signal(signal)
    print("Done")


def send_message(text):
    data_bits = text_to_bits(text)
    send_data(data_bits, f"message '{text}'")


def send_file(filename):
    basename = os.path.basename(filename)
    name_bits = text_to_bits(basename)
    length_name = format(len(name_bits), "016b")
    file_bits = file_to_bits(filename)
    combined_bits = length_name + name_bits + file_bits
    send_data(combined_bits, f"file '{filename}'")


# ========== Общая функция приёма данных ==========
def receive_data(data_handler, listen_description="data", stop_event=None):
    chunk_size = int(FS * BIT_DURATION)
    print(f"Listening for {listen_description}...")

    def start_stream():
        s = sd.InputStream(samplerate=FS, channels=1, blocksize=chunk_size)
        s.start()
        return s

    stream = start_stream()
    bit_buffer = ""

    try:
        while True:
            if stop_event and stop_event.is_set():
                break
            chunk, _ = stream.read(chunk_size)
            chunk = chunk[:, 0]
            bit = detect_bit(chunk)
            bit_buffer += bit
            bit_buffer = bit_buffer[-20000:]

            if PREAMBLE in bit_buffer:
                start = bit_buffer.find(PREAMBLE)
                data = bit_buffer[start + len(PREAMBLE):]
                decoded = manchester_decode(data)

                if START_SEQ in decoded:
                    pos = decoded.find(START_SEQ)
                    payload = decoded[pos + len(START_SEQ):]

                    if len(payload) >= 16:
                        length_bits = payload[:16]
                        msg_len = int(length_bits, 2)
                        needed = 16 + msg_len + 16 + len(END_SEQ)

                        if len(payload) >= needed:
                            data_bits = payload[16:16+msg_len]
                            crc_bits = payload[16+msg_len:16+msg_len+16]
                            recv_crc = crc16(data_bits)

                            if crc_bits == recv_crc:
                                data_handler(data_bits)
                            else:
                                print("CRC error")

                            bit_buffer = ""
                            stream.stop()
                            stream.close()
                            time.sleep(0.2)
                            if stop_event and stop_event.is_set():
                                break
                            stream = start_stream()
                            print(f"Listening for next {listen_description}...")
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        stream.close()
        print("Receive stopped.")


# ========== Универсальный приём (текст или файл) ==========
def receive_any(callback_text=None, callback_file=None, stop_event=None):
    def handler(data_bits):
        # Попытка интерпретировать как файл
        try:
            if len(data_bits) >= 16:
                len_name = int(data_bits[:16], 2)
                if len(data_bits) >= 16 + len_name and len_name > 0:
                    name_bits = data_bits[16:16+len_name]
                    # Проверим, что имя состоит из печатных ASCII символов
                    name = bits_to_text(name_bits)
                    if all(32 <= ord(c) <= 126 for c in name):
                        file_bits = data_bits[16+len_name:]
                        if callback_file:
                            callback_file(name, file_bits)
                        return
        except:
            pass

        # Иначе текст
        if callback_text:
            text = bits_to_text(data_bits)
            callback_text(text)

    receive_data(handler, "any data", stop_event)


def receive():
    def handler(data_bits):
        text = bits_to_text(data_bits)
        print("Received:", text)
    receive_data(handler, "message")


def receive_file():
    def handler(data_bits):
        process_received_file_bits(data_bits, output_prefix="received_")
    receive_data(handler, "file")


def send_data_progress(data_bits, description="data", progress_callback=None, stop_event=None):
    length_bits = format(len(data_bits), "016b")
    crc_bits = crc16(data_bits)
    frame = START_SEQ + length_bits + data_bits + crc_bits + END_SEQ
    encoded = PREAMBLE + manchester_encode(frame)
    signal = bits_to_signal(encoded)
    silence = np.zeros(int(FS * 0.5))
    signal = np.concatenate((signal, silence))

    total_samples = len(signal)
    chunk_size = FS // 10  # 100 мс чанки
    num_chunks = (total_samples + chunk_size - 1) // chunk_size

    print(f"Sending {description}...")
    with sd.OutputStream(samplerate=FS, channels=1, dtype='float32') as stream:
        for i in range(num_chunks):
            if stop_event and stop_event.is_set():
                print("Send stopped by user")
                break
            start = i * chunk_size
            end = min(start + chunk_size, total_samples)
            chunk = signal[start:end]
            stream.write(chunk.astype(np.float32))
            if progress_callback:
                progress_callback((i + 1) / num_chunks * 100)
        # Дожидаемся окончания последнего чанка
        time.sleep(0.1)
    if not (stop_event and stop_event.is_set()):
        print("Done")
    else:
        print("Send aborted")

def send_message_progress(text, progress_callback=None, stop_event=None):
    data_bits = text_to_bits(text)
    send_data_progress(data_bits, f"message '{text}'", progress_callback, stop_event)

def send_file_progress(filename, progress_callback=None, stop_event=None):
    basename = os.path.basename(filename)
    name_bits = text_to_bits(basename)
    length_name = format(len(name_bits), "016b")
    file_bits = file_to_bits(filename)
    combined_bits = length_name + name_bits + file_bits
    send_data_progress(combined_bits, f"file '{filename}'", progress_callback, stop_event)


# ========== Точка входа ==========
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python modem.py send                 - Send messages")
        print("  python modem.py receive              - Receive messages")
        print("  python modem.py sendfile <file>      - Send a file")
        print("  python modem.py receivefile          - Receive a file (auto-named)")
        print("  python modem.py analyze <file.npy>   - Analyze recording")
        print("  python modem.py record <seconds>     - Record and analyze")
        sys.exit()

    mode = sys.argv[1]
    if mode == "send":
        msg = input("Enter message: ")
        send_message(msg)
    elif mode == "sendfile" and len(sys.argv) > 2:
        filename = sys.argv[2]
        send_file(filename)
    elif mode == "receive":
        receive()
    elif mode == "receivefile":
        receive_file()
    elif mode == "analyze" and len(sys.argv) > 2:
        recording = np.load(sys.argv[2])
        analyze_recording(recording)
    elif mode == "record":
        duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10
        record_and_analyze(duration)
    else:
        print(f"Unknown mode: {mode}")