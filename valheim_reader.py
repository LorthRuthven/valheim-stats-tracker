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


# -- Suivi des succès (compteurs de sauvegarde Valheim 1.0.21) --
"""Règles de progression des succès Valheim 1.0.21 liées aux statistiques.

Ces règles reflètent les compteurs de sauvegarde et NE constituent PAS une lecture
technique de l'état des succès Steam. Les valeurs dans RawStats ne comptent pas :
seul le groupe Any (ou Default/Hard pour les boss) sert aux succès.

Table des PlayerStatType dans l'ordre Valheim 1.0.21 / profils v46-v47.
Références documentaires :
- https://github.com/lanchelms/fch-decoder/blob/main/valheim/names.go
- https://github.com/Melichor/ValheimSaveParser/blob/main/achi_hunter.py
- https://valheim.gamevault.in/achievements/
"""

from dataclasses import dataclass

"""Listes exactes de prefabs Valheim 1.0.21 pour succès de collection.

Références : Melichor/ValheimSaveParser, achi_hunter.py (listes extraites des
ressources du jeu par tools/update_achievement_lists.py) et fch-decoder.
Les clés sont figées dans la release et le tracker fonctionne hors ligne.
"""

_ENEMIES = '''$enemy_abomination|$enemy_asksvin|$enemy_asksvin_hatchling|$enemy_aspect_bonemass|$enemy_aspect_dragon|$enemy_aspect_eikthyr|$enemy_aspect_fader|$enemy_aspect_gdking|$enemy_aspect_goblinking|$enemy_aspect_seekerqueen|$enemy_babyseeker|$enemy_barka|$enemy_bat|$enemy_bjorn|$enemy_blob|$enemy_blobelite|$enemy_blobfrost|$enemy_bloblava|$enemy_blobmork|$enemy_blobmorkmini|$enemy_blobtar|$enemy_boar|$enemy_boarpiggy|$enemy_bonemawserpent|$enemy_charred_archer|$enemy_charred_mage|$enemy_charred_melee|$enemy_charred_melee_Dyrnwyn|$enemy_charred_melee_Fader|$enemy_charred_twitcher|$enemy_charred_twitcher_summoned|$enemy_chicken|$enemy_deathsquito|$enemy_deer|$enemy_drake|$enemy_draugr|$enemy_draugrelite|$enemy_dvergr|$enemy_dvergr_deepnorth|$enemy_dvergr_mage|$enemy_elaking|$enemy_elakingmole|$enemy_fallenvalkyrie|$enemy_fallenwarrior|$enemy_fenring|$enemy_fenringcultist|$enemy_fenringcultist_hildir|$enemy_frozenking|$enemy_ghost|$enemy_gjall|$enemy_goblin|$enemy_goblin_deepnorth|$enemy_goblin_hildir|$enemy_goblinbrute|$enemy_goblinbrute_hildircombined|$enemy_goblinshaman|$enemy_greydwarf|$enemy_greydwarfbrute|$enemy_greydwarfshaman|$enemy_greyling|$enemy_hare|$enemy_hen|$enemy_jotun_warrior|$enemy_jotun_witch|$enemy_kvastur|$enemy_leech|$enemy_lox|$enemy_loxcalf|$enemy_moose|$enemy_moosecalf|$enemy_morgen|$enemy_neck|$enemy_root|$enemy_seal|$enemy_seal_baby|$enemy_seeker|$enemy_seekerbrute|$enemy_serpent|$enemy_skeleton|$enemy_skeleton_summoned|$enemy_skeletonfire|$enemy_skeletonpoison|$enemy_stonegolem|$enemy_summonedtroll|$enemy_surtling|$enemy_tick|$enemy_troll|$enemy_trollfrost|$enemy_ulv|$enemy_unbjorn|$enemy_volture|$enemy_wolf|$enemy_wolfcub|$enemy_wraith|$enemy_writhan|$piece_trainingdummy|$spiritcaller_bjorn|$spiritcaller_boar|$spiritcaller_moose|$spiritcaller_wolf'''
_TROPHIES = '''$enemy_kvastur|$item_trophy_abomination|$item_trophy_asksvin|$item_trophy_barka|$item_trophy_bjorn|$item_trophy_bjorn_undead|$item_trophy_blob|$item_trophy_blob_frost|$item_trophy_blob_lava|$item_trophy_blob_morkhalla|$item_trophy_boar|$item_trophy_bonemass|$item_trophy_bonemaw|$item_trophy_brutebro|$item_trophy_charredarcher|$item_trophy_charredmage|$item_trophy_charredmelee|$item_trophy_cultist|$item_trophy_cultist_hildir|$item_trophy_deathsquito|$item_trophy_deer|$item_trophy_dragonqueen|$item_trophy_draugr|$item_trophy_draugrelite|$item_trophy_dvergr|$item_trophy_eikthyr|$item_trophy_elaking|$item_trophy_elder|$item_trophy_fader|$item_trophy_fallenvalkyrie|$item_trophy_fenring|$item_trophy_ghost|$item_trophy_gjall|$item_trophy_goblin|$item_trophy_goblinbrute|$item_trophy_goblinking|$item_trophy_goblinshaman|$item_trophy_greydwarf|$item_trophy_greydwarfbrute|$item_trophy_greydwarfshaman|$item_trophy_growth|$item_trophy_hare|$item_trophy_hatchling|$item_trophy_jotunwarrior|$item_trophy_jotunwitch|$item_trophy_leech|$item_trophy_lox|$item_trophy_mole|$item_trophy_moose|$item_trophy_morgen|$item_trophy_neck|$item_trophy_seal|$item_trophy_seeker|$item_trophy_seeker_brute|$item_trophy_seekerqueen|$item_trophy_serpent|$item_trophy_sgolem|$item_trophy_shamanbro|$item_trophy_skeleton|$item_trophy_skeleton_hildir|$item_trophy_skeletonpoison|$item_trophy_surtling|$item_trophy_tick|$item_trophy_troll|$item_trophy_ulv|$item_trophy_volture|$item_trophy_wolf|$item_trophy_wraith|$item_trophy_writhan'''
_WEAPONS = '''$item_atgeir_blackmetal|$item_atgeir_bronze|$item_atgeir_gold|$item_atgeir_gold_bloodlightning|$item_atgeir_gold_frostfire|$item_atgeir_himminafl|$item_atgeir_iron|$item_axe2h_gold|$item_axe2h_gold_bloodlightning|$item_axe2h_gold_frostfire|$item_axe_berzerkr|$item_axe_berzerkr_blood|$item_axe_berzerkr_lightning|$item_axe_berzerkr_nature|$item_axe_blackmetal|$item_axe_bronze|$item_axe_early|$item_axe_flint|$item_axe_gold|$item_axe_gold_bloodlightning|$item_axe_gold_frostfire|$item_axe_iron|$item_axe_jotunbane|$item_axe_stone|$item_battleaxe|$item_battleaxe_blackmetal|$item_battleaxe_crystal|$item_battleaxe_skullsplittur|$item_bilebomb|$item_bomb_dynamite|$item_bombblob_frost|$item_bombblob_lava|$item_bombblob_morkhalla|$item_bombblob_poison|$item_bombblob_poisonelite|$item_bombblob_tar|$item_bow|$item_bow_ashlands|$item_bow_ashlandsblood|$item_bow_ashlandsroot|$item_bow_ashlandsstorm|$item_bow_draugrfang|$item_bow_finewood|$item_bow_gold|$item_bow_gold_bloodlightning|$item_bow_gold_frostfire|$item_bow_huntsman|$item_bow_snipesnap|$item_club|$item_crossbow_arbalest|$item_crossbow_bloodlightning_gold|$item_crossbow_frostfire_gold|$item_crossbow_gold|$item_crossbow_ripper|$item_crossbow_ripper_blood|$item_crossbow_ripper_lightning|$item_crossbow_ripper_nature|$item_fistweapon_bjorn|$item_fistweapon_bjorn_undead|$item_fistweapon_fenris|$item_fistweapon_frostfire_gold|$item_fistweapon_gold|$item_fistweapon_gold_bloodlightning|$item_graplinghook|$item_knife_blackmetal|$item_knife_butcher|$item_knife_chitin|$item_knife_copper|$item_knife_flint|$item_knife_gold|$item_knife_gold_bloodlightning|$item_knife_gold_frostfire|$item_knife_silver|$item_knife_skollandhati|$item_mace2h_gold_bloodlightning|$item_mace2h_gold_frostfire|$item_mace_bronze|$item_mace_eldner|$item_mace_eldner_blood|$item_mace_eldner_lightning|$item_mace_eldner_nature|$item_mace_gold|$item_mace_gold_bloodlightning|$item_mace_gold_frostfire|$item_mace_iron|$item_mace_needle|$item_mace_silver|$item_oozebomb|$item_pickaxe_antler|$item_pickaxe_blackmetal|$item_pickaxe_bronze|$item_pickaxe_iron|$item_scythe|$item_sledge_demolisher|$item_sledge_gold|$item_sledge_iron|$item_spear_ancientbark|$item_spear_bronze|$item_spear_carapace|$item_spear_chitin|$item_spear_flint|$item_spear_gold|$item_spear_gold_bloodlightning|$item_spear_gold_frostfire|$item_spear_splitner|$item_spear_splitner_blood|$item_spear_splitner_lightning|$item_spear_splitner_nature|$item_spear_wolffang|$item_staff_frostorbs|$item_staff_lightning|$item_staff_orbofahri|$item_staff_spiritcaller|$item_staff_thunderblood|$item_staffclusterbomb|$item_stafffireball|$item_staffgreenroots|$item_stafficeshards|$item_staffredtroll|$item_staffshield|$item_staffskeleton|$item_stagbreaker|$item_sword2h_gold|$item_sword2h_gold_bloodlightning|$item_sword2h_gold_frostfire|$item_sword_blackmetal|$item_sword_bronze|$item_sword_dyrnwyn|$item_sword_gold|$item_sword_gold_bloodlightning|$item_sword_gold_frostfire|$item_sword_iron|$item_sword_krom|$item_sword_mistwalker|$item_sword_niedhogg|$item_sword_niedhogg_blood|$item_sword_niedhogg_lightning|$item_sword_niedhogg_nature|$item_sword_silver|$item_sword_slayer|$item_sword_slayer_blood|$item_sword_slayer_lightning|$item_sword_slayer_nature|$item_sword_wood|$item_torch'''
_COOKED = '''$item_asksvin_meat_cooked|$item_bakedpoteitr|$item_bakedpoteitr_uncooked|$item_bjorn_meat_cooked|$item_blacksoup|$item_bloodpudding|$item_blubber_cooked|$item_boar_meat_cooked|$item_boarjerky|$item_bonemawmeat_cooked|$item_bread|$item_breaddough|$item_bug_meat_cooked|$item_carrotsoup|$item_chicken_meat_cooked|$item_deer_meat_cooked|$item_deerstew|$item_egg_cooked|$item_eyescream|$item_fierysvinstew|$item_fish_cooked|$item_fish_raw|$item_fishandbread|$item_fishandbreaduncooked|$item_fishsoup|$item_fishwraps|$item_hare_meat_cooked|$item_honeyglazedchicken|$item_honeyglazedchickenuncooked|$item_kalechips|$item_kalechips_uncooked|$item_lingondricka|$item_loxmeat_cooked|$item_loxpie|$item_loxpie_uncooked|$item_magicallystuffedmushroom|$item_magicallystuffedmushroomuncooked|$item_marinatedgreens|$item_mashedmeat|$item_meatballsmashedpoteitr|$item_meatplatter|$item_meatplatteruncooked|$item_mincemeatsauce|$item_mistharesupreme|$item_mistharesupremeuncooked|$item_moose_meat_cooked|$item_moosekebab|$item_mushroomomelette|$item_necktailgrilled|$item_oatmeallingonberryjam|$item_oatmilk|$item_onionsoup|$item_ovenpancake|$item_ovenpancake_uncooked|$item_pancakes|$item_piquantpie|$item_piquantpie_uncooked|$item_pulledbear|$item_queensjam|$item_roastedcrustpie|$item_roastedcrustpie_uncooked|$item_salad|$item_sausages|$item_scorchingmedley|$item_sealsoup|$item_seekeraspic|$item_serpentmeatcooked|$item_serpentstew|$item_shocklatesmoothie|$item_sizzlingberrybroth|$item_smokedfish|$item_smokedmoosemeat|$item_sparklingshroomshake|$item_spicymarmalade|$item_turnipstew|$item_vikingcupcake|$item_vikingcupcake_uncooked|$item_volture_meat_cooked|$item_wolf_meat_cooked|$item_wolf_skewer|$item_wolfjerky|$item_yggdrasilporridge'''
_EATEN = '''$item_asksvin_meat_cooked|$item_bakedpoteitr|$item_bjorn_meat_cooked|$item_blacksoup|$item_bloodpudding|$item_blubber_cooked|$item_blueberries|$item_boar_meat_cooked|$item_boarjerky|$item_bonemawmeat_cooked|$item_bread|$item_bug_meat_cooked|$item_carrot|$item_carrotsoup|$item_chicken_meat_cooked|$item_cloudberries|$item_deer_meat_cooked|$item_deerstew|$item_egg_cooked|$item_eyescream|$item_feastashlands|$item_feastblackforest|$item_feastdeepnorth|$item_feastmeadows|$item_feastmistlands|$item_feastmountains|$item_feastoceans|$item_feastplains|$item_feastswamps|$item_fiddleheadfern|$item_fierysvinstew|$item_fish_cooked|$item_fishandbread|$item_fishsoup|$item_fishwraps|$item_glowworm|$item_hare_meat_cooked|$item_honey|$item_honeyglazedchicken|$item_jotunpuffs|$item_kale|$item_kalechips|$item_lingonberries|$item_lingondricka|$item_loxmeat_cooked|$item_loxpie|$item_magecap|$item_magicallystuffedmushroom|$item_marinatedgreens|$item_mashedmeat|$item_meatballsmashedpoteitr|$item_meatplatter|$item_mincemeatsauce|$item_mistharesupreme|$item_moose_meat_cooked|$item_moosekebab|$item_mushroomcommon|$item_mushroomomelette|$item_mushroomyellow|$item_necktailgrilled|$item_oat|$item_oatmeallingonberryjam|$item_oatmilk|$item_onion|$item_onionsoup|$item_ovenpancake|$item_pancakes|$item_piquantpie|$item_poteitr|$item_pulledbear|$item_queensjam|$item_raspberries|$item_roastedcrustpie|$item_royaljelly|$item_salad|$item_sausages|$item_scorchingmedley|$item_sealsoup|$item_seekeraspic|$item_serpentmeatcooked|$item_serpentstew|$item_shocklatesmoothie|$item_sizzlingberrybroth|$item_smokedfish|$item_smokedmoosemeat|$item_smokepuff|$item_sparklingshroomshake|$item_spicymarmalade|$item_turnipstew|$item_vikingcupcake|$item_vineberry|$item_volture_meat_cooked|$item_wolf_meat_cooked|$item_wolf_skewer|$item_wolfjerky|$item_yggdrasilporridge'''
_CRAFT_EXTRA = '''$item_arrow_bloodgold|$item_arrow_bronze|$item_arrow_carapace|$item_arrow_charred|$item_arrow_fire|$item_arrow_flint|$item_arrow_frost|$item_arrow_iron|$item_arrow_needle|$item_arrow_obsidian|$item_arrow_poison|$item_arrow_silver|$item_arrow_wood|$item_atgeir_gold_uncooked|$item_axe_gold_uncooked|$item_barleywinebase|$item_battleaxe_gold_uncooked|$item_bell|$item_bolt_blackmetal|$item_bolt_bloodgold|$item_bolt_bone|$item_bolt_carapace|$item_bolt_charred|$item_bolt_iron|$item_bow_gold_uncooked|$item_bronze|$item_bronzenails|$item_cape_ash|$item_cape_asksvin|$item_cape_deepnorth|$item_cape_deepnorth_mage|$item_cape_deerhide|$item_cape_feather|$item_cape_linen|$item_cape_lox|$item_cape_trollhide|$item_cape_wolf|$item_catapult_ammo|$item_catapult_bloodgold_ammo|$item_catapult_training_ammo|$item_ceramicplate|$item_chest_berserker|$item_chest_berserker_undead|$item_chest_bronze|$item_chest_carapace|$item_chest_fenris|$item_chest_flametal|$item_chest_heavy_deepnorth|$item_chest_heavy_gold_uncooked|$item_chest_iron|$item_chest_leather|$item_chest_lox|$item_chest_mage|$item_chest_mage_ashlands|$item_chest_mage_deepnorth|$item_chest_mage_gold_uncooked|$item_chest_medium_ashlands|$item_chest_medium_deepnorth|$item_chest_medium_gold_uncooked|$item_chest_pcuirass|$item_chest_rags|$item_chest_root|$item_chest_trollleather|$item_chest_wolf|$item_crossbow_gold_uncooked|$item_cultivator|$item_demister|$item_dvergrkey|$item_feastashlands|$item_feastblackforest|$item_feastdeepnorth|$item_feastmeadows|$item_feastmistlands|$item_feastmountains|$item_feastoceans|$item_feastplains|$item_feastswamps|$item_fireworkrocket_blue|$item_fireworkrocket_cyan|$item_fireworkrocket_green|$item_fireworkrocket_purple|$item_fireworkrocket_red|$item_fireworkrocket_yellow|$item_fishingbait_ashlands|$item_fishingbait_cave|$item_fishingbait_deepnorth|$item_fishingbait_forest|$item_fishingbait_mistlands|$item_fishingbait_ocean|$item_fishingbait_plains|$item_fishingbait_swamp|$item_fistweapon_gold_uncooked|$item_frostorbs_uncooked|$item_helmet_berserker|$item_helmet_berserker_undead|$item_helmet_bronze|$item_helmet_carapace|$item_helmet_celebration|$item_helmet_crown_of_valheim|$item_helmet_drake|$item_helmet_fenris|$item_helmet_fishinghat|$item_helmet_flametal|$item_helmet_heavy_deepnorth|$item_helmet_heavy_gold_uncooked|$item_helmet_iron|$item_helmet_leather|$item_helmet_lox|$item_helmet_mage|$item_helmet_mage_ashlands|$item_helmet_mage_deepnorth|$item_helmet_mage_gold_uncooked|$item_helmet_medium_ashlands|$item_helmet_medium_deepnorth|$item_helmet_medium_gold_uncooked|$item_helmet_padded|$item_helmet_root|$item_helmet_trollleather|$item_hoe|$item_ironnails|$item_keys_gold_uncooked|$item_knife_gold_uncooked|$item_legs_berserker|$item_legs_berserker_undead|$item_legs_bronze|$item_legs_carapace|$item_legs_fenris|$item_legs_flametal|$item_legs_heavy_deepnorth|$item_legs_heavy_gold_uncooked|$item_legs_iron|$item_legs_leather|$item_legs_lox|$item_legs_mage|$item_legs_mage_ashlands|$item_legs_mage_deepnorth|$item_legs_mage_gold_uncooked|$item_legs_medium_ashlands|$item_legs_medium_deepnorth|$item_legs_medium_gold_uncooked|$item_legs_pgreaves|$item_legs_rags|$item_legs_root|$item_legs_trollleather|$item_legs_wolf|$item_mace_gold_uncooked|$item_meadbasebugrepellent|$item_meadbasebzerker|$item_meadbaseeitr|$item_meadbaseeitr_lingering|$item_meadbasefrostresist|$item_meadbasehasty|$item_meadbasehealth|$item_meadbasehealth_lingering|$item_meadbasehealth_major|$item_meadbasehealth_medium|$item_meadbaselightfoot|$item_meadbasepoisonresist|$item_meadbasestamina|$item_meadbasestamina_lingering|$item_meadbasestamina_medium|$item_meadbasestrength|$item_meadbaseswimmer|$item_meadbasetamer|$item_meadbasetasty|$item_mechanicalspring|$item_saddleasksvin|$item_saddlelox|$item_saddlemoose|$item_sharpeningstone|$item_shield_banded|$item_shield_blackmetal|$item_shield_blackmetal_tower|$item_shield_bonetower|$item_shield_bronzebuckler|$item_shield_buckler_gold_uncooked|$item_shield_carapace|$item_shield_carapacebuckler|$item_shield_flametal|$item_shield_flametal_tower|$item_shield_gold|$item_shield_gold_tower|$item_shield_goldbuckler|$item_shield_iron_tower|$item_shield_ironbuckler|$item_shield_roots|$item_shield_round_gold_uncooked|$item_shield_serpentscale|$item_shield_silver|$item_shield_tower_gold_uncooked|$item_shield_wood|$item_shield_woodtower|$item_shieldcore|$item_sledge_gold_uncooked|$item_spear_gold_uncooked|$item_staff_orbofahri_uncooked|$item_staff_spiritcaller_uncooked|$item_staff_thunderblood_uncooked|$item_sword2h_gold_uncooked|$item_sword_gold_uncooked|$item_trinketblackdamagedealth|$item_trinketblackdtamina|$item_trinketbloodgoldhealth|$item_trinketbloodgoldstamina|$item_trinketbronzehealth|$item_trinketbronzestamina|$item_trinketcarapaceeitr|$item_trinketchitinswim|$item_trinketflametaleitr|$item_trinketflametalstaminahealth|$item_trinketironhealth|$item_trinketironstamina|$item_trinketscalestaminadamage|$item_trinketsilverdamage|$item_trinketsilverresist|$item_turretbolt|$item_turretbolt_bloodgold|$item_turretbolt_flametal|$item_turretboltwood'''
_NOT_CRAFTABLE = '''$item_axe_stone|$item_club|$item_torch|$item_asksvin_meat_cooked|$item_bakedpoteitr|$item_bjorn_meat_cooked|$item_blubber_cooked|$item_boar_meat_cooked|$item_bonemawmeat_cooked|$item_bread|$item_bug_meat_cooked|$item_chicken_meat_cooked|$item_deer_meat_cooked|$item_fish_cooked|$item_fishandbread|$item_hare_meat_cooked|$item_honeyglazedchicken|$item_kalechips|$item_loxmeat_cooked|$item_loxpie|$item_magicallystuffedmushroom|$item_meatplatter|$item_mistharesupreme|$item_moose_meat_cooked|$item_necktailgrilled|$item_ovenpancake|$item_piquantpie|$item_roastedcrustpie|$item_serpentmeatcooked|$item_vikingcupcake|$item_volture_meat_cooked|$item_wolf_meat_cooked'''
_BUILDABLE = '''$item_hardrock|$piece_BlackwoodStakewall|$piece_archerytarget|$piece_armorstand|$piece_artisan_ext1|$piece_artisanstation|$piece_ashwood_archedwall|$piece_ashwood_beam_1m|$piece_ashwood_beam_2m|$piece_ashwood_bed|$piece_ashwood_decowall|$piece_ashwood_decowall_divider|$piece_ashwood_decowall_tree|$piece_ashwood_door|$piece_ashwood_floor_1x1|$piece_ashwood_floor_2x2|$piece_ashwood_floor_deco|$piece_ashwood_halfwall|$piece_ashwood_pole_1m|$piece_ashwood_pole_2m|$piece_ashwood_quarterwall|$piece_ashwood_wall|$piece_ashwoodarch_big|$piece_ashwoodbeam26|$piece_ashwoodbeam45|$piece_ashwoodbeam67|$piece_ashwoodcross26|$piece_ashwoodcross45|$piece_ashwoodstair|$piece_ashwoodwallroof67|$piece_ashwoodwallroof67upsidedown|$piece_ashwoodwallroof_26|$piece_ashwoodwallroof_26_upsidedown|$piece_ashwoodwallroof_45|$piece_ashwoodwallroof_45_upsidedown|$piece_ashwoodwallrooftop67|$piece_asksvinskeleton|$piece_banner01|$piece_banner02|$piece_banner03|$piece_banner04|$piece_banner05|$piece_banner06|$piece_banner07|$piece_banner08|$piece_banner09|$piece_banner10|$piece_banner11|$piece_barber|$piece_bathtub|$piece_bed|$piece_bed02|$piece_beehive|$piece_bench01|$piece_bench_runed|$piece_benchlog|$piece_birdnest|$piece_blackforge|$piece_blackforge_ext1|$piece_blackforge_ext2|$piece_blackforge_ext3|$piece_blackforge_ext4|$piece_blackforge_ext5|$piece_blackmarble1x1|$piece_blackmarble2x1x1|$piece_blackmarble2x2x2|$piece_blackmarble_arch|$piece_blackmarble_base1|$piece_blackmarble_basecorner|$piece_blackmarble_bench|$piece_blackmarble_column_1|$piece_blackmarble_column_2|$piece_blackmarble_floor|$piece_blackmarble_floor_triangle|$piece_blackmarble_out1|$piece_blackmarble_outcorner|$piece_blackmarble_stair|$piece_blackmarble_table|$piece_blackmarble_throne|$piece_blackmarble_tip|$piece_blackmetalbarstack|$piece_blackwoodbench01|$piece_blackwoodstack|$piece_blastfurnace|$piece_bloodgoldbarstack|$piece_bone_throne|$piece_bonestack|$piece_bonfire|$piece_brazierceiling01|$piece_brazierfloor01|$piece_brazierfloor02|$piece_bronzebarstack|$piece_candle|$piece_cartographytable|$piece_cauldron|$piece_cauldron_ext1_spice|$piece_cauldron_ext3_butchertable|$piece_cauldron_ext4_pans|$piece_cauldron_ext5_mortarandpestle|$piece_cauldron_ext6_rollingpins|$piece_cauldron_ext7_smoker|$piece_celebrationgarland|$piece_chair|$piece_chair_runed|$piece_charcoalkiln|$piece_chest|$piece_chestbarrel|$piece_chestblackmetal|$piece_chestgrausten|$piece_chestprivate|$piece_chesttreasure|$piece_chestwarderobe|$piece_chestwood|$piece_clothdoor|$piece_coalpile|$piece_cookingstation|$piece_cookingstation_iron|$piece_copperbarstack|$piece_crystalwall1x1|$piece_darkwoodarch|$piece_darkwoodbeam|$piece_darkwoodbeam4|$piece_darkwoodbeam67|$piece_darkwoodbeam_26|$piece_darkwoodbeam_45|$piece_darkwoodchair|$piece_darkwooddecowall|$piece_darkwoodgate|$piece_darkwoodpole|$piece_darkwoodpole4|$piece_darkwoodraven|$piece_darkwoodroof26|$piece_darkwoodroof45|$piece_darkwoodroof67|$piece_darkwoodrooficorner|$piece_darkwoodrooficorner45|$piece_darkwoodrooficorner67|$piece_darkwoodroofocorner|$piece_darkwoodroofocorner45|$piece_darkwoodroofocorner67|$piece_darkwoodrooftop|$piece_darkwoodrooftop45|$piece_darkwoodrooftop67|$piece_darkwoodwolf|$piece_deco_stave_wall|$piece_drawbridge_dn|$piece_drawbridge_log|$piece_dvergr_lantern|$piece_dvergr_lantern_pole|$piece_dvergr_metal_wall|$piece_dvergr_sharpstakes|$piece_dvergr_spiralstair|$piece_dvergr_spiralstair_right|$piece_dvergr_stake_wall|$piece_eitrrefinery|$piece_faderember|$piece_fairylightgarland|$piece_fermenter|$piece_firepit|$piece_firepit_iron|$piece_flametal_beam|$piece_flametal_pillar|$piece_flametalbarstack|$piece_flametalgate|$piece_flintpile|$piece_forge|$piece_forge_ext1|$piece_forge_ext2|$piece_forge_ext3|$piece_forge_ext4|$piece_forge_ext5|$piece_forge_ext6|$piece_frostfoundry|$piece_frostkiln|$piece_grausten_archmedium|$piece_grausten_archsmall|$piece_grausten_beammedium|$piece_grausten_beamsmall|$piece_grausten_floor1x1|$piece_grausten_floor2x2|$piece_grausten_floor4x4|$piece_grausten_pillarmedium|$piece_grausten_pillarsmall|$piece_grausten_pillartapered|$piece_grausten_pillartaperedinverted|$piece_grausten_roof45|$piece_grausten_roof45_arch|$piece_grausten_roof45_archcorner|$piece_grausten_roof45_archcorner2|$piece_grausten_roof45_corner|$piece_grausten_roof45_corner2|$piece_grausten_stair|$piece_grausten_stoneladder|$piece_grausten_wall1x2|$piece_grausten_wall2x2|$piece_grausten_wall4x2|$piece_grausten_wallarch|$piece_grausten_wallarchinv|$piece_grausten_window2x2|$piece_grausten_window4x2|$piece_graustenpile|$piece_groundtorch|$piece_groundtorchblue|$piece_groundtorchdemister|$piece_groundtorchgreen|$piece_groundtorchwood|$piece_guardstone|$piece_hanging_cloth_blue1|$piece_hanging_cloth_blue2|$piece_hearth|$piece_hexagonalgate|$piece_hoodedlantern|$piece_icecube|$piece_incinerator|$piece_ironbarstack|$piece_ironfloor|$piece_ironfloorSmall|$piece_irongate|$piece_ironwall|$piece_ironwallSmall|$piece_ironwoodbeam67|$piece_itemstand|$piece_jackoturnip|$piece_jute_carpet|$piece_juteblue_carpet|$piece_lavalantern|$piece_logbeam2|$piece_logbeam4|$piece_logpole2|$piece_logpole4|$piece_magetable|$piece_magetable_ext|$piece_magetable_ext2|$piece_magetable_ext3|$piece_magetable_ext4|$piece_marblepile|$piece_maypole|$piece_meadcauldron|$piece_mistletoe|$piece_moose_throne|$piece_oven|$piece_portal|$piece_portal_stone|$piece_pot_large_green|$piece_pot_medium_green|$piece_pot_small_green|$piece_preptable|$piece_rug_asksvin|$piece_rug_bjorn|$piece_rug_deer|$piece_rug_hare|$piece_rug_lox|$piece_rug_moose|$piece_rug_seal|$piece_rug_straw|$piece_rug_wolf|$piece_sapcollector|$piece_scale_26|$piece_scale_26_flipped|$piece_scale_26_upsidedown|$piece_scale_26_upsidedown_flipped|$piece_scale_45|$piece_scale_45_flipped|$piece_scale_45_upsidedown|$piece_scale_45_upsidedown_flipped|$piece_scale_67|$piece_scale_67_flipped|$piece_scale_67_upsidedown|$piece_scale_67_upsidedown_flipped|$piece_scale_halfwall|$piece_scale_quarterwall|$piece_scale_wall|$piece_sconce|$piece_sharpstakes|$piece_shieldgenerator|$piece_sign|$piece_silverbarstack|$piece_skullpile|$piece_smelter|$piece_snowlantern|$piece_spinningwheel|$piece_stakewall|$piece_stave_deco_beam_2m|$piece_stave_deco_pole_2m|$piece_stave_pole_2m|$piece_stave_pole_4m|$piece_stave_wall|$piece_stavebeam2|$piece_stavebeam26|$piece_stavebeam4|$piece_stavebeam45|$piece_stavebeam67|$piece_stavecross26|$piece_stavecross45|$piece_stavedecobeam26|$piece_stavedecobeam45|$piece_stavedecobeam67|$piece_stavegate|$piece_stavewallrooftop67|$piece_stonearch|$piece_stonecutter|$piece_stonefence|$piece_stonefloor2x2|$piece_stonepile|$piece_stonepillar|$piece_stonestair|$piece_stonethrone|$piece_stonewall1x1|$piece_stonewall2x1|$piece_stonewall4x2|$piece_stool|$piece_table|$piece_table_oak|$piece_table_round|$piece_table_runed|$piece_table_runed_small|$piece_throne01|$piece_tinbarstack|$piece_trainingdummy|$piece_trap|$piece_treasure_pile|$piece_treasure_stack|$piece_turret|$piece_windmill|$piece_wisplure|$piece_woodbeam1|$piece_woodbeam2|$piece_woodbeam26|$piece_woodbeam45|$piece_woodbeam67|$piece_woodcorestack|$piece_wooddoor|$piece_wooddragon|$piece_woodfence|$piece_woodfencegate|$piece_woodfinestack|$piece_woodfloor1x1|$piece_woodfloor2x2|$piece_woodfroststack|$piece_woodgate|$piece_woodironbeam|$piece_woodironbeam_26|$piece_woodironbeam_45|$piece_woodironpole|$piece_woodlog26|$piece_woodlog45|$piece_woodlog67|$piece_woodpole|$piece_woodpole2|$piece_woodroof26|$piece_woodroof45|$piece_woodroof67|$piece_woodrooficorner|$piece_woodrooficorner45|$piece_woodrooficorner67|$piece_woodroofocorner|$piece_woodroofocorner45|$piece_woodroofocorner67|$piece_woodrooftop|$piece_woodrooftop45|$piece_woodrooftop67|$piece_woodstack|$piece_woodstair|$piece_woodstepladder|$piece_woodwall|$piece_woodwallhalf|$piece_woodwallquarter|$piece_woodwallroof|$piece_woodwallroof45|$piece_woodwallroof45_upsidedown|$piece_woodwallroof67|$piece_woodwallroof67upsidedown|$piece_woodwallroof_upsidedown|$piece_woodwallrooftop|$piece_woodwallrooftop45|$piece_woodwallrooftop67|$piece_woodwindowshutter|$piece_workbench|$piece_workbench_ext1|$piece_workbench_ext2|$piece_workbench_ext3|$piece_workbench_ext4|$piece_yggdrasilstack|$piece_yulecrown|$piece_yulegarland|$piece_yuleklapp|$piece_yuletree|$ship_karve|$ship_longship|$ship_longship_ashlands|$ship_raft|$tool_batteringram|$tool_cart|$tool_catapult'''

