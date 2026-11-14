"""Valheim Stats Tracker V1.3 — application de bureau sans mod (stdlib Python)."""
import csv
import queue
import threading
import hashlib
import json
import os
import sqlite3
import sys
import tkinter as tk
import zlib
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import updater

from valheim_reader import (BOSSES, DEATH_KINDS, GROUPS, MODIFIERS, SaveError,
                            defeated_bosses, decode, metrics, pretty_key,
                            total_kills)

APP_NAME = 'Valheim Stats Tracker'
BG, PANEL, PANEL2, BORDER = '#0d1420', '#172232', '#1d2b3f', '#304156'
FG, MUTED, ACCENT, GREEN, GOLD = '#e9f1fa', '#9bafc6', '#73c6f8', '#65dba6', '#f3c76e'
GROUP_FR = {'RawStats':'Brut (tous)', 'Any':'Toutes difficultés', 'Default':'Normal ou +',
            'Hard':'Difficile ou +', 'VeryHard':'Très difficile ou +',
            'Hardcore':'Extrême', 'Casual':'Détendu ou +', 'VeryEasy':'Très facile ou +',
            'Easy':'Facile ou +', 'Hammer':'Marteau'}
SECTIONS = {
    'Objets fabriqués':'crafted', 'Objets ramassés':'picked_up',
    'Éléments placés':'pieces_built', 'Ressources collectées':'pickables',
    'Nourritures consommées':'foods_eaten'
}
METRICS = {'Créatures tuées':'kills','Décès':'deaths','Boss différents':'bosses',
           'Objets fabriqués':'crafted','Éléments placés':'built',
           'Objets ramassés':'picked_up','Temps de jeu (h)':'world_hours',
           'Magie élémentaire (niveau)':'skill:Magie élémentaire',
           'Magie du sang (niveau)':'skill:Magie du sang',
           'Poings (niveau)':'skill:Poings',
           'Course (niveau)':'skill:Course',
           'Épées (niveau)':'skill:Épées'}
CHART_PERIODS = {'Tous les relevés': None, '7 derniers jours': 7,
                 '30 derniers jours': 30, '90 derniers jours': 90}


def history_metric(snapshot, key, difficulty='Any'):
    """Valeur cumulative fiable d'un relevé ; les niveaux ignorent la difficulté."""
    if key.startswith('skill:'):
        return float(snapshot.get('skills', {}).get(key[6:], {}).get('level', 0))
    return metrics(snapshot, difficulty)[key]


def history_series(rows, key, difficulty='Any', period_days=None, changes=False):
    """[(timestamp, valeur, fichier)] chronologique. Variations entre deux sauvegardes.

    Le calcul du delta se fait AVANT le filtrage pour conserver le point précédent.
    Les périodes sont mesurées depuis le dernier relevé disponible.
    """
    ordered = sorted(rows, key=lambda row: (row[1], row[0]))
    series = []
    previous = None
    for _, timestamp, filename, snapshot in ordered:
        value = history_metric(snapshot, key, difficulty)
        delta = value-previous if previous is not None else 0
        series.append((timestamp, delta if changes else value, filename))
        previous = value
    if period_days is not None and series:
        threshold = series[-1][0] - 86400*period_days
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
            # Ce compteur représente la catégorie de l'élimination, PAS une preuve
            # que tout le combat a été effectué uniquement aux poings.
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
    matches.extend((Path.home()/'AppData/LocalLow/IronGate/Valheim/characters_local').glob('*.fch'))
    matches = [p for p in matches if '_backup' not in p.name.lower() and p.is_file()]
    if matches: return str(max(matches,key=lambda p:p.stat().st_mtime))
    return ''


def db_open():
    db = sqlite3.connect(app_dir()/'historique.sqlite3')
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
    return [(n, t, f, json.loads(zlib.decompress(data)))
            for n, t, f, data in db.execute(
                'SELECT id,observed_at,filename,data FROM snapshots WHERE character=? ORDER BY observed_at, id', (character,))]


def fmt(v):
    if isinstance(v,float) and not v.is_integer(): return f'{v:,.1f}'.replace(',',' ').replace('.',',')
    return f'{int(v):,}'.replace(',',' ')


def lbl(parent, text, size=11, color=FG, bold=False, **kw):
    return tk.Label(parent,text=text,fg=color,bg=parent.cget('bg'),font=('Segoe UI',size,'bold' if bold else 'normal'),**kw)


