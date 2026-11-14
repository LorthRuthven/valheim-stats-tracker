"""Interface V2.1 « Chroniques nordiques » : SVG embarqués et animations Qt.

La gestion des sauvegardes, du suivi des succès et des favoris est héritée
sans modification de l'interface V2.0. Aucun téléchargement au démarrage.
"""
from __future__ import annotations

import math
import json
from pathlib import Path
from PySide6.QtCore import Qt, QByteArray, QRectF, QTimer, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QIcon, QPixmap, QLinearGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QWidget, QSizePolicy,
    QGraphicsOpacityEffect, QProgressBar, QCheckBox
)
from desktop_v2 import TrackerWindow as BaseTracker, TrendChart, label, panel
from v2_core import VERSION, progress_ranking

BG='#0c1117'; SIDEBAR='#111b22'; PANEL='#17232c'
BRONZE='#e9b77b'; FG='#f1eee8'; MUTED='#afc0bd'
ICON_PATH={
 'home': 'M3 11l9-8 9 8v10H4V11 M9 21v-8h6v8',
 'trophy': 'M7 4h10v5a5 5 0 0 1-10 0V4 M7 6H4v3c0 2 2 4 5 4M17 6h3v3c0 2-2 4-5 4M12 14v5 M7 21h10',
 'skull': 'M5 12a7 7 0 1 1 14 0c0 3-2 4-3 5v4H8v-4c-1-1-3-2-3-5z M9 12v2m6-2v2 M10 18h4',
 'history': 'M12 3a9 9 0 1 1-9 9 M12 7v5l4 3 M3 5v6h6',
 'settings': 'M12 2v4m0 12v4M2 12h4m12 0h4M5 5l3 3m8 8 3 3M5 19l3-3m8-8 3-3 M12 9a3 3 0 1 1 0 6a3 3 0 0 1 0-6',
 'paw': 'M7 18c0-4 4-6 5-6s5 2 5 6c0 4-10 4-10 0 M5 9v2 M10 6v2 M15 6v2 M20 9v2',
 'shield': 'M12 2l9 4v7c-1 7-9 10-9 10S4 20 3 13V6z M12 6v13 M7 12h10',
 'clock': 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M12 6v7l4 2',
 'compass': 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M15 9l-2 6-5 2 2-6z',
 'axe': 'M5 21L17 3M15 4c8-2 8 7 2 10l-5-6',
 'tree': 'M12 2L5 12h4l-6 7h18l-6-7h4z M12 19v4',
 'flame': 'M13 2c2 6-3 6 0 10 2-1 3-3 3-5 7 8 4 15-4 15S2 15 8 9c0 3 2 3 2 5 3-5 0-7 3-12z',
}
def rune_icon(name, size=28, color=BRONZE):
    path=ICON_PATH.get(name,ICON_PATH['shield'])
    xml=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="{path}" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    pix=QPixmap(size,size);pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix);QSvgRenderer(QByteArray(xml.encode())).render(painter);painter.end()
    return QIcon(pix)

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
QMainWindow,QWidget{{background:{BG};color:{FG};font:10pt 'Segoe UI';}}
QFrame#sidebar{{background:{SIDEBAR};border-right:1px solid #38464a;}}
QFrame#topbar{{background:#101b23;border-bottom:1px solid #33444b;}}
QFrame#panel{{background:{PANEL};border:1px solid #344b50;border-radius:14px;}}
QFrame#metric{{background:#1b2932;border:1px solid #3b5152;border-radius:13px;}}
QFrame#metric:hover{{background:#24343d;border:1px solid {BRONZE};}}
QLabel#section{{color:#fff1dd;font:bold 15pt 'Segoe UI';}}
QLabel#muted{{color:{MUTED};}}
QLabel#metricValue{{color:#fff1df;font:bold 25pt 'Segoe UI';}}
QPushButton{{background:#273842;color:{FG};border:1px solid #46575a;border-radius:9px;padding:10px 13px;font-weight:600;}}
QPushButton:hover{{background:#34515a;border-color:{BRONZE};}}
QPushButton#primary{{background:{BRONZE};color:#1c2428;border-color:#f6d79f;}}
QPushButton#nav{{background:transparent;border:1px solid transparent;text-align:left;padding:12px 14px;color:#b3c2bf;}}
QPushButton#nav:hover{{background:#273b43;border-color:#3e565a;}}
QPushButton#nav:checked{{background:#303b37;color:#ffdbae;border-color:#96774e;font-weight:bold;}}
QLineEdit,QComboBox{{background:#24343e;border:1px solid #475f61;border-radius:8px;padding:9px;color:{FG};}}
QTableWidget,QTreeWidget{{background:{PANEL};alternate-background-color:#1e2c35;border:0;color:{FG};selection-background-color:#40564f;outline:none;}}
QHeaderView::section{{background:#26373e;color:#f2cd9b;border:0;padding:10px;font-weight:bold;}}
QTableWidget::item,QTreeWidget::item{{padding:6px;}}
QScrollArea{{border:0;}}
QScrollBar:vertical{{width:10px;background:#15252d;}}
QScrollBar::handle:vertical{{background:#526b70;border-radius:5px;min-height:30px;}}
QProgressBar{{background:#12212a;border:1px solid #3d5256;border-radius:6px;color:#f2eadb;text-align:center;height:16px;}}
QProgressBar::chunk{{background:#c39557;border-radius:5px;}}
QToolTip{{background:#1a2b33;border:1px solid {BRONZE};color:#f5e6cf;padding:8px;}}
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

class Hero(Artwork):
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

class NordicWindow(BaseTracker):
    def __init__(self,store=None):
        self.motion=True
        self.fade=None
        super().__init__(store=store)
        self.setWindowTitle('Valheim Stats Tracker • Chroniques nordiques • '+VERSION)
        self.setStyleSheet(QSS)
        self.setMinimumSize(1100,740)
        self.resize(1580,940)
        self._load_motion()
    def _build(self):
        root=QWidget();self.setCentralWidget(root)
        row=QHBoxLayout(root);row.setContentsMargins(0,0,0,0);row.setSpacing(0)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(251)
        menu=QVBoxLayout(side);menu.setContentsMargins(19,21,17,19);menu.setSpacing(10)
        mast=QHBoxLayout()
        logo=Artwork(EMBLEM,61);logo.setFixedSize(61,61)
        mast.addWidget(logo)
        branding=QVBoxLayout()
        name=QLabel('VALHEIM');name.setStyleSheet('color:#f6ca88;font:bold 17pt Georgia;')
        branding.addWidget(name);branding.addWidget(label('STATS TRACKER',muted=True))
        mast.addLayout(branding);menu.addLayout(mast)
        tag=QLabel('  CHRONIQUES NORDIQUES  •  V'+VERSION)
        tag.setStyleSheet('color:#ddae6f;font:9pt Segoe UI;')
        menu.addWidget(tag);menu.addSpacing(22)
        menu.addWidget(label('LES CHAPITRES',muted=True))
        self.nav_buttons=[]
        for idx,(name,_) in enumerate(self.NAV):
            btn=QPushButton(name);btn.setObjectName('nav');btn.setCheckable(True)
            btn.setMinimumHeight(47)
            btn.setIcon(rune_icon(('home','trophy','skull','history','settings')[idx]))
            btn.clicked.connect(lambda _=False,i=idx:self.show_page(i))
            menu.addWidget(btn);self.nav_buttons.append(btn)
        menu.addStretch()
        glimpse=Artwork(HERO,114)
        menu.addWidget(glimpse)
        menu.addWidget(label('PERSONNAGE',muted=True))
        self.sidebar_character=label('Aucun personnage',wrap=True)
        self.sidebar_character.setStyleSheet('font-weight:bold;color:#f4d3a7;')
        menu.addWidget(self.sidebar_character)
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
        self.btn_refresh.setIcon(rune_icon('history',23,'#242b27'))
        self.btn_refresh.clicked.connect(lambda:self.refresh_save(force=True));head.addWidget(self.btn_refresh)
        ml.addWidget(top)
        self.stack=QStackedWidget();ml.addWidget(self.stack,1)
        self._make_dashboard();self._make_achievements();self._make_combat()
        self._make_history();self._make_settings()
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
        box.setMinimumHeight(151)
        return box,val
    def _make_dashboard(self):
        super()._make_dashboard()
        self.dash_priority.verticalHeader().setDefaultSectionSize(47)
        self.dash_priority.cellDoubleClicked.connect(self._jump_to_achievement)
    def _make_settings(self):
        super()._make_settings()
        area=self.stack.widget(4)
        inner=area.widget() if hasattr(area,'widget') else None
        if inner is not None:
            frame, layout=panel('AMBIANCE ET MOUVEMENTS',
                'Illustrations locales : aucune connexion n’est nécessaire.')
            self.motion_checkbox=QCheckBox('Activer les animations de navigation et de progression')
            self.motion_checkbox.setChecked(True)
            self.motion_checkbox.toggled.connect(self.set_motion)
            layout.addWidget(self.motion_checkbox)
            layout.addWidget(label('Illustrations vectorielles, pictogrammes et effets discrets.',muted=True,wrap=True))
            inner.layout().insertWidget(0,frame)
    def _load_motion(self):
        path=self.store.directory/'appearance.json'
        try:
            pref=json.loads(path.read_text(encoding='utf8'))
            enabled=bool(pref.get('animations',True))
        except (OSError,ValueError,AttributeError,TypeError):
            enabled=True
        self.motion=enabled
        if hasattr(self,'motion_checkbox'):
            self.motion_checkbox.blockSignals(True)
            self.motion_checkbox.setChecked(enabled)
            self.motion_checkbox.blockSignals(False)
    def set_motion(self,enabled):
        self.motion=bool(enabled)
        path=self.store.directory/'appearance.json'
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps({'animations':self.motion},indent=2),encoding='utf8')
            temp.replace(path)
        except OSError as exc:
            self.statusBar().showMessage('Réglage non enregistré : '+str(exc))
    def _jump_to_achievement(self,index,column):
        ranked=progress_ranking(self.results,self.store.favorites())[:8]
        if 0<=index<len(ranked):
            self.selected_achievement=ranked[index]['key']
            self.show_page(1);self.draw_achievements()
    def show_page(self,index):
        super().show_page(index)
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
        profile=self.store.profile
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
            if item:item.setIcon(rune_icon('trophy',24))
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
        lookup={a['key']:a for a in self.results}
        for i in range(self.ach_tree.topLevelItemCount()):
            item=self.ach_tree.topLevelItem(i)
            a=lookup.get(item.data(0,Qt.ItemDataRole.UserRole),{})
            category=a.get('category','')
            icon='skull' if category=='Boss' else 'paw' if category=='Combat' else 'axe' if category=='Construction' else 'compass' if category=='Exploration' else 'trophy'
            item.setIcon(0,rune_icon(icon,23))
    def draw_combat(self):
        super().draw_combat()
        icons=('shield','tree','skull','flame','trophy','paw','flame','compass')
        for i in range(self.combat_bosses.rowCount()):
            cell=self.combat_bosses.item(i,0)
            if cell:cell.setIcon(rune_icon(icons[i%len(icons)],24))

def main():
    import sys
    app=QApplication(sys.argv);app.setApplicationName('Valheim Stats Tracker');app.setStyle('Fusion')
    window=NordicWindow();window.show()
    return app.exec()

if __name__=='__main__':
    import sys
    sys.exit(main())