COLLECTIONS = {
    'hunter': tuple(_ENEMIES.split('|')),
    'master_hunter': tuple(_ENEMIES.split('|')),
    'trophy_collector': tuple(_TROPHIES.split('|')),
    'blacksmith': tuple(_WEAPONS.split('|')),
    'master_chef': tuple(_COOKED.split('|')),
    'gourmet': tuple(_EATEN.split('|')),
    'carpenter': tuple(_BUILDABLE.split('|')),
    'artisan': tuple(sorted((set(_WEAPONS.split('|')) | set(_COOKED.split('|'))
                             | set(_CRAFT_EXTRA.split('|'))) - set(_NOT_CRAFTABLE.split('|')))),
}
EXPECTED_COUNTS = {
    'hunter': 100, 'master_hunter': 100,
    'trophy_collector': 69, 'blacksmith': 145, 'master_chef': 82,
    'gourmet': 96, 'carpenter': 394, 'artisan': 414,
}
for _key, _tokens in COLLECTIONS.items():
    assert len(_tokens) == EXPECTED_COUNTS[_key], (_key, len(_tokens), EXPECTED_COUNTS[_key])
    assert len(set(_tokens)) == len(_tokens), 'Token en double : ' + _key


from localization_fr import localized_name


def prefab_label(token: str) -> str:
    """Nom humain lisible, sans code $item_/$piece_ ni identifiant brut."""
    import re
    name = token.lstrip('$')
    for prefix in ('enemy_', 'item_', 'piece_', 'animal_', 'ship_', 'tool_', 'spiritcaller_'):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break
    name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    name = name.replace('_', ' ').strip()
    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+(?:x[0-9]+)?', name)
    if words:
        name = ' '.join(words)
    fallback = name[:1].upper() + name[1:] if name else token
    return localized_name(token, fallback)



