"""Encyclopédie Qt V2.3.0 : icônes extraites du jeu et preuves de sauvegarde.

Ne modifie aucune sauvegarde. Un objet absent des compteurs n'est jamais
présenté comme manquant dans le jeu ou non découvert.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QScrollArea, QFrame, QStackedWidget, QProgressBar, QApplication,
)
import threading
import time

from collection_catalog import CATEGORIES, catalogue
from collection_gallery import CollectionGallery, thematic_material
from desktop_v2 import label, panel
from real_assets import game_icon, piece_icon, character_icon, world_icon, collection_icon, creature_trophy_icon, reset_icon_cache
from wiki_images import WikiImageCache, wiki_title

MAX_VISIBLE = 350


class CollectionPage(QWidget):
    wiki_item_done = Signal(str)
    wiki_batch_done = Signal(int, int)
    game_import_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wiki_active = False
        self._wiki_busy = False
        self.wiki_cache = WikiImageCache()
        self.wiki_item_done.connect(self._wiki_received)
        self.wiki_batch_done.connect(self._wiki_finished)
        self.wiki_timer = QTimer(self)
        self.wiki_timer.setSingleShot(True)
        self.wiki_timer.timeout.connect(self._fetch_selected)
        self.entries = []
        self.visible_entries = []
        self.filtered_entries = []
        self._image_state_cache = {}
        self._wiki_targets = []
        self._wiki_cancel_requested = False
        self._wiki_checked = 0
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 6, 7)
        outer.setSpacing(7)

        # Le bandeau est compact : images et navigation ont la priorité.
        overview = QFrame()
        overview.setObjectName("collectionCompactHeader")
        overview.setStyleSheet("QFrame#collectionCompactHeader{background:#1b3039;"
                               "border:1px solid #3e5c63;border-radius:10px;}")
        summary_layout = QVBoxLayout(overview)
        summary_layout.setContentsMargins(12, 7, 12, 7)
        summary_layout.setSpacing(4)
        headline = QHBoxLayout()
        headline.addWidget(label("ENCYCLOPÉDIE DU DIXIÈME MONDE", section=True))
        headline.addStretch(1)
        self.coverage_bar = QProgressBar()
        self.coverage_bar.setObjectName("collectionCoverageBar")
        self.coverage_bar.setRange(0, 1000)
        self.coverage_bar.setValue(0)
        self.coverage_bar.setFixedWidth(190)
        self.coverage_bar.setMinimumHeight(20)
        self.coverage_bar.setFormat("Illustrations : %p %")
        headline.addWidget(self.coverage_bar)
        self.wiki_button = QPushButton("Chercher les images manquantes (Wiki)")
        self.wiki_button.setObjectName("wikiImportButton")
        self.wiki_button.setToolTip(
            "Recherche les visuels exacts encore absents sur le Wiki, en tâche de fond. "
            "Les objets déjà illustrés ne sont jamais retéléchargés.")
        self.wiki_button.clicked.connect(self._fetch_missing)
        headline.addWidget(self.wiki_button)
        self.game_import_button = QPushButton("Importer depuis Valheim")
        self.game_import_button.setObjectName("collectionImportRealImages")
        self.game_import_button.setToolTip("Extraire les sprites de ton jeu, sans mod.")
        self.game_import_button.clicked.connect(self.game_import_requested.emit)
        headline.addWidget(self.game_import_button)
        self.image_options_button = QPushButton("Options images")
        self.image_options_button.setCheckable(True)
        headline.addWidget(self.image_options_button)
        summary_layout.addLayout(headline)
        self.summary = label("Chargement du catalogue…", muted=True, wrap=True)
        self.summary.setObjectName("collectionSummary")
        self.summary.setStyleSheet("font:9pt 'Segoe UI';color:#b7c9c8;")
        summary_layout.addWidget(self.summary)
        self.image_options = QWidget()
        options = QHBoxLayout(self.image_options)
        options.setContentsMargins(0, 1, 0, 0)
        self.wiki_clear = QPushButton("Vider seulement le cache Wiki")
        self.wiki_clear.clicked.connect(self._clear_wiki_cache)
        options.addWidget(self.wiki_clear)
        self.wiki_cancel_button = QPushButton("Arrêter la recherche Wiki")
        self.wiki_cancel_button.setObjectName("wikiCancelSearch")
        self.wiki_cancel_button.clicked.connect(self._cancel_wiki_download)
        self.wiki_cancel_button.hide()
        options.addWidget(self.wiki_cancel_button)
        self.copy_missing_button = QPushButton("Copier les images manquantes")
        self.copy_missing_button.setObjectName("collectionCopyMissing")
        self.copy_missing_button.setToolTip("Copie tous les identifiants encore sans vraie illustration pour les compléter précisément.")
        self.copy_missing_button.clicked.connect(self._copy_missing_report)
        options.addWidget(self.copy_missing_button)
        self.wiki_status = label(
            "Téléchargements facultatifs ; images enregistrées en cache local.",
            muted=True, wrap=True)
        self.wiki_status.setObjectName("wikiStatus")
        options.addWidget(self.wiki_status, 1)
        self.image_options.setVisible(False)
        self.image_options_button.toggled.connect(self.image_options.setVisible)
        summary_layout.addWidget(self.image_options)
        outer.addWidget(overview)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un nom ou un identifiant Valheim…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.render)
        filters.addWidget(self.search, 4)
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.currentIndexChanged.connect(self.render)
        filters.addWidget(self.category, 2)
        self.activity = QComboBox()
        self.activity.addItems(("Toutes les activités", "Activité enregistrée", "Statut inconnu"))
        self.activity.currentIndexChanged.connect(self.render)
        filters.addWidget(self.activity, 2)
        self.image_filter = QComboBox()
        self.image_filter.setObjectName("collectionImageFilter")
        self.image_filter.addItem("Toutes les images", "all")
        self.image_filter.addItem("Avec illustration", "available")
        self.image_filter.addItem("Sans illustration", "missing")
        self.image_filter.addItem("Sprites exacts du jeu", "game")
        self.image_filter.addItem("Images de constructions", "piece")
        self.image_filter.addItem("Images de créatures", "character")
        self.image_filter.addItem("Images du monde", "world")
        self.image_filter.addItem("Images du Wiki", "wiki")
        self.image_filter.addItem("Trophées associés", "trophy")
        self.image_filter.currentIndexChanged.connect(self.render)
        filters.addWidget(self.image_filter, 2)
        outer.addLayout(filters)

        split = QSplitter(Qt.Orientation.Horizontal)
        list_frame = QFrame()
        list_frame.setObjectName("collectionWideGalleryFrame")
        list_frame.setStyleSheet("QFrame#collectionWideGalleryFrame{background:#1b3039;"
                                 "border:1px solid #42626a;border-radius:10px;}")
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(7, 7, 7, 7)
        list_layout.setSpacing(5)
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("collectionTable")
        self.table.setHorizontalHeaderLabels(("Objet ou créature", "Catégorie", "Statut"))
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setIconSize(QSize(50, 50))
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(64)
        header = self.table.horizontalHeader()
        from PySide6.QtWidgets import QHeaderView
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.show_selected)
        modes = QHBoxLayout()
        self.gallery_button = QPushButton("Galerie illustrée")
        self.gallery_button.setObjectName("collectionGalleryMode")
        self.gallery_button.setCheckable(True)
        self.list_button = QPushButton("Liste détaillée")
        self.list_button.setObjectName("collectionListMode")
        self.list_button.setCheckable(True)
        self.gallery_button.clicked.connect(lambda: self._set_view("gallery"))
        self.list_button.clicked.connect(lambda: self._set_view("list"))
        modes.addWidget(self.gallery_button)
        modes.addWidget(self.list_button)
        modes.addStretch(1)
        modes.addWidget(label("TAILLE", muted=True))
        self.card_size = QComboBox()
        self.card_size.setObjectName("collectionCardSize")
        for name, key in (("Compact", "compact"),
                          ("Normal", "normal"), ("Grand", "large")):
            self.card_size.addItem(name, key)
        self.card_size.setCurrentIndex(1)
        self.card_size.currentIndexChanged.connect(
            lambda: self.gallery.set_card_size(self.card_size.currentData()))
        modes.addWidget(self.card_size)
        self.detail_toggle = QPushButton("Afficher la fiche")
        self.detail_toggle.setObjectName("collectionDetailToggle")
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.clicked.connect(
            lambda: self._set_detail_visible(self.detail_toggle.isChecked()))
        modes.addWidget(self.detail_toggle)
        list_layout.addLayout(modes)
        self.gallery = CollectionGallery(self.image_state)
        self.gallery.setObjectName("collectionGallery")
        self.gallery.selected.connect(self._select_gallery_entry)
        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.gallery)
        self.list_stack.addWidget(self.table)
        self.list_stack.setCurrentWidget(self.gallery)
        self.gallery_button.setChecked(True)
        list_layout.addWidget(self.list_stack)
        split.addWidget(list_frame)

        details, detail_layout = panel(
            "FICHE DE COLLECTION",
            "Les objets sans image authentique ne reçoivent pas d'icône inventée."
        )
        self.detail_close_button = QPushButton("✕ Fermer la fiche")
        self.detail_close_button.setObjectName("collectionCloseDetail")
        self.detail_close_button.clicked.connect(lambda: self._set_detail_visible(False))
        detail_layout.addWidget(self.detail_close_button)
        self.detail_title = label("Sélectionne une entrée", section=True, wrap=True)
        self.detail_title.setObjectName("collectionDetailTitle")
        detail_layout.addWidget(self.detail_title)
        detail_layout.addSpacing(6)
        self.preview = QLabel("Choisis un objet")
        self.preview.setObjectName("collectionPreview")
        self.preview.setFixedHeight(184)
        self.preview.setWordWrap(True)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setContentsMargins(16, 12, 16, 12)
        self.preview.setStyleSheet(
            "QLabel#collectionPreview { background:#10212a; "
            "border:1px solid #3f5960; border-radius:12px; "
            "color:#b7c5c4; padding:8px; }"
        )
        detail_layout.addWidget(self.preview)
        detail_layout.addSpacing(12)
        self.detail_category = label("", muted=True, wrap=True)
        detail_layout.addWidget(self.detail_category)
        self.detail_status = label("", wrap=True)
        self.detail_status.setObjectName("collectionDetailStatus")
        detail_layout.addWidget(self.detail_status)
        self.detail_evidence = label("", muted=True, wrap=True)
        detail_layout.addWidget(self.detail_evidence)
        self.image_source=label("",muted=True,wrap=True)
        detail_layout.addWidget(self.image_source)
        self.image_link=QPushButton("Voir l'image sur le wiki")
        self.image_link.setEnabled(False)
        self.image_link.clicked.connect(self._open_image_source)
        detail_layout.addWidget(self.image_link)
        self.wiki_selected_button=QPushButton("Chercher le portrait / l'image sur le Wiki")
        self.wiki_selected_button.setObjectName("collectionFetchSelectedWiki")
        self.wiki_selected_button.setToolTip(
            "Recherche l'image de cette entrée seulement, sans modifier les données du jeu."
        )
        self.wiki_selected_button.clicked.connect(self._fetch_selected)
        detail_layout.addWidget(self.wiki_selected_button)
        detail_layout.addStretch(1)
        # Un panneau scrollable évite que Qt compresse ses QLabel au point
        # de superposer le nom de l'objet et l'illustration sur un écran Full HD.
        details.setMinimumHeight(0)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setObjectName("collectionDetailScroll")
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setWidget(details)
        split.addWidget(self.detail_scroll)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        self.detail_scroll.setMinimumWidth(320)
        self.detail_scroll.hide()
        self.split = split
        self._detail_visible = False
        outer.addWidget(split, 1)
        self.refresh(None)

    def _set_detail_visible(self, visible):
        self._detail_visible = bool(visible)
        self.detail_scroll.setVisible(self._detail_visible)
        self.detail_toggle.blockSignals(True)
        self.detail_toggle.setChecked(self._detail_visible)
        self.detail_toggle.setText(
            "Masquer la fiche" if self._detail_visible else "Afficher la fiche")
        self.detail_toggle.blockSignals(False)
        if self._detail_visible:
            width = max(self.split.width(), 800)
            self.split.setSizes((round(width * 0.73), round(width * 0.27)))
            self.show_selected()

    def refresh(self, profile):
        """Rafraîchit les compteurs sans changer les filtres choisis."""
        selected = self._selected_token()
        self.entries = catalogue(profile)
        self.render()
        if selected:
            for index, entry in enumerate(self.visible_entries):
                if entry["token"] == selected:
                    self.table.selectRow(index)
                    break

    def invalidate_image_cache(self, token=None):
        """Invalide le bilan après un téléchargement ou une extraction locale."""
        if token is None:
            self._image_state_cache.clear()
        else:
            self._image_state_cache.pop(token, None)
        if token is None:
            self.gallery.invalidate_images()
        else:
            self.gallery.update_token(token)

    def image_state(self, token):
        """Distingue un vrai sprite Valheim, une image Wiki et une absence."""
        state = self._image_state_cache.get(token)
        if state is not None:
            return state
        if not game_icon(token).isNull():
            state = "game"
        elif not piece_icon(token).isNull():
            state = "piece"
        elif not character_icon(token).isNull():
            state = "character"
        elif not world_icon(token).isNull():
            state = "world"
        elif self.wiki_cache.cached_image(token) is not None:
            state = "wiki"
        elif not creature_trophy_icon(token).isNull():
            state = "trophy"
        else:
            state = "missing"
        self._image_state_cache[token] = state
        return state

    def _selected_token(self):
        if self.list_stack.currentWidget() is self.gallery:
            return self.gallery.selected_token
        row = self.table.currentRow()
        if 0 <= row < len(self.visible_entries):
            return self.visible_entries[row]["token"]
        return None

    def _set_view(self, mode):
        selected = self._selected_token()
        use_gallery = mode == "gallery"
        self.list_stack.setCurrentWidget(self.gallery if use_gallery else self.table)
        self.gallery_button.setChecked(use_gallery)
        self.list_button.setChecked(not use_gallery)
        if use_gallery:
            self.gallery.set_entries(self.filtered_entries, selected)
        elif selected:
            index = next((i for i, entry in enumerate(self.visible_entries)
                          if entry["token"] == selected), 0)
            if self.visible_entries:
                self.table.selectRow(index)
        self.show_selected()

    def _select_gallery_entry(self, token):
        self.gallery.select_token(token)
        for index, entry in enumerate(self.visible_entries):
            if entry["token"] == token:
                self.table.selectRow(index)
                break
        self._set_detail_visible(True)
        self.show_selected()

    def render(self, *_):
        selected = self._selected_token()
        needle = self.search.text().casefold().strip()
        category = self.category.currentText()
        status = self.activity.currentText()
        picture_filter = self.image_filter.currentData()
        filtered = [
            e for e in self.entries
            if (not needle or needle in e["name"].casefold()
                or needle in e["token"].casefold())
            and (category == CATEGORIES[0] or e["category"] == category)
            and (status == "Toutes les activités" or e["status"] == status)
            and (
                picture_filter == "all"
                or (picture_filter == "available" and self.image_state(e["token"]) != "missing")
                or (picture_filter == "missing" and self.image_state(e["token"]) == "missing")
                or (picture_filter in ("game", "piece", "character", "world", "wiki", "trophy")
                    and self.image_state(e["token"]) == picture_filter)
            )
        ]
        self.filtered_entries = filtered
        shown = filtered[:MAX_VISIBLE]
        self.visible_entries = shown
        self.gallery.set_entries(filtered, selected)
        observed = sum(1 for e in self.entries if e["observed"])
        stats = {"game": 0, "piece": 0, "character": 0, "world": 0, "wiki": 0, "trophy": 0, "missing": 0}
        for entry in self.entries:
            stats[self.image_state(entry["token"])] += 1
        illustrated=len(self.entries)-stats["missing"]
        ratio=1000*illustrated/len(self.entries) if self.entries else 0
        self.coverage_bar.setValue(round(ratio))
        self.coverage_bar.setToolTip(
            f"{illustrated} illustrations du jeu, du Wiki ou trophées associés "
            f"sur {len(self.entries)} entrées."
        )
        self.summary.setText(
            f"{len(self.entries)} entrées • {len(filtered)} résultats • "
            f"{observed} activités enregistrées • "
            f"Illustrations : {stats['game']} sprites d’inventaire • "
            f"{stats['piece']} images de constructions • "
            f"{stats['character']} créatures • {stats['world']} monde • "
            f"{stats['wiki']} images Wiki • "
            f"{stats['trophy']} trophées associés • {stats['missing']} sans image"
        )
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(shown))
            for index, entry in enumerate(shown):
                name = QTableWidgetItem(entry["name"])
                name.setData(Qt.ItemDataRole.UserRole, entry["token"])
                picture = collection_icon(entry["token"])
                if not picture.isNull():
                    name.setIcon(picture)
                self.table.setItem(index, 0, name)
                self.table.setItem(index, 1, QTableWidgetItem(entry["category"]))
                state = QTableWidgetItem(entry["status"])
                if entry["observed"]:
                    state.setForeground(QColor("#a9dbc6"))
                self.table.setItem(index, 2, state)
                self.table.setRowHeight(index, 64)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.blockSignals(False)
        if shown:
            position = next((i for i, entry in enumerate(shown)
                             if entry["token"] == selected), 0)
            self.table.selectRow(position)
        # setRowCount() peut conserver la meme selection : rafraichir tout de meme la fiche.
        self.show_selected()

    def show_selected(self):
        if self.list_stack.currentWidget() is self.gallery:
            token = self.gallery.selected_token
            entry = next((item for item in self.filtered_entries
                          if item["token"] == token), None)
        else:
            index = self.table.currentRow()
            entry = (self.visible_entries[index]
                     if 0 <= index < len(self.visible_entries) else None)
        if entry is None:
            self.detail_title.setText("Aucun résultat")
            self.detail_category.clear()
            self.detail_status.clear()
            self.detail_evidence.clear()
            self.preview.clear()
            self.preview.setText("Aucune icône à afficher")
            self.wiki_selected_button.hide()
            return
        self.detail_title.setText(entry["name"])
        self.detail_category.setText(f"{entry['category']}  •  {entry['token']}")
        self.detail_status.setText(entry["status"])
        self.detail_evidence.setText(
            "\n".join(entry["evidence"]) if entry["evidence"] else
            "Aucune preuve individuelle disponible dans les compteurs de cette sauvegarde. "
            "Cela ne signifie pas que l'objet est absent ou jamais découvert."
        )
        visual = collection_icon(entry["token"])
        thematic = False
        if visual.isNull():
            material = thematic_material(entry["token"])
            if material is not None:
                visual = material
                thematic = True
        source=self.wiki_cache.source(entry["token"])
        if visual.isNull():
            self.preview.clear()
            self.preview.setText("Illustration indisponible\nRecherche possible sur le wiki")
        else:
            self.preview.setText("")
            self.preview.setPixmap(visual.pixmap(QSize(155, 155)))
        if (source and game_icon(entry["token"]).isNull()
                and piece_icon(entry["token"]).isNull()
                and character_icon(entry["token"]).isNull()
                and world_icon(entry["token"]).isNull()):
            self.image_source.setText(
                "Image : Valheim Wiki (cache local)\n"
                "Source : " + source.get("wiki_title","") +
                "\nDroits et attribution : consulter la page source."
            )
            self.image_link.setEnabled(True)
        else:
            if self.image_state(entry["token"]) == "character":
                description = ("Image de la créature Valheim correspondant à ce prefab, "
                               "issue de la documentation Jötunn. "
                               "© Iron Gate AB / Coffee Stain Publishing.")
            elif self.image_state(entry["token"]) == "world":
                description = ("Image authentique de l'objet ou élément du monde Valheim, "
                               "issue de la documentation Jötunn.")
            elif self.image_state(entry["token"]) == "piece":
                description = ("Image de cette construction Valheim, référencée par le "
                               "prefab exact dans la documentation Jötunn. "
                               "© Iron Gate AB / Coffee Stain Publishing.")
            elif thematic:
                description = (
                    "Vrai sprite du matériau Valheim associé à cette famille de constructions. "
                    "Ce n'est pas une image exacte de cette pièce."
                )
            elif self.image_state(entry["token"]) == "trophy":
                description = (
                    "Illustration : véritable trophée Valheim correspondant à cette créature. "
                    "Ce n'est pas un portrait officiel du monstre."
                )
            elif not visual.isNull():
                description = "Sprite authentique Valheim (pack inclus ou installation locale)."
            else:
                description = "Aucune illustration exacte ou liée à cette entrée n'est disponible."
            self.image_source.setText(description)
            self.image_link.setEnabled(False)
        can_wiki = (game_icon(entry["token"]).isNull()
                    and piece_icon(entry["token"]).isNull()
                    and character_icon(entry["token"]).isNull()
                    and world_icon(entry["token"]).isNull()
                    and self.wiki_cache.cached_image(entry["token"]) is None
                    and wiki_title(entry["token"]) is not None)
        retry_available = (can_wiki and self.wiki_cache.can_attempt(entry["token"]))
        self.wiki_selected_button.setVisible(can_wiki)
        self.wiki_selected_button.setEnabled(retry_available and not self._wiki_busy)
        if can_wiki and not retry_available:
            reason = self.wiki_cache.last_error(entry["token"])
            self.wiki_selected_button.setToolTip(
                "Recherche déjà effectuée récemment : " +
                (reason or "nouvel essai possible après six heures.")
            )
        if (self._wiki_active and visual.isNull() and not self._wiki_busy
                and self.wiki_cache.can_attempt(entry["token"])):
            self.wiki_timer.start(380)


    def activate(self):
        """Démarre la recherche uniquement lors de la visite de cette page."""
        self._wiki_active=True
        self.show_selected()

    def _fetch_selected(self):
        if self._wiki_busy or not self._wiki_active:
            return
        token=self._selected_token()
        if not token or wiki_title(token) is None or self.image_state(token) != "missing":
            return
        if self.wiki_cache.cached_image(token) is not None:
            self.show_selected()
            return
        if self.wiki_cache.can_attempt(token):
            self._start_wiki_download([token])

    def _copy_missing_report(self):
        """Diagnostic local de chaque prefab sans illustration (sans .fch)."""
        missing = [entry for entry in self.entries
                   if self.image_state(entry["token"]) == "missing"]
        categories = sorted({entry["category"] for entry in missing})
        lines = [
            "Valheim Stats Tracker — images encore manquantes",
            f"Catalogue : {len(self.entries)} entrées / {len(missing)} sans image",
            "Liste exacte des identifiants (sans données personnelles ni sauvegarde) :",
        ]
        for category in categories:
            entries = [entry for entry in missing if entry["category"] == category]
            lines.append(f"\n[{category}] {len(entries)}")
            lines.extend(f'{entry["token"]} | {entry["name"]}' for entry in entries)
        QApplication.clipboard().setText("\n".join(lines))
        self.copy_missing_button.setText(
            f"Copié : {len(missing)} entrées manquantes")

    def _fetch_missing(self):
        if self._wiki_busy:
            return
        # Les erreurs ne doivent pas bloquer le catalogue : on saute les
        # échecs récents et on explore aussi après les 350 premières lignes.
        from wiki_images import WIKI_NAMES
        targets = [
            entry for entry in self.filtered_entries
            if (self.image_state(entry["token"]) == "missing"
                and wiki_title(entry["token"]) is not None
                and self.wiki_cache.can_attempt(entry["token"]))
        ]
        def priority(entry):
            raw = entry["token"].lstrip("$").split("_", 1)[-1].lower()
            return (raw not in WIKI_NAMES, not entry["observed"],
                    entry["name"].casefold())
        targets.sort(key=priority)
        if not targets:
            self.wiki_status.setText(
                "Aucune nouvelle recherche utile : les images restantes sont "
                "sans page Wiki fiable ou ont été tentées récemment. "
                "Les échecs sont réessayables après six heures."
            )
            return
        # Un clic peut compléter tous les prefabs connus par le Wiki.
        # Le plafond évite une activité réseau non bornée sur un très gros FCH.
        self._start_wiki_download([entry["token"] for entry in targets[:500]])

    def _start_wiki_download(self,tokens):
        if self._wiki_busy or not tokens:
            return
        self._wiki_busy=True
        self._wiki_cancel_requested=False
        self._wiki_checked=0
        self._wiki_targets=list(tokens)
        self.wiki_timer.stop()
        self.wiki_button.setEnabled(False)
        self.wiki_clear.setEnabled(False)
        self.wiki_cancel_button.show()
        self.image_options_button.setChecked(True)
        self.wiki_status.setText(
            f"Valheim Wiki : recherche de {len(tokens)} image(s) manquante(s)…"
        )
        def worker():
            found=0
            checked=0
            for pos,token in enumerate(tokens):
                if self._wiki_cancel_requested:
                    break
                try:
                    if self.wiki_cache.fetch(token) is not None:
                        found+=1
                finally:
                    checked+=1
                except Exception:
                    # La lecture du wiki est facultative et ne bloque jamais la progression.
                    pass
                try:
                    self.wiki_item_done.emit(token)
                except RuntimeError:
                    return
                if pos+1<len(tokens):
                    time.sleep(0.6)
            try:
                self.wiki_batch_done.emit(found,checked)
            except RuntimeError:
                pass
        threading.Thread(target=worker,daemon=True,name="ValheimWikiCache").start()

    def _cancel_wiki_download(self):
        """Interrompt la liste après la requête en cours, sans effacer le cache."""
        if self._wiki_busy:
            self._wiki_cancel_requested=True
            self.wiki_cancel_button.setEnabled(False)
            self.wiki_status.setText("Arrêt demandé après la recherche en cours…")

    def _wiki_received(self,token):
        self._wiki_checked += 1
        self.wiki_status.setText(
            f"Valheim Wiki : {self._wiki_checked}/{len(self._wiki_targets)} "
            "identifiant(s) vérifié(s). Les images trouvées apparaissent immédiatement.")
        # Une image ajoutée doit apparaître dans la ligne et la fiche sans recharger tout.
        self.invalidate_image_cache(token)
        reset_icon_cache()
        visual=collection_icon(token)
        if not visual.isNull():
            for index,entry in enumerate(self.visible_entries):
                if entry["token"]==token:
                    item=self.table.item(index,0)
                    if item is not None:
                        item.setIcon(visual)
        self.gallery.update_token(token)
        if token==self._selected_token():
            self.show_selected()

    def _wiki_finished(self,found,total):
        self._wiki_busy=False
        self.wiki_button.setEnabled(True)
        self.wiki_clear.setEnabled(True)
        self.wiki_cancel_button.hide()
        self.wiki_cancel_button.setEnabled(True)
        self.invalidate_image_cache()
        problems = [
            self.wiki_cache.last_error(token)
            for token in self._wiki_targets
            if self.wiki_cache.last_error(token)
        ]
        example = ("\nExemple d'échec : " + problems[0]
                   if problems and found < total else "")
        self.wiki_status.setText(
            ("Recherche interrompue. " if self._wiki_cancel_requested else "")
            + f"Valheim Wiki : {found} nouvelle(s) image(s) sur {total} tentative(s). "
            f"{len(problems)} échec(s) diagnostiqué(s). "
            f"Cache Wiki : {self.wiki_cache.count()} image(s)."
            + example
        )
        self.render()

    def _clear_wiki_cache(self):
        if self._wiki_busy:
            return
        answer=QMessageBox.question(
            self,"Images wiki","Vider seulement les images téléchargées depuis le wiki ? "
            "Les véritables icônes extraites du jeu seront conservées."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed=self.wiki_cache.clear()
        reset_icon_cache()
        self.invalidate_image_cache()
        self.wiki_status.setText(f"Cache wiki vidé ({removed} fichier(s)). Icônes du jeu conservées.")
        self.render()

    def _open_image_source(self):
        token=self._selected_token()
        source=self.wiki_cache.source(token) if token else None
        if source:
            link=source.get("page_url","")
            if link.startswith(("https://valheim.wiki/","https://valheim.weirdgloop.org/")):
                QDesktopServices.openUrl(QUrl(link))
