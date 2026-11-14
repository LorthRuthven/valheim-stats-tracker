"""Lecteur VALHEIM .fch 1.0, profil v46-v47. LECTURE SEULE.

Les statistiques sont cumulées sur TOUS les mondes du personnage.
Les groupes de difficulté se recouvrent : NE JAMAIS les additionner.
Adaptation du format documenté par fch-decoder et ValheimSaveParser.
"""
from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

GROUPS = ('RawStats', 'Any', 'Hammer', 'Casual', 'VeryEasy', 'Easy',
          'Default', 'Hard', 'VeryHard', 'Hardcore')
MODIFIERS = ('Total', 'Poings', 'Magie', 'Distance', 'Mêlée')
BOSSES = {
    '$enemy_eikthyr': 'Eikthyr',
    '$enemy_gdking': 'L’Ancien',
    '$enemy_bonemass': 'Masse d’os',
    '$enemy_dragon': 'Moder',
    '$enemy_goblinking': 'Yagluth',
    '$enemy_seekerqueen': 'La Reine',
    '$enemy_fader': 'Fader',
    '$enemy_frozenking_p3': 'Kall Fimbulbringer',
}
SKILLS = {
    1:'Épées', 2:'Couteaux', 3:'Masses', 4:'Armes d’hast', 5:'Lances',
    6:'Blocage', 7:'Haches', 8:'Arcs', 9:'Magie élémentaire',
    10:'Magie du sang', 11:'Poings', 12:'Pioches', 13:'Coupe du bois',
    14:'Arbalètes', 100:'Saut', 101:'Discrétion', 102:'Course',
    103:'Natation', 104:'Pêche', 105:'Cuisine', 106:'Agriculture',
    107:'Artisanat', 108:'Esquive', 110:'Équitation',
}
DEATH_KINDS = {
    56:'Touché par un ennemi',58:'Chute',59:'Noyade',60:'Brûlure',
    61:'Gel',62:'Poison',63:'Fumée',65:'Bord du monde',68:'Arbre',
    71:'Tourelle',73:'Stalactite',105:'Catapulte',107:'Océan des Ashlands',
    108:'Incinérateur',203:'Pont-levis',204:'Lave des Ashlands',
}

class SaveError(Exception):
    pass

class Reader:
    def __init__(self, blob: bytes):
        self.data = blob
        self.pos = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise SaveError(f'Sauvegarde tronquée, décalage {self.pos}, longueur {n}')
        chunk = self.data[self.pos:self.pos+n]
        self.pos += n
        return chunk

    def number(self, fmt):
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self.take(size))[0]

    def i32(self): return self.number('<i')
    def i64(self): return self.number('<q')
    def u16(self): return self.number('<H')
    def f32(self): return self.number('<f')
    def u8(self): return self.number('<B')
    def bool(self): return bool(self.u8())
    def v3(self): return [self.f32(), self.f32(), self.f32()]

    def string(self):
        length = shift = 0
        for _ in range(5):
            b = self.u8()
            length |= (b & 127) << shift
            if b < 128:
                break
            shift += 7
        else:
            raise SaveError('Longueur de chaîne invalide')
        if length > 100_000:
            raise SaveError('Chaîne de sauvegarde trop longue')
        return self.take(length).decode('utf8')

    def mapping(self):
        count = self.i32()
        if not 0 <= count <= 20_000:
            raise SaveError(f'Dictionnaire invalide ({count})')
        out = {}
        for _ in range(count):
            key = self.string()
            out[key] = self.f32()
        return out

    def strings(self):
        n = self.i32()
        if not 0 <= n <= 15_000:
            raise SaveError(f'Liste de chaînes invalide ({n})')
        return [self.string() for _ in range(n)]

    def compact_count(self):
        first = self.u8()
        return ((first & 127) << 8) | self.u8() if first & 128 else first


def _read_items(r, inv_version):
    if inv_version not in (109, 110):
        raise SaveError(f'Version d’inventaire non prise en charge : {inv_version}')
    n = r.u16()
    if n > 512:
        raise SaveError('Inventaire trop grand')
    out = []
    for _ in range(n):
        durability = r.i32() / 100.0
        x, y, level, flags = r.u8(), r.u8(), r.u8(), r.u8()
        quality = r.u16() if flags & 4 else 1
        stack = r.u16() if flags & 8 else 1
        variant = r.i32() if flags & 16 else 0
        if flags & 32:
            r.i64()
            r.string()
        prefab_hash = r.i32() if flags & 64 else None
        if flags & 128:
            for _ in range(r.compact_count()):
                r.string()
                r.string()
        cheated = bool(r.u8() & 1)
        out.append({'hash':prefab_hash, 'x':x, 'y':y, 'level':level,
                    'quality':quality, 'stack':stack, 'variant':variant,
                    'durability':durability, 'equipped':bool(flags & 2),
                    'cheated':cheated})
    return out


