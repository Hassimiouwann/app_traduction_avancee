#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import string
import re
import nltk
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

# === Import depuis la nouvelle base MySQL ===
from translator.global_config import load_global_config

# Charger builder + traducteur (inchangé)
from translator.frame_builder import build_frames
from translator.frame_to_english import translate_frames_to_english

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

app = Flask(__name__)

# Charger la config globale au démarrage (depuis MySQL)
global_data = load_global_config()

# On peut garder des raccourcis pour la base + frames
knowledge_base = global_data["knowledge_base"]       # ex: verbes, noms, ...
frames_config_data = global_data["frames_config"]    # ex: frames_definition, celestial_bodies_rules...

AUDIO_FIXED_GROUPS = [
    # Groupes classiques
    "to the", "of the", "in the", "at the", "on the", "for the", "with the", "by the", "from the",
    "to a", "of a", "in a", "at a", "on a", "for a", "with a", "by a", "from a",
    # Groupes custom
    "as well as", "such as", "according to", "in order to", "in front of", "because of",
    "instead of", "due to", "thanks to", "in spite of", "out of", "as soon as", "as long as", "as far as",
    "so that", "even though", "as if", "as though", "rather than", "on behalf of",
    # Ajoute tout ce que tu veux ici
]

def normalize_expr(expr):
    """
    Pour expressions idiomatiques : retire ponctuation, espaces et met en minuscule pour comparer.
    """
    return expr.strip().lower().translate(str.maketrans('', '', string.punctuation))

@app.route('/')
def index():
    # Page principale (templates/index.html)
    return render_template('index.html')

AUDIO_FOLDER = os.path.join('static', 'expressions_audio')
os.makedirs(AUDIO_FOLDER, exist_ok=True)

@app.route('/upload_expression_audio', methods=['POST'])
def upload_expression_audio():
    if 'audio' not in request.files or 'expr_key' not in request.form:
        return jsonify({'msg': "Données manquantes"}), 400
    audio = request.files['audio']
    expr_key = request.form['expr_key']
    filename = secure_filename(expr_key + ".mp3")
    AUDIO_FOLDER = os.path.join('static', 'expressions_audio')
    os.makedirs(AUDIO_FOLDER, exist_ok=True)
    save_path = os.path.join(AUDIO_FOLDER, filename)
    audio.save(save_path)
    return jsonify({'msg': "Audio enregistré !"})

@app.route('/record_audio_segments')
def record_audio_segments():
    # On recharge la config globale (pour inclure éventuelles modifs)
    global global_data, knowledge_base
    global_data = load_global_config()
    knowledge_base = global_data["knowledge_base"]
    segments_en = set()
    # Expressions idiomatiques
    segments_en.update(knowledge_base.get("expressions", {}).values())
    # Verbes (tous temps)
    for v in knowledge_base.get("verbes", {}).values():
        for enverb in v.get("en", {}).values():
            segments_en.add(enverb)
    # Noms
    segments_en.update(knowledge_base.get("noms", {}).values())
    # Adjectifs
    segments_en.update(knowledge_base.get("adjectifs", {}).values())
    # Adverbes
    segments_en.update(knowledge_base.get("adverbes", {}).values())
    # Trie pour l'affichage
    segments_en = sorted(segments_en)
    return render_template("record_audio_segments.html", segments_en=segments_en)

def get_audio_segments_from_kb(knowledge_base):
    """Retourne l'ensemble des segments anglais multi-mots utilisés dans la base (ex: 'takes off', 'will take off')"""
    segments = set()
    # Verbes (tous temps)
    for v in knowledge_base.get("verbes", {}).values():
        for enverb in v.get("en", {}).values():
            segments.add(enverb.lower())
    # Expressions idiomatiques
    for expr in knowledge_base.get("expressions", {}).values():
        segments.add(expr.lower())
    # Noms, adjectifs, adverbes
    for cat in ["noms", "adjectifs", "adverbes"]:
        for mot in knowledge_base.get(cat, {}):
            segments.add(knowledge_base[cat][mot].lower())
    # Groupes fixes (voir ci-dessus)
    segments.update(AUDIO_FIXED_GROUPS)
    # Trie par longueur décroissante pour matcher le plus long d'abord
    segments = sorted(segments, key=lambda s: -len(s))
    return segments

