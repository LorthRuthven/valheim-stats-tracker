"""Panneau de mise à jour Windows avec installation et redémarrage intégrés."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from v2_core import VERSION, app_dir
from windows_install import install_release, launch_executable
from windows_update import check_release, open_download_folder, stage_release


class Events(QObject):
    checked = Signal(object)
    downloaded = Signal(str)
    installed = Signal(str)
    phase = Signal(str)
    progress = Signal(int)
    failure = Signal(str)


class UpdatePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.info = None
        self.archive = None
        self.busy = False
        self.events = Events(self)
        self.events.checked.connect(self._checked)
        self.events.downloaded.connect(self._downloaded)
        self.events.installed.connect(self._installed)
        self.events.phase.connect(self._phase)
        self.events.progress.connect(self._progress)
        self.events.failure.connect(self._failed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.status = QLabel("Version Windows " + VERSION + " • Mise à jour intégrée")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        self.check_button = QPushButton("Vérifier les mises à jour")
        self.check_button.clicked.connect(self.check)
        self.install_button = QPushButton("Télécharger et installer")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install)
        self.manual_button = QPushButton("Ouvrir le dossier du ZIP")
        self.manual_button.setEnabled(False)
        self.manual_button.clicked.connect(self.open_archive_folder)
        row.addWidget(self.check_button)
        row.addWidget(self.install_button)
        row.addWidget(self.manual_button)
        row.addStretch()
        layout.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        QTimer.singleShot(1500, self.check)

    def _start(self, task):
        if self.busy:
            return
        self.busy = True
        self.check_button.setEnabled(False)
        self.install_button.setEnabled(False)

        def run():
            try:
                task()
            except Exception as exc:
                self.events.failure.emit(str(exc))

        threading.Thread(target=run, daemon=True).start()

    def check(self):
        if self.busy:
            return
        self.status.setText("Vérification de la version officielle sur GitHub…")
        self._start(lambda: self.events.checked.emit(check_release(VERSION)))

    def _checked(self, info):
        self.busy = False
        self.check_button.setEnabled(True)
        self.info = info
        if info["available"]:
            self.status.setText(
                f"Nouvelle version Windows : {info['version']} (actuelle : {VERSION}). "
                "Installation intégrée disponible."
            )
            self.install_button.setEnabled(True)
        else:
            self.status.setText(f"Version Windows {VERSION} à jour.")

    def install(self):
        if self.busy or not self.info or not self.info["available"]:
            return
        answer = QMessageBox.question(
            self, "Mettre à jour Valheim Stats Tracker",
            "Installer la version Windows " + self.info["version"] + " ?\n\n"
            "Le ZIP GitHub officiel sera contrôlé par SHA-256, puis analysé "
            "avec Microsoft Defender. L'application vérifiera le lancement "
            "de la nouvelle version avant de l'activer.\n\n"
            "Une copie des données sera conservée et l'ancienne version "
            "restera installée. Aucun script PowerShell ni contournement "
            "antivirus ne sera utilisé.\n\n"
            "Le redémarrage sera proposé à la fin."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        info = dict(self.info)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText("Téléchargement et vérification SHA-256…")

        def work():
            def progress(done, total):
                self.events.progress.emit(int(100 * done / total) if total else 0)

            archive = stage_release(info, app_dir() / "updates", progress)
            self.events.downloaded.emit(str(archive))
            self.events.phase.emit(
                "Archive vérifiée. Extraction, analyse Defender et test de démarrage…"
            )
            executable = install_release(info, archive)
            self.events.installed.emit(str(executable))

        self._start(work)

    def _phase(self, message):
        self.bar.setRange(0, 0)
        self.status.setText(message)

    def _progress(self, value):
        if self.bar.maximum() and 0 < value <= 100:
            self.bar.setValue(value)

    def _downloaded(self, archive):
        self.archive = Path(archive)
        self.manual_button.setEnabled(True)

    def _installed(self, executable):
        self.busy = False
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(False)
        self.bar.setRange(0, 100)
        self.bar.setValue(100)
        self.status.setText(
            "Nouvelle version installée et vérifiée. Ancienne installation préservée."
        )
        answer = QMessageBox.question(
            self, "Mise à jour terminée",
            "La version " + self.info["version"] + " est prête.\n\n"
            "Fermer Valheim Stats Tracker et redémarrer avec cette version ?"
        )
        if answer == QMessageBox.StandardButton.Yes:
            app = QApplication.instance()

            def restart():
                try:
                    launch_executable(executable)
                except OSError:
                    # L'ancien raccourci relancera la version installée.
                    pass

            app.aboutToQuit.connect(restart)
            self.window().close()

    def open_archive_folder(self):
        if self.archive and self.archive.is_file():
            try:
                open_download_folder(self.archive)
            except Exception as exc:
                QMessageBox.warning(self, "Dossier inaccessible", str(exc))

    def _failed(self, message):
        self.busy = False
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(bool(self.info and self.info.get("available")))
        self.bar.setRange(0, 100)
        self.status.setText(
            "Mise à jour interrompue : " + message
            + "\nL'ancienne installation et les données sont conservées."
        )
