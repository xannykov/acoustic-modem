import os
import sys
import time
import numpy as np
import matplotlib.pyplot as plt
import sounddevice as sd
from src import modem_vc, modem_base
from src.modem_config import load_config, update_modem_base

print(sd.query_devices())

VC_INPUT_DEVICE = 2
VC_OUTPUT_DEVICE = 5
REAL_INPUT_DEVICE = None
REAL_OUTPUT_DEVICE = None

TEST_MESSAGE = "Hello World"
NUM_TESTS = 5
AMPLITUDES = [1.0, 0.8, 0.6, 0.4, 0.2, 0.1]

REFERENCE_DIR = "recordings"
os.makedirs(REFERENCE_DIR, exist_ok=True)
REFERENCE_PAYLOAD_TXT = os.path.join(REFERENCE_DIR, "reference_payload.txt")


def generate_reference_signal(amp=None):
    original_amp = modem_base.AMPLITUDE
    if amp is not None:
        modem_base.AMPLITUDE = amp
    print("=== Генерация эталонного сигнала ===")
    data_bits = modem_base.text_to_bits(TEST_MESSAGE)
    length_bits = format(len(data_bits), "016b")
    crc_bits = modem_base.crc16(data_bits)
    frame = modem_base.START_SEQ + length_bits + data_bits + crc_bits + modem_base.END_SEQ
    bits_before = modem_base.PREAMBLE + modem_base.manchester_encode(frame)
    total_bits = len(bits_before)
    signal_duration = total_bits * modem_base.BIT_DURATION
    margin = 3
    record_duration = signal_duration + margin

    print(f"Длительность сигнала: {signal_duration:.2f} сек, запись: {record_duration:.2f} сек")

    modem_vc.OUTPUT_DEVICE = VC_OUTPUT_DEVICE
    try:
        recording = sd.rec(int(record_duration * modem_base.FS),
                           samplerate=modem_base.FS,
                           channels=1,
                           device=VC_INPUT_DEVICE,
                           dtype='float32')
        time.sleep(1)
        modem_vc.send_message(TEST_MESSAGE)
        sd.wait()
        recording = recording[:, 0]

        # Визуализация эталонного сигнала (графики)
        # print("Визуализация эталонного сигнала...")
        # modem_base.analyze_recording(recording)

        # Декодирование и извлечение полезной нагрузки
        bits_after = modem_base.analyze_recording(recording, plot=False)
        payload_bits = extract_payload_bits(bits_after)
        if payload_bits is not None:
            with open(REFERENCE_PAYLOAD_TXT, 'w') as f:
                f.write(payload_bits)
            print(f"Биты полезной нагрузки сохранены в {REFERENCE_PAYLOAD_TXT}")

        decoded_text = decode_message_from_bits(bits_after)
        if decoded_text == TEST_MESSAGE:
            print("Эталонный сигнал декодирован верно.")
        else:
            print(f"Эталонный сигнал декодирован как '{decoded_text}' (ожидалось '{TEST_MESSAGE}')")
    except Exception as e:
        print(f"Ошибка при генерации эталонного сигнала: {e}")
        sys.exit(1)
    finally:
        if amp is not None:
            modem_base.AMPLITUDE = original_amp


def decode_message_from_bits(bits_str):
    if modem_base.PREAMBLE not in bits_str:
        return None
    start = bits_str.find(modem_base.PREAMBLE) + len(modem_base.PREAMBLE)
    data = bits_str[start:]
    decoded = modem_base.manchester_decode(data)
    if modem_base.START_SEQ not in decoded:
        return None
    pos = decoded.find(modem_base.START_SEQ) + len(modem_base.START_SEQ)
    if len(decoded) < pos + 16:
        return None
    msg_len = int(decoded[pos:pos+16], 2)
    if len(decoded) < pos + 16 + msg_len:
        return None
    payload_bits = decoded[pos+16:pos+16+msg_len]
    text = modem_base.bits_to_text(payload_bits)
    return text


