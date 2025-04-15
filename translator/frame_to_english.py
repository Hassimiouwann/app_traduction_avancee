# translator/frame_to_english.py (ultra-robuste : gestion slots, adjectifs/adverbes, fallback accent, logs)

import unicodedata

def unaccent(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def extract_text_and_pos(slot):
    if slot is None:
        return None, None
    if isinstance(slot, dict):
        return slot.get("text"), slot.get("pos")
    return slot, None

def translate_frames_to_english(frames, connaissances, frames_config):
    english_sentences = []
    for frame in frames:
        if "type" in frame and frame["type"] == "no_frame_detected":
            # Log special frame
            english_sentences.append("[No frame detected: {}]".format(frame.get("diagnostic", "")))
        else:
            sentence_en = translate_single_frame_to_english(frame, connaissances, frames_config)
            if sentence_en:
                english_sentences.append(sentence_en)
    return " ".join(english_sentences)

def translate_single_frame_to_english(frame, connaissances, frames_config):
    primitive = frame.get("primitive")
    temps = frame.get("temps", "présent")
    verbe_fr = frame.get("verbe_fr")

    # Extraction des slots et de leur POS
    # On récupère tous les slots connus, et on gère dynamiquement les autres si besoin
    slots = [
        "agent", "objet", "source", "destination", "instrument", "manière", "bénéficiaire",
        "information", "idées_source", "résultat", "direction", "force", "substance", "origin",
        "message", "audience", "cible_sens"
    ]
    slot_values = {}
    for slot in slots:
        slot_values[slot+"_text"], slot_values[slot+"_pos"] = extract_text_and_pos(frame.get(slot))

    primitive_to_en_verb = frames_config["primitive_to_en_verb"]

    # Récupération du verbe anglais selon la base de connaissance (essai lemma, sans accents, etc)
    english_verb = get_from_kb_with_fallback(verbe_fr, connaissances["verbes"], "en", temps)
    # Fallback si pas trouvé
    if not english_verb:
        english_verb = primitive_to_en_verb.get(primitive, "do")
        if temps == "présent":
            english_verb = add_third_person_s(english_verb)
        elif temps == "passé":
            english_verb += "ed"  # Simple fallback
        elif temps == "futur":
            english_verb = f"will {english_verb}"

    # Traduction ultra-robuste des slots : essaye toutes les catégories, avec et sans accents
    agent_en = translate_phrase(slot_values["agent_text"], connaissances, frames_config, role="subject", pos=slot_values["agent_pos"])
    objet_en = translate_phrase(slot_values["objet_text"], connaissances, frames_config, pos=slot_values["objet_pos"])
    source_en = translate_phrase(slot_values["source_text"], connaissances, frames_config, pos=slot_values["source_pos"])
    destination_en = translate_phrase(slot_values["destination_text"], connaissances, frames_config, pos=slot_values["destination_pos"])
    instrument_en = translate_phrase(slot_values["instrument_text"], connaissances, frames_config, pos=slot_values["instrument_pos"])
    manner_en = translate_phrase(slot_values["manière_text"], connaissances, frames_config, cat='adverbes', pos=slot_values["manière_pos"])
    beneficiaire_en = translate_phrase(slot_values["bénéficiaire_text"], connaissances, frames_config, pos=slot_values["bénéficiaire_pos"])
    info_en = translate_phrase(slot_values["information_text"], connaissances, frames_config, pos=slot_values["information_pos"])
    idees_src_en = translate_phrase(slot_values["idées_source_text"], connaissances, frames_config, pos=slot_values["idées_source_pos"])
    resultat_en = translate_phrase(slot_values["résultat_text"], connaissances, frames_config, pos=slot_values["résultat_pos"])
    direction_en = translate_phrase(slot_values["direction_text"], connaissances, frames_config, pos=slot_values["direction_pos"])
    force_en = translate_phrase(slot_values["force_text"], connaissances, frames_config, pos=slot_values["force_pos"])
    substance_en = translate_phrase(slot_values["substance_text"], connaissances, frames_config, pos=slot_values["substance_pos"])
    origin_en = translate_phrase(slot_values["origin_text"], connaissances, frames_config, pos=slot_values["origin_pos"])
    message_en = translate_phrase(slot_values["message_text"], connaissances, frames_config, pos=slot_values["message_pos"])
    audience_en = translate_phrase(slot_values["audience_text"], connaissances, frames_config, pos=slot_values["audience_pos"])
    cible_sens_en = translate_phrase(slot_values["cible_sens_text"], connaissances, frames_config, pos=slot_values["cible_sens_pos"])

    # -------- Correction : ne pas mettre "The" devant un agent nom propre --------
    agent_phrase = agent_en
    if agent_en and (slot_values["agent_pos"] != "PROPN") and not agent_en.lower().startswith(("the ", "a ", "an ")):
        agent_phrase = f"the {agent_en}"

    # On assemble la phrase en fonction de la primitive
    sentence = ""

    # =========================
    # 1) Primitives existantes
    # =========================
    if primitive == "PTRANS":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if source_en:
            sentence += f" from {source_en}"
        if destination_en:
            sentence += f" to {destination_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "ATRANS":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if objet_en:
            sentence += f" {objet_en}"
        if beneficiaire_en:
            sentence += f" to {beneficiaire_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "MOVE":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if source_en:
            sentence += f" from {source_en}"
        if destination_en:
            sentence += f" to {destination_en}"
        if manner_en:
            sentence += f" {manner_en}"

    # ==============================
    # 2) Nouvelles primitives (8)
    # ==============================
    elif primitive == "MTRANS":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if info_en:
            sentence += f" {info_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "MBUILD":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if resultat_en:
            sentence += f" {resultat_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "PROPEL":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if objet_en:
            sentence += f" {objet_en}"
        if direction_en:
            sentence += f" toward {direction_en}"
        if force_en:
            sentence += f" with {force_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "INGEST":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if substance_en:
            sentence += f" {substance_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "EXPEL":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if substance_en:
            sentence += f" {substance_en}"
        if origin_en:
            sentence += f" from {origin_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "SPEAK":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if message_en:
            sentence += f" {message_en}"
        if audience_en:
            sentence += f" to {audience_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "ATTEND":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if cible_sens_en:
            sentence += f" {cible_sens_en}"
        if manner_en:
            sentence += f" {manner_en}"

    elif primitive == "GRASP":
        if not agent_phrase:
            return None
        sentence = f"{agent_phrase} {english_verb}"
        if objet_en:
            sentence += f" {objet_en}"
        if manner_en:
            sentence += f" {manner_en}"

    else:
        if agent_phrase:
            sentence = f"{agent_phrase} {english_verb}"
            if manner_en:
                sentence += f" {manner_en}"

    if sentence:
        sentence = sentence[0].upper() + sentence[1:] + "."
        return sentence

    return None

def add_third_person_s(verb_phrase):
    words = verb_phrase.split()
    if not words:
        return verb_phrase
    first_word = words[0]
    if not first_word.endswith("s"):
        first_word += "s"
    words[0] = first_word
    return " ".join(words)

def get_from_kb_with_fallback(key, verbes_kb, tense="en", temps="présent"):
    # Cherche avec et sans accents
    if key in verbes_kb and tense in verbes_kb[key]:
        if isinstance(verbes_kb[key][tense], dict):
            return verbes_kb[key][tense].get(temps)
        return verbes_kb[key][tense]
    key_noacc = unaccent(key)
    if key_noacc in verbes_kb and tense in verbes_kb[key_noacc]:
        if isinstance(verbes_kb[key_noacc][tense], dict):
            return verbes_kb[key_noacc][tense].get(temps)
        return verbes_kb[key_noacc][tense]
    return None

def translate_phrase(text, connaissances, frames_config, cat=None, role=None, pos=None):
    """
    Ultra-robuste : gère adjectifs/noms/adverbes multiples dans une phrase, essaye toutes les catégories, tente sans accents
    """
    if not text:
        return None

    # Nettoie et découpe la phrase en mots
    text_clean = text.lower().replace("le ", "").replace("la ", "").replace("les ", "").replace("l'", "").strip()
    # Sépare les mots
    parts = text_clean.split()
    translated_parts = []
    for part in parts:
        # Si possible, traduit dans la catégorie demandée
        found = None
        search_cats = [cat] if cat else []
        # Ajoute toutes les catégories si ce n'est pas une catégorie imposée
        if not search_cats:
            search_cats = ["noms", "adjectifs", "adverbes"]

        for c in search_cats:
            if part in connaissances.get(c, {}):
                found = connaissances[c][part]
                break
            part_noacc = unaccent(part)
            if part_noacc in connaissances.get(c, {}):
                found = connaissances[c][part_noacc]
                break
        # Si pas trouvé, tente dans toutes les catégories
        if not found:
            for c in ["noms", "adjectifs", "adverbes"]:
                if part in connaissances.get(c, {}):
                    found = connaissances[c][part]
                    break
                part_noacc = unaccent(part)
                if part_noacc in connaissances.get(c, {}):
                    found = connaissances[c][part_noacc]
                    break
        # Si encore rien, fallback : retourne _mot
        if not found:
            found = f"_{part}"
        translated_parts.append(found)

    # Gestion du cas des corps célestes (frames_config)
    celestial_bodies = frames_config["celestial_bodies_rules"]
    joined = " ".join(parts)
    joined_noacc = unaccent(joined)
    if joined in celestial_bodies:
        if role == "subject":
            return celestial_bodies[joined]["subject_form"]
        else:
            return celestial_bodies[joined]["non_subject_form"]
    if joined_noacc in celestial_bodies:
        if role == "subject":
            return celestial_bodies[joined_noacc]["subject_form"]
        else:
            return celestial_bodies[joined_noacc]["non_subject_form"]

    # Si c'est un nom propre SpaCy
    if pos == "PROPN":
        return text

    # Pour les rôles d'agents/objets (noms communs), ajoute "the" si nécessaire
    val = " ".join(translated_parts)
    if role != "subject" and pos == "NOUN" and not val.lower().startswith(("the ", "a ", "an ", "_")):
        return f"the {val}"
    return val