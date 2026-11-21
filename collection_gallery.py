"""Galerie paginée de l'Encyclopédie Valheim.

N'affiche que des ressources vérifiées : sprites extraits du jeu, images Wiki
mises en cache, véritables trophées associés. Aucune illustration synthétique.
Les éléments sans portrait restent visibles.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from real_assets import collection_icon

PAGE_SIZE = 18
SOURCE_LABELS = {
    "game": "SPRITE DU JEU",
    "wiki": "IMAGE DU WIKI",
    "trophy": "TROPHÉE ASSOCIÉ",
    "missing": "SANS ILLUSTRATION",
}


class GalleryCard(QFrame):
    """Carte d'objet : titre et image assez grands pour l'écran Full HD."""

    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.token = ""
        self.setObjectName("collectionGalleryCard")
        self.setMinimumSize(175, 198)
        self.setMaximumHeight(220)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 11, 12, 11)
        outer.setSpacing(6)
        self.picture = QLabel()
        self.picture.setObjectName("collectionGalleryImage")
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setFixedHeight(91)
        outer.addWidget(self.picture)
        self.title = QLabel()
        self.title.setObjectName("collectionGalleryTitle")
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setMinimumHeight(36)
        self.title.setStyleSheet(
            "color:#f5e9d4;font:600 10pt 'Segoe UI';background:transparent;"
        )
        outer.addWidget(self.title)
        self.origin = QLabel()
        self.origin.setObjectName("collectionGalleryOrigin")
        self.origin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.origin.setStyleSheet("color:#a9c0ba;font:8pt 'Segoe UI';background:transparent;")
        outer.addWidget(self.origin)
        self.inspect = QPushButton("Voir la fiche")
        self.inspect.setObjectName("collectionGalleryOpen")
        self.inspect.setFixedHeight(29)
        self.inspect.clicked.connect(self._open)
        outer.addWidget(self.inspect)
        self._set_highlight(False)

    def _set_highlight(self, selected):
        color = "#d5b078" if selected else "#425c62"
        background = "#27413f" if selected else "#192e38"
        self.setStyleSheet(
            "QFrame#collectionGalleryCard {background:" + background +
            ";border:1px solid " + color + ";border-radius:12px;}"
            "QFrame#collectionGalleryCard:hover {border:1px solid #d5b078;}"
        )

    def set_entry(self, entry, source, chosen=False):
        self.token = str(entry["token"])
        self.title.setText(str(entry["name"]))
        self.origin.setText(SOURCE_LABELS.get(source, "SANS ILLUSTRATION"))
        image = collection_icon(self.token)
        self.picture.clear()
        if image.isNull():
            self.picture.setText("Illustration\nindisponible")
            self.picture.setWordWrap(True)
            self.picture.setStyleSheet(
                "color:#afc0bc;font:9pt 'Segoe UI';background:transparent;"
            )
        else:
            self.picture.setPixmap(image.pixmap(QSize(88, 88)))
        self.setToolTip(
            f"{entry['name']}\n{entry['category']}\n"
            f"{SOURCE_LABELS.get(source, source)}\n"
            f"{entry['status']}\nIdentifiant : {entry['token']}"
        )
        self._set_highlight(chosen)

    def _open(self):
        if self.token:
            self.selected.emit(self.token)


class CollectionGallery(QWidget):
    """Affiche *toutes* les correspondances, sans troncature à 350 lignes."""

    selected = Signal(str)

    def __init__(self, state_lookup, parent=None):
        super().__init__(parent)
        self.lookup = state_lookup
        self.entries = []
        self.page_number = 0
        self.selected_token = None
        self.columns = 3
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(9)
        navigation = QHBoxLayout()
        self.page_status = QLabel("Aucune entrée")
        self.page_status.setObjectName("collectionGalleryCount")
        self.page_status.setWordWrap(True)
        navigation.addWidget(self.page_status, 1)
        self.previous = QPushButton("‹ Précédent")
        self.previous.setObjectName("collectionGalleryPrevious")
        self.next = QPushButton("Suivant ›")
        self.next.setObjectName("collectionGalleryNext")
        self.previous.clicked.connect(lambda: self.move_page(-1))
        self.next.clicked.connect(lambda: self.move_page(1))
        navigation.addWidget(self.previous)
        navigation.addWidget(self.next)
        outer.addLayout(navigation)
        self.empty = QLabel("Aucune entrée pour ces filtres.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.empty)
        self.scroller = QScrollArea()
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QFrame.Shape.NoFrame)
        self.scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        canvas = QWidget()
        self.grid = QGridLayout(canvas)
        self.grid.setContentsMargins(2, 3, 5, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroller.setWidget(canvas)
        outer.addWidget(self.scroller, 1)

        self.cards = []
        for _ in range(PAGE_SIZE):
            card = GalleryCard(canvas)
            card.selected.connect(self._select)
            self.cards.append(card)
            self.grid.addWidget(card, 0, 0)
            card.hide()
        self.render()

    def set_entries(self, entries, selected=None):
        self.entries = list(entries)
        tokens = {item["token"] for item in self.entries}
        self.selected_token = selected if selected in tokens else (
            self.entries[0]["token"] if self.entries else None
        )
        index = next(
            (i for i, item in enumerate(self.entries)
             if item["token"] == self.selected_token), 0
        )
        self.page_number = index // PAGE_SIZE
        self.render()

    def _select(self, token):
        self.selected_token = token
        self.render()
        self.selected.emit(token)

    def move_page(self, offset):
        last = max(0, (len(self.entries) - 1) // PAGE_SIZE)
        self.page_number = max(0, min(last, self.page_number + offset))
        self.render()
        self.scroller.verticalScrollBar().setValue(0)

    def render(self):
        last = max(0, (len(self.entries) - 1) // PAGE_SIZE)
        self.page_number = max(0, min(last, self.page_number))
        start = self.page_number * PAGE_SIZE
        page = self.entries[start:start + PAGE_SIZE]
        self.page_status.setText(
            (f"{start + 1}–{start + len(page)} sur {len(self.entries)}"
             f"  •  page {self.page_number + 1}/{last + 1}")
            if page else "Aucune entrée dans cette sélection"
        )
        self.previous.setEnabled(self.page_number > 0)
        self.next.setEnabled(self.page_number < last)
        self.empty.setVisible(not page)
        for index, card in enumerate(self.cards):
            self.grid.removeWidget(card)
            if index >= len(page):
                card.hide()
                continue
            entry = page[index]
            card.set_entry(
                entry, self.lookup(entry["token"]),
                entry["token"] == self.selected_token,
            )
            self.grid.addWidget(card, index // self.columns, index % self.columns)
            card.show()

    def update_token(self, token):
        start = self.page_number * PAGE_SIZE
        for index, entry in enumerate(self.entries[start:start + PAGE_SIZE]):
            if entry["token"] == token:
                self.cards[index].set_entry(
                    entry, self.lookup(token), token == self.selected_token
                )
                return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(self.width(), 100)
        new_columns = 4 if width >= 1040 else 3 if width >= 740 else 2 if width >= 485 else 1
        if self.columns != new_columns:
            self.columns = new_columns
            self.render()
