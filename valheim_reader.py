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
) + tuple(AchievementSpec(key, title, category, description, tuple(), kind='not_calculable',
       note='Il manque la liste exacte des objets/créatures ou le statut de succès du jeu pour une vérification sans faux positifs.')
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
    if spec.kind in ('boss', 'boss_single', 'miniboss'):
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
