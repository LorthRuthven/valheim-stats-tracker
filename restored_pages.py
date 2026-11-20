"""Restitution des fonctions V1.9 dans l'interface Qt Windows.

Aucune écriture de sauvegarde. Pages supplémentaires assemblées en Qt natif.
Le fonctionnement des succès est fourni par valheim_reader ; pas de fausses validations Steam.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QSplitter, QFrame,
)
from desktop_v2 import label, panel, table, txt
from valheim_reader import (
    BOSSES, PLAYER_STAT_NAMES, STAT_INDEX, evaluate_all, metrics,
    localized_name, prefab_label,
)
from v2_core import progress_ranking, pending_actions, session_report
from real_assets import achievement_icon, game_icon, collection_icon
from game_visuals import boss_game_icon, skill_game_icon, THEMATIC_BOSS_ICONS

GROUP_CHOICES = (
    ('Toutes difficultés', 'Any'), ('Normal ou +', 'Default'),
    ('Difficile ou +', 'Hard'), ('Très difficile ou +', 'VeryHard'),
    ('Extrême', 'Hardcore'), ('Brut (tous)', 'RawStats'),
)
ACTIVITY_CHOICES = (
    ('Ressources collectées', 'pickables'),
    ('Objets ramassés', 'picked_up'),
    ('Objets fabriqués', 'crafted'),
    ('Éléments placés', 'pieces_built'),
    ('Nourritures consommées', 'foods_eaten'),
)
ACTIVITY_CATEGORIES = (
    ('Bois et arbres', ('wood','log','tree','branch','finewood','corewood','bark','beech','pine','oak')),
    ('Métaux et minerais', ('metal','iron','copper','tin','silver','bronze','flametal','ore','scrap')),
    ('Pierre et minéraux', ('stone','flint','obsidian','crystal','marble','grausten')),
    ('Cuisine et nourriture', ('meat','fish','berry','mushroom','honey','bread','soup','stew','salad','egg')),
    ('Plantes et graines', ('seed','turnip','carrot','flax','barley','onion','vine','thistle','flower')),
    ('Matériel et armes', ('sword','axe','bow','staff','helmet','armor','shield','spear','knife')),
    ('Constructions', ('wall','floor','roof','door','beam','gate','portal','fire','torch','workbench')),
)

def group_control():
    widget = QComboBox()
    for name, key in GROUP_CHOICES:
        widget.addItem(name, key)
    return widget

def activity_category(key):
    token = key.casefold()
    for title, terms in ACTIVITY_CATEGORIES:
        if any(term in token for term in terms):
            return title
    return 'Autres'

def _display_token(token):
    if token.startswith('$'):
        return localized_name(token, prefab_label(token))
    translated = localized_name(token)
    return translated if translated != token else prefab_label(token)

def _table_item(text, icon=None):
    cell = QTableWidgetItem(str(text))
    if icon is not None and not icon.isNull():
        cell.setIcon(icon)
    return cell

def _fill_table(widget, rows, icons=None):
    widget.setUpdatesEnabled(False)
    try:
        widget.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for j, val in enumerate(cells):
                icon = icons[i] if icons and j == 0 and i < len(icons) else None
                widget.setItem(i, j, _table_item(val, icon))
    finally:
        widget.setUpdatesEnabled(True)

def _sample_values(profile, group, key):
    if key.startswith('skill:'):
        return float(profile.get('skills', {}).get(key.split(':',1)[1], {}).get('level',0))
    if key in ('kills','deaths','bosses','crafted','built','picked_up','world_hours'):
        return float(metrics(profile,group).get(key,0))
    index=STAT_INDEX.get(key)
    return float(profile['groups'][group]['stats'][index]) if index is not None else 0.0

def history_points(rows, key, group, changes=False):
    samples=sorted((float(row[1]), _sample_values(row[3], group, key)) for row in rows)
    if not changes:
        return samples
    previous=None
    points=[]
    for timestamp, value in samples:
        # A rollback/reset ne doit jamais être présenté comme une perte d'actions.
        delta = 0.0 if previous is None else max(0, value-previous)
        points.append((timestamp, delta))
        previous=value
    return points


class RestoredPagesMixin:
    """Ajoute les écrans V1.9 perdus, sans toucher à la sauvegarde du personnage."""

    def _make_dashboard(self):
        """Conserve le tableau de bord V2 et le résumé du monde de la V1.9."""
        super()._make_dashboard()
        area=self.stack.widget(0)
        interior=area.widget() if hasattr(area,'widget') else None
        if interior is None:return
        p,layout=panel("MONDES ET ACTIVITÉS",
            "Compléments du tableau de bord V1.9, cumulés sur le personnage.")
        self.world_summary=label("Charge une sauvegarde pour consulter les mondes.",muted=True,wrap=True)
        layout.addWidget(self.world_summary)
        interior.layout().addWidget(p)

    def _refresh_dashboard_extra(self):
        if not self.store.profile or not hasattr(self,'world_summary'):return
        p=self.store.profile
        stats=metrics(p,'Any')
        worlds=p['groups']['RawStats']['worlds']
        details=', '.join(f"{name} {seconds/3600:.1f} h" for name,seconds
                          in sorted(worlds.items(),key=lambda x:-x[1])[:8])
        self.world_summary.setText(
           f"Fabriqués : {txt(stats['crafted'])}   •   Constructions : {txt(stats['built'])}"
           f"   •   Objets ramassés : {txt(stats['picked_up'])}\n"
           f"Version de la sauvegarde : {p.get('version','?')}\n"
           f"Mondes visités : {details or 'aucun connu'}"
        )

    def _make_restored_pages(self):
        self._make_progress_center()
        self._make_boss_detail()
        self._make_activity_detail()
        self._make_skill_detail()
        self._make_raw_detail()
        self._restore_history_controls()
        self._restore_achievement_controls()
        self._restore_combat_controls()

    def _make_progress_center(self):
        page=self._scroll_page()
        intro, il = panel("CENTRE DE PROGRESSION",
            "Tous les objectifs calculables, les favoris et un plan d'action précis.")
        row=QHBoxLayout()
        self.focus_filter=QComboBox()
        self.focus_filter.addItems(["Plus proches", "Favoris", "Non commencés"])
        self.focus_filter.currentIndexChanged.connect(self._refresh_progress_center)
        row.addWidget(label("Afficher :",muted=True));row.addWidget(self.focus_filter)
        row.addStretch();il.addLayout(row)
        self.focus_table=table(["Favori", "Succès", "Progression", "Restants"])
        self.focus_table.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(38,38))
        self.focus_table.verticalHeader().setDefaultSectionSize(46)
        self.focus_table.itemSelectionChanged.connect(self._focus_selection)
        il.addWidget(self.focus_table,1)
        page.addWidget(intro,5)
        detail,dl=panel("CRITÈRES À TERMINER", "Les prochaines actions viennent directement de la sauvegarde.")
        self.focus_title=label("Choisis un objectif",section=True)
        dl.addWidget(self.focus_title)
        self.focus_note=label("",muted=True,wrap=True);dl.addWidget(self.focus_note)
        actions=QHBoxLayout()
        self.focus_star=QPushButton("☆ Ajouter aux favoris")
        self.focus_star.clicked.connect(self._toggle_focus_favorite)
        self.focus_open=QPushButton("Ouvrir la fiche")
        self.focus_open.clicked.connect(self._open_focus_achievement)
        actions.addWidget(self.focus_star);actions.addWidget(self.focus_open);actions.addStretch()
        dl.addLayout(actions)
        self.focus_actions=table(["Action", "Actuel", "Encore"])
        self.focus_actions.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(35,35))
        self.focus_actions.verticalHeader().setDefaultSectionSize(43)
        dl.addWidget(self.focus_actions,1)
        page.addWidget(detail,4)
        session,sl=panel("RAPPORT DE SESSION", "Gains comparés entre sauvegardes enregistrées.")
        self.focus_session=label("En attente de deux relevés rapprochés.",wrap=True)
        sl.addWidget(self.focus_session)
        page.addWidget(session,2)
        self.focus_key=''

    def _make_boss_detail(self):
        page=self._scroll_page()
        top,tl=panel("BOSS ET DIFFICULTÉS", "Ne jamais additionner les groupes : ils se recouvrent.")
        row=QHBoxLayout()
        self.boss_group_choice=group_control()
        self.boss_group_choice.currentIndexChanged.connect(self._refresh_boss_detail)
        row.addWidget(label("Difficulté :",muted=True));row.addWidget(self.boss_group_choice)
        row.addStretch();tl.addLayout(row)
        self.boss_table=table(["Boss", "Toutes", "Normal ou +", "Difficile ou +", "Très difficile ou +", "Extrême"])
        self.boss_table.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(40,40))
        self.boss_table.verticalHeader().setDefaultSectionSize(48)
        # Frise des huit boss : icônes du jeu lorsqu'elles sont disponibles.
        self.boss_cards = {}
        overview, cards_layout = panel(
            "LES HUIT BOSS",
            "Chaque carte représente un boss enregistré par le personnage, "
            "pour la difficulté sélectionnée."
        )
        grid = QGridLayout()
        grid.setSpacing(10)
        for index, (token, name) in enumerate(BOSSES.items()):
            box = QFrame()
            box.setObjectName("bossVisualCard")
            box.setStyleSheet(
                "QFrame#bossVisualCard {background:#152c35; "
                "border:1px solid #415c61;border-radius:12px;}"
            )
            line = QHBoxLayout(box)
            line.setContentsMargins(12, 10, 12, 10)
            picture = QLabel()
            picture.setFixedSize(50, 50)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon = boss_game_icon(token)
            if not icon.isNull():
                picture.setPixmap(icon.pixmap(48, 48))
                if token in THEMATIC_BOSS_ICONS:
                    picture.setToolTip(
                        "Illustration thématique Valheim, pas le trophée de ce boss."
                    )
            else:
                picture.setText("Image\nabsente")
                picture.setWordWrap(True)
                picture.setStyleSheet("color:#bcc9c9;font:8pt 'Segoe UI';")
                picture.setToolTip("L'illustration de ce boss n'est pas disponible.")
            line.addWidget(picture)
            texts = QVBoxLayout()
            title = label(name, wrap=True)
            title.setStyleSheet("font-weight:700;color:#e9dec7;")
            state = label("En attente des compteurs", muted=True, wrap=True)
            texts.addWidget(title)
            texts.addWidget(state)
            line.addLayout(texts, 1)
            grid.addWidget(box, index // 4, index % 4)
            self.boss_cards[token] = (box, state)
        cards_layout.addLayout(grid)
        self.boss_overview = label("Charge un personnage pour découvrir ses victoires.", muted=True, wrap=True)
        cards_layout.addWidget(self.boss_overview)
        page.addWidget(overview)
        tl.addWidget(self.boss_table)
        page.addWidget(top,1)
        info,il=panel("CONDITIONS DE VALIDATION",
            "Les victoires sur un boss en normal ne comptent pas pour les objectifs en difficile.")
        self.boss_info=label("La sauvegarde du personnage n'est pas encore chargée.",muted=True,wrap=True)
        il.addWidget(self.boss_info);page.addWidget(info)

    def _make_activity_detail(self):
        """Galerie d'objets Valheim en premier, données brutes facultatives."""
        page=self._scroll_page()
        intro, body=panel(
            "TON AVENTURE, OBJET PAR OBJET",
            "Tout ce que ton Viking a réellement collecté, ramassé, fabriqué, "
            "placé ou consommé. Les quantités proviennent de sa sauvegarde."
        )
        self.activity_metrics={}
        summary_row=QHBoxLayout()
        summary_row.setSpacing(12)
        for key, heading in (
            ("types", "OBJETS DIFFÉRENTS"),
            ("total", "ACTIONS ENREGISTRÉES"),
            ("family", "FAMILLE DOMINANTE"),
        ):
            box=QFrame()
            box.setObjectName("activitySummaryTile")
            box.setStyleSheet(
                "QFrame#activitySummaryTile {background:#172f38;"
                "border:1px solid #526b6c;border-radius:12px;}"
            )
            inner=QVBoxLayout(box)
            inner.setContentsMargins(16,12,16,12)
            inner.setSpacing(6)
            headline=label(heading,muted=True,wrap=True)
            number=label("—",wrap=True)
            number.setStyleSheet("color:#f4cb8d;font:bold 19pt 'Segoe UI';")
            inner.addWidget(headline)
            inner.addWidget(number)
            summary_row.addWidget(box,1)
            self.activity_metrics[key]=number
        body.addLayout(summary_row)
        body.addSpacing(5)

        controls=QHBoxLayout()
        self.activity_choice=QComboBox()
        for title,field in ACTIVITY_CHOICES:self.activity_choice.addItem(title,field)
        self.activity_choice.setToolTip("Quelle action souhaites-tu examiner ?")
        self.activity_difficulty=group_control()
        self.activity_difficulty.setToolTip("Les niveaux de difficulté se recouvrent.")
        controls.addWidget(label("Activité :",muted=True))
        controls.addWidget(self.activity_choice,3)
        controls.addWidget(label("Difficulté :",muted=True))
        controls.addWidget(self.activity_difficulty,2)
        body.addLayout(controls)

        filters=QHBoxLayout()
        self.activity_search=QLineEdit()
        self.activity_search.setPlaceholderText("Chercher une ressource ou un objet Valheim…")
        self.activity_search.setClearButtonEnabled(True)
        self.activity_family=QComboBox()
        self.activity_family.addItem("Toutes les familles","")
        for heading,_ in ACTIVITY_CATEGORIES:
            self.activity_family.addItem(heading,heading)
        self.activity_family.addItem("Autres","Autres")
        self.activity_sort=QComboBox()
        self.activity_sort.addItem("Les plus nombreux","most")
        self.activity_sort.addItem("Ordre alphabétique","az")
        self.activity_sort.addItem("Les moins nombreux","least")
        filters.addWidget(self.activity_search,5)
        filters.addWidget(self.activity_family,3)
        filters.addWidget(self.activity_sort,3)
        body.addLayout(filters)
        self.activity_summary=label("Charge un Viking pour consulter ses activités.",muted=True,wrap=True)
        body.addWidget(self.activity_summary)
        page.addWidget(intro)

        self.activity_gallery_panel, gallery_layout=panel(
            "GALERIE DES OBJETS",
            "Une carte par objet : sprite du jeu, nom, famille et quantité exacte. "
            "Les images thématiques sont signalées."
        )
        nav=QHBoxLayout()
        self.activity_gallery_count=label("Aucune activité",muted=True,wrap=True)
        nav.addWidget(self.activity_gallery_count,1)
        self.activity_prev=QPushButton("‹ Précédent")
        self.activity_next=QPushButton("Suivant ›")
        self.activity_prev.setObjectName("activityPrevPage")
        self.activity_next.setObjectName("activityNextPage")
        self.activity_prev.clicked.connect(lambda _=False:self._activity_move_page(-1))
        self.activity_next.clicked.connect(lambda _=False:self._activity_move_page(1))
        nav.addWidget(self.activity_prev)
        nav.addWidget(self.activity_next)
        gallery_layout.addLayout(nav)

        self.activity_empty=label(
            "Aucune activité enregistrée pour ce choix. Essaie un autre filtre "
            "ou un autre niveau de difficulté.",muted=True,wrap=True)
        gallery_layout.addWidget(self.activity_empty)
        self.activity_grid=QGridLayout()
        self.activity_grid.setSpacing(13)
        gallery_layout.addLayout(self.activity_grid)
        self.activity_tiles=[]
        self.activity_page_size=16
        self.activity_page_number=0
        self.activity_rows=[]
        self.activity_columns=0
        for _ in range(self.activity_page_size):
            tile=QFrame()
            tile.setObjectName("activityGalleryCard")
            tile.setMinimumWidth(220)
            tile.setFixedHeight(143)
            tile.setStyleSheet(
                "QFrame#activityGalleryCard {background:#182e38;"
                "border:1px solid #415f65;border-radius:12px;}"
                "QFrame#activityGalleryCard:hover {background:#263e46;"
                "border:1px solid #cca274;}"
            )
            inner=QHBoxLayout(tile)
            inner.setContentsMargins(12,12,12,12)
            inner.setSpacing(12)
            picture=QLabel()
            picture.setObjectName("activityGameImage")
            picture.setFixedSize(65,65)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inner.addWidget(picture)
            column=QVBoxLayout()
            column.setSpacing(4)
            family=label("—",muted=True,wrap=True)
            name=label("—",wrap=True)
            name.setStyleSheet("color:#f1e7d9;font:bold 11pt 'Segoe UI';")
            quantity=label("—")
            quantity.setStyleSheet("color:#f7c483;font:bold 18pt 'Segoe UI';")
            hint=label("",muted=True,wrap=True)
            hint.setStyleSheet("color:#a8bcbc;font:8pt 'Segoe UI';")
            column.addWidget(family)
            column.addWidget(name)
            column.addWidget(quantity)
            column.addWidget(hint)
            column.addStretch(1)
            inner.addLayout(column,1)
            self.activity_tiles.append((tile,picture,family,name,quantity,hint))
            self.activity_grid.addWidget(tile,0,0)
            tile.hide()
        page.addWidget(self.activity_gallery_panel)

        detail,detail_layout=panel(
            "DÉTAIL TECHNIQUE",
            "Tableaux complets des objets et des familles : pour vérifier les données "
            "ou rechercher un identifiant spécifique."
        )
        self.activity_technical_button=QPushButton("Afficher les tableaux détaillés")
        self.activity_technical_button.setObjectName("activityTechnicalToggle")
        self.activity_technical_button.setCheckable(True)
        self.activity_technical_button.setChecked(False)
        self.activity_technical_button.toggled.connect(self._toggle_activity_technical)
        detail_layout.addWidget(self.activity_technical_button)
        self.activity_technical_content=QWidget()
        technical_layout=QHBoxLayout(self.activity_technical_content)
        technical_layout.setContentsMargins(0,10,0,0)
        main,ml=panel("OBJETS", "Toutes les lignes, sans limite de pagination.")
        self.activity_items=table(["Catégorie", "Objet / ressource", "Quantité"])
        self.activity_items.setIconSize(QSize(34,34))
        self.activity_items.verticalHeader().setDefaultSectionSize(42)
        ml.addWidget(self.activity_items)
        technical_layout.addWidget(main,3)
        side,sl=panel("RÉPARTITION", "Familles présentes dans les filtres.")
        self.activity_families=table(["Famille", "Quantité", "Part"])
        sl.addWidget(self.activity_families)
        technical_layout.addWidget(side,2)
        detail_layout.addWidget(self.activity_technical_content)
        self.activity_technical_content.hide()
        page.addWidget(detail)
        page.addStretch(1)

        for widget in (self.activity_choice,self.activity_difficulty,
                       self.activity_family,self.activity_sort):
            widget.currentIndexChanged.connect(self._refresh_activity)
        self.activity_search.textChanged.connect(self._refresh_activity)

    def _toggle_activity_technical(self, enabled):
        self.activity_technical_content.setVisible(enabled)
        self.activity_technical_button.setText(
            "Masquer les tableaux détaillés" if enabled else
            "Afficher les tableaux détaillés"
        )

    def _activity_move_page(self, offset):
        total_pages=max(1,(len(self.activity_rows)+self.activity_page_size-1)
                        //self.activity_page_size)
        self.activity_page_number=max(
            0,min(total_pages-1,self.activity_page_number+offset)
        )
        self._render_activity_gallery()

    def _render_activity_gallery(self):
        if not hasattr(self,"activity_tiles"):
            return
        rows=self.activity_rows
        total_pages=max(1,(len(rows)+self.activity_page_size-1)
                        //self.activity_page_size)
        self.activity_page_number=max(0,min(self.activity_page_number,total_pages-1))
        first=self.activity_page_number*self.activity_page_size
        visible=rows[first:first+self.activity_page_size]
        self.activity_gallery_count.setText(
            (f"{first+1}–{first+len(visible)} sur {len(rows)} objets"
             f"  •  Page {self.activity_page_number+1}/{total_pages}")
            if rows else "Aucun objet dans cette sélection"
        )
        self.activity_prev.setEnabled(self.activity_page_number>0)
        self.activity_next.setEnabled(self.activity_page_number+1<total_pages)
        self.activity_empty.setVisible(not rows)
        viewport=self.stack.widget(7)
        available=(viewport.width() if viewport is not None else 1300)-55
        columns=4 if available>=1220 else 3 if available>=850 else 2
        self.activity_columns=columns

        thematic={
            "Bois et arbres":"Wood",
            "Métaux et minerais":"Iron",
            "Pierre et minéraux":"Wishbone",
            "Cuisine et nourriture":"CarrotSoup",
            "Plantes et graines":"Cultivator",
            "Matériel et armes":"SwordIron",
            "Constructions":"Hammer",
            "Autres":"Wishbone",
        }
        for index,(tile,picture,family,name,quantity,hint) in enumerate(self.activity_tiles):
            self.activity_grid.removeWidget(tile)
            if index>=len(visible):
                tile.hide()
                continue
            group,display,count,key=visible[index]
            image=game_icon(key)
            exact=not image.isNull()
            if not exact:
                image=collection_icon(key)
                exact=not image.isNull()
            if image.isNull():
                image=game_icon(thematic[group])
            picture.clear()
            if not image.isNull():
                picture.setPixmap(image.pixmap(QSize(62,62)))
                picture.setToolTip(
                    "Vrai sprite de cet objet Valheim" if exact
                    else "Sprite Valheim thématique : l'objet exact n'a pas d'image locale"
                )
            else:
                picture.setText("Image\nabsente")
                picture.setWordWrap(True)
                picture.setStyleSheet("color:#b8c6c7;font:8pt 'Segoe UI';")
            family.setText(group.upper())
            name.setText(display)
            quantity.setText(txt(count))
            hint.setText("UNITÉS ENREGISTRÉES" if exact else "IMAGE THÉMATIQUE VALHEIM")
            tile.setToolTip(f"{display}\n{txt(count)} unité(s)\n{group}\n"
                            f"Identifiant : {key}")
            self.activity_grid.addWidget(tile,index//columns,index%columns)
            tile.show()

    def _make_skill_detail(self):
        page=self._scroll_page()
        p,pl=panel("COMPÉTENCES DU VIKING",
           "Niveaux et XP exacts enregistrés dans la dernière sauvegarde.")
        self.skills_summary = label("En attente des compétences du Viking.", muted=True, wrap=True)
        pl.addWidget(self.skills_summary)
        self.skills_table=table(["Compétence", "Niveau", "XP enregistré", "Maîtrise / 100"])
        self.skills_table.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(40,40))
        self.skills_table.verticalHeader().setDefaultSectionSize(54)
        pl.addWidget(self.skills_table)
        page.addWidget(p,1)

    def _make_raw_detail(self):
        page=self._scroll_page()
        p,pl=panel("COMPTEURS BRUTS",
           "205 indices par groupe de difficulté ; indices sans nom conservés.")
        row=QHBoxLayout()
        self.raw_group=group_control()
        self.raw_search=QLineEdit()
        self.raw_search.setPlaceholderText("Chercher un indice, un nom ou une valeur…")
        self.raw_group.currentIndexChanged.connect(self._refresh_raw)
        self.raw_search.textChanged.connect(self._refresh_raw)
        row.addWidget(self.raw_group)
        row.addWidget(self.raw_search,1)
        pl.addLayout(row)
        self.raw_count=label("",muted=True);pl.addWidget(self.raw_count)
        self.raw_table_restored=table(["Indice", "Nom technique", "Valeur"])
        pl.addWidget(self.raw_table_restored)
        page.addWidget(p,1)

    def _restore_history_controls(self):
        area=self.stack.widget(3)
        interior=area.widget() if hasattr(area,'widget') else None
        if interior is None:return
        top=interior.layout().itemAt(0)
        if top is None:return
        header=top.widget()
        if header is None:return
        container=header.layout()
        controls=QHBoxLayout()
        self.history_group_restored=group_control()
        self.history_group_restored.currentIndexChanged.connect(self._draw_history_restored)
        self.history_changes_restored=QComboBox()
        self.history_changes_restored.addItems(["Total cumulé","Gains entre sauvegardes"])
        self.history_changes_restored.currentIndexChanged.connect(self._draw_history_restored)
        export=QPushButton("Exporter CSV")
        export.clicked.connect(self.export_history_csv)
        controls.addWidget(label("Difficulté :",muted=True))
        controls.addWidget(self.history_group_restored)
        controls.addWidget(label("Affichage :",muted=True))
        controls.addWidget(self.history_changes_restored)
        controls.addWidget(export)
        container.insertLayout(1,controls)
        self.history_metric.currentIndexChanged.connect(self._draw_history_restored)
        self.history_period.currentIndexChanged.connect(self._draw_history_restored)

    def _restore_achievement_controls(self):
        # Les 53 succès et les deux entrées internes restent dans le moteur.
        area=self.stack.widget(1)
        interior=area
        row=interior.layout()
        if row is None:return
        first=row.itemAt(0).widget()
        if first is None:return
        layout=first.layout()
        line=QHBoxLayout()
        self.ach_category=QComboBox()
        self.ach_category.addItem("Toutes catégories")
        if hasattr(__import__('valheim_reader'),'SPECS'):
            for category in sorted({s.category for s in __import__('valheim_reader').SPECS}):
                self.ach_category.addItem(category)
        self.ach_origin=QComboBox()
        self.ach_origin.addItems(["Actifs + internes","Succès actifs (53)","Internes non vérifiés (2)"])
        self.ach_category.currentIndexChanged.connect(self.draw_achievements)
        self.ach_origin.currentIndexChanged.connect(self.draw_achievements)
        line.addWidget(self.ach_category)
        line.addWidget(self.ach_origin)
        layout.insertLayout(2,line)
        self.ach_parts_search=QLineEdit()
        self.ach_parts_search.setPlaceholderText("Filtrer les critères de ce succès…")
        self.ach_parts_search.textChanged.connect(self.draw_success_detail)
        second=row.itemAt(1).widget()
        if second is not None:
            second.layout().insertWidget(second.layout().count()-1, self.ach_parts_search)

    def _restore_combat_controls(self):
        page=self.stack.widget(2)
        interior=page.widget() if hasattr(page,'widget') else None
        if interior is None:return
        layout=interior.layout()
        if layout is None:return
        p,pl=panel("DÉTAIL DES ÉLIMINATIONS",
            "Poings, magie, distance et mêlée : catégories enregistrées par le jeu.")
        self.combat_search_restored=QLineEdit()
        self.combat_search_restored.setPlaceholderText("Rechercher une créature…")
        self.combat_search_restored.textChanged.connect(self._refresh_combat_detail)
        pl.addWidget(self.combat_search_restored)
        self.combat_details=table(["Créature","Total","Poings","Magie","Distance","Mêlée"])
        self.combat_details.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(34,34))
        self.combat_details.verticalHeader().setDefaultSectionSize(42)
        pl.addWidget(self.combat_details,1)
        layout.addWidget(p,2)
        self.combat_group.currentIndexChanged.connect(self._refresh_combat_detail)


    def draw_success_detail(self):
        """Restaure les listes complètes, sans limite cachée de 50/200 critères."""
        super().draw_success_detail()
        if not hasattr(self,'ach_parts_search') or not getattr(self,'results',None):
            return
        achievement=next((a for a in self.results
                          if a['key']==self.selected_achievement),None)
        if achievement is None:return
        self.ach_parts.setColumnCount(3)
        self.ach_parts.setHorizontalHeaderLabels(['Critère','Acquis / objectif','Restant'])
        query=self.ach_parts_search.text().strip().casefold()
        parts=sorted(achievement['parts'],key=lambda p:(p.get('complete',False),str(p['label']).casefold()))
        if query:
            parts=[p for p in parts if query in str(p['label']).casefold() or query in str(p.get('key','')).casefold()]
        self.ach_parts.setRowCount(len(parts))
        for i,part in enumerate(parts):
            icon=game_icon(part.get('key',''))
            if icon.isNull():icon=game_icon(part.get('label',''))
            current=txt(float(part.get('current',0)),1)
            goal=part.get('goal')
            remaining=part.get('remaining')
            self.ach_parts.setItem(i,0,_table_item(part['label'],icon))
            self.ach_parts.setItem(i,1,_table_item(current+' / '+txt(float(goal),1) if goal is not None else current))
            self.ach_parts.setItem(i,2,_table_item(
                '✓' if part.get('complete') else ('—' if remaining is None else txt(float(remaining),1))))
        self.ach_parts.verticalHeader().setDefaultSectionSize(38)

    def _refresh_restored_pages(self):
        if not self.store.profile:return
        self._refresh_dashboard_extra()
        self._refresh_progress_center()
        self._refresh_boss_detail()
        self._refresh_activity()
        self._refresh_skills()
        self._refresh_raw()
        self._refresh_combat_detail()
        self._draw_history_restored()

    def _refresh_progress_center(self):
        if not self.store.profile or not hasattr(self,'focus_table'):return
        favorites=self.store.favorites()
        ranked=progress_ranking(self.results, favorites)
        selected=self.focus_filter.currentText()
        if selected=="Favoris":ranked=[r for r in ranked if r['key'] in favorites]
        if selected=="Non commencés":ranked=[r for r in ranked if r['fraction']==0]
        self.focus_table.blockSignals(True)
        _fill_table(self.focus_table,[
            ('★' if r['key'] in favorites else '☆', r['title'],
             f"{r['percent']:.1f} %",str(r['total_conditions']-r['completed_conditions']))
            for r in ranked])
        for idx,r in enumerate(ranked):
            self.focus_table.item(idx,0).setData(Qt.ItemDataRole.UserRole,r['key'])
            ico=achievement_icon(r.get('title_en',''))
            if not ico.isNull():self.focus_table.item(idx,1).setIcon(ico)
        self.focus_table.blockSignals(False)
        keys=[r['key'] for r in ranked]
        if keys:
            if self.focus_key not in keys:self.focus_key=keys[0]
            self.focus_table.setCurrentCell(keys.index(self.focus_key),1)
        else:self.focus_key=''
        self._focus_selection()
        report=session_report(self.store.rows(limit=500))
        if report.get('available'):
            gains=[f"{name} +{txt(value,1)}" for name,value in report['changes'].items() if value>0]
            self.focus_session.setText(
                f"{report['samples']} relevés · {report['game_minutes']:.0f} min observées\n"
                + (' · '.join(gains) if gains else 'Pas de gains constatés')
                + ('\nNouveaux objectifs : '+', '.join(report['reached']) if report['reached'] else '')
                + '\nSession estimée, sans heures de connexion exactes.'
            )
        else:self.focus_session.setText(report.get('reason','Aucune donnée.'))

    def _focus_selection(self):
        if not self.store.profile or not hasattr(self,'focus_table'):return
        row=self.focus_table.currentRow()
        if row<0:return
        cell=self.focus_table.item(row,0)
        if cell is None:return
        key=cell.data(Qt.ItemDataRole.UserRole)
        if not key:return
        self.focus_key=key
        target=next((r for r in self.results if r['key']==key),None)
        if target is None:return
        self.focus_title.setText(target['title'])
        self.focus_note.setText(target['description'] + "\n"
            + f"{target['percent']:.1f} % · {target['completed_conditions']} sur {target['total_conditions']} critères.")
        self.focus_star.setText("★ Retirer des favoris" if key in self.store.favorites() else "☆ Ajouter aux favoris")
        remaining=pending_actions(target,limit=len(target['parts']))
        _fill_table(self.focus_actions,[
           (p['label'],txt(p['current'],1),txt(p['remaining'],1)) for p in remaining],
            [game_icon(p.get('label','')) for p in remaining])

    def _toggle_focus_favorite(self):
        if not self.focus_key:return
        self.store.toggle_favorite(self.focus_key)
        self._refresh_progress_center()
        self.draw_achievements()

    def _open_focus_achievement(self):
        if not self.focus_key:return
        self.selected_achievement=self.focus_key
        self.show_page(1)
        self.draw_achievements()

    def _refresh_boss_detail(self):
        if not self.store.profile or not hasattr(self,'boss_table'):return
        p=self.store.profile
        groups=('Any','Default','Hard','VeryHard','Hardcore')
        lines=[]
        for token,display in BOSSES.items():
            lines.append(tuple([display]+[txt(p['groups'][g]['enemies'][0].get(token,0)) for g in groups]))
        _fill_table(self.boss_table,lines,
             [boss_game_icon(token) for token in BOSSES])
        selected = self.boss_group_choice.currentData()
        selected_kills = p['groups'][selected]['enemies'][0]
        cleared = 0
        for token, (card, state) in self.boss_cards.items():
            count = int(selected_kills.get(token, 0))
            cleared += bool(count)
            status = (f"{count} victoire(s) enregistrée(s)" if count else
                      "Aucune victoire enregistrée")
            if token in THEMATIC_BOSS_ICONS:
                status += " · visuel thématique"
            state.setText(status)
            card.setStyleSheet(
                "QFrame#bossVisualCard {background:" +
                ("#243b37;border:1px solid #96b883;" if count else
                 "#152c35;border:1px solid #415c61;") +
                "border-radius:12px;}"
            )
        self.boss_overview.setText(
            f"{cleared} / {len(BOSSES)} boss distincts enregistrés dans le groupe "
            f"« {self.boss_group_choice.currentText()} ». "
            "Les niveaux de difficulté se recouvrent."
        )
        done={g:sum(p['groups'][g]['enemies'][0].get(tok,0)>0 for tok in BOSSES) for g in groups}
        self.boss_info.setText(
            'Boss distincts validés : '+', '.join(
                f"{name} {done[key]}/8" for name,key in GROUP_CHOICES if key in done
            )+'\nLes difficultés sont des ensembles qui se recouvrent : ne les additionne pas.'
        )

    def _refresh_activity(self):
        if not hasattr(self,"activity_items"):
            return
        if not self.store.profile:
            self.activity_rows=[]
            self.activity_metrics["types"].setText("0")
            self.activity_metrics["total"].setText("0")
            self.activity_metrics["family"].setText("—")
            self.activity_summary.setText(
                "Charge une sauvegarde .fch pour afficher ses activités."
            )
            self._render_activity_gallery()
            return
        group=self.activity_difficulty.currentData()
        action=self.activity_choice.currentData()
        data=self.store.profile.get("groups",{}).get(group,{}).get(action,{})
        needle=self.activity_search.text().strip().casefold()
        group_filter=self.activity_family.currentData()
        rows=[]
        families={}
        for key,amount in data.items():
            try:
                number=float(amount)
            except (ValueError,TypeError,OverflowError):
                continue
            if not 0<number<float("inf"):
                continue
            display=_display_token(key)
            if needle not in display.casefold() and needle not in key.casefold():
                continue
            family=activity_category(key)
            if group_filter and family!=group_filter:
                continue
            rows.append((family,display,number,key))
            families[family]=families.get(family,0)+number
        sorting=self.activity_sort.currentData()
        if sorting=="az":
            rows.sort(key=lambda r:(r[1].casefold(),-r[2]))
        elif sorting=="least":
            rows.sort(key=lambda r:(r[2],r[1].casefold()))
        else:
            rows.sort(key=lambda r:(-r[2],r[1].casefold()))
        self.activity_rows=rows
        self.activity_page_number=0
        total=sum(families.values())
        dominant=(max(families,key=families.get) if families else "—")
        self.activity_metrics["types"].setText(txt(len(rows)))
        self.activity_metrics["total"].setText(txt(total))
        self.activity_metrics["family"].setText(dominant)
        self.activity_summary.setText(
            (f"{len(rows)} objets distincts  •  {txt(total)} actions enregistrées  •  "
             "Les groupes de difficulté sont des ensembles qui se recouvrent.")
            if rows else
            "Aucun objet correspondant aux filtres. Les anciens compteurs "
            "absents ne signifient pas qu'aucune action n'a été réalisée."
        )
        self._render_activity_gallery()
        # Tableau inchangé pour le contrôle de toutes les lignes. Il reste
        # entièrement accessible sans envahir la galerie.
        self.activity_items.setRowCount(len(rows))
        for idx,(family,display,count,key) in enumerate(rows):
            self.activity_items.setItem(idx,0,_table_item(family))
            self.activity_items.setItem(idx,1,_table_item(display,game_icon(key)))
            self.activity_items.setItem(idx,2,_table_item(txt(count)))
        _fill_table(self.activity_families,[
            (family,txt(amount),f"{100*amount/total:.0f} %" if total else "—")
            for family,amount in sorted(families.items(),key=lambda pair:-pair[1])
        ])

    def _refresh_skills(self):
        if not self.store.profile or not hasattr(self,'skills_table'):return
        skills=sorted(self.store.profile['skills'].items(),
            key=lambda p:-float(p[1].get('level',0)))
        _fill_table(self.skills_table,[
            (name,txt(float(d.get('level',0)),2),txt(float(d.get('xp',0)),1),
             f"{max(0, min(100, float(d.get('level',0)))):.0f} / 100")
            for name,d in skills], [skill_game_icon(name) for name,_ in skills])
        self.skills_summary.setText(
            (f"{len(skills)} compétences enregistrées · "
             f"Plus élevée : {skills[0][0]} "
             f"(niveau {txt(float(skills[0][1].get('level',0)),1)}).")
            if skills else "Aucune compétence enregistrée dans ce fichier."
        )
        for i, (name, item) in enumerate(skills):
            level = max(0, min(100, float(item.get('level', 0))))
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(level * 10))
            bar.setFormat(f"{level:.0f} / 100")
            bar.setMinimumHeight(23)
            bar.setToolTip(f"{name} : niveau {level:.1f} sur 100")
            self.skills_table.setCellWidget(i, 3, bar)

    def _refresh_raw(self):
        if not self.store.profile or not hasattr(self,'raw_table_restored'):return
        group=self.raw_group.currentData()
        stats=self.store.profile['groups'][group]['stats']
        needle=self.raw_search.text().strip().casefold()
        rows=[]
        for index,value in enumerate(stats):
            name=PLAYER_STAT_NAMES[index] if index<len(PLAYER_STAT_NAMES) else f"Inconnu_{index}"
            if needle not in str(index).casefold() and needle not in name.casefold() and needle not in txt(value).casefold():
                continue
            rows.append((str(index),name,txt(float(value),1)))
        self.raw_count.setText(f"{len(rows)} / {len(stats)} compteurs affichés · {sum(bool(v) for v in stats)} non nuls.")
        _fill_table(self.raw_table_restored,rows)

    def _refresh_combat_detail(self):
        if not self.store.profile or not hasattr(self,'combat_details'):return
        group=self.combat_group.currentData()
        data=self.store.profile['groups'][group]['enemies']
        search=self.combat_search_restored.text().casefold().strip()
        tokens=sorted(data[0], key=lambda tok:-data[0].get(tok,0))
        rows=[]
        icons=[]
        for token in tokens:
            name=_display_token(token)
            if search not in name.casefold() and search not in token.casefold():continue
            rows.append(tuple([name]+[txt(view.get(token,0)) for view in data[:5]]))
            icons.append(game_icon(token))
        _fill_table(self.combat_details,rows,icons)

    def _draw_history_restored(self):
        if not self.store.profile or not hasattr(self,'history_changes_restored'):return
        records=self.store.rows(limit=5000)
        group=self.history_group_restored.currentData()
        measure=self.history_metric.currentData()
        period=self.history_period.currentData()
        gains=self.history_changes_restored.currentIndex()==1
        points=history_points(records,measure,group,changes=gains)
        if period is not None and points:
            cutoff=points[-1][0]-period
            points=[p for p in points if p[0]>=cutoff]
        self.history_chart.set_data(points,
            self.history_metric.currentText()+(' • gains' if gains else ' • total'))

    def export_history_csv(self):
        if not self.store.profile:return
        path,_=QFileDialog.getSaveFileName(self,'Exporter l’historique','valheim_stats_historique.csv',
            'Fichier CSV (*.csv)')
        if not path:return
        try:
            rows=self.store.rows(limit=5000)
            from valheim_reader import metrics
            with open(path,'w',encoding='utf-8-sig',newline='') as out:
                writer=csv.writer(out,delimiter=';')
                writer.writerow(['date','fichier','groupe','créatures tuées','décès','boss',
                                 'objets fabriqués','constructions','objets ramassés','heures'])
                for _,ts,filename,p in rows:
                    for group in ('Any','Default','Hard'):
                        result=metrics(p,group)
                        writer.writerow([datetime.fromtimestamp(ts).isoformat(timespec='seconds'),
                           filename,group]+[result[key] for key in
                             ('kills','deaths','bosses','crafted','built','picked_up','world_hours')])
        except (OSError,ValueError) as exc:
            QMessageBox.critical(self,"Export impossible",str(exc))
            return
        QMessageBox.information(self,"Export terminé",str(path))
