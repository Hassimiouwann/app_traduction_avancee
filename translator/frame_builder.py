# translator/frame_builder.py (version ultra-robuste : détection verbe principal + slots + adj/nmod)

import spacy

nlp = spacy.load("fr_core_news_md")

def detecter_temps_verb(token):
    if token.morph.get("Tense") == ["Past"]:
        return "passé"
    elif token.morph.get("Tense") == ["Fut"]:
        return "futur"
    else:
        return "présent"

def build_frames(phrase, global_config):
    knowledge_base = global_config["knowledge_base"]
    frames_definition = global_config["frames_config"]["frames_definition"]

    doc = nlp(phrase)
    frames = []

    print("\n--- Diagnostic SpaCy complet ---")
    for token in doc:
        print(f"{token.text} | lemma: {token.lemma_}, dep: {token.dep_}, "
              f"pos: {token.pos_}, head: {token.head.text}, morph: {token.morph}")
    print("--- Fin diagnostic ---\n")

    # Prend tous les tokens VERB (même s'ils ne sont pas ROOT ou flat:name)
    verb_tokens = [tok for tok in doc if tok.pos_ == "VERB"]
    # Si rien trouvé, tente aussi les NOUN "mal taggués"
    if not verb_tokens:
        verb_tokens = [tok for tok in doc if tok.tag_ in {"VERB", "AUX"} or "VerbForm" in tok.morph]

    for token in verb_tokens:
        lemma_spacy = token.lemma_.lower()
        if lemma_spacy in knowledge_base.get("verbes", {}):
            verbe_info = knowledge_base["verbes"][lemma_spacy]
        else:
            form_token = token.text.lower()
            if form_token in knowledge_base.get("verbes", {}):
                lemma_spacy = form_token
                verbe_info = knowledge_base["verbes"][form_token]
            else:
                continue

        primitive = verbe_info.get("primitive")
        if primitive:
            temps = detecter_temps_verb(token)
            frame_instance = fill_frame(token, primitive, doc, frames_definition)
            frame_instance["temps"] = temps
            frame_instance["verbe_fr"] = lemma_spacy
            frames.append(frame_instance)

    return frames

def slot_value_with_pos(token):
    if token is None:
        return None
    # Ajout : concatène adjectif(s) éventuel(s)
    text = token.text
    if hasattr(token, "children"):
        adjs = [child.text for child in token.children if child.pos_ == "ADJ"]
        if adjs:
            text = " ".join(adjs + [text])
    return {"text": text, "pos": token.pos_}

def fill_frame(verb_token, primitive, doc, frames_definition):
    frame_info = frames_definition.get(primitive, {})
    slots = frame_info.get("slots", [])

    frame_instance = {"primitive": primitive}
    for slot in slots:
        frame_instance[slot] = None

    if "agent" in frame_instance:
        frame_instance["agent"] = slot_value_with_pos(find_nsubj(verb_token, doc))
    if "objet" in frame_instance:
        frame_instance["objet"] = slot_value_with_pos(find_obj(verb_token, doc))
    if "source" in frame_instance or "destination" in frame_instance:
        src, dst = find_source_destination(verb_token)
        if "source" in frame_instance:
            frame_instance["source"] = slot_value_with_pos(src)
        if "destination" in frame_instance:
            frame_instance["destination"] = slot_value_with_pos(dst)
    if "instrument" in frame_instance:
        frame_instance["instrument"] = slot_value_with_pos(find_instrument(verb_token))
    if "manière" in frame_instance:
        frame_instance["manière"] = slot_value_with_pos(find_manner(verb_token))
    if "bénéficiaire" in frame_instance:
        frame_instance["bénéficiaire"] = slot_value_with_pos(find_beneficiaire(verb_token, doc))
    if "information" in frame_instance:
        frame_instance["information"] = slot_value_with_pos(find_information(verb_token))
    if "idées_source" in frame_instance:
        frame_instance["idées_source"] = slot_value_with_pos(find_ideas_source(verb_token))
    if "résultat" in frame_instance:
        frame_instance["résultat"] = slot_value_with_pos(find_result(verb_token))
    if "direction" in frame_instance:
        frame_instance["direction"] = slot_value_with_pos(find_direction(verb_token))
    if "force" in frame_instance:
        frame_instance["force"] = slot_value_with_pos(find_force(verb_token))
    if "substance" in frame_instance:
        frame_instance["substance"] = slot_value_with_pos(find_substance(verb_token))
    if "origin" in frame_instance:
        frame_instance["origin"] = slot_value_with_pos(find_origin(verb_token))
    if "message" in frame_instance:
        frame_instance["message"] = slot_value_with_pos(find_message(verb_token))
    if "audience" in frame_instance:
        frame_instance["audience"] = slot_value_with_pos(find_audience(verb_token, doc))
    if "cible_sens" in frame_instance:
        frame_instance["cible_sens"] = slot_value_with_pos(find_cible_sens(verb_token))

    return frame_instance

