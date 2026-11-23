"""V3.0 : galerie d'activités continue, virtualisée et accessible."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate
from real_assets import collection_icon, game_icon


def readable_count(value):
    return f"{value:,.0f}".replace(",", " ") if float(value).is_integer() else f"{value:,.1f}".replace(",", " ").replace(".", ",")


class ActivityModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        family, name, count, token = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return name
        if role == Qt.ItemDataRole.UserRole:
            return token
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{name}\n{family}\n{readable_count(count)} actions enregistrées\nIdentifiant : {token}"
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()


class ActivityDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icons = {}

    def sizeHint(self, option, index):
        return QSize(228, 159)

    def _icon(self, token):
        if token not in self.icons:
            image = game_icon(token)
            if image.isNull():
                image = collection_icon(token)
            if len(self.icons) >= 192:
                self.icons.clear()
            self.icons[token] = image.pixmap(QSize(62, 62)) if not image.isNull() else None
        return self.icons[token]

    def paint(self, painter, option, index):
        if not index.isValid() or index.row() >= len(index.model().rows):
            return
        family, name, count, token = index.model().rows[index.row()]
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#e7b979" if selected else "#49666c"), 1.2))
        painter.setBrush(QColor("#29443f" if selected else "#1c303a"))
        painter.drawRoundedRect(rect, 12, 12)
        pix = self._icon(token)
        if pix is not None:
            painter.drawPixmap(rect.x()+12, rect.y()+13, pix)
        else:
            painter.setPen(QColor("#b6cac8"))
            painter.drawText(QRect(rect.x()+10, rect.y()+12, 70, 63),
                             int(Qt.AlignmentFlag.AlignCenter), "—")
        painter.setPen(QColor("#b8c9c7"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRect(rect.x()+84, rect.y()+12, rect.width()-92, 23),
                         int(Qt.AlignmentFlag.AlignVCenter), family.upper())
        painter.setPen(QColor("#f4e8d7"))
        font=QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRect(rect.x()+84, rect.y()+35, rect.width()-94, 52),
                         int(Qt.TextFlag.TextWordWrap), name)
        painter.setPen(QColor("#f0c489"))
        number=QFont("Segoe UI", 18)
        number.setBold(True)
        painter.setFont(number)
        painter.drawText(QRect(rect.x()+12, rect.bottom()-52, rect.width()-24, 32),
                         int(Qt.AlignmentFlag.AlignLeft), readable_count(count))
        painter.setPen(QColor("#b6c9c6"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRect(rect.x()+12, rect.bottom()-20, rect.width()-24, 17),
                         int(Qt.AlignmentFlag.AlignLeft), "ACTIONS ENREGISTRÉES")
        painter.restore()


class ActivityGallery(QListView):
    """QListView : toutes les entrées existent, seules les visibles sont peintes."""
    activated_token = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("activityContinuousGallery")
        self.model_data = ActivityModel(self)
        self.setModel(self.model_data)
        self.setItemDelegate(ActivityDelegate(self))
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(128)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(8)
        self.setGridSize(QSize(240, 171))
        self.setMinimumHeight(430)
        self.setStyleSheet("QListView#activityContinuousGallery{background:transparent;border:0;outline:0;}")
        self.clicked.connect(self._open)
        self.activated.connect(self._open)

    def set_rows(self, rows):
        old = self.currentIndex().data(Qt.ItemDataRole.UserRole)
        self.model_data.set_rows(rows)
        wanted = next((i for i,row in enumerate(rows) if row[3] == old), -1)
        if wanted >= 0:
            self.setCurrentIndex(self.model_data.index(wanted))
        else:
            self.clearSelection()
            self.scrollToTop()

    def _open(self, index):
        if index.isValid():
            token = index.data(Qt.ItemDataRole.UserRole)
            if token:
                self.activated_token.emit(token)
