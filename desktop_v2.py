"""Valheim Stats Tracker 2.0 — interface PySide6 autonome Windows.

Grille et graphiques natifs Qt, sans webview ni réseau pour lire les sauvegardes.
Les succès reflètent uniquement les statistiques .fch, jamais l'état Steam.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTimer, QUrl, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QToolTip, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from valheim_reader import BOSSES, evaluate_all, metrics, prefab_label
from v2_core import (
    VERSION, TrackerStore, history_series, pending_actions,
    progress_ranking, session_report,
)

NAVY = "#0c1323"
SIDE = "#111a2c"
PANEL = "#182339"
PANEL2 = "#202d45"
BORDER = "#2a3851"
WHITE = "#edf4ff"
MUTED = "#9caec8"
GOLD = "#e9bd71"
GREEN = "#69d6a2"
BLUE = "#6da9ff"


QSS = f"""
QMainWindow, QWidget {{ background: {NAVY}; color: {WHITE}; font: 10pt 'Segoe UI'; }}
QFrame#sidebar {{ background: {SIDE}; border-right: 1px solid {BORDER}; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#metric {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#section {{ font-size: 16pt; font-weight: 700; color: {WHITE}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#metricValue {{ color: {GOLD}; font-size: 23pt; font-weight: 700; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 9px 15px; font-weight: 600; }}
QPushButton:hover {{ border: 1px solid {BLUE}; background: #253d5a; }}
QPushButton:pressed {{ background: #34506e; }}
QPushButton#primary {{ color: {NAVY}; background: {GOLD}; border-color: {GOLD}; }}
QPushButton#primary:hover {{ background: #ffd58e; }}
QPushButton#nav {{ background: transparent; border: none; border-radius: 9px;
    text-align: left; padding: 11px 15px; color: {MUTED}; }}
QPushButton#nav:hover {{ background: {PANEL2}; color: {WHITE}; }}
QPushButton#nav:checked {{ background: #2b405b; color: {WHITE}; border-left: 3px solid {GOLD}; }}
QLineEdit, QComboBox {{ background: {PANEL2}; color: {WHITE}; border: 1px solid {BORDER};
    border-radius: 7px; padding: 8px; selection-background-color: #3c638c; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; color: {WHITE}; }}
QTableWidget, QTreeWidget {{ background: {PANEL}; alternate-background-color: #1d2a40;
    color: {WHITE}; border: 0; gridline-color: {BORDER}; selection-background-color: #355578;
    outline: none; }}
QHeaderView::section {{ background: {PANEL2}; color: {MUTED}; font-weight: 600;
    padding: 9px; border: 0; border-right: 1px solid {BORDER}; }}
QTableWidget::item, QTreeWidget::item {{ padding: 6px 5px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ width: 11px; background: {NAVY}; }}
QScrollBar::handle:vertical {{ background: #415571; min-height: 35px; border-radius: 4px; }}
QProgressBar {{ background: #101a2a; color: {WHITE}; border-radius: 7px; height: 14px;
    text-align: center; border: 0; }}
QProgressBar::chunk {{ background: {BLUE}; border-radius: 7px; }}
QToolTip {{ background: #22314a; color: {WHITE}; border: 1px solid {BLUE}; padding: 7px; }}
"""


def label(text="", *, muted=False, section=False, size=None, wrap=False):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if muted:
        widget.setObjectName("muted")
    if section:
        widget.setObjectName("section")
    if size:
        font = widget.font()
        font.setPointSize(size)
        widget.setFont(font)
    widget.setWordWrap(wrap)
    return widget


def panel(title="", subtitle=""):
    outer = QFrame()
    outer.setObjectName("panel")
    layout = QVBoxLayout(outer)
    layout.setContentsMargins(19, 17, 19, 18)
    layout.setSpacing(11)
    if title:
        layout.addWidget(label(title, section=True))
    if subtitle:
        layout.addWidget(label(subtitle, muted=True, wrap=True))
    return outer, layout


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    widget.setAlternatingRowColors(True)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return widget


def txt(value, decimal=0):
    if isinstance(value, float) and abs(value - round(value)) > 0.0001:
        return f"{value:,.{max(1, decimal)}f}".replace(",", " ").replace(".", ",")
    return f"{int(value):,}".replace(",", " ")


class TrendChart(QWidget):
    """Courbe Qt interactive : survol d'un relevé et zoom de période."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.caption = "Évolution des relevés"
        self.setMouseTracking(True)
        self.setMinimumHeight(270)
        self.hover_index = -1
        self.coords = []

    def set_data(self, points, title="Évolution des relevés"):
        self.points = sorted((float(x), float(y)) for x, y in points)
        self.caption = title
        self.hover_index = -1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor(PANEL))
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(18, 28, self.caption)
        area = QRectF(63, 44, max(80, rect.width()-87), max(90, rect.height()-87))
        self.coords = []
        if not self.points:
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, "Pas encore assez de relevés")
            p.end()
            return
        values = [y for _, y in self.points]
        xvalues = [x for x, _ in self.points]
        ymin, ymax = min(values), max(values)
        if abs(ymax-ymin) < 1e-6:
            ymin -= max(1, ymax*.02)
            ymax += max(1, ymax*.02)
        else:
            pad = (ymax-ymin)*.13
            ymin -= pad
            ymax += pad
        tmin, tmax = min(xvalues), max(xvalues)
        if tmin == tmax:
            tmin -= 60
            tmax += 60
        for i in range(5):
            yy = area.top()+i*area.height()/4
            p.setPen(QPen(QColor("#344157"), 1))
            p.drawLine(QPointF(area.left(), yy), QPointF(area.right(), yy))
            p.setPen(QColor(MUTED))
            v = ymax - i*(ymax-ymin)/4
            p.drawText(QRectF(0, yy-9, 55, 18), Qt.AlignmentFlag.AlignRight, txt(v,1))
        for i in range(3):
            t = tmin + (tmax-tmin)*i/2
            x = area.left()+area.width()*i/2
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x-47, area.bottom()+7, 94, 20), Qt.AlignmentFlag.AlignHCenter,
                       datetime.fromtimestamp(t).strftime("%d/%m %H:%M"))
        route = QPainterPath()
        for idx, (timestamp, value) in enumerate(self.points):
            x = area.left()+(timestamp-tmin)/(tmax-tmin)*area.width()
            y = area.bottom()-(value-ymin)/(ymax-ymin)*area.height()
            position = QPointF(x, y)
            self.coords.append(position)
            if idx == 0:
                route.moveTo(position)
            else:
                route.lineTo(position)
        if len(self.coords) > 1:
            shade = QPainterPath(route)
            shade.lineTo(self.coords[-1].x(), area.bottom())
            shade.lineTo(self.coords[0].x(), area.bottom())
            shade.closeSubpath()
            gradient = QLinearGradient(0, area.top(), 0, area.bottom())
            gradient.setColorAt(0, QColor(91, 155, 244, 90))
            gradient.setColorAt(1, QColor(91, 155, 244, 0))
            p.fillPath(shade, gradient)
        p.setPen(QPen(QColor(BLUE), 2.5))
        p.drawPath(route)
        if self.coords:
            idx = max(0, min(len(self.coords)-1, self.hover_index)) if self.hover_index >= 0 else len(self.coords)-1
            p.setPen(QPen(QColor(GOLD if self.hover_index >= 0 else GREEN), 2))
            p.setBrush(QColor(PANEL))
            p.drawEllipse(self.coords[idx], 5, 5)
        p.end()

    def mouseMoveEvent(self, event):
        if not self.points or not self.coords:
            return
        x = event.position().x()
        idx = min(range(len(self.coords)), key=lambda i: abs(self.coords[i].x()-x))
        if idx != self.hover_index:
            self.hover_index = idx
            date, value = self.points[idx]
            QToolTip.showText(event.globalPosition().toPoint(),
                              datetime.fromtimestamp(date).strftime("%d/%m/%Y %H:%M")
                              + "\nValeur : " + txt(value,2), self)
            self.update()

    def leaveEvent(self, event):
        self.hover_index = -1
        QToolTip.hideText()
        self.update()


class TrackerWindow(QMainWindow):
    NAV = [("Vue d’ensemble", "Accueil"), ("Succès", "Succès"),
           ("Combat", "Combats"), ("Historique", "Historique"),
           ("Réglages", "Réglages")]

    def __init__(self, store=None):
        super().__init__()
        self.store = store if store is not None else TrackerStore()
        self.results = []
        self.selected_achievement = ""
        self.current_page = 0
        self.setWindowTitle("Valheim Stats Tracker • V" + VERSION)
        self.resize(1520, 940)
        self.setMinimumSize(1040, 700)
        self.setStyleSheet(QSS)
        self._build()
        self.show_page(0)
        if self.store.path:
            self.refresh_save(force=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_save)
        self.timer.start(5000)

    def _build(self):
        frame = QWidget()
        self.setCentralWidget(frame)
        horizontal = QHBoxLayout(frame)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        left = QFrame()
        left.setObjectName("sidebar")
        left.setFixedWidth(225)
        ls = QVBoxLayout(left)
        ls.setContentsMargins(16, 25, 16, 19)
        ls.setSpacing(10)
        mark = label("VALHEIM", size=22)
        mark.setStyleSheet(f"color: {GOLD}; font-weight: 900")
        ls.addWidget(mark)
        ls.addWidget(label("STATS TRACKER", muted=True, size=10))
        ls.addSpacing(23)
        self.nav_buttons = []
        for idx, (name, _) in enumerate(self.NAV):
            btn = QPushButton(name)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=idx: self.show_page(i))
            ls.addWidget(btn)
            self.nav_buttons.append(btn)
        ls.addStretch()
        ls.addWidget(label("PERSONNAGE", muted=True))
        self.sidebar_character = label("Aucun personnage", wrap=True)
        self.sidebar_character.setStyleSheet("font-weight:700")
        ls.addWidget(self.sidebar_character)
        ls.addWidget(label("Version " + VERSION + " • Lecture seule", muted=True))
        horizontal.addWidget(left)

        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(24, 19, 25, 17)
        ml.setSpacing(16)
        header = QHBoxLayout()
        titlecolumn = QVBoxLayout()
        titlecolumn.setSpacing(3)
        self.header_title = label("Vue d’ensemble", section=True)
        self.header_status = label("Sélectionne ton personnage pour afficher les statistiques.", muted=True, wrap=True)
        titlecolumn.addWidget(self.header_title)
        titlecolumn.addWidget(self.header_status)
        header.addLayout(titlecolumn, 1)
        self.btn_file = QPushButton("Choisir un personnage")
        self.btn_file.clicked.connect(self.choose_file)
        header.addWidget(self.btn_file)
        self.btn_refresh = QPushButton("↻ Actualiser")
        self.btn_refresh.setObjectName("primary")
        self.btn_refresh.clicked.connect(lambda: self.refresh_save(force=True))
        header.addWidget(self.btn_refresh)
        ml.addLayout(header)
        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)
        self._make_dashboard()
        self._make_achievements()
        self._make_combat()
        self._make_history()
        self._make_settings()
        horizontal.addWidget(main, 1)
        self.statusBar().showMessage("Sauvegardes .fch lues en lecture seule • Mise à jour toutes les 5 secondes")

    def _scroll_page(self):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(4, 3, 6, 12)
        layout.setSpacing(15)
        scroller.setWidget(inner)
        self.stack.addWidget(scroller)
        return layout

    def _metric(self, title, hint=""):
        box = QFrame()
        box.setObjectName("metric")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(17, 13, 17, 14)
        layout.addWidget(label(title, muted=True))
        val = label("—")
        val.setObjectName("metricValue")
        layout.addWidget(val)
        layout.addWidget(label(hint, muted=True, wrap=True))
        return box, val

    def _make_dashboard(self):
        layout = self._scroll_page()
        metricsrow = QHBoxLayout()
        self.dash_metrics = {}
        for key, title, hint in (
            ("kills", "Créatures tuées", "Toutes difficultés"),
            ("bosses", "Boss vaincus", "Sur les huit boss"),
            ("deaths", "Décès", "Enregistrés sur le personnage"),
            ("world_hours", "Temps de jeu", "Tous mondes cumulés"),
        ):
            box, value = self._metric(title, hint)
            self.dash_metrics[key] = value
            metricsrow.addWidget(box)
        layout.addLayout(metricsrow)
        split = QHBoxLayout()
        a, al = panel("OBJECTIFS PRIORITAIRES", "Succès mesurables les plus proches d’être terminés")
        self.dash_priority = table(["Succès", "Progression", "À terminer"])
        al.addWidget(self.dash_priority)
        split.addWidget(a, 3)
        b, bl = panel("DERNIÈRE SESSION", "Gains estimés entre sauvegardes rapprochées")
        self.dash_session = label("Pas de relevés disponibles.", muted=True, wrap=True)
        self.dash_session.setAlignment(Qt.AlignmentFlag.AlignTop)
        bl.addWidget(self.dash_session, 1)
        split.addWidget(b, 2)
        layout.addLayout(split, 2)
        c, cl = panel("PROGRESSION DANS LE TEMPS", "Survole la courbe pour lire la date et la valeur exacte")
        self.dash_chart = TrendChart()
        cl.addWidget(self.dash_chart)
        layout.addWidget(c, 1)

    def _make_achievements(self):
        body = QWidget()
        row = QHBoxLayout(body)
        row.setContentsMargins(4, 3, 6, 8)
        row.setSpacing(15)
        self.stack.addWidget(body)
        left, leftlayout = panel("SUCCÈS VALHEIM", "53 succès actifs + 2 entrées internes non vérifiées")
        searchrow = QHBoxLayout()
        self.ach_search = QLineEdit()
        self.ach_search.setPlaceholderText("Rechercher un succès, objet, créature…")
        self.ach_search.textChanged.connect(self.draw_achievements)
        searchrow.addWidget(self.ach_search, 2)
        self.ach_filter = QComboBox()
        self.ach_filter.addItems(["Tous", "À terminer", "Favoris", "Atteints", "Non calculables"])
        self.ach_filter.currentTextChanged.connect(self.draw_achievements)
        searchrow.addWidget(self.ach_filter, 1)
        leftlayout.addLayout(searchrow)
        self.ach_tree = QTreeWidget()
        self.ach_tree.setHeaderLabels(["Succès", "Progression", "Critères"])
        self.ach_tree.setColumnWidth(0, 255)
        self.ach_tree.setColumnWidth(1, 115)
        self.ach_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.ach_tree.itemSelectionChanged.connect(self.selected_success_changed)
        leftlayout.addWidget(self.ach_tree)
        row.addWidget(left, 3)
        detail, details = panel("DÉTAIL DE L’OBJECTIF", "Données calculées depuis les sauvegardes, pas depuis Steam")
        self.ach_title = label("Sélectionne un succès", section=True, wrap=True)
        details.addWidget(self.ach_title)
        self.ach_desc = label("", muted=True, wrap=True)
        details.addWidget(self.ach_desc)
        self.ach_bar = QProgressBar()
        self.ach_bar.setRange(0, 1000)
        details.addWidget(self.ach_bar)
        controls = QHBoxLayout()
        self.ach_favorite_btn = QPushButton("☆ Ajouter aux favoris")
        self.ach_favorite_btn.clicked.connect(self.toggle_favorite)
        controls.addWidget(self.ach_favorite_btn)
        controls.addStretch()
        details.addLayout(controls)
        self.ach_parts = table(["Critère à accomplir", "Restant"])
        details.addWidget(self.ach_parts, 1)
        row.addWidget(detail, 2)

    def _make_combat(self):
        layout = self._scroll_page()
        top, tl = panel("BOSS", "Éliminations comptées par groupe de difficulté, sans additionner les groupes")
        controls = QHBoxLayout()
        controls.addWidget(label("Difficulté :"))
        self.combat_group = QComboBox()
        for title, group in [("Toutes difficultés", "Any"), ("Normal ou supérieur", "Default"),
                             ("Difficile ou supérieur", "Hard"), ("Très difficile", "VeryHard"),
                             ("Extrême", "Hardcore")]:
            self.combat_group.addItem(title, group)
        self.combat_group.currentIndexChanged.connect(self.draw_combat)
        controls.addWidget(self.combat_group)
        controls.addStretch()
        tl.addLayout(controls)
        self.combat_bosses = table(["Boss", "Victoires enregistrées"])
        tl.addWidget(self.combat_bosses)
        layout.addWidget(top, 1)
        bottom, bl = panel("BESTIAIRE", "Total enregistré pour les créatures de la difficulté sélectionnée")
        self.combat_enemies = table(["Créature", "Éliminations"])
        bl.addWidget(self.combat_enemies)
        layout.addWidget(bottom, 2)

    def _make_history(self):
        layout = self._scroll_page()
        graph, gl = panel("ÉVOLUTION DES STATISTIQUES", "Graphique interactif • Passe la souris sur un relevé")
        settings = QHBoxLayout()
        settings.addWidget(label("Statistique :", muted=True))
        self.history_metric = QComboBox()
        for title, key in [("Créatures tuées", "kills"), ("Objets fabriqués", "crafted"),
                           ("Constructions", "built"), ("Décès", "deaths"),
                           ("Arbres abattus", "Tree"), ("Cultures récoltées", "HarvestCrop"),
                           ("Miel récolté", "BeesHarvested"), ("Heures de jeu", "world_hours"),
                           ("Niveau de course", "skill:Course"),
                           ("Magie élémentaire", "skill:Magie élémentaire"),
                           ("Magie du sang", "skill:Magie du sang")]:
            self.history_metric.addItem(title, key)
        self.history_metric.currentIndexChanged.connect(self.draw_charts)
        settings.addWidget(self.history_metric, 3)
        settings.addWidget(label("Période :", muted=True))
        self.history_period = QComboBox()
        for title, seconds in [("Tout", None), ("7 jours", 604800),
                               ("30 jours", 2592000), ("90 jours", 7776000)]:
            self.history_period.addItem(title, seconds)
        self.history_period.currentIndexChanged.connect(self.draw_charts)
        settings.addWidget(self.history_period, 1)
        gl.addLayout(settings)
        self.history_chart = TrendChart()
        self.history_chart.setMinimumHeight(400)
        gl.addWidget(self.history_chart, 1)
        layout.addWidget(graph, 3)
        report, rl = panel("RAPPORT DE SESSION ESTIMÉE", "Deux relevés proches sont nécessaires")
        self.history_report = label("Aucun relevé.", muted=True, wrap=True)
        rl.addWidget(self.history_report)
        layout.addWidget(report)

    def _make_settings(self):
        layout = self._scroll_page()
        config, cl = panel("FICHIER DE PERSONNAGE", "Le suivi reste en lecture seule ; le chemin est partagé avec la V1.9")
        self.settings_path = label("Aucun fichier sélectionné.", muted=True, wrap=True)
        cl.addWidget(self.settings_path)
        b = QPushButton("Sélectionner une sauvegarde .fch")
        b.clicked.connect(self.choose_file)
        cl.addWidget(b)
        layout.addWidget(config)
        updates, ul = panel("MISES À JOUR", "Vérifier les nouvelles versions officielles sur GitHub")
        ul.addWidget(label(
            "La V2.0 est distribuée en application Windows autonome. Pour une nouvelle version, "
            "télécharge l'archive Windows depuis les Releases. Le paquet de mise à jour V1.x "
            "reste disponible séparément pour les installations Python.",
            muted=True, wrap=True))
        gh = QPushButton("Ouvrir les versions sur GitHub")
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest")))
        ul.addWidget(gh)
        layout.addWidget(updates)
        about, al = panel("DONNÉES ET CONFIDENTIALITÉ", "Aucune connexion nécessaire pour analyser un personnage")
        al.addWidget(label(
            "Les statistiques, favoris et anciens relevés restent dans :\n"
            "%LOCALAPPDATA%\\ValheimStatsTracker\\\n\n"
            "Le logiciel ne modifie jamais la sauvegarde .fch. Les succès affichés "
            "sont estimés à partir des statistiques enregistrées ; ils ne prouvent "
            "pas qu'un succès Steam a été officiellement débloqué.",
            muted=True, wrap=True))
        layout.addWidget(about)
        layout.addStretch()

    def show_page(self, index):
        self.current_page = index
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.header_title.setText(self.NAV[index][0])

    def choose_file(self):
        initial = str(Path(self.store.path).parent) if self.store.path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Choisir un personnage Valheim",
                                               initial, "Sauvegardes Valheim (*.fch)")
        if not path:
            return
        try:
            self.store.choose(path)
            self.refresh_save(force=True)
        except Exception as error:
            QMessageBox.critical(self, "Fichier non valide", str(error))

    def refresh_save(self, force=False):
        try:
            result = self.store.refresh(force=force)
        except Exception as error:
            self.header_status.setText("Erreur de lecture : " + str(error))
            if force:
                QMessageBox.critical(self, "Sauvegarde inaccessible", str(error))
            return
        kind = result["state"]
        self.header_status.setText(result["message"] + (" · " + Path(self.store.path).name if self.store.path else ""))
        self.statusBar().showMessage("Vérification à " + datetime.now().strftime("%H:%M:%S")
                                     + " • " + result["message"])
        if kind == "updated":
            self.populate()
        elif kind == "missing" and force:
            self.choose_file()

    def populate(self):
        profile = self.store.profile
        if not profile:
            return
        self.sidebar_character.setText(profile["name"])
        self.settings_path.setText(self.store.path)
        self.results = evaluate_all(profile)
        self.draw_dashboard()
        self.draw_achievements()
        self.draw_combat()
        self.draw_charts()
        self.draw_session()

    def draw_dashboard(self):
        if not self.store.profile:
            return
        result = metrics(self.store.profile, "Any")
        for key in ("kills", "deaths"):
            self.dash_metrics[key].setText(txt(result[key]))
        self.dash_metrics["bosses"].setText(f"{result['bosses']} / 8")
        self.dash_metrics["world_hours"].setText(txt(result["world_hours"], 1) + " h")
        ranked = progress_ranking(self.results, self.store.favorites())[:8]
        self.dash_priority.setRowCount(len(ranked))
        for i, row in enumerate(ranked):
            parts = row["total_conditions"] - row["completed_conditions"]
            for j, text in enumerate((row["title"], f"{row['percent']:.1f} %", str(parts))):
                self.dash_priority.setItem(i, j, QTableWidgetItem(str(text)))
        self.dash_priority.resizeRowsToContents()
        rows = self.store.rows()
        self.dash_chart.set_data(history_series(rows, "kills"), "Créatures vaincues • total cumulé")

    def draw_achievements(self):
        if not self.store.profile:
            return
        prev = self.selected_achievement
        q = self.ach_search.text().casefold().strip()
        filt = self.ach_filter.currentText()
        favorites = self.store.favorites()
        visible = []
        for row in self.results:
            if q and not any(q in str(x).casefold() for x in (
                    row["title"], row.get("title_en", ""), row.get("description", ""),
                    row.get("category", ""))):
                continue
            if filt == "À terminer" and (not row["measurable"] or row["complete"]):
                continue
            if filt == "Favoris" and row["key"] not in favorites:
                continue
            if filt == "Atteints" and not row["complete"]:
                continue
            if filt == "Non calculables" and row["measurable"]:
                continue
            visible.append(row)
        self.ach_tree.blockSignals(True)
        self.ach_tree.clear()
        selected_item = None
        for row in visible:
            ratio = "Non calculable" if not row["measurable"] else f"{row['percent']:.1f} %"
            count = "—" if not row["measurable"] else f"{row['completed_conditions']} / {row['total_conditions']}"
            item = QTreeWidgetItem([
                ("★  " if row["key"] in favorites else "") + row["title"], ratio, count])
            item.setData(0, Qt.ItemDataRole.UserRole, row["key"])
            if row["complete"]:
                item.setForeground(0, QColor(GREEN))
            self.ach_tree.addTopLevelItem(item)
            if row["key"] == prev:
                selected_item = item
        if selected_item is None and visible:
            selected_item = self.ach_tree.topLevelItem(0)
        if selected_item:
            self.ach_tree.setCurrentItem(selected_item)
            self.selected_achievement = selected_item.data(0, Qt.ItemDataRole.UserRole)
        else:
            self.selected_achievement = ""
        self.ach_tree.blockSignals(False)
        self.draw_success_detail()

    def selected_success_changed(self):
        item = self.ach_tree.currentItem()
        if item:
            self.selected_achievement = item.data(0, Qt.ItemDataRole.UserRole)
        self.draw_success_detail()

    def draw_success_detail(self):
        row = next((x for x in self.results if x["key"] == self.selected_achievement), None)
        if not row:
            self.ach_title.setText("Aucun objectif sélectionné")
            self.ach_desc.setText("Modifie le filtre pour afficher des succès.")
            self.ach_bar.setValue(0)
            self.ach_parts.setRowCount(0)
            return
        self.ach_title.setText(row["title"])
        self.ach_desc.setText(row.get("description", "") + ("\n" + row.get("note", "") if row.get("note") else ""))
        self.ach_bar.setValue(round(float(row["fraction"] or 0)*1000) if row["measurable"] else 0)
        self.ach_bar.setFormat("Non calculable" if not row["measurable"] else f"{row['percent']:.1f} %")
        self.ach_favorite_btn.setText("★ Retirer des favoris" if row["key"] in self.store.favorites()
                                      else "☆ Ajouter aux favoris")
        parts = pending_actions(row, 200) if row["measurable"] and not row["complete"] else row["parts"][:50]
        self.ach_parts.setRowCount(len(parts))
        for i, part in enumerate(parts):
            remaining = part.get("remaining")
            text = "—" if remaining is None else txt(float(remaining), 1)
            self.ach_parts.setItem(i, 0, QTableWidgetItem(str(part["label"])))
            self.ach_parts.setItem(i, 1, QTableWidgetItem(text))
        self.ach_parts.resizeRowsToContents()

    def toggle_favorite(self):
        if not self.selected_achievement:
            return
        try:
            self.store.toggle_favorite(self.selected_achievement)
        except Exception as error:
            QMessageBox.critical(self, "Enregistrement impossible", str(error))
            return
        self.draw_achievements()
        self.draw_dashboard()

    def draw_combat(self):
        if not self.store.profile:
            return
        group = self.combat_group.currentData()
        data = self.store.profile["groups"][group]
        killed = data["enemies"][0]
        self.combat_bosses.setRowCount(len(BOSSES))
        for index, (token, name) in enumerate(BOSSES.items()):
            self.combat_bosses.setItem(index, 0, QTableWidgetItem(name))
            self.combat_bosses.setItem(index, 1, QTableWidgetItem(txt(killed.get(token, 0))))
        enemies = sorted(((prefab_label(token), count) for token, count in killed.items() if count > 0),
                         key=lambda p: (-p[1], p[0]))
        self.combat_enemies.setRowCount(len(enemies))
        for index, (name, count) in enumerate(enemies):
            self.combat_enemies.setItem(index, 0, QTableWidgetItem(name))
            self.combat_enemies.setItem(index, 1, QTableWidgetItem(txt(count)))

    def draw_charts(self):
        if not self.store.profile:
            return
        rows = self.store.rows(limit=500)
        key = self.history_metric.currentData()
        period = self.history_period.currentData()
        points = history_series(rows, key, since_seconds=period)
        self.history_chart.set_data(points, self.history_metric.currentText())

    def draw_session(self):
        if not self.store.profile:
            return
        report = session_report(self.store.rows(limit=500))
        if not report["available"]:
            self.history_report.setText(report["reason"] + "\nAucune durée ni aucun gain ne sont inventés.")
            self.dash_session.setText(report["reason"])
            return
        summary = f"{report['samples']} sauvegardes • {report['game_minutes']:.0f} min de jeu observées\n"
        summary += "Du " + datetime.fromtimestamp(report["start"]).strftime("%d/%m %H:%M")
        summary += " au " + datetime.fromtimestamp(report["end"]).strftime("%d/%m %H:%M")
        changes = [(name, value) for name, value in report["changes"].items() if value > 0]
        lines = [f"{name} : +{txt(value,1)}" for name, value in changes]
        if report["reached"]:
            lines += ["\nObjectifs atteints : " + ", ".join(report["reached"][:5])]
        if report["skills"]:
            lines += ["Compétences : " + ", ".join(f"{name} +{gain:.2f}" for name, gain in report["skills"][:4])]
        if report["resets"]:
            lines += ["Compteurs diminués (non comptabilisés) : " + ", ".join(report["resets"])]
        lines += ["\nSession estimée, pas un suivi en temps réel."]
        report_text = summary + "\n\n" + "\n".join(lines)
        self.history_report.setText(report_text)
        self.dash_session.setText(report_text)

    def closeEvent(self, event):
        self.timer.stop()
        self.store.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Valheim Stats Tracker")
    app.setStyle("Fusion")
    window = TrackerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
