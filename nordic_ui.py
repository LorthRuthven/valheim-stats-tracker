"""Interface V2.1 « Chroniques nordiques » : SVG embarqués et animations Qt.

La gestion des sauvegardes, du suivi des succès et des favoris est héritée
sans modification de l'interface V2.0. Aucun téléchargement au démarrage.
"""
from __future__ import annotations

import math
import json
from pathlib import Path
from PySide6.QtCore import Qt, QByteArray, QRectF, QSize, QTimer, QUrl, QDateTime, Property, QPropertyAnimation, QEasingCurve, QObject, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QIcon, QPixmap, QLinearGradient, QDesktopServices
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QHeaderView,
    QPushButton, QStackedWidget, QWidget, QSizePolicy,
    QGraphicsOpacityEffect, QProgressBar, QCheckBox, QComboBox, QScrollArea
)
from desktop_v2 import TrackerWindow as BaseTracker, TrendChart, label, panel, txt
from restored_pages import RestoredPagesMixin
from real_assets import hero_photo, achievement_icon, game_icon, reset_icon_cache
from game_visuals import nav_game_icon, boss_game_icon
from collection_page import CollectionPage
from viking_stats_page import VikingStatsPage
from windows_update_ui import UpdatePanel
from display_scaling import SCALES, DEFAULT_SCALE, update_readability
from v2_core import VERSION, progress_ranking
from valheim_reader import BOSSES, prefab_label

BG='#0c1117'; SIDEBAR='#111b22'; PANEL='#17232c'
BRONZE='#e9b77b'; FG='#f1eee8'; MUTED='#afc0bd'
def rune_icon(name, size=28, color=BRONZE):
    """Compatibilité UI : renvoie exclusivement une image authentique Valheim.

    Le paramètre color est conservé pour les anciens appels, sans recolorer
    la texture originale du jeu.
    """
    return nav_game_icon(name)


EMBLEM="""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
<circle cx="60" cy="60" r="55" fill="#15262c" stroke="#d6a36c" stroke-width="4"/>
<circle cx="60" cy="60" r="44" fill="none" stroke="#65716b" stroke-width="2"/>
<path d="M60 9v102M9 60h102M24 24l72 72M96 24L24 96" stroke="#805f44" stroke-width="2"/>
<path d="M36 27v66M36 51l49 29M36 80l49-51M85 27v67" stroke="#f4c183" stroke-width="7" fill="none" stroke-linecap="round"/>
</svg>"""
HERO="""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 370" preserveAspectRatio="xMidYMid slice">
<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#0b2432"/><stop offset=".6" stop-color="#224655"/><stop offset="1" stop-color="#15242d"/></linearGradient>
<linearGradient id="water" x2="0" y2="1"><stop stop-color="#163d47"/><stop offset="1" stop-color="#091720"/></linearGradient>
<radialGradient id="fire"><stop stop-color="#ffc57b" stop-opacity=".75"/><stop offset="1" stop-color="#e2934b" stop-opacity="0"/></radialGradient></defs>
<path fill="url(#sky)" d="M0 0h1440v370H0z"/>
<path d="M600-80C780 90 940-55 1090 12c120 70 220-35 380 40" stroke="#72e5c0" stroke-opacity=".16" stroke-width="82" fill="none"/>
<path d="M0 270L290 96l92 89 136-119 143 135 143-157 136 170 136-127 158 171 156-110v222H0z" fill="#345664"/>
<path d="M250 120l40-24 39 34-38-8-20 15zM490 93l28-27 33 34-27-13-15 14zM773 79l31-35 38 42-32-13-17 16z" fill="#a0c3c2" opacity=".68"/>
<path d="M0 244l160-69 155 76 150-45 168 58 147-86 135 70 183-60 145 72 97-39v149H0z" fill="#152e38"/>
<path d="M0 267q240-30 500 12t480-15 460 15v91H0z" fill="url(#water)"/>
<path d="M0 300q160-12 320 0t350-3 380 7 390-5" fill="none" stroke="#90b7ba" stroke-opacity=".18" stroke-width="3"/>
<circle cx="1155" cy="66" r="34" fill="#ffe8c1" opacity=".82"/>
<path d="M0 302l36-89 27 83 42-111 45 125 30-95 41 101 39-87 43 104V370H0z" fill="#10272e"/>
<path d="M1221 319l35-115 31 107 28-132 42 129 31-104 52 116v50h-219z" fill="#11262c"/>
<path d="M1040 276v-88l86-45 107 54v91z" fill="#44332a" stroke="#ad7548" stroke-width="5"/>
<path d="M1013 205l109-83 139 82-23 3-114-55-87 71z" fill="#171f20" stroke="#ad865b" stroke-width="5"/>
<path d="M1093 222h28v35h-28zM1176 221h25v31h-25zM1138 230h28v58h-28z" fill="#ffbe6c"/>
<circle cx="1146" cy="247" r="79" fill="url(#fire)"/>
<path d="M1250 190v-88m-15 9h38" stroke="#cba374" stroke-width="6"/>
<path d="M1250 114h41v57l-22-12-19 13z" fill="#994d35" stroke="#e3b27b" stroke-width="3"/>
<path d="M770 294q68 34 154 0-62 14-154 0z" fill="#152026" stroke="#b38c5c" stroke-width="4"/>
<path d="M830 288v-66m-7 8q40 13 57 47l-56-1z" stroke="#d9b995" stroke-width="3" fill="#c4b1a0"/>
<path fill="#08141c" opacity=".60" d="M0 0h715L475 370H0z"/></svg>"""

