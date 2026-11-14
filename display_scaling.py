"""Densité et lisibilité réglables de toute l'interface Qt (V2.2.3).

Les dimensions sont exprimées en points Qt et non en pixels écran fixes.
L'option 'Grand' est le défaut pour les anciennes installations.
"""
from __future__ import annotations

import re
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTreeWidget,
)

SCALES = {
    'Compact': {'ratio':1.00, 'row':38, 'control':34, 'nav':36, 'sidebar':244, 'icon':25},
    'Normal': {'ratio':1.12, 'row':44, 'control':39, 'nav':42, 'sidebar':263, 'icon':29},
    'Grand': {'ratio':1.24, 'row':51, 'control':45, 'nav':47, 'sidebar':282, 'icon':34},
    'Très grand': {'ratio':1.36, 'row':59, 'control':51, 'nav':52, 'sidebar':302, 'icon':39},
}
DEFAULT_SCALE = 'Grand'


def display_style(base_qss, mode):
    ratio = SCALES[mode]['ratio']
    # Remettre systématiquement le style à l'échelle depuis l'original
    # évite une croissance cumulative lors des changements de profil.
    def scale(match):
        pt = float(match.group(1)) * ratio
        return f'{pt:.1f}pt'
    style = re.sub(r'(?<![\w.])(\d+(?:\.\d+)?)pt\b', scale, base_qss)
    # Les tableaux doivent conserver des hauteurs de ligne choisies plus bas.
    return style


def update_readability(window, mode, base_qss):
    if mode not in SCALES:
        raise ValueError('Mode de lisibilité inconnu : ' + str(mode))
    dimensions=SCALES[mode]
    window.setStyleSheet(display_style(base_qss,mode))
    side=window.findChild(QFrame,'sidebar')
    if side is not None:
        side.setFixedWidth(dimensions['sidebar'])
    for button in window.findChildren(QPushButton):
        is_nav=button.objectName()=='nav'
        button.setMinimumHeight(dimensions['nav'] if is_nav else dimensions['control'])
        if is_nav:
            button.setIconSize(QSize(dimensions['icon'],dimensions['icon']))
    for widget_type in (QComboBox, QLineEdit):
        for box in window.findChildren(widget_type):
            box.setMinimumHeight(dimensions['control'])
    for check in window.findChildren(QCheckBox):
        check.setMinimumHeight(round(dimensions['control']*.8))
    for widget in window.findChildren(QTableWidget):
        widget.verticalHeader().setDefaultSectionSize(dimensions['row'])
        widget.horizontalHeader().setMinimumHeight(round(dimensions['row']*.9))
        widget.setIconSize(QSize(dimensions['icon'],dimensions['icon']))
    for widget in window.findChildren(QTreeWidget):
        widget.setIconSize(QSize(dimensions['icon'],dimensions['icon']))
        widget.header().setMinimumHeight(round(dimensions['row']*.9))
        # La hauteur des entrées d'arbre est gérée par le délégué Qt ou les icônes.
    for label in window.findChildren(QLabel):
        original=label.property('_unscaled_qss')
        if original is None:
            original=label.styleSheet()
            label.setProperty('_unscaled_qss',original)
        if original:
            label.setStyleSheet(display_style(original,mode))
    return dimensions