def smart_tokenize_english(sentence, knowledge_base):
    """
    Découpe la phrase anglaise en segments selon la base (verbes composés, expressions, groupes comme 'from the', etc.), puis mots.
    Ne retourne jamais de .mp3 vide.
    """
    sentence_lc = sentence.lower()
    segments = get_audio_segments_from_kb(knowledge_base)
    used = [False] * len(sentence)
    found = []

    # 1. On prend tous les groupes connus (plus long d'abord)
    for seg in segments:
        pattern = re.compile(r'\b' + re.escape(seg) + r'\b')
        for m in pattern.finditer(sentence_lc):
            idx = m.start()
            if not any(used[idx:idx+len(seg)]):
                found.append((idx, idx+len(seg), sentence[idx:idx+len(seg)]))
                for i in range(idx, idx+len(seg)):
                    used[i] = True

    # 2. Reste à découper en mots simples (jamais de vide)
    rest = []
    current = ""
    for i, c in enumerate(sentence):
        if not used[i]:
            if c.isalnum() or c in "'":
                current += c
            else:
                if current:
                    rest.append((i-len(current), i, current))
                    current = ""
                if c.strip() and c not in ".!?,":  # ponctuation exclue
                    rest.append((i, i+1, c))
        else:
            if current:
                rest.append((i-len(current), i, current))
                current = ""
    if current:
        rest.append((len(sentence)-len(current), len(sentence), current))

    # 3. Fusionne et trie
    all_tokens = found + rest
    all_tokens.sort(key=lambda t: t[0])
    result = []
    for _, _, val in all_tokens:
        val = val.strip()
        if val:
            result.append(val)
    # 4. Retirer la ponctuation simple et tokens vides
    result = [tok for tok in result if re.match(r"^[\w\s']+$", tok)]
    return result

@app.route('/traduire', methods=['POST'])
def traduire():
    global global_data, knowledge_base, frames_config_data
    # Recharger la config à chaque requête pour prise en compte modifications en BDD
    global_data = load_global_config()
    knowledge_base = global_data["knowledge_base"]
    frames_config_data = global_data["frames_config"]

    data = request.json
    phrase = data.get('phrase', '').strip()
    if phrase and phrase[0].islower():
        phrase = phrase[0].upper() + phrase[1:]
    if not phrase:
        return jsonify({"phrase_traduite": "", "frames": [], "audio_tokens": []})

    # Vérification DIRECTE des expressions idiomatiques avant analyse
    expressions = knowledge_base.get('expressions', {})
    norm_phrase = normalize_expr(phrase)
    matches = [e for e in expressions if normalize_expr(e) == norm_phrase]
    if matches:
        expr_key = matches[0]
        phrase_traduite = expressions[expr_key]
        audio_tokens = smart_tokenize_english(phrase_traduite, knowledge_base)
        return jsonify({
            "phrase_traduite": phrase_traduite,
            "frames": [{"type": "expression_idiomatique", "phrase": phrase}],
            "audio_tokens": audio_tokens
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
        audio_tokens = []
    else:
        audio_tokens = smart_tokenize_english(phrase_traduite, knowledge_base)

    return jsonify({
        "phrase_traduite": phrase_traduite,
        "frames": frames,
        "audio_tokens": audio_tokens
    })

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
    # Ici, pour la version MySQL, il faut implémenter l'insertion dans la base.
    # À faire : tu peux adapter la logique de populate_db.py ici si besoin.
    return jsonify({"msg": "Route à implémenter pour l'insertion directe en base MySQL."}), 501

@app.route('/enrichir_config', methods=['GET'])
def page_enrichir_config():
    return render_template('enrichir_global.html')

if __name__ == '__main__':
    app.run(debug=True)