QSS=f"""
/* Un fond sur QWidget colorait aussi les QLabel : bandes noires visibles en V2.1. */
QMainWindow{{background:{BG};color:{FG};font:10pt 'Segoe UI';}}
QWidget{{color:{FG};font:10pt 'Segoe UI';}}
QLabel{{background:transparent;border:none;}}
QFrame{{background:transparent;border:none;}}
QStackedWidget,QScrollArea{{background:transparent;border:none;}}
QScrollArea>QWidget>QWidget{{background:transparent;}}
QFrame#sidebar{{background:{SIDEBAR};border-right:1px solid #38464a;}}
QFrame#topbar{{background:#101b23;border-bottom:1px solid #33444b;}}
QFrame#panel{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1e3039,stop:1 #14222c);border:1px solid #385057;border-radius:14px;}}
QFrame#metric{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #22343d,stop:1 #17262f);border:1px solid #3e555b;border-radius:13px;}}
QFrame#metric:hover{{background:#28404a;border:1px solid {BRONZE};}}
QFrame#dashboardClock{{background:#1a3038;border:1px solid #54716e;border-radius:12px;}}
QLabel#dashboardClockTime{{font:bold 23pt 'Segoe UI';color:#f4d39b;}}
QLabel#dashboardClockDate{{font:10pt 'Segoe UI';color:#d2e1d9;}}
QLabel#dashboardClockCaption{{font:bold 9pt 'Segoe UI';color:#a9c6c2;}}
QTableWidget#dashboardPriority{{background:#182b34;border:1px solid #405c60;alternate-background-color:#20343d;}}
QTableWidget#dashboardPriority::item{{padding:9px 8px;}}
QFrame#dashboardSession{{background:#1a2d37;border:1px solid #456166;border-radius:12px;}}
QLabel#section{{color:#fff1dd;background:transparent;font:bold 13pt 'Segoe UI';}}
QLabel#muted{{background:transparent;color:{MUTED};}}
QLabel#metricValue{{background:transparent;color:#fff1df;font:bold 23pt 'Segoe UI';}}
QPushButton{{background:#273842;color:{FG};border:1px solid #46575a;border-radius:9px;padding:10px 13px;font-weight:600;}}
QPushButton:hover{{background:#34515a;border-color:{BRONZE};}}
QPushButton#primary{{background:{BRONZE};color:#1c2428;border-color:#f6d79f;}}
QPushButton#nav{{background:transparent;border:1px solid transparent;text-align:left;padding:12px 14px;color:#b3c2bf;}}
QPushButton#nav:hover{{background:#273b43;border-color:#3e565a;}}
QPushButton#nav:checked{{background:#303b37;color:#ffdbae;border-color:#96774e;font-weight:bold;}}
QPushButton#nav:focus{{border:1px solid #d5a66c;}}
QLabel#navSection{{color:#e6bb83;font:bold 9pt 'Segoe UI';padding:13px 10px 4px 12px;}}
QFrame#dashboardQuickActions{{background:#152730;border:1px solid #39545b;border-radius:12px;}}
QPushButton#dashboardShortcut{{background:#253a43;border:1px solid #4c6769;border-radius:10px;text-align:left;padding:10px 13px;}}
QPushButton#dashboardShortcut:hover{{background:#36515b;border-color:#d6a56b;}}
QFrame#dashboardSessionPanel{{background:#192f39;border:1px solid #4a666b;border-radius:14px;}}
QLabel#dashboardSectionTitle{{color:#f6d4a0;font:bold 11pt 'Segoe UI';}}
QLineEdit,QComboBox{{background:#24343e;border:1px solid #475f61;border-radius:8px;padding:9px;color:{FG};}}
QTableWidget,QTreeWidget{{background:#162630;alternate-background-color:#1c2d37;border:1px solid #344d53;border-radius:8px;color:{FG};selection-background-color:#3c5c53;outline:none;}}
QHeaderView::section{{background:#23363d;color:#e9c7a1;border:0;border-bottom:1px solid #41575c;padding:10px;font-weight:600;}}
QTableWidget::item,QTreeWidget::item{{padding:6px;}}
QScrollArea{{background:transparent;border:0;}}
QScrollBar:vertical{{width:10px;background:#15252d;}}
QScrollBar::handle:vertical{{background:#526b70;border-radius:5px;min-height:30px;}}
QProgressBar{{background:#0e1b24;border:1px solid #40585c;border-radius:7px;color:#f8e8d1;text-align:center;height:17px;}}
QProgressBar::chunk{{background:#c39557;border-radius:5px;}}
QToolTip{{background:#1a2b33;border:1px solid {BRONZE};color:#f5e6cf;padding:8px;}}
QTreeWidget#achievementList{{border-radius:12px;alternate-background-color:#23353d;}}
QTreeWidget#achievementList::item{{padding:11px 6px;border-bottom:1px solid #334b50;}}
QTreeWidget#achievementList::item:selected{{background:#3d554e;color:#fff7e8;}}
QLabel#achievementHeroTitle{{font:bold 15pt Segoe UI;color:#f5d49a;}}
QLabel#collectionDetailTitle{{font:bold 16pt Segoe UI;}}
QLabel#collectionDetailStatus{{font:bold 11pt Segoe UI;color:#a9dbc6;}}
QLabel#collectionSummary{{font:bold 10pt Segoe UI;color:#e8c493;}}
QLabel#collectionPreview{{background:#111e27;border:1px solid #3a545a;border-radius:12px;padding:10px;}}
QTableWidget#collectionTable::item{{padding:9px 7px;}}

"""

class Artwork(QWidget):
    def __init__(self, svg, height=185, parent=None):
        super().__init__(parent)
        self.renderer=QSvgRenderer(QByteArray(svg.encode('utf8')),self)
        self.setFixedHeight(height)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.renderer.render(p,QRectF(self.rect()))
        p.end()

