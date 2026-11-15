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
)
import threading
import time

from collection_catalog import CATEGORIES, catalogue
from desktop_v2 import label, panel
from real_assets import game_icon, collection_icon, reset_icon_cache
from wiki_images import WikiImageCache, wiki_title

MAX_VISIBLE = 350


class CollectionPage(QWidget):
    wiki_item_done = Signal(str)
    wiki_batch_done = Signal(int, int)

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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(7, 7, 8, 10)
        outer.setSpacing(13)

        overview, summary_layout = panel(
            "ENCYCLOPÉDIE DU DIXIÈME MONDE",
            "Véritables icônes de ton installation Valheim. Les compteurs de sauvegarde "
            "indiquent une activité, jamais un statut de découverte garanti."
        )
        self.summary = label("Chargement du catalogue…", muted=True, wrap=True)
        self.summary.setObjectName("collectionSummary")
        summary_layout.addWidget(self.summary)
        wiki_controls=QHBoxLayout()
        self.wiki_button=QPushButton("Compléter 20 images via Valheim Wiki")
        self.wiki_button.setObjectName("wikiImportButton")
        self.wiki_button.setToolTip("Télécharge uniquement les images manquantes des éléments affichés, au maximum 20 par action.")
        self.wiki_button.clicked.connect(self._fetch_missing)
        wiki_controls.addWidget(self.wiki_button)
        self.wiki_clear=QPushButton("Vider les images wiki")
        self.wiki_clear.clicked.connect(self._clear_wiki_cache)
        wiki_controls.addWidget(self.wiki_clear)
        wiki_controls.addStretch(1)
        summary_layout.addLayout(wiki_controls)
        self.wiki_status=label("Le téléchargement wiki est facultatif ; images enregistrées dans un cache privé.",muted=True,wrap=True)
        self.wiki_status.setObjectName("wikiStatus")
        summary_layout.addWidget(self.wiki_status)
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
        outer.addLayout(filters)

        split = QSplitter(Qt.Orientation.Horizontal)
        list_frame, list_layout = panel(
            "CATALOGUE ILLUSTRÉ",
            "Les illustrations proviennent de tes fichiers de jeu, pas de dessins génériques."
        )
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
        list_layout.addWidget(self.table)
        split.addWidget(list_frame)

        details, detail_layout = panel(
            "FICHE DE COLLECTION",
            "Les objets sans image authentique ne reçoivent pas d'icône inventée."
        )
        self.preview = QLabel("Choisis un objet")
        self.preview.setObjectName("collectionPreview")
        self.preview.setMinimumHeight(170)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail_layout.addWidget(self.preview)
        self.detail_title = label("Sélectionne une entrée", section=True, wrap=True)
        self.detail_title.setObjectName("collectionDetailTitle")
        detail_layout.addWidget(self.detail_title)
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
        detail_layout.addStretch(1)
        split.addWidget(details)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes((780, 360))
        outer.addWidget(split, 1)
        self.refresh(None)

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

    def _selected_token(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.visible_entries):
            return self.visible_entries[row]["token"]
        return None

    def render(self, *_):
        selected = self._selected_token()
        needle = self.search.text().casefold().strip()
        category = self.category.currentText()
        status = self.activity.currentText()
        filtered = [
            e for e in self.entries
            if (not needle or needle in e["name"].casefold()
                or needle in e["token"].casefold())
            and (category == CATEGORIES[0] or e["category"] == category)
            and (status == "Toutes les activités" or e["status"] == status)
        ]
        shown = filtered[:MAX_VISIBLE]
        self.visible_entries = shown
        observed = sum(1 for e in self.entries if e["observed"])
        self.summary.setText(
            f"{len(self.entries)} entrées référencées  •  {observed} avec activité enregistrée  •  "
            f"{len(filtered)} correspondent aux filtres"
            + (f"  •  {MAX_VISIBLE} premières affichées (affine ta recherche)" if len(filtered) > MAX_VISIBLE else "")
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
        index = self.table.currentRow()
        if index < 0 or index >= len(self.visible_entries):
            self.detail_title.setText("Aucun résultat")
            self.detail_category.clear()
            self.detail_status.clear()
            self.detail_evidence.clear()
            self.preview.clear()
            self.preview.setText("Aucune icône à afficher")
            return
        entry = self.visible_entries[index]
        self.detail_title.setText(entry["name"])
        self.detail_category.setText(f"{entry['category']}  •  {entry['token']}")
        self.detail_status.setText(entry["status"])
        self.detail_evidence.setText(
            "\n".join(entry["evidence"]) if entry["evidence"] else
            "Aucune preuve individuelle disponible dans les compteurs de cette sauvegarde. "
            "Cela ne signifie pas que l'objet est absent ou jamais découvert."
        )
        visual = collection_icon(entry["token"])
        source=self.wiki_cache.source(entry["token"])
        if visual.isNull():
            self.preview.clear()
            self.preview.setText("Image manquante\nRecherche possible sur Valheim Wiki")
        else:
            self.preview.setText("")
            self.preview.setPixmap(visual.pixmap(QSize(155, 155)))
        if source and game_icon(entry["token"]).isNull():
            self.image_source.setText(
                "Image : Valheim Wiki (cache local)\n"
                "Source : " + source.get("wiki_title","") +
                "\nDroits et attribution : consulter la page source."
            )
            self.image_link.setEnabled(True)
        else:
            self.image_source.setText(
                "Icône provenant des fichiers du jeu." if not visual.isNull()
                else "Aucune image confirmée pour ce prefab."
            )
            self.image_link.setEnabled(False)
        if self._wiki_active and visual.isNull() and not self._wiki_busy:
            self.wiki_timer.start(380)


    def activate(self):
        """Démarre la recherche uniquement lors de la visite de cette page."""
        self._wiki_active=True
        self.show_selected()

    def _fetch_selected(self):
        if self._wiki_busy or not self._wiki_active:
            return
        token=self._selected_token()
        if not token or wiki_title(token) is None or not game_icon(token).isNull():
            return
        if self.wiki_cache.cached_image(token) is not None:
            self.show_selected()
            return
        self._start_wiki_download([token])

    def _fetch_missing(self):
        if self._wiki_busy:
            return
        targets=[
            entry["token"] for entry in self.visible_entries
            if (wiki_title(entry["token"]) is not None
                and game_icon(entry["token"]).isNull()
                and self.wiki_cache.cached_image(entry["token"]) is None)
        ][:20]
        if not targets:
            self.wiki_status.setText("Aucune image wiki manquante exploitable parmi les entrées affichées.")
            return
        self._start_wiki_download(targets)

    def _start_wiki_download(self,tokens):
        if self._wiki_busy or not tokens:
            return
        self._wiki_busy=True
        self.wiki_timer.stop()
        self.wiki_button.setEnabled(False)
        self.wiki_clear.setEnabled(False)
        self.wiki_status.setText(
            f"Valheim Wiki : recherche de {len(tokens)} image(s) manquante(s)…"
        )
        def worker():
            found=0
            for pos,token in enumerate(tokens):
                try:
                    if self.wiki_cache.fetch(token) is not None:
                        found+=1
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
                self.wiki_batch_done.emit(found,len(tokens))
            except RuntimeError:
                pass
        threading.Thread(target=worker,daemon=True,name="ValheimWikiCache").start()

    def _wiki_received(self,token):
        # Une image ajoutée doit apparaître dans la ligne et la fiche sans recharger tout.
        reset_icon_cache()
        visual=collection_icon(token)
        if not visual.isNull():
            for index,entry in enumerate(self.visible_entries):
                if entry["token"]==token:
                    item=self.table.item(index,0)
                    if item is not None:
                        item.setIcon(visual)
        if token==self._selected_token():
            self.show_selected()

    def _wiki_finished(self,found,total):
        self._wiki_busy=False
        self.wiki_button.setEnabled(True)
        self.wiki_clear.setEnabled(True)
        missing_reason = self.wiki_cache.last_error(self._selected_token() or "")
        self.wiki_status.setText(
            f"Valheim Wiki : {found} nouvelle(s) image(s) sur {total} tentative(s). "
            "Les pages sans correspondance exacte restent sans illustration. "
            f"Cache : {self.wiki_cache.count()} image(s)."
            + ("\nDernier diagnostic : " + missing_reason if missing_reason and found == 0 else "")
        )

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
        self.wiki_status.setText(f"Cache wiki vidé ({removed} fichier(s)). Icônes du jeu conservées.")
        self.render()

    def _open_image_source(self):
        token=self._selected_token()
        source=self.wiki_cache.source(token) if token else None
        if source:
            link=source.get("page_url","")
            if link.startswith(("https://valheim.wiki/","https://valheim.weirdgloop.org/")):
                QDesktopServices.openUrl(QUrl(link))
