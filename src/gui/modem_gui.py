import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import time as time_module
import sounddevice as sd
from src import modem_base
from src.modem_controller import ModemController
from src.modem_config import load_config, save_config, update_modem_base


class ModemApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AcousticModem v2.0")
        self.geometry("950x650")
        self.minsize(850, 600)

        self.theme_map = {
            "Светлая": "Light",
            "Тёмная": "Dark",
            "Системная": "System"
        }
        self.reverse_theme_map = {v: k for k, v in self.theme_map.items()}

        # Загружаем конфигурацию
        self.config = load_config()
        appearance = self.config.get('APPEARANCE_MODE', 'System')
        ctk.set_appearance_mode(appearance)
        ctk.set_default_color_theme("blue")

        update_modem_base(self.config)

        # Создаём контроллер
        self.controller = ModemController()

        # Переменные для отправки
        self.send_start_time = None
        self.send_timer_id = None
        self.was_listening_before_send = False
        self.selected_file = None
        self.send_stopped_by_user = False

        # Настройка сетки окна
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.create_sidebar()
        self.create_transfer_frame()
        self.create_settings_frame()

        self.select_frame_by_name("transfer")
        self.check_devices()
        self.start_listening()

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Акустический\nмодем",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.btn_transfer = ctk.CTkButton(
            self.sidebar,
            text="📨 Передача",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=16),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self.select_frame_by_name("transfer")
        )
        self.btn_transfer.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.btn_settings = ctk.CTkButton(
            self.sidebar,
            text="⚙️ Настройки",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=16),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            command=lambda: self.select_frame_by_name("settings")
        )
        self.btn_settings.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="🟢 Слушаю эфир",
            text_color="green",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=16)
        )

        self.status_label.grid(row=5, column=0, padx=20, pady=20, sticky="w")

    def create_transfer_frame(self):
        self.transfer_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.transfer_frame.grid_columnconfigure(0, weight=1)
        self.transfer_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            self.transfer_frame,
            text="Передача данных",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.chat_log = ctk.CTkTextbox(
            self.transfer_frame,
            state="disabled",
            wrap="word",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=14),
        )
        self.chat_log.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")

        input_panel = ctk.CTkFrame(self.transfer_frame, fg_color="transparent")
        input_panel.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        input_panel.grid_columnconfigure(1, weight=1)

        self.btn_attach = ctk.CTkButton(
            input_panel,
            text="📁",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=14),
            anchor='center',
            width=40,
            fg_color="transparent",
            border_width=1,
            text_color=("black", "white"),
            command=self.choose_file
        )
        self.btn_attach.grid(row=0, column=0, padx=(0, 10))

        self.msg_entry = ctk.CTkEntry(
            input_panel,
            placeholder_text="Введите сообщение или выберите файл..."
        )
        self.msg_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.msg_entry.bind("<KeyRelease>", lambda event: self.update_estimate_from_text())

        self.btn_send = ctk.CTkButton(
            input_panel,
            text="➡️ Отправить",
            width=120,
            height=30,
            fg_color="transparent",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=14),
            border_width=1,
            text_color=("black", "white"),
            text_color_disabled=("gray50", "gray50"),
            command=self.send
        )
        self.btn_send.grid(row=0, column=2)

        self.btn_stop_send = ctk.CTkButton(
            input_panel,
            text="⏹️ Остановить",
            width=120,
            height=30,
            fg_color="transparent",
            font=ctk.CTkFont(family="Segoe UI Emoji", size=14),
            border_width=1,
            text_color=("black", "white"),
            text_color_disabled=("gray50", "gray50"),
            command=self.stop_send,
            state="disabled"
        )
        self.btn_stop_send.grid(row=0, column=3, padx=(10, 0))

        self.progress = ctk.CTkProgressBar(self.transfer_frame, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=2, padx=20, pady=(5, 0), sticky="ew")
        self.progress.set(0)

        info_frame = ctk.CTkFrame(self.transfer_frame, fg_color="transparent")
        info_frame.grid(row=4, column=0, columnspan=2, padx=20, pady=(5, 10), sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_columnconfigure(1, weight=1)

        self.estimate_label = ctk.CTkLabel(info_frame, text="⏱️ Оценочное время: —")
        self.estimate_label.grid(row=0, column=0, sticky="w")

        self.timer_label = ctk.CTkLabel(info_frame, text="⌛ Прошло: 0.0 с")
        self.timer_label.grid(row=0, column=1, sticky="e")

        self.send_status = ctk.CTkLabel(self.transfer_frame, text="")
        self.send_status.grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 10))

    def create_settings_frame(self):
        """Создаёт окно настроек (без прокрутки)"""
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame.grid_columnconfigure(0, weight=1)

        # Заголовок
        header = ctk.CTkLabel(
            self.settings_frame,
            text="Настройки",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Основной контейнер для параметров
        params_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        params_frame.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        params_frame.grid_columnconfigure(1, weight=1)

        # Словарь для переменных настроек
        self.settings_vars = {}
        row = 0

        # Тема оформления
        ctk.CTkLabel(params_frame, text="Тема оформления:").grid(row=row, column=0, sticky="w", pady=8)
        current_theme = self.config.get('APPEARANCE_MODE', 'System')
        self.appearance_var = ctk.StringVar(value=self.reverse_theme_map[current_theme])
        self.appearance_combo = ctk.CTkComboBox(
            params_frame,
            values=["Светлая", "Тёмная", "Системная"],
            variable=self.appearance_var,
            width=200,
            command=self.change_appearance
        )
        self.appearance_combo.grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # FS
        ctk.CTkLabel(params_frame, text="Частота дискретизации (Гц):").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['FS'] = ctk.IntVar(value=self.config['FS'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['FS'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # BIT_DURATION
        ctk.CTkLabel(params_frame, text="Длительность бита (с):").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['BIT_DURATION'] = ctk.DoubleVar(value=self.config['BIT_DURATION'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['BIT_DURATION'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # FREQ_0
        ctk.CTkLabel(params_frame, text="Частота для 0 (Гц):").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['FREQ_0'] = ctk.IntVar(value=self.config['FREQ_0'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['FREQ_0'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # FREQ_1
        ctk.CTkLabel(params_frame, text="Частота для 1 (Гц):").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['FREQ_1'] = ctk.IntVar(value=self.config['FREQ_1'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['FREQ_1'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # ENERGY_THRESHOLD
        ctk.CTkLabel(params_frame, text="Порог энергии:").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['ENERGY_THRESHOLD'] = ctk.DoubleVar(value=self.config['ENERGY_THRESHOLD'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['ENERGY_THRESHOLD'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # SYNC_THRESHOLD
        ctk.CTkLabel(params_frame, text="Порог синхронизации:").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['SYNC_THRESHOLD'] = ctk.DoubleVar(value=self.config['SYNC_THRESHOLD'])
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['SYNC_THRESHOLD'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # PREAMBLE_LEN
        ctk.CTkLabel(params_frame, text="Длина преамбулы (пар 10):").grid(row=row, column=0, sticky="w", pady=8)
        self.settings_vars['PREAMBLE_LEN'] = ctk.IntVar(value=self.config.get('PREAMBLE_LEN', 16))
        ctk.CTkEntry(params_frame, textvariable=self.settings_vars['PREAMBLE_LEN'], width=150).grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # Устройства ввода/вывода
        ctk.CTkLabel(params_frame, text="Устройство ввода (микрофон):").grid(row=row, column=0, sticky="w", pady=8)
        self.input_device_var = ctk.StringVar(value="По умолчанию")
        self.input_combo = ctk.CTkComboBox(params_frame, variable=self.input_device_var, width=300)
        self.input_combo.grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        ctk.CTkLabel(params_frame, text="Устройство вывода (динамики):").grid(row=row, column=0, sticky="w", pady=8)
        self.output_device_var = ctk.StringVar(value="По умолчанию")
        self.output_combo = ctk.CTkComboBox(params_frame, variable=self.output_device_var, width=300)
        self.output_combo.grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # Папка сохранения
        ctk.CTkLabel(params_frame, text="Папка для сохранения файлов:").grid(row=row, column=0, sticky="w", pady=8)
        folder_frame = ctk.CTkFrame(params_frame, fg_color="transparent")
        folder_frame.grid(row=row, column=1, padx=10, pady=8, sticky="ew")
        folder_frame.grid_columnconfigure(0, weight=1)

        self.save_folder_var = ctk.StringVar(
            value=self.config.get('SAVE_FOLDER', os.path.join(os.path.expanduser("~"), "Downloads"))
        )
        ctk.CTkEntry(folder_frame, textvariable=self.save_folder_var, state="readonly").grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(folder_frame, text="Обзор", command=self.choose_save_folder, width=80).grid(row=0, column=1)
        row += 1

        # Кнопка сохранения
        ctk.CTkButton(params_frame, text="Сохранить настройки", command=self.save_settings).grid(row=row, column=0, columnspan=2, pady=25)

        # Заполняем список устройств
        self.refresh_devices()

    def change_appearance(self, choice):
        ctk.set_appearance_mode(self.theme_map[choice])

    def select_frame_by_name(self, name):
        """Переключает видимый фрейм (transfer/settings)"""
        self.btn_transfer.configure(fg_color=("gray75", "gray25") if name == "transfer" else "transparent")
        self.btn_settings.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")

        if name == "transfer":
            self.settings_frame.grid_forget()
            self.transfer_frame.grid(row=0, column=1, sticky="nsew")
        elif name == "settings":
            self.transfer_frame.grid_forget()
            self.settings_frame.grid(row=0, column=1, sticky="nsew")

    # ---------- Проверка устройств ----------
    def check_devices(self):
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            output_devices = [d for d in devices if d['max_output_channels'] > 0]
            if not input_devices:
                messagebox.showwarning("Предупреждение", "Не найдено устройств ввода (микрофон).")
            if not output_devices:
                messagebox.showwarning("Предупреждение", "Не найдено устройств вывода (динамики).")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить список устройств: {e}")

    # ---------- Устройства ----------
    def refresh_devices(self):
        try:
            devices = sd.query_devices()
            inputs = ["По умолчанию"] + [f"{i}: {d['name']}" for i, d in enumerate(devices) if d['max_input_channels'] > 0]
            outputs = ["По умолчанию"] + [f"{i}: {d['name']}" for i, d in enumerate(devices) if d['max_output_channels'] > 0]

            self.input_combo.configure(values=inputs)
            self.output_combo.configure(values=outputs)
            self.input_combo.set(inputs[0])
            self.output_combo.set(outputs[0])
        except Exception as e:
            print(f"Ошибка получения устройств: {e}")

    # ---------- Настройки ----------
    def choose_save_folder(self):
        folder = filedialog.askdirectory(initialdir=self.save_folder_var.get())
        if folder:
            self.save_folder_var.set(folder)

    def save_settings(self):
        try:
            new_config = {}
            for key, var in self.settings_vars.items():
                new_config[key] = var.get()

            new_config['APPEARANCE_MODE'] = self.theme_map[self.appearance_var.get()]

            new_config['SAVE_FOLDER'] = self.save_folder_var.get()
            inp = self.input_combo.get()
            out = self.output_combo.get()
            new_config['INPUT_DEVICE'] = None if inp == "По умолчанию" else int(inp.split(':')[0])
            new_config['OUTPUT_DEVICE'] = None if out == "По умолчанию" else int(out.split(':')[0])

            save_config(new_config)
            update_modem_base(new_config)
            self.config = new_config
            messagebox.showinfo("Успех", "Настройки сохранены.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {e}")

    # ---------- Логика лога ----------
    def append_log(self, text, is_sender=False, is_system=False):
        self.chat_log.configure(state="normal")
        if is_system:
            self.chat_log.insert("end", f"⚙️ {text}\n\n")
        elif is_sender:
            self.chat_log.insert("end", f"Вы: {text}\n\n")
        else:
            self.chat_log.insert("end", f"Собеседник: {text}\n\n")
        self.chat_log.configure(state="disabled")
        self.chat_log.yview("end")

    # ---------- Отправка ----------
    def choose_file(self):
        """Выбор файла без немедленной отправки"""
        filepath = filedialog.askopenfilename()
        if filepath:
            self.selected_file = filepath
            filename = os.path.basename(filepath)
            self.msg_entry.delete(0, 'end')
            self.msg_entry.insert(0, f"[Файл: {filename}]")
            self.update_estimate_from_file(filepath)

    def update_estimate_from_text(self):
        """Обновляет оценку времени на основе текста в поле ввода"""
        text = self.msg_entry.get().strip()
        if text and not text.startswith("[Файл:"):  # если это не метка файла
            duration = self.calculate_duration_estimate("text", text)
            if duration:
                self.estimate_label.configure(text=f"⏱️ Оценочное время: {self.format_time(duration)}")
            else:
                self.estimate_label.configure(text="⏱️ Оценочное время: —")
        else:
            self.estimate_label.configure(text="⏱️ Оценочное время: —")

    def update_estimate_from_file(self, filepath):
        """Обновляет оценку времени на основе выбранного файла"""
        duration = self.calculate_duration_estimate("file", filepath)
        if duration:
            self.estimate_label.configure(text=f"⏱️ Оценочное время: {self.format_time(duration)}")
        else:
            self.estimate_label.configure(text="⏱️ Оценочное время: —")

    def calculate_duration_estimate(self, data_type, value):
        try:
            if data_type == "text":
                data_bits = modem_base.text_to_bits(value)
            else:
                basename = os.path.basename(value)
                name_bits = modem_base.text_to_bits(basename)
                length_name = format(len(name_bits), "016b")
                file_bits = modem_base.file_to_bits(value)
                data_bits = length_name + name_bits + file_bits

            length_bits = format(len(data_bits), "016b")
            crc_bits = modem_base.crc16(data_bits)
            frame = modem_base.START_SEQ + length_bits + data_bits + crc_bits + modem_base.END_SEQ
            encoded = modem_base.PREAMBLE + modem_base.manchester_encode(frame)
            total_bits = len(encoded)
            duration = total_bits * modem_base.BIT_DURATION + 0.5
            return duration
        except Exception:
            return None

    def format_time(self, seconds):
        if seconds < 0:
            return "—"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        parts = []
        if hours > 0:
            parts.append(f"{hours} ч")
        if minutes > 0 or hours > 0:
            parts.append(f"{minutes} мин")
        parts.append(f"{secs:.1f} с")
        return " ".join(parts)

    def send(self):
        """Отправляет либо текст, либо выбранный файл"""
        self.send_stopped_by_user = False
        # Блокируем кнопки
        self.btn_send.configure(state="disabled")
        self.btn_stop_send.configure(state="normal")
        self.btn_attach.configure(state="disabled")

        # Останавливаем прослушивание, если оно активно
        if self.controller.is_listening:
            self.was_listening_before_send = True
            self.controller.stop_listen()
            self.status_label.configure(text="🟡 Прослушивание приостановлено", text_color="orange")
        else:
            self.was_listening_before_send = False

        # Определяем, что отправляем
        if self.selected_file:
            filepath = self.selected_file
            filename = os.path.basename(filepath)
            self.append_log(f"[Файл отправлен: {filename}]", is_sender=True)
            self.controller.send(
                data_type="file",
                text=None,
                filepath=filepath,
                progress_cb=self.on_send_progress,
                timer_cb=None,
                finished_cb=self.on_send_finished
            )
        else:
            text = self.msg_entry.get().strip()
            if not text:
                self.on_send_finished(False, "Нет данных для отправки")
                return
            self.append_log(text, is_sender=True)
            self.controller.send(
                data_type="text",
                text=text,
                filepath=None,
                progress_cb=self.on_send_progress,
                timer_cb=None,
                finished_cb=self.on_send_finished
            )

        self.status_label.configure(text="🟡 Передача...", text_color="orange")
        self.send_start_time = time_module.time()
        self.update_timer()

    def on_send_progress(self, percent):
        if self.send_stopped_by_user:
            return
        self.progress.set(percent / 100)

    def on_send_finished(self, success, error_msg):
        if self.send_stopped_by_user:
            return

        # Разблокируем кнопки
        self.btn_send.configure(state="normal")
        self.btn_stop_send.configure(state="disabled")
        self.btn_attach.configure(state="normal")

        # Очищаем выбранный файл и поле ввода
        self.selected_file = None
        self.msg_entry.delete(0, 'end')

        if success:
            self.append_log("Сигнал успешно отправлен.", is_system=True)
            self.status_label.configure(
                text="🟢 Слушаю эфир" if self.was_listening_before_send else "🟡 Прослушивание остановлено",
                text_color="green" if self.was_listening_before_send else "orange"
            )
        else:
            self.append_log(f"Ошибка: {error_msg}", is_system=True)
            self.status_label.configure(text="🔴 Ошибка отправки", text_color="red")

        # Восстанавливаем прослушивание, если оно было активно до отправки
        if self.was_listening_before_send and not self.controller.is_listening:
            self.start_listening()
            self.status_label.configure(text="🟢 Слушаю эфир", text_color="green")

        self.send_start_time = None
        if self.send_timer_id:
            self.after_cancel(self.send_timer_id)
            self.send_timer_id = None
        self.progress.set(0)
        self.estimate_label.configure(text="⏱️ Оценочное время: —")
        self.timer_label.configure(text="⌛ Прошло: 0.0 с")

    def stop_send(self):
        self.send_stopped_by_user = True
        self.controller.stop_send()

        # Останавливаем таймер
        if self.send_timer_id:
            self.after_cancel(self.send_timer_id)
            self.send_timer_id = None
        self.send_start_time = None

        # Сбрасываем прогресс и оценки
        self.progress.set(0)
        self.estimate_label.configure(text="⏱️ Оценочное время: —")
        self.timer_label.configure(text="⌛ Прошло: 0.0 с")

        self.msg_entry.delete(0, 'end')

        # Разблокируем кнопки
        self.btn_send.configure(state="normal")
        self.btn_stop_send.configure(state="disabled")
        self.btn_attach.configure(state="normal")

        # Восстанавливаем прослушивание, если оно было активно до отправки
        if self.was_listening_before_send and not self.controller.is_listening:
            self.start_listening()
            self.status_label.configure(text="🟢 Слушаю эфир", text_color="green")
        else:
            self.status_label.configure(text="🟡 Прослушивание остановлено", text_color="orange")
        self.append_log("Отправление приостановлено.", is_system=True)

    def update_timer(self):
        if self.send_start_time is None:
            return
        elapsed = time_module.time() - self.send_start_time
        self.timer_label.configure(text=f"⌛ Прошло: {self.format_time(elapsed)}")
        self.send_timer_id = self.after(100, self.update_timer)

    # ========== Приём ==========
    def start_listening(self):
        folder = self.config.get('SAVE_FOLDER', os.path.join(os.path.expanduser("~"), "Downloads"))
        os.makedirs(folder, exist_ok=True)
        self.controller.start_listen(
            save_folder=folder,
            text_callback=self.on_receive_text,
            file_callback=self.on_receive_file
        )
        self.status_label.configure(text="🟢 Слушаю эфир", text_color="green")

    def on_receive_text(self, text):
        self.append_log(text, is_sender=False)

    def on_receive_file(self, filename):
        self.append_log(f"[Файл получен: {filename}]", is_sender=False)

def main():
    app = ModemApp()
    app.mainloop()

if __name__ == "__main__":
    main()