# Il faut garder les 205 entrées : le format .fch contient un tableau indexé.
PLAYER_STAT_NAMES = tuple("""
Deaths
CraftsOrUpgrades
Builds
Jumps
Cheats
EnemyHits
EnemyKills
EnemyKillsLastHits
PlayerHits
PlayerKills
HitsTakenEnemies
HitsTakenPlayers
ItemsPickedUp
Crafts
Upgrades
PortalsUsed
DistanceTraveled
DistanceWalk
DistanceRun
DistanceSail
DistanceAir
TimeInBase
TimeOutOfBase
Sleep
ItemStandUses
ArmorStandUses
WorldLoads
TreeChops
Tree
TreeTier0
TreeTier1
TreeTier2
TreeTier3
TreeTier4
TreeTier5
LogChops
Logs
MineHits
Mines
MineTier0
MineTier1
MineTier2
MineTier3
MineTier4
MineTier5
RavenHits
RavenTalk
RavenAppear
CreatureTamed
FoodEaten
SkeletonSummons
ArrowsShot
TombstonesOpenedOwn
TombstonesOpenedOther
TombstonesFit
DeathByUndefined
DeathByEnemyHit
DeathByPlayerHit
DeathByFall
DeathByDrowning
DeathByBurning
DeathByFreezing
DeathByPoisoned
DeathBySmoke
DeathByWater
DeathByEdgeOfWorld
DeathByImpact
DeathByCart
DeathByTree
DeathBySelf
DeathByStructural
DeathByTurret
DeathByBoat
DeathByStalagtite
DoorsOpened
DoorsClosed
BeesHarvested
SapHarvested
TurretAmmoAdded
TurretTrophySet
TrapArmed
TrapTriggered
PlaceStacks
PortalDungeonIn
PortalDungeonOut
BossKills
BossLastHits
SetGuardianPower
SetPowerEikthyr
SetPowerElder
SetPowerBonemass
SetPowerModer
SetPowerYagluth
SetPowerQueen
SetPowerAshlands
SetPowerDeepNorth
UseGuardianPower
UsePowerEikthyr
UsePowerElder
UsePowerBonemass
UsePowerModer
UsePowerYagluth
UsePowerQueen
UsePowerAshlands
UsePowerDeepNorth
DeathByCatapult
DeathByCinderFire
DeathByAshlandsOcean
DeathByIncinerator
CraftFood
CraftFoodBonus
CraftGrill
CraftGrillBurnt
CraftGrillBonus
CraftWeapon
CraftArmor
CraftTrinket
CraftAmmo
CraftMaterial
CraftTool
CraftTorch
CraftBait
CraftOther
HarvestCrop
HarvestBerry
HarvestMushroom
HarvestVine
HarvestBonus
ConsecutiveDaysSurvived
ConsecutiveDaysSurvivedMax
MaxBuildingHeight
MaxBuildingHeightWorld
MaxComfort
TreasureBuriedFound
TreasureDungeonFound
TreasureLocationFound
LeviathanSink
LavaLeviathanSink
ExploreNorth
ExploreSouth
ExploreEast
ExploreWest
ExploreNorthNoMap
ExploreSouthNoMap
ExploreEastNoMap
ExploreWestNoMap
BossKillMultiplayer
BossKillSolo
VillagePointsMax
DeepestDungeon
DistanceSailHelm
PlayerSpawn
DeathByTreeTier0
DeathByTreeTier1
DeathByTreeTier2
DeathByTreeTier3
DeathByTreeTier4
DeathByTreeTier5
FishHooked
FishLost
FishCaught
FishCaughtTier0
FishCaughtTier1
FishCaughtTier2
FishCaughtTier3
FishCaughtTier4
FishCaughtTier5
FishCaughtTier6
BuiltPieces
BuiltPiecesNoDebt
BuildPiecesRemoved
BuildClusterMisc
BuildClusterCrafting
BuildClusterBuilding
BuildClusterFloor
BuildClusterWall
BuildClusterRoof
BuildClusterArchitecture
BuildClusterFurniture
BuildClusterLighting
BuildClusterDecor
BuildClusterStorage
BuildClusterTransport
BuildClusterFood
BuildClusterMeads
BuildClusterFeasts
BuildClusterDefense
BuildClusterStacks
BuildClusterStairs
BuildClusterDoors
BuildClusterSeasonal
TamedPetting
TamedCommand
TreeFir
TreeOak
TreePine
TreeAshlands
TreeYggdrasilShoot
TreeSwamp
TreeBeech
TreeBirch
TreeSnowFir
TreeSnowPine
DeathByDrawBridge
DeathByAshlandsLava
""".strip().splitlines())
STAT_INDEX = {name: index for index, name in enumerate(PLAYER_STAT_NAMES)}
assert len(PLAYER_STAT_NAMES) == 205 and STAT_INDEX['Tree'] == 28 and STAT_INDEX['DeathByTree'] == 68 and STAT_INDEX['TreeFir'] == 193

