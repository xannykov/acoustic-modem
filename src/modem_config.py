import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'modem_config.json')

DEFAULT_CONFIG = {
    'FS': 44100,
    'BIT_DURATION': 0.01,
    'FREQ_0': 4400,
    'FREQ_1': 8800,
    'ENERGY_THRESHOLD': 0.05,
    'SYNC_THRESHOLD': 0.8,
    'PREAMBLE_LEN': 16,
    'SAVE_FOLDER': os.path.join(os.path.expanduser("~"), "Downloads"),
    'INPUT_DEVICE': None,
    'OUTPUT_DEVICE': None,
    'APPEARANCE_MODE': 'System'
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Объединяем с дефолтными, чтобы добавить новые ключи
            return {**DEFAULT_CONFIG, **config}
    return DEFAULT_CONFIG.copy()

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def update_modem_base(config):
    from src import modem_base
    modem_base.FS = config["FS"]
    modem_base.BIT_DURATION = config["BIT_DURATION"]
    modem_base.FREQ_0 = config["FREQ_0"]
    modem_base.FREQ_1 = config["FREQ_1"]
    modem_base.ENERGY_THRESHOLD = config["ENERGY_THRESHOLD"]
    modem_base.SYNC_THRESHOLD = config["SYNC_THRESHOLD"]
    # Пересчитываем PREAMBLE если изменилась длина
    modem_base.PREAMBLE = "10" * config["PREAMBLE_LEN"]
    # Пересчёт CHUNK_SIZE
    modem_base.CHUNK_SIZE = int(modem_base.FS * modem_base.BIT_DURATION)