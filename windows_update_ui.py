"""Bouton de mise à jour automatique de l'exécutable Windows Qt."""
from __future__ import annotations

import threading
import os
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from v2_core import VERSION, app_dir
from windows_update import check_release, stage_release, manual_update_instructions

class Events(QObject):
    checked=Signal(object)
    downloaded=Signal(object)
    progress=Signal(int)
    failure=Signal(str)

class UpdatePanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.info=None
        self.busy=False
        self.events=Events(self)
        self.events.checked.connect(self._checked)
        self.events.downloaded.connect(self._downloaded)
        self.events.progress.connect(self._progress)
        self.events.failure.connect(self._failed)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        self.status=QLabel("Version Windows "+VERSION+" • Vérification automatique disponible")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row=QHBoxLayout()
        self.check_button=QPushButton("Vérifier les mises à jour")
        self.check_button.clicked.connect(self.check)
        self.install_button=QPushButton("Télécharger la mise à jour")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install)
        row.addWidget(self.check_button);row.addWidget(self.install_button)
        row.addStretch()
        layout.addLayout(row)
        self.bar=QProgressBar()
        self.bar.setRange(0,100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        QTimer.singleShot(1500,self.check)

    def _start(self,task):
        if self.busy:return
        self.busy=True
        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)
        def run():
            try:task()
            except Exception as exc:self.events.failure.emit(str(exc))
        threading.Thread(target=run,daemon=True).start()

    def check(self):
        self.status.setText("Vérification de la version officielle sur GitHub…")
        self._start(lambda:self.events.checked.emit(check_release(VERSION)))

    def _checked(self,info):
        self.busy=False
        self.check_button.setEnabled(True)
        self.info=info
        if info['available']:
            self.status.setText(f"Nouvelle version Windows : {info['version']} (actuelle : {VERSION}).")
            self.install_button.setEnabled(True)
        else:
            self.status.setText(f"Version Windows {VERSION} à jour.")

    def install(self):
        if not self.info or not self.info['available']:return
        answer=QMessageBox.question(self,"Mettre à jour Valheim Stats Tracker",
            "Télécharger la version Windows "+self.info['version']+" ?\\n"
            "Le fichier sera contrôlé par SHA-256. "
            "Pour réduire les alertes de sécurité, aucun installateur automatique "
            "ni script caché ne sera lancé. Le remplacement se fera manuellement.")
        if answer!=QMessageBox.StandardButton.Yes:return
        self.status.setText("Téléchargement et contrôle SHA-256…")
        self.bar.setRange(0,100);self.bar.setValue(0)
        def work():
            def progress(done,total):
                self.events.progress.emit(int(100*done/total) if total else 0)
            result=stage_release(self.info,app_dir()/'updates',progress)
            self.events.downloaded.emit(str(result))
        self._start(work)

    def _progress(self,value):
        if 0<value<=100:self.bar.setValue(value)

    def _downloaded(self,directory):
        self.busy=False
        self.bar.setValue(100)
        self.status.setText("Version vérifiée et téléchargée. Installation manuelle.")
        try:
            info=manual_update_instructions(directory)
        except Exception as exc:
            self._failed(str(exc))
            return
        text=(
            "La mise à jour a été téléchargée et contrôlée (SHA-256).\\n\\n"
            "Pour éviter tout script d'installation caché :\\n"
            "1. Ferme complètement Valheim Stats Tracker.\\n"
            "2. Copie le contenu du dossier NOUVEAU vers le dossier ACTUEL "
            "en remplaçant les anciens fichiers.\\n"
            "3. Relance ValheimStatsTracker.exe.\\n\\n"
            "Tes historiques et favoris restent dans le dossier de données "
            "Windows, séparé de l'application.\\n\\n"
            "Ouvrir les deux dossiers dans l'Explorateur Windows maintenant ?"
        )
        answer=QMessageBox.question(
            self,"Mise à jour vérifiée — installation manuelle",text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer==QMessageBox.StandardButton.Yes:
            try:
                os.startfile(info['source'])
                os.startfile(info['target'])
            except OSError as exc:
                self._failed("Impossible d'ouvrir les dossiers : "+str(exc))

    def _failed(self,message):
        self.busy=False
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(bool(self.info and self.info.get('available')))
        self.status.setText("Mise à jour indisponible : "+message)
