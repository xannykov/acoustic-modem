import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. Настраиваем 40-битную структуру
# ==========================================
PREAMBLE = "10101010"  # 8 бит
START_SEQ = "1111"  # 4 бита
DATA_BITS = "1010"  # 4 бита
END_SEQ = "0000"  # 4 бита


def manchester(bits):
    return ''.join("01" if b == "0" else "10" for b in bits)


frame = START_SEQ + DATA_BITS + END_SEQ
encoded_frame = manchester(frame)
full_bits = PREAMBLE + encoded_frame

print(f"Длина данных: {len(DATA_BITS)} бит")
print(f"Длина кадра: {len(frame)} бит")
print(f"После Манчестера: {len(encoded_frame)} бит")
print(f"С преамбулой: {len(full_bits)} бит")
print(f"Битовая строка: {full_bits}")

# ==========================================
# 2. Генерация визуализационного сигнала
# ==========================================
FS_viz = 2000
BIT_DURATION_viz = 0.05  # 50 мс на бит
FREQ_0_viz = 20  # Частота для бита 0
FREQ_1_viz = 60  # Частота для бита 1

signal = []
for bit in full_bits:
    freq = FREQ_1_viz if bit == "1" else FREQ_0_viz
    t = np.linspace(0, BIT_DURATION_viz, int(FS_viz * BIT_DURATION_viz), False)
    tone = np.sin(2 * np.pi * freq * t)
    signal.extend(tone)
signal = np.array(signal)
time_axis = np.arange(len(signal)) / FS_viz

# ==========================================
# 3. Построение графика
# ==========================================
t_preamble_end = len(PREAMBLE) * BIT_DURATION_viz
t_start_end = t_preamble_end + len(manchester(START_SEQ)) * BIT_DURATION_viz
t_payload_end = t_start_end + len(manchester(DATA_BITS)) * BIT_DURATION_viz
t_end_end = t_payload_end + len(manchester(END_SEQ)) * BIT_DURATION_viz

plt.figure(figsize=(9, 9))
plt.plot(time_axis, signal, color='blue', alpha=0.5, linewidth=2)

plt.axvspan(0, t_preamble_end, color='lightblue', alpha=0.5, label='Preamble (8 бит)')
plt.axvspan(t_preamble_end, t_start_end, color='lightgreen', alpha=0.5, label='Start (8 бит)')
plt.axvspan(t_start_end, t_payload_end, color='lightyellow', alpha=0.9, label='Payload (8 бит)')
plt.axvspan(t_payload_end, t_end_end, color='lightcoral', alpha=0.5, label='End (8 бит)')

plt.title("Структура сигнала (32 бит)", fontsize=14)
plt.xlabel("Время (с)", fontsize=14)
plt.ylabel("Амплитуда", fontsize=14)
plt.xlim(0, t_end_end)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(loc='upper right', fontsize=14)

for i, bit in enumerate(full_bits):
    mid_time = (i + 0.5) * BIT_DURATION_viz
    plt.axvline(i * BIT_DURATION_viz, color='gray', linestyle=':', alpha=1)
    plt.text(mid_time, -1.1, bit, ha='center', va='bottom',
             fontsize=14, color='black', fontweight='bold')

plt.axvline(len(full_bits) * BIT_DURATION_viz, color='gray', linestyle=':', alpha=1)

plt.ylim(-1.2, 1.2)

plt.tight_layout()
plt.show()