# Description et règle : (nom lisible, compteur PlayerStatType, seuil).
DEATH_CRITERIA = (
    ('Touché par un ennemi', 'DeathByEnemyHit', 1),
    ('Chute', 'DeathByFall', 1),
    ('Noyade', 'DeathByDrowning', 1),
    ('Brûlure', 'DeathByBurning', 1),
    ('Gel', 'DeathByFreezing', 1),
    ('Poison', 'DeathByPoisoned', 1),
    ('Fumée', 'DeathBySmoke', 1),
    ('Bord du monde', 'DeathByEdgeOfWorld', 1),
    ('Arbre', 'DeathByTree', 1),
    ('Tourelle', 'DeathByTurret', 1),
    ('Stalactite', 'DeathByStalagtite', 1),
    ('Catapulte', 'DeathByCatapult', 1),
    ('Océan des Ashlands', 'DeathByAshlandsOcean', 1),
    ('Incinérateur', 'DeathByIncinerator', 1),
    ('Pont-levis', 'DeathByDrawBridge', 1),
    ('Lave des Ashlands', 'DeathByAshlandsLava', 1),
)
TREE_DEATH_CRITERIA = (
    ('Sapin', 'TreeFir', 1), ('Chêne', 'TreeOak', 1),
    ('Pin', 'TreePine', 1), ('Arbre des Ashlands', 'TreeAshlands', 1),
    ('Pousse d’Yggdrasil', 'TreeYggdrasilShoot', 1),
    ('Arbre des marais', 'TreeSwamp', 1),
    ('Hêtre', 'TreeBeech', 1), ('Bouleau', 'TreeBirch', 1),
    ('Sapin enneigé', 'TreeSnowFir', 1),
    ('Pin enneigé', 'TreeSnowPine', 1),
)

