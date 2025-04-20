# translator/global_config.py

import json

GLOBAL_CONFIG_FILE = "global_config.json"

def load_global_config():
    with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def save_global_config(data):
    with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
