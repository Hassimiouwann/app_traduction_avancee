# app.py (ultra-robuste: gestion idiomatiques, fallback, logs, frames vides, accents, ponctuations)

from flask import Flask, render_template, request, jsonify
import nltk
import json
import string
import unicodedata

from translator.global_config import load_global_config, save_global_config
from translator.frame_builder import build_frames
from translator.frame_to_english import translate_frames_to_english

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

app = Flask(__name__)

# Charger la config globale au démarrage
global_data = load_global_config()
knowledge_base = global_data["knowledge_base"]
frames_config_data = global_data["frames_config"]

def normalize_expr(expr):
    # Retire ponctuation, accents, espaces, et met en minuscule pour matcher les expressions idiomatiques
    expr = expr.strip().lower()
    expr = ''.join(c for c in expr if c not in string.punctuation)
    expr = ''.join(
        c for c in unicodedata.normalize('NFD', expr)
        if unicodedata.category(c) != 'Mn'
    )
    return expr

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/traduire', methods=['POST'])
def traduire():
    data = request.json
    phrase = data.get('phrase', '').strip()
    if not phrase:
        return jsonify({"phrase_traduite": "", "frames": []})

    # Préparation pour matcher idiomatiques ultra-tolérant
    expressions = knowledge_base.get('expressions', {})
    norm_phrase = normalize_expr(phrase)
    expressions_norm = {normalize_expr(e): e for e in expressions}
    if norm_phrase in expressions_norm:
        expr_key = expressions_norm[norm_phrase]
        return jsonify({
            "phrase_traduite": expressions[expr_key],
            "frames": [{"type": "expression_idiomatique", "phrase": phrase}]
        })

    # Analyse ultra-robuste : essaie la phrase brute, puis sans ponctuation finale, puis tout en minuscules, puis sans accents
    tried = set()
    frames = build_frames(phrase, global_data)
    tried.add(phrase)
    # Si frames vides, tente sans ponctuation finale
    if not frames or (len(frames) == 1 and "type" in frames[0] and frames[0]["type"] == "no_frame_detected"):
        phrase2 = phrase
        if phrase2 and phrase2[-1] in string.punctuation:
            phrase2 = phrase2[:-1]
        if phrase2 and phrase2 not in tried:
            frames = build_frames(phrase2, global_data)
            tried.add(phrase2)
    # Si toujours rien, tente tout en minuscules
    if (not frames or (len(frames) == 1 and "type" in frames[0] and frames[0]["type"] == "no_frame_detected")) and phrase.lower() not in tried:
        frames = build_frames(phrase.lower(), global_data)
        tried.add(phrase.lower())
    # Si toujours rien, tente sans accents
    def unaccent(text):
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
    if (not frames or (len(frames) == 1 and "type" in frames[0] and frames[0]["type"] == "no_frame_detected")) and unaccent(phrase) not in tried:
        frames = build_frames(unaccent(phrase), global_data)
        tried.add(unaccent(phrase))

    # Traduction ultra-robuste
    phrase_traduite = translate_frames_to_english(frames, knowledge_base, frames_config_data)

    # Si aucune traduction, indique-le explicitement
    if not phrase_traduite or "[No frame detected" in phrase_traduite:
        phrase_traduite = "Pas de traduction"

    # Ajoute log si frames non trouvés
    log_diag = []
    if frames and isinstance(frames, list) and "type" in frames[0] and frames[0]["type"] == "no_frame_detected":
        log_diag = frames[0].get("diagnostic", [])

    return jsonify({
        "phrase_traduite": phrase_traduite,
        "frames": frames,
        "log_diag": log_diag
    })

@app.route('/ajouter_data', methods=['POST'])
def ajouter_data():
    """
    Voir docstring précédente
    """
    data = request.json
    if not data:
        return jsonify({"msg": "Pas de données reçues"}), 400

    global_data_reload = load_global_config()
    kb = global_data_reload["knowledge_base"]
    fc = global_data_reload["frames_config"]

    type_zone = data.get("type_zone")

    if type_zone == "knowledge_base":
        categorie = data.get("categorie")
        mot_fr = data.get("mot_fr")
        mot_en = data.get("mot_en")
        primitive = data.get("primitive", None)
        if not categorie or not mot_fr or not mot_en:
            return jsonify({"msg":"Paramètres manquants (categorie, mot_fr, mot_en)."}), 400
        if categorie not in kb:
            kb[categorie] = {}
        if categorie == "verbes":
            kb["verbes"].setdefault(mot_fr, {})
            kb["verbes"][mot_fr]["en"] = {"présent": mot_en}
            if primitive:
                kb["verbes"][mot_fr]["primitive"] = primitive
        else:
            kb[categorie][mot_fr] = mot_en

    elif type_zone == "frames_config":
        sub_type = data.get("type_data")
        if sub_type == "celestial_bodies_rules":
            clef = data.get("clef")
            subject_form = data.get("subject_form")
            non_subject_form = data.get("non_subject_form")
            if clef and subject_form and non_subject_form:
                fc["celestial_bodies_rules"][clef.lower()] = {
                    "subject_form": subject_form,
                    "non_subject_form": non_subject_form
                }
            else:
                return jsonify({"msg":"Données incomplètes pour celestial_bodies_rules"}),400
        elif sub_type == "primitive_to_en_verb":
            primitive = data.get("primitive")
            verb_en = data.get("verb_en")
            if primitive and verb_en:
                fc["primitive_to_en_verb"][primitive] = verb_en
            else:
                return jsonify({"msg":"Données incomplètes pour primitive_to_en_verb"}),400
        elif sub_type == "frames_definition":
            primitive = data.get("primitive")
            slots = data.get("slots", [])
            description = data.get("description", "")
            if primitive and slots:
                fc["frames_definition"][primitive] = {
                    "name": primitive,
                    "slots": slots,
                    "description": description
                }
            else:
                return jsonify({"msg":"Données incomplètes pour frames_definition"}),400
        else:
            return jsonify({"msg": f"type_data '{sub_type}' inconnu"}),400
    else:
        return jsonify({"msg": f"type_zone '{type_zone}' inconnu. Utilisez 'knowledge_base' ou 'frames_config'."}),400

    save_global_config(global_data_reload)
    return jsonify({"msg": "OK, data ajoutée/maj."})

@app.route('/enrichir_config', methods=['GET'])
def page_enrichir_config():
    return render_template('enrichir_global.html')

if __name__ == '__main__':
    app.run(debug=True)