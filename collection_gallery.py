"""Encyclopédie : grille Valheim continue et virtualisée, sans pagination."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QListView, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)
from real_assets import collection_icon, game_icon

SIZES = {"compact": (156, 155, 66), "normal": (205, 192, 94),
         "large": (260, 247, 126)}
SOURCE_LABELS = {"game": "SPRITE DU JEU", "wiki": "IMAGE DU WIKI",
                 "trophy": "TROPHÉE ASSOCIÉ", "missing": "IMAGE MANQUANTE"}
# Un vrai sprite de matériau peut illustrer une famille de constructions.
# Cette association reste toujours indiquée comme thématique et n'est jamais
# comptée comme une illustration exacte de la construction.
MATERIAL_HINTS = (
    ("blackmarble", "BlackMarble"), ("ashwood", "Ashwood"),
    ("grausten", "Grausten"), ("flametal", "Flametal"),
    ("crystal", "Crystal"), ("stone", "Stone"),
    ("wood", "Wood"), ("iron", "Iron"),
)


def thematic_material(token):
    key = str(token).removeprefix("$").lower()
    if not key.startswith("piece_"):
        return None
    for prefix, material in MATERIAL_HINTS:
        if key[6:].startswith(prefix):
            icon = game_icon(material)
            if not icon.isNull():
                return icon
    return None


class EntryModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return entry["name"]
        if role == Qt.ItemDataRole.UserRole:
            return entry["token"]
        if role == Qt.ItemDataRole.ToolTipRole:
            return (f"{entry['name']}\n{entry['category']}\n"
                    f"{entry['status']}\nIdentifiant : {entry['token']}")
        return None

    def set_entries(self, entries):
        same = (len(self.entries) == len(entries) and
                all(a["token"] == b["token"]
                    for a, b in zip(self.entries, entries)))
        if same:
            self.entries = list(entries)
            if self.entries:
                self.dataChanged.emit(
                    self.index(0, 0), self.index(len(self.entries)-1, 0))
        else:
            self.beginResetModel()
            self.entries = list(entries)
            self.endResetModel()
        return same


class CardDelegate(QStyledItemDelegate):
    def __init__(self, lookup, parent=None):
        super().__init__(parent)
        self.lookup = lookup
        self.mode = "normal"
        self._cache = {}

    def sizeHint(self, option, index):
        width, height, _ = SIZES[self.mode]
        return QSize(width, height)

    def invalidate(self, token=None):
        if token is None:
            self._cache.clear()
        else:
            for key in tuple(self._cache):
                if key[0] == token:
                    del self._cache[key]

    def _image(self, token, source, size):
        key = (token, source, size)
        if key not in self._cache:
            image = collection_icon(token)
            thematic = False
            if image.isNull():
                image = thematic_material(token)
                thematic = image is not None
            pix = None if image is None or image.isNull() else image.pixmap(QSize(size, size))
            if len(self._cache) >= 160:
                self._cache.clear()
            self._cache[key] = pix, thematic
        return self._cache[key]

    def paint(self, painter, option, index):
        if not index.isValid() or index.row() >= len(index.model().entries):
            return
        entry = index.model().entries[index.row()]
        source = self.lookup(entry["token"])
        _, _, image_size = SIZES[self.mode]
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(3, 3, -3, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#e6bd7e" if selected else "#45636b"), 1.2))
        painter.setBrush(QColor("#29403d" if selected else "#1a303a"))
        painter.drawRoundedRect(rect, 11, 11)
        pix, thematic = self._image(entry["token"], source, image_size)
        img_rect = QRect(rect.x()+8, rect.y()+8, rect.width()-16, image_size+5)
        if pix is not None and not pix.isNull():
            painter.drawPixmap(
                img_rect.x()+(img_rect.width()-pix.width())//2,
                img_rect.y()+(img_rect.height()-pix.height())//2, pix)
        else:
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor("#8ba5a6"))
            painter.drawText(img_rect, int(Qt.AlignmentFlag.AlignCenter),
                             "IMAGE\nINDISPONIBLE")
        font = QFont("Segoe UI", 10 if self.mode != "large" else 11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#f3e6d5"))
        painter.drawText(
            QRect(rect.x()+7, img_rect.bottom()+4, rect.width()-14,
                  31 if self.mode == "compact" else 38),
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
            entry["name"])
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#b0c5c4"))
        caption = "MATÉRIAU ASSOCIÉ" if thematic else SOURCE_LABELS[source]
        painter.drawText(
            QRect(rect.x()+5, rect.bottom()-24, rect.width()-10, 19),
            int(Qt.AlignmentFlag.AlignCenter), caption)
        if entry.get("observed"):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#a5d5b5"))
            painter.drawEllipse(rect.right()-15, rect.y()+10, 6, 6)
        painter.restore()


class CollectionGallery(QWidget):
    """La liste contient toutes les entrées mais Qt ne peint que les visibles."""
    selected = Signal(str)

    def __init__(self, state_lookup, parent=None):
        super().__init__(parent)
        self.lookup = state_lookup
        self.entries = []
        self.selected_token = None
        self.size_mode = "normal"
        self.model = EntryModel(self)
        self.delegate = CardDelegate(state_lookup, self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.list = QListView(self)
        self.list.setObjectName("collectionContinuousList")
        self.list.setModel(self.model)
        self.list.setItemDelegate(self.delegate)
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setFlow(QListView.Flow.LeftToRight)
        self.list.setWrapping(True)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setLayoutMode(QListView.LayoutMode.Batched)
        self.list.setBatchSize(160)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setSpacing(7)
        self.list.setStyleSheet(
            "QListView#collectionContinuousList{background:transparent;"
            "border:none;outline:none;} QListView::item{border:none;}")
        self.list.clicked.connect(self._clicked)
        root.addWidget(self.list, 1)
        self.set_card_size("normal")

    def _clicked(self, index):
        if index.isValid() and index.row() < len(self.entries):
            self.selected_token = self.entries[index.row()]["token"]
            self.selected.emit(self.selected_token)

    def set_card_size(self, mode):
        if mode not in SIZES:
            return
        self.size_mode = mode
        self.delegate.mode = mode
        self.delegate.invalidate()
        width, height, _ = SIZES[mode]
        self.list.setGridSize(QSize(width+8, height+8))
        self.list.doItemsLayout()
        self.list.viewport().update()

    def set_entries(self, entries, selected=None):
        self.entries = list(entries)
        unchanged = self.model.set_entries(self.entries)
        names = {entry["token"] for entry in self.entries}
        self.selected_token = (
            selected if selected in names else
            self.selected_token if self.selected_token in names else
            self.entries[0]["token"] if self.entries else None)
        if not unchanged:
            self.list.scrollToTop()
        self.list.viewport().update()

    def select_token(self, token, *, emit=False):
        if not any(entry["token"] == token for entry in self.entries):
            return False
        self.selected_token = token
        if emit:
            self.selected.emit(token)
        return True

    def update_token(self, token):
        self.delegate.invalidate(token)
        for i, entry in enumerate(self.entries):
            if entry["token"] == token:
                index = self.model.index(i, 0)
                self.model.dataChanged.emit(index, index)
                break
        self.list.viewport().update()

    def invalidate_images(self):
        self.delegate.invalidate()
        self.list.viewport().update()
