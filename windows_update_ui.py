"""Bouton de mise à jour automatique de l'exécutable Windows Qt."""
from __future__ import annotations

import threading
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from v2_core import VERSION, app_dir
from windows_update import check_release, stage_release, open_download_folder, launch_verified_installer

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
        self.status=QLabel("Version Windows "+VERSION+" • Mise à jour via installateur Windows visible")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row=QHBoxLayout()
        self.check_button=QPushButton("Vérifier les mises à jour")
        self.check_button.clicked.connect(self.check)
        self.install_button=QPushButton("Télécharger et installer")
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
            if info.get('kind') == 'installer':
                self.status.setText(
                    f"V{info['version']} disponible • installateur Windows classique, "
                    "téléchargement vérifié SHA-256 ; installation avec votre accord."
                )
                self.install_button.setText("Télécharger et installer")
            else:
                self.status.setText(
                    f"V{info['version']} disponible • ZIP portable : "
                    "extraction manuelle (aucun installateur publié)."
                )
                self.install_button.setText("Télécharger le ZIP")
            self.install_button.setEnabled(True)
        else:
            self.status.setText(f"Version Windows {VERSION} à jour.")

    def install(self):
        if not self.info or not self.info['available']:return
        if self.info.get('kind') == 'installer':
            question=(
                "Télécharger l'installateur Windows "+self.info['version']+" ?\n\n"
                "Le programme sera contrôlé par SHA-256 avant toute ouverture. "
                "Une fois prêt, il te sera proposé de lancer son assistant "
                "d'installation visible. Aucun script PowerShell ni modification "
                "des règles antivirus."
            )
        else:
            question=(
                "Télécharger le ZIP Windows "+self.info['version']+" ?\n\n"
                "L'archive sera vérifiée, mais aucune installation n'aura lieu. "
                "Il faudra extraire manuellement le ZIP."
            )
        answer=QMessageBox.question(self,"Mettre à jour Valheim Stats Tracker",question)
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
        self.check_button.setEnabled(True)
        if self.info and self.info.get('kind') == 'installer':
            self.status.setText(
                "Installateur officiel téléchargé et SHA-256 vérifié. "
                "Assistant Windows prêt, sans exécution automatique."
            )
            answer=QMessageBox.question(
                self, "Lancer l'installateur Windows",
                "Le programme d'installation officiel est prêt :\n"
                +str(directory)+"\n\n"
                "Ouvrir l'assistant d'installation maintenant ?\n"
                "Windows peut demander une confirmation de sécurité. "
                "Ne désactive pas Defender si une alerte apparaît."
            )
            if answer!=QMessageBox.StandardButton.Yes:
                self.status.setText("Installateur téléchargé et contrôlé, non exécuté : "+str(directory))
                return
            try:
                launch_verified_installer(self.info,directory)
            except Exception as exc:
                self._failed(str(exc))
                return
            self.status.setText(
                "Assistant d'installation Windows ouvert. Suis ses étapes ; "
                "le tracker sera fermé uniquement si l'installateur le demande."
            )
            return
        self.status.setText(
            "ZIP portable vérifié, non exécuté. "
            "Installation manuelle dans un nouveau dossier."
        )
        try:
            open_download_folder(directory)
        except Exception as exc:
            self.status.setText("ZIP contrôlé : "+str(directory)+" • "+str(exc))
            return
        QMessageBox.information(
            self, "Archive Windows vérifiée",
            "Le ZIP téléchargé se trouve ici :\n"
            +str(directory)+"\n\n"
            "La version portable n'est pas mise à jour automatiquement. "
            "Après contrôle antivirus, ferme le tracker, extrais l'archive "
            "dans un NOUVEAU dossier et lance le nouveau programme.\n\n"
            "Tes sauvegardes et tes réglages ne sont pas modifiés."
        )

    def _failed(self,message):
        self.busy=False
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(bool(self.info and self.info.get('available')))
        self.status.setText("Mise à jour indisponible : "+message)
