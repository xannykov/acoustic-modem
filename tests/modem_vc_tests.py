import os
import sys
import sounddevice as sd
import numpy as np
from src import modem_vc, modem_base
import time

# Определяем корневую папку проекта (где находится папка src)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
RECORDINGS_DIR = os.path.join(BASE_DIR, 'recordings')
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Конфигурация устройств
INPUT_DEVICE = 1
OUTPUT_DEVICE = 5

# Тестовые данные с абсолютными путями
TEST_MESSAGES = ["HELLO WORLD"]
TEST_IMAGE = os.path.join(DATA_DIR, "img.png")
TEST_TEXT_FILE = os.path.join(DATA_DIR, "test.txt")

def run_test(data_source, data_type, output_name=None):
    inp_dev, out_dev = INPUT_DEVICE, OUTPUT_DEVICE
    fs = modem_base.FS

    print(f"--- Начинаем тест ({data_type}) ---")
    print(f"Запись (Input): {sd.query_devices(inp_dev)['name']}")
    print(f"Вывод (Output): {sd.query_devices(out_dev)['name']}")

    # Преобразование данных в биты
    if data_type == 'text':
        data_bits = modem_base.text_to_bits(data_source)
        source_info = f"Сообщение: '{data_source}'"
    elif data_type == 'file':
        if not os.path.exists(data_source):
            print(f"Ошибка: файл {data_source} не найден!")
            return
        data_bits = modem_base.file_to_bits(data_source)
        source_info = f"Файл: {data_source} (размер: {os.path.getsize(data_source)} байт)"
    else:
        print("Неизвестный тип данных")
        return

    length_bits = format(len(data_bits), "016b")
    crc_bits = modem_base.crc16(data_bits)

    frame = modem_base.START_SEQ + length_bits + data_bits + crc_bits + modem_base.END_SEQ
    bits_before = modem_base.PREAMBLE + modem_base.manchester_encode(frame)

    total_bits_count = len(bits_before)
    pure_signal_duration = total_bits_count * modem_vc.BIT_DURATION
    margin = 3
    dynamic_duration = pure_signal_duration + margin

    print(f"\n[ИНФО] {source_info}")
    print(f"[ИНФО] Всего бит для передачи: {total_bits_count}")
    print(f"[ИНФО] Чистое время сигнала: {pure_signal_duration:.2f} сек.")
    print(f"[ИНФО] Установленная длительность записи: {dynamic_duration:.2f} сек.")

    # Запись
    try:
        recording = sd.rec(int(dynamic_duration * fs), samplerate=fs, channels=2, device=inp_dev)
    except Exception:
        recording = sd.rec(int(dynamic_duration * fs), samplerate=fs, channels=1, device=inp_dev)

    time.sleep(1)

    # Отправка
    modem_vc.OUTPUT_DEVICE = out_dev
    print(f"\n")
    if data_type == 'text':
        modem_vc.send_message(data_source)
    else:
        modem_vc.send_file(data_source)

    print("Ожидание завершения записи...")
    sd.wait()

    # Обработка записи
    clean_signal = recording[:, 0] if recording.shape[1] > 1 else recording.flatten()
    # Сохраняем в папку recordings
    signal_path = os.path.join(RECORDINGS_DIR, "clean_signal.npy")
    np.save(signal_path, clean_signal)
    print(f"Запись сохранена в {signal_path} (размер: {clean_signal.shape[0]} семплов)")

    # Анализ
    print("\n--- Анализ полученного сигнала ---")
    bits_after = modem_base.analyze_recording(clean_signal)

    print(f"\n[ПОСЛЕ] Длина массива распознанных бит: {len(bits_after)}")

    # Декодирование
    if modem_base.PREAMBLE in bits_after:
        start_idx = bits_after.find(modem_base.PREAMBLE) + len(modem_base.PREAMBLE)
        data = bits_after[start_idx:]
        decoded_frame = modem_base.manchester_decode(data)

        if modem_base.START_SEQ in decoded_frame:
            pos = decoded_frame.find(modem_base.START_SEQ) + len(modem_base.START_SEQ)
            if len(decoded_frame) >= pos + 16:
                msg_len = int(decoded_frame[pos:pos+16], 2)
                payload_bits = decoded_frame[pos+16:pos+16+msg_len]

                if data_type == 'text':
                    final_text = modem_base.bits_to_text(payload_bits)
                    print(f"\nПолученное сообщение: {final_text}")
                else:  # file
                    saved_name = modem_base.process_received_file_bits(payload_bits, output_prefix=os.path.join(DATA_DIR, "received_"))
                    if saved_name and os.path.exists(saved_name):
                        print(f"   Размер: {os.path.getsize(saved_name)} байт")
            else:
                print("Недостаточно данных для декодирования")
        else:
            print("START_SEQ не найден")
    else:
        print("Преамбула не найдена")

def main():
    print("Выберите тип теста:")
    print("1 - Текстовое сообщение")
    print("2 - Файл (изображение, текст и т.д.)")
    choice = input("Введите номер: ").strip()

    if choice == '1':
        msg = TEST_MESSAGES[0]
        run_test(msg, 'text')
    elif choice == '2':
        print("Доступные тестовые файлы:")
        print(f"1 - {TEST_IMAGE}")
        print(f"2 - {TEST_TEXT_FILE}")
        file_choice = input("Выберите номер файла: ").strip()
        if file_choice == '1':
            filename = TEST_IMAGE
        elif file_choice == '2':
            filename = TEST_TEXT_FILE
        else:
            print("Неверный выбор")
            return
        run_test(filename, 'file')
    else:
        print("Неверный выбор")

if __name__ == "__main__":
    main()