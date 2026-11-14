"""Valheim Stats Tracker V1.4 — application de bureau sans mod (stdlib Python)."""
import csv
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

from valheim_reader import (BOSSES, DEATH_KINDS, GROUPS, SaveError,
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
    'Vue d’ensemble', 'Boss', 'Combats', 'Activités', 'Compétences', 'Historique', 'Compteurs bruts'
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
    return ' '.join(name.split())



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
        self.page_var = tk.StringVar(value='Vue d’ensemble')
        self.group = tk.StringVar(value='Any')
        self.search_combat = tk.StringVar()
        self.search_activity = tk.StringVar()
        self.search_raw = tk.StringVar()
        self.activity = tk.StringVar(value='Ressources collectées')
        self.metric = tk.StringVar(value='Créatures tuées')
        self.history_group = tk.StringVar(value='Any')
        self.history_period = tk.StringVar(value='Tous les relevés')
        self.history_mode = tk.StringVar(value='Total cumulé')
        self.boss_difficulty = tk.StringVar(value='Default')
        self._history_points = []
        self.status = tk.StringVar(value='Choisis une sauvegarde pour commencer.')
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
                         activebackground=PANEL_SOFT, activeforeground=FG, relief='flat', bd=0,
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
        self.show_page('Vue d’ensemble')

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
        ttk.Combobox(row, textvariable=self.group, values=['Any', 'Default', 'Hard', 'VeryHard', 'Hardcore', 'RawStats'], width=13, state='readonly').pack(side='right')
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
        self._button(tools, 'Changer de personnage', self.pick_file).pack(fill='x', pady=(0, 8))
        self._button(tools, 'Actualiser maintenant', lambda: self.read_and_record(force=True), accent=True).pack(fill='x')
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
        self._boss_ui()
        self._combat_ui()
        self._activity_ui()
        self._skills_ui()
        self._history_ui()
        self._raw_ui()

    def show_page(self, name):
        self.page_var.set(name)
        title_map = {
            'Vue d’ensemble': ('Vue d’ensemble', 'Les statistiques essentielles de ton personnage en un coup d’œil.'),
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

    def _boss_ui(self):
        tab = self.pages['Boss']
        top = tk.Frame(tab, bg=BG)
        top.pack(fill='x', pady=(0, 12))
        shell, inner = self._panel(top, 'Suivi des boss', 'Choisis une difficulté pour contrôler le statut de validation.')
        shell.pack(fill='x')
        row = tk.Frame(inner, bg=PANEL)
        row.pack(fill='x')
        lbl(row, 'Difficulté suivie', 10, MUTED).pack(side='left')
        ttk.Combobox(row, textvariable=self.boss_difficulty,
                     values=['Any', 'Default', 'Hard', 'VeryHard', 'Hardcore'],
                     width=14, state='readonly').pack(side='left', padx=(10, 0))
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
        ttk.Combobox(bar, textvariable=self.history_group, values=['Any', 'Default', 'Hard', 'RawStats'], state='readonly', width=14).pack(side='left')
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

    def read_and_record(self, force=False):
        if not self.path:
            return
        p = Path(self.path)
        try:
            stat_before = p.stat()
            stamp = (stat_before.st_mtime_ns, stat_before.st_size)
            if stamp == self.file_stamp and not force:
                return
            raw = p.read_bytes()
            stat_after = p.stat()
            if (stat_after.st_mtime_ns, stat_after.st_size) != stamp:
                self.status.set('Écriture en cours : nouvelle tentative dans 5 secondes')
                return
            digest = hashlib.sha256(raw).hexdigest()
            if digest == self.current_digest and not force:
                self.file_stamp = stamp
                return
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
        except (OSError, SaveError, ValueError, IndexError, UnicodeError) as e:
            self.file_stamp = None
            self.status.set('Lecture différée : ' + str(e)[:120])
            if force:
                raise

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
            nm = 'Décès' if index == 0 else DEATH_KINDS.get(index, f'Compteur #{index:03d} (non identifié)')
            if val:
                non_zero += 1
            if search and search not in nm.lower() and search not in str(index):
                continue
            rows.append((str(index), nm, fmt(val)))
        self._put(self.raw_table, rows)
        self.raw_summary.config(text=f'{non_zero} compteur(s) non nuls sur 205 dans la vue « {GROUP_FR.get(g, g)} ». Utilise la recherche pour retrouver rapidement un index précis.')

        self.refresh_bosses()
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
