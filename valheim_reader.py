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


# Localisation française intégrée, compatible avec les anciens updaters.
import html as _fr_html
import json as _fr_json
import re as _fr_re
from functools import lru_cache as _fr_cache
_FR_NAMES_SOURCE = '{\n  "$animal_fish": "Poisson",\n  "$animal_fish1": "Perche",\n  "$animal_fish10": "Saumon nordique",\n  "$animal_fish11": "Poisson-magma",\n  "$animal_fish12": "Poisson-globe",\n  "$animal_fish2": "Brochet",\n  "$animal_fish3": "Thon",\n  "$animal_fish4": "Tétra",\n  "$animal_fish5": "Poisson-troll",\n  "$animal_fish6": "Guinée saumon",\n  "$animal_fish7": "Mérou",\n  "$animal_fish8": "Vieille de corail",\n  "$animal_fish9": "Poisson-pêcheur",\n  "$enemy_abomination": "Abomination",\n  "$enemy_asksvin": "Asksvin",\n  "$enemy_asksvin_hatchling": "Jeune asksvin",\n  "$enemy_aspect_bonemass": "Aspect de la Mort difforme",\n  "$enemy_aspect_dragon": "Aspect de la Mère des dragons",\n  "$enemy_aspect_eikthyr": "Aspect du Cerf de l\'orage",\n  "$enemy_aspect_fader": "Aspect de la Flamme d\'émeraude",\n  "$enemy_aspect_gdking": "Aspect de la Forêt vivante",\n  "$enemy_aspect_goblinking": "Aspect de l\'Âme tourmentée",\n  "$enemy_aspect_seekerqueen": "Aspect de la Matriarche rampante",\n  "$enemy_babyseeker": "Jeune fouineur",\n  "$enemy_barka": "Barka",\n  "$enemy_bat": "Chauve souris",\n  "$enemy_bigblob": "Pâte hexaèdre",\n  "$enemy_bjorn": "Ours",\n  "$enemy_blob": "Blob",\n  "$enemy_blobelite": "Oozer",\n  "$enemy_blobfrost": "Blob de givre",\n  "$enemy_bloblava": "Blob de lave",\n  "$enemy_blobmork": "Pâte sans forme",\n  "$enemy_blobmorkmini": "Petite pâte",\n  "$enemy_blobtar": "Excroissance",\n  "$enemy_boar": "Sanglier",\n  "$enemy_boarpiggy": "Marcassin",\n  "$enemy_bonemass": "Masse-d\'Os",\n  "$enemy_bonemawserpent": "Gueule-d\'os",\n  "$enemy_boss_bonemass_spawnmessage": "Massd\'Os se déplace.",\n  "$enemy_boss_dragon_spawnmessage": "Moder est enragée.",\n  "$enemy_boss_goblinking_spawnmessage": "L\'âme corrompue de Yagluths a été invoquée.",\n  "$enemy_charred": "Calciné",\n  "$enemy_charred_archer": "Archer calciné",\n  "$enemy_charred_grunt": "Cogneur calciné",\n  "$enemy_charred_mage": "Sorcier calciné",\n  "$enemy_charred_melee": "Guerrier calciné",\n  "$enemy_charred_melee_Dyrnwyn": "Seigneur Reto",\n  "$enemy_charred_melee_Fader": "Guerrier calciné invoqué",\n  "$enemy_charred_twitcher": "Forcené calciné",\n  "$enemy_charred_twitcher_summoned": "Forcené invoqué",\n  "$enemy_charredspawnercross": "Effigie malveillante",\n  "$enemy_charredtwitcherspawner": "Monument du tourment",\n  "$enemy_chicken": "Poulet",\n  "$enemy_deathsquito": "Morstique",\n  "$enemy_deer": "Cerf",\n  "$enemy_dragon": "Moder",\n  "$enemy_drake": "Drac",\n  "$enemy_draugr": "Draugr",\n  "$enemy_draugrelite": "Élite draugr",\n  "$enemy_draugrspawner": "Charnier méphitique",\n  "$enemy_dvergr": "Brigand dvergr",\n  "$enemy_dvergr_deepnorth": "Dvergr emprisonné",\n  "$enemy_dvergr_mage": "Mage dvergr",\n  "$enemy_dvergrs": "Dvergr",\n  "$enemy_eikthyr": "Eikthyr",\n  "$enemy_elaking": "Elaking",\n  "$enemy_elakingmole": "Sans yeux",\n  "$enemy_fader": "Fader",\n  "$enemy_fader_codename": "La Flamme d\'émeraude",\n  "$enemy_fallenvalkyrie": "Valkyrie déchue",\n  "$enemy_fallenwarrior": "Guerrier déchu",\n  "$enemy_fenring": "Fenring",\n  "$enemy_fenringcultist": "Cultiste",\n  "$enemy_fenringcultist_hildir": "<color=orange>Geirrhafa</color>",\n  "$enemy_frozenking": "Kall Mandefimbul",\n  "$enemy_frozenking_p3": "Kall Mandefimbul",\n  "$enemy_frysling": "Frysling",\n  "$enemy_gdking": "L\'Aîné",\n  "$enemy_gemgoblin": "Vilain gobelin",\n  "$enemy_ghost": "Fantôme",\n  "$enemy_ghost_void": "Le Vide",\n  "$enemy_gjall": "Gjall",\n  "$enemy_goblin": "Gobelin",\n  "$enemy_goblin_deepnorth": "Gobelin captif",\n  "$enemy_goblin_hildir": "<color=orange>Zil</color>",\n  "$enemy_goblinbrute": "Berserker gobelin",\n  "$enemy_goblinbrute_hildir": "<color=orange>Thungr</color>",\n  "$enemy_goblinbrute_hildircombined": "<color=orange>Zil et Thungr</color>",\n  "$enemy_goblinking": "Yagluth",\n  "$enemy_goblinshaman": "Chaman gobelin",\n  "$enemy_greydwarf": "Naingris",\n  "$enemy_greydwarfbrute": "Brute naingris",\n  "$enemy_greydwarfshaman": "Chaman naingris",\n  "$enemy_greydwarfspawner": "Nid de naingris",\n  "$enemy_greyling": "Bourgeon naingris",\n  "$enemy_hare": "Lièvre",\n  "$enemy_hen": "Cocotte",\n  "$enemy_holespawner": "Armoire maléfique",\n  "$enemy_jotun_warrior": "Krigen",\n  "$enemy_jotun_witch": "Hexen",\n  "$enemy_kvastur": "Kvastur",\n  "$enemy_leech": "Sangsue",\n  "$enemy_lox": "Lox",\n  "$enemy_loxcalf": "Petit de Lox",\n  "$enemy_mistile": "Brumectile",\n  "$enemy_moose": "Élan",\n  "$enemy_moosecalf": "Faon d\'élan",\n  "$enemy_morgen": "Morgen",\n  "$enemy_neck": "Nixe",\n  "$enemy_seal": "Phoque",\n  "$enemy_seal_baby": "Blanchon",\n  "$enemy_seeker": "Fouineur",\n  "$enemy_seekerbrute": "Soldat fouineur",\n  "$enemy_seekerqueen": "La Reine",\n  "$enemy_serpent": "Serpent de mer",\n  "$enemy_shadowperson": "Ombre",\n  "$enemy_skeleton": "Squelette",\n  "$enemy_skeleton_summoned": "Skelett",\n  "$enemy_skeletonfire": "<color=orange>Brenna</color>",\n  "$enemy_skeletonpoison": "Cadavre rance",\n  "$enemy_skeletonspawner": "Péril d\'os",\n  "$enemy_stonegolem": "Golem de pierre",\n  "$enemy_summonedroot": "Racine invoquée",\n  "$enemy_summonedtroll": "Troll invoqué",\n  "$enemy_surtling": "Surtling",\n  "$enemy_tick": "Tique",\n  "$enemy_troll": "Troll",\n  "$enemy_trollfrost": "Gammeltroll",\n  "$enemy_ulv": "Warg",\n  "$enemy_unbjorn": "Ours maudit",\n  "$enemy_volture": "Voltour",\n  "$enemy_wolf": "Loup",\n  "$enemy_wolfcub": "Louveteau",\n  "$enemy_wraith": "Spectre",\n  "$item_amber": "Ambre",\n  "$item_amberpearl": "Perle d’ambre",\n  "$item_ancientcoin": "Pièce ancienne",\n  "$item_ancientgemstone_black": "Draumyx",\n  "$item_ancientgemstone_green": "Grimvarn",\n  "$item_ancientgemstone_orange": "Solryth",\n  "$item_ancientgemstone_purple": "Veydris",\n  "$item_ancientroot": "Racine ancienne",\n  "$item_ancientroot_empty": "La racine ancienne semble asséchée.",\n  "$item_ancientroot_full": "La racine ancienne vibre d\'énergie.",\n  "$item_ancientroot_half": "La lueur de la racine ancienne s\'amenuise.",\n  "$item_ancientseed": "Graine ancienne",\n  "$item_armor": "Armure",\n  "$item_arrow_bloodgold": "Flèche d\'or-sang",\n  "$item_arrow_bronze": "Flèche en bronze",\n  "$item_arrow_carapace": "Flèche en carapace",\n  "$item_arrow_charred": "Flèche calcinée",\n  "$item_arrow_fire": "Flêche enflammée",\n  "$item_arrow_flint": "Flèche en silex",\n  "$item_arrow_frost": "Flèche de givre",\n  "$item_arrow_iron": "Flèche en fer",\n  "$item_arrow_needle": "Flèche aiguille",\n  "$item_arrow_obsidian": "Flèche d\'obsidienne",\n  "$item_arrow_poison": "Flèche empoisonnée",\n  "$item_arrow_silver": "Flèche d’argent",\n  "$item_arrow_wood": "Flèche en bois",\n  "$item_askbladder": "Vessie d\'asksvin",\n  "$item_askhide": "Peau d\'asksvin",\n  "$item_asksvin_egg": "Œuf d\'asksvin",\n  "$item_asksvin_meat": "Queue d\'asksvin",\n  "$item_asksvin_meat_cooked": "Queue d\'asksvin cuite",\n  "$item_asksvincarrionneck": "Cou d\'asksvin",\n  "$item_asksvincarrionpelvic": "Pelvis d\'asksvin",\n  "$item_asksvincarrionribcage": "Cage thoracique d\'asksvin",\n  "$item_asksvincarrionskull": "Crâne d\'asksvin",\n  "$item_atgeir_blackmetal": "Atgeir en sombracier",\n  "$item_atgeir_bronze": "Atgeir en bronze",\n  "$item_atgeir_gold": "Atgeir nordique",\n  "$item_atgeir_gold_bloodlightning": "Atgeir de sang-tonnerre",\n  "$item_atgeir_gold_bloodlightning_uncooked": "Moulage : atgeir de sang-tonnerre",\n  "$item_atgeir_gold_frostfire": "Atgeir de givrefeu",\n  "$item_atgeir_gold_frostfire_uncooked": "Moulage : atgeir de givrefeu",\n  "$item_atgeir_gold_uncooked": "Moulage : atgeir nordique",\n  "$item_atgeir_himminafl": "Himmin afl",\n  "$item_atgeir_iron": "Atgeir en fer",\n  "$item_atgeir_wood": "Atgeir en bois",\n  "$item_axe_berzerkr": "Haches des berserkir",\n  "$item_axe_berzerkr_blood": "Haches des berserkir d\'hémorragie",\n  "$item_axe_berzerkr_lightning": "Haches des berserkir du tonnerre",\n  "$item_axe_berzerkr_nature": "Haches des berserkir primitives",\n  "$item_axe_blackmetal": "Hache en sombracier",\n  "$item_axe_bronze": "Hache en bronze",\n  "$item_axe_early": "Haches primitives",\n  "$item_axe_flint": "Hache en silex",\n  "$item_axe_gold": "Hache nordique",\n  "$item_axe_gold_bloodlightning": "Hache de sang-tonnerre",\n  "$item_axe_gold_bloodlightning_uncooked": "Moulage : hache de sang-tonnerre",\n  "$item_axe_gold_frostfire": "Hache de givrefeu",\n  "$item_axe_gold_frostfire_uncooked": "Moulage : hache de givrefeu",\n  "$item_axe_gold_uncooked": "Moulage : hache nordique",\n  "$item_axe_iron": "Hache en fer",\n  "$item_axe_jotunbane": "Fléau des jötnars",\n  "$item_axe_rusty": "Hache en fer rouillée INUTILISÉ",\n  "$item_axe_stone": "Hache en pierre",\n  "$item_axe_wood": "Hache en bois",\n  "$item_axe2h_gold": "Bardiche nordique",\n  "$item_axe2h_gold_bloodlightning": "Bardiche de sang-tonnerre",\n  "$item_axe2h_gold_bloodlightning_uncooked": "Moulage : bardiche de sang-tonnerre",\n  "$item_axe2h_gold_frostfire": "Bardiche de givrefeu",\n  "$item_axe2h_gold_frostfire_uncooked": "Moulage : bardiche de givrefeu",\n  "$item_axe2h_gold_uncooked": "Moulage : bardiche nordique",\n  "$item_axehead1": "Tête de hache curieuse",\n  "$item_axehead2": "Tête de hache mystérieuse",\n  "$item_backstab": "Attaque sournoise",\n  "$item_bakedpoteitr": "Poteitr au four",\n  "$item_bakedpoteitr_uncooked": "Poteitr crue",\n  "$item_barberkit": "Nécessaire de barbier",\n  "$item_barkabranch": "Branche gelée",\n  "$item_barley": "Orge",\n  "$item_barleyflour": "Farine d\'orge",\n  "$item_barleywine": "Vin d\'orge de résistance au feu",\n  "$item_barleywinebase": "Base de vin d\'orge : résistance au feu",\n  "$item_barrelrings": "Cercles de tonneau",\n  "$item_battleaxe": "Hache de combat",\n  "$item_battleaxe_blackmetal": "Hache de combat en sombracier",\n  "$item_battleaxe_crystal": "Hache de combat en cristal",\n  "$item_battleaxe_gold_uncooked": "Moulage : bardiche nordique",\n  "$item_battleaxe_skullsplittur": "Fend-les-crânes",\n  "$item_battleaxe_wood": "Hache de combat en bois",\n  "$item_beechseeds": "Graine de hêtre",\n  "$item_bell": "Cloche",\n  "$item_bellfragment": "Fragment de cloche",\n  "$item_beltstrength": "Megingjord",\n  "$item_bilebag": "Sac de bile",\n  "$item_bilebomb": "Bombe de bile",\n  "$item_birchseeds": "Graines de bouleau",\n  "$item_bjorn_meat": "Viande d\'ours",\n  "$item_bjorn_meat_cooked": "Viande d\'ours cuite",\n  "$item_bjornhide": "Peau d\'ours",\n  "$item_bjornpaw": "Patte d\'ours",\n  "$item_blackcore": "Noyau noir",\n  "$item_blackmarble": "Marbre noir",\n  "$item_blackmetal": "Sombracier",\n  "$item_blackmetalscrap": "Morceau de sombracier",\n  "$item_blacksoup": "Soupe noire",\n  "$item_blackwood": "Cendrebois",\n  "$item_blobvial": "Fiole à bouchon",\n  "$item_blockarmor": "Valeur défensive",\n  "$item_blockforce": "Force de blocage",\n  "$item_blockpower": "Valeur défensive",\n  "$item_bloodbag": "Poche de sang",\n  "$item_bloodclot": "Caillot de sang",\n  "$item_bloodgoldkey": "Clé délicate",\n  "$item_bloodpudding": "Boudin",\n  "$item_blubber": "Lard de phoque",\n  "$item_blubber_cooked": "Lard de phoque cuit",\n  "$item_blueberries": "Myrtilles",\n  "$item_boar_meat": "Viande de sanglier",\n  "$item_boar_meat_cooked": "Viande de sanglier cuite",\n  "$item_boarjerky": "Viande séchée de sanglier",\n  "$item_bolt_blackmetal": "Carreau en sombracier",\n  "$item_bolt_bloodgold": "Carreau d\'or-sang",\n  "$item_bolt_bone": "Carreau en os",\n  "$item_bolt_carapace": "Carreau en carapace",\n  "$item_bolt_charred": "Carreau calciné",\n  "$item_bolt_iron": "Carreau en fer",\n  "$item_bomb_dynamite": "Charge de braise",\n  "$item_bombblob_frost": "Bombe de blob : givre",\n  "$item_bombblob_lava": "Bombe de blob : lave",\n  "$item_bombblob_morkhalla": "Bombe de blob : blob",\n  "$item_bombblob_poison": "Bombe de blob : poison",\n  "$item_bombblob_poisonelite": "Bombe de blob : poison avancé",\n  "$item_bombblob_tar": "Bombe de blob : goudron",\n  "$item_bonefragments": "Fragments d\'os",\n  "$item_bonemawmeat": "Viande de gueule-d\'os",\n  "$item_bonemawmeat_cooked": "Viande de gueule-d\'os cuite",\n  "$item_bonemawscale": "Écaille de gueule-d\'os",\n  "$item_bonemawtooth": "Croc de gueule-d\'os",\n  "$item_bow": "Arc",\n  "$item_bow_ashlands": "Croc des cendres",\n  "$item_bow_ashlandsblood": "Croc sanglant",\n  "$item_bow_ashlandsroot": "Croc sauvage",\n  "$item_bow_ashlandsstorm": "Croc des tempêtes",\n  "$item_bow_draugrfang": "Croc de draugr",\n  "$item_bow_finewood": "Arc de bois noble",\n  "$item_bow_gold": "Arc nordique",\n  "$item_bow_gold_bloodlightning": "Arc de sang-tonnerre",\n  "$item_bow_gold_bloodlightning_uncooked": "Moulage : arc de sang-tonnerre",\n  "$item_bow_gold_frostfire": "Arc de givrefeu",\n  "$item_bow_gold_frostfire_uncooked": "Moulage : arc de givrefeu",\n  "$item_bow_gold_uncooked": "Moulage : arc nordique",\n  "$item_bow_huntsman": "Arc de chasse",\n  "$item_bow_snipesnap": "Échine brisée",\n  "$item_bread": "Pain",\n  "$item_breaddough": "Pâte à pain",\n  "$item_bronze": "Bronze",\n  "$item_bronzenails": "Clous en bronze",\n  "$item_bronzescrap": "Morceau de bronze",\n  "$item_bug_meat": "Viande de fouineur",\n  "$item_bug_meat_cooked": "Viande de fouineur cuite",\n  "$item_candlewick": "Mèche de bougie",\n  "$item_cape_ash": "Cape des cendres",\n  "$item_cape_asksvin": "Manteau en asksvin",\n  "$item_cape_deepnorth": "Cape en peau d\'élan",\n  "$item_cape_deepnorth_mage": "Cape de l\'orateur",\n  "$item_cape_deerhide": "Cape en peau de cerf",\n  "$item_cape_feather": "Cape de plumes",\n  "$item_cape_linen": "Cape en tissu",\n  "$item_cape_lox": "Cape de Lox",\n  "$item_cape_odin": "Cape d\'Odin",\n  "$item_cape_trollhide": "Cape en peau de troll",\n  "$item_cape_wolf": "Cape en fourrure de loup",\n  "$item_carapace": "Carapace",\n  "$item_carrot": "Carotte",\n  "$item_carrotseeds": "Graines de carotte",\n  "$item_carrotsoup": "Soupe de carottes",\n  "$item_catapult_ammo": "Projectile explosif",\n  "$item_catapult_bloodgold_ammo": "Charge d\'or-sang",\n  "$item_catapult_training_ammo": "Projectile en grise-pierre",\n  "$item_celestialfeather": "Plume céleste",\n  "$item_ceramicplate": "Plaque en céramique",\n  "$item_chain": "Chaîne",\n  "$item_chancetoapplyse": "Chances d\'appliquer l\'effet :",\n  "$item_charcoalresin": "Résine de charbon",\n  "$item_charredbone": "Os calciné",\n  "$item_charredcogwheel": "Roue dentée calcinée",\n  "$item_charredskull": "Crâne calciné",\n  "$item_chest_berserker": "Marque de l\'ours",\n  "$item_chest_berserker_undead": "Torse d\'ours maudit",\n  "$item_chest_bronze": "Cuirasse en plaques de bronze",\n  "$item_chest_carapace": "Plastron en carapace",\n  "$item_chest_dress1": "Robe marron simple",\n  "$item_chest_dress10": "Robe neutre simple",\n  "$item_chest_dress2": "Robe marron avec châle",\n  "$item_chest_dress3": "Robe marron avec perles",\n  "$item_chest_dress4": "Robe bleue simple",\n  "$item_chest_dress5": "Robe bleue avec châle",\n  "$item_chest_dress6": "Robe bleue avec perles",\n  "$item_chest_dress7": "Robe jaune simple",\n  "$item_chest_dress8": "Robe jaune avec châle",\n  "$item_chest_dress9": "Robe jaune avec perles",\n  "$item_chest_fenris": "Manteau de Fenris",\n  "$item_chest_flametal": "Plastron en flametal",\n  "$item_chest_harvester1": "Tunique des moissons",\n  "$item_chest_harvester2": "Robe des moissons",\n  "$item_chest_heavy_deepnorth": "Plastron du courage",\n  "$item_chest_heavy_gold_uncooked": "Moulage : plastron du courage",\n  "$item_chest_hildir1": "Coffre en cuivre d\'Hildir",\n  "$item_chest_hildir2": "Coffre en argent d\'Hildir",\n  "$item_chest_hildir3": "Coffre en bronze d\'Hildir",\n  "$item_chest_iron": "Armure d\'écailles de fer",\n  "$item_chest_leather": "Tunique en cuir",\n  "$item_chest_lox": "Veste en fourrure de lox",\n  "$item_chest_mage": "Robe d\'Eitr tissé",\n  "$item_chest_mage_ashlands": "Robe d\'Embla",\n  "$item_chest_mage_deepnorth": "Robe de l\'orateur",\n  "$item_chest_mage_gold_uncooked": "Moulage : robe de l\'orateur",\n  "$item_chest_medium_ashlands": "Plastron d\'Ask",\n  "$item_chest_medium_deepnorth": "Plastron de cuir de l\'Avant-garde",\n  "$item_chest_medium_gold_uncooked": "Moulage : plastron de cuir de l\'Avant-garde",\n  "$item_chest_pcuirass": "Cuirasse rembourrée",\n  "$item_chest_rags": "Tunique en haillons",\n  "$item_chest_root": "Cuirasse de racines",\n  "$item_chest_trollleather": "Tunique en cuir de troll",\n  "$item_chest_tunic1": "Tunique bleue simple",\n  "$item_chest_tunic10": "Tunique neutre simple",\n  "$item_chest_tunic2": "Tunique bleue avec cape",\n  "$item_chest_tunic3": "Tunique bleue avec perles",\n  "$item_chest_tunic4": "Tunique rouge simple",\n  "$item_chest_tunic5": "Tunique rouge avec cape",\n  "$item_chest_tunic6": "Tunique rouge avec perles",\n  "$item_chest_tunic7": "Tunique jaune simple",\n  "$item_chest_tunic8": "Tunique jaune avec cape",\n  "$item_chest_tunic9": "Tunique jaune avec perles",\n  "$item_chest_wolf": "Plastron de loup",\n  "$item_chicken_egg": "Œuf",\n  "$item_chicken_egg_cold": "(Trop froid)",\n  "$item_chicken_egg_stacked": "(N\'éclot pas en pile.)",\n  "$item_chicken_egg_warm": "(Au chaud)",\n  "$item_chicken_meat": "Viande de poulet",\n  "$item_chicken_meat_cooked": "Viande de poulet cuite",\n  "$item_chitin": "Chitine",\n  "$item_cloudberries": "Plaquebières",\n  "$item_club": "Bâton",\n  "$item_coal": "Charbon",\n  "$item_coin": "Pièce",\n  "$item_coins": "Piastres",\n  "$item_copper": "Cuivre",\n  "$item_copperore": "Minerai de cuivre",\n  "$item_copperscrap": "Morceau de cuivre",\n  "$item_crafter": "Fabriqué par",\n  "$item_crossbow_arbalest": "Arbalète",\n  "$item_crossbow_bloodlightning_gold": "Arbalète de sang-tonnerre",\n  "$item_crossbow_bloodlightning_gold_uncooked": "Moulage : arbalète de sang-tonnerre",\n  "$item_crossbow_frostfire_gold": "Arbalète de givrefeu",\n  "$item_crossbow_frostfire_gold_uncooked": "Moulage : arbalète de givrefeu",\n  "$item_crossbow_gold": "Arbalète nordique",\n  "$item_crossbow_gold_uncooked": "Moulage : arbalète nordique",\n  "$item_crossbow_ripper": "Éventreuse",\n  "$item_crossbow_ripper_blood": "Éventreuse sanglante",\n  "$item_crossbow_ripper_lightning": "Éventreuse des tempêtes",\n  "$item_crossbow_ripper_nature": "Éventreuse sauvage",\n  "$item_crownjewel": "Joyau de la couronne",\n  "$item_cryptkey": "Clé des cryptes",\n  "$item_crystal": "Cristal",\n  "$item_cultivator": "Cultivateur",\n  "$item_curedsquirrelhamstring": "Tendon d\'écureuil séché",\n  "$item_current": "Actuellement",\n  "$item_damagemultiplierhp": "Dégâts augmentés selon la santé manquante",\n  "$item_damagemultipliertotal": "Augmentation des dégâts en fonction de la santé totale manquante",\n  "$item_dandelion": "Pissenlit",\n  "$item_deer_meat": "Viande de cerf",\n  "$item_deer_meat_cooked": "Viande de cerf cuite",\n  "$item_deerhide": "Peau de cerf",\n  "$item_deerstew": "Ragoût de cerf",\n  "$item_deflection": "Force de parade",\n  "$item_deflection_OLD": "Déviation",\n  "$item_demister": "Lumière de feu-follet",\n  "$item_destructible_gucksack": "Sac visqueux",\n  "$item_destructible_unstablelavarock": "Rocher de lave instable",\n  "$item_dlc": "Objet de DLC",\n  "$item_dragonegg": "Œuf de dragon",\n  "$item_dragontear": "Larme de dragon",\n  "$item_drink": "Boisson",\n  "$item_durability": "Durabilité",\n  "$item_dvergrkey": "Brise-sceau",\n  "$item_dvergrkeyfragment": "Fragment de brise-sceau",\n  "$item_dvergrneedle": "Extracteur dvergr",\n  "$item_dvergrtankard": "Chope dvergr",\n  "$item_Dyrnwyn_blade": "Fragment de lame de Dyrnwyn",\n  "$item_Dyrnwyn_hilt": "Fragment de garde de Dyrnwyn",\n  "$item_Dyrnwyn_tip": "Fragment de pointe de Dyrnwyn",\n  "$item_eat": "Manger",\n  "$item_ectoplasm": "Ectoplasme",\n  "$item_egg_cooked": "Œuf cuit",\n  "$item_eitr": "Eitr raffiné",\n  "$item_eitrhitreturn": "Rappel de l\'Eitr",\n  "$item_eitrregen_modifier": "Régénération de l\'Eitr",\n  "$item_eitruse": "Perte d\'Eitr",\n  "$item_elakinghairbundle": "Poignée de poils d\'elaking",\n  "$item_elderbark": "Écorce ancienne",\n  "$item_entrails": "Entrailles",\n  "$item_eyescream": "Sorbœil",\n  "$item_fader_drop": "Relique de Fader",\n  "$item_faderember": "Braises",\n  "$item_falldamage": "Dégâts de chute",\n  "$item_feastashlands": "Bol gourmand des Terres de cendres",\n  "$item_feastblackforest": "Plateau de la Forêt noire",\n  "$item_feastdeepnorth": "Petit-déjeuner nordique",\n  "$item_feaster": "Plateau de service",\n  "$item_feastmeadows": "Sanglier des champs rôti",\n  "$item_feastmistlands": "Folie de champignons des Terres brumeuses",\n  "$item_feastmountains": "Copieux ragoût de bûcheron des montagnes",\n  "$item_feastoceans": "Butin du marin",\n  "$item_feastplains": "Ensemble de tartes des plaines",\n  "$item_feastswamps": "Délice du marais",\n  "$item_feathers": "Plumes",\n  "$item_fiddleheadfern": "Torse-tête",\n  "$item_fierysvinstew": "Ragoût de svin ardent",\n  "$item_finewood": "Bois précieux",\n  "$item_fircone": "Pomme de sapin",\n  "$item_fircone_big": "Pomme de sapin nordique",\n  "$item_fireworkrocket_blue": "Feu d\'artifice bleu",\n  "$item_fireworkrocket_cyan": "Feu d\'artifice cyan",\n  "$item_fireworkrocket_green": "Feu d\'artifice vert",\n  "$item_fireworkrocket_purple": "Feu d\'artifice violet",\n  "$item_fireworkrocket_red": "Feu d\'artifice rouge",\n  "$item_fireworkrocket_white": "Feu d\'artifice simple",\n  "$item_fireworkrocket_yellow": "Feu d\'artifice jaune",\n  "$item_fish_cooked": "Poisson fumé",\n  "$item_fish_raw": "Poisson cru",\n  "$item_fishandbread": "Poisson et pain",\n  "$item_fishandbreaduncooked": "Poisson cru et pain",\n  "$item_fishingbait": "Appât de pêche",\n  "$item_fishingbait_ashlands": "Appât de pêche chaud",\n  "$item_fishingbait_cave": "Appât de pêche froid",\n  "$item_fishingbait_deepnorth": "Appât de pêche gelé",\n  "$item_fishingbait_forest": "Appât de pêche moussu",\n  "$item_fishingbait_mistlands": "Appât de pêche brumeux",\n  "$item_fishingbait_ocean": "Appât de pêche lourd",\n  "$item_fishingbait_plains": "Appât de pêche piquant",\n  "$item_fishingbait_swamp": "Appât de pêche odorant",\n  "$item_fishingrod": "Canne à pêche",\n  "$item_fishsoup": "Soupe de poisson",\n  "$item_fishwraps": "Friands au poisson",\n  "$item_fistweapon_bjorn": "Pattes de l\'ours",\n  "$item_fistweapon_bjorn_undead": "Griffes d\'ours maudit",\n  "$item_fistweapon_fenris": "Arracheurs de chair",\n  "$item_fistweapon_frostfire_gold": "Chaînes de poing de givrefeu",\n  "$item_fistweapon_frostfire_gold_uncooked": "Moulage : chaînes de poing de givrefeu",\n  "$item_fistweapon_gold": "Chaînes de poing nordiques",\n  "$item_fistweapon_gold_bloodlightning": "Chaînes de poing de sang-tonnerre",\n  "$item_fistweapon_gold_bloodlightning_uncooked": "Moulage : chaînes de poing de sang-tonnerre",\n  "$item_fistweapon_gold_uncooked": "Moulage : chaînes de poing nordiques",\n  "$item_flametal": "Flametal",\n  "$item_flametal_old": "Ancien métal",\n  "$item_flametalore": "Minerai de Flamétal",\n  "$item_flametalore_old": "Minerai de métal brillant",\n  "$item_flax": "Lin",\n  "$item_flint": "Silex",\n  "$item_food": "Nourriture",\n  "$item_food_duration": "Durée",\n  "$item_food_eitr": "Eitr",\n  "$item_food_health": "Vie",\n  "$item_food_regen": "Régénération",\n  "$item_food_stamina": "Endurance",\n  "$item_fragrantbundle": "Botte parfumée",\n  "$item_freezegland": "Glande gelée",\n  "$item_freshseaweed": "Algues fraîches",\n  "$item_frostcore": "Cœur de givre",\n  "$item_frostorbs_uncooked": "Moulage : Vengeance nordique",\n  "$item_frostwood": "Sapin nordique",\n  "$item_frozenfuel": "Givre liquide",\n  "$item_frozenking_drop": "Sang sacrificiel",\n  "$item_fryslingcore": "Cœur de frysling",\n  "$item_fulladrenaline": "Effet de l\'adrénaline",\n  "$item_gemstone_blue": "Iolite",\n  "$item_gemstone_green": "Jade",\n  "$item_gemstone_red": "Pierre-de-sang",\n  "$item_glowworm": "Larve lumineuse",\n  "$item_goblintotem": "Totem gobelin",\n  "$item_gold": "Or-sang",\n  "$item_goldore": "Tissu pétrifié",\n  "$item_graplinghook": "Grappin",\n  "$item_grausten": "Grise-pierre",\n  "$item_greydwarfeye": "Œil de naingris",\n  "$item_guck": "Viscosité",\n  "$item_hammer": "Marteau",\n  "$item_hardantler": "Bois dur",\n  "$item_hardrock": "Pierre mystérieuse",\n  "$item_hardrock_knowledge1": "Ne craignez pas la mort, car votre destin est déjà tracé. Nul ne peut y échapper.",\n  "$item_hardrock_knowledge10": "Vous pouvez garder le silence si vous le souhaitez, mais quelqu\'un finira par vous trouver.",\n  "$item_hardrock_knowledge11": "Qu\'importe les souffrances que vous avez subies, vous ne voudrez jamais vous séparer de ces souvenirs.",\n  "$item_hardrock_knowledge12": "Lorsque vous quitterez la tempête, vous ne serez plus la même personne. Voilà tout l\'intérêt de la tempête.",\n  "$item_hardrock_knowledge13": "Une pierre ne souffre jamais, et une île ne pleure jamais.",\n  "$item_hardrock_knowledge2": "Mieux vaut tomber au combat que de vivre sans espoir.",\n  "$item_hardrock_knowledge3": "Nombreuses seront les runes que vous trouverez et lirez. Leur poids est imposant et leur magie redoutable.",\n  "$item_hardrock_knowledge4": "L\'homme ne peut découvrir de nouveaux océans que s\'il a le courage d\'abandonner le rivage.",\n  "$item_hardrock_knowledge5": "Si l\'on sait pourquoi vivre, peu importe le comment.",\n  "$item_hardrock_knowledge6": "C\'est par vos blessures qu\'entre la lumière.",\n  "$item_hardrock_knowledge7": "L\'imagination nous fait plus souffrir que la réalité.",\n  "$item_hardrock_knowledge8": "La douleur est inévitable. La souffrance est facultative.",\n  "$item_hardrock_knowledge9": "Ce que vous recherchez n\'apparaîtra pas sous la forme attendue.",\n  "$item_hare_meat": "Viande de lièvre",\n  "$item_hare_meat_cooked": "Viande de lièvre cuite",\n  "$item_hatefulblood": "Sang malicieux",\n  "$item_healthhitreturn": "Vie rendue par coup",\n  "$item_healthuse": "Perte de vie",\n  "$item_heat_modifier": "Résistance à la chaleur",\n  "$item_helmet_berserker": "Coiffe de l\'ours",\n  "$item_helmet_berserker_undead": "Visage d\'ours maudit",\n  "$item_helmet_bronze": "Casque en bronze",\n  "$item_helmet_bronzehorned": "Casque à cornes en bronze",\n  "$item_helmet_carapace": "Casque en carapace",\n  "$item_helmet_celebration": "Bonnet festif",\n  "$item_helmet_crown_of_valheim": "Couronne de Valheim",\n  "$item_helmet_drake": "Casque de drac",\n  "$item_helmet_dverger": "Diadème de dverger",\n  "$item_helmet_fenris": "Capuche de Fenris",\n  "$item_helmet_fishinghat": "Chapeau de pêcheur",\n  "$item_helmet_flametal": "Casque en flamétal",\n  "$item_helmet_hat1": "Foulard noué bleu",\n  "$item_helmet_hat10": "Bonnet violet simple",\n  "$item_helmet_hat2": "Foulard torsadé vert",\n  "$item_helmet_hat3": "Bonnet en fourrure marron",\n  "$item_helmet_hat4": "Bonnet vert extravagant",\n  "$item_helmet_hat5": "Bonnet rouge simple",\n  "$item_helmet_hat6": "Foulard noué jaune",\n  "$item_helmet_hat7": "Foulard torsadé rouge",\n  "$item_helmet_hat8": "Bonnet en fourrure gris",\n  "$item_helmet_hat9": "Bonnet orange extravagant",\n  "$item_helmet_heavy_deepnorth": "Casque du courage",\n  "$item_helmet_heavy_gold_uncooked": "Moulage : casque du courage",\n  "$item_helmet_iron": "Casque en fer",\n  "$item_helmet_leather": "Casque en cuir",\n  "$item_helmet_lox": "Capuche en fourrure de lox",\n  "$item_helmet_mage": "Capuchon d\'Eitr tissé",\n  "$item_helmet_mage_ashlands": "Capuche d\'Embla",\n  "$item_helmet_mage_deepnorth": "Coiffe de l\'orateur",\n  "$item_helmet_mage_gold_uncooked": "Moulage : coiffe de l\'orateur",\n  "$item_helmet_medium_ashlands": "Capuche d\'Ask",\n  "$item_helmet_medium_deepnorth": "Capuche de l\'Avant-garde",\n  "$item_helmet_medium_gold_uncooked": "Moulage : capuche de l\'Avant-garde",\n  "$item_helmet_midsummercrown": "Couronne de la mi-été",\n  "$item_helmet_odin": "Cagoule d\'Odin",\n  "$item_helmet_padded": "Casque rembourré",\n  "$item_helmet_root": "Casque de racine",\n  "$item_helmet_rootcrown": "Couronne de racines",\n  "$item_helmet_strawhat": "Chapeau de paille",\n  "$item_helmet_sweatband": "Bandeau",\n  "$item_helmet_trollleather": "Casque en cuir de troll",\n  "$item_helmet_witchhat": "Chapeau pointu",\n  "$item_helmet_yule": "Chapeau de Noël",\n  "$item_hide": "Peau",\n  "$item_hildir_divan": "Divan",\n  "$item_hildirkey1": "Clé en cuivre d\'Hildir",\n  "$item_hildirkey2": "Clé en argent d\'Hildir",\n  "$item_hildirkey3": "Clé en bronze d\'Hildir",\n  "$item_hoe": "Houe",\n  "$item_honey": "Miel",\n  "$item_honeyglazedchicken": "Poulet nappé de miel",\n  "$item_honeyglazedchickenuncooked": "Poulet cru nappé de miel",\n  "$item_hook": "Crochet",\n  "$item_ice": "Glace",\n  "$item_iron": "Fer",\n  "$item_ironnails": "Clous en fer",\n  "$item_ironore": "Minerai de fer",\n  "$item_ironpit": "Brasero",\n  "$item_ironscrap": "Ferraille",\n  "$item_jotunpuffs": "Globes jötnars",\n  "$item_juteblue": "Jute bleue",\n  "$item_jutered": "Jute rouge",\n  "$item_kale": "Chou kale",\n  "$item_kalechips": "Chips de chou kale",\n  "$item_kalechips_uncooked": "Chips de chou kale crus",\n  "$item_kaleseeds": "Graines de chou kale",\n  "$item_keys_gold_uncooked": "Moulage : clé délicate",\n  "$item_knife_blackmetal": "Couteau en sombracier",\n  "$item_knife_butcher": "Couteau de boucher",\n  "$item_knife_chitin": "Rasoir abyssal",\n  "$item_knife_copper": "Couteau en cuivre",\n  "$item_knife_flint": "Couteau en silex",\n  "$item_knife_gold": "Dague nordique",\n  "$item_knife_gold_bloodlightning": "Dague de sang-tonnerre",\n  "$item_knife_gold_bloodlightning_uncooked": "Moulage : dague de sang-tonnerre",\n  "$item_knife_gold_frostfire": "Dague de givrefeu",\n  "$item_knife_gold_frostfire_uncooked": "Moulage : dague de givrefeu",\n  "$item_knife_gold_uncooked": "Moulage : dague nordique",\n  "$item_knife_silver": "Couteau en argent",\n  "$item_knife_skollandhati": "Sköll et Hati",\n  "$item_knife_void": "Mandevide",\n  "$item_knife_wood": "Couteau en bois",\n  "$item_knockback": "Repoussement",\n  "$item_lantern": "Lanterne dvergr",\n  "$item_lanternDN": "Lanterne récupérée",\n  "$item_lavabomb": "Bombe au basalte",\n  "$item_leatherscraps": "Bouts de cuir",\n  "$item_leatherstraps": "Lanières de cuir",\n  "$item_legs_berserker": "Pagne de l\'ours",\n  "$item_legs_berserker_undead": "Parure d\'ours maudit",\n  "$item_legs_bronze": "Jambières en plaques de bronze",\n  "$item_legs_carapace": "Jambières en carapace",\n  "$item_legs_fenris": "Braies de Fenris",\n  "$item_legs_flametal": "Jambières en flametal",\n  "$item_legs_heavy_deepnorth": "Pantalon du courage",\n  "$item_legs_heavy_gold_uncooked": "Moulage : pantalon du courage",\n  "$item_legs_iron": "Jambières en plaques de fer",\n  "$item_legs_leather": "Pantalon en cuir",\n  "$item_legs_lox": "Pantalon en fourrure de lox",\n  "$item_legs_mage": "Pantalon d\'Eitr tissé",\n  "$item_legs_mage_ashlands": "Pantalon d\'Embla",\n  "$item_legs_mage_deepnorth": "Pantalon de l\'orateur",\n  "$item_legs_mage_gold_uncooked": "Moulage : pantalon de l\'orateur",\n  "$item_legs_medium_ashlands": "Pantalon d\'Ask",\n  "$item_legs_medium_deepnorth": "Pantalon de l\'Avant-garde",\n  "$item_legs_medium_gold_uncooked": "Moulage : pantalon de l\'Avant-garde",\n  "$item_legs_pgreaves": "Jambières rembourrées",\n  "$item_legs_rags": "Pantalon en haillons",\n  "$item_legs_root": "Bottes de racines",\n  "$item_legs_trollleather": "Pantalon en cuir de troll",\n  "$item_legs_wolf": "Jambières de loup",\n  "$item_limitfallspeed": "Vitesse de chute limitée",\n  "$item_linenthread": "Toile de lin",\n  "$item_lingonberries": "Airelles rouges",\n  "$item_lingondricka": "Jus d\'airelles rouges",\n  "$item_loxmeat": "Viande de Lox",\n  "$item_loxmeat_cooked": "Viande de Lox cuite",\n  "$item_loxpelt": "Peau de Lox",\n  "$item_loxpie": "Tourte au Lox",\n  "$item_loxpie_uncooked": "Tourte au lox non cuite",\n  "$item_mace_bronze": "Massue de bronze",\n  "$item_mace_eldner": "Massue en flametal",\n  "$item_mace_eldner_blood": "Masse-sang",\n  "$item_mace_eldner_lightning": "Étoile des tempêtes",\n  "$item_mace_eldner_nature": "Klossen",\n  "$item_mace_gold": "Massue nordique",\n  "$item_mace_gold_bloodlightning": "Massue de sang-tonnerre",\n  "$item_mace_gold_bloodlightning_uncooked": "Moulage : massue de sang-tonnerre",\n  "$item_mace_gold_frostfire": "Massue de givrefeu",\n  "$item_mace_gold_frostfire_uncooked": "Moulage : massue de givrefeu",\n  "$item_mace_gold_uncooked": "Moulage : massue nordique",\n  "$item_mace_iron": "Massue de fer",\n  "$item_mace_needle": "Porc-épic",\n  "$item_mace_silver": "Argivre",\n  "$item_mace_wood": "Massue en bois",\n  "$item_mace2h_gold": "Masse nordique",\n  "$item_mace2h_gold_bloodlightning": "Masse de sang-tonnerre",\n  "$item_mace2h_gold_bloodlightning_uncooked": "Moulage : masse de sang-tonnerre",\n  "$item_mace2h_gold_frostfire": "Masse de givrefeu",\n  "$item_mace2h_gold_frostfire_uncooked": "Moulage : masse de givrefeu",\n  "$item_mace2h_gold_uncooked": "Moulage : masse nordique",\n  "$item_magecap": "Coiffe-de-mage",\n  "$item_magicallystuffedmushroom": "Champignon farci",\n  "$item_magicallystuffedmushroomuncooked": "Champignon farci cru",\n  "$item_mandible": "Mandibule",\n  "$item_marinatedgreens": "Légumes marinés",\n  "$item_mashedmeat": "Écrasée de viande",\n  "$item_maxadrenaline": "Adrénaline",\n  "$item_mead_bugrepellent": "Concoction anti-morstique",\n  "$item_mead_bzerker": "Hydromel des berserkir",\n  "$item_mead_eitr_lingering": "Hydromel d\'Eitr latent",\n  "$item_mead_eitr_minor": "Hydromel d\'Eitr mineur",\n  "$item_mead_frostres": "Hydromel de résistance au gel",\n  "$item_mead_hasty": "Tonique de ratatosk",\n  "$item_mead_hp_lingering": "Hydromel de vie latente",\n  "$item_mead_hp_major": "Hydromel extrêmement revigorant",\n  "$item_mead_hp_medium": "Hydromel très revigorant",\n  "$item_mead_hp_minor": "Hydromel revigorant",\n  "$item_mead_lightfoot": "Hydromel du pied léger",\n  "$item_mead_poisonres": "Hydromel de résistance au poison",\n  "$item_mead_stamina_lingering": "Hydromel d\'endurance latente",\n  "$item_mead_stamina_medium": "Hydromel de bonne endurance",\n  "$item_mead_stamina_minor": "Hydromel d\'endurance",\n  "$item_mead_strength": "Hydromel de force des trolls",\n  "$item_mead_swimmer": "Élixir de Vananidir",\n  "$item_mead_tamer": "Infusion des murmures sauvages",\n  "$item_mead_tasty": "Hydromel savoureux",\n  "$item_mead_trollpheromones": "Potion d\'amour trolle",\n  "$item_meadbasebugrepellent": "Base d\'hydromel : anti-morstique",\n  "$item_meadbasebzerker": "Base d\'hydromel : berserkir",\n  "$item_meadbaseeitr": "Base d\'hydromel : Eitr mineur",\n  "$item_meadbaseeitr_lingering": "Base d\'hydromel : Eitr latent",\n  "$item_meadbasefrostresist": "Base d\'hydromel : résistance au givre",\n  "$item_meadbasehasty": "Base d\'hydromel : ratatosk",\n  "$item_meadbasehealth": "Base d\'hydromel : revigorant",\n  "$item_meadbasehealth_lingering": "Base d\'hydromel : vie latente",\n  "$item_meadbasehealth_major": "Base d\'hydromel : extrêmement revigorant",\n  "$item_meadbasehealth_medium": "Base d\'hydromel : très revigorant",\n  "$item_meadbaselightfoot": "Base d\'hydromel : pied léger",\n  "$item_meadbasepoisonresist": "Base d\'hydromel : résistance au poison",\n  "$item_meadbasestamina": "Base d\'hydromel : endurance",\n  "$item_meadbasestamina_lingering": "Base d\'hydromel : endurance latente",\n  "$item_meadbasestamina_medium": "Base d\'hydromel : bonne endurance",\n  "$item_meadbasestrength": "Base d\'hydromel : force des trolls",\n  "$item_meadbaseswimmer": "Base d\'hydromel : Vananidir",\n  "$item_meadbasetamer": "Base d\'hydromel : murmures sauvages",\n  "$item_meadbasetasty": "Base d\'hydromel : savoureux",\n  "$item_meat_cooked": "Viande cuite",\n  "$item_meat_raw": "Viande crue",\n  "$item_meat_rotten": "Viande avariée",\n  "$item_meatballsmashedpoteitr": "Boulettes de viande et poteitr",\n  "$item_meatplatter": "Plateau de viande",\n  "$item_meatplatteruncooked": "Plateau de viande crue",\n  "$item_mechanicalspring": "Ressort mécanique",\n  "$item_memorialcoal": "Charbon du souvenir",\n  "$item_mincemeatsauce": "Sauce à la viande hachée",\n  "$item_mistharesupreme": "Suprême de lièvre des brumes",\n  "$item_mistharesupremeuncooked": "Suprême de lièvre des brumes cru",\n  "$item_mold_armor_gold_chest": "Moule : plastron du courage",\n  "$item_mold_armor_gold_helmet": "Moule : casque du courage",\n  "$item_mold_armor_gold_legs": "Moule : pantalon du courage",\n  "$item_mold_armor_mage_chest": "Moule : robe de l\'orateur",\n  "$item_mold_armor_mage_helmet": "Moule : coiffe de l\'orateur",\n  "$item_mold_armor_mage_legs": "Moule : pantalon de l\'orateur",\n  "$item_mold_armor_medium_chest": "Moule : plastron de cuir de l\'Avant-garde",\n  "$item_mold_armor_medium_helmet": "Moule : capuche de l\'Avant-garde",\n  "$item_mold_armor_medium_legs": "Moule : pantalon de l\'Avant-garde",\n  "$item_mold_atgeir": "Moule : atgeir nordique",\n  "$item_mold_axe": "Moule : hache nordique",\n  "$item_mold_axe2h": "Moule : bardiche nordique",\n  "$item_mold_bow": "Moule : arc nordique",\n  "$item_mold_crossbow": "Moule : arbalète nordique",\n  "$item_mold_fistweapon": "Moule : chaînes de poing nordiques",\n  "$item_mold_keys": "Moule : clé délicate",\n  "$item_mold_knife": "Moule : dague nordique",\n  "$item_mold_mace": "Moule : massue nordique",\n  "$item_mold_mace2h": "Moule : masse nordique",\n  "$item_mold_shield_buckler": "Moule : targe nordique",\n  "$item_mold_shield_round": "Moule : bouclier nordique",\n  "$item_mold_shield_tower": "Moule : grand bouclier nordique",\n  "$item_mold_spear": "Moule : lance nordique",\n  "$item_mold_stafffrostorbs": "Moule : Vengeance nordique",\n  "$item_mold_stafforbofahri": "Moule : Flèche de l\'écho",\n  "$item_mold_staffspiritcaller": "Moule : Mande-esprits",\n  "$item_mold_staffthunderblood": "Moule : Coup de tonnerre",\n  "$item_mold_sword": "Moule : épée nordique",\n  "$item_mold_sword2h": "Moule : espadon nordique",\n  "$item_moleclaws": "Longues griffes",\n  "$item_moltencore": "Noyau en fusion",\n  "$item_moose_meat": "Viande d\'élan",\n  "$item_moose_meat_cooked": "Viande d\'élan cuite",\n  "$item_moosehide": "Peau d\'élan",\n  "$item_moosekebab": "Pain et viande",\n  "$item_moosesinew": "Tendon d\'élan",\n  "$item_morgenheart": "Cœur de morgen",\n  "$item_morgensinew": "Tendon de morgen",\n  "$item_movement_modifier": "Vitesse de déplacement",\n  "$item_mushroom_bzerker": "Amanite",\n  "$item_mushroomblue": "Champignon bleu",\n  "$item_mushroomcommon": "Champignon",\n  "$item_mushroomomelette": "Omelette aux champignons",\n  "$item_mushroomyellow": "Champignon jaune",\n  "$item_necktail": "Queue de Nixe",\n  "$item_necktailgrilled": "Queue de Nixe grillée",\n  "$item_needle": "Aiguille",\n  "$item_nornthread": "Fils des Nornes",\n  "$item_noteleport": "Ne peut être téléporté",\n  "$item_oakseeds": "Glands",\n  "$item_oat": "Flocons d\'avoine",\n  "$item_oatflour": "Farine d\'avoine",\n  "$item_oatmeallingonberryjam": "Gruau d\'avoine",\n  "$item_oatmilk": "Boisson d\'avoine",\n  "$item_oatseeds": "Graines d\'avoine",\n  "$item_obsidian": "Obsidienne",\n  "$item_onehanded": "Une main",\n  "$item_onion": "Oignon",\n  "$item_onionseeds": "Graines d\'oignon",\n  "$item_onionsoup": "Soupe à l\'oignon",\n  "$item_ooze": "Gadoue",\n  "$item_ooze_mork": "Pâte inanimée",\n  "$item_oozebomb": "Bombe puante",\n  "$item_orbfrostfire": "Essence de givrefeu",\n  "$item_orbthunderblood": "Essence de sang-tonnerre",\n  "$item_ovenpancake": "Pancake au four",\n  "$item_ovenpancake_uncooked": "Pâte de pancake au four",\n  "$item_pancakes": "Pancakes",\n  "$item_parryadrenaline": "Adrénaline de parade",\n  "$item_parrybonus": "Bonus de parade",\n  "$item_parts": "pièces",\n  "$item_pickable_barley": "Orge",\n  "$item_pickable_bogiron": "Fer à repasser",\n  "$item_pickable_branch": "Branche",\n  "$item_pickable_hairstrands": "Fourrure de Fenris",\n  "$item_pickable_meatpile": "Tas de viande",\n  "$item_pickable_meteorite": "Météorite",\n  "$item_pickable_obsidian": "Obsidienne",\n  "$item_pickable_skeletalremains": "Restes de squelette",\n  "$item_pickable_sulfurrock": "Pierre de soufre",\n  "$item_pickaxe_antler": "Pioche de bois de cerf",\n  "$item_pickaxe_blackmetal": "Pioche en sombracier",\n  "$item_pickaxe_bronze": "Pioche en bronze",\n  "$item_pickaxe_iron": "Pioche en fer",\n  "$item_pickaxe_stone": "Pioche en pierre",\n  "$item_pinecone": "Pomme de pin",\n  "$item_piquantpie": "Tarte piquante",\n  "$item_piquantpie_uncooked": "Tarte piquante crue",\n  "$item_pot_shard_green": "Fragment de pot",\n  "$item_poteitr": "Poteitr",\n  "$item_poteitrseeds": "Graine de poteitr",\n  "$item_powdereddragonegg": "Coquilles d\'œuf de dragon en poudre",\n  "$item_proustitepowder": "Poudre de proustite",\n  "$item_pukeberries": "Dégobibaies",\n  "$item_pulledbear": "Effiloché d\'ours",\n  "$item_pungentpebbles": "Cailloux odorants",\n  "$item_queen_drop": "Butin de la Reine",\n  "$item_queenbee": "Reine abeille",\n  "$item_queensjam": "Confiture de la reine",\n  "$item_raspberries": "Framboises",\n  "$item_repairlevel": "Niveau de la station de réparation",\n  "$item_resin": "Résine",\n  "$item_roastedcrustpie": "Tourte rôtie",\n  "$item_roastedcrustpie_uncooked": "Tourte rôtie crue",\n  "$item_root": "Racine",\n  "$item_roundlog": "Bois robuste",\n  "$item_royaljelly": "Gelée royale",\n  "$item_ruby": "Rubis",\n  "$item_saddleasksvin": "Selle d\'asksvin",\n  "$item_saddlelox": "Selle de Lox",\n  "$item_saddlemoose": "Selle d\'élan",\n  "$item_salad": "Salade",\n  "$item_sap": "Sève",\n  "$item_sausages": "Saucisses",\n  "$item_scalehide": "Peau écailleuse",\n  "$item_scorchingmedley": "Mélange brûlant",\n  "$item_scythe": "Faux",\n  "$item_scythehandle": "Manche de faux",\n  "$item_sealhide": "Peau de phoque",\n  "$item_sealsoup": "Soupe de viande de phoque",\n  "$item_seekeraspic": "Aspic de fouineur",\n  "$item_seekerqueen_drop": "Carapace majestueuse",\n  "$item_serpentmeat": "Viande de serpent",\n  "$item_serpentmeatcooked": "Viande de serpent cuite",\n  "$item_serpentscale": "Écaille de serpent",\n  "$item_serpentstew": "Soupe de serpent",\n  "$item_seteffect": "Définir l’effet",\n  "$item_sharpeningstone": "Roue à aiguiser",\n  "$item_shield_banded": "Bouclier bandé",\n  "$item_shield_blackmetal": "Bouclier en sombracier",\n  "$item_shield_blackmetal_tower": "Écu en sombracier",\n  "$item_shield_bonetower": "Écu en os",\n  "$item_shield_bronzebuckler": "Bouclier en bronze",\n  "$item_shield_buckler_gold_uncooked": "Moulage : targe nordique",\n  "$item_shield_carapace": "Bouclier en carapace",\n  "$item_shield_carapacebuckler": "Targe en carapace",\n  "$item_shield_flametal": "Bouclier en flametal",\n  "$item_shield_flametal_tower": "Écu en flametal",\n  "$item_shield_gold": "Bouclier nordique",\n  "$item_shield_gold_tower": "Grand bouclier nordique",\n  "$item_shield_goldbuckler": "Targe nordique",\n  "$item_shield_iron_square": "Bouclier en fer",\n  "$item_shield_iron_tower": "Écu en fer",\n  "$item_shield_ironbuckler": "Bouclier en fer",\n  "$item_shield_knight": "Bouclier de chevalier INUTILISÉ",\n  "$item_shield_roots": "Bouclier des racines",\n  "$item_shield_round_gold_uncooked": "Moulage : bouclier nordique",\n  "$item_shield_serpentscale": "Bouclier ophidien",\n  "$item_shield_silver": "Bouclier en argent",\n  "$item_shield_tower_gold_uncooked": "Moulage : grand bouclier nordique",\n  "$item_shield_wood": "Bouclier en bois",\n  "$item_shield_woodtower": "Écu en bois",\n  "$item_shieldcore": "Noyau de bouclier",\n  "$item_shocklatesmoothie": "Gadoue-shake",\n  "$item_silver": "Argent",\n  "$item_silvernecklace": "Collier en argent",\n  "$item_silverore": "Minerai d\'argent",\n  "$item_sizzlingberrybroth": "Bouillon de baies grésillant",\n  "$item_sledge_demolisher": "Démolisseur",\n  "$item_sledge_gold": "Masse nordique",\n  "$item_sledge_gold_uncooked": "Moulage : masse nordique",\n  "$item_sledge_iron": "Masse de fer",\n  "$item_sledge_wood": "Masse en bois",\n  "$item_smokebomb": "Bombe fumigène",\n  "$item_smokedfish": "Poisson fumé",\n  "$item_smokedmoosemeat": "Viande d\'élan fumée",\n  "$item_smokepuff": "Fume-spore",\n  "$item_snowball": "Boule de neige",\n  "$item_snowshovel": "Pelle à neige",\n  "$item_softtissue": "Tissu délicat",\n  "$item_sparkler": "Cierge magique",\n  "$item_sparklingshroomshake": "Velouté de champignon pétillant",\n  "$item_spear_ancientbark": "Lance en écorce ancienne",\n  "$item_spear_bronze": "Lance en bronze",\n  "$item_spear_carapace": "Lance en carapace",\n  "$item_spear_chitin": "Harpon abyssal",\n  "$item_spear_flint": "Lance en silex",\n  "$item_spear_gold": "Lance nordique",\n  "$item_spear_gold_bloodlightning": "Lance de sang-tonnerre",\n  "$item_spear_gold_bloodlightning_uncooked": "Moulage : lance de sang-tonnerre",\n  "$item_spear_gold_frostfire": "Lance de givrefeu",\n  "$item_spear_gold_frostfire_uncooked": "Moulage : lance de givrefeu",\n  "$item_spear_gold_uncooked": "Moulage : lance nordique",\n  "$item_spear_splitner": "Pourfendeuse",\n  "$item_spear_splitner_blood": "Pourfendeuse la sanglante",\n  "$item_spear_splitner_lightning": "Pourfendeuse des tempêtes",\n  "$item_spear_splitner_nature": "Pourfendeuse la primitive",\n  "$item_spear_wolffang": "Lance en crocs",\n  "$item_spear_wood": "Lance en bois",\n  "$item_spiceashlands": "Poudre d\'épices fougueuses",\n  "$item_spicedeepnorth": "Assaisonnement de la gourde",\n  "$item_spiceforests": "Mélange d\'herbes des bois",\n  "$item_spicemistlands": "Herbes des collines cachées",\n  "$item_spicemountains": "Poivre moulu du col",\n  "$item_spiceoceans": "Herbes du marinier",\n  "$item_spiceplains": "Moisson de l\'herboriste",\n  "$item_spicymarmalade": "Marmelade épicée",\n  "$item_staff_frostorbs": "Vengeance nordique",\n  "$item_staff_lightning": "Dundr",\n  "$item_staff_orbofahri": "Flèche de l\'écho",\n  "$item_staff_orbofahri_uncooked": "Moulage : Flèche de l\'écho",\n  "$item_staff_spiritcaller": "Mande-esprits",\n  "$item_staff_spiritcaller_uncooked": "Moulage : Mande-esprits",\n  "$item_staff_thunderblood": "Coup de tonnerre",\n  "$item_staff_thunderblood_uncooked": "Moulage : Coup de tonnerre",\n  "$item_staffclusterbomb": "Bâton de fracture",\n  "$item_stafffireball": "Bâton des braises",\n  "$item_staffgreenroots": "Bâton de la nature",\n  "$item_stafficeshards": "Bâton de givre",\n  "$item_stafflaser": "Bâton lancegivre",\n  "$item_staffredlightning": "Dundr",\n  "$item_staffredtroll": "Bâton des trolls",\n  "$item_staffshield": "Bâton de protection",\n  "$item_staffskeleton": "Éveil des morts",\n  "$item_stagbreaker": "Brise-cerf",\n  "$item_staminahold": "Puiser de l\'endurance",\n  "$item_staminause": "Utiliser de l\'endurance",\n  "$item_stone": "Pierre",\n  "$item_stonerock": "Pierre",\n  "$item_sulfurstone": "Soufre",\n  "$item_surtlingcore": "Cœur de surtling",\n  "$item_swimspeed_modifier": "Vitesse de nage",\n  "$item_sword_blackmetal": "Épée en sombracier",\n  "$item_sword_bronze": "Épée en bronze",\n  "$item_sword_dyrnwyn": "Dyrnwyn",\n  "$item_sword_fire": "Dyrnwyn",\n  "$item_sword_gold": "Épée nordique",\n  "$item_sword_gold_bloodlightning": "Épée de sang-tonnerre",\n  "$item_sword_gold_bloodlightning_uncooked": "Moulage : épée de sang-tonnerre",\n  "$item_sword_gold_frostfire": "Épée de givrefeu",\n  "$item_sword_gold_frostfire_uncooked": "Moulage : épée de givrefeu",\n  "$item_sword_gold_uncooked": "Moulage : épée nordique",\n  "$item_sword_iron": "Épée en fer",\n  "$item_sword_krom": "Krom",\n  "$item_sword_mistwalker": "Marchebrume",\n  "$item_sword_niedhogg": "Nidhögg",\n  "$item_sword_niedhogg_blood": "Nidhögg le sanglant",\n  "$item_sword_niedhogg_lightning": "Nidhögg le tonitruant",\n  "$item_sword_niedhogg_nature": "Nidhögg le primitif",\n  "$item_sword_silver": "Épée en argent",\n  "$item_sword_slayer": "Égorgeuse",\n  "$item_sword_slayer_blood": "Égorgeuse brutale",\n  "$item_sword_slayer_lightning": "Égorgeuse flagellante",\n  "$item_sword_slayer_nature": "Égorgeuse primitive",\n  "$item_sword_wood": "Épée en bois",\n  "$item_sword_wood_2h": "Espadon en bois",\n  "$item_sword2h_gold": "Espadon nordique",\n  "$item_sword2h_gold_bloodlightning": "Espadon de sang-tonnerre",\n  "$item_sword2h_gold_bloodlightning_uncooked": "Moulage : espadon de sang-tonnerre",\n  "$item_sword2h_gold_frostfire": "Espadon de givrefeu",\n  "$item_sword2h_gold_frostfire_uncooked": "Moulage : espadon de givrefeu",\n  "$item_sword2h_gold_uncooked": "Moulage : espadon nordique",\n  "$item_tamedonly": "Ne peut blesser que les créatures apprivoisées.",\n  "$item_tankard": "Chope",\n  "$item_tankard_anniversary": "Corne de la Célébration",\n  "$item_tankard_odin": "Corne d\'hydromel d\'Odin",\n  "$item_tar": "Goudron",\n  "$item_thistle": "Chardon",\n  "$item_thunderstone": "Pierre de tonnerre",\n  "$item_tin": "Étain",\n  "$item_tinore": "Minerai d\'étain",\n  "$item_torch": "Torche",\n  "$item_total": "Total",\n  "$item_trinket": "Bibelot",\n  "$item_trinketblackdamagedealth": "Peau de fer",\n  "$item_trinketblackdtamina": "Voile d\'ombre",\n  "$item_trinketbloodgoldhealth": "Perce-cou",\n  "$item_trinketbloodgoldstamina": "Couronne de sorcière",\n  "$item_trinketbronzehealth": "Cœur de la forêt",\n  "$item_trinketbronzestamina": "Pendentif en bronze",\n  "$item_trinketcarapaceeitr": "Boucles d\'oreilles palpitantes",\n  "$item_trinketchitinswim": "Aileron du destin",\n  "$item_trinketflametaleitr": "Jörmundling",\n  "$item_trinketflametalstaminahealth": "Cœur ardent",\n  "$item_trinketironhealth": "Broche en fer",\n  "$item_trinketironstamina": "Bracelet de cheville",\n  "$item_trinketscalestaminadamage": "Fers retentissants",\n  "$item_trinketsilverdamage": "Vision du loup",\n  "$item_trinketsilverresist": "Cœur de cristal",\n  "$item_trollhide": "Peau de troll",\n  "$item_trophy_abomination": "Trophée d\'abomination",\n  "$item_trophy_asksvin": "Trophée d\'asksvin",\n  "$item_trophy_barka": "Trophée de barka",\n  "$item_trophy_bjorn": "Trophée d\'ours",\n  "$item_trophy_bjorn_undead": "Trophée d\'ours maudit",\n  "$item_trophy_blob": "Trophée de blob",\n  "$item_trophy_blob_frost": "Trophée de blob de givre",\n  "$item_trophy_blob_lava": "Trophée de blob de lave",\n  "$item_trophy_blob_morkhalla": "Trophée de blob",\n  "$item_trophy_boar": "Trophée de sanglier",\n  "$item_trophy_bonemass": "Trophée de Masse-d’Os",\n  "$item_trophy_bonemaw": "Trophée de gueule-d\'os",\n  "$item_trophy_brutebro": "Trophée de Thungr",\n  "$item_trophy_charredarcher": "Trophée d\'archer",\n  "$item_trophy_charredmage": "Trophée de sorcier",\n  "$item_trophy_charredmelee": "Trophée de guerrier",\n  "$item_trophy_cultist": "Trophée de cultiste",\n  "$item_trophy_cultist_hildir": "Trophée de Geirrhafa",\n  "$item_trophy_deathsquito": "Trophée de morstique",\n  "$item_trophy_deer": "Trophée de cerf",\n  "$item_trophy_dragonqueen": "Trophée de Moder",\n  "$item_trophy_draugr": "Trophée de draugr",\n  "$item_trophy_draugrelite": "Trophée de draugr élite",\n  "$item_trophy_dvergr": "Trophée de dvergr",\n  "$item_trophy_eikthyr": "Trophée d\'Eikthyr",\n  "$item_trophy_elaking": "Trophée d\'elaking",\n  "$item_trophy_elder": "Trophée de l’Aîné",\n  "$item_trophy_fader": "Trophée de Fader",\n  "$item_trophy_fallenvalkyrie": "Trophée de valkyrie déchue",\n  "$item_trophy_fenring": "Trophée de fenring",\n  "$item_trophy_foresttroll": "Trophée de troll de la forêt",\n  "$item_trophy_frosttroll": "Trophée de troll de givre",\n  "$item_trophy_ghost": "Trophée de fantôme",\n  "$item_trophy_gjall": "Trophée de gjall",\n  "$item_trophy_goblin": "Trophée de gobelin",\n  "$item_trophy_goblinbrute": "Trophée de berserker gobelin",\n  "$item_trophy_goblinking": "Trophée de Yagluth",\n  "$item_trophy_goblinshaman": "Trophée de Chaman Gobelin",\n  "$item_trophy_greydwarf": "Trophée de naingris",\n  "$item_trophy_greydwarfbrute": "Trophée de brute naingris",\n  "$item_trophy_greydwarfshaman": "Trophée de chaman naingris",\n  "$item_trophy_growth": "Trophée d\'excroissance",\n  "$item_trophy_hare": "Trophée de lièvre",\n  "$item_trophy_hatchling": "Trophée de drac",\n  "$item_trophy_jotunwarrior": "Trophée de krigen",\n  "$item_trophy_jotunwitch": "Trophée d\'Hexen",\n  "$item_trophy_leech": "Trophée de sangsue",\n  "$item_trophy_lox": "Trophée de lox",\n  "$item_trophy_mole": "Trophée de Sans yeux",\n  "$item_trophy_moose": "Trophée d\'élan",\n  "$item_trophy_morgen": "Trophée de morgen",\n  "$item_trophy_neck": "Trophée de Nixe",\n  "$item_trophy_seal": "Trophée de phoque",\n  "$item_trophy_seeker": "Trophée de fouineur",\n  "$item_trophy_seeker_brute": "Trophée de soldat fouineur",\n  "$item_trophy_seekerqueen": "Trophée de la Reine",\n  "$item_trophy_serpent": "Trophée de serpent",\n  "$item_trophy_sgolem": "Trophée de golem de pierre",\n  "$item_trophy_shamanbro": "Trophée de Zil",\n  "$item_trophy_skeleton": "Trophée de squelette",\n  "$item_trophy_skeleton_hildir": "Trophée de Brenna",\n  "$item_trophy_skeletonpoison": "Trophée de cadavre rance",\n  "$item_trophy_surtling": "Trophée de surtling",\n  "$item_trophy_tick": "Trophée de tique",\n  "$item_trophy_troll": "Trophée de troll",\n  "$item_trophy_ulv": "Trophée de warg",\n  "$item_trophy_volture": "Trophée de voltour",\n  "$item_trophy_wolf": "Trophée de loup",\n  "$item_trophy_wraith": "Trophée de spectre",\n  "$item_trophy_writhan": "Trophée de writhan",\n  "$item_turnip": "Navet",\n  "$item_turnipseeds": "Graines de navet",\n  "$item_turnipstew": "Soupe de navets",\n  "$item_turretbolt": "Projectile en sombracier",\n  "$item_turretbolt_bloodgold": "Projectile d\'or-sang",\n  "$item_turretbolt_flametal": "Projectile en flametal",\n  "$item_turretboltwood": "Projectile en bois",\n  "$item_twohanded": "Deux mains",\n  "$item_UndeadBjornRibcage": "Cage thoracique d\'ours maudit",\n  "$item_upgrader_armor": "Protection",\n  "$item_upgrader_name": "Idole",\n  "$item_upgrader_tier0": "Bois",\n  "$item_upgrader_tier1": "Bronze",\n  "$item_upgrader_tier2": "Fer",\n  "$item_upgrader_tier3": "Argent",\n  "$item_upgrader_tier4": "Sombracier",\n  "$item_upgrader_tier5": "Marbre noir",\n  "$item_upgrader_tier6": "Flametal",\n  "$item_upgrader_tier7": "Or-sang",\n  "$item_upgrader_weapon": "Combat",\n  "$item_utility": "Accessoires",\n  "$item_value": "Valeur",\n  "$item_vikingcupcake": "Brioche glacée",\n  "$item_vikingcupcake_uncooked": "Brioche crue",\n  "$item_vineberry": "Grappe de baies-de-lierre",\n  "$item_vineberryseeds": "Graines de lierre des cendres",\n  "$item_vinegreenseeds": "Graines de lierre",\n  "$item_volture_meat": "Viande de voltour",\n  "$item_volture_meat_cooked": "Viande de voltour cuite",\n  "$item_voltureegg": "Œuf de voltour",\n  "$item_weight": "Poids",\n  "$item_wishbone": "Bréchet",\n  "$item_wisp": "Feu-follet",\n  "$item_witheredbone": "Os atrophié",\n  "$item_wolf_meat": "Viande de loup",\n  "$item_wolf_meat_cooked": "Viande de loup cuite",\n  "$item_wolf_skewer": "Brochette de loup",\n  "$item_wolfclaw": "Griffes de Fenris",\n  "$item_wolffang": "Croc de loup",\n  "$item_wolfhairbundle": "Fourrure de Fenris",\n  "$item_wolfjerky": "Viande séchée de loup",\n  "$item_wolfpelt": "Peau de loup",\n  "$item_wood": "Bois",\n  "$item_writhanroots": "Racines de writhan",\n  "$item_yagluththing": "Esprit déchiré",\n  "$item_yggdrasilporridge": "Gruau d\'Yggdrasil",\n  "$item_yggdrasilwood": "Bois d\'Yggdrasil",\n  "$item_ymirremains": "Chair d\'Ymir",\n  "$piece_ancient_pot": "Pot ancien",\n  "$piece_ancientmetalbarstack": "Tas d\'ancien métal",\n  "$piece_archerytarget": "Cible",\n  "$piece_archerytarget_hits": "touches",\n  "$piece_archerytarget_lastscores": "Touches",\n  "$piece_archerytarget_reset": "Récupérer les flèches",\n  "$piece_archerytarget_total": "Total",\n  "$piece_armorstand": "Support d\'armure",\n  "$piece_armorstand_cantattach": "Cet objet ne va pas là.",\n  "$piece_artisan_ext1": "Presse artisanale",\n  "$piece_artisanstation": "Table d\'artisan",\n  "$piece_ashwood_archedwall": "Arche murale en cendrebois",\n  "$piece_ashwood_beam_1m": "Poutre en cendrebois 1m",\n  "$piece_ashwood_beam_2m": "Poutre en cendrebois 2m",\n  "$piece_ashwood_bed": "Lit en cendrebois",\n  "$piece_ashwood_decowall": "Mur décoratif en cendrebois",\n  "$piece_ashwood_decowall_divider": "Séparateur en cendrebois",\n  "$piece_ashwood_decowall_tree": "Fenêtre décorative en cendrebois",\n  "$piece_ashwood_door": "Porte en cendrebois",\n  "$piece_ashwood_floor_1x1": "Sol en cendrebois 1x1",\n  "$piece_ashwood_floor_2x2": "Sol en cendrebois 2x2",\n  "$piece_ashwood_floor_deco": "Sol décoratif en cendrebois",\n  "$piece_ashwood_halfwall": "Demi-mur en cendrebois",\n  "$piece_ashwood_pole_1m": "Poteau en cendrebois 1m",\n  "$piece_ashwood_pole_2m": "Poteau en cendrebois 2m",\n  "$piece_ashwood_quarterwall": "Quart de mur en cendrebois",\n  "$piece_ashwood_wall": "Mur en cendrebois",\n  "$piece_ashwoodarch_big": "Arche en cendrebois",\n  "$piece_ashwoodarch_bottom": "Arche en cendrebois (bas)",\n  "$piece_ashwoodarch_top": "Arche en cendrebois (haut)",\n  "$piece_ashwoodbeam26": "Poutre en cendrebois 26°",\n  "$piece_ashwoodbeam45": "Poutre en cendrebois 45°",\n  "$piece_ashwoodbeam67": "Poutre en cendrebois 67°",\n  "$piece_ashwoodcross26": "Croix de toit en cendrebois 26°",\n  "$piece_ashwoodcross45": "Croix de toit en cendrebois 45°",\n  "$piece_ashwoodstair": "Escalier en cendrebois",\n  "$piece_ashwoodwallroof_26": "Mur en cendrebois 26°",\n  "$piece_ashwoodwallroof_26_upsidedown": "Mur en cendrebois 26° (inversé)",\n  "$piece_ashwoodwallroof_45": "Mur en cendrebois 45°",\n  "$piece_ashwoodwallroof_45_upsidedown": "Mur en cendrebois 45° (inversé)",\n  "$piece_ashwoodwallroof67": "Mur en cendrebois 67°",\n  "$piece_ashwoodwallroof67upsidedown": "Mur en cendrebois 67° (inversé)",\n  "$piece_ashwoodwallrooftop67": "Croix de toit en cendrebois 67°",\n  "$piece_asksvinskeleton": "Squelette d\'asksvin",\n  "$piece_banner01": "Bannière noire",\n  "$piece_banner02": "Bannière bleue",\n  "$piece_banner03": "Bannière à rayures blanches et rouges",\n  "$piece_banner04": "Bannière rouge",\n  "$piece_banner05": "Bannière verte",\n  "$piece_banner06": "Bleu(e)",\n  "$piece_banner07": "Bannière à rayures blanches et bleues",\n  "$piece_banner08": "Bannière jaune",\n  "$piece_banner09": "Bannière violette",\n  "$piece_banner10": "Bannière orange",\n  "$piece_banner11": "Bannière blanche",\n  "$piece_barber": "Barbier",\n  "$piece_bathtub": "Baignoire",\n  "$piece_bed": "Lit",\n  "$piece_bed_claim": "Réclamer",\n  "$piece_bed_currentspawn": "Point d\'apparition actuel",\n  "$piece_bed_setspawn": "Définir comme point d\'apparition",\n  "$piece_bed_sleep": "Dormir",\n  "$piece_bed_unclaimed": "Lit non réclamé",\n  "$piece_bed02": "Lit dragon",\n  "$piece_beehive": "Ruche",\n  "$piece_beehive_area": "Les abeilles n\'aiment pas ce biome",\n  "$piece_beehive_check": "Observer les abeilles",\n  "$piece_beehive_extract": "Extraire",\n  "$piece_beehive_freespace": "Les abeilles ont besoin d\'un espace plus ouvert",\n  "$piece_beehive_happy": "Les abeilles sont heureuses",\n  "$piece_beehive_sleep": "Les abeilles dorment",\n  "$piece_bench_runed": "Banc sculpté",\n  "$piece_bench01": "Banc",\n  "$piece_benchlog": "Siège en rondin",\n  "$piece_birdnest": "Nid d\'oiseaux",\n  "$piece_birdnest_area": "Les oiseaux n\'aiment pas cet endroit",\n  "$piece_birdnest_check": "Vérifier le nid",\n  "$piece_birdnest_extract": "Ramasser des plumes",\n  "$piece_birdnest_freespace": "Les oiseaux ont besoin d\'un espace plus ouvert",\n  "$piece_birdnest_happy": "Les oiseaux s\'installent",\n  "$piece_birdnest_sleep": "Les oiseaux dorment",\n  "$piece_blackforge": "Forge noire",\n  "$piece_blackforge_ext1": "Cuve de forge noire",\n  "$piece_blackforge_ext2": "Étau",\n  "$piece_blackforge_ext3": "Coupe-métal",\n  "$piece_blackforge_ext4": "Taille-gemme",\n  "$piece_blackforge_ext5": "Tablier de forgeron",\n  "$piece_blackmarble_arch": "Arche de marbre noir",\n  "$piece_blackmarble_base1": "Socle de marbre noir",\n  "$piece_blackmarble_base2": "Socle de marbre noir large",\n  "$piece_blackmarble_basecorner": "Socle de marbre noir, coin",\n  "$piece_blackmarble_bench": "Banc de marbre noir",\n  "$piece_blackmarble_bronze_head1": "Tête de bronze 1",\n  "$piece_blackmarble_bronze_head2": "Tête de bronze 2",\n  "$piece_blackmarble_column_1": "Colonne de marbre noir, petite",\n  "$piece_blackmarble_column_2": "Colonne de marbre noir, large",\n  "$piece_blackmarble_column_3": "Colonne de marbre noir, grande",\n  "$piece_blackmarble_equilateral_triangle_floor": "Sol de marbre noir, triangle équilatéral",\n  "$piece_blackmarble_floor": "Sol de marbre noir",\n  "$piece_blackmarble_floor_triangle": "Sol de marbre noir, triangle",\n  "$piece_blackmarble_floor4x4": "Sol de marbre noir, 4x4",\n  "$piece_blackmarble_head_big1": "Grande tête de marbre noir 1",\n  "$piece_blackmarble_head_big2": "Grande tête de marbre noir 2",\n  "$piece_blackmarble_inverted_slope1x2": "Pente de marbre noir, inversée",\n  "$piece_blackmarble_out1": "Corniche de marbre noir",\n  "$piece_blackmarble_out2": "Corniche de marbre noir, large",\n  "$piece_blackmarble_outcorner": "Corniche de marbre noir, coin",\n  "$piece_blackmarble_slope1x2": "Pente de marbre noir",\n  "$piece_blackmarble_stair": "Escalier de marbre noir",\n  "$piece_blackmarble_stair_corner_left": "Escalier de marbre noir, gauche",\n  "$piece_blackmarble_stair_corner_right": "Escalier de marbre noir, droit",\n  "$piece_blackmarble_table": "Table de marbre noir",\n  "$piece_blackmarble_throne": "Trône de marbre noir",\n  "$piece_blackmarble_tile_floor_1x1": "Carreau de sol de marbre noir, petit",\n  "$piece_blackmarble_tile_floor_2x2": "Carreau de sol de marbre noir, grand",\n  "$piece_blackmarble_tile_wall_1x1": "Carreau de mur de marbre noir, petit",\n  "$piece_blackmarble_tile_wall_2x2": "Carreau de mur de marbre noir, grand",\n  "$piece_blackmarble_tile_wall_2x4": "Carreau de mur de marbre noir, large",\n  "$piece_blackmarble_tip": "Quart de flèche de marbre noir",\n  "$piece_blackmarble1x1": "Marbre noir 1x1x1",\n  "$piece_blackmarble2x1x1": "Marbre noir 2x1x1",\n  "$piece_blackmarble2x2_enforced": "Marbre noir renforcé",\n  "$piece_blackmarble2x2x1": "Marbre noir 2x2x1",\n  "$piece_blackmarble2x2x2": "Marbre noir 2x2x2",\n  "$piece_blackmetalbarstack": "Tas de sombracier",\n  "$piece_blackwoodbench01": "Banc en cendrebois",\n  "$piece_blackwoodstack": "Tas de cendrebois",\n  "$piece_BlackwoodStakewall": "Palissade en cendrebois",\n  "$piece_blastfurnace": "Haut fourneau",\n  "$piece_bloodgoldbarstack": "Tas d\'or-sang",\n  "$piece_bone_throne": "Trône d\'os",\n  "$piece_bonestack": "Tas d\'os",\n  "$piece_bonfire": "Feu de joie",\n  "$piece_brazierceiling01": "Brasier suspendu",\n  "$piece_brazierfloor01": "Brasero à pied",\n  "$piece_brazierfloor02": "Brasero bleu à pied",\n  "$piece_bronzebarstack": "Tas de bronze",\n  "$piece_candle": "Bougie en résine",\n  "$piece_cartographytable": "Table de cartographie",\n  "$piece_catapult_legsdown": "Baisser les pieds",\n  "$piece_catapult_legsup": "Lever les pieds",\n  "$piece_catapult_placeitem": "Placer l\'objet",\n  "$piece_catapult_wontfit": "Cela ne rentre pas dans la catapulte",\n  "$piece_cauldron": "Chaudron",\n  "$piece_cauldron_ext1_spice": "Support à épices",\n  "$piece_cauldron_ext3_butchertable": "Table de boucher",\n  "$piece_cauldron_ext4_pans": "Pots et casseroles",\n  "$piece_cauldron_ext5_mortarandpestle": "Mortier et pilon",\n  "$piece_cauldron_ext6_rollingpins": "Rouleaux à pâtisserie et planches à découper",\n  "$piece_cauldron_ext7_smoker": "Fumoir",\n  "$piece_celebrationgarland": "Guirlande de fleurs",\n  "$piece_chair": "Chaise",\n  "$piece_chair_runed": "Chaise sculptée",\n  "$piece_charcoalkiln": "Four à charbon",\n  "$piece_charredballista": "Baliste de chair",\n  "$piece_charredchest": "Coffre calciné",\n  "$piece_chest": "Coffre renforcé",\n  "$piece_chestbarrel": "Tonneau",\n  "$piece_chestblackmetal": "Coffre en sombracier",\n  "$piece_chestgrausten": "Coffre en grise-pierre",\n  "$piece_chestprivate": "Coffre personnel",\n  "$piece_chesttreasure": "Coffre au trésor",\n  "$piece_chestwarderobe": "Penderie",\n  "$piece_chestwood": "Coffre",\n  "$piece_clothdoor": "Rideau de jute rouge",\n  "$piece_coalpile": "Pile de charbon",\n  "$piece_container_empty": "VIDE",\n  "$piece_container_open": "Ouvrir",\n  "$piece_cookingstation": "Poste de cuisson",\n  "$piece_cookingstation_iron": "Cuisine en fer",\n  "$piece_copperbarstack": "Tas de cuivre",\n  "$piece_craftingstation": "Établi",\n  "$piece_crate": "Caisse",\n  "$piece_crate_long": "Caisse de composants dvergr",\n  "$piece_crystalwall1x1": "Mur de cristal 1x1",\n  "$piece_cstand_cook": "Cuire l\'aliment",\n  "$piece_cultivate": "Cultiver",\n  "$piece_darkwoodarch": "Arche de bois sombre",\n  "$piece_darkwoodbeam": "Poutre en bois sombre 2m",\n  "$piece_darkwoodbeam_26": "Poutre en bois sombre 26°",\n  "$piece_darkwoodbeam_45": "Poutre en bois sombre 45°",\n  "$piece_darkwoodbeam4": "Poutre en bois sombre 4m",\n  "$piece_darkwoodchair": "Chaise de bois sombre",\n  "$piece_darkwooddecowall": "Séparateur en bois sombre sculpté",\n  "$piece_darkwoodgate": "Portail de bois sombre",\n  "$piece_darkwoodpole": "Poteau en bois sombre 2m",\n  "$piece_darkwoodpole4": "Poteau en bois sombre 4m",\n  "$piece_darkwoodraven": "Corbeau décoratif",\n  "$piece_darkwoodroof26": "Toit de bardeaux 26°",\n  "$piece_darkwoodroof45": "Toit de bardeaux 45°",\n  "$piece_darkwoodroof67": "Toit de bardeaux 67°",\n  "$piece_darkwoodrooficorner": "Toit de bardeaux 26° concave",\n  "$piece_darkwoodrooficorner45": "Toit de bardeaux 45° concave",\n  "$piece_darkwoodrooficorner67": "Toit de bardeaux 67° concave",\n  "$piece_darkwoodroofocorner": "Toit de bardeaux 26° convexe",\n  "$piece_darkwoodroofocorner45": "Toit de bardeaux 45° convexe",\n  "$piece_darkwoodroofocorner67": "Toit de bardeaux 67° convexe",\n  "$piece_darkwoodrooftop": "Faîte de toit de bardeaux 26°",\n  "$piece_darkwoodrooftop45": "Faîte de toit de bardeaux 45°",\n  "$piece_darkwoodrooftop67": "Faîte de toit de bardeaux 67°",\n  "$piece_darkwoodwolf": "Loup décoratif",\n  "$piece_deco_stave_wall": "Mur en bois latté",\n  "$piece_deposit_copper": "Dépôt de cuivre",\n  "$piece_deposit_goldvein": "Gammeltroll pétrifié",\n  "$piece_deposit_obsidian": "Dépôt d\'obsidienne",\n  "$piece_deposit_silver": "Dépôt d\'argent",\n  "$piece_deposit_silvervein": "Veine d\'argent",\n  "$piece_deposit_tin": "Dépôt d\'étain",\n  "$piece_door_close": "Fermer",\n  "$piece_door_open": "Ouvrir",\n  "$piece_drawbridge": "Pont-levis",\n  "$piece_drawbridge_dn": "Pont-levis en sapin nordique",\n  "$piece_drawbridge_log": "Pont-levis rustique",\n  "$piece_dv_gate": "Vieille porte dvergr",\n  "$piece_dvergr_door": "Porte dvergr",\n  "$piece_dvergr_lantern": "Lanterne murale dvergr",\n  "$piece_dvergr_lantern_pole": "Lanterne sur pied dvergr",\n  "$piece_dvergr_metal_wall": "Mur de métal dvergr",\n  "$piece_dvergr_pole": "Poteau dvergr",\n  "$piece_dvergr_sharpstakes": "Pieux acérés dvergr",\n  "$piece_dvergr_spiralstair": "Escalier en spirale gauche dvergr",\n  "$piece_dvergr_spiralstair_right": "Escalier en spirale droit dvergr",\n  "$piece_dvergr_stake_wall": "Palissade dvergr",\n  "$piece_dvergr_woodwall": "Mur dvergr",\n  "$piece_dvergrchest": "Coffre au trésor dvergr",\n  "$piece_eitrrefinery": "Raffinerie d\'Eitr",\n  "$piece_faderember": "Bûcher éternel",\n  "$piece_faderember_full": "Les braises brûlent de mille feux",\n  "$piece_faderember_light": "Les braises reprennent feu",\n  "$piece_faderember_nospace": "Les braises sont suffocantes",\n  "$piece_faderember_ok": "Les braises reprennent feu",\n  "$piece_fairylightgarland": "Lumières féériques",\n  "$piece_fermenter": "Fermenteur",\n  "$piece_fermenter_add": "Ajouter l\'objet",\n  "$piece_fermenter_exposed": "Trop exposé",\n  "$piece_fermenter_fermenting": "Fermentation",\n  "$piece_fermenter_needroof": "Nécessite un toit",\n  "$piece_fermenter_ready": "Terminé",\n  "$piece_fermenter_tap": "Robinet",\n  "$piece_fire": "Feu",\n  "$piece_fire_fuel": "Combustible",\n  "$piece_firepit": "Feu de camp",\n  "$piece_firepit_iron": "Brasero en fer",\n  "$piece_flametal_beam": "Poutre en flametal",\n  "$piece_flametal_pillar": "Pilier en flametal",\n  "$piece_flametalbarstack": "Tas de flametal",\n  "$piece_flametalgate": "Portail en flametal",\n  "$piece_flintpile": "Tas de silex",\n  "$piece_forge": "Forge",\n  "$piece_forge_ext1": "Soufflet de forge",\n  "$piece_forge_ext2": "Enclumes",\n  "$piece_forge_ext3": "Meule",\n  "$piece_forge_ext4": "Enclume de forgeron",\n  "$piece_forge_ext5": "Seau de forge",\n  "$piece_forge_ext6": "Râtelier de forge",\n  "$piece_frostfoundry": "Fonderie à givre",\n  "$piece_frostfoundry_additem": "Placer le moulage",\n  "$piece_frostfoundry_takeitem": "Prendre l\'objet",\n  "$piece_frostkiln": "Four frigide",\n  "$piece_giant_bone": "Os pétrifié",\n  "$piece_giant_brain": "Tissu délicat",\n  "$piece_giant_helmet": "Armure ancienne",\n  "$piece_giant_sword": "Épée ancienne",\n  "$piece_grausten_archmedium": "Arche moyenne en grise-pierre",\n  "$piece_grausten_archsmall": "Petite arche en grise-pierre",\n  "$piece_grausten_beammedium": "Poutre moyenne en grise-pierre",\n  "$piece_grausten_beamsmall": "Petite poutre en grise-pierre",\n  "$piece_grausten_floor1x1": "Sol en grise-pierre 1x1",\n  "$piece_grausten_floor2x2": "Sol en grise-pierre 2x2",\n  "$piece_grausten_floor4x4": "Sol en grise-pierre 4x4",\n  "$piece_grausten_pillarmedium": "Pilier moyen en grise-pierre",\n  "$piece_grausten_pillarsmall": "Petit pilier en grise-pierre",\n  "$piece_grausten_pillartapered": "Pilier fuselé en grise-pierre",\n  "$piece_grausten_pillartaperedinverted": "Pilier fuselé en grise-pierre (inversé)",\n  "$piece_grausten_roof45": "Toit en grise-pierre",\n  "$piece_grausten_roof45_arch": "Arche de toit en grise-pierre",\n  "$piece_grausten_roof45_archcorner": "Coin d\'arche de toit en grise-pierre",\n  "$piece_grausten_roof45_archcorner2": "Coin d\'arche de toit en grise-pierre",\n  "$piece_grausten_roof45_corner": "Coin de toit en grise-pierre",\n  "$piece_grausten_roof45_corner2": "Coin de toit en grise-pierre",\n  "$piece_grausten_stair": "Escalier en grise-pierre",\n  "$piece_grausten_stoneladder": "Escalier raide en grise-pierre",\n  "$piece_grausten_wall1x2": "Mur en grise-pierre 1x2",\n  "$piece_grausten_wall2x2": "Mur en grise-pierre 2x2",\n  "$piece_grausten_wall4x2": "Mur en grise-pierre 4x2",\n  "$piece_grausten_wallarch": "Arche murale en grise-pierre",\n  "$piece_grausten_wallarchinv": "Arche murale inversée en grise-pierre",\n  "$piece_grausten_window2x2": "Fenêtre en grise-pierre 2x2",\n  "$piece_grausten_window4x2": "Fenêtre en grise-pierre 4x2",\n  "$piece_graustenpile": "Pile de grise-pierre",\n  "$piece_groundtorch": "Torche en fer",\n  "$piece_groundtorchblue": "Torche en fer à flamme bleue",\n  "$piece_groundtorchdemister": "Torche de feu-follet",\n  "$piece_groundtorchgreen": "Torche en fer à flamme verte",\n  "$piece_groundtorchwood": "Torche en bois",\n  "$piece_guardstone": "Balise",\n  "$piece_guardstone_activate": "Activer",\n  "$piece_guardstone_active": "Actif",\n  "$piece_guardstone_add": "Ajouter",\n  "$piece_guardstone_additional": "Autorisé",\n  "$piece_guardstone_deactivate": "Désactiver",\n  "$piece_guardstone_inactive": "Inactif",\n  "$piece_guardstone_owner": "Propriétaire",\n  "$piece_guardstone_remove": "Retirer",\n  "$piece_hanging_cloth_blue1": "Tentures de jute bleue",\n  "$piece_hanging_cloth_blue2": "Rideau de jute bleue",\n  "$piece_harvest": "Récolter",\n  "$piece_hearth": "Foyer",\n  "$piece_hexagonalgate": "Porte hexagonale",\n  "$piece_hoodedlantern": "Lanterne couverte",\n  "$piece_horizontal": "Horizontal",\n  "$piece_icecube": "Bloc de glace",\n  "$piece_incinerator": "Oblitérateur",\n  "$piece_incinerator_conversion": "Thor vous octroie un cadeau !",\n  "$piece_incinerator_empty": "Thor vous regarde d\'un mauvais œil",\n  "$piece_incinerator_fail": "L\'oblitérateur est en service",\n  "$piece_incinerator_success": "Objets oblitérés !",\n  "$piece_ironbarstack": "Tas de fer",\n  "$piece_ironfloor": "Sol de cage 2x2",\n  "$piece_ironfloorSmall": "Sol de cage 1x1",\n  "$piece_irongate": "Portail de fer",\n  "$piece_ironwall": "Mur de cage 2x2",\n  "$piece_ironwallSmall": "Mur de cage 1x1",\n  "$piece_ironwoodbeam67": "Poutre de fer et bois 67°",\n  "$piece_itemstand": "Présentoir",\n  "$piece_itemstand_attach": "Attacher l\'objet",\n  "$piece_itemstand_cantattach": "Vous ne pouvez pas attacher cet objet",\n  "$piece_itemstand_missingitem": "Objet requis manquant",\n  "$piece_itemstand_take": "Prendre l\'objet",\n  "$piece_jackoturnip": "Lanterne d\'Halloween",\n  "$piece_jotunchest": "Coffre des jötnars",\n  "$piece_jotungate": "Portes de Mörkhalla",\n  "$piece_jute_carpet": "Tapis de jute rouge",\n  "$piece_juteblue_carpet": "Tapis de jute bleue",\n  "$piece_lavalantern": "Lanterne de lave",\n  "$piece_levelground": "Aplanir le sol",\n  "$piece_logbeam2": "Poutre en bûche 2m",\n  "$piece_logbeam4": "Poutre en bûche 4m",\n  "$piece_logpole2": "Poteau en bûche 2m",\n  "$piece_logpole4": "Poteau en bûche 4m",\n  "$piece_magetable": "Table de galdr",\n  "$piece_magetable_ext": "Table runique",\n  "$piece_magetable_ext2": "Bougies éternelles",\n  "$piece_magetable_ext3": "Couronne de plumes",\n  "$piece_magetable_ext4": "Métier à tisser",\n  "$piece_maptable_hildir": "Table de la carte d\'Hildir",\n  "$piece_maptable_hildir_use": "Enregistrer l\'emplacement des coffres",\n  "$piece_marblepile": "Pile de marbre noir",\n  "$piece_maypole": "Mât de Cocagne",\n  "$piece_meadcauldron": "Chaudron à hydromel",\n  "$piece_mistletoe": "Gui",\n  "$piece_moose_throne": "Trône de bois de cerf",\n  "$piece_morkborg_gate": "Portes de Mörkhalla",\n  "$piece_morkhallachestancient": "Coffre ancien",\n  "$piece_mudpile": "Tas de boue",\n  "$piece_noaccess": "Inaccessible",\n  "$piece_obsidianpile": "Tas d\'obsidienne",\n  "$piece_offerbowl_bonemass": "Mort bouillonnante",\n  "$piece_offerbowl_eikthyr": "Autel mystique",\n  "$piece_offerbowl_fader": "Autel de la Flamme d\'émeraude",\n  "$piece_offerbowl_frozenking": "Bol étrange",\n  "$piece_offerbowl_hive": "Siège de l\'essaim",\n  "$piece_offerbowl_makeoffer": "Faire une offrande",\n  "$piece_offerbowl_memorial": "Ancien autel",\n  "$piece_offerbowl_offeritem": "Offrir l\'objet",\n  "$piece_offerbowl_offeritem_fader": "Sonner les cloches",\n  "$piece_offerbowl_offeritem_memorial": "Allumer l\'autel",\n  "$piece_offerbowl_yagluth": "Autel mystique",\n  "$piece_oven": "Four en pierre",\n  "$piece_oven_additem": "Cuire l’objet",\n  "$piece_path": "Déblayer",\n  "$piece_pavedroad": "Route pavée",\n  "$piece_plant_healthy": "Sain",\n  "$piece_plant_nospace": "Nécessite davantage d\'espace pour pousser",\n  "$piece_plant_nosun": "Doit être à ciel ouvert",\n  "$piece_plant_notcultivated": "Le sol doit être cultivé",\n  "$piece_plant_nowall": "Nécessite un mur proche",\n  "$piece_plant_toocold": "Trop froid",\n  "$piece_plant_toohot": "Trop chaud",\n  "$piece_plant_wrongbiome": "Ne peut pousser dans cet environnement",\n  "$piece_portal": "Portail",\n  "$piece_portal_censored_warning": "Des mots interdits ont été trouvés, ce qui pourrait poser problème pour le jeu inter-plateforme.",\n  "$piece_portal_connected": "CONNECTÉ",\n  "$piece_portal_settag": "Établir le repère",\n  "$piece_portal_stone": "Portal – Pierre",\n  "$piece_portal_tag": "Repère",\n  "$piece_portal_unconnected": "NON CONNECTÉ",\n  "$piece_pot_large_cracked": "Grand pot en terre cuite",\n  "$piece_pot_large_green": "Grand pot vert",\n  "$piece_pot_large_red": "Grand pot rouge",\n  "$piece_pot_medium_cracked": "Pot en terre cuite moyen",\n  "$piece_pot_medium_green": "Pot vert moyen",\n  "$piece_pot_medium_red": "Pot rouge moyen",\n  "$piece_pot_small_cracked": "Petit pot en terre cuite",\n  "$piece_pot_small_green": "Petit pot vert",\n  "$piece_pot_small_red": "Petit pot rouge",\n  "$piece_preptable": "Table de préparation culinaire",\n  "$piece_pulllever": "Tirer le levier",\n  "$piece_queendoor": "Chambre forte dvergr",\n  "$piece_raise": "Rehausser le sol",\n  "$piece_readmap": "Lire la carte",\n  "$piece_register_location": "Enregistrer le lieu",\n  "$piece_repair": "Réparer",\n  "$piece_replant": "Herbe",\n  "$piece_rock_01": "Rocher ornemental",\n  "$piece_rock_02": "Rocher décoratif",\n  "$piece_rug_asksvin": "Tapis en asksvin",\n  "$piece_rug_bjorn": "Tapis en peau d\'ours",\n  "$piece_rug_deer": "Tapis de cerf",\n  "$piece_rug_hare": "Tapis de lièvre",\n  "$piece_rug_lox": "Tapis de Lox",\n  "$piece_rug_moose": "Tapis en peau d\'élan",\n  "$piece_rug_seal": "Tapis en peau de phoque",\n  "$piece_rug_straw": "Paille",\n  "$piece_rug_wolf": "Tapis de loup",\n  "$piece_rune_read": "Lire",\n  "$piece_sapcollector": "Extracteur de sève",\n  "$piece_sapcollector_draining": "Extraction",\n  "$piece_sapcollector_drainingslow": "Extraction lente",\n  "$piece_sapcollector_extract": "Collecter",\n  "$piece_sapcollector_isfull": "Plein",\n  "$piece_sapcollector_notconnected": "Rien à extraire",\n  "$piece_sapling_barley": "Orge",\n  "$piece_sapling_carrot": "Carotte",\n  "$piece_sapling_flax": "Lin",\n  "$piece_sapling_jotunpuffs": "Primordium de globes jötnar",\n  "$piece_sapling_kale": "Chou kale",\n  "$piece_sapling_magecap": "Primordium de coiffe-de-mage",\n  "$piece_sapling_oat": "Paille d\'avoine",\n  "$piece_sapling_onion": "Oignon",\n  "$piece_sapling_poteitr": "Poteitr",\n  "$piece_sapling_seedcarrot": "Graine de carotte",\n  "$piece_sapling_seedkale": "Graine de chou kale",\n  "$piece_sapling_seedonion": "Pousse d\'oignon",\n  "$piece_sapling_seedturnip": "Graine de navet",\n  "$piece_sapling_turnip": "Navet",\n  "$piece_sapling_vineash": "Lierre des cendres",\n  "$piece_sapling_vinegreen": "Lierre",\n  "$piece_scale_26": "Mur en boidécaille 26° gauche",\n  "$piece_scale_26_flipped": "Mur en boidécaille 26° droite",\n  "$piece_scale_26_upsidedown": "Mur en boidécaille 26° droite (inversé)",\n  "$piece_scale_26_upsidedown_flipped": "Mur en boidécaille 26° gauche (inversé)",\n  "$piece_scale_45": "Mur en boidécaille 45° gauche",\n  "$piece_scale_45_flipped": "Mur en boidécaille 45° droite",\n  "$piece_scale_45_upsidedown": "Mur en boidécaille 45° droite (inversé)",\n  "$piece_scale_45_upsidedown_flipped": "Mur en boidécaille 45° gauche (inversé)",\n  "$piece_scale_67": "Mur en boidécaille 67° gauche",\n  "$piece_scale_67_flipped": "Mur en boidécaille 67° droite",\n  "$piece_scale_67_upsidedown": "Mur en boidécaille 67° droite (inversé)",\n  "$piece_scale_67_upsidedown_flipped": "Mur en boidécaille 67° gauche (inversé)",\n  "$piece_scale_halfwall": "Demi-mur en boidécaille",\n  "$piece_scale_quarterwall": "Quart de mur en boidécaille",\n  "$piece_scale_wall": "Mur en boidécaille",\n  "$piece_sconce": "Chandelier",\n  "$piece_secretdoor": "Porte cachée",\n  "$piece_sharpstakes": "Pieux acérés",\n  "$piece_shieldgenerator": "Générateur de bouclier",\n  "$piece_shieldgenerator_add": "Ajouter des os",\n  "$piece_shieldgenerator_charging": "Chargement",\n  "$piece_shieldgenerator_fuelname": "os",\n  "$piece_shieldgenerator_ready": "Chargé et prêt",\n  "$piece_shieldgenerator_use": "Activer",\n  "$piece_shieldgenerator_waiting": "Nécessite du carburant",\n  "$piece_ship_ladder": "Échelle",\n  "$piece_ship_rudder": "Utiliser le gouvernail",\n  "$piece_sign": "Pancarte",\n  "$piece_sign_input": "Entrez du texte",\n  "$piece_silverbarstack": "Tas d\'argent",\n  "$piece_skullpile": "Tas de crânes",\n  "$piece_smelter": "Fonderie",\n  "$piece_smelter_add": "Ajouter",\n  "$piece_smelter_additem": "Ajouter l\'objet",\n  "$piece_smelter_empty": "Vide",\n  "$piece_smelter_ready": "Transformé",\n  "$piece_smelter_reqroof": "Nécessite un toit",\n  "$piece_snowlantern": "Lanterne de neige",\n  "$piece_spinningwheel": "Roue",\n  "$piece_stakewall": "Palissade",\n  "$piece_stave_deco_beam_2m": "Poutre en bois décoré 2 m",\n  "$piece_stave_deco_pole_2m": "Poteau en bois décoré 2 m",\n  "$piece_stave_pole_2m": "Poteau en bois 2 m",\n  "$piece_stave_pole_4m": "Poteau en bois 4 m",\n  "$piece_stave_wall": "Mur en bois",\n  "$piece_stavebeam2": "Poutre en bois 2 m",\n  "$piece_stavebeam26": "Poutre en bois 26°",\n  "$piece_stavebeam4": "Poutre en bois 4 m",\n  "$piece_stavebeam45": "Poutre en bois 45°",\n  "$piece_stavebeam67": "Poutre en bois 67°",\n  "$piece_stavecross26": "Croix de toit en bois 26°",\n  "$piece_stavecross45": "Croix de toit en bois 45°",\n  "$piece_stavedecobeam26": "Poutre en bois décoré 26°",\n  "$piece_stavedecobeam45": "Poutre en bois décoré 45°",\n  "$piece_stavedecobeam67": "Poutre en bois décoré 67°",\n  "$piece_stavegate": "Portail de sapin nordique",\n  "$piece_stavewallrooftop67": "Croix de toit en bois 67°",\n  "$piece_stonearch": "Arche de pierre",\n  "$piece_stonecutter": "Tailleur de pierre",\n  "$piece_stonefence": "Clôture en pierre",\n  "$piece_stonefloor2x2": "Sol de pierre 2x2",\n  "$piece_stonefloor4x4": "Sol de pierre 4x4",\n  "$piece_stonepile": "Pile de pierre",\n  "$piece_stonepillar": "Pilier de pierre",\n  "$piece_stonestair": "Escalier de pierre",\n  "$piece_stonethrone": "Trône en pierre",\n  "$piece_stonewall1x1": "Mur de pierre 1x1",\n  "$piece_stonewall2x1": "Mur de pierre 2x1",\n  "$piece_stonewall4x2": "Mur de pierre 4x2",\n  "$piece_stool": "Tabouret",\n  "$piece_table": "Table",\n  "$piece_table_oak": "Longue table lourde",\n  "$piece_table_round": "Table ronde",\n  "$piece_table_runed": "Longue table sculptée",\n  "$piece_table_runed_small": "Table carrée sculptée",\n  "$piece_tarpile": "Baril de goudron",\n  "$piece_throne01": "Trône corvidé",\n  "$piece_tinbarstack": "Tas d\'étain",\n  "$piece_tombstone": "Ci-gît",\n  "$piece_tombstone_container": "Tombe",\n  "$piece_tombstone_recovered": "Objets récupérés",\n  "$piece_toofar": "Trop loin",\n  "$piece_trainingdummy": "Frère d\'armes",\n  "$piece_trap": "Piège",\n  "$piece_trap_arm": "Armer le piège",\n  "$piece_trap_armed": "Armé",\n  "$piece_trap_cooldown": "Le piège à trolls n\'est pas encore prêt.",\n  "$piece_treasure_pile": "Tas de pièces",\n  "$piece_treasure_stack": "Pile de pièces",\n  "$piece_turret": "Baliste",\n  "$piece_turret_addammo": "Ajouter un projectile",\n  "$piece_turret_armed": "Chargée et prête",\n  "$piece_turret_noammo": "Pas de projectile",\n  "$piece_turret_target": "Cible :",\n  "$piece_turret_target_everything": "tout",\n  "$piece_turret_target_set": "Définir une cible avec un trophée",\n  "$piece_turret_target_set_msg": "Cibles de baliste",\n  "$piece_UnstableMine": "Mine instable",\n  "$piece_upgrade": "amélioration",\n  "$piece_upgradestation": "Forge du potentiel",\n  "$piece_use": "Utiliser",\n  "$piece_useitem": "Utiliser l\'objet",\n  "$piece_vegvisir": "Vegvisir",\n  "$piece_vertical": "Vertical",\n  "$piece_windmill": "Moulin",\n  "$piece_wisplure": "Fontaine aux feux-follets",\n  "$piece_wisplure_full": "Les feux-follets dansent.",\n  "$piece_wisplure_light": "Les feux-follets réclament l\'obscurité.",\n  "$piece_wisplure_nospace": "Les feux-follets veulent plus d\'espace.",\n  "$piece_wisplure_ok": "Les feux-follets arrivent.",\n  "$piece_woodbeam1": "Poutre en bois 1m",\n  "$piece_woodbeam2": "Poutre en bois 2m",\n  "$piece_woodbeam26": "Poutre en bois 26°",\n  "$piece_woodbeam45": "Poutre en bois 45°",\n  "$piece_woodbeam67": "Poutre en bois 67°",\n  "$piece_woodcorestack": "Pile de bois robuste",\n  "$piece_wooddoor": "Porte en bois",\n  "$piece_wooddragon": "Dragon décoratif en bois",\n  "$piece_woodfence": "Clôture de bûches",\n  "$piece_woodfencegate": "Portail de bûches",\n  "$piece_woodfinestack": "Pile de bois précieux",\n  "$piece_woodfloor1x1": "Plancher 1x1",\n  "$piece_woodfloor2x2": "Plancher 2x2",\n  "$piece_woodfroststack": "Tas de sapin nordique",\n  "$piece_woodgate": "Portail en bois",\n  "$piece_woodironbeam": "Poutre de fer et bois",\n  "$piece_woodironbeam_26": "Poutre de fer et bois 26°",\n  "$piece_woodironbeam_45": "Poutre de fer et bois 45°",\n  "$piece_woodironpole": "Poteau de fer et bois",\n  "$piece_woodledge": "Corniche en bois",\n  "$piece_woodlog26": "Poutre en bûche 26°",\n  "$piece_woodlog45": "Poutre en bûche 45°",\n  "$piece_woodlog67": "Poutre en bûche 67°",\n  "$piece_woodpole": "Poteau en bois 1m",\n  "$piece_woodpole2": "Poteau en bois 2m",\n  "$piece_woodroof26": "Toit de chaume 26°",\n  "$piece_woodroof45": "Toit de chaume 45°",\n  "$piece_woodroof67": "Toit de chaume 67°",\n  "$piece_woodrooficorner": "Toit de chaume 26° concave",\n  "$piece_woodrooficorner45": "Toit de chaume 45° concave",\n  "$piece_woodrooficorner67": "Toit de chaume 67° concave",\n  "$piece_woodroofocorner": "Toit de chaume 26° convexe",\n  "$piece_woodroofocorner45": "Toit de chaume 45° convexe",\n  "$piece_woodroofocorner67": "Toit de chaume 67° convexe",\n  "$piece_woodrooftop": "Faîte de toit de chaume 26°",\n  "$piece_woodrooftop45": "Faîte de toit de chaume 45°",\n  "$piece_woodrooftop67": "Faîte de toit de chaume 67°",\n  "$piece_woodstack": "Tas de bois",\n  "$piece_woodstair": "Escalier en bois",\n  "$piece_woodstepladder": "Échelle en bois",\n  "$piece_woodwall": "Mur en bois",\n  "$piece_woodwallhalf": "Demi-mur en bois",\n  "$piece_woodwallquarter": "Mur en bois 1x1",\n  "$piece_woodwallroof": "Mur en bois 26°",\n  "$piece_woodwallroof_upsidedown": "Mur en bois 26° (inversé)",\n  "$piece_woodwallroof45": "Mur en bois 45°",\n  "$piece_woodwallroof45_upsidedown": "Mur en bois 45° (inversé)",\n  "$piece_woodwallroof67": "Mur en bois 67°",\n  "$piece_woodwallroof67upsidedown": "Mur en bois 67° (inversé)",\n  "$piece_woodwallrooftop": "Croix de toit en bois 26°",\n  "$piece_woodwallrooftop45": "Croix de toit en bois 45°",\n  "$piece_woodwallrooftop67": "Croix de toit en bois 67°",\n  "$piece_woodwindowshutter": "Volet en bois",\n  "$piece_workbench": "Table de fabrication",\n  "$piece_workbench_ext1": "Billot",\n  "$piece_workbench_ext2": "Support de tannage",\n  "$piece_workbench_ext3": "Herminette",\n  "$piece_workbench_ext4": "Étagère à outils",\n  "$piece_writemap": "Enregistrer les découvertes",\n  "$piece_yggdrasilstack": "Pile de bois d\'Yggdrasil",\n  "$piece_yulecrown": "Couronne de fête",\n  "$piece_yulegarland": "Guirlande de fête",\n  "$piece_yuleklapp": "Yuleklapp",\n  "$piece_yuletree": "Arbre de fête",\n  "$ship_ashlandocean_warning": "Les eaux bouillonnantes rongent votre coque, faites demi-tour !",\n  "$ship_cargo": "Cargaison",\n  "$ship_holdfast": "Maintenir",\n  "$ship_karve": "Karv",\n  "$ship_longship": "Long navire",\n  "$ship_longship_ashlands": "Drakkar",\n  "$ship_raft": "Radeau",\n  "$tool_batteringram": "Bélier",\n  "$tool_cart": "Charrette",\n  "$tool_catapult": "Catapulte"\n}\n'
@_fr_cache(maxsize=1)
def french_names():
    result = {}
    for key, value in _fr_json.loads(_FR_NAMES_SOURCE).items():
        if isinstance(key, str) and key.startswith('


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
) and isinstance(value, str):
            cleaned = _fr_html.unescape(_fr_re.sub(r'</?(?:color|b|i|size)(?:=[^>]*)?>', '', value, flags=_fr_re.I)).replace('\u00a0', ' ').strip()
            if cleaned and not cleaned.startswith('


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
) and len(cleaned) <= 140:
                result[key.casefold()] = cleaned
    return result

def localized_name(token, fallback=None):
    if not isinstance(token, str):
        return fallback or str(token)
    return french_names().get(token.casefold(), fallback if fallback is not None else token)



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