@dataclass(frozen=True)
class AchievementSpec:
    key: str
    title: str
    category: str
    description: str
    criteria: tuple[tuple[str, str, int], ...]
    kind: str = 'stat'          # stat / boss / fish / miniboss
    difficulty: str = 'Any'    # Any / Default / Hard
    secret: bool = False
    origin: str = 'Jeu + Steam'
    note: str = ''


def one(key, title, category, desc, stat, goal, *, secret=False):
    return AchievementSpec(key, title, category, desc, ((desc, stat, goal),), secret=secret)

SPECS = (
    one('lumberjack', 'The Lumberjack', 'Récolte', 'Arbres abattus', 'Tree', 500),
    one('builder', 'The Builder', 'Construction', 'Pièces construites comptabilisées', 'BuiltPiecesNoDebt', 500),
    one('farmer', 'The Farmer', 'Récolte', 'Récoltes cultivées', 'HarvestCrop', 500),
    one('beekeeper', 'The Beekeeper', 'Récolte', 'Miel récolté', 'BeesHarvested', 500),
    AchievementSpec('forager', 'The Forager', 'Récolte', 'Récolter 250 baies et 250 champignons', (
        ('Baies', 'HarvestBerry', 250), ('Champignons', 'HarvestMushroom', 250),
    )),
    one('cook', 'The Cook', 'Cuisine', 'Plats préparés', 'CraftFood', 100),
    one('stomach', 'No Adventuring On an Empty Stomach', 'Cuisine', 'Aliments consommés', 'FoodEaten', 500),
    one('sailor', 'The Sailor', 'Exploration', 'Distance totale à la voile (m)', 'DistanceSail', 131946),
    one('captain', 'The Captain', 'Exploration', 'Distance à la barre (m)', 'DistanceSailHelm', 65973),
    AchievementSpec('explorer', 'The Explorer', 'Exploration', 'Atteindre les quatre extrémités cardinales', (
        ('Nord', 'ExploreNorth', 1), ('Sud', 'ExploreSouth', 1),
        ('Est', 'ExploreEast', 1), ('Ouest', 'ExploreWest', 1),
    )),
    AchievementSpec('pathfinder', 'The Pathfinder', 'Exploration', 'Atteindre les extrémités sans carte', (
        ('Nord sans carte', 'ExploreNorthNoMap', 1), ('Sud sans carte', 'ExploreSouthNoMap', 1),
        ('Est sans carte', 'ExploreEastNoMap', 1), ('Ouest sans carte', 'ExploreWestNoMap', 1),
    )),
    one('survivor', 'The Survivor', 'Survie', 'Jours consécutifs survécus (record)', 'ConsecutiveDaysSurvivedMax', 30),
    one('comfort', 'Comfort is King', 'Construction', 'Niveau de confort maximal', 'MaxComfort', 20),
    one('mighty', 'Mighty Halls', 'Construction', 'Hauteur maximale d’une construction', 'MaxBuildingHeight', 49),
    one('top', 'Top of the World', 'Construction', 'Hauteur de construction dans le monde', 'MaxBuildingHeightWorld', 432),
    one('fish4', 'A Catch Worthy of Njord', 'Exploration', 'Poisson de niveau 4 pêché', 'FishCaughtTier4', 1),
    one('solo', 'Lone Wolf', 'Combat', 'Boss vaincu seul', 'BossKillSolo', 1),
    one('coop', 'Stronger Together', 'Combat', 'Boss vaincu à plusieurs', 'BossKillMultiplayer', 1),
    one('firstdeath', 'The First of Many', 'Survie', 'Premier décès', 'Deaths', 1, secret=True),
    one('accident', 'Accidents Happen', 'Survie', 'Décès provoqué par un arbre', 'DeathByTree', 1, secret=True),
    AchievementSpec('treesall', 'That Can’t Be an Accident', 'Survie', 'Mourir à cause des dix variétés d’arbres', TREE_DEATH_CRITERIA, secret=True),
    AchievementSpec('deathall', 'Are You Alright?', 'Survie', 'Mourir des seize manières possibles', DEATH_CRITERIA),
    one('obliterated', 'Obliterated', 'Survie', 'Mort par incinérateur', 'DeathByIncinerator', 1, secret=True),
    one('legend', 'The Legends Are True', 'Survie', 'Mort au bord du monde', 'DeathByEdgeOfWorld', 1, secret=True),
    one('treasure', 'The Treasure Hunter', 'Exploration', 'Trésors enterrés découverts', 'TreasureBuriedFound', 10, secret=True),
    one('leviathan', 'No Time For Snoozing', 'Exploration', 'Léviathan réveillé', 'LeviathanSink', 1, secret=True),
    AchievementSpec('fisherman', 'The Fisherman', 'Exploration', 'Pêcher les douze espèces différentes', tuple(), kind='fish'),
    AchievementSpec('miniboss', 'Odin is Pleased', 'Combat', 'Vaincre les cinq mini-boss requis', tuple(), kind='miniboss'),
    AchievementSpec('viking', 'The Viking', 'Boss', 'Vaincre les huit boss', tuple(), kind='boss', difficulty='Any'),
    AchievementSpec('tough', 'The Tough Viking', 'Boss', 'Vaincre les huit boss en normal ou plus', tuple(), kind='boss', difficulty='Default'),
    AchievementSpec('toughest', 'The Toughest Viking', 'Boss', 'Vaincre les huit boss en difficile ou plus', tuple(), kind='boss', difficulty='Hard'),
)

