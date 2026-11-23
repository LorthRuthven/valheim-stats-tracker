"""Recherche d'activités testable sans interface Qt."""
import unicodedata


def search_normalize(text):
    """Recherche tolérante aux accents, à la casse et aux espaces."""
    raw = unicodedata.normalize("NFKD", str(text)).casefold()
    return "".join(c for c in raw if not unicodedata.combining(c))
