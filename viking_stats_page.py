"""La page « Statistiques du Viking » : cartes façon Minecraft, vraies données.

Chaque icône de jeu n'est montrée que si elle existe réellement. Une rune
typographique signale une statistique pour laquelle aucune image n'a été associée.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
    QFileDialog, QMessageBox, QDialog, QProgressBar,
)

from desktop_v2 import label, panel
from character_archive import aggregation_mode, character_key, combine_profiles
from stat_breakdown import breakdown
from real_assets import game_icon
from stat_pictograms import pictogram
from viking_stats import (
    CATEGORIES, STATS, change, favorites, pretty, save_favorites, value,
)


class StatCard(QFrame):
    def __init__(self, stat, toggle, details=None):
        super().__init__()
        self.stat = stat
        self._details = details
        self.setObjectName("vikingStatCard")
        self.setMinimumHeight(154)
        self.setMinimumWidth(210)
        self.setStyleSheet(
            "QFrame#vikingStatCard {background:#192b35;border:1px solid #436069;"
            "border-radius:14px;} "
            "QFrame#vikingStatCard:hover {border:1px solid #cda271;background:#253b43;} "
            "QPushButton#statStar {border:none;background:transparent;color:#efc78d;"
            "padding:0px;font:bold 17pt 'Segoe UI';}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 11, 15, 12)
        outer.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setFixedSize(55, 55)
        self.picture.setObjectName("statPicture")
        image = game_icon(stat.icon) if stat.icon else None
        if image is not None and not image.isNull():
            self.picture.setPixmap(image.pixmap(QSize(53, 53)))
        else:
            # Pictogramme vectoriel d'interface : jamais présenté comme un item Valheim.
            self.picture.setPixmap(pictogram(stat.key,53).pixmap(QSize(53,53)))
        top.addWidget(self.picture)
        name = label(stat.title, wrap=True)
        name.setStyleSheet("color:#f4e8d7;font:bold 10pt 'Segoe UI';")
        name.setMinimumHeight(45)
        top.addWidget(name, 1)
        self.star = QPushButton("☆")
        self.star.setObjectName("statStar")
        self.star.setFixedSize(35, 35)
        self.star.setToolTip("Épingler ou retirer des favoris")
        self.star.clicked.connect(lambda _=False, key=stat.key: toggle(key))
        top.addWidget(self.star, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(top)
        self.amount = label("—")
        self.amount.setObjectName("statValue")
        self.amount.setStyleSheet("color:#fff4dc;font:bold 22pt 'Segoe UI';")
        outer.addWidget(self.amount)
        self.description = label(stat.note, muted=True, wrap=True)
        self.description.setStyleSheet("color:#b1c5c4;font:9pt 'Segoe UI';")
        outer.addWidget(self.description)
        self.delta = label("", muted=True)
        self.delta.setObjectName("statChange")
        self.delta.setStyleSheet("color:#9cd9bf;font:9pt 'Segoe UI';")
        outer.addWidget(self.delta)
        self.detail_button = QPushButton("Voir le détail par Viking  ›")
        self.detail_button.setObjectName("statBreakdownButton")
        self.detail_button.setToolTip(
            "Voir la contribution de chaque personnage au résultat cumulé"
        )
        self.detail_button.setStyleSheet(
            "QPushButton#statBreakdownButton {"
            "color:#f0c890;background:#24404a;border:1px solid #54747a;"
            "border-radius:8px;padding:7px 11px;text-align:left;font-weight:700;}"
            "QPushButton#statBreakdownButton:hover {"
            "background:#35535b;border-color:#e5ba7b;}"
        )
        self.detail_button.clicked.connect(
            lambda _=False: self._details(self.stat.key) if self._details else None
        )
        self.detail_button.setVisible(False)
        outer.addWidget(self.detail_button)

    def set_favorite(self, favorite):
        self.star.setText("★" if favorite else "☆")
        self.star.setToolTip("Retirer des favoris" if favorite else "Épingler dans les favoris")

    def set_values(self, profile, previous, group, cumulative=False):
        self.detail_button.setVisible(bool(cumulative and self._details))
        self.setMinimumHeight(185 if cumulative and self._details else 154)
        current = value(profile, self.stat, group)
        self.amount.setText(pretty(current, self.stat.unit))
        d = change(profile, previous, self.stat, group)
        if d is None or d <= 0 or self.stat.unit == "binary":
            self.delta.setText("")
        else:
            self.delta.setText("↑ +" + pretty(d, self.stat.unit) + " depuis le dernier relevé")
        rule = ""
        if cumulative or (profile and profile.get("aggregate")):
            policy = ("sum" if self.stat.counter == "@world_hours"
                      else aggregation_mode(self.stat.counter))
            rule = {"sum": "Somme des personnages", "max": "Meilleur record parmi les personnages",
                    "any": "Atteint par au moins un personnage"}[policy] + "\n"
        self.setToolTip(f"{self.stat.title}\nCompteur : {self.stat.counter}\n"
                        f"Groupe : {group}\n{rule}{self.stat.note}")



class CumulativeStatDialog(QDialog):
    """Fiche flottante : décompose un total sans cacher la page de statistiques."""

    RULES = {
        "sum": ("SOMME DES PERSONNAGES",
                "Les compteurs d'activité de chaque Viking sont additionnés."),
        "max": ("MEILLEUR RECORD",
                "Le total conserve la meilleure valeur atteinte par un Viking."),
        "any": ("AU MOINS UN VIKING",
                "Cette étape est validée dès qu'un personnage l'a atteinte."),
    }

    def __init__(self, stat, people, group, group_label, parent=None):
        super().__init__(parent)
        self.stat = stat
        self.model = breakdown(stat, people, group)
        self.rows = self.model.rows
        self.setObjectName("cumulativeStatDialog")
        self.setWindowTitle("Détail du cumul — " + stat.title)
        self.resize(750, 610)
        self.setMinimumWidth(550)
        self.setStyleSheet(
            "QDialog#cumulativeStatDialog {background:#101c24;color:#f1e8db;}"
            "QFrame#contributionRow {background:#192f39;"
            "border:1px solid #46636c;border-radius:11px;}"
            "QLabel {background:transparent;}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(13)
        head = QHBoxLayout()
        icon_holder = QLabel()
        icon_holder.setFixedSize(63, 63)
        icon_holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        game_image = game_icon(stat.icon) if stat.icon else None
        picture = (game_image if game_image is not None and not game_image.isNull()
                   else pictogram(stat.key, 57))
        icon_holder.setPixmap(picture.pixmap(QSize(57, 57)))
        head.addWidget(icon_holder)
        titles = QVBoxLayout()
        main_title = label(stat.title, wrap=True)
        main_title.setObjectName("breakdownStatTitle")
        main_title.setStyleSheet("font:bold 19pt 'Segoe UI';color:#f8e7ce;")
        titles.addWidget(main_title)
        level = label(
            f"{len(self.rows)} personnage(s)  •  Difficulté : {group_label}",
            muted=True, wrap=True,
        )
        titles.addWidget(level)
        head.addLayout(titles, 1)
        outer.addLayout(head)

        total = QFrame()
        total.setStyleSheet(
            "QFrame {background:#243a3c;border:1px solid #a48755;"
            "border-radius:13px;}"
        )
        total_layout = QVBoxLayout(total)
        total_layout.setContentsMargins(19, 14, 19, 14)
        total_label = label("TOTAL CUMULÉ", muted=True)
        total_layout.addWidget(total_label)
        self.total_amount = label(pretty(self.model.total, stat.unit))
        self.total_amount.setObjectName("breakdownTotal")
        self.total_amount.setStyleSheet(
            "color:#f6cc8b;font:bold 29pt 'Segoe UI';border:none;"
        )
        total_layout.addWidget(self.total_amount)
        outer.addWidget(total)

        rule_name, rule_text = self.RULES[self.model.policy]
        rule_label = label(rule_name, section=True, wrap=True)
        rule_label.setStyleSheet("font:bold 12pt Segoe UI;color:#f3cd91;")
        outer.addWidget(rule_label)
        rule_description = label(rule_text + " " + stat.note, muted=True, wrap=True)
        outer.addWidget(rule_description)

        section = label("DÉTAIL PAR PERSONNAGE", section=True)
        outer.addWidget(section)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(2, 3, 8, 3)
        list_layout.setSpacing(9)
        self.contribution_labels = {}
        for entry in self.rows:
            box = QFrame()
            box.setObjectName("contributionRow")
            row_layout = QVBoxLayout(box)
            row_layout.setContentsMargins(15, 11, 15, 11)
            row_layout.setSpacing(7)
            first = QHBoxLayout()
            person = label(entry.name, wrap=True)
            person.setStyleSheet("font:bold 12pt Segoe UI;color:#eee5db;")
            first.addWidget(person, 1)
            displayed = label(pretty(entry.amount, stat.unit))
            displayed.setObjectName("contributionAmount")
            displayed.setStyleSheet("font:bold 14pt Segoe UI;color:#f2c486;")
            first.addWidget(displayed)
            self.contribution_labels[entry.identity] = displayed
            row_layout.addLayout(first)
            source = "Personnage actif" if entry.source == "active" else "Archive importée"
            if entry.filename and entry.source != "active":
                source += " • " + entry.filename
            note = source
            if entry.amount is None:
                note += " • Compteur non disponible"
            elif self.model.policy == "sum" and entry.percentage is not None:
                note += f" • {entry.percentage:.1f} % du total".replace(".", ",")
            elif entry.leading:
                note += (" • Record partagé" if self.model.policy == "max"
                         else " • Objectif atteint")
            source_label = label(note, muted=True, wrap=True)
            row_layout.addWidget(source_label)
            if entry.percentage is not None:
                progress = QProgressBar()
                progress.setObjectName("characterContributionBar")
                progress.setRange(0, 1000)
                progress.setValue(round(min(100.0, max(0.0, entry.percentage)) * 10))
                progress.setTextVisible(False)
                progress.setFixedHeight(10)
                row_layout.addWidget(progress)
            list_layout.addWidget(box)
        list_layout.addStretch(1)
        scroll.setWidget(list_widget)
        outer.addWidget(scroll, 1)

        hint = label(
            "Une valeur « — » signifie que le compteur est absent du fichier. "
            "Les difficultés ne sont jamais additionnées entre elles.",
            muted=True, wrap=True,
        )
        outer.addWidget(hint)
        close_button = QPushButton("Fermer le détail")
        close_button.clicked.connect(self.close)
        outer.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)


class VikingStatsPage(QScrollArea):
    def __init__(self, directory, parent=None, store=None):
        super().__init__(parent)
        self.directory = directory
        self.store = store
        self.active_profile = None
        self.active_previous = None
        self.people = []
        self._favorite_target = ""
        self.profile = None
        self.previous = None
        self._favorites = set()
        self._columns = 0
        self.visible_stat_keys = []
        self._detail_dialog = None
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(12, 13, 16, 20)
        self.layout.setSpacing(14)
        self.setWidget(self.content)

        intro, tools = panel(
            "STATISTIQUES DU VIKING",
            "Tous les chiffres viennent des compteurs du personnage. "
            "Comme dans Minecraft, épingle tes statistiques préférées pour les retrouver rapidement."
        )
        title = label("TON AVENTURE EN CHIFFRES", section=True)
        title.setStyleSheet("color:#f3c88c;font:bold 15pt 'Segoe UI';")
        tools.addWidget(title)
        self.summary = label(
            "Charge ton personnage pour consulter ses statistiques.", muted=True, wrap=True)
        tools.addWidget(self.summary)
        # Vue cumulative et vue individuelle : accès direct, sans ouvrir un menu.
        view_row = QHBoxLayout()
        view_row.addWidget(label("AFFICHAGE :", muted=True))
        self.total_mode_button = QPushButton("CUMUL • Tous les Vikings")
        self.total_mode_button.setObjectName("statsTotalMode")
        self.total_mode_button.setCheckable(True)
        self.total_mode_button.setStyleSheet(
            "QPushButton {background:#172f3a;border:1px solid #4b6670;"
            "border-radius:10px;padding:11px 15px;color:#e2ddd2;font-weight:700;}"
            "QPushButton:checked {background:#54432e;border:2px solid #e7b677;"
            "color:#fff0d5;} QPushButton:disabled {color:#778b91;}"
        )
        self.total_mode_button.clicked.connect(self.show_total)
        view_row.addWidget(self.total_mode_button)
        self.individual_mode_button = QPushButton("INDIVIDUEL • Un Viking")
        self.individual_mode_button.setObjectName("statsIndividualMode")
        self.individual_mode_button.setCheckable(True)
        self.individual_mode_button.setStyleSheet(
            "QPushButton {background:#172f3a;border:1px solid #4b6670;"
            "border-radius:10px;padding:11px 15px;color:#e2ddd2;font-weight:700;}"
            "QPushButton:checked {background:#54432e;border:2px solid #e7b677;"
            "color:#fff0d5;} QPushButton:disabled {color:#778b91;}"
        )
        self.individual_mode_button.clicked.connect(self.show_individual)
        view_row.addWidget(self.individual_mode_button)
        view_row.addStretch(1)
        tools.addLayout(view_row)
        self.source_hint = label(
            "Choisis le cumul ou un Viking ; importe des .fch pour enrichir la liste.",
            muted=True, wrap=True)
        tools.addWidget(self.source_hint)
        # Le sélecteur est indépendant du personnage suivi automatiquement.
        # Une archive n'est jamais sélectionnée comme sauvegarde active du jeu.
        source_row = QHBoxLayout()
        source_row.addWidget(label("PERSONNAGES", muted=True))
        self.character_selector = QComboBox()
        self.character_selector.setObjectName("characterStatsSelector")
        self.character_selector.setMinimumWidth(225)
        self.character_selector.currentIndexChanged.connect(self.select_character)
        source_row.addWidget(self.character_selector, 1)
        self.import_button = QPushButton("Importer des .fch")
        self.import_button.setObjectName("importFchArchives")
        self.import_button.setToolTip("Importer plusieurs anciens personnages sans modifier leurs fichiers")
        self.import_button.clicked.connect(self.import_archives)
        self.import_button.setEnabled(store is not None)
        source_row.addWidget(self.import_button)
        self.remove_button = QPushButton("Retirer l'archive")
        self.remove_button.clicked.connect(self.remove_archive)
        self.remove_button.setEnabled(False)
        source_row.addWidget(self.remove_button)
        tools.addLayout(source_row)
        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher : arbres, distance, portails, boss…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.relayout)
        filter_row.addWidget(self.search, 4)
        self.category = QComboBox()
        self.category.addItems(("Toutes les catégories", "Favoris", *CATEGORIES))
        self.category.currentIndexChanged.connect(self.relayout)
        filter_row.addWidget(self.category, 2)
        self.difficulty = QComboBox()
        for title, key in (
            ("Toutes difficultés", "Any"), ("Normal ou +", "Default"),
            ("Difficile ou +", "Hard"), ("Très difficile ou +", "VeryHard"),
            ("Extrême", "Hardcore"),
        ):
            self.difficulty.addItem(title, key)
        self.difficulty.currentIndexChanged.connect(self.update_values)
        filter_row.addWidget(self.difficulty, 2)
        tools.addLayout(filter_row)
        tools.addWidget(label(
            "Les activités enregistrées avant l'apparition de certains compteurs "
            "peuvent manquer. Les groupes de difficulté se recouvrent : ne les additionne pas. "
            "Distance de nage non disponible.",
            muted=True, wrap=True))
        self.layout.addWidget(intro)

        self.favorite_panel, favorites_layout = panel(
            "★ MES STATISTIQUES ÉPINGLÉES",
            "Retrouve tes indicateurs favoris en premier, quel que soit leur catégorie."
        )
        self.favorite_grid = QGridLayout()
        self.favorite_grid.setSpacing(12)
        favorites_layout.addLayout(self.favorite_grid)
        self.layout.addWidget(self.favorite_panel)
        self.favorite_cards = {}
        self.cards = {
            stat.key: StatCard(stat, self.toggle_favorite, self.open_stat_details)
            for stat in STATS
        }
        self.sections = {}
        for category in CATEGORIES:
            frame, group_layout = panel(category.upper(), "")
            grid = QGridLayout()
            grid.setSpacing(12)
            group_layout.addLayout(grid)
            self.sections[category] = frame, grid
            self.layout.addWidget(frame)
        self.layout.addStretch(1)
        self.refresh(None)

    def open_stat_details(self, stat_key):
        """Affiche le panneau de contribution d'une carte du mode Cumul."""
        if self.character_selector.currentData() != "__total__" or not self.people:
            return None
        stat = next((item for item in STATS if item.key == stat_key), None)
        if stat is None:
            return None
        if self._detail_dialog is not None:
            self._detail_dialog.close()
        dialog = CumulativeStatDialog(
            stat, self.people,
            self.difficulty.currentData(), self.difficulty.currentText(), self
        )
        self._detail_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def import_archives(self):
        if self.store is None:
            return
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Importer d'anciens personnages Valheim", "",
            "Personnages Valheim (*.fch)")
        if not filenames:
            return
        report = self.store.archive.import_files(filenames)
        self.refresh(self.active_profile, self.active_previous)
        if self.people:
            self.show_total()
        message = (f"{report['added']} personnage(s) ajouté(s)\n"
                   f"{report['updated']} archive(s) actualisée(s)\n"
                   f"{report['unchanged']} fichier(s) déjà connu(s)")
        if report["errors"]:
            message += "\n\nFichiers non importés :\n" + "\n".join(report["errors"])
        QMessageBox.information(self, "Import des personnages", message)

    def remove_archive(self):
        if self.store is None:
            return
        identity = self.character_selector.currentData()
        entry = next((p for p in self.people
                      if p["id"] == identity and p["source"] == "archive"), None)
        if entry is None:
            return
        answer = QMessageBox.question(
            self, "Retirer une archive",
            f"Retirer {entry['name']} des statistiques du tracker ?\n"
            "Le fichier .fch d'origine ne sera ni supprimé ni modifié.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.archive.remove(identity)
            self.refresh(self.active_profile, self.active_previous)

    def show_total(self):
        index = self.character_selector.findData("__total__")
        if index >= 0:
            self.character_selector.setCurrentIndex(index)
            self.select_character()

    def show_individual(self):
        if not self.people:
            return
        active_id = character_key(self.active_profile) if self.active_profile else None
        available = [p["id"] for p in self.people]
        identity = active_id if active_id in available else available[0]
        index = self.character_selector.findData(identity)
        if index >= 0:
            self.character_selector.setCurrentIndex(index)
            self.select_character()

    def select_character(self, *_):
        identity = self.character_selector.currentData()
        entry = next((p for p in self.people if p["id"] == identity), None)
        if identity == "__total__":
            self.profile = combine_profiles(p["profile"] for p in self.people)
            self.previous = None
            self._favorite_target = "__all_characters__"
            description = f"Cumul de {len(self.people)} personnage(s)"
        elif entry:
            self.profile = entry["profile"]
            self.previous = self.active_previous if entry["source"] == "active" else None
            # Les favoris historiques du personnage actif gardent sa clé de nom.
            self._favorite_target = (
                entry["name"] if entry["source"] == "active" else entry["id"])
            description = (f"{entry['name']} · personnage actif" if entry["source"] == "active"
                           else f"{entry['name']} · archive : {entry['filename']}")
        else:
            self.profile = None
            self.previous = None
            self._favorite_target = ""
            description = "Aucun personnage importé"
        is_total = identity == "__total__" and bool(self.people)
        self.total_mode_button.setEnabled(bool(self.people))
        self.individual_mode_button.setEnabled(bool(self.people))
        self.total_mode_button.setChecked(is_total)
        self.individual_mode_button.setChecked(bool(entry))
        if is_total:
            self.source_hint.setText(
                f"Vue cumulative de {len(self.people)} Viking(s). "
                "Activités additionnées, records conservés au maximum, "
                "exploration réunie ; chaque personnage n'est compté qu'une fois."
            )
        elif entry:
            self.source_hint.setText(
                f"Vue individuelle : {entry['name']} "
                f"({'sauvegarde active' if entry['source'] == 'active' else 'archive importée'}). "
                "Le menu PERSONNAGES permet de choisir un autre Viking."
            )
        else:
            self.source_hint.setText(
                "Aucun Viking : charge un personnage actif ou importe des sauvegardes .fch."
            )
        self.remove_button.setEnabled(bool(entry and entry["source"] == "archive"))
        self._favorites = favorites(self._favorite_target, self.directory)
        for key, card in self.cards.items():
            card.set_favorite(key in self._favorites)
            card.set_values(self.profile, self.previous, self.difficulty.currentData(), is_total)
        for key, card in self.favorite_cards.items():
            card.set_favorite(key in self._favorites)
            card.set_values(self.profile, self.previous, self.difficulty.currentData(), self.character_selector.currentData() == "__total__")
        self.summary.setText(
            f"{description}  •  {len(STATS)} statistiques  •  "
            f"{len(self._favorites)} favoris épinglés"
        )
        self.relayout()

    def refresh(self, profile, previous=None):
        self.active_profile = profile
        self.active_previous = previous
        previous_selection = self.character_selector.currentData()
        if self.store is not None:
            self.people = self.store.archive.entries(profile)
        elif profile:
            self.people = [{"id": character_key(profile), "name": profile["name"],
                            "source": "active", "profile": profile, "filename": ""}]
        else:
            self.people = []
        self.character_selector.blockSignals(True)
        self.character_selector.clear()
        if self.people:
            self.character_selector.addItem(
                f"Σ CUMUL DE TOUS LES VIKINGS ({len(self.people)})", "__total__")
        for item in self.people:
            suffix = "Viking actif" if item["source"] == "active" else "Viking archivé"
            self.character_selector.addItem(f"{item['name']}  ·  {suffix}", item["id"])
        choices = [self.character_selector.itemData(i)
                   for i in range(self.character_selector.count())]
        active_id = character_key(profile) if profile else None
        requested = (previous_selection if previous_selection in choices
                     else active_id if active_id in choices
                     else "__total__" if "__total__" in choices else None)
        self.character_selector.setCurrentIndex(
            choices.index(requested) if requested in choices else -1)
        self.character_selector.blockSignals(False)
        self.select_character()

    def update_values(self, *_):
        if not self.cards:
            return
        if self._detail_dialog is not None:
            self._detail_dialog.close()
            self._detail_dialog = None
        group = self.difficulty.currentData()
        is_total = self.character_selector.currentData() == "__total__"
        for card in (*self.cards.values(), *self.favorite_cards.values()):
            card.set_values(self.profile, self.previous, group, is_total)

    def toggle_favorite(self, key):
        if key not in self.cards:
            return
        if key in self._favorites:
            self._favorites.remove(key)
        else:
            self._favorites.add(key)
        name = self._favorite_target
        if name:
            save_favorites(name, self._favorites, self.directory)
        for identity, card in self.cards.items():
            card.set_favorite(identity in self._favorites)
        for identity, card in self.favorite_cards.items():
            card.set_favorite(identity in self._favorites)
        # Conserver le descriptif de la source sélectionnée.
        self.summary.setText(
            f"{self.character_selector.currentText()} • {len(STATS)} statistiques • "
            f"{len(self._favorites)} favoris épinglés"
        )
        self.relayout()

    def relayout(self, *_):
        if not hasattr(self, "sections"):
            return
        category_filter = self.category.currentText()
        needle = self.search.text().casefold().strip()
        columns = 3 if self.viewport().width() >= 1050 else (2 if self.viewport().width() >= 710 else 1)
        self._columns = columns
        # Rangée de favoris dédiée, en haut du tableau, sans déplacer les cartes
        # originales des sections de catégorie.
        while self.favorite_grid.count():
            item=self.favorite_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
        favorites_visible = (
            [stat for stat in STATS if stat.key in self._favorites]
            if category_filter == "Toutes les catégories" and not needle else []
        )
        self.favorite_panel.setVisible(bool(favorites_visible))
        for index, stat in enumerate(favorites_visible):
            card=self.favorite_cards.get(stat.key)
            if card is None:
                card=StatCard(stat, self.toggle_favorite, self.open_stat_details)
                self.favorite_cards[stat.key]=card
            card.set_favorite(True)
            card.set_values(self.profile, self.previous, self.difficulty.currentData())
            self.favorite_grid.addWidget(card,index//columns,index%columns)
            card.show()
        visible = []
        for category in CATEGORIES:
            frame, grid = self.sections[category]
            while grid.count():
                item = grid.takeAt(0)
                if item.widget() is not None:
                    item.widget().hide()
            entries = [
                stat for stat in STATS
                if stat.category == category
                and (category_filter in ("Toutes les catégories", "Favoris") or category_filter == category)
                and (category_filter != "Favoris" or stat.key in self._favorites)
                and (not needle or needle in stat.title.casefold()
                     or needle in stat.note.casefold()
                     or needle in stat.counter.casefold())
            ]
            frame.setVisible(bool(entries))
            for index, stat in enumerate(entries):
                card = self.cards[stat.key]
                grid.addWidget(card, index // columns, index % columns)
                card.show()
                visible.append(stat.key)
        self.visible_stat_keys = visible

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_columns = 3 if self.viewport().width() >= 1050 else (2 if self.viewport().width() >= 710 else 1)
        if self._columns != new_columns:
            self.relayout()
