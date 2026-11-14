"""Valheim Stats Tracker V1.4 — application de bureau sans mod (stdlib Python)."""
import csv
import webbrowser
import hashlib
import json
import os
import queue
import sqlite3
import sys
import threading
import zlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import updater

from valheim_reader import (localized_name, BOSSES, DEATH_KINDS, GROUPS, STAT_INDEX, SaveError,
                            PLAYER_STAT_NAMES, SPECS, evaluate_all, evaluate_one, progress_delta,
                            defeated_bosses, decode, metrics, pretty_key,
                            total_kills)

APP_NAME = 'Valheim Stats Tracker'

# Palette plus moderne et lisible.
BG = '#0b1220'
BG_ALT = '#0f1729'
SIDEBAR = '#111b2f'
PANEL = '#131f35'
PANEL_SOFT = '#182742'
PANEL_STRONG = '#1d3152'
BORDER = '#243a61'
FG = '#f3f7ff'
MUTED = '#9fb2cf'
ACCENT = '#66c5ff'
ACCENT2 = '#7ee0c1'
GREEN = '#63e3a4'
GOLD = '#f6cf72'
RED = '#f38b8d'
ORANGE = '#ffb66d'

GROUP_FR = {
    'RawStats': 'Brut (tous)', 'Any': 'Toutes difficultés', 'Default': 'Normal ou +',
    'Hard': 'Difficile ou +', 'VeryHard': 'Très difficile ou +',
    'Hardcore': 'Extrême', 'Casual': 'Détendu ou +', 'VeryEasy': 'Très facile ou +',
    'Easy': 'Facile ou +', 'Hammer': 'Marteau',
}
SECTIONS = {
    'Objets fabriqués': 'crafted',
    'Objets ramassés': 'picked_up',
    'Ressources collectées': 'pickables',
    'Éléments placés': 'pieces_built',
    'Nourritures consommées': 'foods_eaten',
}
SECTION_BADGES = {
    'crafted': 'Fabrication',
    'picked_up': 'Ramassage',
    'pickables': 'Récolte',
    'pieces_built': 'Construction',
    'foods_eaten': 'Cuisine',
}
METRICS = {
    'Créatures tuées': 'kills',
    'Décès': 'deaths',
    'Boss différents': 'bosses',
    'Objets fabriqués': 'crafted',
    'Éléments placés': 'built',
    'Objets ramassés': 'picked_up',
    'Temps de jeu (h)': 'world_hours',
    'Magie élémentaire (niveau)': 'skill:Magie élémentaire',
    'Magie du sang (niveau)': 'skill:Magie du sang',
    'Poings (niveau)': 'skill:Poings',
    'Course (niveau)': 'skill:Course',
    'Épées (niveau)': 'skill:Épées',
}
CHART_PERIODS = {
    'Tous les relevés': None,
    '7 derniers jours': 7,
    '30 derniers jours': 30,
    '90 derniers jours': 90,
}
NAV_ITEMS = [
    'Centre de progression', 'Vue d’ensemble', 'Succès', 'Boss', 'Combats', 'Activités', 'Compétences', 'Historique', 'Compteurs bruts'
]

CATEGORY_RULES = [
    ('Bois / arbres', ('tree', 'wood', 'log', 'branch', 'beech', 'birch', 'oak', 'pine', 'fir', 'finewood', 'roundlog', 'ancientbark', 'yggdrasil', 'mangrove')),
    ('Pierre / minéraux', ('stone', 'rock', 'flint', 'obsidian', 'crystal', 'marble', 'grausten', 'grausten')),
    ('Métaux / minerais', ('copper', 'tin', 'iron', 'silver', 'bronze', 'blackmetal', 'flametal', 'ore', 'scrap', 'surtlingcore')),
    ('Plantes / graines', ('seed', 'sapling', 'barley', 'flax', 'turnip', 'carrot', 'onion', 'vine', 'mushroom', 'dandelion', 'thistle', 'jotunpuffs', 'magecap')),
    ('Nourriture / cuisine', ('meat', 'fish', 'berry', 'jam', 'honey', 'bread', 'salad', 'stew', 'soup', 'pie', 'pudding', 'cooked', 'egg', 'mushroom', 'turnip', 'carrot', 'onion')),
    ('Monnaie / objets rares', ('coin', 'amber', 'ruby', 'pearls', 'treasure', 'jewelry')),
    ('Mobilier / structure', ('roof', 'wall', 'floor', 'beam', 'door', 'gate', 'bed', 'chair', 'table', 'torch', 'fire', 'portal', 'workbench', 'forge', 'cauldron')),
]


def history_metric(snapshot, key, difficulty='Any'):
    """Valeur cumulative fiable d'un relevé ; les niveaux ignorent la difficulté."""
    if key.startswith('skill:'):
        return float(snapshot.get('skills', {}).get(key[6:], {}).get('level', 0))
    return metrics(snapshot, difficulty)[key]



def history_series(rows, key, difficulty='Any', period_days=None, changes=False):
    """[(timestamp, valeur, fichier)] chronologique. Variations entre deux sauvegardes."""
    ordered = sorted(rows, key=lambda row: (row[1], row[0]))
    series = []
    previous = None
    for _, timestamp, filename, snapshot in ordered:
        value = history_metric(snapshot, key, difficulty)
        delta = value - previous if previous is not None else 0
        series.append((timestamp, delta if changes else value, filename))
        previous = value
    if period_days is not None and series:
        threshold = series[-1][0] - 86400 * period_days
        series = [p for p in series if p[0] >= threshold]
    return series



def boss_matrix(parsed):
    """Comptes par difficulté (groupes imbriqués, jamais additionnés)."""
    matrix = {}
    for token, name in BOSSES.items():
        row = {'name': name}
        for group in ('Any', 'Default', 'Hard', 'VeryHard', 'Hardcore'):
            enemies = parsed['groups'][group]['enemies']
            row[group] = int(round(enemies[0].get(token, 0)))
            row[group + '_unarmed'] = int(round(enemies[1].get(token, 0)))
        matrix[token] = row
    return matrix



def boss_progress(parsed, group='Default'):
    return sum(row[group] > 0 for row in boss_matrix(parsed).values())



def app_dir():
    root = Path(os.getenv('LOCALAPPDATA') or (Path.home() / '.local' / 'share')) / 'ValheimStatsTracker'
    root.mkdir(parents=True, exist_ok=True)
    return root



def default_save():
    matches = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as reg:
            steam = Path(winreg.QueryValueEx(reg, 'SteamPath')[0])
        matches.extend(steam.glob('userdata/*/892970/remote/characters/*.fch'))
    except (ImportError, OSError, ValueError):
        pass
    matches.extend((Path.home() / 'AppData/LocalLow/IronGate/Valheim/characters_local').glob('*.fch'))
    matches = [p for p in matches if '_backup' not in p.name.lower() and p.is_file()]
    if matches:
        return str(max(matches, key=lambda p: p.stat().st_mtime))
    return ''