def find_nsubj(verb_token, doc):
    for child in verb_token.children:
        if child.dep_ == "nsubj":
            return child
    # Fallback : cherche NOUN/PROPN à gauche du verbe
    for tok in doc:
        if tok.i < verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_obj(verb_token, doc):
    for child in verb_token.children:
        if child.dep_ in ("obj", "dobj", "obj:obj"):
            return child
    # Fallback: NOUN à droite du verbe
    for tok in doc:
        if tok.i > verb_token.i and tok.pos_ == "NOUN":
            return tok
    return None

def find_source_destination(verb_token):
    source = None
    destination = None
    for child in verb_token.children:
        if child.dep_ in ("obl", "obl:arg", "obl:mod", "nmod"):
            prep_text = ""
            for grandchild in child.children:
                if grandchild.dep_ == "case":
                    prep_text = grandchild.text.lower()
            if prep_text in ("de", "du", "des", "d'"):
                if not source:
                    source = child
            elif prep_text in ("vers", "à", "au", "aux"):
                if not destination:
                    destination = child
            for subchild in child.children:
                for subgrandchild in subchild.children:
                    if subgrandchild.dep_ == "case":
                        sub_prep = subgrandchild.text.lower()
                        if sub_prep in ("de", "du", "des", "d'") and not source:
                            source = subchild
                        elif sub_prep in ("vers", "à", "au", "aux") and not destination:
                            destination = subchild
    return source, destination

def find_instrument(verb_token):
    return None

def find_manner(verb_token):
    advs = [child for child in verb_token.children if child.pos_ == "ADV"]
    if advs:
        return advs[0]
    return None

def find_beneficiaire(verb_token, doc):
    # Cherche iobj/obl:arg/obl/nmod à droite de l'objet (ex: à Pierre)
    for child in verb_token.children:
        if child.dep_ in ("iobj", "obl:arg", "obl", "obl:mod", "nmod"):
            for grandchild in child.children:
                if grandchild.dep_ == "case" and grandchild.text.lower() in ("à", "au", "aux", "a", "a'", "à l'", "a l'", "l'", "à l’"):
                    return child
    # Fallback : nmod à droite de l'objet ou du verbe
    for tok in doc:
        if tok.dep_ == "nmod" and tok.i > verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_information(verb_token):
    return None

def find_ideas_source(verb_token):
    return None

def find_result(verb_token):
    return None

def find_direction(verb_token):
    return None

def find_force(verb_token):
    return None

def find_substance(verb_token):
    direct_obj = find_obj(verb_token, verb_token.doc)
    if direct_obj:
        return direct_obj
    for child in verb_token.children:
        if child.dep_ in ("obl", "obl:mod"):
            prep_case = None
            for grandchild in child.children:
                if grandchild.dep_ == "case" and grandchild.text.lower() in ("de", "d'", "du", "des"):
                    prep_case = grandchild.text.lower()
            if prep_case:
                return child
    return None

def find_origin(verb_token):
    return None

def find_message(verb_token):
    return find_obj(verb_token, verb_token.doc)

def find_audience(verb_token, doc):
    for child in verb_token.children:
        if child.dep_ in ("iobj", "obl:arg", "obl", "obl:mod", "nmod"):
            for grandchild in child.children:
                if grandchild.dep_ == "case" and grandchild.text.lower() in ("à", "au", "aux", "a", "a'", "à l'", "a l'", "l'"):
                    return child
    for tok in doc:
        if tok.dep_ == "nmod" and tok.i > verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_cible_sens(verb_token):
    return find_obj(verb_token, verb_token.doc)
