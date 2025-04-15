# translator/frame_builder.py (ultra-robuste: gestion tous cas SpaCy, slots, adjectifs, fallback)

import spacy
import unicodedata

nlp = spacy.load("fr_core_news_md")

def strip_punctuation_and_accents(text):
    # Retire ponctuation et accents
    text = ''.join(c for c in text if c.isalnum() or c.isspace())
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text

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

    # Analyse la phrase normale, puis fallback sans ponctuation/accents si frames vides
    doc = nlp(phrase)
    frames = _build_frames_from_doc(doc, knowledge_base, frames_definition)
    if not frames:
        doc = nlp(strip_punctuation_and_accents(phrase))
        frames = _build_frames_from_doc(doc, knowledge_base, frames_definition, fallback=True)
    # Si toujours rien, retourne un diagnostic spécial
    if not frames:
        return [{
            "type": "no_frame_detected",
            "diagnostic": [(t.text, t.lemma_, t.pos_, t.dep_, t.head.text) for t in doc]
        }]
    return frames

def _build_frames_from_doc(doc, knowledge_base, frames_definition, fallback=False):
    frames = []
    # 1. Prends tous les tokens VERB (peu importe leur dep_)
    verb_tokens = [tok for tok in doc if tok.pos_ == "VERB"]
    # 2. Si rien trouvé, prends tokens avec "VerbForm" dans la morpho
    if not verb_tokens:
        verb_tokens = [tok for tok in doc if "VerbForm" in tok.morph or tok.tag_ in {"VERB", "AUX"}]
    # 3. Si toujours rien, prends le ROOT et ses enfants
    if not verb_tokens:
        for tok in doc:
            if tok.dep_ == "ROOT":
                if tok.pos_ in ("VERB", "NOUN", "PROPN"):
                    verb_tokens.append(tok)
                for child in tok.children:
                    if child.pos_ == "VERB":
                        verb_tokens.append(child)
    # 4. S'il n'y a vraiment rien, prend tout NOUN/PROPN avec det/adjectif
    if not verb_tokens:
        for tok in doc:
            if tok.pos_ in ("NOUN", "PROPN") and (
                any(child.dep_ == "det" for child in tok.children) or
                any(child.pos_ == "ADJ" for child in tok.children)
            ):
                verb_tokens.append(tok)

    for token in verb_tokens:
        lemma_spacy = token.lemma_.lower()
        # Essaie toutes les variantes du lemma (avec et sans accents)
        verb_kb = get_from_kb_with_fallback(lemma_spacy, knowledge_base.get("verbes", {}))
        if not verb_kb:
            form_token = token.text.lower()
            verb_kb = get_from_kb_with_fallback(form_token, knowledge_base.get("verbes", {}))
            if not verb_kb:
                continue
            lemma_spacy = form_token

        primitive = verb_kb.get("primitive")
        if primitive:
            temps = detecter_temps_verb(token)
            frame_instance = fill_frame(token, primitive, doc, frames_definition)
            frame_instance["temps"] = temps
            frame_instance["verbe_fr"] = lemma_spacy
            if fallback:
                frame_instance["spaCy_fallback"] = True
            frames.append(frame_instance)
    return frames

def get_from_kb_with_fallback(key, kb_dict):
    # Essaie clé brute, puis sans accents, puis fallback None
    if key in kb_dict:
        return kb_dict[key]
    key_noacc = unaccent(key)
    if key_noacc in kb_dict:
        return kb_dict[key_noacc]
    return None

