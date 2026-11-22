"""Suivi manuel de forge, indépendant des compteurs .fch et des succès Steam.

Le journal vit dans LOCALAPPDATA et n'écrit jamais dans les sauvegardes du jeu.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def checklist_path(directory=None):
    root = Path(directory) if directory is not None else (
        Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "ValheimStatsTracker")
    return root / "forge_checklist.json"


class ForgeChecklist:
    def __init__(self, directory=None):
        self.path = checklist_path(directory)
        self._data = {"schema": 1, "characters": {}}
        if self.path.is_file():
            try:
                decoded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(decoded, dict) and decoded.get("schema") == 1 and isinstance(decoded.get("characters"), dict):
                    self._data = decoded
            except (ValueError, OSError):
                # Une sauvegarde invalide n'est jamais écrasée silencieusement.
                self._read_only = True
                return
        self._read_only = False

    def checked(self, character, token):
        if not character or not token:
            return False
        return token in self._data["characters"].get(character, [])

    def count(self, character):
        return len(self._data["characters"].get(character, []))

    def set_checked(self, character, token, checked):
        if self._read_only:
            raise ValueError("Journal de forge invalide : aucun écrasement automatique")
        if not isinstance(character, str) or not character.strip():
            raise ValueError("Personnage requis pour le journal de forge")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Identifiant d'objet requis")
        before = self._data["characters"].get(character, [])
        after = set(before)
        if checked:
            after.add(token)
        else:
            after.discard(token)
        if set(before) == after:
            return
        data = {"schema": 1, "characters": dict(self._data["characters"])}
        data["characters"][character] = sorted(after)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".forge_", suffix=".json", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        self._data = data