# L'ordre de l'énumération est également documenté dans valheim_reader.py.
BOSS_CRITERIA = (
    ('Eikthyr', '$enemy_eikthyr', 1),
    ('L’Ancien', '$enemy_gdking', 1),
    ('Masse d’os', '$enemy_bonemass', 1),
    ('Moder', '$enemy_dragon', 1),
    ('Yagluth', '$enemy_goblinking', 1),
    ('La Reine', '$enemy_seekerqueen', 1),
    ('Fader', '$enemy_fader', 1),
    ('Kall Fimbulbringer', '$enemy_frozenking_p3', 1),
)

FISH_CRITERIA = tuple((label, f'$animal_fish{i}', 1) for i, label in enumerate((
    'Perche', 'Brochet', 'Thon', 'Tétra', 'Poisson-troll',
    'Hareng géant', 'Mérou', 'Morue corail', 'Poisson-pêcheur',
    'Saumon du Nord', 'Poisson magma', 'Poisson-globe',
), start=1))

MINIBOSS_CRITERIA = (
    ('Geirrhafa', '$enemy_fenringcultist_hildir', 1),
    ('Brenna', '$enemy_skeletonfire', 1),
    ('Lord Reto', '$enemy_charred_melee_Dyrnwyn', 1),
    ('Zil & Thungr', '$enemy_goblinbrute_hildircombined', 1),
    ('Zil', '$enemy_goblin_hildir', 1),
)


