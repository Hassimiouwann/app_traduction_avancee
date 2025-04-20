# translator/global_config.py

import os
import mysql.connector


def get_db_connection():
    """
    Établit une connexion à la base MySQL en utilisant les variables d'environnement.

    Variables utilisées :
      - DB_HOST (par défaut 'localhost')
      - DB_PORT (par défaut 3307)
      - DB_USER (par défaut 'root')
      - DB_PASS (par défaut '')
      - DB_NAME (par défaut 'translation_app')
    """
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3307)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASS", ""),
        database=os.getenv("DB_NAME", "translation_app"),
        charset="utf8mb4"
    )


def load_simple_table(table: str, key_col: str, val_col: str) -> dict:
    """
    Charge une table simple composée de deux colonnes key_col et val_col.
    Retourne un dict {key: value}.
    """
    cnx = get_db_connection()
    cur = cnx.cursor()
    cur.execute(f"SELECT {key_col}, {val_col} FROM {table}")
    result = {row[0]: row[1] for row in cur}
    cur.close()
    cnx.close()
    return result


def load_knowledge_base() -> dict:
    """
    Charge la knowledge_base depuis MySQL.
    Structure retournée identique à l'ancien JSON :
      {
        'verbes': { infinitive: {'primitive': ..., 'en': {tense: translation}}},
        'noms': {...},
        'adjectifs': {...},
        'adverbes': {...},
        'expressions': {...}
      }
    """
    cnx = get_db_connection()
    cur = cnx.cursor(dictionary=True)

    # Verbes et traductions
    cur.execute("SELECT id, infinitive, primitive FROM verbs")
    verbs = {}
    id_to_inf = {}
    for row in cur:
        vid = row['id']
        inf = row['infinitive']
        verbs[inf] = {'primitive': row['primitive'], 'en': {}}
        id_to_inf[vid] = inf

    cur.execute("SELECT verb_id, tense, translation FROM verb_translations")
    for row in cur:
        inf = id_to_inf.get(row['verb_id'])
        if inf:
            verbs[inf]['en'][row['tense']] = row['translation']

    cur.close()
    cnx.close()

    return {
        'verbes': verbs,
        'noms':        load_simple_table('nouns', 'fr', 'en'),
        'adjectifs':   load_simple_table('adjectives', 'fr', 'en'),
        'adverbes':    load_simple_table('adverbs', 'fr', 'en'),
        'expressions': load_simple_table('expressions', 'fr', 'en')
    }


def load_frames_config() -> dict:
    """
    Charge la frames_config depuis MySQL.
    Structure retournée identique à l'ancien JSON.
    """
    cnx = get_db_connection()
    cur = cnx.cursor(dictionary=True)

    # Primitives et slots
    cur.execute("SELECT primitive, description FROM primitives")
    frames_def = {r['primitive']: {'description': r['description'], 'slots': []} for r in cur}

    cur.execute("SELECT primitive, slot FROM frame_slots")
    for r in cur:
        frames_def[r['primitive']]['slots'].append(r['slot'])

    # Règles pour corps célestes
    cur.execute("SELECT `key`, subject_form, non_subject_form FROM celestial_bodies")
    celestial = {r['key']: {'subject_form': r['subject_form'], 'non_subject_form': r['non_subject_form']} for r in cur}

    # Primitive → verbe fallback
    cur.execute("SELECT primitive, verb_en FROM primitive_to_en_verb")
    prim2en = {r['primitive']: r['verb_en'] for r in cur}

    cur.close()
    cnx.close()

    return {
        'frames_definition':        frames_def,
        'celestial_bodies_rules':   celestial,
        'primitive_to_en_verb':     prim2en
    }


def load_global_config() -> dict:
    """
    Point d'entrée : charge knowledge_base et frames_config depuis MySQL.
    """
    return {
        'knowledge_base': load_knowledge_base(),
        'frames_config':  load_frames_config()
    }
