"""Capture de toutes les pages de l'interface Qt réelle, sur Windows.

Usage : python -m tools.capture_tracker_pages <sauvegarde.fch> <dossier_sortie>
Ce script est réservé à la documentation ; il ne modifie jamais les fichiers .fch.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

from nordic_ui import NordicWindow
from v2_core import TrackerStore

PAGE_SLUGS = (
    "vue-ensemble",
    "succes",
    "combat",
    "historique",
    "reglages",
    "centre-progression",
    "boss",
    "activites",
    "competences",
    "compteurs-bruts",
    "encyclopedie",
    "statistiques-viking",
)


def screenshot_gallery(fch: Path, dest: Path):
    if not fch.is_file():
        raise FileNotFoundError(f"Fichier test introuvable : {fch}")
    dest.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Valheim Stats Tracker — Captures de validation")
    print("Plateforme Qt:", QApplication.platformName(), flush=True)
    for filename in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf", "arial.ttf"):
        font_file = Path("C:/Windows/Fonts") / filename
        if font_file.is_file():
            font_id = QFontDatabase.addApplicationFont(str(font_file))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            print(f"Police enregistrée : {filename} -> {font_id} {families}", flush=True)
    app.setFont(QFont("Segoe UI", 10))
    print("Familles Qt disponibles :", len(QFontDatabase.families()), flush=True)

    shots = []
    with tempfile.TemporaryDirectory(prefix="valheim_tracker_screens_") as temp:
        store = TrackerStore(temp)
        window = NordicWindow(store=store)
        window.set_motion(False)
        window.resize(1650, 960)
        window.show()
        app.processEvents()
        # Le runner Windows limite parfois la fenêtre à son écran virtuel au moment de show().
        window.resize(1650, 960)
        app.processEvents()
        print(f"Dimensions rendues : {window.width()} x {window.height()}", flush=True)
        store.choose(str(fch))
        window.refresh_save(force=True)
        app.processEvents()
        if not store.profile:
            raise RuntimeError("Aucun personnage chargé : impossible de valider le rendu.")
        if window.stack.count() != 12:
            raise RuntimeError(f"Nombre de pages inattendu : {window.stack.count()}")

        for index, slug in enumerate(PAGE_SLUGS):
            window.show_page(index)
            app.processEvents()
            window.repaint()
            app.processEvents()
            image = window.grab()
            if image.isNull() or image.width() < 1000 or image.height() < 690:
                raise RuntimeError(f"Capture incorrecte de la page {index}: {image.size()}")
            output = dest / f"{index + 1:02d}_{slug}.png"
            if not image.save(str(output), "PNG"):
                raise RuntimeError(f"Impossible de sauver la capture : {output}")
            shots.append((window.NAV[index][0], output))
            print(f"CAPTURE {index + 1:02d}/12 {window.NAV[index][0]} : {output}", flush=True)

        # Rendu supplémentaire dans la liste défilante des statistiques.
        window.show_page(11)
        app.processEvents()
        scroller = window.viking_stats_page.verticalScrollBar()
        if scroller.maximum() > 0:
            for suffix, value in (("milieu", scroller.maximum() // 2),
                                  ("bas", scroller.maximum())):
                scroller.setValue(value)
                app.processEvents()
                path = dest / f"13_statistiques-viking_{suffix}.png"
                if not window.grab().save(str(path), "PNG"):
                    raise RuntimeError("Capture de défilement ratée")
                print(f"CAPTURE BONUS : {path}", flush=True)

        # Deux captures supplémentaires du même vrai Viking, sans données fabriquées :
        # seuls les modes d'affichage diffèrent.
        window.show_page(11)
        stats = window.viking_stats_page
        for slug, switch in (
            ("14_statistiques-mode-cumul", stats.show_total),
            ("15_statistiques-mode-individuel", stats.show_individual),
        ):
            switch()
            stats.verticalScrollBar().setValue(0)
            app.processEvents()
            picture = window.grab()
            if picture.isNull():
                raise RuntimeError("La comparaison des modes ne peut pas être capturée")
            output = dest / (slug + ".png")
            if not picture.save(str(output), "PNG"):
                raise RuntimeError("Échec de la sauvegarde du mode")
            print(f"CAPTURE MODE : {output}", flush=True)

        # Démonstration VISUELLE du détail avec deux Vikings : le deuxième
        # est simulé en mémoire. Aucun faux fichier .fch n'est créé ou importé.
        # Les captures précédentes restent 100 % issues du personnage public réel.
        import copy
        from valheim_reader import STAT_INDEX
        fictional = copy.deepcopy(store.profile)
        fictional["name"] = "Viking Démo (fictif)"
        fictional["player_id"] = 987654321
        for group_data in fictional.get("groups", {}).values():
            raw = group_data.get("stats")
            if isinstance(raw, list) and len(raw) > STAT_INDEX["DistanceRun"]:
                raw[STAT_INDEX["DistanceRun"]] = 1948292.0
        stats.people.append({
            "id": "id:987654321",
            "name": "Viking Démo (fictif)",
            "source": "archive",
            "filename": "EXEMPLE-SIMULÉ.fch",
            "profile": fictional,
        })
        stats.character_selector.addItem(
            "Viking Démo (fictif)  ·  Viking archivé", "id:987654321")
        stats.character_selector.setItemText(
            0, "Σ CUMUL DE TOUS LES VIKINGS (2)"
        )
        stats.show_total()
        stats.verticalScrollBar().setValue(0)
        app.processEvents()
        cumshot = dest / "16_DEMONSTRATION-cumul-deux-vikings.png"
        if not window.grab().save(str(cumshot), "PNG"):
            raise RuntimeError("Capture du cumul démonstratif impossible")
        print("CAPTURE DEMO CUMUL :", cumshot, flush=True)

        dialog = stats.open_stat_details("run")
        if dialog is None:
            raise RuntimeError("Impossible d'ouvrir le détail de la course")
        app.processEvents()
        if len(dialog.rows) != 2:
            raise RuntimeError("La fiche de démonstration doit contenir deux Vikings")
        popupshot = dest / "17_DEMONSTRATION-detail-course-par-viking.png"
        if not dialog.grab().save(str(popupshot), "PNG"):
            raise RuntimeError("Impossible de capturer le détail du cumul")
        print("CAPTURE DEMO DETAIL :", popupshot, flush=True)
        dialog.close()

        window.close()
        store.close()
        app.processEvents()

    # Vignette comparative de toutes les pages ; les PNG restent intacts.
    cols = 3
    cell_w = 640
    thumb_h = 375
    title_h = 47
    margin = 24
    step_y = thumb_h + title_h + margin
    rows = (len(shots) + cols - 1) // cols
    background = Image.new("RGB", (cols * cell_w + (cols + 1) * margin,
                                   rows * step_y + margin + 8), "#0c161c")
    draw = ImageDraw.Draw(background)
    font_path = Path("C:/Windows/Fonts/segoeuib.ttf")
    if not font_path.is_file():
        font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 22) if font_path.is_file() else ImageFont.load_default()
    for index, (title, shot) in enumerate(shots):
        col, row = index % cols, index // cols
        x = margin + col * (cell_w + margin)
        y = margin + row * step_y
        screenshot = Image.open(shot).convert("RGB")
        screenshot.thumbnail((cell_w, thumb_h))
        background.paste(screenshot, (x, y))
        draw.text((x + 4, y + thumb_h + 8),
                  f"{index + 1:02d} · {title}", fill="#f4dfbe", font=font)
    collage = dest / "00_apercu_12_pages.jpg"
    background.save(collage, quality=90, optimize=True)
    (dest / "LIRE-MOI.txt").write_text(
        "Captures authentiques du rendu Qt de Valheim Stats Tracker V2.5.0 sur Windows.\n"
        "Résolution : 1650 x 960.\n"
        "Données : personnage public de test Nichael (.fch v46), jamais modifié.\n"
        "Les 12 PNG montrent le début de chaque page ; quatre vues supplémentaires détaillent les statistiques et les modes cumul/individuel.\n"        "Les fichiers 16 et 17 sont des DEMONSTRATIONS : Viking Démo et ses chiffres sont fictifs,\n"
        "créés seulement en mémoire pour illustrer les deux lignes du détail du cumul.\n"

        "Une capture sur runner GitHub peut différer légèrement de la machine personnelle.\n",
        encoding="utf-8")
    print(f"MONTAGE : {collage}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage : python -m tools.capture_tracker_pages sauvegarde.fch sortie/")
    screenshot_gallery(Path(sys.argv[1]), Path(sys.argv[2]))
