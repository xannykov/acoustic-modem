import numpy as np
import matplotlib.pyplot as plt

fs = 1000          # Частота дискретизации (Гц)
bit_dur = 0.5      # Длительность одного бита (сек)
fc = 5             # Несущая частота (Гц)
f0 = 3             # Частота для '0' в FSK (Гц)
f1 = 7             # Частота для '1' в FSK (Гц)
bits = [1, 0, 1, 1, 0]

# Время и развернутая битовая последовательность
t = np.linspace(0, len(bits) * bit_dur, int(fs * len(bits) * bit_dur), endpoint=False)
bits_expanded = np.repeat(bits, int(fs * bit_dur))

# --- ASK (Amplitude Shift Keying) ---
ask_signal = bits_expanded * np.sin(2 * np.pi * fc * t)

# --- FSK (Frequency Shift Keying) ---
freq = np.where(bits_expanded == 1, f1, f0)
phase_fsk = 2 * np.pi * np.cumsum(freq) / fs
fsk_signal = np.sin(phase_fsk)

# --- PSK (Phase Shift Keying) ---
phase_shift = np.where(bits_expanded == 1, 0, np.pi)
psk_signal = np.sin(2 * np.pi * fc * t + phase_shift)

# --- Построение графиков ---
fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)

# Границы битов и настройка оси X
for ax in axes:
    ax.tick_params(labelbottom=True, labelsize=14)
    ax.set_xticks(np.arange(0, len(bits) * bit_dur + 0.1, bit_dur))
    for i in range(1, len(bits)):
        ax.axvline(i * bit_dur, color='red', linestyle='--', alpha=0.5)

# ASK
axes[0].plot(t, ask_signal, color='#1f77b4')
axes[0].set_title(f"ASK (Amplitude Shift Keying)\nБиты: {bits}", fontsize=14)
axes[0].set_ylabel("Амплитуда", fontsize=14)
axes[0].set_xlabel("Время (с)", fontsize=14)
axes[0].grid(True)

# FSK
axes[1].plot(t, fsk_signal, color='#ff7f0e')
axes[1].set_title(f"FSK (Frequency Shift Keying)\nБиты: {bits}", fontsize=14)
axes[1].set_ylabel("Амплитуда", fontsize=14)
axes[1].set_xlabel("Время (с)", fontsize=14)
axes[1].grid(True)

# PSK
axes[2].plot(t, psk_signal, color='#2ca02c')
axes[2].set_title(f"PSK (Phase Shift Keying)\nБиты: {bits}", fontsize=14)
axes[2].set_ylabel("Амплитуда", fontsize=14)
axes[2].set_xlabel("Время (с)", fontsize=14)
axes[2].grid(True)

plt.tight_layout()
plt.show()