def extract_payload_bits(bits_str):
    if modem_base.PREAMBLE not in bits_str:
        return None
    start = bits_str.find(modem_base.PREAMBLE) + len(modem_base.PREAMBLE)
    data = bits_str[start:]
    decoded = modem_base.manchester_decode(data)
    if modem_base.START_SEQ not in decoded:
        return None
    pos = decoded.find(modem_base.START_SEQ) + len(modem_base.START_SEQ)
    if len(decoded) < pos + 16:
        return None
    msg_len = int(decoded[pos:pos+16], 2)
    if len(decoded) < pos + 16 + msg_len:
        return None
    payload_bits = decoded[pos+16:pos+16+msg_len]
    return payload_bits


def run_test(test_number, amp=None):
    if amp is None:
        amp = modem_base.AMPLITUDE
    print(f"\n--- Тест {test_number} (амплитуда {amp}) ---")
    data_bits = modem_base.text_to_bits(TEST_MESSAGE)
    length_bits = format(len(data_bits), "016b")
    crc_bits = modem_base.crc16(data_bits)
    frame = modem_base.START_SEQ + length_bits + data_bits + crc_bits + modem_base.END_SEQ
    bits_before = modem_base.PREAMBLE + modem_base.manchester_encode(frame)
    total_bits = len(bits_before)
    signal_duration = total_bits * modem_base.BIT_DURATION
    margin = 3
    record_duration = signal_duration + margin

    modem_vc.OUTPUT_DEVICE = REAL_OUTPUT_DEVICE
    try:
        recording = sd.rec(int(record_duration * modem_base.FS),
                           samplerate=modem_base.FS,
                           channels=1,
                           device=REAL_INPUT_DEVICE,
                           dtype='float32')
        time.sleep(1)
        modem_vc.send_message(TEST_MESSAGE)
        sd.wait()
        recording = recording[:, 0]
        bits_after = modem_base.analyze_recording(recording, plot=False)
        decoded_text = decode_message_from_bits(bits_after)

        # Загружаем эталонные биты полезной нагрузки
        if not os.path.exists(REFERENCE_PAYLOAD_TXT):
            return False, None, "Эталонные биты не найдены", None

        with open(REFERENCE_PAYLOAD_TXT, 'r') as f:
            ref_payload = f.read().strip()

        test_payload = extract_payload_bits(bits_after)

        if test_payload is None:
            return False, None, "Не удалось извлечь полезную нагрузку", recording

        if len(test_payload) != len(ref_payload):
            return False, None, f"Несовпадение длины: эталон {len(ref_payload)}, получено {len(test_payload)}", recording

        errors = sum(1 for a, b in zip(ref_payload, test_payload) if a != b)
        ber = errors / len(ref_payload) if len(ref_payload) > 0 else 0

        if decoded_text == TEST_MESSAGE:
            return True, ber, f"SUCCESS (BER = {ber*100:.2f}%)", recording
        else:
            return False, ber, f"Текст не совпал: '{decoded_text}' (BER = {ber*100:.2f}%)", recording

    except Exception as e:
        return False, None, f"Ошибка: {e}", None


