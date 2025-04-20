# translator/frame_to_english.py (version robuste : meilleure gestion des slots, adjectives et fallback)

def extract_text_and_pos(slot):
    if slot is None:
        return None, None
    if isinstance(slot, dict):
        return slot.get("text"), slot.get("pos")
    return slot, None

def translate_frames_to_english(frames, connaissances, frames_config):
    english_sentences = []
    for frame in frames:
        sentence_en = translate_single_frame_to_english(frame, connaissances, frames_config)
        if sentence_en:
            english_sentences.append(sentence_en)
    return " ".join(english_sentences)

def translate_single_frame_to_english(frame, connaissances, frames_config):
    primitive = frame.get("primitive")
    temps = frame.get("temps", "présent")
    verbe_fr = frame.get("verbe_fr")

    # Extraction des slots et de leur POS
    agent_text, agent_pos = extract_text_and_pos(frame.get("agent"))
    objet_text, objet_pos = extract_text_and_pos(frame.get("objet"))
    source_text, source_pos = extract_text_and_pos(frame.get("source"))
    destination_text, destination_pos = extract_text_and_pos(frame.get("destination"))
    instrument_text, instrument_pos = extract_text_and_pos(frame.get("instrument"))
    maniere_text, maniere_pos = extract_text_and_pos(frame.get("manière"))
    beneficiaire_text, beneficiaire_pos = extract_text_and_pos(frame.get("bénéficiaire"))
    information_text, information_pos = extract_text_and_pos(frame.get("information"))
    idees_source_text, idees_source_pos = extract_text_and_pos(frame.get("idées_source"))
    resultat_text, resultat_pos = extract_text_and_pos(frame.get("résultat"))
    direction_text, direction_pos = extract_text_and_pos(frame.get("direction"))
    force_text, force_pos = extract_text_and_pos(frame.get("force"))
    substance_text, substance_pos = extract_text_and_pos(frame.get("substance"))
    origin_text, origin_pos = extract_text_and_pos(frame.get("origin"))
    message_text, message_pos = extract_text_and_pos(frame.get("message"))
    audience_text, audience_pos = extract_text_and_pos(frame.get("audience"))
    cible_sens_text, cible_sens_pos = extract_text_and_pos(frame.get("cible_sens"))

    primitive_to_en_verb = frames_config["primitive_to_en_verb"]

    # Récupération du verbe anglais selon la base de connaissance (temps + lemma)
    english_verb = connaissances["verbes"].get(verbe_fr, {}).get("en", {}).get(temps)

    # Fallback si pas trouvé
    if not english_verb:
        english_verb = primitive_to_en_verb.get(primitive, "do")
        if temps == "présent":
            english_verb = add_third_person_s(english_verb)
        elif temps == "passé":
            english_verb += "ed"  # Simple fallback
        elif temps == "futur":
            english_verb = f"will {english_verb}"

    # Traduction des slots en anglais, en passant le POS pour robustesse
    agent_en = translate_word(agent_text, connaissances, frames_config, role="subject", pos=agent_pos)
    objet_en = translate_word(objet_text, connaissances, frames_config, pos=objet_pos)
    source_en = translate_word(source_text, connaissances, frames_config, pos=source_pos)
    destination_en = translate_word(destination_text, connaissances, frames_config, pos=destination_pos)
    instrument_en = translate_word(instrument_text, connaissances, frames_config, pos=instrument_pos)
    manner_en = translate_word(maniere_text, connaissances, frames_config, cat='adverbes', pos=maniere_pos)
    beneficiaire_en = translate_word(beneficiaire_text, connaissances, frames_config, pos=beneficiaire_pos)
    info_en = translate_word(information_text, connaissances, frames_config, pos=information_pos)
    idees_src_en = translate_word(idees_source_text, connaissances, frames_config, pos=idees_source_pos)
    resultat_en = translate_word(resultat_text, connaissances, frames_config, pos=resultat_pos)
    direction_en = translate_word(direction_text, connaissances, frames_config, pos=direction_pos)
    force_en = translate_word(force_text, connaissances, frames_config, pos=force_pos)
    substance_en = translate_word(substance_text, connaissances, frames_config, pos=substance_pos)
    origin_en = translate_word(origin_text, connaissances, frames_config, pos=origin_pos)
    message_en = translate_word(message_text, connaissances, frames_config, pos=message_pos)
    audience_en = translate_word(audience_text, connaissances, frames_config, pos=audience_pos)
    cible_sens_en = translate_word(cible_sens_text, connaissances, frames_config, pos=cible_sens_pos)

    # -------- Correction : ne pas mettre "The" devant un agent nom propre --------
    if agent_pos == "PROPN":
        agent_phrase = agent_en
    else:
        agent_phrase = f"the {agent_en}" if agent_en else None

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
    # Ne double pas le 's' si déjà conjugué
    if not first_word.endswith("s"):
        first_word += "s"
    words[0] = first_word
    return " ".join(words)

def translate_word(word, connaissances, frames_config, cat=None, role=None, pos=None):
    if not word:
        return None

    word_clean = word.lower().replace("le ", "").replace("la ", "").replace("les ", "").replace("l'", "")
    word_clean = word_clean.strip()

    # Si la phrase contient déjà un adjectif (ex: "jolie pomme"), séparer et traduire chaque terme
    if " " in word_clean:
        parts = word_clean.split()
        translated_parts = []
        for part in parts:
            # Cherche d'abord dans adjectifs, sinon dans noms
            if part in connaissances.get("adjectifs", {}):
                translated_parts.append(connaissances["adjectifs"][part])
            elif part in connaissances.get("noms", {}):
                translated_parts.append(connaissances["noms"][part])
            else:
                translated_parts.append(f"_{part}")
        return " ".join(translated_parts)

    celestial_bodies = frames_config["celestial_bodies_rules"]
    if word_clean in celestial_bodies:
        if role == "subject":
            return celestial_bodies[word_clean]["subject_form"]
        else:
            return celestial_bodies[word_clean]["non_subject_form"]

    if cat:
        return connaissances.get(cat, {}).get(word_clean, f"_{word_clean}")

    # Si c'est un nom propre SpaCy
    if pos == "PROPN":
        return word

    for category in ["noms", "adjectifs", "adverbes", "articles", "pronoms", "prépositions"]:
        if word_clean in connaissances.get(category, {}):
            val = connaissances[category][word_clean]
            if category == "noms" and role != "subject" and not val.lower().startswith(("the ", "a ", "an ", "_")):
                return f"the {val}"
            return val

    return f"_{word_clean}"
