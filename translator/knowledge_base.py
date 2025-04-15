# translator/knowledge_base.py
import json

def charger_bc():
    """
    Charge le fichier JSON contenant la base de connaissances 
    et renvoie un dictionnaire Python.
    """
    with open('base_connaissance.json', 'r', encoding='utf-8') as f:
        return json.load(f)
