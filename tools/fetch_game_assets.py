"""Télécharge, pour la distribution Windows, des ressources de première main.

Succès : icônes Steam Community de Valheim. Décor : capture du kit presse
officiel Iron Gate. Une image manquante n'est jamais remplacée par une fausse
icône de succès. Les icônes d'inventaire complètes sont extraites du jeu
déjà installé, sur demande (game_icon_extraction.py), sans aucun mod.
"""
from __future__ import annotations

import json
import re
import ssl
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets'
STEAM_PAGES=[
    'https://steamcommunity.com/stats/892970/achievements/?l=english',
    'https://steamcommunity.com/achievements/892970?l=english',
]
FALLBACK='https://valheim.fans/guides/achievements'
OFFICIAL_PRESS='https://img2.storyblok.com/fit-in/1400x850/f/157036/2560x1440/ed87ecf070/news-1.jpg'

def slug(value):
    return re.sub('[^a-z0-9]+','',unicodedata.normalize('NFKD',value).casefold())

def get(url,max_size=2_000_000):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (compatible; ValheimTracker/2.2; community companion)',
        'Accept':'text/html,image/avif,image/webp,image/png,image/jpeg,*/*',
    })
    with urllib.request.urlopen(req,timeout=22) as response:
        content=response.read(max_size+1)
        if len(content)>max_size:raise ValueError('Ressource trop volumineuse')
        return content

def find_achievements(html):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    found={}
    for row in soup.select('.achieveRow, .achieve_block, .achievement, .achievement-card'):
        title=row.select_one('h3, .achieveTxt h3, .achieveTxt .achieveName')
        img=row.select_one('.achieveImgHolder img, .achievmentIcon img, img')
        if title is not None and img is not None:
            url=img.get('src') or img.get('data-src')
            if url:found[slug(title.get_text(' ',strip=True))]=urllib.parse.urljoin(FALLBACK,url)
    for img in soup.select('img'):
        alt=img.get('alt','')
        if alt.casefold().endswith(' achievement icon'):
            title=alt[:-len(' achievement icon')]
            url=img.get('src') or img.get('data-src')
            if url:found.setdefault(slug(title),urllib.parse.urljoin(FALLBACK,url))
    return found

def valid_steam(url):
    host=urllib.parse.urlsplit(url).hostname or ''
    return (host.endswith('steamstatic.com') or host.endswith('steamcommunity.com')
            or host.endswith('akamaihd.net') or host=='valheim.fans')

def download_assets():
    from valheim_reader import SPECS
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/'achievements').mkdir(parents=True,exist_ok=True)
    (BASE/'items').mkdir(parents=True,exist_ok=True)
    required={slug(s.title):s.title for s in SPECS if s.origin=='Jeu + Steam'}
    found={}
    for url in STEAM_PAGES+[FALLBACK]:
        try:
            content=get(url,max_size=3_500_000).decode('utf8',errors='replace')
            entries=find_achievements(content)
            print('SOURCE',url,'pictogrammes',len(entries),flush=True)
            print('EXEMPLES',list(entries.items())[:3],flush=True)
            for key,value in entries.items():
                if key in required and key not in found and valid_steam(value):
                    found[key]=value
            # On peut exploiter les 53 badges Steam de deux sources sans les dupliquer.
        except Exception as exc:
            print('SOURCE INDISPONIBLE',url,str(exc)[:120],flush=True)
    catalog={'achievements':{},'items':{}}
    for key,url in found.items():
        try:
            content=get(url,max_size=400_000)
            from PIL import Image
            from io import BytesIO
            image=Image.open(BytesIO(content))
            if image.width<32 or image.height<32 or image.width>2000 or image.height>2000:
                continue
            name=key+'.png'
            image.convert('RGBA').save(BASE/'achievements'/name,format='PNG',optimize=True)
            catalog['achievements'][key]=name
        except Exception as exc:
            print('ICON FAILED',key,str(exc)[:95],flush=True)
    # Décor officiel, jamais une image générée.
    try:
        content=get(OFFICIAL_PRESS,max_size=3_000_000)
        if content.startswith(b'\xff\xd8\xff'):
            (BASE/'hero.jpg').write_bytes(content)
    except Exception as exc:
        print('OFFICIAL HERO FAILED',str(exc)[:130],flush=True)
    # Logo original Valheim tel que publié dans les médias Steam.
    try:
        header=get('https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/892970/header.jpg',
                   max_size=1_000_000)
        if header.startswith(b'\xff\xd8\xff'):
            (BASE/'logo.jpg').write_bytes(header)
    except Exception as exc:
        print('OFFICIAL LOGO FAILED',str(exc)[:120],flush=True)
    # Un petit ensemble d'icônes d'inventaire publiques si le wiki est accessible.
    # Les centaines d'icônes complètes proviendront de l'installation locale.
    images={
        'Wood.png':['wood'], 'Stone.png':['stone'], 'Raspberries.png':['raspberries','raspberry'],
        'Blueberries.png':['blueberries'], 'Mushroom.png':['mushroom'],
        'Flint.png':['flint'], 'Iron.png':['iron'], 'Bronze.png':['bronze'],
        'Honey.png':['honey'], 'Carrot.png':['carrot'], 'Turnip.png':['turnip'],
        'Thistle.png':['thistle'], 'Obsidian.png':['obsidian'],
        'Lox meat.png':['loxmeat'], 'Deer trophy.png':['trophydeer'],
        'Greydwarf trophy.png':['trophygreydwarf'],
    }
    for filename,keys in images.items():
        url='https://valheim.fandom.com/wiki/Special:Redirect/file/'+urllib.parse.quote(filename)
        try:
            content=get(url,max_size=300_000)
            from PIL import Image
            from io import BytesIO
            image=Image.open(BytesIO(content))
            if image.width<24 or image.height<24 or image.width>3000:continue
            name=slug(keys[0])+'.png'
            image.convert('RGBA').save(BASE/'items'/name,format='PNG',optimize=True)
            for key in keys:catalog['items'][slug(key)]=name
        except Exception:
            continue
    (BASE/'index.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (BASE/'ATTRIBUTIONS.txt').write_text(
        'Valheim, captures du kit presse et icônes : © Iron Gate AB / Coffee Stain Publishing.\n'
        'Succès : images officielles publiées par Steam Community.\n'
        'Capture : https://www.valheimgame.com/press/\n'
        'Logo Valheim : visuel promotionnel Valve Steam Store.\n'
        'Objets : images du jeu (wiki Valheim) ou extraction facultative des fichiers du jeu appartenant à l’utilisateur.\n'
        'Compagnon non officiel, sans affiliation ni approbation des éditeurs.\n',
        encoding='utf8'
    )
    print('BILAN',len(catalog['achievements']),'icônes Steam / 53 ;',
          len(catalog['items']),'icônes objets ;',
          (BASE/'hero.jpg').is_file(),'image presse',flush=True)
    if len(catalog['achievements'])<15:
        raise RuntimeError('Moins de 15 icônes de succès officielles récupérées ; distribution graphique incomplète.')
    if not (BASE/'hero.jpg').is_file():
        raise RuntimeError('Image réelle officielle manquante : distribution non publiée.')
    return catalog

if __name__=='__main__':
    download_assets()