class AnimatedRing(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(160,160)
        self._value=0.
        self._anim=None
    def get_value(self):return self._value
    def set_value(self,value):
        self._value=max(0.,min(100.,float(value)));self.update()
    progress=Property(float,get_value,set_value)
    def move_to(self,value,animated=True):
        if self._anim:self._anim.stop()
        if not animated:self.set_value(value);return
        self._anim=QPropertyAnimation(self,b'progress',self)
        self._anim.setStartValue(self._value);self._anim.setEndValue(value)
        self._anim.setDuration(750);self._anim.setEasingCurve(QEasingCurve.Type.OutCubic);self._anim.start()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(9,18,22,220));p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(5,5,150,150))
        p.setPen(QPen(QColor('#3a4e4c'),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(16,16,128,128),0,5760)
        p.setPen(QPen(QColor(BRONZE),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(16,16,128,128),90*16,-int(self._value/100*5760))
        p.setPen(QColor('#fff1d8'));p.setFont(QFont('Segoe UI',23,QFont.Weight.Bold))
        p.drawText(QRectF(20,43,120,60),Qt.AlignmentFlag.AlignCenter,f'{self._value:.0f} %')
        p.setPen(QColor('#bdccc5'));p.setFont(QFont('Segoe UI',8))
        p.drawText(QRectF(9,102,142,26),Qt.AlignmentFlag.AlignCenter,'SUCCÈS ATTEINTS')
        p.end()

class PhotoArtwork(Artwork):
    def paintEvent(self,event):
        photo=hero_photo()
        if photo.isNull():
            super().paintEvent(event)
            return
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale=max(self.width()/max(1,photo.width()),self.height()/max(1,photo.height()))
        w=self.width()/scale
        h=self.height()/scale
        source=QRectF((photo.width()-w)/2,(photo.height()-h)/2,w,h)
        p.drawPixmap(QRectF(self.rect()),photo,source)
        p.end()

class Hero(Artwork):
    def paintEvent(self,event):
        photo=hero_photo()
        if photo.isNull():
            super().paintEvent(event)
            return
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale=max(self.width()/max(1,photo.width()),self.height()/max(1,photo.height()))
        w=self.width()/scale
        h=self.height()/scale
        source=QRectF((photo.width()-w)/2,(photo.height()-h)/2,w,h)
        painter.drawPixmap(QRectF(self.rect()),photo,source)
        shade=QLinearGradient(0,0,self.width(),0)
        shade.setColorAt(0,QColor(6,16,22,235))
        shade.setColorAt(.54,QColor(6,16,22,195))
        shade.setColorAt(1,QColor(6,16,22,45))
        painter.fillRect(QRectF(self.rect()),shade)
        painter.end()

    def __init__(self,parent=None):
        super().__init__(HERO,207,parent)
        lay=QHBoxLayout(self);lay.setContentsMargins(27,19,26,18)
        col=QVBoxLayout()
        small=QLabel('✧  CHRONIQUES DU DIXIÈME MONDE')
        small.setStyleSheet('color:#eac48a;font:bold 9pt Segoe UI;letter-spacing:1px;')
        col.addWidget(small)
        self.title=QLabel('CHAQUE AVENTURE LAISSE UNE TRACE')
        self.title.setStyleSheet('color:#fff0d7;font:bold 23pt Georgia;')
        self.title.setWordWrap(True);col.addWidget(self.title)
        self.subtitle=QLabel('Le parcours de ton Viking, de la prairie au Nord profond.')
        self.subtitle.setStyleSheet('color:#d9dfd4;');self.subtitle.setWordWrap(True)
        col.addWidget(self.subtitle);col.addStretch()
        lay.addLayout(col,1)
        self.ring=AnimatedRing();lay.addWidget(self.ring)

class _IconEvents(QObject):
    finished=Signal(int,str)
    progress=Signal(int,int,str)

class NordicWindow(RestoredPagesMixin,BaseTracker):
    NAV = BaseTracker.NAV + [
        ('Centre de progression','Priorités'),
        ('Boss','Boss'),
        ('Activités','Objets'),
        ('Compétences','Compétences'),
        ('Compteurs bruts','Statistiques'),
        ('Encyclopédie','Collection'),
        ('Statistiques du Viking','Statistiques'),
    ]
    def __init__(self,store=None):
        self.motion=True
        self.fade=None
        self.icon_events=_IconEvents()
        self.icon_events.finished.connect(self._icons_finished)
        self.icon_events.progress.connect(self._icons_progress)
        super().__init__(store=store)
        self.setWindowTitle('Valheim Stats Tracker • Statistiques du Viking • '+VERSION)
        self.setStyleSheet(QSS)
        self.setMinimumSize(1100,740)
        self.resize(1580,940)
        self._load_motion()
    def _build(self):
        root=QWidget();self.setCentralWidget(root)
        row=QHBoxLayout(root);row.setContentsMargins(0,0,0,0);row.setSpacing(0)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(232)
        menu=QVBoxLayout(side);menu.setContentsMargins(13,12,12,12);menu.setSpacing(4)
        mast=QHBoxLayout()
        # En priorité le véritable visuel promotionnel fourni par Steam.
        logo=QLabel()
        real_logo=QPixmap(str(__import__('real_assets').bundled_assets()/'logo.jpg'))
        if not real_logo.isNull():
            logo.setPixmap(real_logo.scaled(100,57,Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText('V')
            logo.setStyleSheet('color:#e3ad71;font:bold 34pt Georgia;')
        logo.setFixedSize(100,57)
        mast.addWidget(logo)
        branding=QVBoxLayout()
        name=QLabel('VALHEIM');name.setStyleSheet('color:#f6ca88;font:bold 17pt Georgia;')
        branding.addWidget(name);branding.addWidget(label('STATS TRACKER',muted=True))
        mast.addLayout(branding);menu.addLayout(mast)
        tag=QLabel('  CHRONIQUES NORDIQUES  •  V'+VERSION)
        tag.setStyleSheet('color:#ddae6f;font:9pt Segoe UI;')
        menu.addWidget(tag);menu.addSpacing(4)
        menu.addWidget(label('NAVIGATION',muted=True))
        # La navigation reste accessible sur les petits ecrans, meme avec 12 pages.
        nav_scroller=QScrollArea()
        nav_scroller.setWidgetResizable(True)
        nav_scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroller.setFrameShape(QFrame.Shape.NoFrame)
        nav_container=QWidget()
        nav_layout=QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0,0,0,0)
        nav_layout.setSpacing(4)
        self.nav_buttons=[]
        nav_icons=('home','trophy','skull','history','settings',
                   'trophy','skull','axe','tree','settings','compass','tree')
        for idx,(name,_) in enumerate(self.NAV):
            btn=QPushButton(name);btn.setObjectName('nav');btn.setCheckable(True)
            btn.setMinimumHeight(35)
            btn.setIcon(rune_icon(nav_icons[idx]))
            btn.clicked.connect(lambda _=False,i=idx:self.show_page(i))
            self.nav_buttons.append(btn)

        # Les identifiants de pages restent inchangés pour les raccourcis et les
        # données enregistrées. Seul l'ordre VISUEL du menu est réorganisé.
        self.nav_groups = (
            ('AVENTURE', (0, 5, 1)),
            ('CHRONIQUES', (3, 2, 6, 7)),
            ('STATISTIQUES', (11, 8)),
            ('DÉCOUVERTE', (10,)),
            ('APPLICATION', (4,)),
        )
        for heading, indices in self.nav_groups:
            section=QLabel(heading)
            section.setObjectName('navSection')
            nav_layout.addWidget(section)
            for idx in indices:
                nav_layout.addWidget(self.nav_buttons[idx])
        # Page de diagnostic historique invisible dans la navigation.
        self.nav_buttons[9].setParent(nav_container)
        self.nav_buttons[9].hide()
        nav_layout.addStretch(1)
        nav_scroller.setWidget(nav_container)
        menu.addWidget(nav_scroller,1)
        glimpse=PhotoArtwork(HERO,55)
        menu.addWidget(glimpse)
        menu.addWidget(label('PERSONNAGE',muted=True))
        self.sidebar_character=label('Aucun personnage',wrap=True)
        self.sidebar_character.setStyleSheet('font-weight:bold;color:#f4d3a7;')
        menu.addWidget(self.sidebar_character)
        self.sidebar_cumulative_button=QPushButton('Σ  Cumul des Vikings')
        self.sidebar_cumulative_button.setObjectName('sidebarStatsShortcut')
        self.sidebar_cumulative_button.setToolTip(
            'Ouvrir les Statistiques du Viking en mode cumul de tous les personnages.'
        )
        self.sidebar_cumulative_button.clicked.connect(self.open_cumulative_stats)
        menu.addWidget(self.sidebar_cumulative_button)
        row.addWidget(side)
        main=QWidget();ml=QVBoxLayout(main);ml.setContentsMargins(0,0,0,0);ml.setSpacing(0)
        top=QFrame();top.setObjectName('topbar')
        head=QHBoxLayout(top);head.setContentsMargins(27,18,27,17)
        titlecol=QVBoxLayout()
        breadcrumb=QLabel('✧   JOURNAL DU VIKING  /  DIXIÈME MONDE')
        breadcrumb.setStyleSheet('color:#e2b378;font:bold 9pt Segoe UI;')
        titlecol.addWidget(breadcrumb)
        self.header_title=QLabel('Vue d’ensemble')
        self.header_title.setStyleSheet('color:#f8ecdb;font:bold 22pt Segoe UI;')
        titlecol.addWidget(self.header_title)
        self.header_status=label('Choisis ton personnage pour commencer.',muted=True,wrap=True)
        titlecol.addWidget(self.header_status);head.addLayout(titlecol,1)
        self.btn_file=QPushButton('Choisir un personnage');self.btn_file.setIcon(rune_icon('shield',23))
        self.btn_file.clicked.connect(self.choose_file);head.addWidget(self.btn_file)
        self.btn_refresh=QPushButton('Actualiser');self.btn_refresh.setObjectName('primary')
        self.btn_refresh.setIcon(rune_icon('history',23))
        self.btn_refresh.clicked.connect(lambda:self.refresh_save(force=True));head.addWidget(self.btn_refresh)
        ml.addWidget(top)
        self.stack=QStackedWidget();ml.addWidget(self.stack,1)
        self._make_dashboard();self._make_achievements();self._make_combat()
        self._make_history();self._make_settings();self._make_restored_pages()
        self._make_collection_page()
        self._make_viking_stats_page()
        row.addWidget(main,1)
        self.statusBar().showMessage('Sans mod • Lecture seule • Vérification toutes les 5 secondes')
    def _scroll_page(self):
        layout=super()._scroll_page()
        if self.stack.count()==1:
            self.hero=Hero()
            layout.insertWidget(0,self.hero)
        return layout
    def _metric(self,title,hint=''):
        box,val=super()._metric(title,hint)
        icon={'Créatures tuées':'paw','Boss vaincus':'skull','Décès':'shield','Temps de jeu':'clock'}.get(title,'trophy')
        lab=QLabel();lab.setPixmap(rune_icon(icon,28).pixmap(28,28))
        box.layout().insertWidget(0,lab)
        box.setMinimumHeight(128)
        return box,val
    def _make_combat(self):
        super()._make_combat()
        page=self.stack.widget(2)
        interior=page.widget() if hasattr(page, 'widget') else None
        if interior is None:
            return
        layout=interior.layout()
        if layout is None:
            return
        summary, sl=panel(
            'CHRONIQUE DES COMBATS',
            'Indicateurs enregistrés pour le groupe de difficulté choisi, sans double comptage.'
        )
        strip=QHBoxLayout()
        self.combat_summary_labels={}
        for key, heading in (
            ('kills','CRÉATURES ÉLIMINÉES'),
            ('species','ESPÈCES AVEC ÉLIMINATIONS'),
            ('bosses','BOSS VAINCUS'),
        ):
            card=QFrame()
            card.setObjectName('combatMetricCard')
            card.setStyleSheet(
                'QFrame#combatMetricCard {background:#172d39;'
                'border:1px solid #425c64;border-radius:12px;}'
            )
            inner=QVBoxLayout(card)
            inner.setContentsMargins(17,12,17,12)
            small=label(heading,muted=True,wrap=True)
            number=label('—')
            number.setStyleSheet('color:#e9bb7b;font:bold 24pt Segoe UI;')
            inner.addWidget(small)
            inner.addWidget(number)
            strip.addWidget(card,1)
            self.combat_summary_labels[key]=number
        sl.addLayout(strip)
        layout.insertWidget(0,summary)

    def _make_dashboard(self):
        super()._make_dashboard()
        # Heure locale du PC : sans lien avec l'horloge de Valheim ni le .fch.
        page = self.stack.widget(0)
        inner = page.widget() if hasattr(page, 'widget') else None
        layout = inner.layout() if inner is not None else None
        if layout is not None:
            strip = QFrame()
            strip.setObjectName('dashboardClock')
            strip_layout = QHBoxLayout(strip)
            strip_layout.setContentsMargins(22, 12, 22, 12)
            strip_layout.setSpacing(20)
            about = QVBoxLayout()
            about.setSpacing(3)
            heading = QLabel('AUJOURD’HUI • HEURE RÉELLE')
            heading.setObjectName('dashboardClockCaption')
            about.addWidget(heading)
            self.dash_clock_date = QLabel('—')
            self.dash_clock_date.setObjectName('dashboardClockDate')
            about.addWidget(self.dash_clock_date)
            strip_layout.addLayout(about, 1)
            self.dash_clock_time = QLabel('--:--:--')
            self.dash_clock_time.setObjectName('dashboardClockTime')
            self.dash_clock_time.setAlignment(Qt.AlignmentFlag.AlignRight |
                                             Qt.AlignmentFlag.AlignVCenter)
            self.dash_clock_time.setToolTip(
                "Heure locale de Windows, indépendante du temps dans Valheim.")
            strip_layout.addWidget(self.dash_clock_time)
            # La bannière de personnage reste la première section visible.
            layout.insertWidget(1, strip)
            self._update_dashboard_clock()
            self.dash_clock_timer = QTimer(self)
            self.dash_clock_timer.setInterval(1000)
            self.dash_clock_timer.timeout.connect(self._update_dashboard_clock)
            self.dash_clock_timer.start()

        # Accès direct aux tâches courantes, utilisable même avant de charger
        # un personnage. Aucune modification de sauvegarde.
        if layout is not None:
            quick = QFrame()
            quick.setObjectName('dashboardQuickActions')
            quick_row = QHBoxLayout(quick)
            quick_row.setContentsMargins(14, 10, 14, 10)
            quick_row.setSpacing(10)
            self.dashboard_shortcuts = {}
            for title, index, icon in (
                ('Mes objectifs', 5, 'trophy'),
                ('Historique', 3, 'history'),
                ('Stats du Viking', 11, 'tree'),
                ('Encyclopédie', 10, 'compass'),
            ):
                button = QPushButton(title)
                button.setObjectName('dashboardShortcut')
                button.setIcon(rune_icon(icon, 24))
                button.setToolTip('Ouvrir : ' + self.NAV[index][0])
                button.clicked.connect(lambda _=False, page=index: self.show_page(page))
                quick_row.addWidget(button, 1)
                self.dashboard_shortcuts[index] = button
            layout.insertWidget(2, quick)

        # Le tableau donne plus de place aux titres des succès ; les deux
        # colonnes numériques restent faciles à scanner en écran 1440p.
        self.dash_priority.setObjectName('dashboardPriority')
        self.dash_priority.setAlternatingRowColors(True)
        self.dash_priority.setShowGrid(False)
        self.dash_priority.setWordWrap(False)
        self.dash_priority.setMinimumHeight(295)
        header = self.dash_priority.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.dash_priority.setColumnWidth(1, 165)
        self.dash_priority.setColumnWidth(2, 100)
        self.dash_priority.verticalHeader().setDefaultSectionSize(51)
        self.dash_priority.setToolTip(
            "Double-clique sur un succès pour consulter son détail.")
        self.dash_priority.cellDoubleClicked.connect(self._jump_to_achievement)
        self.dash_chart.setMinimumHeight(290)
        self.dash_chart.setToolTip('Historique des éliminations, calculé à partir des relevés du personnage.')
        # Lisibilité des textes de session et des indicateurs secondaires.
        self.dash_session.setWordWrap(True)
        self.dash_session.setMinimumWidth(240)
        for value in self.dash_metrics.values():
            value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def _update_dashboard_clock(self):
        """Actualise l'horloge chaque seconde, même sans personnage chargé."""
        if not hasattr(self, 'dash_clock_time'):
            return
        now = QDateTime.currentDateTime()
        self.dash_clock_time.setText(now.toString('HH:mm:ss'))
        self.dash_clock_date.setText(now.toString('dddd d MMMM yyyy'))
    def _make_collection_page(self):
        self.collection_page=CollectionPage(self)
        self.collection_page.game_import_requested.connect(self._import_game_icons)
        self.stack.addWidget(self.collection_page)

    def _make_viking_stats_page(self):
        self.viking_stats_page=VikingStatsPage(self.store.directory, self, store=self.store)
        self.stack.addWidget(self.viking_stats_page)

    def _make_achievements(self):
        super()._make_achievements()
        self.ach_tree.setObjectName('achievementList')
        self.ach_tree.setIconSize(QSize(52,52))
        self.ach_tree.setAlternatingRowColors(True)
        detail=self.stack.widget(1).layout().itemAt(1).widget()
        content=detail.layout()
        hero=QHBoxLayout()
        self.ach_large_icon=QLabel('Illustration indisponible')
        self.ach_large_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ach_large_icon.setFixedSize(104,104)
        self.ach_large_icon.setWordWrap(True)
        self.ach_large_icon.setStyleSheet(
            'background:#10212a;border:1px solid #425a5c;border-radius:12px;color:#a8bbb6;')
        hero.addWidget(self.ach_large_icon)
        textcol=QVBoxLayout()
        self.ach_state=QLabel('Sélectionne un succès pour afficher sa progression.')
        self.ach_state.setObjectName('achievementHeroTitle')
        self.ach_state.setWordWrap(True)
        textcol.addWidget(self.ach_state)
        self.ach_condition_count=label('',muted=True,wrap=True)
        textcol.addWidget(self.ach_condition_count)
        hero.addLayout(textcol,1)
        content.insertLayout(2,hero)
        self.ach_bar.setMinimumHeight(23)

    def draw_success_detail(self):
        super().draw_success_detail()
        if not hasattr(self,'ach_large_icon'):
            return
        achievement=next((x for x in getattr(self,'results',[])
                          if x['key']==getattr(self,'selected_achievement','')),None)
        self.ach_large_icon.clear()
        if not achievement:
            self.ach_large_icon.setText('Illustration indisponible')
            self.ach_state.setText('Aucun succès sélectionné')
            self.ach_condition_count.clear()
            return
        visual=achievement_icon(achievement.get('title_en',''))
        if visual.isNull():
            self.ach_large_icon.setText('Icône officielle indisponible')
        else:
            self.ach_large_icon.setPixmap(visual.pixmap(QSize(92,92)))
        self.ach_state.setText(
            'OBJECTIF ATTEINT' if achievement.get('complete') else
            ('PROGRESSION EN COURS' if achievement.get('measurable')
             else 'PROGRESSION NON CALCULABLE')
        )
        self.ach_condition_count.setText(
            f"{achievement.get('category','')}  •  "
            f"{achievement.get('completed_conditions',0)} / "
            f"{achievement.get('total_conditions',0)} critères"
        )

    def _make_settings(self):
        super()._make_settings()
        area=self.stack.widget(4)
        inner=area.widget() if hasattr(area,'widget') else None
        if inner is not None:
            # Retirer le panneau hérité de la V2.0, qui proposait uniquement
            # une mise à jour manuelle (désormais remplacée ci-dessous).
            old_item=inner.layout().itemAt(1)
            old_panel=old_item.widget() if old_item is not None else None
            if old_panel is not None and any(
                isinstance(x,QLabel) and x.text()=='MISES À JOUR'
                for x in old_panel.findChildren(QLabel)
            ):
                inner.layout().removeWidget(old_panel)
                old_panel.setParent(None)  # retire immédiatement des enfants Qt
                old_panel.deleteLater()
            frame, layout=panel('AMBIANCE ET MOUVEMENTS',
                'Illustrations locales : aucune connexion n’est nécessaire.')
            self.motion_checkbox=QCheckBox('Activer les animations de navigation et de progression')
            self.motion_checkbox.setChecked(True)
            self.motion_checkbox.toggled.connect(self.set_motion)
            layout.addWidget(self.motion_checkbox)
            layout.addWidget(label('Vrais sprites Valheim pour les menus et les statistiques, sans pictogrammes maison.',muted=True,wrap=True))
            inner.layout().insertWidget(0,frame)
            display_panel, display_layout=panel(
                'TAILLE DE L’INTERFACE',
                'Agrandit tous les textes, menus, filtres et lignes de tableau. '
                'Le réglage est appliqué immédiatement et mémorisé.'
            )
            scale_row=QHBoxLayout()
            scale_row.addWidget(label('Lisibilité :'))
            self.display_choice=QComboBox()
            self.display_choice.addItems(list(SCALES))
            self.display_choice.setCurrentText(DEFAULT_SCALE)
            self.display_choice.currentTextChanged.connect(self.set_display_mode)
            scale_row.addWidget(self.display_choice)
            scale_row.addStretch()
            display_layout.addLayout(scale_row)
            display_layout.addWidget(label(
                '« Grand » est recommandé sur un écran Full HD ; '
                '« Très grand » privilégie la lecture au nombre de lignes visibles.',
                muted=True, wrap=True
            ))
            inner.layout().insertWidget(1,display_panel)
            updates, update_layout=panel('MISES À JOUR WINDOWS',
                'Téléchargement SHA-256, installation intégrée et redémarrage après confirmation.')
            self.update_controller=UpdatePanel(self)
            update_layout.addWidget(self.update_controller)
            inner.layout().insertWidget(2,updates)
            icons, icon_layout=panel('VÉRITABLES ICÔNES VALHEIM',
                'Extraction locale des sprites depuis ton jeu installé ; aucun mod.')
            self.icon_import_button=QPushButton('Importer depuis le dossier de Valheim')
            self.icon_import_button.clicked.connect(self._import_game_icons)
            icon_layout.addWidget(self.icon_import_button)
            self.icon_progress=QProgressBar()
            self.icon_progress.setRange(0,100)
            self.icon_progress.setValue(0)
            icon_layout.addWidget(self.icon_progress)
            self.icon_log_button=QPushButton('Ouvrir le rapport de diagnostic')
            self.icon_log_button.clicked.connect(self._open_icon_report)
            icon_layout.addWidget(self.icon_log_button)
            self.icon_status=label('Sélectionne le dossier contenant valheim.exe.',muted=True,wrap=True)
            icon_layout.addWidget(self.icon_status)
            inner.layout().insertWidget(3,icons)
            wiki, wiki_layout=panel('IMAGES DU WIKI VALHEIM',
                'Complète les illustrations absentes depuis le wiki communautaire. '
                'Les sprites déjà extraits du jeu restent prioritaires.')
            wiki_button=QPushButton('Compléter les images manquantes du catalogue')
            wiki_button.clicked.connect(self._open_collection_wiki)
            wiki_layout.addWidget(wiki_button)
            wiki_layout.addWidget(label(
                'Les téléchargements se font seulement au besoin ; maximum 20 par action. '
                'Une attribution renvoie à chaque page du wiki.',muted=True,wrap=True))
            inner.layout().insertWidget(4,wiki)
            diagnostics,diagnostic_layout=panel(
                'DIAGNOSTIC AVANCÉ',
                'Accès aux 205 compteurs techniques du fichier Valheim. '
                'Cette vue ne modifie aucune sauvegarde.'
            )
            self.raw_diagnostic_button=QPushButton('Ouvrir les compteurs bruts')
            self.raw_diagnostic_button.setObjectName('openRawDiagnostics')
            self.raw_diagnostic_button.clicked.connect(
                lambda _=False:self.show_page(9)
            )
            diagnostic_layout.addWidget(self.raw_diagnostic_button)
            diagnostic_layout.addWidget(label(
                'Les activités et statistiques utiles restent disponibles '
                'dans leurs pages dédiées. Les noms et indices bruts '
                'servent essentiellement au dépannage.',
                muted=True, wrap=True
            ))
            inner.layout().insertWidget(5,diagnostics)

    def _open_collection_wiki(self):
        self.show_page(10)
        self.collection_page._fetch_missing()

    def _open_icon_report(self):
        from v2_core import app_dir
        file=app_dir()/'game_icons'/'extraction-report.json'
        if not file.exists():
            self.icon_status.setText('Aucun rapport disponible : lance d’abord une extraction.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(file)))

    def _import_game_icons(self):
        from PySide6.QtWidgets import QFileDialog
        from v2_core import app_dir
        from game_icon_extraction import extract_owned_icons
        import threading
        folder=QFileDialog.getExistingDirectory(self,'Dossier contenant valheim.exe')
        if not folder:return
        self.icon_import_button.setEnabled(False)
        self.icon_progress.setRange(0,100)
        self.icon_progress.setValue(0)
        self.icon_status.setText('Analyse des bundles Unity en cours ; aucun fichier du jeu n’est modifié.')
        def progress(index,total,name):
            self.icon_events.progress.emit(index,total,name)
        def job():
            try:
                count=extract_owned_icons(folder,app_dir()/'game_icons',notify=progress)
                self.icon_events.finished.emit(count,'')
            except Exception as exc:
                self.icon_events.finished.emit(0,str(exc))
        threading.Thread(target=job,daemon=True).start()

    def _icons_progress(self,index,total,name):
        if total>0:
            self.icon_progress.setValue(min(100,round(index/total*100)))
        self.icon_status.setText(f'Analyse : {index} / {total} fichiers Unity · {name}')

    def _icons_finished(self,count,error):
        self.icon_import_button.setEnabled(True)
        from v2_core import app_dir
        report=app_dir()/'game_icons'/'extraction-report.json'
        details=''
        try:
            state=json.loads(report.read_text(encoding='utf-8'))
            details=(f"{state.get('files_read',0)} fichiers lus, "
                     f"{state.get('sprites_found',0)} sprites, "
                     f"{state.get('textures_found',0)} textures ; "
                     f"{state.get('images_written',0)} nouvelles icônes, "
                     f"{state.get('images_existing',0)} déjà présentes ; "
                     f"{state.get('errors_total',0)} erreurs.")
        except (OSError,ValueError):
            pass
        if error:
            self.icon_status.setText('Échec d’extraction : '+error+'\n'+details)
        else:
            self.icon_progress.setValue(100)
            self.icon_status.setText(f'{count} vraies icônes disponibles.\n'+details)
            reset_icon_cache()
            self._refresh_restored_pages()
            self.draw_achievements()
            self.draw_combat()
            self.collection_page.invalidate_image_cache()
            self.collection_page.refresh(self.store.profile)

    def _appearance_path(self):
        return self.store.directory/'appearance.json'

    def _write_appearance(self, changes):
        path=self._appearance_path()
        try:
            current=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(current,dict):
                current={}
        except (OSError,ValueError,TypeError):
            current={}
        current.update(changes)
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(path)
        except OSError as exc:
            self.statusBar().showMessage('Réglage non enregistré : '+str(exc))

    def _load_motion(self):
        try:
            settings=json.loads(self._appearance_path().read_text(encoding='utf-8'))
            if not isinstance(settings,dict):
                settings={}
        except (OSError,ValueError,TypeError):
            settings={}
        self.motion=bool(settings.get('animations',True))
        if hasattr(self,'motion_checkbox'):
            self.motion_checkbox.blockSignals(True)
            self.motion_checkbox.setChecked(self.motion)
            self.motion_checkbox.blockSignals(False)
        wanted=settings.get('display_mode',DEFAULT_SCALE)
        if wanted not in SCALES:
            wanted=DEFAULT_SCALE
        if hasattr(self,'display_choice'):
            self.display_choice.blockSignals(True)
            self.display_choice.setCurrentText(wanted)
            self.display_choice.blockSignals(False)
        update_readability(self,wanted,QSS)
        self.display_mode=wanted

    def set_motion(self,enabled):
        self.motion=bool(enabled)
        self._write_appearance({'animations':self.motion})

    def set_display_mode(self,mode):
        if mode not in SCALES:
            return
        update_readability(self,mode,QSS)
        self.display_mode=mode
        self._write_appearance({'display_mode':mode})

    def _jump_to_achievement(self,index,column):
        ranked=progress_ranking(self.results,self.store.favorites())[:8]
        if 0<=index<len(ranked):
            self.selected_achievement=ranked[index]['key']
            self.show_page(1);self.draw_achievements()
    def open_cumulative_stats(self):
        self.show_page(11)
        self.viking_stats_page.show_total()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,"activity_grid") or not hasattr(self,"activity_tiles"):
            return
        available=max(0,self.width()-300)
        columns=4 if available>=1220 else 3 if available>=850 else 2
        if self.activity_columns != columns:
            self._render_activity_gallery()

    def show_page(self,index):
        super().show_page(index)
        if index == 9:
            # La navigation visible reste sur Réglages pour le diagnostic.
            self.nav_buttons[4].setChecked(True)
        if index == 10 and hasattr(self, 'collection_page'):
            self.collection_page.activate()
        if not self.motion:return
        page=self.stack.currentWidget()
        if page.graphicsEffect():page.setGraphicsEffect(None)
        effect=QGraphicsOpacityEffect(page);page.setGraphicsEffect(effect)
        anim=QPropertyAnimation(effect,b'opacity',page)
        anim.setStartValue(.17);anim.setEndValue(1.);anim.setDuration(260)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade=anim;anim.start()
    def populate(self):
        super().populate()
        self._refresh_restored_pages()
        profile=self.store.profile
        self.collection_page.refresh(profile)
        rows=self.store.rows(limit=2) if profile else []
        previous=rows[-2][3] if len(rows)>=2 else None
        self.viking_stats_page.refresh(profile,previous)
        if profile:
            self.hero.title.setText('LA SAGA DE '+profile['name'].upper())
            active=[a for a in self.results if a.get('origin')=='Jeu + Steam']
            finished=sum(bool(a.get('complete')) for a in active)
            self.hero.subtitle.setText(f'{finished} objectifs estimés atteints sur {len(active)} • Tes prochaines conquêtes')
            self.hero.ring.move_to(100*finished/max(1,len(active)),self.motion)
    def draw_dashboard(self):
        super().draw_dashboard()
        self._progress_anims=[]
        ranked=progress_ranking(self.results,self.store.favorites())[:8]
        for idx,a in enumerate(ranked):
            item=self.dash_priority.item(idx,0)
            if item:
                icon=achievement_icon(a.get('title_en',''))
                if not icon.isNull():
                    item.setIcon(icon)
            bar=QProgressBar();bar.setRange(0,1000)
            percent=float(a.get('percent') or 0)
            goal=round(percent*10)
            bar.setValue(0 if self.motion else goal)
            bar.setFormat(f'{percent:.1f} %')
            self.dash_priority.setCellWidget(idx,1,bar)
            if self.motion:
                animation=QPropertyAnimation(bar,b'value',bar)
                animation.setDuration(500+idx*40)
                animation.setStartValue(0)
                animation.setEndValue(goal)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._progress_anims.append(animation)
                animation.start()
    def draw_achievements(self):
        super().draw_achievements()
        if not self.store.profile:return
        index={r['key']:r for r in self.results}
        for i in range(self.ach_tree.topLevelItemCount()):
            item=self.ach_tree.topLevelItem(i)
            result=index.get(item.data(0,Qt.ItemDataRole.UserRole),{})
            ico=achievement_icon(result.get('title_en',''))
            if not ico.isNull():item.setIcon(0,ico)
            item.setSizeHint(0,QSize(0,69))
        if hasattr(self,'ach_category'):
            category=self.ach_category.currentText()
            origin=self.ach_origin.currentIndex()
            for i in range(self.ach_tree.topLevelItemCount()):
                item=self.ach_tree.topLevelItem(i)
                result=index.get(item.data(0,Qt.ItemDataRole.UserRole),{})
                visible=category=='Toutes catégories' or result.get('category')==category
                if origin==1:visible &= result.get('origin')=='Jeu + Steam'
                if origin==2:visible &= result.get('origin')=='Interne uniquement'
                item.setHidden(not visible)
        if hasattr(self,'ach_parts_search'):
            search=self.ach_parts_search.text().strip().casefold()
            for i in range(self.ach_parts.rowCount()):
                cell=self.ach_parts.item(i,0)
                self.ach_parts.setRowHidden(i,bool(search and cell and search not in cell.text().casefold()))

    def draw_combat(self):
        super().draw_combat()
        if not self.store.profile:
            return
        # Correspondances exactes des prefabs du bestiaire et des boss.
        for i,(token,name) in enumerate(BOSSES.items()):
            cell=self.combat_bosses.item(i,0)
            icon=boss_game_icon(token)
            if cell is not None and not icon.isNull():cell.setIcon(icon)
        group=self.combat_group.currentData()
        kills=self.store.profile['groups'][group]['enemies'][0]
        if hasattr(self,'combat_summary_labels'):
            self.combat_summary_labels['kills'].setText(txt(sum(max(0,v) for v in kills.values())))
            self.combat_summary_labels['species'].setText(
                str(sum(v>0 for v in kills.values()))
            )
            self.combat_summary_labels['bosses'].setText(
                f"{sum(kills.get(tok,0)>0 for tok in BOSSES)} / {len(BOSSES)}"
            )
        enemies=sorted(((prefab_label(token), count, token)
                        for token,count in kills.items() if count>0),
                       key=lambda row:(-row[1],row[0]))
        for i,(_,__,token) in enumerate(enemies):
            cell=self.combat_enemies.item(i,0)
            icon=game_icon(token)
            if cell is not None and not icon.isNull():
                cell.setIcon(icon)


def main():
    import sys
    from windows_install import handoff_if_newer
    bypass = '--no-update-handoff' in sys.argv
    if not bypass and handoff_if_newer(VERSION):
        return 0
    qt_args = [arg for arg in sys.argv if arg != '--no-update-handoff']
    app=QApplication(qt_args);app.setApplicationName('Valheim Stats Tracker');app.setStyle('Fusion')
    window=NordicWindow();window.show()
    return app.exec()

def _verify_update_ready(expected_version):
    """Controle reel du nouveau programme avant son activation automatique."""
    if VERSION != expected_version:
        raise RuntimeError("La version du programme ne correspond pas au ZIP.")
    from tempfile import TemporaryDirectory
    from v2_core import TrackerStore
    app = QApplication.instance() or QApplication([])
    with TemporaryDirectory() as folder:
        store = TrackerStore(folder)
        try:
            window = NordicWindow(store)
            if window.stack.count() != 12 or window.update_controller is None:
                raise RuntimeError("Interface incomplete dans l'EXE candidat.")
            window.close()
        finally:
            store.close()


def _verify_unitypy_bundle():
    """Teste l'exécutable réellement compilé : régression UnityPy.resources."""
    import importlib
    import importlib.resources
    for name in ('UnityPy', 'UnityPy.resources', 'PIL.Image', 'fmod_toolkit'):
        importlib.import_module(name)
    # Les tests synthetiques seuls ne chargeaient jamais les DLL natives.
    # Cette verification reproduit la dependance reelle des sprites Valheim.
    import ctypes
    import os
    import sys
    from pathlib import Path
    if os.name == 'nt' and getattr(sys, 'frozen', False):
        from game_icon_extraction import verify_fmod_runtime, verify_archspec_runtime
        dll = verify_fmod_runtime(Path(sys._MEIPASS))
        verify_archspec_runtime(Path(sys._MEIPASS))
        try:
            ctypes.WinDLL(str(dll))
        except OSError as exc:
            raise RuntimeError(f'fmod.dll presente mais impossible a charger : {dll} : {exc}') from exc
    # Importer archspec ne suffit pas : son JSON est charge paresseusement.
    # Forcer un vrai acces au catalogue CPU depuis l'EXE compile.
    import archspec.cpu
    if archspec.cpu.TARGETS['x86_64'].name != 'x86_64':
        raise RuntimeError('La base microarchitectures.json ne peut pas etre lue')
    import UnityPy
    if not callable(UnityPy.load):
        raise RuntimeError('UnityPy.load absent du paquet')
    # Les fichiers de métadonnées Unity sont indispensables au lecteur de sprites.
    contents=list(importlib.resources.files('UnityPy.resources').iterdir())
    if not contents:
        raise RuntimeError('UnityPy.resources est vide après empaquetage')


def _verify_icon_extractor():
    """Test compilé indépendant du jeu : Sprite et Texture2D synthétiques."""
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from PIL import Image
    from game_icon_extraction import extract_owned_icons
    with TemporaryDirectory() as base:
        root=Path(base)/'Valheim'
        bundles=root/'valheim_Data'/'StreamingAssets'/'SoftRef'/'Bundles'
        bundles.mkdir(parents=True)
        (root/'valheim.exe').write_bytes(b'MZ')
        (bundles/'sample').write_bytes(b'UnityFS')
        photo=Image.new('RGBA',(32,32),(170,80,35,255))
        def make(kind,name):
            return SimpleNamespace(
                type=SimpleNamespace(name=kind),
                parse_as_object=lambda:SimpleNamespace(m_Name=name,image=photo))
        count=extract_owned_icons(root,Path(base)/'icons',
            unity_loader=lambda _:SimpleNamespace(
                objects=[make('Sprite','Icon_Wood'),
                         make('Texture2D','Inventory_Honey')]))
        if count!=2:
            raise RuntimeError(f'Extraction de contrôle incomplète : {count}/2')

def _verify_wiki_cache():
    """Verifie les imports natifs wiki/Pillow depuis l'executable PyInstaller."""
    import tempfile
    from pathlib import Path
    from PIL import Image, ImageOps
    from wiki_images import WikiImageCache, wiki_title
    if wiki_title('$enemy_greyling') != 'Greyling':
        raise RuntimeError('Mapping du prefab Greyling incorrect')
    with tempfile.TemporaryDirectory() as temp:
        cache=WikiImageCache(Path(temp)/'wiki_cache')
        if cache.count()!=0 or cache.cached_image('$enemy_greyling') is not None:
            raise RuntimeError('Le cache wiki de controle est non vide')
        image=Image.new('RGB',(30,30),(123,45,67))
        image=ImageOps.exif_transpose(image)
        if image.size != (30,30):
            raise RuntimeError('Le decodeur Pillow ImageOps ne fonctionne pas')


def _verify_safe_updater():
    """Vérifie l'archive sans exécution ni extraction dans l'EXE PyInstaller."""
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from zipfile import ZipFile
    from windows_update import validate_archive, UpdateError
    with TemporaryDirectory() as directory:
        archive=Path(directory)/'windows.zip'
        with ZipFile(archive,'w') as package:
            package.writestr('ValheimStatsTracker/ValheimStatsTracker.exe',b'MZ')
        validate_archive(archive)
        archive.write_bytes(b'not a zip')
        try:
            validate_archive(archive)
        except UpdateError:
            pass
        else:
            raise RuntimeError('Archive corrompue acceptée par le vérificateur')




def _verify_game_sprites_bundle():
    """Dans le VRAI EXE, teste les pixels de chaque icône attendue par l'UI."""
    import json
    from PySide6.QtWidgets import QApplication
    from real_assets import bundled_assets, manifest, game_icon
    from game_visuals import (
        required_inventory_items, STAT_ITEMS, NAV_ITEMS, BOSS_ITEMS, SKILL_ITEMS
    )
    from viking_stats import STATS
    from valheim_reader import BOSSES, SKILLS
    app = QApplication.instance() or QApplication([])
    index_path = bundled_assets() / 'GAME_ICONS_AUDIT.json'
    if not index_path.is_file():
        raise RuntimeError('Audit du pack de sprites Valheim manquant dans le programme')
    audit = json.loads(index_path.read_text(encoding='utf8'))
    if audit.get('selected_icons', 0) < 38:
        raise RuntimeError('Nombre insuffisant de sprites Valheim authentiques')
    if set(STAT_ITEMS) != {stat.key for stat in STATS}:
        raise RuntimeError('Statistiques manquant une association à un objet Valheim')
    if set(BOSS_ITEMS) != set(BOSSES):
        raise RuntimeError('Boss manquant une illustration du jeu')
    if not set(SKILLS.values()).issubset(SKILL_ITEMS):
        raise RuntimeError('Compétence manquant une illustration')
    for item in sorted(required_inventory_items()):
        icon = game_icon(item)
        if icon.isNull() or icon.pixmap(53,53).isNull():
            raise RuntimeError('Sprite Valheim absent du programme : ' + item)
    print(f"{len(required_inventory_items())} icônes originales Valheim présentes dans l'EXE",flush=True)




if __name__=='__main__':
    import sys
    if '--verify-update-ready' in sys.argv:
        try:
            expected = sys.argv[sys.argv.index('--verify-update-ready') + 1]
            _verify_update_ready(expected)
        except Exception:
            import traceback
            details = traceback.format_exc()
            if '--update-diagnostics' in sys.argv:
                try:
                    logpath = Path(sys.argv[sys.argv.index('--update-diagnostics') + 1])
                    logpath.write_text(details, encoding='utf-8')
                except (OSError, IndexError):
                    pass
            traceback.print_exc()
            sys.exit(25)
        sys.exit(0)
    if '--verify-real-icons' in sys.argv:
        try:
            _verify_game_sprites_bundle()
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(24)
        sys.exit(0)
    if '--verify-wiki-cache' in sys.argv:
        try:
            _verify_wiki_cache()
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(23)
        sys.exit(0)
    if '--verify-safe-updater' in sys.argv:
        try:
            _verify_safe_updater()
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(22)
        sys.exit(0)
    if '--verify-icon-extractor' in sys.argv:
        try:
            _verify_icon_extractor()
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(20)
        sys.exit(0)
    if '--verify-unitypy-bundle' in sys.argv:
        try:
            _verify_unitypy_bundle()
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(19)
        sys.exit(0)
    sys.exit(main())