def _read_player(body):
    r = Reader(body)
    version = r.i32()
    if version not in (33, 34):
        raise SaveError(f'Version des données du joueur inconnue : {version}')
    max_health = r.f32() if version >= 7 else None
    health = r.f32()
    max_stamina = r.f32() if version >= 10 else None
    if 8 <= version < 28: r.bool()
    if version >= 20: r.f32()  # temps depuis le dernier décès
    guardian = r.string() if version >= 23 else ''
    cooldown = r.f32() if version >= 24 else 0
    inv_ver = r.i32()
    inventory = _read_items(r, inv_ver)
    recipes = r.strings()
    stations = {}
    for _ in range(r.i32()):
        name = r.string()
        stations[name] = r.i32()
    materials = r.strings()
    tutorials = r.strings()
    uniques = r.strings()
    trophies = r.strings()
    biomes = r.strings() if version >= 33 or version == 31 else []
    texts = {}
    if version >= 22:
        for _ in range(r.i32()):
            key = r.string()
            texts[key] = r.string()
    if version >= 4:
        beard = r.string()
        hair = r.string()
    else:
        beard = hair = ''
    if version >= 5:
        r.v3()
        r.v3()
    if version >= 11: r.i32()
    if version >= 12:
        nf = r.i32()
        if not 0 <= nf < 100: raise SaveError('Nombre de nourritures invalide')
        for _ in range(nf):
            r.string()
            r.f32()
    skill_version = r.i32()
    skill_count = r.i32()
    if skill_version != 2 or not 0 <= skill_count <= 250:
        raise SaveError(f'Format des compétences non pris en charge {skill_version}/{skill_count}')
    skills = {}
    for _ in range(skill_count):
        k = r.i32()
        val = r.f32()
        acc = r.f32()
        skills[SKILLS.get(k, f'Compétence #{k}')] = {'level':val, 'xp':acc, 'id':k}
    return {'player_version':version,'inventory_version':inv_ver,
            'health':health,'max_health':max_health,'max_stamina':max_stamina,
            'guardian':guardian,'cooldown':cooldown,
            'inventory':inventory,'recipes_count':len(recipes),
            'materials_count':len(materials),'known_biomes':biomes,
            'skills':skills,'known_trophies':len(trophies)}


def decode(raw: bytes):
    """Décodage d'une COPIE mémoire; la sauvegarde source n'est jamais ouverte en écriture."""
    if len(raw) < 80:
        raise SaveError('Fichier trop court')
    length = struct.unpack_from('<I', raw)[0]
    if len(raw) != length + 72:
        raise SaveError('Longueur du fichier incompatible avec son en-tête')
    if struct.unpack_from('<I', raw, 4 + length)[0] != 64:
        raise SaveError('Taille de contrôle SHA-512 incorrecte')
    body = raw[4:4+length]
    if hashlib.sha512(body).digest() != raw[8+length:]:
        raise SaveError('Empreinte SHA-512 incorrecte (sauvegarde potentiellement incomplète)')
    r = Reader(body)
    version, count, sets_count = r.i32(), r.i32(), r.i32()
    if version not in (46,47) or count != 205 or sets_count != 10:
        raise SaveError(f'Format non pris en charge : v{version}, {count} compteurs, {sets_count} groupes')
    groups = {}
    for group in GROUPS:
        stats = [r.f32() for _ in range(count)]
        worlds = r.mapping()
        worldkeys = r.mapping()
        commands = r.mapping()
        ne = r.i32()
        if ne != 5:
            raise SaveError('Nombre de catégories de combat inattendu')
        enemies = [r.mapping() for _ in range(5)]
        groups[group] = {'stats':stats, 'worlds':worlds, 'worldkeys':worldkeys,
                         'commands':commands, 'enemies':enemies,
                         'picked_up':r.mapping(), 'crafted':r.mapping(),
                         'pickables':r.mapping(), 'foods_eaten':r.mapping(),
                         'pieces_built':r.mapping()}
    first_spawn = r.bool()
    nw = r.i32()
    if not 0 <= nw <= 300:
        raise SaveError('Nombre de mondes invalide')
    world_ids = []
    for _ in range(nw):
        key = r.i64()
        r.bool();r.v3()  # spawn
        r.bool();r.v3()  # logout
        r.bool();r.v3()  # death
        r.v3()           # home
        if r.bool():
            data_size = r.i32()
            if not 0 <= data_size <= 25_000_000:
                raise SaveError('Taille des données de carte invalide')
            r.take(data_size)
        world_ids.append(key)
    name = r.string()
    player_id = r.i64()
    start_seed = r.string()
    used_cheats = r.bool()
    created = r.i64()
    if not r.bool():
        raise SaveError('Sauvegarde sans données de joueur')
    player_data = r.take(r.i32())
    if r.pos != len(body):
        raise SaveError(f'Données de sauvegarde supplémentaires inattendues : {len(body)-r.pos} octets')
    player = _read_player(player_data)
    return {'name':name, 'version':version, 'created':created,
            'worlds_count':nw, 'first_spawn':first_spawn,
            'groups':groups, **player}


def read_file(path):
    return decode(Path(path).read_bytes())


def top_kills(parsed, group='Any'):
    return parsed['groups'][group]['enemies'][0]


def total_kills(parsed, group='Any'):
    # Total = somme de la table "MixedAndTotal" ; pas les 5 tables ajoutées.
    return int(round(sum(top_kills(parsed, group).values())))


def defeated_bosses(parsed, group='Any'):
    kills = top_kills(parsed, group)
    return {name:int(kills.get(token,0)) for token,name in BOSSES.items()}


def activity_total(parsed, category='crafted', group='Any'):
    return int(round(sum(parsed['groups'][group][category].values())))


def pretty_key(key):
    for prefix in ('$enemy_', '$item_', '$piece_', '$pickable_', '$animal_'):
        if key.startswith(prefix): return key[len(prefix):].replace('_',' ').title()
    return key.replace('_',' ').title()


def time_hours(seconds):
    return round(seconds/3600,1)


def metrics(parsed, group='Any'):
    data=parsed['groups'][group]
    raw=parsed['groups']['RawStats']
    seconds = sum(raw['worlds'].values())
    return {
        'deaths': int(data['stats'][0]),
        'kills': total_kills(parsed,group),
        'bosses': sum(v>0 for v in defeated_bosses(parsed,group).values()),
        'crafted': activity_total(parsed,'crafted',group),
        'built': activity_total(parsed,'pieces_built',group),
        'picked_up': activity_total(parsed,'picked_up',group),
        'world_hours': time_hours(seconds),
    }
