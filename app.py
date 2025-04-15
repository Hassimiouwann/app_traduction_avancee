# app.py

from flask import Flask, render_template, request, jsonify
import nltk
import json
import string

# Charger la config globale (knowledge_base + frames_config)
from translator.global_config import load_global_config, save_global_config

# Charger builder + traducteur
from translator.frame_builder import build_frames
from translator.frame_to_english import translate_frames_to_english

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

app = Flask(__name__)

# Charger la config globale au démarrage
global_data = load_global_config()

# On peut garder des raccourcis pour la base + frames
knowledge_base = global_data["knowledge_base"]       # ex: verbes, noms, ...
frames_config_data = global_data["frames_config"]    # ex: frames_definition, celestial_bodies_rules...

def normalize_expr(expr):
    """
    Pour expressions idiomatiques : retire ponctuation, espaces et met en minuscule pour comparer.
    """
    return expr.strip().lower().translate(str.maketrans('', '', string.punctuation))

@app.route('/')
def index():
    # Page principale (templates/index.html)
    return render_template('index.html')

@app.route('/traduire', methods=['POST'])
def traduire():
    data = request.json
    phrase = data.get('phrase', '').strip()
    if phrase and phrase[0].islower():
        phrase = phrase[0].upper() + phrase[1:]
    if not phrase:
        return jsonify({"phrase_traduite": "", "frames": []})

    # Vérification DIRECTE des expressions idiomatiques avant analyse
    expressions = knowledge_base.get('expressions', {})
    norm_phrase = normalize_expr(phrase)
    matches = [e for e in expressions if normalize_expr(e) == norm_phrase]
    if matches:
        expr_key = matches[0]
        return jsonify({
            "phrase_traduite": expressions[expr_key],
            "frames": [{"type": "expression_idiomatique", "phrase": phrase}]
        })

    # Construire les frames (tente phrase sans ponctuation si frames vides)
    frames = build_frames(phrase, global_data)
    if not frames and phrase[-1] in string.punctuation:
        phrase2 = phrase[:-1]
        frames = build_frames(phrase2, global_data)

    # Traduire
    phrase_traduite = translate_frames_to_english(frames, knowledge_base, frames_config_data)

    # Si aucune traduction, indique-le explicitement
    if not phrase_traduite:
        phrase_traduite = "Pas de traduction"

    return jsonify({
        "phrase_traduite": phrase_traduite,
        "frames": frames
    })

# ------ Route unique pour enrichir la config globale ------
@app.route('/ajouter_data', methods=['POST'])
def ajouter_data():
    """
    Reçoit un JSON du style :
    {
      "type_zone": "knowledge_base" ou "frames_config",

      // si "knowledge_base", on peut avoir:
      //   "categorie": "noms"/"verbes"/...,
      //   "mot_fr": "...",
      //   "mot_en": "...",
      //   "primitive": "...",
      //   etc.

      // si "frames_config", on peut avoir:
      //   "type_data": "celestial_bodies_rules" / "primitive_to_en_verb" / "frames_definition"
      //   ... + champs nécessaires
    }
    """
    data = request.json
    if not data:
        return jsonify({"msg": "Pas de données reçues"}), 400

    global_data_reload = load_global_config()  # recharger la dernière version
    kb = global_data_reload["knowledge_base"]
    fc = global_data_reload["frames_config"]

    type_zone = data.get("type_zone")

    if type_zone == "knowledge_base":
        # Ex: { "categorie": "noms", "mot_fr":"chat", "mot_en":"cat" }
        categorie = data.get("categorie")
        mot_fr = data.get("mot_fr")
        mot_en = data.get("mot_en")
        primitive = data.get("primitive", None)

        if not categorie or not mot_fr or not mot_en:
            return jsonify({"msg":"Paramètres manquants (categorie, mot_fr, mot_en)."}), 400

        # Vérifier que la catégorie existe ou la créer si tu veux
        if categorie not in kb:
            kb[categorie] = {}

        if categorie == "verbes":
            # On stocke un dict
            # ex: "verbes": { "envoyer": { "en":{"présent":"send"}, "primitive":"ATRANS"}}
            kb["verbes"].setdefault(mot_fr, {})
            kb["verbes"][mot_fr]["en"] = {"présent": mot_en}
            if primitive:
                kb["verbes"][mot_fr]["primitive"] = primitive
        else:
            # ex: "noms": { "chat": "cat" }
            kb[categorie][mot_fr] = mot_en

    elif type_zone == "frames_config":
        # ex: sub_type => "celestial_bodies_rules", "primitive_to_en_verb", "frames_definition"
        sub_type = data.get("type_data")
        if sub_type == "celestial_bodies_rules":
            # ex: { "clef":"lune", "subject_form":"the Moon", "non_subject_form":"the Moon" }
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
            # ex: { "primitive":"MTRANS", "verb_en":"transfer" }
            primitive = data.get("primitive")
            verb_en = data.get("verb_en")
            if primitive and verb_en:
                fc["primitive_to_en_verb"][primitive] = verb_en
            else:
                return jsonify({"msg":"Données incomplètes pour primitive_to_en_verb"}),400

        elif sub_type == "frames_definition":
            # ex: { "primitive":"PROPEL", "slots":["agent","objet"], "description":"..." }
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

    # Sauvegarder
    save_global_config(global_data_reload)
    return jsonify({"msg": "OK, data ajoutée/maj."})

# On peut imaginer un GET pour afficher un formulaire unique "enrichir_global.html" si besoin
@app.route('/enrichir_config', methods=['GET'])
def page_enrichir_config():
    return render_template('enrichir_global.html')

if __name__ == '__main__':
    app.run(debug=True)