def db_open():
    db = sqlite3.connect(app_dir() / 'historique.sqlite3')
    db.execute('''CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character TEXT NOT NULL,
        sha TEXT NOT NULL,
        observed_at REAL NOT NULL,
        filename TEXT NOT NULL,
        data BLOB NOT NULL,
        UNIQUE(character,sha)
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS ix_snap_character ON snapshots(character,observed_at)')
    db.commit()
    return db



def sample_rows(db, character):
    return [
        (n, t, f, json.loads(zlib.decompress(data)))
        for n, t, f, data in db.execute(
            'SELECT id,observed_at,filename,data FROM snapshots WHERE character=? ORDER BY observed_at, id',
            (character,),
        )
    ]



def fmt(v):
    if isinstance(v, float) and not v.is_integer():
        return f'{v:,.1f}'.replace(',', ' ').replace('.', ',')
    return f'{int(v):,}'.replace(',', ' ')




# V1.9 — fonctions de progression indépendantes de l'interface graphique.
# Les validations sont des estimations issues du fichier .fch, jamais des badges Steam.

def pending_actions(result, limit=5):
    """Critères manquants prioritaires, en conservant les noms français."""
    if not result.get('measurable') or result.get('complete'):
        return []
    pending = [part for part in result.get('parts', ())
               if not part.get('complete') and part.get('goal') is not None]
    pending.sort(key=lambda part: (
        max(0.0, float(part.get('remaining', 0))) / max(1.0, float(part['goal'])),
        str(part.get('label', '')).casefold()))
    return [
        {'label': part['label'], 'remaining': max(0, float(part.get('remaining', 0))),
         'goal': float(part['goal']), 'current': float(part.get('current', 0))}
        for part in pending[:max(0, int(limit))]
    ]


def progress_ranking(results, favorites=(), limit=None):
    """Priorise l'avancement réel, sans déclarer terminés les succès internes."""
    favorite_set = set(favorites)
    ranked = [row for row in results if row.get('measurable') and not row.get('complete')
              and row.get('fraction') is not None]
    ranked.sort(key=lambda row: (
        -float(row.get('fraction', 0)),
        -int(row.get('completed_conditions', 0)),
        row.get('title', '').casefold()))
    if limit is not None:
        ranked = ranked[:max(0, int(limit))]
    return [{**row, 'favorite': row['key'] in favorite_set} for row in ranked]


def load_favorites(character, directory=None):
    """Favoris par personnage dans %LOCALAPPDATA%, sans toucher à .fch ni SQLite."""
    path = (Path(directory) if directory is not None else app_dir()) / 'favoris.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        saved = data.get('characters', {}).get(character, [])
        if isinstance(saved, list):
            valid = {spec.key for spec in SPECS}
            return {x for x in saved if isinstance(x, str) and x in valid}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return set()


def save_favorites(character, selected, directory=None):
    root = Path(directory) if directory is not None else app_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'favoris.json'
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            obj = {}
    except (OSError, ValueError, TypeError):
        obj = {}
    characters = obj.get('characters')
    if not isinstance(characters, dict):
        characters = {}
    known = {spec.key for spec in SPECS}
    characters[str(character)] = sorted(x for x in selected if x in known)
    obj['characters'] = characters
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


SESSION_METRICS = (
    ('Ennemis vaincus', 'kills'),
    ('Décès', 'deaths'),
    ('Fabrications', 'crafted'),
    ('Constructions', 'built'),
    ('Objets ramassés', 'picked_up'),
    ('Arbres abattus', 'Tree'),
    ('Récoltes cultivées', 'HarvestCrop'),
    ('Miel récolté', 'BeesHarvested'),
)


def _saved_counter(profile, key):
    if key in ('kills', 'deaths', 'crafted', 'built', 'picked_up'):
        return float(metrics(profile, 'Any')[key])
    idx = STAT_INDEX.get(key)
    if idx is None:
        return None
    return float(profile['groups']['Any']['stats'][idx])


def estimate_last_session(rows, gap_minutes=90):
    """Bilan entre relevés d'une séquence présumée ; aucune heure de connexion inventée.

    rows est la sortie sample_rows() : (id, timestamp, nom_fichier, données).
    Un seul relevé de la séquence ne prouve aucun gain pendant cette session.
    """
    if not rows:
        return {'available': False, 'reason': 'Aucun relevé enregistré.'}
    ordered = sorted(rows, key=lambda item: (item[1], item[0]))
    end = len(ordered) - 1
    start = end
    while start and ordered[start][1] - ordered[start - 1][1] <= gap_minutes * 60:
        start -= 1
    segment = ordered[start:]
    if len(segment) < 2:
        return {
            'available': False,
            'reason': 'Un seul relevé dans la session estimée : il faut au moins deux sauvegardes.',
            'start': segment[0][1], 'end': segment[-1][1], 'samples': len(segment),
        }
    first, last = segment[0], segment[-1]
    delta = {}
    resets = []
    for label, key in SESSION_METRICS:
        left, right = _saved_counter(first[3], key), _saved_counter(last[3], key)
        if left is None or right is None:
            continue
        diff = right - left
        if diff < -0.001:
            resets.append(label)
            continue
        delta[label] = max(0, diff)
    skills = []
    for label, now in last[3].get('skills', {}).items():
        prior = first[3].get('skills', {}).get(label)
        if prior:
            gain = float(now['level']) - float(prior['level'])
            if gain > .0001:
                skills.append((label, gain))
    skills.sort(key=lambda pair: (-pair[1], pair[0]))
    before = {a['key']: a for a in evaluate_all(first[3]) if a['measurable']}
    after = [a for a in evaluate_all(last[3]) if a['measurable']]
    unlocked = [a['title'] for a in after if a['complete'] and
                a['key'] in before and not before[a['key']]['complete']]
    time_start = sum(first[3]['groups']['RawStats']['worlds'].values())
    time_end = sum(last[3]['groups']['RawStats']['worlds'].values())
    return {
        'available': True,
        'start': first[1], 'end': last[1], 'samples': len(segment),
        'minutes_played': max(0, (time_end - time_start) / 60),
        'changes': delta, 'skills': skills[:5],
        'new_goals': unlocked, 'resets': resets,
        'note': 'Session estimée par un écart maximal de %s min entre sauvegardes. '
                'Les heures de connexion exactes ne sont pas connues.' % gap_minutes,
    }


def lbl(parent, text, size=11, color=FG, bold=False, **kw):
    return tk.Label(parent, text=text, fg=color, bg=parent.cget('bg'), font=('Segoe UI', size, 'bold' if bold else 'normal'), **kw)



def normalize_token(token):
    return token.lower().replace('$', '').replace('_', ' ')



def clean_name(token):
    name = pretty_key(token)
    replacements = {
        'Gdking': 'Ancien',
        'Frozenking P3': 'Kall Fimbulbringer',
        'Pickable': '',
        'Piece': '',
        'Enemy': '',
        'Item': '',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return localized_name(token, ' '.join(name.split()))



def classify_entry(token, section):
    if section == 'pieces_built':
        return 'Construction'
    if section == 'foods_eaten':
        return 'Nourriture / cuisine'
    flat = normalize_token(token)
    for label, keywords in CATEGORY_RULES:
        if any(word in flat for word in keywords):
            return label
    return SECTION_BADGES.get(section, 'Divers')



def build_activity_rows(parsed, group, section, term=''):
    data = parsed['groups'][group][section]
    term = term.strip().lower()
    rows = []
    for token, qty in sorted(data.items(), key=lambda x: (-x[1], pretty_key(x[0]).lower())):
        label = clean_name(token)
        category = classify_entry(token, section)
        if term and term not in label.lower() and term not in token.lower() and term not in category.lower():
            continue
        rows.append({'category': category, 'label': label, 'value': int(round(qty)), 'token': token})
    return rows



def summarize_categories(rows):
    totals = defaultdict(int)
    for row in rows:
        totals[row['category']] += row['value']
    total_all = sum(totals.values())
    summary = []
    for name, value in sorted(totals.items(), key=lambda x: (-x[1], x[0])):
        pct = 100 * value / total_all if total_all else 0
        summary.append((name, value, pct))
    return summary



def activity_highlights(rows):
    total_quantity = sum(row['value'] for row in rows)
    top = rows[0] if rows else None
    cats = summarize_categories(rows)
    dominant = cats[0][0] if cats else '—'
    return {
        'types': len(rows),
        'quantity': total_quantity,
        'top_name': top['label'] if top else '—',
        'top_value': top['value'] if top else 0,
        'dominant': dominant,
        'dominant_value': cats[0][1] if cats else 0,
    }


class TrackerApp(tk.Tk):
    def __init__(self, initial=''):
        super().__init__()
        self.title(f'Valheim Stats Tracker • V{updater.current_version()}')
        self.geometry('1400x900')
        self.minsize(1120, 720)
        self.configure(bg=BG)
        self.db = db_open()
        self.path = ''
        self.current = None
        self.current_digest = ''
        self.file_stamp = None
        self.old = None
        self.page_var = tk.StringVar(value='Centre de progression')
        self.group = tk.StringVar(value='Any')
        self.group_display = tk.StringVar(value=GROUP_FR['Any'])
        self.search_combat = tk.StringVar()
        self.search_activity = tk.StringVar()
        self.search_raw = tk.StringVar()
        self.achievement_search = tk.StringVar()
        self.achievement_detail_search = tk.StringVar()
        self.achievement_filter = tk.StringVar(value='Tous')
        self.achievement_category = tk.StringVar(value='Toutes les catégories')
        self.achievement_origin = tk.StringVar(value='Jeu + Steam + internes')
        self.achievement_selected = 'lumberjack'
        self.achievement_results = []
        self.progress_filter = tk.StringVar(value='Plus proches')
        self.progress_selected = ''
        self.progress_favorites = set()
        self.achievement_previous = {}
        self.achievement_detail_limit = 65
        self.activity = tk.StringVar(value='Ressources collectées')
        self.metric = tk.StringVar(value='Créatures tuées')
        self.history_group = tk.StringVar(value='Any')
        self.history_group_display = tk.StringVar(value=GROUP_FR['Any'])
        self.history_period = tk.StringVar(value='Tous les relevés')
        self.history_mode = tk.StringVar(value='Total cumulé')
        self.boss_difficulty = tk.StringVar(value='Default')
        self.boss_difficulty_display = tk.StringVar(value=GROUP_FR['Default'])
        self._history_points = []
        self.status = tk.StringVar(value='Choisis une sauvegarde pour commencer.')
        self.refresh_notice = tk.StringVar(value='Lecture automatique des sauvegardes toutes les 5 secondes.')
        self.sidebar_player = tk.StringVar(value='Aucun personnage')
        self.sidebar_subtitle = tk.StringVar(value='Aucune sauvegarde chargée')
        self.quick_time = tk.StringVar(value='—')
        self.quick_world = tk.StringVar(value='—')
        self.update_events = queue.Queue()
        self.update_window = None
        self.update_manifest = None
        self.update_busy = False
        self.updater_notice = tk.StringVar(value='')
        self.nav_buttons = {}
        self.pages = {}
        self._style()
        self._ui()
        for var in (self.group, self.search_combat, self.search_activity, self.search_raw, self.activity):
            var.trace_add('write', lambda *a: self.refresh())
        self.metric.trace_add('write', lambda *a: self.draw_history())
        self.history_group.trace_add('write', lambda *a: self.draw_history())
        self.history_period.trace_add('write', lambda *a: self.draw_history())
        self.history_mode.trace_add('write', lambda *a: self.draw_history())
        self.boss_difficulty.trace_add('write', lambda *a: self.refresh_bosses())
        self.group_display.trace_add('write', lambda *a: self._set_difficulty(self.group_display, self.group))
        self.history_group_display.trace_add('write', lambda *a: self._set_difficulty(self.history_group_display, self.history_group))
        self.boss_difficulty_display.trace_add('write', lambda *a: self._set_difficulty(self.boss_difficulty_display, self.boss_difficulty))
        for var in (self.achievement_search, self.achievement_filter, self.achievement_category, self.achievement_origin):
            var.trace_add('write', lambda *a: self.refresh_achievements())
        self.achievement_detail_search.trace_add('write', lambda *a: self._render_achievement_details())
        self.progress_filter.trace_add('write', lambda *a: self.refresh_progress())
        config = app_dir() / 'config.json'
        try:
            saved = json.loads(config.read_text(encoding='utf-8')).get('path', '')
        except (OSError, ValueError):
            saved = ''
        requested = initial or (saved if saved and Path(saved).is_file() else '') or default_save()
        if requested:
            self.open_file(requested)
        self.after(5000, self.poll)
        self.after(200, self._update_pump)
        self.after(2200, self._startup_update_check)
        self.protocol('WM_DELETE_WINDOW', self.close)

    @staticmethod
    def _set_difficulty(label_var, group_var):
        lookup = {label: key for key, label in GROUP_FR.items()}
        value = lookup.get(label_var.get())
        if value and group_var.get() != value:
            group_var.set(value)

    def _style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('Treeview', background=PANEL, foreground=FG, fieldbackground=PANEL,
                    font=('Segoe UI', 10), rowheight=30, borderwidth=0)
        s.configure('Treeview.Heading', background=PANEL_STRONG, foreground=FG,
                    relief='flat', font=('Segoe UI Semibold', 10))
        s.map('Treeview', background=[('selected', '#274c77')], foreground=[('selected', FG)])
        s.configure('TCombobox', fieldbackground=PANEL_SOFT, background=PANEL_SOFT,
                    foreground=FG, arrowcolor=FG, bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, padding=6)
        s.map('TCombobox', fieldbackground=[('readonly', PANEL_SOFT)], foreground=[('readonly', FG)])
        s.configure('TEntry', fieldbackground=PANEL_SOFT, foreground=FG, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, padding=6)
        s.configure('TScrollbar', background=PANEL_SOFT, troughcolor=BG_ALT)
        s.configure('Side.TButton', background=SIDEBAR, foreground=MUTED, borderwidth=0,
                    padding=(18, 12), font=('Segoe UI Semibold', 10), anchor='w')
        s.map('Side.TButton', background=[('active', PANEL_SOFT)], foreground=[('active', FG)])

    def _button(self, parent, text, command, accent=False):
        bg = ACCENT if accent else PANEL_SOFT
        fg = BG if accent else FG
        abg = '#8fd8ff' if accent else PANEL_STRONG
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=abg, activeforeground=fg, relief='flat',
                         bd=0, padx=14, pady=9, font=('Segoe UI Semibold', 10), cursor='hand2')

    def _ghost_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=SIDEBAR, fg=MUTED,
                         activebackground=PANEL_SOFT, activeforeground=FG, relief='flat', bd=0, highlightthickness=0,
                         padx=16, pady=10, font=('Segoe UI Semibold', 10), anchor='w', cursor='hand2')

    def _panel(self, parent, title=None, subtitle=None, pad=16):
        shell = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        inner = tk.Frame(shell, bg=PANEL, padx=pad, pady=pad)
        inner.pack(fill='both', expand=True)
        if title:
            lbl(inner, title, 12, FG, True).pack(anchor='w')
        if subtitle:
            lbl(inner, subtitle, 9, MUTED).pack(anchor='w', pady=(3, 10))
        return shell, inner

    def _metric_card(self, parent, title, accent=ACCENT):
        shell = tk.Frame(parent, bg=PANEL_SOFT, highlightthickness=1, highlightbackground=BORDER)
        body = tk.Frame(shell, bg=PANEL_SOFT, padx=16, pady=14)
        body.pack(fill='both', expand=True)
        lbl(body, title.upper(), 9, MUTED, True).pack(anchor='w')
        value = lbl(body, '—', 24, FG, True)
        value.pack(anchor='w', pady=(8, 0))
        hint = lbl(body, '', 9, accent)
        hint.pack(anchor='w', pady=(4, 0))
        return shell, value, hint

    def _search_field(self, parent, var, placeholder):
        row = tk.Frame(parent, bg=parent.cget('bg'))
        lbl(row, placeholder, 10, MUTED).pack(side='left', padx=(0, 10))
        ttk.Entry(row, textvariable=var, width=34).pack(side='left')
        return row

    def _mk_table(self, parent, columns, widths=None):
        area = tk.Frame(parent, bg=parent.cget('bg'))
        table = ttk.Treeview(area, columns=columns, show='headings', selectmode='browse')
        widths = widths or {}
        for col in columns:
            table.heading(col, text=col, command=lambda c=col: self._sort_table(table, c, False))
            table.column(col, width=widths.get(col, 140), anchor='w' if col == columns[0] else 'e')
        scroll = ttk.Scrollbar(area, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.tag_configure('odd', background='#172841')
        table.tag_configure('even', background=PANEL)
        table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        return area, table

    def _ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill='both', expand=True)

        self.sidebar = tk.Frame(root, bg=SIDEBAR, width=255)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(root, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)

        self._build_sidebar()
        self._build_content()
        self.show_page('Centre de progression')

    def _build_sidebar(self):
        top = tk.Frame(self.sidebar, bg=SIDEBAR, padx=18, pady=18)
        top.pack(fill='x')
        lbl(top, 'VALHEIM', 17, FG, True).pack(anchor='w')
        lbl(top, 'Stats Tracker', 15, ACCENT, True).pack(anchor='w')
        lbl(top, f'Version {updater.current_version()} • sans mod', 9, MUTED).pack(anchor='w', pady=(4, 14))

        char = tk.Frame(self.sidebar, bg=PANEL, padx=14, pady=14, highlightthickness=1, highlightbackground=BORDER)
        char.pack(fill='x', padx=14, pady=(0, 14))
        lbl(char, 'PERSONNAGE', 9, MUTED, True).pack(anchor='w')
        tk.Label(char, textvariable=self.sidebar_player, fg=FG, bg=PANEL, font=('Segoe UI Semibold', 12), anchor='w').pack(anchor='w', pady=(6, 0))
        tk.Label(char, textvariable=self.sidebar_subtitle, fg=MUTED, bg=PANEL, font=('Segoe UI', 9), anchor='w', justify='left').pack(anchor='w', pady=(3, 10))
        row = tk.Frame(char, bg=PANEL)
        row.pack(fill='x', pady=(0, 8))
        lbl(row, 'Vue de stats', 9, MUTED).pack(side='left')
        ttk.Combobox(row, textvariable=self.group_display, values=[GROUP_FR[k] for k in ('Any', 'Default', 'Hard', 'VeryHard', 'Hardcore', 'RawStats')], width=19, state='readonly').pack(side='right')
        lbl(char, 'Temps de jeu', 9, MUTED).pack(anchor='w', pady=(8, 0))
        tk.Label(char, textvariable=self.quick_time, fg=FG, bg=PANEL, font=('Segoe UI Semibold', 11)).pack(anchor='w')
        lbl(char, 'Monde principal', 9, MUTED).pack(anchor='w', pady=(8, 0))
        tk.Label(char, textvariable=self.quick_world, fg=FG, bg=PANEL, font=('Segoe UI', 10), wraplength=190, justify='left').pack(anchor='w')

        nav = tk.Frame(self.sidebar, bg=SIDEBAR, padx=10, pady=4)
        nav.pack(fill='x')
        lbl(nav, 'PAGES', 9, MUTED, True).pack(anchor='w', padx=8, pady=(0, 6))
        for name in NAV_ITEMS:
            btn = self._ghost_button(nav, name, lambda n=name: self.show_page(n))
            btn.pack(fill='x', pady=2)
            self.nav_buttons[name] = btn

        tools = tk.Frame(self.sidebar, bg=SIDEBAR, padx=14, pady=12)
        tools.pack(fill='x', side='bottom')
        self._button(tools, 'Mises à jour', self.show_updater).pack(fill='x', pady=(0, 8))
        self._button(tools, 'Interface Windows V2 (Qt)',
            lambda: webbrowser.open('https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest')).pack(fill='x', pady=(0, 8))
        self._button(tools, 'Changer de personnage', self.pick_file).pack(fill='x', pady=(0, 8))
        self._button(tools, 'Actualiser maintenant', self.manual_refresh, accent=True).pack(fill='x')
        lbl(tools, 'État du suivi', 9, MUTED, True).pack(anchor='w', pady=(12, 4))
        tk.Label(tools, textvariable=self.status, fg=ACCENT2, bg=SIDEBAR, wraplength=208, justify='left', font=('Segoe UI', 9)).pack(anchor='w')

    def _build_content(self):
        header = tk.Frame(self.content, bg=BG, padx=22, pady=18)
        header.pack(fill='x')
        left = tk.Frame(header, bg=BG)
        left.pack(side='left')
        self.page_title = lbl(left, 'Vue d’ensemble', 22, FG, True)
        self.page_title.pack(anchor='w')
        self.page_subtitle = lbl(left, 'Tableau de bord complet et lecture seule de tes sauvegardes Valheim.', 10, MUTED)
        self.page_subtitle.pack(anchor='w', pady=(4, 0))
        tk.Label(left, textvariable=self.refresh_notice, fg=ACCENT2, bg=BG,
                 font=('Segoe UI', 9), anchor='w', justify='left').pack(anchor='w', pady=(5, 0))
        right = tk.Frame(header, bg=BG)
        right.pack(side='right')
        self.header_group = lbl(right, 'Toutes difficultés', 10, ACCENT, True)
        self.header_group.pack(anchor='e')
        lbl(right, 'Les groupes se recouvrent : ne jamais les additionner.', 9, MUTED).pack(anchor='e', pady=(4, 0))

        self.page_container = tk.Frame(self.content, bg=BG)
        self.page_container.pack(fill='both', expand=True, padx=16, pady=(0, 14))

        for name in NAV_ITEMS:
            frame = tk.Frame(self.page_container, bg=BG)
            self.pages[name] = frame

        self._dashboard_ui()
        self._achievements_ui()
        self._progress_ui()
        self._boss_ui()
        self._combat_ui()
        self._activity_ui()
        self._skills_ui()
        self._history_ui()
        self._raw_ui()

    def show_page(self, name):
        self.page_var.set(name)
        title_map = {
            'Centre de progression': ('Centre de progression', 'Objectifs prioritaires, favoris et bilan de session issu des sauvegardes.'),
            'Vue d’ensemble': ('Vue d’ensemble', 'Les statistiques essentielles de ton personnage en un coup d’œil.'),
            'Succès': ('Succès', '55 entrées du jeu : 53 actives et 2 internes non vérifiées ; critères de collection Valheim 1.0.21. Progrès issus de la sauvegarde.'),
            'Boss': ('Boss', 'Progression des 8 boss, filtres par difficulté et éliminations aux poings.'),
            'Combats': ('Combats', 'Bestiaire et types d’éliminations enregistrés par le jeu.'),
            'Activités': ('Activités', 'Ressources, fabrication, construction et vue nettoyée par catégories utiles.'),
            'Compétences': ('Compétences', 'Niveaux sauvegardés du personnage et progression restante.'),
            'Historique': ('Historique', 'Évolution de tes relevés enregistrés au fil des sauvegardes.'),
            'Compteurs bruts': ('Compteurs bruts', 'Explorer les 205 compteurs du profil sans perdre la lisibilité.'),
        }
        title, subtitle = title_map.get(name, (name, ''))
        self.page_title.config(text=title)
        self.page_subtitle.config(text=subtitle)
        for page_name, frame in self.pages.items():
            frame.pack_forget()
            button = self.nav_buttons[page_name]
            active = page_name == name
            button.configure(bg=PANEL_SOFT if active else SIDEBAR,
                             fg=FG if active else MUTED,
                             activebackground=PANEL_STRONG if active else PANEL_SOFT)
        self.pages[name].pack(fill='both', expand=True)


    def _progress_ui(self):
        tab = self.pages['Centre de progression']
        cards = tk.Frame(tab, bg=BG)
        cards.pack(fill='x', pady=(0, 10))
        self.progress_cards = {}
        for idx, (key, name, hint) in enumerate((
            ('pending', 'Restants', 'Objectifs calculables'),
            ('active', 'En cours', 'Déjà commencés'),
            ('favorite', 'Favoris', 'Priorités personnelles'),
            ('done', 'Atteints', 'Selon le fichier .fch'),
        )):
            shell, value, small = self._metric_card(cards, name, accent=ACCENT2)
            shell.grid(row=0, column=idx, padx=5, sticky='nsew')
            cards.grid_columnconfigure(idx, weight=1, uniform='progress')
            small.config(text=hint)
            self.progress_cards[key] = value

        body = tk.Frame(tab, bg=BG)
        body.pack(fill='both', expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=4)
        body.grid_rowconfigure(0, weight=5)
        body.grid_rowconfigure(1, weight=3)

        ranking_shell, ranking = self._panel(body, 'Objectifs les plus proches',
            'Classement par pourcentage restant ; ce n’est pas une estimation de difficulté.', pad=12)
        ranking_shell.grid(row=0, column=0, sticky='nsew', padx=(0, 6), pady=(0, 10))
        filter_row = tk.Frame(ranking, bg=PANEL)
        filter_row.pack(fill='x', pady=(0, 8))
        lbl(filter_row, 'Afficher :', 9, MUTED).pack(side='left', padx=(0, 8))
        ttk.Combobox(filter_row, textvariable=self.progress_filter,
                     values=('Plus proches', 'Favoris', 'Non commencés'),
                     state='readonly', width=20).pack(side='left')
        area, self.progress_table = self._mk_table(ranking,
            ('Favori', 'Succès', 'Progression', 'Critères restants'),
            {'Favori': 57, 'Succès': 205, 'Progression': 105, 'Critères restants': 113})
        area.pack(fill='both', expand=True)
        self.progress_table.column('Favori', anchor='center')
        self.progress_table.bind('<<TreeviewSelect>>', self._progress_select)
        self.progress_empty = lbl(ranking, '', 9, MUTED)
        self.progress_empty.pack(anchor='w', pady=(6, 0))

        actions_shell, actions = self._panel(body, 'Plan d’action',
            'Choisis un succès : les critères encore manquants s’affichent en priorité.', pad=12)
        actions_shell.grid(row=0, column=1, sticky='nsew', padx=(6, 0), pady=(0, 10))
        self.progress_title = lbl(actions, 'Sélectionne un objectif', 14, FG, True, wraplength=360, justify='left')
        self.progress_title.pack(anchor='w', pady=(0, 7))
        self.progress_description = lbl(actions, '', 10, MUTED, wraplength=380, justify='left')
        self.progress_description.pack(anchor='w')
        actionbar = tk.Frame(actions, bg=PANEL)
        actionbar.pack(fill='x', pady=(12, 10))
        self.progress_favorite_button = self._button(actionbar, '☆ Ajouter aux favoris', self.toggle_progress_favorite)
        self.progress_favorite_button.pack(side='left', padx=(0, 8))
        self._button(actionbar, 'Voir les critères', self.open_progress_achievement).pack(side='left')
        self.progress_action_text = tk.Text(actions, bg=PANEL_SOFT, fg=FG, wrap='word',
            font=('Segoe UI', 10), height=10, relief='flat', padx=12, pady=9,
            highlightthickness=1, highlightbackground=BORDER, state='disabled')
        self.progress_action_text.pack(fill='both', expand=True)

        session_shell, session = self._panel(body, 'Bilan de la dernière session estimée',
            'Différences entre sauvegardes rapprochées ; pas de données en temps réel.', pad=12)
        session_shell.grid(row=1, column=0, columnspan=2, sticky='nsew')
        self.progress_session_status = lbl(session, '', 10, ACCENT, True, wraplength=880, justify='left')
        self.progress_session_status.pack(anchor='w', pady=(0, 9))
        area, self.progress_session_table = self._mk_table(session, ('Statistique', 'Gain constaté'),
                                                           {'Statistique': 290, 'Gain constaté': 155})
        area.pack(fill='both', expand=True)
        self.progress_session_extra = lbl(session, '', 9, MUTED, wraplength=940, justify='left')
        self.progress_session_extra.pack(anchor='w', pady=(9, 0))

    def _progress_select(self, event=None):
        selected = self.progress_table.selection()
        if selected:
            self.progress_selected = selected[0]
        self._render_progress_actions()

    def _progress_write_text(self, content):
        self.progress_action_text.configure(state='normal')
        self.progress_action_text.delete('1.0', 'end')
        self.progress_action_text.insert('1.0', content)
        self.progress_action_text.configure(state='disabled')

    def _render_progress_actions(self):
        result = next((a for a in self.achievement_results if a['key'] == self.progress_selected), None)
        if not result:
            self.progress_title.config(text='Sélectionne un objectif')
            self.progress_description.config(text='Aucun objectif correspondant à ce filtre.')
            self.progress_favorite_button.config(state='disabled')
            self._progress_write_text('Les succès déjà atteints sont consultables dans la page Succès.')
            return
        self.progress_favorite_button.config(state='normal')
        favorite = result['key'] in self.progress_favorites
        self.progress_favorite_button.config(text='★ Retirer des favoris' if favorite else '☆ Ajouter aux favoris')
        self.progress_title.config(text=result['title'])
        self.progress_description.config(text=(
            result.get('description', '') + '\n'
            + f"{float(result['percent'] or 0):.1f} % accomplis · "
            + f"{result['completed_conditions']} / {result['total_conditions']} critères."
        ))
        missing = pending_actions(result, 9)
        if not missing:
            content = 'Aucun critère mesurable restant.'
        else:
            content = '\n\n'.join(
                f"{i}. {part['label']}\n"
                f"    Encore {fmt(part['remaining'])} · "
                f"{fmt(part['current'])} / {fmt(part['goal'])}"
                for i, part in enumerate(missing, 1))
            remaining_total = sum(not p['complete'] for p in result['parts'])
            if remaining_total > len(missing):
                content += f"\n\n… et {remaining_total - len(missing)} autres critères non remplis."
        self._progress_write_text(content)

    def toggle_progress_favorite(self):
        if not self.current or not self.progress_selected:
            return
        key = self.progress_selected
        if key in self.progress_favorites:
            self.progress_favorites.remove(key)
        else:
            self.progress_favorites.add(key)
        try:
            save_favorites(self.current['name'], self.progress_favorites)
        except OSError as exc:
            # Ne pas afficher un succès sauvegardé si le disque est en erreur.
            if key in self.progress_favorites:
                self.progress_favorites.remove(key)
            else:
                self.progress_favorites.add(key)
            messagebox.showerror(APP_NAME, f'Impossible de sauvegarder les favoris : {exc}')
            return
        self.refresh_progress()

    def open_progress_achievement(self):
        if not self.progress_selected:
            return
        key = self.progress_selected
        self.achievement_selected = key
        self.achievement_filter.set('Tous')
        self.achievement_origin.set('Jeu + Steam + internes')
        self.achievement_category.set('Toutes les catégories')
        self.achievement_search.set('')
        self.show_page('Succès')
        self.refresh_achievements()
        if self.achievement_table.exists(key):
            self.achievement_table.selection_set(key)
            self.achievement_table.see(key)
            self._render_achievement_details()

    def refresh_progress(self):
        if not self.current or not hasattr(self, 'progress_table'):
            return
        name = self.current['name']
        self.progress_favorites = load_favorites(name)
        results = self.achievement_results
        all_pending = progress_ranking(results, self.progress_favorites)
        complete = sum(a['complete'] for a in results if a['measurable'])
        active = sum(a['fraction'] > 0 for a in all_pending)
        for key, value in (('pending', len(all_pending)), ('active', active),
                           ('favorite', len(self.progress_favorites)), ('done', complete)):
            self.progress_cards[key].config(text=fmt(value))
        shown = all_pending
        chosen = self.progress_filter.get()
        if chosen == 'Favoris':
            shown = [r for r in all_pending if r['favorite']]
        elif chosen == 'Non commencés':
            shown = [r for r in all_pending if not r['fraction']]
        self.progress_table.delete(*self.progress_table.get_children())
        for row in shown:
            remain = row['total_conditions'] - row['completed_conditions']
            self.progress_table.insert('', 'end', iid=row['key'], values=(
                '★' if row['favorite'] else '☆', row['title'],
                f"{row['percent']:.1f} %", f"{remain} / {row['total_conditions']}"
            ))
        if self.progress_table.exists(self.progress_selected):
            self.progress_table.selection_set(self.progress_selected)
        elif shown:
            self.progress_selected = shown[0]['key']
            self.progress_table.selection_set(self.progress_selected)
        else:
            self.progress_selected = ''
        self.progress_empty.config(text=(
            f'{len(shown)} objectif(s) affiché(s) · {len(all_pending)} calculables à terminer'
            if shown else 'Aucun succès à afficher avec ce filtre.'
        ))
        self._render_progress_actions()
        self._render_progress_session()

    def _render_progress_session(self):
        rows = sample_rows(self.db, self.current['name'])
        report = estimate_last_session(rows)
        if not report['available']:
            self.progress_session_status.config(text=report['reason'])
            self._put(self.progress_session_table, [])
            self.progress_session_extra.config(text=(
                'Le tracker doit observer au moins deux sauvegardes rapprochées pour calculer des gains.'
            ))
            return
        start = datetime.fromtimestamp(report['start']).strftime('%d/%m %H:%M')
        end = datetime.fromtimestamp(report['end']).strftime('%d/%m %H:%M')
        self.progress_session_status.config(text=(
            f"{start} → {end} · {report['samples']} relevés · "
            f"{report['minutes_played']:.0f} min de jeu enregistrées"
        ))
        self._put(self.progress_session_table, [
            (label, '+' + fmt(value)) for label, value in report['changes'].items()
        ])
        skills = ', '.join(f'{name} +{gain:.2f}' for name, gain in report['skills'][:4]) or 'aucun gain visible'
        reached = ', '.join(report['new_goals'][:5]) or 'aucun nouvel objectif atteint détecté'
        resets = '\nCompteurs diminués/retour en arrière : ' + ', '.join(report['resets']) if report['resets'] else ''
        self.progress_session_extra.config(text=(
            'Compétences : ' + skills + '\n'
            + 'Objectifs atteints sur cet intervalle : ' + reached + '\n'
            + report['note'] + resets
        ))

    def _dashboard_ui(self):
        tab = self.pages['Vue d’ensemble']
        grid = tk.Frame(tab, bg=BG)
        grid.pack(fill='both', expand=True)

        cards = tk.Frame(grid, bg=BG)
        cards.pack(fill='x', pady=(0, 12))
        self.cards = {}
        items = [
            ('kills', 'Créatures tuées', 'Bestiaire total'),
            ('deaths', 'Décès', 'Toutes causes confondues'),
            ('bosses', 'Boss validés', 'Sur 8 boss'),
            ('crafted', 'Objets fabriqués', 'Tous mondes confondus'),
            ('built', 'Éléments placés', 'Construction totale'),
            ('picked_up', 'Objets ramassés', 'Stacks collectés'),
            ('world_hours', 'Temps de jeu', 'Heures cumulées'),
            ('recipes', 'Recettes connues', 'Découvertes sauvegardées'),
        ]
        for i, (key, title, hint) in enumerate(items):
            card, value, small = self._metric_card(cards, title)
            card.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky='nsew')
            cards.grid_columnconfigure(i % 4, weight=1, uniform='cards')
            small.config(text=hint)
            self.cards[key] = value

        bottom = tk.Frame(grid, bg=BG)
        bottom.pack(fill='both', expand=True)
        left_shell, left = self._panel(bottom, 'Progression rapide', 'Lecture synthétique des boss et de l’état du personnage.')
        left_shell.pack(side='left', fill='both', expand=True, padx=(0, 6))
        right_shell, right = self._panel(bottom, 'Résumé détaillé', 'Informations utiles sur la sauvegarde chargée et les mondes connus.')
        right_shell.pack(side='left', fill='both', expand=True, padx=(6, 0))

        self.dashboard_boss_line = lbl(left, '', 11, FG, True, justify='left', anchor='w')
        self.dashboard_boss_line.pack(anchor='w')
        self.dashboard_killer_line = lbl(left, '', 10, ACCENT, justify='left', anchor='w')
        self.dashboard_killer_line.pack(anchor='w', pady=(6, 12))

        self.boss_rows = {}
        boss_box = tk.Frame(left, bg=PANEL)
        boss_box.pack(fill='x')
        for boss in BOSSES.values():
            line = tk.Frame(boss_box, bg=PANEL)
            line.pack(fill='x', pady=3)
            lbl(line, boss, 10, FG).pack(side='left')
            v = lbl(line, '—', 10, MUTED, True)
            v.pack(side='right')
            self.boss_rows[boss] = v

        self.summary_text = lbl(right, '—', 10, MUTED, False, justify='left', anchor='nw', wraplength=560)
        self.summary_text.pack(fill='x')
        self.previous_text = lbl(right, '', 10, ACCENT, False, justify='left', anchor='w', wraplength=560)
        self.previous_text.pack(anchor='w', pady=(16, 0))

    def _achievements_ui(self):
        tab = self.pages['Succès']
        summary = tk.Frame(tab, bg=BG)
        summary.pack(fill='x', pady=(0, 10))
        self.achievement_cards = {}
        for i, (key, name, hint) in enumerate((
            ('complete', 'Objectifs atteints', 'Selon la sauvegarde'),
            ('ongoing', 'En progression', 'Au moins un critère commencé'),
            ('remaining', 'Non commencés', 'Aucun critère validé'),
            ('unknown', 'Non calculables', 'Aucune validation déduite'),
            ('total', 'Catalogue du jeu', '53 actifs + 2 internes'),
        )):
            card, value, small = self._metric_card(summary, name, accent=GREEN)
            card.grid(row=0, column=i, sticky='nsew', padx=5)
            summary.grid_columnconfigure(i, weight=1, uniform='achievements')
            self.achievement_cards[key] = value
            small.config(text=hint)

        filt_shell, filt = self._panel(tab, 'Succès du jeu et Steam',
            'Objectifs calculés depuis la sauvegarde. Aucune confirmation directe des déblocages Steam.', pad=12)
        filt_shell.pack(fill='x', pady=(0, 10))
        filter_row = tk.Frame(filt, bg=PANEL)
        filter_row.pack(fill='x')
        lbl(filter_row, 'Source :', 10, MUTED).pack(side='left', padx=(0, 8))
        ttk.Combobox(filter_row, textvariable=self.achievement_origin,
                     values=['Jeu + Steam + internes', 'Jeu + Steam (53)', 'Internes supplémentaires (2)'],
                     width=25, state='readonly').pack(side='left', padx=(0, 18))
        lbl(filter_row, 'Chercher :', 10, MUTED).pack(side='left', padx=(0, 8))
        ttk.Entry(filter_row, textvariable=self.achievement_search, width=23).pack(side='left')
        second_filter = tk.Frame(filt, bg=PANEL)
        second_filter.pack(fill='x', pady=(9, 0))
        lbl(second_filter, 'Catégorie :', 10, MUTED).pack(side='left', padx=(0, 8))
        ttk.Combobox(second_filter, textvariable=self.achievement_category,
                     values=['Toutes les catégories'] + sorted({x.category for x in SPECS}),
                     width=22, state='readonly').pack(side='left')
        lbl(second_filter, 'État :', 10, MUTED).pack(side='left', padx=(18, 8))
        ttk.Combobox(second_filter, textvariable=self.achievement_filter,
                     values=['Tous', 'À terminer', 'Objectif atteint', 'En progression', 'Non commencé', 'Non calculable'],
                     width=20, state='readonly').pack(side='left')

        body = tk.Frame(tab, bg=BG)
        body.pack(fill='both', expand=True)
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=5)
        body.grid_rowconfigure(0, weight=1)

        listing_shell, listing = self._panel(body, 'Liste des objectifs',
            'Choisis un succès pour afficher ses critères.', pad=12)
        listing_shell.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        area, self.achievement_table = self._mk_table(listing,
            ('Succès', 'Progression', 'État'),
            {'Succès': 214, 'Progression': 105, 'État': 150})
        area.pack(fill='both', expand=True)
        self.achievement_table.tag_configure('ach-done', background='#13332d', foreground=GREEN)
        self.achievement_table.tag_configure('ach-active', background=PANEL, foreground=FG)
        self.achievement_table.tag_configure('ach-idle', background='#172841', foreground=MUTED)
        self.achievement_table.tag_configure('ach-unknown', background='#25243b', foreground='#d2bfd9')
        self.achievement_table.bind('<<TreeviewSelect>>', self._achievement_select)

        details_shell, details = self._panel(body, 'Détail du succès',
            'Estimation basée sur la sauvegarde, sans confirmation du jeu.', pad=12)
        details_shell.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        title = tk.Frame(details, bg=PANEL)
        title.pack(fill='x', pady=(0, 10))
        self.achievement_detail_title = lbl(title, 'Choisis un succès', 13, FG, True, wraplength=330, justify='left')
        self.achievement_detail_title.pack(anchor='w')
        self.achievement_detail_status = lbl(title, '', 10, ACCENT, True)
        self.achievement_detail_status.pack(anchor='w', pady=(5, 0))
        self.achievement_progress = tk.Canvas(details, bg=PANEL_SOFT, height=14, highlightthickness=0)
        self.achievement_progress.pack(fill='x', pady=(0, 9))
        self.achievement_progress.bind('<Configure>', lambda e: self._paint_achievement_progress())
        self.achievement_note = lbl(details, '', 10, MUTED, wraplength=360, justify='left', anchor='w')
        self.achievement_note.pack(anchor='w', pady=(0, 8))
        lbl(details, 'Rechercher un objet ou une créature :', 9, MUTED).pack(anchor='w', pady=(2, 4))
        ttk.Entry(details, textvariable=self.achievement_detail_search).pack(fill='x', pady=(0, 8))

        scroll_area = tk.Frame(details, bg=PANEL)
        scroll_area.pack(fill='both', expand=True)
        self.achievement_canvas = tk.Canvas(scroll_area, bg=PANEL, highlightthickness=0, height=170)
        ach_scroll = ttk.Scrollbar(scroll_area, orient='vertical', command=self.achievement_canvas.yview)
        self.achievement_canvas.configure(yscrollcommand=ach_scroll.set)
        self.achievement_canvas.pack(side='left', fill='both', expand=True)
        ach_scroll.pack(side='right', fill='y')
        self.achievement_detail_body = tk.Frame(self.achievement_canvas, bg=PANEL)
        self.achievement_canvas.create_window((0, 0), anchor='nw', window=self.achievement_detail_body, tags='ach-window')
        self.achievement_detail_body.bind('<Configure>', lambda e: self.achievement_canvas.configure(scrollregion=self.achievement_canvas.bbox('all')))
        self.achievement_canvas.bind('<Configure>', lambda e: self.achievement_canvas.itemconfigure('ach-window', width=e.width))

    def _achievement_select(self, event=None):
        tree = self.achievement_table
        selected = tree.selection()
        if selected:
            self.achievement_selected = selected[0]
        self.achievement_detail_limit = 65
        if self.achievement_detail_search.get():
            self.achievement_detail_search.set('')
        else:
            self._render_achievement_details()

    def _show_more_achievement_details(self):
        self.achievement_detail_limit += 65
        self._render_achievement_details(reset_scroll=False)

    def _paint_achievement_progress(self):
        if not hasattr(self, 'achievement_progress'):
            return
        c = self.achievement_progress
        c.delete('all')
        width = max(100, c.winfo_width())
        result = next((v for v in self.achievement_results if v['key'] == self.achievement_selected), None)
        fraction = (result['fraction'] or 0) if result else 0
        c.create_rectangle(0, 0, width, 14, fill=PANEL_SOFT, outline='')
        if fraction > 0:
            c.create_rectangle(0, 0, width * fraction, 14,
                               fill=GREEN if result['complete'] else ACCENT, outline='')

    def _render_achievement_details(self, reset_scroll=True):
        if not hasattr(self, 'achievement_detail_title'):
            return
        result = next((v for v in self.achievement_results if v['key'] == self.achievement_selected), None)
        for widget in self.achievement_detail_body.winfo_children():
            widget.destroy()
        if result is None:
            self.achievement_detail_title.config(text='Choisis un succès')
            self.achievement_detail_status.config(text='')
            self.achievement_note.config(text='')
            self._paint_achievement_progress()
            return
        self.achievement_detail_title.config(text=result['title'])
        if not result['measurable']:
            self.achievement_detail_status.config(text='NON CALCULABLE · ' +
                ('Entrée interne non vérifiée' if result['origin'] == 'Interne uniquement'
                 else 'Liste complète des critères indisponible'), fg=ORANGE)
        else:
            self.achievement_detail_status.config(text=f"{result['percent']:.0f} % · " +
                ('Objectif atteint selon la sauvegarde' if result['complete'] else
                 f"{result['completed_conditions']}/{result['total_conditions']} critères"),
                fg=GREEN if result['complete'] else ACCENT)
        self._paint_achievement_progress()
        older = self.achievement_previous.get(result['key'])
        changes = progress_delta(result, older)
        change_text = ''
        if changes:
            change_text = ' · Depuis le relevé précédent : ' + ', '.join(
                f'{name} +{fmt(delta)}' if delta > 0 else f'{name} {fmt(delta)}' for name, delta in changes[:3])
        extra_note = ''
        if result['key'] == 'master_hunter' and self.current:
            any_spec = next(sp for sp in SPECS if sp.key == 'hunter')
            any_result = evaluate_one(self.current, any_spec)
            extra_note = (
                f"\n\nDifficulté : DIFFICILE OU SUPÉRIEUR UNIQUEMENT. "
                f"Toutes difficultés : {any_result['completed_conditions']}/{any_result['total_conditions']} espèces ; "
                f"difficile ou supérieur : {result['completed_conditions']}/{result['total_conditions']}. "
                "Les éliminations faites en normal ne sont pas reprises dans le compteur difficile. "
                "En changeant la difficulté du serveur, il faudra vaincre à nouveau les espèces concernées."
            )
        elif result['key'] == 'toughest':
            extra_note = "\n\nSeules les victoires en difficile ou supérieur comptent. Les boss déjà vaincus en normal doivent être refaits."
        self.achievement_note.config(text=result['description'] +
            ('\n\n' + result['note'] if result['note'] else '') + extra_note + change_text)
        all_parts = sorted(result['parts'], key=lambda part: (part['complete'], part['label'].casefold()))
        term = self.achievement_detail_search.get().strip().casefold()
        if term:
            all_parts = [part for part in all_parts if term in part['label'].casefold() or term in str(part['key']).casefold()]
        shown_parts = all_parts[:self.achievement_detail_limit]
        if not all_parts:
            lbl(self.achievement_detail_body, 'Aucun critère correspondant à cette recherche.', 10, MUTED).pack(anchor='w', pady=8)
        if len(all_parts) > 65:
            lbl(self.achievement_detail_body,
                f"{len(shown_parts)} / {len(all_parts)} critères affichés • Manquants d'abord",
                9, ACCENT, True).pack(anchor='w', pady=(0, 8))
        for part in shown_parts:
            row = tk.Frame(self.achievement_detail_body, bg=PANEL)
            row.pack(fill='x', pady=2)
            lbl(row, '✓' if part['complete'] else '○', 12,
                GREEN if part['complete'] else MUTED, True).pack(side='left', padx=(0, 8))
            lbl(row, part['label'], 10, FG, False, wraplength=185, justify='left').pack(side='left')
            current = fmt(part['current'])
            if part.get('diagnostic'):
                status_text = f'Poings : {current}' if part['diagnostic'] == 'poings' else f'{current} / 53 (indicatif)'
                status_color = ORANGE
            else:
                target = fmt(part['goal'])
                remain = 'atteint' if part['complete'] else f"reste {fmt(part['remaining'])}"
                status_text = f'{current} / {target} · {remain}'
                status_color = GREEN if part['complete'] else MUTED
            lbl(row, status_text, 10, status_color, True,
                wraplength=175, justify='right').pack(side='right')
        if len(shown_parts) < len(all_parts):
            self._button(self.achievement_detail_body,
                f"Afficher 65 critères supplémentaires ({len(all_parts)-len(shown_parts)} restants)",
                self._show_more_achievement_details).pack(fill='x', pady=(12, 8))
        if reset_scroll:
            self.achievement_canvas.yview_moveto(0)

    def refresh_achievements(self):
        if not self.current or not hasattr(self, 'achievement_table'):
            return
        self.achievement_results = evaluate_all(self.current)
        recent = sample_rows(self.db, self.current['name'])
        self.achievement_previous = {}
        if len(recent) >= 2:
            previous = evaluate_all(recent[-2][3])
            self.achievement_previous = {x['key']: x for x in previous}
        completed = sum(r['complete'] for r in self.achievement_results)
        active = sum(r['measurable'] and 0 < r['fraction'] < 1 for r in self.achievement_results)
        idle = sum(r['measurable'] and r['fraction'] == 0 for r in self.achievement_results)
        unknown = sum(not r['measurable'] for r in self.achievement_results)
        for key, value in [('complete', completed), ('ongoing', active),
                           ('remaining', idle), ('unknown', unknown), ('total', len(self.achievement_results))]:
            self.achievement_cards[key].config(text=fmt(value))
        needle = self.achievement_search.get().strip().lower()
        category = self.achievement_category.get()
        status = self.achievement_filter.get()
        origin = self.achievement_origin.get()
        visible = []
        for row in self.achievement_results:
            if origin == 'Jeu + Steam (53)' and row['origin'] != 'Jeu + Steam':
                continue
            if origin == 'Internes supplémentaires (2)' and row['origin'] != 'Interne uniquement':
                continue
            if needle and needle not in row['title'].lower() and needle not in row.get('title_en', '').lower() and needle not in row['description'].lower() and needle not in row['category'].lower():
                continue
            if category != 'Toutes les catégories' and row['category'] != category:
                continue
            if status == 'À terminer' and (row['complete'] or not row['measurable']):
                continue
            if status == 'Objectif atteint' and not row['complete']:
                continue
            if status == 'En progression' and not (row['measurable'] and 0 < row['fraction'] < 1):
                continue
            if status == 'Non commencé' and (not row['measurable'] or row['fraction'] != 0):
                continue
            if status == 'Non calculable' and row['measurable']:
                continue
            visible.append(row)
        tree = self.achievement_table
        tree.delete(*tree.get_children())
        for row in visible:
            if not row['measurable']:
                progress = '—'
                state = 'Interne non vérifié' if row['origin'] == 'Interne uniquement' else 'Non calculable'
                tag = 'ach-unknown'
            elif row['total_conditions'] == 1:
                part = row['parts'][0]
                progress = f"{fmt(part['current'])} / {fmt(part['goal'])}"
                state = 'Objectif atteint' if row['complete'] else ('En cours' if row['fraction'] else 'Non commencé')
                tag = 'ach-done' if row['complete'] else ('ach-active' if row['fraction'] else 'ach-idle')
            else:
                progress = f"{row['completed_conditions']} / {row['total_conditions']} critères"
                state = 'Objectif atteint' if row['complete'] else ('En cours' if row['fraction'] else 'Non commencé')
                tag = 'ach-done' if row['complete'] else ('ach-active' if row['fraction'] else 'ach-idle')
            tree.insert('', 'end', iid=row['key'],
                        values=(row['title'], progress, state), tags=(tag,))
        if tree.exists(self.achievement_selected):
            tree.selection_set(self.achievement_selected)
        elif visible:
            self.achievement_selected = visible[0]['key']
            tree.selection_set(self.achievement_selected)
        else:
            self.achievement_selected = ''
        self._render_achievement_details()
        self.refresh_progress()

    def _boss_ui(self):
        tab = self.pages['Boss']
        top = tk.Frame(tab, bg=BG)
        top.pack(fill='x', pady=(0, 12))
        shell, inner = self._panel(top, 'Suivi des boss', 'Choisis une difficulté pour contrôler le statut de validation.')
        shell.pack(fill='x')
        row = tk.Frame(inner, bg=PANEL)
        row.pack(fill='x')
        lbl(row, 'Difficulté suivie', 10, MUTED).pack(side='left')
        ttk.Combobox(row, textvariable=self.boss_difficulty_display,
                     values=[GROUP_FR[k] for k in ('Any', 'Default', 'Hard', 'VeryHard', 'Hardcore')],
                     width=20, state='readonly').pack(side='left', padx=(10, 0))
        self.boss_group_text = lbl(row, '', 10, ACCENT, True)
        self.boss_group_text.pack(side='left', padx=12)

        counters = tk.Frame(tab, bg=BG)
        counters.pack(fill='x', pady=(0, 12))
        self.boss_cards = {}
        for i, (group, name) in enumerate((('Default', 'Normal ou +'), ('Hard', 'Difficile ou +'),
                                           ('VeryHard', 'Très difficile ou +'), ('Hardcore', 'Extrême'))):
            card, value, hint = self._metric_card(counters, name, accent=GOLD)
            card.grid(row=0, column=i, sticky='nsew', padx=6)
            counters.grid_columnconfigure(i, weight=1, uniform='boss')
            hint.config(text='Boss validés')
            self.boss_cards[group] = value

        table_shell, table_inner = self._panel(tab, 'Tableau détaillé',
                                               'Le compteur “Poings” décrit le type d’élimination enregistré, pas un combat forcément 100 % aux poings.')
        table_shell.pack(fill='both', expand=True)
        area, self.boss_table = self._mk_table(table_inner,
              ('Boss', 'Total', 'Normal +', 'Difficile +', 'Très difficile +', 'Extrême', 'Poings*'),
              {'Boss': 220, 'Total': 80, 'Normal +': 100, 'Difficile +': 110,
               'Très difficile +': 126, 'Extrême': 90, 'Poings*': 90})
        area.pack(fill='both', expand=True)
        self.boss_table.tag_configure('completed', background='#16352f', foreground=GREEN)
        self.boss_table.tag_configure('missing', background=PANEL, foreground=FG)

    def _combat_ui(self):
        tab = self.pages['Combats']
        top_cards = tk.Frame(tab, bg=BG)
        top_cards.pack(fill='x', pady=(0, 12))
        self.combat_cards = {}
        for i, (key, title) in enumerate((('kills', 'Victimes totales'), ('unique', 'Créatures différentes'), ('top', 'Top créature'))):
            card, value, hint = self._metric_card(top_cards, title, accent=RED)
            card.grid(row=0, column=i, sticky='nsew', padx=6)
            top_cards.grid_columnconfigure(i, weight=1, uniform='combat')
            self.combat_cards[key] = (value, hint)
        self.combat_cards['top'][1].config(text='—')

        shell, inner = self._panel(tab, 'Bestiaire', 'Filtre les créatures pour retrouver rapidement un ennemi.')
        shell.pack(fill='both', expand=True)
        search = self._search_field(inner, self.search_combat, 'Rechercher dans les créatures :')
        search.pack(fill='x', pady=(0, 10))
        area, self.combat_table = self._mk_table(inner, ('Créature', 'Total', 'Poings', 'Magie', 'Distance', 'Mêlée'), {'Créature': 330})
        area.pack(fill='both', expand=True)
        lbl(inner, 'Astuce : “Poings” correspond à la catégorie d’élimination enregistrée. Ce n’est pas une preuve d’un combat entier à mains nues.', 9, MUTED, wraplength=980, justify='left').pack(anchor='w', pady=(10, 0))

    def _activity_ui(self):
        tab = self.pages['Activités']
        top_cards = tk.Frame(tab, bg=BG)
        top_cards.pack(fill='x', pady=(0, 12))
        self.activity_cards = {}
        activity_items = [('quantity', 'Quantité totale'), ('types', 'Types distincts'), ('top', 'Top ressource'), ('dominant', 'Famille dominante')]
        for i, (key, title) in enumerate(activity_items):
            card, value, hint = self._metric_card(top_cards, title, accent=ORANGE)
            card.grid(row=0, column=i, sticky='nsew', padx=6)
            top_cards.grid_columnconfigure(i, weight=1, uniform='activity')
            self.activity_cards[key] = (value, hint)

        content = tk.Frame(tab, bg=BG)
        content.pack(fill='both', expand=True)

        left_shell, left = self._panel(content, 'Vue propre des activités', 'Tu peux filtrer les éléments et la liste te montre une catégorie lisible pour chaque entrée.')
        left_shell.pack(side='left', fill='both', expand=True, padx=(0, 6))
        right_shell, right = self._panel(content, 'Répartition utile', 'Résumé par grande famille pour mieux repérer bois, métaux, nourriture, etc.')
        right_shell.pack(side='left', fill='y', padx=(6, 0))

        controls = tk.Frame(left, bg=PANEL)
        controls.pack(fill='x', pady=(0, 10))
        search = self._search_field(controls, self.search_activity, 'Filtrer les éléments :')
        search.pack(side='left')
        ttk.Combobox(controls, textvariable=self.activity, values=list(SECTIONS), state='readonly', width=24).pack(side='right')

        area, self.activity_table = self._mk_table(left, ('Catégorie', 'Élément', 'Quantité'), {'Catégorie': 170, 'Élément': 330, 'Quantité': 110})
        area.pack(fill='both', expand=True)

        self.activity_summary = lbl(right, '', 10, MUTED, False, justify='left', anchor='nw', wraplength=300)
        self.activity_summary.pack(anchor='w', pady=(0, 10))
        area2, self.activity_group_table = self._mk_table(right, ('Famille', 'Quantité', 'Part'), {'Famille': 180, 'Quantité': 92, 'Part': 72})
        area2.pack(fill='both', expand=True)

    def _skills_ui(self):
        tab = self.pages['Compétences']
        top_cards = tk.Frame(tab, bg=BG)
        top_cards.pack(fill='x', pady=(0, 12))
        self.skill_cards = {}
        for i, (key, title) in enumerate((('best1', 'Compétence #1'), ('best2', 'Compétence #2'), ('best3', 'Compétence #3'))):
            card, value, hint = self._metric_card(top_cards, title, accent=ACCENT2)
            card.grid(row=0, column=i, sticky='nsew', padx=6)
            top_cards.grid_columnconfigure(i, weight=1, uniform='skills')
            self.skill_cards[key] = (value, hint)
        shell, inner = self._panel(tab, 'Compétences', 'Les niveaux proviennent de la dernière sauvegarde lue. Le tracker n’accède jamais au jeu en direct.')
        shell.pack(fill='both', expand=True)
        self.skills_summary = lbl(inner, '', 10, ACCENT, justify='left')
        self.skills_summary.pack(anchor='w', pady=(0, 8))
        area, self.skill_table = self._mk_table(inner, ('Compétence', 'Niveau', 'XP vers le suivant', 'Progression'), {'Compétence': 300})
        area.pack(fill='both', expand=True)

    def _history_ui(self):
        tab = self.pages['Historique']
        shell, inner = self._panel(tab, 'Historique des sauvegardes', 'Courbe cumulée ou gains entre deux sauvegardes avec export CSV.')
        shell.pack(fill='both', expand=True)
        bar = tk.Frame(inner, bg=PANEL)
        bar.pack(fill='x', pady=(0, 8))
        lbl(bar, 'Mesure', 10, MUTED).pack(side='left', padx=(0, 8))
        ttk.Combobox(bar, textvariable=self.metric, values=list(METRICS), width=26, state='readonly').pack(side='left')
        lbl(bar, 'Difficulté', 10, MUTED).pack(side='left', padx=(18, 8))
        ttk.Combobox(bar, textvariable=self.history_group_display, values=[GROUP_FR[k] for k in ('Any', 'Default', 'Hard', 'RawStats')], state='readonly', width=19).pack(side='left')
        self._button(bar, 'Exporter CSV', self.export_csv).pack(side='right')

        options = tk.Frame(inner, bg=PANEL)
        options.pack(fill='x', pady=(0, 12))
        lbl(options, 'Période', 10, MUTED).pack(side='left', padx=(0, 8))
        ttk.Combobox(options, textvariable=self.history_period, values=list(CHART_PERIODS), width=20, state='readonly').pack(side='left')
        lbl(options, 'Affichage', 10, MUTED).pack(side='left', padx=(18, 8))
        ttk.Combobox(options, textvariable=self.history_mode, values=['Total cumulé', 'Gains entre sauvegardes'], width=24, state='readonly').pack(side='left')

        self.chart = tk.Canvas(inner, bg=BG_ALT, highlightthickness=1, highlightbackground=BORDER, height=360)
        self.chart.pack(fill='both', expand=True, pady=(0, 8))
        self.chart.bind('<Configure>', lambda e: self.draw_history())
        self.chart.bind('<Motion>', self._history_hover)
        self.chart.bind('<Leave>', lambda e: self.chart.delete('tooltip'))
        self.history_info = lbl(inner, '', 9, MUTED, wraplength=1000, justify='left')
        self.history_info.pack(anchor='w')

    def _raw_ui(self):
        tab = self.pages['Compteurs bruts']
        top = tk.Frame(tab, bg=BG)
        top.pack(fill='x', pady=(0, 12))
        shell, inner = self._panel(top, 'Explorer les compteurs', 'Cherche par numéro ou par nom connu. Les indices non identifiés sont volontairement affichés comme tels.')
        shell.pack(fill='x')
        search = self._search_field(inner, self.search_raw, 'Filtrer les compteurs :')
        search.pack(fill='x')
        self.raw_summary = lbl(inner, '', 9, ACCENT, wraplength=950, justify='left')
        self.raw_summary.pack(anchor='w', pady=(10, 0))
        shell2, inner2 = self._panel(tab, 'Table complète', '205 compteurs par groupe de difficulté. Les valeurs restent brutes quand leur signification n’est pas documentée.')
        shell2.pack(fill='both', expand=True)
        area, self.raw_table = self._mk_table(inner2, ('Indice', 'Nom / correspondance connue', 'Valeur'), {'Indice': 90, 'Nom / correspondance connue': 500})
        area.pack(fill='both', expand=True)

    def _sort_table(self, tree, col, reverse):
        def key(item):
            v = tree.set(item, col).replace(' ', '').replace(',', '.')
            try:
                return (0, float(v.rstrip('%')))
            except ValueError:
                return (1, v.lower())
        items = sorted(tree.get_children(''), key=key, reverse=reverse)
        for idx, item in enumerate(items):
            tree.move(item, '', idx)
        tree.heading(col, command=lambda: self._sort_table(tree, col, not reverse))

    def pick_file(self):
        directory = str(Path(self.path).parent) if self.path else str(Path.home())
        path = filedialog.askopenfilename(title='Sélectionner le fichier de personnage Valheim',
              filetypes=[('Personnages Valheim', '*.fch'), ('Tous les fichiers', '*.*')], initialdir=directory)
        if path:
            self.open_file(path)

    def open_file(self, path):
        path = str(Path(path).resolve())
        if not Path(path).is_file():
            messagebox.showerror(APP_NAME, 'Fichier introuvable.')
            return
        self.path = path
        self.file_stamp = None
        self.current_digest = ''
        try:
            self.read_and_record(force=True)
            (app_dir() / 'config.json').write_text(json.dumps({'path': path}, ensure_ascii=False, indent=2), encoding='utf8')
        except (OSError, SaveError, ValueError) as e:
            messagebox.showerror(APP_NAME, str(e))

    # ----- MISES À JOUR -----
    def show_updater(self):
        if self.update_window and self.update_window.winfo_exists():
            self.update_window.lift()
            return
        win = tk.Toplevel(self)
        self.update_window = win
        win.title('Mises à jour — Valheim Stats Tracker')
        win.configure(bg=BG)
        win.geometry('760x560')
        win.minsize(690, 500)
        win.transient(self)
        panel = tk.Frame(win, bg=BG, padx=22, pady=18)
        panel.pack(fill='both', expand=True)
        lbl(panel, f'VALHEIM TRACKER  /  VERSION {updater.current_version()}', 14, FG, True).pack(anchor='w')
        lbl(panel, 'Les données et sauvegardes du personnage restent intactes.', 10, MUTED).pack(anchor='w', pady=(3, 20))
        cfg = updater.read_config()
        lbl(panel, 'Dépôt GitHub public (pseudo/nom-du-depot) :', 10, FG, True).pack(anchor='w', pady=(0, 5))
        self.github_repo = tk.StringVar(value=updater.repo_from_manifest_url(cfg['manifest_url']))
        repo_row = tk.Frame(panel, bg=BG)
        repo_row.pack(fill='x', pady=(0, 14))
        ttk.Entry(repo_row, textvariable=self.github_repo).pack(side='left', fill='x', expand=True)
        self._button(repo_row, 'Configurer GitHub', self._configure_github_repo).pack(side='right', padx=(8, 0))
        lbl(panel, 'Adresse HTTPS du manifeste (mode avancé) :', 10, FG, True).pack(anchor='w', pady=(0, 5))
        self.update_url = tk.StringVar(value=cfg['manifest_url'])
        self.update_autocheck = tk.BooleanVar(value=cfg['check_at_startup'])
        ttk.Entry(panel, textvariable=self.update_url).pack(fill='x')
        ttk.Checkbutton(panel, text='Vérifier au démarrage si une URL est configurée', variable=self.update_autocheck).pack(anchor='w', pady=(9, 15))
        actions = tk.Frame(panel, bg=BG)
        actions.pack(fill='x')
        self._button(actions, 'Enregistrer les paramètres', self._save_update_settings).pack(side='left', padx=(0, 8))
        self._button(actions, 'Vérifier en ligne', self._check_update_from_window).pack(side='left', padx=(0, 8))
        self._button(actions, 'Installer un ZIP local', self._install_local_zip).pack(side='left')
        tk.Frame(panel, bg=BORDER, height=1).pack(fill='x', pady=18)
        lbl(panel, 'ÉTAT DES MISES À JOUR', 10, MUTED, True).pack(anchor='w', pady=(0, 8))
        tk.Label(panel, textvariable=self.updater_notice, wraplength=660, justify='left', bg=BG, fg=ACCENT, font=('Segoe UI', 10)).pack(anchor='w', fill='x')
        self.install_remote_button = self._button(panel, 'Télécharger et installer cette version', self._install_remote, accent=True)
        if self.update_manifest and updater.parse_version(self.update_manifest['version']) > updater.parse_version(updater.current_version()):
            self.install_remote_button.pack(anchor='w', pady=(15, 0))
        if not self.updater_notice.get():
            self.updater_notice.set('Aucune vérification effectuée. Définis une URL de manifeste ou sélectionne un ZIP local.')
        lbl(panel, 'SHA-256 vérifié avant installation ; un backup du programme est conservé.', 9, MUTED).pack(side='bottom', anchor='w')

    def _configure_github_repo(self):
        try:
            url = updater.github_manifest_url(self.github_repo.get())
            self.update_url.set(url)
            if self._save_update_settings():
                self.updater_notice.set('Dépôt GitHub configuré. Vérification de la dernière release…')
                self._check_updates(url)
        except updater.UpdateError as e:
            messagebox.showerror('Mises à jour', str(e), parent=self.update_window)

    def _save_update_settings(self):
        try:
            updater.save_config(self.update_url.get(), self.update_autocheck.get())
        except updater.UpdateError as e:
            messagebox.showerror('Mises à jour', str(e), parent=self.update_window)
            return False
        self.updater_notice.set('Paramètres enregistrés dans le dossier utilisateur.')
        return True

    def _check_update_from_window(self):
        if not self._save_update_settings():
            return
        self._check_updates(self.update_url.get().strip())

    def _startup_update_check(self):
        cfg = updater.read_config()
        if cfg['check_at_startup'] and cfg['manifest_url']:
            self._check_updates(cfg['manifest_url'], quiet=True)

    def _check_updates(self, url, quiet=False):
        if self.update_busy:
            return
        if not url:
            self.updater_notice.set('Renseigne d’abord l’URL HTTPS de ton manifeste.')
            if not quiet:
                messagebox.showinfo('Mises à jour', 'Aucune URL configurée. Tu peux déjà installer un ZIP local.', parent=self.update_window or self)
            return
        self.update_busy = True
        self.updater_notice.set('Vérification de la version en ligne…')
        def work():
            try:
                result = updater.load_manifest(url)
                self.update_events.put(('checked', result, quiet))
            except Exception as e:
                self.update_events.put(('error', f'Verification impossible : {e}', quiet))
        threading.Thread(target=work, daemon=True).start()

    def _install_remote(self):
        if self.update_busy or not self.update_manifest:
            return
        info = self.update_manifest
        if updater.parse_version(info['version']) <= updater.parse_version(updater.current_version()):
            return
        if not messagebox.askyesno('Mises à jour', f"Télécharger et installer Valheim Stats Tracker {info['version']} ?\n\n"
                                   'L’application redémarrera automatiquement. Tes données locales sont conservées.', parent=self.update_window or self):
            return
        self.update_busy = True
        self.updater_notice.set(f"Téléchargement de la version {info['version']} et contrôle SHA-256…")
        def work():
            try:
                package = updater.download_release(info, minimum_version=updater.current_version())
                self.update_events.put(('package', package, False))
            except Exception as e:
                self.update_events.put(('error', f'Mise à jour annulée : {e}', False))
        threading.Thread(target=work, daemon=True).start()

    def _install_local_zip(self):
        if self.update_busy:
            return
        filepath = filedialog.askopenfilename(parent=self.update_window or self, title='Choisir la nouvelle version du tracker', filetypes=[('Archive de mise à jour ZIP', '*.zip')])
        if not filepath:
            return
        self.update_busy = True
        self.updater_notice.set('Vérification et préparation du ZIP local…')
        def work():
            try:
                package = updater.stage_archive(filepath, minimum_version=updater.current_version())
                self.update_events.put(('package_local', package, False))
            except Exception as e:
                self.update_events.put(('error', f'ZIP refusé : {e}', False))
        threading.Thread(target=work, daemon=True).start()

    def _update_pump(self):
        try:
            while True:
                event, payload, quiet = self.update_events.get_nowait()
                self.update_busy = False
                if event == 'error':
                    self.updater_notice.set(payload)
                    if not quiet and self.update_window and self.update_window.winfo_exists():
                        messagebox.showerror('Mises à jour', payload, parent=self.update_window)
                elif event == 'checked':
                    self.update_manifest = payload
                    version = payload['version']
                    if updater.parse_version(version) > updater.parse_version(updater.current_version()):
                        self.updater_notice.set(f"Nouvelle version {version} disponible !\n{payload['notes']}")
                        if self.update_window and self.update_window.winfo_exists():
                            self.install_remote_button.pack(anchor='w', pady=(15, 0))
                        elif quiet:
                            self.status.set(f'Une mise à jour V{version} est disponible (bouton Mises à jour).')
                    else:
                        self.updater_notice.set(f'Le logiciel est à jour (version {updater.current_version()}).')
                        if self.update_window and self.update_window.winfo_exists():
                            self.install_remote_button.pack_forget()
                elif event in ('package', 'package_local'):
                    if event == 'package_local':
                        confirmed = messagebox.askyesno('Mettre à jour',
                            f"Installer la version {payload['version']} depuis ce ZIP ?\n\n"
                            'Choisis uniquement un paquet provenant d’une source de confiance.\n'
                            'Le tracker se fermera puis redémarrera.', parent=self.update_window or self)
                        if not confirmed:
                            self.updater_notice.set('Installation annulée.')
                            continue
                    try:
                        updater.launch_installer(payload, Path(__file__).resolve().parent, os.getpid())
                    except Exception as e:
                        self.updater_notice.set(f'Impossible de lancer l’installateur : {e}')
                        messagebox.showerror('Mises à jour', str(e), parent=self.update_window or self)
                    else:
                        self.close()
                        return
        except queue.Empty:
            pass
        self.after(200, self._update_pump)

    def _save_snapshot(self, decoded, digest, filename, modified):
        self.db.execute('INSERT OR IGNORE INTO snapshots(character,sha,observed_at,filename,data) VALUES (?,?,?,?,?)',
                        (decoded['name'], digest, modified, filename,
                         zlib.compress(json.dumps(decoded, ensure_ascii=False, separators=(',', ':')).encode('utf8'))))
        self.db.commit()

    def manual_refresh(self):
        """Relit réellement le fichier .fch et indique si Valheim l'a modifié."""
        checked_at = datetime.now().strftime('%H:%M:%S')
        if not self.path:
            self.status.set('Aucun personnage sélectionné.')
            self.refresh_notice.set('Sélectionne une sauvegarde .fch pour l’actualiser.')
            messagebox.showwarning(APP_NAME, 'Aucun personnage sélectionné. Utilise « Changer de personnage ».')
            return
        try:
            result = self.read_and_record(force=True)
        except Exception as exc:
            self.status.set('Échec de la vérification : ' + str(exc)[:110])
            self.refresh_notice.set(f'Échec de lecture à {checked_at} — consulte le message d’erreur.')
            messagebox.showerror(
                APP_NAME,
                'Impossible de lire la sauvegarde sélectionnée :\n\n'
                + self.path + '\n\n'
                + str(exc),
            )
            return
        if result == 'unchanged':
            written_at = datetime.fromtimestamp(Path(self.path).stat().st_mtime).strftime('%d/%m/%Y %H:%M:%S')
            self.status.set(f'Vérifié à {checked_at} • aucune nouvelle sauvegarde. Fichier : {written_at}')
            self.refresh_notice.set(
                f'Vérifié à {checked_at} : sauvegarde inchangée (écrite le {written_at}).'
            )
        elif result == 'updated':
            self.status.set(f'Nouveau relevé chargé à {checked_at} depuis {Path(self.path).name}.')
            self.refresh_notice.set(f'Nouveau relevé chargé à {checked_at} — tableaux et succès actualisés.')
        elif result == 'busy':
            self.refresh_notice.set('Valheim/Steam écrit la sauvegarde : nouvelle tentative au prochain contrôle.')
        else:
            self.status.set('Aucune nouvelle sauvegarde lisible.')
            self.refresh_notice.set(f'Vérifié à {checked_at} : aucune donnée nouvelle.')

    def read_and_record(self, force=False):
        if not self.path:
            return 'missing'
        p = Path(self.path)
        try:
            stat_before = p.stat()
            stamp = (stat_before.st_mtime_ns, stat_before.st_size)
            if stamp == self.file_stamp and not force:
                return 'unchanged'
            raw = p.read_bytes()
            stat_after = p.stat()
            if (stat_after.st_mtime_ns, stat_after.st_size) != stamp:
                self.status.set('Écriture en cours : nouvelle tentative dans 5 secondes')
                return 'busy'
            digest = hashlib.sha256(raw).hexdigest()
            if digest == self.current_digest and self.current is not None:
                # Ne pas simuler une sauvegarde nouvelle si elle est identique.
                self.file_stamp = stamp
                return 'unchanged'
            decoded = decode(raw)
            old_path = Path(str(p) + '.old')
            self.old = None
            if old_path.is_file():
                try:
                    rawold = old_path.read_bytes()
                    olddecoded = decode(rawold)
                    if olddecoded['name'] == decoded['name']:
                        self.old = olddecoded
                        if not sample_rows(self.db, decoded['name']):
                            self._save_snapshot(olddecoded, hashlib.sha256(rawold).hexdigest(), old_path.name, old_path.stat().st_mtime)
                except (OSError, SaveError, ValueError, IndexError):
                    pass
            self._save_snapshot(decoded, digest, p.name, stat_before.st_mtime)
            self.current = decoded
            self.current_digest = digest
            self.file_stamp = stamp
            when = datetime.fromtimestamp(stat_before.st_mtime).strftime('%d/%m/%Y %H:%M:%S')
            self.sidebar_player.set(decoded['name'])
            self.sidebar_subtitle.set(f'Sauvegarde v{decoded["version"]}\nMise à jour : {when}')
            self.status.set('Lecture valide • ' + when)
            self.refresh()
            self.refresh_notice.set('Dernière sauvegarde chargée : ' + when + ' • ' + p.name)
            return 'updated'
        except (OSError, SaveError, ValueError, IndexError, UnicodeError) as e:
            self.file_stamp = None
            self.status.set('Lecture différée : ' + str(e)[:120])
            if force:
                raise
            return 'error'

    def poll(self):
        if self.path:
            try:
                self.read_and_record()
            except Exception as e:
                self.status.set('Erreur de surveillance : ' + str(e)[:110])
        self.after(5000, self.poll)

    def _put(self, tree, rows):
        tree.delete(*tree.get_children())
        for i, vals in enumerate(rows):
            tree.insert('', 'end', values=vals, tags=('odd' if i % 2 else 'even',))

    def refresh(self):
        if not self.current:
            return
        p = self.current
        g = self.group.get()
        if g not in GROUPS:
            return
        self.header_group.config(text=GROUP_FR.get(g, g))
        m = metrics(p, g)
        worlds = p['groups']['RawStats']['worlds']
        top_world = max(worlds.items(), key=lambda x: x[1])[0] if worlds else '—'
        self.quick_time.set(f"{fmt(m['world_hours'])} h")
        self.quick_world.set(top_world)

        metric_map = {
            'kills': fmt(m['kills']),
            'deaths': fmt(m['deaths']),
            'bosses': f"{m['bosses']} / 8",
            'crafted': fmt(m['crafted']),
            'built': fmt(m['built']),
            'picked_up': fmt(m['picked_up']),
            'world_hours': f"{fmt(m['world_hours'])} h",
            'recipes': fmt(p['recipes_count']),
        }
        for k, value in metric_map.items():
            if k in self.cards:
                self.cards[k].config(text=value)

        bosses = defeated_bosses(p, g)
        done = sum(v > 0 for v in bosses.values())
        self.dashboard_boss_line.config(text=f'{done} boss sur 8 validés dans la vue « {GROUP_FR.get(g, g)} ».')
        enemies = p['groups'][g]['enemies']
        kills_total = enemies[0]
        if kills_total:
            top_enemy, top_value = max(kills_total.items(), key=lambda x: x[1])
            self.dashboard_killer_line.config(text=f'Top victime : {clean_name(top_enemy)}  •  {fmt(top_value)}')
        else:
            self.dashboard_killer_line.config(text='Aucune élimination enregistrée dans cette vue.')
        for name, val in bosses.items():
            self.boss_rows[name].config(text=f'✓  {val}×' if val else '—', fg=GREEN if val else MUTED)

        world_lines = '\n'.join(f'  • {k} : {v / 3600:.1f} h' for k, v in sorted(worlds.items(), key=lambda x: -x[1])[:8])
        info = (
            f"Compétences connues : {len(p['skills'])}\n"
            f"Objets dans l’inventaire sauvegardé : {len(p['inventory'])}\n"
            f"Recettes connues : {p['recipes_count']}\n"
            f"Biomes découverts : {len(p['known_biomes'])}\n"
            f"Santé à la dernière sauvegarde : {p['health']:.1f}/{p['max_health']:.1f}\n"
            f"Endurance max sauvegardée : {p['max_stamina']:.1f}\n"
            f"Trophées connus : {p['known_trophies']}\n"
            f"\nTemps par monde (données brutes) :\n{world_lines or '  • Aucun monde enregistré'}\n\n"
            'Les compteurs de combats, récolte, fabrication et construction\n'
            'restent cumulés sur tous les mondes de ce personnage.'
        )
        self.summary_text.config(text=info)
        if self.old:
            oldworld = self.old['groups']['RawStats']['worlds']
            shared_worlds = set(worlds) & set(oldworld)
            if shared_worlds:
                name = max(shared_worlds, key=lambda w: worlds[w])
                delta = worlds[name] - oldworld[name]
                self.previous_text.config(text=f'Différence détectée avec le fichier .old sur {name} : {delta / 60:+.1f} min')
            else:
                self.previous_text.config(text='Sauvegarde précédente .old analysée.')
        else:
            self.previous_text.config(text='')

        # Combats
        combat_term = self.search_combat.get().strip().lower()
        combat_rows = []
        names = set().union(*[set(d) for d in enemies])
        for token in names:
            label = clean_name(token)
            if combat_term and combat_term not in label.lower() and combat_term not in token.lower():
                continue
            counts = [int(round(d.get(token, 0))) for d in enemies]
            combat_rows.append((label,) + tuple(fmt(x) for x in counts))
        combat_rows.sort(key=lambda x: -int(x[1].replace(' ', '')))
        self._put(self.combat_table, combat_rows)
        self.combat_cards['kills'][0].config(text=fmt(m['kills']))
        self.combat_cards['kills'][1].config(text='Total toutes victimes')
        self.combat_cards['unique'][0].config(text=fmt(len(names)))
        self.combat_cards['unique'][1].config(text='Entrées distinctes du bestiaire')
        if combat_rows:
            self.combat_cards['top'][0].config(text=combat_rows[0][0])
            self.combat_cards['top'][1].config(text=f'{combat_rows[0][1]} éliminations')
        else:
            self.combat_cards['top'][0].config(text='—')
            self.combat_cards['top'][1].config(text='Aucune donnée')

        # Activités
        section = SECTIONS.get(self.activity.get(), 'pickables')
        activity_rows = build_activity_rows(p, g, section, self.search_activity.get())
        self._put(self.activity_table, [(r['category'], r['label'], fmt(r['value'])) for r in activity_rows])
        highlights = activity_highlights(activity_rows)
        self.activity_cards['quantity'][0].config(text=fmt(highlights['quantity']))
        self.activity_cards['quantity'][1].config(text='Quantité totale visible')
        self.activity_cards['types'][0].config(text=fmt(highlights['types']))
        self.activity_cards['types'][1].config(text='Entrées distinctes filtrées')
        self.activity_cards['top'][0].config(text=highlights['top_name'])
        self.activity_cards['top'][1].config(text=f"{fmt(highlights['top_value'])} unité(s)")
        self.activity_cards['dominant'][0].config(text=highlights['dominant'])
        self.activity_cards['dominant'][1].config(text=f"{fmt(highlights['dominant_value'])} au total")
        cat_summary = summarize_categories(activity_rows)
        self._put(self.activity_group_table, [(name, fmt(value), f'{pct:.0f} %') for name, value, pct in cat_summary])
        self.activity_summary.config(text=(
            f"Section affichée : {self.activity.get()}\n"
            f"Vue nettoyée : chaque ligne reçoit une famille utile (bois, métaux, nourriture, etc.).\n"
            f"Cela rend les stats plus lisibles pour repérer rapidement les ressources que tu farmes le plus."
        ))

        # Compétences
        skills = []
        for name, item in sorted(p['skills'].items(), key=lambda x: (-x[1]['level'], x[0])):
            req = (int(item['level']) + 1) ** 1.5 * 0.5 + 0.5
            pct = 100 * item['xp'] / req if req else 0
            skills.append((name, f"{item['level']:.2f}".replace('.', ','), fmt(item['xp']), f'{min(100, max(0, pct)):.0f} %'))
        self._put(self.skill_table, skills)
        best = sorted(p['skills'].items(), key=lambda item: -item[1]['level'])[:3]
        for idx, key in enumerate(('best1', 'best2', 'best3')):
            if idx < len(best):
                name, value = best[idx]
                self.skill_cards[key][0].config(text=name)
                self.skill_cards[key][1].config(text=f"{value['level']:.1f} / 100")
            else:
                self.skill_cards[key][0].config(text='—')
                self.skill_cards[key][1].config(text='Aucune donnée')
        self.skills_summary.config(text='Compétences les plus développées :  ' + '   ·   '.join(f'{name} {value["level"]:.1f}' for name, value in best))

        # Raw stats
        search = self.search_raw.get().strip().lower()
        rows = []
        non_zero = 0
        for index, val in enumerate(p['groups'][g]['stats']):
            nm = ('Décès · Deaths' if index == 0 else (DEATH_KINDS.get(index, '') + ' · ' if index in DEATH_KINDS else '') + PLAYER_STAT_NAMES[index])
            if val:
                non_zero += 1
            if search and search not in nm.lower() and search not in str(index):
                continue
            rows.append((str(index), nm, fmt(val)))
        self._put(self.raw_table, rows)
        self.raw_summary.config(text=f'{non_zero} compteur(s) non nuls sur 205 dans la vue « {GROUP_FR.get(g, g)} ». Utilise la recherche pour retrouver rapidement un index précis.')

        self.refresh_bosses()
        self.refresh_achievements()
        self.draw_history()

    def refresh_bosses(self):
        if not self.current or not hasattr(self, 'boss_table'):
            return
        matrix = boss_matrix(self.current)
        group = self.boss_difficulty.get()
        self.boss_group_text.config(text=GROUP_FR.get(group, group))
        for difficulty, value in self.boss_cards.items():
            value.config(text=f'{sum(x[difficulty] > 0 for x in matrix.values())} / 8')
        tree = self.boss_table
        tree.delete(*tree.get_children())
        for row in matrix.values():
            completed = row[group] > 0
            vals = (('✓ ' if completed else '○ ') + row['name'], fmt(row['Any']), fmt(row['Default']),
                    fmt(row['Hard']), fmt(row['VeryHard']), fmt(row['Hardcore']), fmt(row[group + '_unarmed']))
            tree.insert('', 'end', values=vals, tags=('completed' if completed else 'missing',))

    def draw_history(self):
        if not hasattr(self, 'chart') or not self.current:
            return
        c = self.chart
        c.delete('all')
        self._history_points = []
        w, h = max(480, c.winfo_width()), max(300, c.winfo_height())
        rows = sample_rows(self.db, self.current['name'])
        if not rows:
            c.create_text(w / 2, h / 2, text='Aucun relevé enregistré', fill=MUTED, font=('Segoe UI', 13))
            return
        metric = METRICS.get(self.metric.get(), 'kills')
        group = self.history_group.get()
        changes = self.history_mode.get() == 'Gains entre sauvegardes'
        series = history_series(rows, metric, group, CHART_PERIODS.get(self.history_period.get()), changes)
        if not series:
            c.create_text(w / 2, h / 2, text='Aucun relevé sur cette période', fill=MUTED, font=('Segoe UI', 13))
            self.history_info.config(text='Modifie la période sélectionnée pour afficher des données.')
            return
        left, top, right, bottom = 88, 52, w - 28, h - 72
        values = [point[1] for point in series]
        minimum, maximum = min(values), max(values)
        if changes:
            minimum = min(minimum, 0)
            maximum = max(maximum, 0)
        if minimum == maximum:
            pad = max(1, abs(minimum) * 0.08)
            minimum -= pad
            maximum += pad
        else:
            pad = (maximum - minimum) * 0.10
            minimum -= pad
            maximum += pad
        c.create_rectangle(left, top, right, bottom, fill=BG_ALT, outline='')
        for i in range(5):
            value = minimum + (maximum - minimum) * i / 4
            y = bottom - (bottom - top) * i / 4
            c.create_line(left, y, right, y, fill=BORDER, dash=(3, 4))
            c.create_text(left - 12, y, text=fmt(value), fill=MUTED, anchor='e', font=('Segoe UI', 9))
        first, last = series[0][0], series[-1][0]
        span = max(1, last - first)
        coordinates = []
        for timestamp, value, filename in series:
            x = left + (right - left) * ((timestamp - first) / span if len(series) > 1 and last > first else 0.5)
            y = bottom - (value - minimum) / (maximum - minimum) * (bottom - top)
            coordinates.append((x, y, timestamp, value, filename))
        if changes:
            zero = bottom - (0 - minimum) / (maximum - minimum) * (bottom - top)
            c.create_line(left, zero, right, zero, fill=MUTED, width=1)
            bar_width = max(3, min(22, (right - left) / max(1, len(series)) * 0.6))
            for x, y, _, value, _ in coordinates:
                c.create_rectangle(x - bar_width / 2, min(y, zero), x + bar_width / 2, max(y, zero) + 0.5,
                                   fill=GREEN if value >= 0 else RED, outline='')
        else:
            pts = [coord for x, y, *_ in coordinates for coord in (x, y)]
            if len(pts) >= 4:
                c.create_line(*pts, fill=ACCENT, width=3, smooth=False)
            if len(coordinates) <= 125:
                for x, y, *_ in coordinates:
                    c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=ACCENT2, outline=BG_ALT)
        for i in range(5 if last > first else 1):
            fraction = i / 4 if last > first else .5
            timestamp = first + (last - first) * fraction
            x = left + (right - left) * fraction
            c.create_text(x, bottom + 22, text=datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M'), fill=MUTED, font=('Segoe UI', 8))
        c.create_text(left, 20, text=f'{self.metric.get()} • {GROUP_FR.get(group, group)}', fill=FG, anchor='w', font=('Segoe UI Semibold', 11))
        self._history_points = coordinates
        first_value = history_metric(rows[0][3], metric, group)
        last_value = history_metric(rows[-1][3], metric, group)
        self.history_info.config(text=f'{len(series)} relevé(s) affiché(s) sur {len(rows)} • Dernière valeur : {fmt(last_value)} • Évolution depuis le premier relevé : {fmt(last_value - first_value)} • Survole un point pour voir le détail.')

    def _history_hover(self, event):
        points = self._history_points
        if not points:
            return
        x, y, stamp, value, filename = min(points, key=lambda p: abs(p[0] - event.x))
        if abs(x - event.x) > 26:
            self.chart.delete('tooltip')
            return
        self.chart.delete('tooltip')
        line = f'{datetime.fromtimestamp(stamp):%d/%m/%Y %H:%M}  ·  {fmt(value)}'
        if self.history_mode.get() == 'Gains entre sauvegardes':
            line += ' (variation)'
        line2 = f'Fichier : {filename}'
        tw = max(240, len(line) * 7)
        th = 46
        tx = min(max(10, x + 12), max(10, self.chart.winfo_width() - tw - 15))
        ty = max(10, y - 52)
        self.chart.create_rectangle(tx, ty, tx + tw, ty + th, fill='#25415f', outline=ACCENT, tags='tooltip')
        self.chart.create_text(tx + 8, ty + 15, text=line, anchor='w', fill=FG, font=('Segoe UI', 9), tags='tooltip')
        self.chart.create_text(tx + 8, ty + 31, text=line2, anchor='w', fill=MUTED, font=('Segoe UI', 8), tags='tooltip')

    def export_csv(self):
        if not self.current:
            return
        rows = sample_rows(self.db, self.current['name'])
        if not rows:
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')],
             initialfile='valheim_stats_historique.csv')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f, delimiter=';')
            wr.writerow(['date', 'fichier', 'groupe'] + list(METRICS))
            for _, stamp, filename, p in rows:
                for g in ['Any', 'Default', 'Hard']:
                    m = metrics(p, g)
                    wr.writerow([datetime.fromtimestamp(stamp).isoformat(timespec='seconds'), filename, g]
                                + [m[key] for key in METRICS.values()])
        messagebox.showinfo(APP_NAME, 'CSV exporté :\n' + path)

    def close(self):
        self.db.close()
        self.destroy()



def main():
    import argparse
    parser = argparse.ArgumentParser(description='Valheim Stats Tracker sans mod, lecture seule')
    parser.add_argument('character', nargs='?', help='Chemin du personnage .fch')
    parser.add_argument('--headless', action='store_true', help='Vérifier et afficher les statistiques en terminal')
    args = parser.parse_args()
    if args.headless:
        path = args.character or default_save()
        if not path:
            parser.error('Indiquer le chemin vers un fichier .fch')
        p = decode(Path(path).read_bytes())
        print(json.dumps({'name': p['name'], 'version': p['version'], 'metrics': metrics(p),
                          'bosses_normal': defeated_bosses(p, 'Default'),
                          'bosses_hard': defeated_bosses(p, 'Hard'),
                          'skills': p['skills'],
                          'worlds': p['groups']['RawStats']['worlds']}, ensure_ascii=False, indent=2))
        return
    TrackerApp(args.character or '').mainloop()


if __name__ == '__main__':
    main()
