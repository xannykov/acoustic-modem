import sys
import os
import sounddevice as sd
import time
import numpy as np
from .modem_base import *
import matplotlib.pyplot as plt

# ========== Настройки устройств ==========
INPUT_DEVICE = 1
OUTPUT_DEVICE = 5


# ========== Воспроизведение через виртуальный кабель ==========
def play_signal(signal):
    with sd.OutputStream(
            samplerate=FS,
            channels=1,
            device=OUTPUT_DEVICE,
            dtype='float32'
    ) as stream:
        stream.write(signal.astype(np.float32))


# ========== Общая функция отправки данных ==========
def send_data(data_bits, description="data"):
    length_bits = format(len(data_bits), "016b")
    crc_bits = crc16(data_bits)
    frame = START_SEQ + length_bits + data_bits + crc_bits + END_SEQ
    encoded = PREAMBLE + manchester_encode(frame)
    signal = bits_to_signal(encoded)
    silence = np.zeros(int(FS * 0.5))
    signal = np.concatenate((signal, silence))
    print(f"Отправка {description}...")
    time.sleep(0.5)
    play_signal(signal)
    print("Выполнено!")


def send_message(text):
    data_bits = text_to_bits(text)
    send_data(data_bits, f"сообщения: '{text}'")


def send_file(filename):
    basename = os.path.basename(filename)
    name_bits = text_to_bits(basename)
    length_name = format(len(name_bits), "016b")
    data_bits = file_to_bits(filename)
    # Объединяем: длина имени + имя + данные
    combined_bits = length_name + name_bits + data_bits
    send_data(combined_bits, f"файла: '{filename}'")


# ========== Общая функция приёма данных ==========
def receive_data(data_handler, listen_description="data"):
    chunk_size = int(FS * BIT_DURATION)
    print(f"Слушаю {listen_description}...")

    def start_stream():
        s = sd.InputStream(
            samplerate=FS,
            channels=1,
            device=INPUT_DEVICE,
            blocksize=chunk_size,
            dtype='float32'
        )
        s.start()
        return s

    stream = start_stream()
    bit_buffer = ""

    try:
        while True:
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
                            stream = start_stream()
                            print(f"Слушаю {listen_description}...")
    except KeyboardInterrupt:
        stream.stop()
        stream.close()


def receive():
    def handler(data_bits):
        text = bits_to_text(data_bits)
        print("Прослушано:", text)
    receive_data(handler, "сообщение")


def receive_file():
    def handler(data_bits):
        process_received_file_bits(data_bits, output_prefix="received_")
    receive_data(handler, "файл")


# ========== Точка входа ==========
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python modem_vc.py send                 - Send messages")
        print("  python modem_vc.py receive              - Receive (original)")
        print("  python modem_vc.py sendfile <file>      - Send a file")
        print("  python modem_vc.py receivefile          - Receive a file (auto-named)")
        print("  python modem_vc.py analyze <file.npy>   - Analyze recording")
        print("  python modem_vc.py record <seconds>     - Record and analyze")
        sys.exit()

    mode = sys.argv[1]
    if mode == "send":
        while True:
            msg = input("Введите сообщение: ")
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