# Le catalogue visible dans le jeu comporte les 53 succès actifs de Steam.
# Deux entrées supplémentaires sont recensées dans les données internes :
# leur règle active n'a PAS été vérifiée. Elles ne sont jamais considérées
# comme obtenues sur la seule base des statistiques.
# Références :
# https://steamcommunity.com/stats/892970/achievements
# https://www.valheim.tools/achievements
# https://github.com/Melichor/ValheimSaveParser/blob/main/achi_hunter.py

_EXTRA_BOSSES = (
    ('eikthyr', 'Eikthyr', '$enemy_eikthyr'),
    ('elder', 'The Elder', '$enemy_gdking'),
    ('bonemass', 'Bonemass', '$enemy_bonemass'),
    ('moder', 'Moder', '$enemy_dragon'),
    ('yagluth', 'Yagluth', '$enemy_goblinking'),
    ('queen', 'The Seeker Queen', '$enemy_seekerqueen'),
    ('fader', 'Fader', '$enemy_fader'),
    ('kall', 'Kall Fimbulbringer', '$enemy_frozenking_p3'),
)
_BOSS_SINGLE_SPECS = tuple(AchievementSpec(
    f'boss_single_{slug}', title, 'Boss', f'Vaincre {title}',
    ((title, token, 1),), kind='boss_single', secret=True,
) for slug, title, token in _EXTRA_BOSSES)

_HOMESTEADER = (
    ('Sol', 'BuildClusterFloor', 6),
    ('Murs', 'BuildClusterWall', 8),
    ('Toit', 'BuildClusterRoof', 4),
    ('Mobilier', 'BuildClusterFurniture', 1),
    ('Éclairage', 'BuildClusterLighting', 1),
    ('Rangement', 'BuildClusterStorage', 1),
)
_ARCHITECT = (
    ('Bâtiments', 'BuildClusterBuilding', 10),
    ('Sols', 'BuildClusterFloor', 40),
    ('Murs', 'BuildClusterWall', 40),
    ('Toits', 'BuildClusterRoof', 20),
    ('Architecture', 'BuildClusterArchitecture', 10),
    ('Mobilier', 'BuildClusterFurniture', 10),
    ('Éclairage', 'BuildClusterLighting', 5),
    ('Décoration', 'BuildClusterDecor', 5),
)

# Catalogue actif incomplet dans le moteur actuel : les collections reposent
# sur des listes de prefabs versionnées. Afficher « non calculable » est plus sûr
# qu'utiliser seulement un nombre d'entrées et annoncer un faux déblocage.
_UNSUPPORTED_ACTIVE = (
    ('hunter', 'The Hunter', 'Combat', 'Vaincre chaque espèce de créature (liste exacte dépendante du jeu).'),
    ('master_hunter', 'The Master Hunter', 'Combat', 'Vaincre chaque espèce de créature en difficile ou plus.'),
    ('trophy_collector', 'The Trophy Collector', 'Collection', 'Ramasser chaque trophée de la liste officielle.'),
    ('blacksmith', 'The Blacksmith', 'Artisanat', 'Fabriquer chaque arme définie dans le jeu.'),
    ('master_chef', 'The Master Chef', 'Cuisine', 'Cuisiner chaque plat de la liste officielle.'),
    ('artisan', 'The Artisan', 'Artisanat', 'Fabriquer tous les objets requis par le jeu.'),
    ('gourmet', 'The Gourmet', 'Cuisine', 'Consommer tous les aliments requis par le jeu.'),
    ('carpenter', 'The Carpenter', 'Construction', 'Construire tous les éléments requis par le jeu.'),
    ('kings_queens', 'Kings and Queens of Valheim', 'Maîtrise',
     'Obtenir The Viking, The Hunter, The Artisan, The Master Chef, The Carpenter et The Explorer.'),
    ('child_odin', 'Child of Odin', 'Maîtrise',
     'Obtenir The Toughest Viking, The Master Hunter, The Survivor et The Pathfinder.'),
)