class TrackerApp(tk.Tk):
    def __init__(self, initial=''):
        super().__init__()
        self.title(f'Valheim Stats Tracker • V{updater.current_version()}')
        self.geometry('1210x820')
        self.minsize(950,650)
        self.configure(bg=BG)
        self.db=db_open()
        self.path=''
        self.current=None
        self.current_digest=''
        self.file_stamp=None
        self.old=None
        self.tables={}
        self.group=tk.StringVar(value='Any')
        self.search_combat=tk.StringVar()
        self.search_activity=tk.StringVar()
        self.search_raw=tk.StringVar()
        self.activity=tk.StringVar(value='Objets fabriqués')
        self.metric=tk.StringVar(value='Créatures tuées')
        self.history_group=tk.StringVar(value='Any')
        self.history_period=tk.StringVar(value='Tous les relevés')
        self.history_mode=tk.StringVar(value='Total cumulé')
        self.boss_difficulty=tk.StringVar(value='Default')
        self._history_points=[]
        self.status=tk.StringVar(value='Choisis une sauvegarde pour commencer.')
        self.update_events=queue.Queue()
        self.update_window=None
        self.update_manifest=None
        self.update_busy=False
        self.updater_notice=tk.StringVar(value='')
        self._style()
        self._ui()
        for var in (self.group,self.search_combat,self.activity,self.search_activity,self.search_raw):
            var.trace_add('write',lambda *a:self.refresh())
        self.metric.trace_add('write',lambda *a:self.draw_history())
        self.history_group.trace_add('write',lambda *a:self.draw_history())
        self.history_period.trace_add('write',lambda *a:self.draw_history())
        self.history_mode.trace_add('write',lambda *a:self.draw_history())
        self.boss_difficulty.trace_add('write',lambda *a:self.refresh_bosses())
        config=app_dir()/'config.json'
        try: saved=json.loads(config.read_text(encoding='utf-8')).get('path','')
        except (OSError,ValueError):saved=''
        requested = initial or (saved if saved and Path(saved).is_file() else '') or default_save()
        if requested: self.open_file(requested)
        self.after(5000,self.poll)
        self.after(200,self._update_pump)
        self.after(2200,self._startup_update_check)
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _style(self):
        s=ttk.Style(self)
        s.theme_use('clam')
        s.configure('TNotebook',background=BG,borderwidth=0,tabmargins=(0,0,0,0))
        s.configure('TNotebook.Tab',background=PANEL,foreground=MUTED,padding=(16,10),font=('Segoe UI',10))
        s.map('TNotebook.Tab',background=[('selected',PANEL2)],foreground=[('selected',ACCENT)])
        s.configure('Treeview',background=PANEL,foreground=FG,fieldbackground=PANEL,
                    font=('Segoe UI',10),rowheight=28,borderwidth=0)
        s.configure('Treeview.Heading',background=PANEL2,foreground=FG,relief='flat',font=('Segoe UI',10,'bold'))
        s.map('Treeview',background=[('selected','#335371')],foreground=[('selected','white')])
        s.configure('TCombobox',fieldbackground=PANEL2,background=PANEL2,foreground=FG,arrowcolor=FG,padding=5)
        s.map('TCombobox',fieldbackground=[('readonly',PANEL2)],foreground=[('readonly',FG)])
        s.configure('TScrollbar',background=PANEL2,troughcolor=PANEL)
        s.configure('TEntry',fieldbackground=PANEL2,foreground=FG,padding=5)

    def _button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg=PANEL2,fg=FG,
                         activebackground='#2a4564',activeforeground=FG,relief='flat',
                         bd=0,padx=14,pady=8,font=('Segoe UI',10),cursor='hand2')

    def _ui(self):
        header=tk.Frame(self,bg=BG)
        header.pack(fill='x',padx=24,pady=(18,10))
        title=tk.Frame(header,bg=BG)
        title.pack(side='left')
        lbl(title,'VALHEIM   /   STATS TRACKER',16,FG,True).pack(anchor='w')
        lbl(title,f'V{updater.current_version()} • lecture seule • sans mod • suivi après sauvegarde',9,MUTED).pack(anchor='w',pady=(2,0))
        self._button(header,'Changer de personnage',self.pick_file).pack(side='right',padx=(8,0))
        self._button(header,'Mises à jour',self.show_updater).pack(side='right',padx=(8,0))
        self._button(header,'Actualiser',lambda:self.read_and_record(force=True)).pack(side='right')
        inf=tk.Frame(self,bg=PANEL,padx=16,pady=11)
        inf.pack(fill='x',padx=24,pady=(0,12))
        self.player_label=lbl(inf,'Aucun personnage chargé',12,FG,True)
        self.player_label.pack(side='left')
        lbl(inf,'Difficulté :',10,MUTED).pack(side='left',padx=(30,8))
        self.group_box=ttk.Combobox(inf,textvariable=self.group,values=['Any','Default','Hard','VeryHard','Hardcore','RawStats'],width=15,state='readonly')
        self.group_box.pack(side='left')
        self.group_fr=lbl(inf,'Toutes difficultés',10,MUTED)
        self.group_fr.pack(side='left',padx=(10,0))
        self.notebook=ttk.Notebook(self)
        self.notebook.pack(fill='both',expand=True,padx=24,pady=(0,8))
        self.tabs={}
        for name in ('Vue d’ensemble','Boss','Combats','Activités','Compétences','Historique','Compteurs bruts'):
            panel=tk.Frame(self.notebook,bg=BG)
            self.notebook.add(panel,text=name)
            self.tabs[name]=panel
        self._dashboard_ui()
        self._boss_ui()
        self._combat_ui()
        self._activity_ui()
        self._skills_ui()
        self._history_ui()
        self._raw_ui()
        footer=tk.Frame(self,bg=BG)
        footer.pack(fill='x',padx=24,pady=(0,14))
        lbl(footer,'●',10,GREEN).pack(side='left')
        lbl(footer,'Suivi automatique toutes les 5 s • source jamais modifiée',9,MUTED).pack(side='left',padx=(6,16))
        tk.Label(footer,textvariable=self.status,fg=ACCENT,bg=BG,font=('Segoe UI',9)).pack(side='right')

    def _card(self,parent,name):
        p=tk.Frame(parent,bg=PANEL,padx=17,pady=13,highlightthickness=1,highlightbackground=BORDER)
        lbl(p,name.upper(),9,MUTED,True).pack(anchor='w')
        value=lbl(p,'—',25,FG,True)
        value.pack(anchor='w',pady=(6,0))
        return p,value

    def _dashboard_ui(self):
        tab=self.tabs['Vue d’ensemble']
        cards=tk.Frame(tab,bg=BG)
        cards.pack(fill='x',padx=8,pady=(14,12))
        self.cards={}
        items=[('kills','Créatures tuées'),('deaths','Décès'),('bosses','Boss différents'),
               ('crafted','Objets fabriqués'),('built','Éléments placés'),('world_hours','Temps de jeu')]
        for i,(key,name) in enumerate(items):
            p,v=self._card(cards,name)
            p.grid(row=i//3,column=i%3,padx=5,pady=5,sticky='ew')
            cards.grid_columnconfigure(i%3,weight=1,uniform='cards')
            self.cards[key]=v
        bottom=tk.Frame(tab,bg=BG)
        bottom.pack(fill='both',expand=True,padx=13,pady=(5,10))
        left=tk.Frame(bottom,bg=PANEL,padx=16,pady=12)
        left.pack(side='left',fill='both',expand=True,padx=(0,6))
        right=tk.Frame(bottom,bg=PANEL,padx=16,pady=12)
        right.pack(side='left',fill='both',expand=True,padx=(6,0))
        lbl(left,'LES HUIT BOSS',12,FG,True).pack(anchor='w',pady=(0,8))
        self.boss_rows={}
        for boss in BOSSES.values():
            line=tk.Frame(left,bg=PANEL)
            line.pack(fill='x',pady=3)
            lbl(line,boss,10,FG).pack(side='left')
            v=lbl(line,'—',10,MUTED,True)
            v.pack(side='right')
            self.boss_rows[boss]=v
        lbl(right,'DÉTAIL DU PERSONNAGE',12,FG,True).pack(anchor='w',pady=(0,10))
        self.summary_text=lbl(right,'—',10,MUTED,False,justify='left',anchor='nw')
        self.summary_text.pack(fill='both')
        self.previous_text=lbl(right,'',10,ACCENT,False,justify='left',anchor='w')
        self.previous_text.pack(anchor='w',pady=(18,0))

    def _boss_ui(self):
        tab=self.tabs['Boss']
        head=tk.Frame(tab,bg=BG)
        head.pack(fill='x',padx=12,pady=(16,10))
        lbl(head,'PROGRESSION DES BOSS',15,FG,True).pack(side='left')
        lbl(head,'Difficulté suivie :',10,MUTED).pack(side='left',padx=(28,7))
        ttk.Combobox(head,textvariable=self.boss_difficulty,
                     values=['Any','Default','Hard','VeryHard','Hardcore'],
                     width=14,state='readonly').pack(side='left')
        self.boss_group_text=lbl(head,'',10,MUTED)
        self.boss_group_text.pack(side='left',padx=10)
        counters=tk.Frame(tab,bg=BG)
        counters.pack(fill='x',padx=10,pady=(0,12))
        self.boss_cards={}
        for i,(group,name) in enumerate((('Default','Normal ou +'),('Hard','Difficile ou +'),
                                         ('VeryHard','Très difficile ou +'),('Hardcore','Extrême'))):
            card,value=self._card(counters,name)
            card.grid(row=0,column=i,sticky='ew',padx=4)
            counters.grid_columnconfigure(i,weight=1,uniform='bosscards')
            self.boss_cards[group]=value
        self.boss_table=self._mk_table(tab,
              ('Boss','Total','Normal +','Difficile +','Très difficile +','Extrême','Poings*'),
              {'Boss':190,'Total':80,'Normal +':95,'Difficile +':105,
               'Très difficile +':120,'Extrême':90,'Poings*':90})
        self.boss_table.tag_configure('completed',background='#14342e',foreground=GREEN)
        self.boss_table.tag_configure('missing',background=PANEL,foreground=FG)
        lbl(tab,'* Poings : éliminations enregistrées dans cette catégorie à la difficulté sélectionnée. '
                'Cela ne prouve pas que tout le combat a été effectué à mains nues.',
            9,MUTED,wraplength=1050,justify='left').pack(anchor='w',padx=13,pady=(0,5))
        lbl(tab,'Les groupes de difficulté se recouvrent : ils ne sont pas additionnables. '
                'Aucune information fiable sur un combat réalisé entièrement en solo.',
            9,MUTED,wraplength=1050,justify='left').pack(anchor='w',padx=13,pady=(0,12))

    def refresh_bosses(self):
        if not self.current or not hasattr(self,'boss_table'):return
        matrix=boss_matrix(self.current)
        group=self.boss_difficulty.get()
        self.boss_group_text.config(text=GROUP_FR.get(group,group))
        for difficulty,value in self.boss_cards.items():
            value.config(text=f'{sum(x[difficulty]>0 for x in matrix.values())} / 8')
        tree=self.boss_table
        tree.delete(*tree.get_children())
        for row in matrix.values():
            completed=row[group]>0
            vals=(('✓ ' if completed else '○ ')+row['name'],fmt(row['Any']),
                  fmt(row['Default']),fmt(row['Hard']),fmt(row['VeryHard']),
                  fmt(row['Hardcore']),fmt(row[group+'_unarmed']))
            tree.insert('','end',values=vals,tags=('completed' if completed else 'missing',))

    def _mk_table(self, parent, columns, widths=None):
        area=tk.Frame(parent,bg=BG)
        area.pack(fill='both',expand=True,padx=8,pady=(4,8))
        table=ttk.Treeview(area,columns=columns,show='headings',selectmode='browse')
        widths=widths or {}
        for col in columns:
            table.heading(col,text=col,command=lambda c=col:self._sort_table(table,c,False))
            table.column(col,width=widths.get(col,140),anchor='w' if col==columns[0] else 'e')
        scroll=ttk.Scrollbar(area,orient='vertical',command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.tag_configure('odd',background='#1b2a3d')
        table.tag_configure('even',background=PANEL)
        table.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y')
        return table

    def _sort_table(self,t,col,reverse):
        def key(item):
            v=t.set(item,col).replace(' ','').replace(',','.')
            try:return (0,float(v))
            except ValueError:return (1,v.lower())
        items=sorted(t.get_children(''),key=key,reverse=reverse)
        for idx,item in enumerate(items):t.move(item,'',idx)
        t.heading(col,command=lambda:self._sort_table(t,col,not reverse))

    def _search_field(self,parent,var,placeholder):
        line=tk.Frame(parent,bg=BG)
        line.pack(fill='x',padx=8,pady=(10,3))
        lbl(line,placeholder,10,MUTED).pack(side='left',padx=(0,10))
        ttk.Entry(line,textvariable=var,width=36).pack(side='left')
        return line

    def _combat_ui(self):
        tab=self.tabs['Combats']
        self._search_field(tab,self.search_combat,'Filtrer les créatures :')
        self.combat_table=self._mk_table(tab,('Créature','Total','Poings','Magie','Distance','Mêlée'),{'Créature':280})
        lbl(tab,'Un compteur de victime ne prouve pas qu’un combat complet a été effectué exclusivement aux poings.',9,MUTED).pack(anchor='w',padx=12,pady=(0,8))

    def _activity_ui(self):
        tab=self.tabs['Activités']
        bar=self._search_field(tab,self.search_activity,'Filtrer les entrées :')
        ttk.Combobox(bar,textvariable=self.activity,values=list(SECTIONS),state='readonly',width=26).pack(side='right')
        self.activity_table=self._mk_table(tab,('Élément','Quantité'),{'Élément':550,'Quantité':130})

    def _skills_ui(self):
        tab=self.tabs['Compétences']
        lbl(tab,'Niveaux sauvegardés — progression suivie par les relevés, sans lecture en direct.',10,MUTED).pack(anchor='w',padx=14,pady=(12,5))
        self.skills_summary=lbl(tab,'',10,ACCENT)
        self.skills_summary.pack(anchor='w',padx=14,pady=(0,4))
        self.skill_table=self._mk_table(tab,('Compétence','Niveau','XP vers le suivant','Progression'),{'Compétence':300})

    def _history_ui(self):
        tab=self.tabs['Historique']
        bar=tk.Frame(tab,bg=BG)
        bar.pack(fill='x',padx=10,pady=(12,4))
        lbl(bar,'Mesure',10,MUTED).pack(side='left',padx=(2,8))
        ttk.Combobox(bar,textvariable=self.metric,values=list(METRICS),width=24,state='readonly').pack(side='left')
        lbl(bar,'Difficulté',10,MUTED).pack(side='left',padx=(22,8))
        ttk.Combobox(bar,textvariable=self.history_group,values=['Any','Default','Hard','RawStats'],state='readonly',width=14).pack(side='left')
        self._button(bar,'Exporter CSV',self.export_csv).pack(side='right')
        options=tk.Frame(tab,bg=BG)
        options.pack(fill='x',padx=10,pady=(4,4))
        lbl(options,'Période',10,MUTED).pack(side='left',padx=(2,8))
        ttk.Combobox(options,textvariable=self.history_period,values=list(CHART_PERIODS),
                     width=19,state='readonly').pack(side='left')
        lbl(options,'Affichage',10,MUTED).pack(side='left',padx=(22,8))
        ttk.Combobox(options,textvariable=self.history_mode,
                     values=['Total cumulé','Gains entre sauvegardes'],
                     width=25,state='readonly').pack(side='left')
        self.chart=tk.Canvas(tab,bg=PANEL,highlightthickness=0,height=330)
        self.chart.pack(fill='both',expand=True,padx=12,pady=(10,4))
        self.chart.bind('<Configure>',lambda e:self.draw_history())
        self.chart.bind('<Motion>',self._history_hover)
        self.chart.bind('<Leave>',lambda e:self.chart.delete('tooltip'))
        self.history_info=lbl(tab,'',9,MUTED)
        self.history_info.pack(anchor='w',padx=12,pady=(3,10))

    def _raw_ui(self):
        tab=self.tabs['Compteurs bruts']
        self._search_field(tab,self.search_raw,'Filtrer par numéro ou nom :')
        self.raw_table=self._mk_table(tab,('Indice','Nom / correspondance connue','Valeur'),{'Indice':90,'Nom / correspondance connue':500})
        lbl(tab,'Les indices sans correspondance vérifiée restent volontairement non nommés.',9,MUTED).pack(anchor='w',padx=12,pady=(0,8))

    def pick_file(self):
        directory=str(Path(self.path).parent) if self.path else str(Path.home())
        path=filedialog.askopenfilename(title='Sélectionner le fichier de personnage Valheim',
              filetypes=[('Personnages Valheim','*.fch'),('Tous les fichiers','*.*')],initialdir=directory)
        if path:self.open_file(path)

    def open_file(self,path):
        path=str(Path(path).resolve())
        if not Path(path).is_file():
            messagebox.showerror(APP_NAME,'Fichier introuvable.');return
        self.path=path
        self.file_stamp=None
        self.current_digest=''
        try:
            self.read_and_record(force=True)
            (app_dir()/'config.json').write_text(json.dumps({'path':path},ensure_ascii=False,indent=2),encoding='utf8')
        except (OSError,SaveError,ValueError) as e:
            messagebox.showerror(APP_NAME,str(e))

    # Mise à jour : téléchargements en thread ; toute manipulation Tk reste dans le thread UI.
    def show_updater(self):
        if self.update_window and self.update_window.winfo_exists():
            self.update_window.lift()
            return
        win=tk.Toplevel(self)
        self.update_window=win
        win.title('Mises à jour — Valheim Stats Tracker')
        win.configure(bg=BG)
        win.geometry('730x520')
        win.minsize(660,485)
        win.transient(self)
        panel=tk.Frame(win,bg=BG,padx=22,pady=18)
        panel.pack(fill='both',expand=True)
        lbl(panel,f'VALHEIM TRACKER  /  VERSION {updater.current_version()}',14,FG,True).pack(anchor='w')
        lbl(panel,'Les données et sauvegardes du personnage restent intactes.',10,MUTED).pack(anchor='w',pady=(3,20))
        cfg=updater.read_config()
        lbl(panel,'Dépôt GitHub public (pseudo/nom-du-depot) :',10,FG,True).pack(anchor='w',pady=(0,5))
        self.github_repo=tk.StringVar(value=updater.repo_from_manifest_url(cfg['manifest_url']))
        repo_row=tk.Frame(panel,bg=BG)
        repo_row.pack(fill='x',pady=(0,14))
        ttk.Entry(repo_row,textvariable=self.github_repo).pack(side='left',fill='x',expand=True)
        self._button(repo_row,'Configurer GitHub',self._configure_github_repo).pack(side='right',padx=(8,0))
        lbl(panel,'Adresse HTTPS du manifeste (mode avancé) :',10,FG,True).pack(anchor='w',pady=(0,5))
        self.update_url=tk.StringVar(value=cfg['manifest_url'])
        self.update_autocheck=tk.BooleanVar(value=cfg['check_at_startup'])
        ttk.Entry(panel,textvariable=self.update_url).pack(fill='x')
        ttk.Checkbutton(panel,text='Vérifier au démarrage si une URL est configurée',variable=self.update_autocheck).pack(anchor='w',pady=(9,15))
        actions=tk.Frame(panel,bg=BG)
        actions.pack(fill='x')
        self._button(actions,'Enregistrer les paramètres',self._save_update_settings).pack(side='left',padx=(0,8))
        self._button(actions,'Vérifier en ligne',self._check_update_from_window).pack(side='left',padx=(0,8))
        self._button(actions,'Installer un ZIP local',self._install_local_zip).pack(side='left')
        tk.Frame(panel,bg=BORDER,height=1).pack(fill='x',pady=18)
        lbl(panel,'ÉTAT DES MISES À JOUR',10,MUTED,True).pack(anchor='w',pady=(0,8))
        tk.Label(panel,textvariable=self.updater_notice,wraplength=640,justify='left',bg=BG,fg=ACCENT,font=('Segoe UI',10)).pack(anchor='w',fill='x')
        self.install_remote_button=self._button(panel,'Télécharger et installer cette version',self._install_remote)
        if self.update_manifest and updater.parse_version(self.update_manifest['version'])>updater.parse_version(updater.current_version()):
            self.install_remote_button.pack(anchor='w',pady=(15,0))
        if not self.updater_notice.get():
            self.updater_notice.set('Aucune vérification effectuée. Définis une URL de manifeste ou sélectionne un ZIP local.')
        lbl(panel,'SHA-256 vérifié avant installation ; un backup du programme est conservé.',9,MUTED).pack(side='bottom',anchor='w')

    def _configure_github_repo(self):
        try:
            url=updater.github_manifest_url(self.github_repo.get())
            self.update_url.set(url)
            if self._save_update_settings():
                self.updater_notice.set('Dépôt GitHub configuré. Vérification de la dernière release…')
                self._check_updates(url)
        except updater.UpdateError as e:
            messagebox.showerror('Mises à jour',str(e),parent=self.update_window)

    def _save_update_settings(self):
        try:
            updater.save_config(self.update_url.get(),self.update_autocheck.get())
        except updater.UpdateError as e:
            messagebox.showerror('Mises à jour',str(e),parent=self.update_window)
            return False
        self.updater_notice.set('Paramètres enregistrés dans le dossier utilisateur.')
        return True

    def _check_update_from_window(self):
        if not self._save_update_settings(): return
        self._check_updates(self.update_url.get().strip())

    def _startup_update_check(self):
        cfg=updater.read_config()
        if cfg['check_at_startup'] and cfg['manifest_url']:
            self._check_updates(cfg['manifest_url'],quiet=True)

    def _check_updates(self,url,quiet=False):
        if self.update_busy:return
        if not url:
            self.updater_notice.set('Renseigne d’abord l’URL HTTPS de ton manifeste.')
            if not quiet:messagebox.showinfo('Mises à jour','Aucune URL configurée. Tu peux déjà installer un ZIP local.',parent=self.update_window or self)
            return
        self.update_busy=True
        self.updater_notice.set('Vérification de la version en ligne…')
        def work():
            try:
                result=updater.load_manifest(url)
                self.update_events.put(('checked',result,quiet))
            except Exception as e:
                self.update_events.put(('error',f'Vérification impossible : {e}',quiet))
        threading.Thread(target=work,daemon=True).start()

    def _install_remote(self):
        if self.update_busy or not self.update_manifest:return
        info=self.update_manifest
        if updater.parse_version(info['version'])<=updater.parse_version(updater.current_version()):return
        if not messagebox.askyesno('Mises à jour',f"Télécharger et installer Valheim Stats Tracker {info['version']} ?\n\n"
                                   'L’application redémarrera automatiquement. Tes données locales sont conservées.',parent=self.update_window or self):
            return
        self.update_busy=True
        self.updater_notice.set(f"Téléchargement de la version {info['version']} et contrôle SHA-256…")
        def work():
            try:
                package=updater.download_release(info,minimum_version=updater.current_version())
                self.update_events.put(('package',package,False))
            except Exception as e:
                self.update_events.put(('error',f'Mise à jour annulée : {e}',False))
        threading.Thread(target=work,daemon=True).start()

    def _install_local_zip(self):
        if self.update_busy:return
        filepath=filedialog.askopenfilename(parent=self.update_window or self,title='Choisir la nouvelle version du tracker',filetypes=[('Archive de mise à jour ZIP','*.zip')])
        if not filepath:return
        self.update_busy=True
        self.updater_notice.set('Vérification et préparation du ZIP local…')
        def work():
            try:
                package=updater.stage_archive(filepath,minimum_version=updater.current_version())
                self.update_events.put(('package_local',package,False))
            except Exception as e:
                self.update_events.put(('error',f'ZIP refusé : {e}',False))
        threading.Thread(target=work,daemon=True).start()

    def _update_pump(self):
        try:
            while True:
                event,payload,quiet=self.update_events.get_nowait()
                self.update_busy=False
                if event=='error':
                    self.updater_notice.set(payload)
                    if not quiet and self.update_window and self.update_window.winfo_exists():
                        messagebox.showerror('Mises à jour',payload,parent=self.update_window)
                elif event=='checked':
                    self.update_manifest=payload
                    version=payload['version']
                    if updater.parse_version(version)>updater.parse_version(updater.current_version()):
                        self.updater_notice.set(f"Nouvelle version {version} disponible !\n{payload['notes']}")
                        if self.update_window and self.update_window.winfo_exists():
                            self.install_remote_button.pack(anchor='w',pady=(15,0))
                        elif quiet:
                            self.status.set(f'Une mise à jour V{version} est disponible (bouton Mises à jour).')
                    else:
                        self.updater_notice.set(f'Le logiciel est à jour (version {updater.current_version()}).')
                        if self.update_window and self.update_window.winfo_exists():
                            self.install_remote_button.pack_forget()
                elif event in ('package','package_local'):
                    if event=='package_local':
                        confirmed=messagebox.askyesno('Mettre à jour',
                            f"Installer la version {payload['version']} depuis ce ZIP ?\n\n"
                            'Choisis uniquement un paquet provenant d’une source de confiance.\n'
                            'Le tracker se fermera puis redémarrera.', parent=self.update_window or self)
                        if not confirmed:
                            self.updater_notice.set('Installation annulée.');continue
                    try:
                        updater.launch_installer(payload,Path(__file__).resolve().parent,os.getpid())
                    except Exception as e:
                        self.updater_notice.set(f'Impossible de lancer l’installateur : {e}')
                        messagebox.showerror('Mises à jour',str(e),parent=self.update_window or self)
                    else:
                        self.close()
                        return
        except queue.Empty:
            pass
        self.after(200,self._update_pump)

    def _save_snapshot(self,decoded,digest,filename,modified):
        self.db.execute('INSERT OR IGNORE INTO snapshots(character,sha,observed_at,filename,data) VALUES (?,?,?,?,?)',
                        (decoded['name'],digest,modified,filename,
                         zlib.compress(json.dumps(decoded,ensure_ascii=False,separators=(',',':')).encode('utf8'))))
        self.db.commit()

    def read_and_record(self,force=False):
        if not self.path:return
        p=Path(self.path)
        try:
            stat_before=p.stat()
            stamp=(stat_before.st_mtime_ns,stat_before.st_size)
            if stamp==self.file_stamp and not force:return
            raw=p.read_bytes()
            stat_after=p.stat()
            if (stat_after.st_mtime_ns,stat_after.st_size)!=stamp:
                self.status.set('Écriture en cours : nouvelle tentative dans 5 secondes')
                return
            digest=hashlib.sha256(raw).hexdigest()
            if digest==self.current_digest and not force:
                self.file_stamp=stamp;return
            decoded=decode(raw)
            old_path=Path(str(p)+'.old')
            self.old=None
            if old_path.is_file():
                try:
                    rawold=old_path.read_bytes()
                    olddecoded=decode(rawold)
                    if olddecoded['name']==decoded['name']:
                        self.old=olddecoded
                        if not sample_rows(self.db,decoded['name']):
                            self._save_snapshot(olddecoded,hashlib.sha256(rawold).hexdigest(),
                                                old_path.name,old_path.stat().st_mtime)
                except (OSError,SaveError,ValueError,IndexError):pass
            self._save_snapshot(decoded,digest,p.name,stat_before.st_mtime)
            self.current=decoded
            self.current_digest=digest
            self.file_stamp=stamp
            self.player_label.config(text=f"{decoded['name']}  •  sauvegarde v{decoded['version']}")
            self.status.set('Lecture valide • '+datetime.fromtimestamp(stat_before.st_mtime).strftime('%d/%m/%Y %H:%M:%S'))
            self.refresh()
        except (OSError,SaveError,ValueError,IndexError,UnicodeError) as e:
            self.file_stamp=None
            self.status.set('Lecture différée : '+str(e)[:120])
            if force:raise

    def poll(self):
        if self.path:
            try:self.read_and_record()
            except Exception as e:self.status.set('Erreur de surveillance : '+str(e)[:110])
        self.after(5000,self.poll)

    def _put(self,tree,rows):
        tree.delete(*tree.get_children())
        for i,vals in enumerate(rows):tree.insert('','end',values=vals,tags=('odd' if i%2 else 'even',))

    def refresh(self):
        if not self.current:return
        p=self.current
        g=self.group.get()
        if g not in GROUPS:return
        self.group_fr.config(text=GROUP_FR.get(g,g))
        m=metrics(p,g)
        for k,v in m.items():
            if k in self.cards:
                self.cards[k].config(text=fmt(v)+(' h' if k=='world_hours' else '') if k!='bosses' else f'{v} / 8')
        bosses=defeated_bosses(p,g)
        for name,val in bosses.items():
            self.boss_rows[name].config(text=f'✓  {val}×' if val else '—',fg=GREEN if val else MUTED)
        worlds=p['groups']['RawStats']['worlds']
        world_lines='\n'.join(f'  • {k} : {v/3600:.1f} h' for k,v in sorted(worlds.items(),key=lambda x:-x[1]))
        info=(f"Compétences : {len(p['skills'])}\n"
              f"Inventaire sauvegardé : {len(p['inventory'])} entrées\n"
              f"Santé à la dernière sauvegarde : {p['health']:.1f}/{p['max_health']:.1f}\n"
              f"Endurance max sauvegardée : {p['max_stamina']:.1f}\n"
              f"\nTemps par monde (données brutes) :\n{world_lines}\n\n"
              'Les compteurs de combats et de fabrication\n'
              'sont cumulés sur tous les mondes.')
        self.summary_text.config(text=info)
        if self.old:
            oldworld=self.old['groups']['RawStats']['worlds']
            shared_worlds=set(worlds) & set(oldworld)
            if shared_worlds:
                name=max(shared_worlds,key=lambda w: worlds[w])
                delta=worlds[name]-oldworld[name]
                self.previous_text.config(text=f'Différence avec .old sur {name} : {delta/60:+.1f} min')
            else:self.previous_text.config(text='Sauvegarde précédente .old analysée')
        else:self.previous_text.config(text='')
        enemies=p['groups'][g]['enemies']
        names=set().union(*[set(d) for d in enemies])
        term=self.search_combat.get().strip().lower()
        combat=[]
        for token in names:
            label=pretty_key(token)
            if term not in label.lower() and term not in token.lower():continue
            counts=[int(round(d.get(token,0))) for d in enemies]
            combat.append((label,)+tuple(fmt(x) for x in counts))
        combat.sort(key=lambda x:-int(x[1].replace(' ','')))
        self._put(self.combat_table,combat)
        section=SECTIONS.get(self.activity.get(),'crafted')
        activities=p['groups'][g][section]
        term=self.search_activity.get().strip().lower()
        self._put(self.activity_table,[ (pretty_key(k),fmt(v)) for k,v in sorted(activities.items(),key=lambda x:-x[1])
                                      if term in k.lower() or term in pretty_key(k).lower() ])
        skills=[]
        for name,item in sorted(p['skills'].items(),key=lambda x:-x[1]['level']):
            req=(int(item['level'])+1)**1.5*0.5+0.5
            pct=100*item['xp']/req if req else 0
            skills.append((name,f"{item['level']:.2f}".replace('.',','),fmt(item['xp']),f'{min(100,max(0,pct)):.0f} %'))
        self._put(self.skill_table,skills)
        best=sorted(p['skills'].items(),key=lambda item:-item[1]['level'])[:3]
        self.skills_summary.config(text='Compétences les plus développées :  '+
                '   ·   '.join(f'{name} {value["level"]:.1f}' for name,value in best))
        search=self.search_raw.get().strip().lower()
        rows=[]
        for index,val in enumerate(p['groups'][g]['stats']):
            nm='Décès' if index==0 else DEATH_KINDS.get(index,f'Compteur #{index:03d} (non identifié)')
            if search and search not in nm.lower() and search not in str(index):continue
            rows.append((str(index),nm,fmt(val)))
        self._put(self.raw_table,rows)
        self.refresh_bosses()
        self.draw_history()

    def draw_history(self):
        if not hasattr(self,'chart') or not self.current:return
        c=self.chart
        c.delete('all')
        self._history_points=[]
        w,h=max(480,c.winfo_width()),max(280,c.winfo_height())
        rows=sample_rows(self.db,self.current['name'])
        if not rows:
            c.create_text(w/2,h/2,text='Aucun relevé enregistré',fill=MUTED,font=('Segoe UI',13))
            return
        metric=METRICS.get(self.metric.get(),'kills')
        group=self.history_group.get()
        changes=self.history_mode.get()=='Gains entre sauvegardes'
        series=history_series(rows,metric,group,CHART_PERIODS.get(self.history_period.get()),changes)
        if not series:
            c.create_text(w/2,h/2,text='Aucun relevé sur cette période',fill=MUTED,font=('Segoe UI',13))
            self.history_info.config(text='Modifie la période sélectionnée pour afficher des données.')
            return
        left,top,right,bottom=80,48,w-30,h-66
        values=[point[1] for point in series]
        minimum,maxval=min(values),max(values)
        if changes:
            minimum=min(minimum,0)
            maxval=max(maxval,0)
        if minimum==maxval:
            pad=max(1,abs(minimum)*0.08)
            minimum-=pad;maxval+=pad
        else:
            pad=(maxval-minimum)*0.10
            minimum-=pad;maxval+=pad
        for i in range(5):
            value=minimum+(maxval-minimum)*i/4
            y=bottom-(bottom-top)*i/4
            c.create_line(left,y,right,y,fill=BORDER,dash=(3,4))
            c.create_text(left-10,y,text=fmt(value),fill=MUTED,anchor='e',font=('Segoe UI',9))
        first,last=series[0][0],series[-1][0]
        span=max(1,last-first)
        coordinates=[]
        for timestamp,value,filename in series:
            x=left+(right-left)*((timestamp-first)/span if len(series)>1 and last>first else 0.5)
            y=bottom-(value-minimum)/(maxval-minimum)*(bottom-top)
            coordinates.append((x,y,timestamp,value,filename))
        if changes:
            zero=bottom-(0-minimum)/(maxval-minimum)*(bottom-top)
            c.create_line(left,zero,right,zero,fill=MUTED,width=1)
            bar_width=max(2,min(22,(right-left)/max(1,len(series))*0.65))
            for x,y,_,value,_ in coordinates:
                c.create_rectangle(x-bar_width/2,min(y,zero),x+bar_width/2,max(y,zero)+0.5,
                                   fill=GREEN if value>=0 else '#f28a87',outline='')
        else:
            points=[coord for x,y,*_ in coordinates for coord in (x,y)]
            if len(points)>=4:
                c.create_line(*points,fill=ACCENT,width=2.5,smooth=False)
            if len(coordinates)<=125:
                for x,y,*_ in coordinates:
                    c.create_oval(x-3,y-3,x+3,y+3,fill=GREEN,outline=PANEL)
        # Graduations en TEMPS réel, jamais des indices espacés artificiellement.
        for i in range(5 if last>first else 1):
            fraction=i/4 if last>first else .5
            timestamp=first+(last-first)*fraction
            x=left+(right-left)*fraction
            c.create_text(x,bottom+23,text=datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M'),
                          fill=MUTED,font=('Segoe UI',8))
        c.create_text(left,18,text=f'{self.metric.get()} • {GROUP_FR.get(group,group)}',
                      fill=FG,anchor='w',font=('Segoe UI',11,'bold'))
        self._history_points=coordinates
        change=values[-1]-values[0] if not changes else sum(values)
        first_value=history_metric(rows[0][3],metric,group)
        last_value=history_metric(rows[-1][3],metric,group)
        self.history_info.config(text=f'{len(series)} relevé(s) affiché(s) sur {len(rows)} • '
             f'Dernière valeur : {fmt(last_value)} • Évolution depuis le premier relevé : {fmt(last_value-first_value)}'
             ' • Glisse la souris sur le graphique pour voir les relevés')

    def _history_hover(self,event):
        points=self._history_points
        if not points:return
        x,y,stamp,value,filename=min(points,key=lambda p:abs(p[0]-event.x))
        if abs(x-event.x)>24:
            self.chart.delete('tooltip')
            return
        self.chart.delete('tooltip')
        line=f'{datetime.fromtimestamp(stamp):%d/%m/%Y %H:%M}  ·  {fmt(value)}'
        if self.history_mode.get()=='Gains entre sauvegardes':
            line+=' (variation)'
        tw=max(200,len(line)*7)
        tx=min(max(10,x+12),max(10,self.chart.winfo_width()-tw-15))
        ty=max(10,y-40)
        self.chart.create_rectangle(tx,ty,tx+tw,ty+28,fill='#253d55',outline=ACCENT,tags='tooltip')
        self.chart.create_text(tx+8,ty+14,text=line,anchor='w',fill=FG,
                               font=('Segoe UI',9),tags='tooltip')

    def export_csv(self):
        if not self.current:return
        rows=sample_rows(self.db,self.current['name'])
        if not rows:return
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],
             initialfile='valheim_stats_historique.csv')
        if not path:return
        with open(path,'w',newline='',encoding='utf-8-sig') as f:
            wr=csv.writer(f,delimiter=';')
            wr.writerow(['date','fichier','groupe']+list(METRICS))
            for _,stamp,filename,p in rows:
                for g in ['Any','Default','Hard']:
                    m=metrics(p,g)
                    wr.writerow([datetime.fromtimestamp(stamp).isoformat(timespec='seconds'),filename,g]
                                +[m[key] for key in METRICS.values()])
        messagebox.showinfo(APP_NAME,'CSV exporté :\n'+path)

    def close(self):
        self.db.close()
        self.destroy()


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Valheim Stats Tracker sans mod, lecture seule')
    parser.add_argument('character',nargs='?',help='Chemin du personnage .fch')
    parser.add_argument('--headless',action='store_true',help='Vérifier et afficher les statistiques en terminal')
    args=parser.parse_args()
    if args.headless:
        path=args.character or default_save()
        if not path:
            parser.error('Indiquer le chemin vers un fichier .fch')
        p=decode(Path(path).read_bytes())
        print(json.dumps({'name':p['name'],'version':p['version'],'metrics':metrics(p),
                          'bosses_normal':defeated_bosses(p,'Default'),
                          'bosses_hard':defeated_bosses(p,'Hard'),
                          'skills':p['skills'],
                          'worlds':p['groups']['RawStats']['worlds']},ensure_ascii=False,indent=2))
        return
    TrackerApp(args.character or '').mainloop()

if __name__=='__main__': main()