def test_amplitude_dependence():
    results = {}        # amp -> (ber_mean, success_rate)
    recordings = {}     # amp -> запись сигнала (первая успешная)

    for amp in AMPLITUDES:
        print(f"\n{'='*50}")
        print(f"Тестирование амплитуды: {amp}")
        print(f"{'='*50}")

        generate_reference_signal(amp)

        modem_base.AMPLITUDE = amp

        ber_list = []
        success_count = 0
        amp_recording = None

        for i in range(1, NUM_TESTS + 1):
            success, ber, reason, recording = run_test(i, amp)
            if success and ber is not None:
                success_count += 1
                ber_list.append(ber)
                if amp_recording is None and recording is not None:
                    amp_recording = recording   # сохраняем первую успешную запись
            else:
                ber_list.append(1.0)  # потеря кадра = BER=1.0

        ber_mean = np.mean(ber_list)
        success_rate = success_count / NUM_TESTS

        results[amp] = (ber_mean, success_rate)
        recordings[amp] = amp_recording

        print(f"Результаты для амплитуды {amp}:")
        print(f"  Успешных кадров: {success_count}/{NUM_TESTS} ({success_rate*100:.1f}%)")
        print(f"  Средний BER (с учётом потерянных кадров): {ber_mean*100:.2f}%")

    # ---- Вывод сводной таблицы ----
    print("\n\n=== Сводная таблица результатов ===")
    print(f"{'Амплитуда':<10} {'Успешность (%)':<15} {'Средний BER (%)':<15}")
    print("-" * 45)
    for amp in sorted(results.keys()):
        ber_mean, success_rate = results[amp]
        print(f"{amp:<10} {success_rate*100:<15.1f} {ber_mean*100:<15.2f}")

    # ---- Построение графиков сигнала для каждой амплитуды ----
    valid_amps = [amp for amp in AMPLITUDES if recordings.get(amp) is not None]
    if valid_amps:
        n = len(valid_amps)
        fig, axes = plt.subplots(n, 1, figsize=(10, 3*n), sharex=True)
        if n == 1:
            axes = [axes]
        for i, amp in enumerate(valid_amps):
            rec = recordings[amp]
            time_axis = np.arange(len(rec)) / modem_base.FS
            axes[i].plot(time_axis, rec)
            axes[i].set_title(f"Амплитуда {amp}")
            axes[i].set_ylabel("Амплитуда")
            axes[i].grid(True)
        axes[-1].set_xlabel("Время (с)")
        plt.tight_layout()
        plt.show()
    else:
        print("Нет записей для построения графиков (все тесты провалились).")

    # ---- График BER ----
    amps_sorted = sorted(results.keys())
    ber_vals = [results[a][0] * 100 for a in amps_sorted]

    plt.figure(figsize=(8, 5))
    plt.plot(amps_sorted, ber_vals, 's-', linewidth=2, markersize=8, color='red')
    plt.xlabel('Амплитуда')
    plt.ylabel('Средний BER, %')
    plt.title('Зависимость BER от амплитуды')
    plt.grid(True)
    plt.xlim(min(amps_sorted), max(amps_sorted))
    plt.tight_layout()
    plt.show()


def test_single_run():
    print("=== Оценка ошибок передачи акустического модема (один прогон) ===")
    # Используем текущую амплитуду из modem_base
    generate_reference_signal()  # генерируем эталон с текущей амплитудой
    results = []
    for i in range(1, NUM_TESTS + 1):
        success, ber, reason, _ = run_test(i)
        results.append((i, success, ber, reason))

    print("\n=== Результаты тестов ===")
    print(f"{'Тест':<6} {'Результат':<10} {'BER (%)':<12} {'Причина'}")
    print("-" * 70)
    successful_bers = []
    for test_num, success, ber, reason in results:
        result_str = "SUCCESS" if success else "FAIL"
        ber_str = f"{ber*100:.2f}" if ber is not None else "—"
        print(f"{test_num:<6} {result_str:<10} {ber_str:<12} {reason}")
        if success and ber is not None:
            successful_bers.append(ber)

    total = len(results)
    success_count = sum(1 for _, s, _, _ in results if s)
    frame_error_rate = 1 - (success_count / total) if total > 0 else 0

    print("\n=== Статистика ===")
    print(f"Всего тестов: {total}")
    print(f"Успешных кадров: {success_count}")
    print(f"Frame Error Rate (FER): {frame_error_rate*100:.2f}%")


def main():
    print("Выберите режим тестирования:")
    print("1 - Один прогон (single)")
    print("2 - Зависимость от амплитуды (amplitude)")
    choice = input("Введите номер: ").strip()
    if choice == "1":
        test_single_run()
    elif choice == "2":
        test_amplitude_dependence()
    else:
        print("Неверный выбор")


if __name__ == "__main__":
    main()