def unaccent(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def slot_value_with_pos(token):
    if token is None:
        return None
    # Récupère tous les adjectifs, déterminants, amod, poss à gauche
    elements = []
    if hasattr(token, "children"):
        # Trie les enfants par index pour garder l'ordre
        lefts = sorted([child for child in token.children
                        if child.dep_ in ("amod", "det", "poss") or child.pos_ == "ADJ"],
                       key=lambda t: t.i)
        for t in lefts:
            elements.append(t.text)
    elements.append(token.text)
    # Ajoute les adjectifs à droite (ex : pomme rouge foncé)
    if hasattr(token, "children"):
        rights = sorted([child for child in token.children
                        if child.dep_ in ("amod",) and child.i > token.i],
                        key=lambda t: t.i)
        for t in rights:
            elements.append(t.text)
    return {"text": " ".join(elements), "pos": token.pos_}

def fill_frame(verb_token, primitive, doc, frames_definition):
    frame_info = frames_definition.get(primitive, {})
    slots = frame_info.get("slots", [])
    frame_instance = {"primitive": primitive}
    for slot in slots:
        frame_instance[slot] = None

    # AGENT
    if "agent" in frame_instance:
        frame_instance["agent"] = slot_value_with_pos(find_nsubj(verb_token, doc))
    # OBJET
    if "objet" in frame_instance:
        frame_instance["objet"] = slot_value_with_pos(find_obj(verb_token, doc))
    # SOURCE/DEST
    if "source" in frame_instance or "destination" in frame_instance:
        src, dst = find_source_destination(verb_token)
        if "source" in frame_instance:
            frame_instance["source"] = slot_value_with_pos(src)
        if "destination" in frame_instance:
            frame_instance["destination"] = slot_value_with_pos(dst)
    # INSTRUMENT
    if "instrument" in frame_instance:
        frame_instance["instrument"] = slot_value_with_pos(find_instrument(verb_token, doc))
    # MANIERE
    if "manière" in frame_instance:
        frame_instance["manière"] = slot_value_with_pos(find_manner(verb_token))
    # BENEFICIAIRE
    if "bénéficiaire" in frame_instance:
        frame_instance["bénéficiaire"] = slot_value_with_pos(find_beneficiaire(verb_token, doc))
    # Slots additionnels
    if "information" in frame_instance:
        frame_instance["information"] = slot_value_with_pos(find_information(verb_token, doc))
    if "idées_source" in frame_instance:
        frame_instance["idées_source"] = slot_value_with_pos(find_ideas_source(verb_token, doc))
    if "résultat" in frame_instance:
        frame_instance["résultat"] = slot_value_with_pos(find_result(verb_token, doc))
    if "direction" in frame_instance:
        frame_instance["direction"] = slot_value_with_pos(find_direction(verb_token, doc))
    if "force" in frame_instance:
        frame_instance["force"] = slot_value_with_pos(find_force(verb_token, doc))
    if "substance" in frame_instance:
        frame_instance["substance"] = slot_value_with_pos(find_substance(verb_token, doc))
    if "origin" in frame_instance:
        frame_instance["origin"] = slot_value_with_pos(find_origin(verb_token, doc))
    if "message" in frame_instance:
        frame_instance["message"] = slot_value_with_pos(find_message(verb_token, doc))
    if "audience" in frame_instance:
        frame_instance["audience"] = slot_value_with_pos(find_audience(verb_token, doc))
    if "cible_sens" in frame_instance:
        frame_instance["cible_sens"] = slot_value_with_pos(find_cible_sens(verb_token, doc))

    return frame_instance

def find_nsubj(verb_token, doc):
    for child in verb_token.children:
        if child.dep_ == "nsubj":
            return child
    # Fallback : cherche NOUN/PROPN à gauche du verbe
    for tok in doc:
        if tok.i < verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    # Fallback : root s'il est NOUN/PROPN
    for tok in doc:
        if tok.dep_ == "ROOT" and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_obj(verb_token, doc):
    # Cherche obj, dobj, obj:obj
    for child in verb_token.children:
        if child.dep_ in ("obj", "dobj", "obj:obj"):
            return child
    # Fallback : NOUN/PROPN à droite du verbe
    for tok in doc:
        if tok.i > verb_token.i and tok.pos_ in ("NOUN", "PROPN"):
            return tok
    # Fallback : enfant det > NOUN
    for child in verb_token.children:
        if child.pos_ == "NOUN":
            return child
        for gchild in child.children:
            if gchild.dep_ == "det":
                return child
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
            # sous-compléments
            for subchild in child.children:
                for subgrandchild in subchild.children:
                    if subgrandchild.dep_ == "case":
                        sub_prep = subgrandchild.text.lower()
                        if sub_prep in ("de", "du", "des", "d'") and not source:
                            source = subchild
                        elif sub_prep in ("vers", "à", "au", "aux") and not destination:
                            destination = subchild
    return source, destination

def find_instrument(verb_token, doc):
    # Prend un "avec" ou "par" + NOUN
    for child in verb_token.children:
        if child.dep_ in ("obl", "obl:mod"):
            for gchild in child.children:
                if gchild.text.lower() in ("avec", "par"):
                    return child
    return None

def find_manner(verb_token):
    advs = [child for child in verb_token.children if child.pos_ == "ADV"]
    if advs:
        return advs[0]
    return None

def find_beneficiaire(verb_token, doc):
    # Cherche iobj, obl:arg, obl, nmod avec prep "à"
    for child in verb_token.children:
        if child.dep_ in ("iobj", "obl:arg", "obl", "obl:mod", "nmod"):
            for grandchild in child.children:
                if grandchild.dep_ == "case" and grandchild.text.lower() in (
                    "à", "au", "aux", "a", "a'", "à l'", "a l'", "l'", "à l’"
                ):
                    return child
    # Fallback : nmod à droite du verbe qui est un humain
    for tok in doc:
        if tok.dep_ == "nmod" and tok.i > verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_information(verb_token, doc):
    # Cherche NOUN obj ou nmod
    for child in verb_token.children:
        if child.pos_ == "NOUN" and child.dep_ in ("obj", "nmod"):
            return child
    return None

def find_ideas_source(verb_token, doc):
    return None

def find_result(verb_token, doc):
    return None

def find_direction(verb_token, doc):
    return None

def find_force(verb_token, doc):
    return None

def find_substance(verb_token, doc):
    direct_obj = find_obj(verb_token, doc)
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

def find_origin(verb_token, doc):
    return None

def find_message(verb_token, doc):
    return find_obj(verb_token, doc)

def find_audience(verb_token, doc):
    for child in verb_token.children:
        if child.dep_ in ("iobj", "obl:arg", "obl", "obl:mod", "nmod"):
            for grandchild in child.children:
                if grandchild.dep_ == "case" and grandchild.text.lower() in (
                    "à", "au", "aux", "a", "a'", "à l'", "a l'", "l'", "à l’"
                ):
                    return child
    for tok in doc:
        if tok.dep_ == "nmod" and tok.i > verb_token.i and tok.pos_ in ("PROPN", "NOUN"):
            return tok
    return None

def find_cible_sens(verb_token, doc):
    return find_obj(verb_token, doc)