SPECS = SPECS + _BOSS_SINGLE_SPECS + (
    one('arrived', 'I Have Arrived!', 'Exploration', 'Apparitions dans le monde', 'PlayerSpawn', 1, secret=True),
    AchievementSpec('homesteader', 'The Homesteader', 'Construction',
        'Construire une maison. Suivi des compteurs de catégories, non confirmation du test local des pièces.',
        _HOMESTEADER, note='Le jeu peut également accepter une combinaison locale de pièces. Statut calculé indicatif.'),
    AchievementSpec('architect', 'The Architect', 'Construction',
        'Construire un village. Suivi des groupes de pièces, non confirmation du test local des pièces.',
        _ARCHITECT, note='Le jeu peut également accepter une combinaison locale de pièces. Statut calculé indicatif.'),
    AchievementSpec('chosen', 'The Chosen One', 'Artisanat', 'Fabriquer Dyrnwyn.',
        (('Dyrnwyn', '$item_sword_dyrnwyn', 1),), kind='crafted_single', secret=True),
) + tuple(AchievementSpec(key, title, category, description, tuple(), kind=('collection' if key in COLLECTIONS else 'meta'),
       difficulty=('Hard' if key == 'master_hunter' else 'Any'),
       note=('Liste complète des critères issue du catalogue des ressources Valheim 1.0.21. '
             'Progression selon le fichier .fch, pas un déblocage Steam.'
             if key in COLLECTIONS else
             'Progression indicative calculée depuis les objectifs prérequis ; aucun accès au statut Steam.'))
    for key, title, category, description in _UNSUPPORTED_ACTIVE) + (
    AchievementSpec('pugilist_internal', 'The Pugilist', 'Interne',
        'Vaincre tous les boss aux poings — entrée présente dans les ressources, déclencheur actif non confirmé.',
        tuple(), kind='internal_unverified', origin='Interne uniquement',
        note='Les éliminations classées Poings sont consultables, mais ne prouvent pas que tous les dégâts du combat ont été infligés aux poings.'),
    AchievementSpec('most_worthy_internal', 'The Most Worthy', 'Interne',
        'Obtenir tous les autres succès — entrée interne sans déblocage actif confirmé.',
        tuple(), kind='internal_unverified', origin='Interne uniquement',
        note='La sauvegarde du personnage ne contient pas la liste autoritative des succès réellement débloqués.'),
)

assert len(SPECS) == 55, f'Catalogue incomplet: {len(SPECS)} entrées'
assert len({x.key for x in SPECS}) == 55
assert sum(x.origin == 'Interne uniquement' for x in SPECS) == 2


def evaluate_one(profile, spec: AchievementSpec):
    """Évalue ce que la sauvegarde peut prouver, sans inventer de déblocages.

    Statut 'non_calculable' : aucun pourcentage n'est publié. Les deux entrées
    internes sont informatives, pas assimilées à des succès actifs.
    """
    if spec.kind in ('not_calculable', 'internal_unverified'):
        diagnostic_parts = []
        if spec.key == 'pugilist_internal':
            # Diagnostic : éliminations classées Poings par le jeu.
            # Pas de preuve de combat intégral aux poings.
            unarmed = profile['groups']['Any']['enemies'][1]
            diagnostic_parts = [{
                'label': name, 'key': token, 'current': float(unarmed.get(token, 0)),
                'goal': None, 'remaining': None, 'complete': False, 'diagnostic': 'poings',
            } for _, name, token in _EXTRA_BOSSES]
        elif spec.key == 'most_worthy_internal':
            official = [evaluate_one(profile, other) for other in SPECS
                        if other.origin == 'Jeu + Steam']
            known = sum(r['measurable'] for r in official)
            done = sum(r['complete'] for r in official)
            diagnostic_parts = [{
                'label': f'Objectifs mesurables atteints ({known} suivis sur 53)',
                'key': 'official_observed', 'current': float(done),
                'goal': None, 'remaining': None, 'complete': False, 'diagnostic': 'partial',
            }]
        return {
            'key': spec.key, 'title': spec.title, 'category': spec.category,
            'description': spec.description, 'difficulty': spec.difficulty,
            'secret': spec.secret, 'origin': spec.origin, 'note': spec.note,
            'measurable': False, 'fraction': None, 'percent': None,
            'completed_conditions': 0, 'total_conditions': 0, 'complete': False,
            'parts': diagnostic_parts,
        }
    group = profile['groups'][spec.difficulty]
    if spec.kind == 'meta':
        required = {
            'kings_queens': ('viking', 'hunter', 'artisan', 'master_chef', 'carpenter', 'explorer'),
            'child_odin': ('toughest', 'master_hunter', 'survivor', 'pathfinder'),
        }[spec.key]
        criteria = tuple((next(s.title for s in SPECS if s.key == target), target, 1)
                         for target in required)
        prereqs = {target: evaluate_one(profile, next(s for s in SPECS if s.key == target))
                   for target in required}
        get_value = lambda key: float(prereqs[key]['complete'])
    elif spec.kind == 'collection':
        criteria = tuple((prefab_label(token), token, 1) for token in COLLECTIONS[spec.key])
        field = {
            'hunter': 'enemies', 'master_hunter': 'enemies',
            'trophy_collector': 'picked_up', 'blacksmith': 'crafted',
            'master_chef': 'crafted', 'artisan': 'crafted',
            'gourmet': 'foods_eaten', 'carpenter': 'pieces_built',
        }[spec.key]
        saved = group[field][0] if field == 'enemies' else group[field]
        get_value = lambda key: saved.get(key, 0)
    elif spec.kind in ('boss', 'boss_single', 'miniboss'):
        criteria = (BOSS_CRITERIA if spec.kind == 'boss' else
                    MINIBOSS_CRITERIA if spec.kind == 'miniboss' else spec.criteria)
        saved = group['enemies'][0]
        get_value = lambda key: saved.get(key, 0)
    elif spec.kind == 'fish':
        criteria = FISH_CRITERIA
        saved = group['pickables']
        get_value = lambda key: saved.get(key, 0)
    elif spec.kind == 'crafted_single':
        criteria = spec.criteria
        saved = group['crafted']
        get_value = lambda key: saved.get(key, 0)
    else:
        criteria = spec.criteria
        stats = group['stats']
        get_value = lambda key: stats[STAT_INDEX[key]]
    parts = []
    fractions = []
    for label, key, goal in criteria:
        if isinstance(key, str) and key.startswith('$'):
            label = localized_name(key, label)
        value = max(0, float(get_value(key)))
        filled = min(goal, value)
        fractions.append(filled / goal)
        parts.append({
            'label': label, 'key': key, 'current': value, 'goal': goal,
            'remaining': max(0, goal - value), 'complete': value >= goal,
        })
    fraction = sum(fractions) / len(fractions) if fractions else 0
    complete = all(p['complete'] for p in parts) and bool(parts)
    return {
        'key': spec.key, 'title': spec.title, 'category': spec.category,
        'description': spec.description, 'difficulty': spec.difficulty,
        'secret': spec.secret, 'origin': spec.origin, 'note': spec.note,
        'measurable': True, 'fraction': fraction, 'percent': round(fraction * 100, 1),
        'completed_conditions': sum(p['complete'] for p in parts),
        'total_conditions': len(parts), 'complete': complete,
        'parts': parts,
    }


def evaluate_all(profile):
    return [evaluate_one(profile, spec) for spec in SPECS]


def progress_delta(current_result, prior_result):
    if not prior_result or not current_result['measurable'] or not prior_result['measurable']:
        return None
    old = {p['key']: p['current'] for p in prior_result['parts']}
    deltas = []
    for part in current_result['parts']:
        delta = part['current'] - old.get(part['key'], part['current'])
        if abs(delta) > 1e-5:
            deltas.append((part['label'], delta))
    return deltas
