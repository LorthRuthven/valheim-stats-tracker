"""Encyclopédie Qt V2.3.0 : icônes extraites du jeu et preuves de sauvegarde.

Ne modifie aucune sauvegarde. Un objet absent des compteurs n'est jamais
présenté comme manquant dans le jeu ou non découvert.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from collection_catalog import CATEGORIES, catalogue
from desktop_v2 import label, panel
from real_assets import game_icon

MAX_VISIBLE = 350


class CollectionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
                picture = game_icon(entry["token"])
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
        else:
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
        visual = game_icon(entry["token"])
        if visual.isNull():
            self.preview.clear()
            self.preview.setText("Icône authentique non associée")
        else:
            self.preview.setText("")
            self.preview.setPixmap(visual.pixmap(QSize(142, 142)))
