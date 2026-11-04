import threading
import time
import os
import sounddevice as sd
from src import modem, modem_base

class ModemController:
    def __init__(self):
        # Отправка
        self.send_stop_event = None
        self.send_thread = None
        self.send_start_time = None
        self.send_progress_callback = None
        self.send_timer_callback = None
        self.send_finished_callback = None

        # Приём
        self.listen_stop_event = None
        self.listen_thread = None
        self.is_listening = False
        self.receive_text_callback = None
        self.receive_file_callback = None

    # ========== Отправка ==========
    def send(self, data_type, text, filepath, progress_cb, timer_cb, finished_cb):
        """Запускает отправку в отдельном потоке."""
        self.send_progress_callback = progress_cb
        self.send_timer_callback = timer_cb
        self.send_finished_callback = finished_cb
        self.send_start_time = time.time()
        self.send_stop_event = threading.Event()
        self.send_thread = threading.Thread(
            target=self._send_task,
            args=(data_type, text, filepath),
            daemon=True
        )
        self.send_thread.start()

    def _send_task(self, data_type, text, filepath):
        def progress_callback(percent):
            if self.send_progress_callback:
                self.send_progress_callback(percent)

        success = False
        error_msg = None
        try:
            if data_type == "text":
                if not text:
                    error_msg = "Введите текст сообщения"
                else:
                    modem.send_message_progress(text, progress_callback, self.send_stop_event)
                    success = True
            else:
                if not filepath or not os.path.exists(filepath):
                    error_msg = "Выберите существующий файл"
                else:
                    modem.send_file_progress(filepath, progress_callback, self.send_stop_event)
                    success = True
        except Exception as e:
            error_msg = str(e)

        if self.send_finished_callback:
            self.send_finished_callback(success, error_msg)

    def stop_send(self):
        """Прерывает отправку."""
        if self.send_stop_event:
            self.send_stop_event.set()
            sd.stop()  # Немедленно останавливает звук

    def get_elapsed_time(self):
        """Возвращает время, прошедшее с начала отправки."""
        if self.send_start_time:
            return time.time() - self.send_start_time
        return 0

    # ========== Приём ==========
    def start_listen(self, save_folder, text_callback, file_callback):
        """Запускает прослушивание в отдельном потоке."""
        self.receive_text_callback = text_callback
        self.receive_file_callback = file_callback
        self.is_listening = True
        self.listen_stop_event = threading.Event()
        self.listen_thread = threading.Thread(
            target=self._listen_task,
            args=(save_folder,),
            daemon=True
        )
        self.listen_thread.start()

    def _listen_task(self, save_folder):
        def on_text(text):
            if self.receive_text_callback:
                self.receive_text_callback(text)

        def on_file(name, file_bits):
            # Сохраняем файл в указанную папку
            safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")
            filepath = os.path.join(save_folder, safe_name)
            base, ext = os.path.splitext(filepath)
            counter = 1
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{ext}"
                counter += 1
            try:
                modem_base.bits_to_file(file_bits, filepath)
                if self.receive_file_callback:
                    self.receive_file_callback(os.path.basename(filepath))
            except Exception as e:
                print(f"Ошибка сохранения файла: {e}")

        try:
            modem.receive_any(
                callback_text=on_text,
                callback_file=on_file,
                stop_event=self.listen_stop_event
            )
        except Exception as e:
            print(f"Ошибка приёма: {e}")
        finally:
            self.is_listening = False

    def stop_listen(self):
        """Останавливает прослушивание."""
        if self.listen_stop_event:
            self.listen_stop_event.set()
        self.is_listening = False