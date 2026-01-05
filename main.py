#!/usr/bin/env python3

import csv
import math
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from PIL import Image
from tqdm import tqdm
from io import BytesIO

# ================= CONFIG =================

ITUNES_TXT_PATH = "___2025 Jazz.txt"
OUTPUT_IMAGE = "bandcamp_jazz_mosaic_2000.png"
TEMP_DIR = "album_covers"

FINAL_SIZE = 2000
BASE_DELAY = 2.0  # seconds between albums
MAX_RETRIES = 5

USER_AGENT = "Mozilla/5.0 (compatible; AlbumArtMosaic/1.0)"

# =========================================

HEADERS = {"User-Agent": USER_AGENT}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def cover_path(artist: str, album: str) -> str:
    name = slugify(f"{artist}_{album}")
    return os.path.join(TEMP_DIR, f"{name}.jpg")


def miss_path(artist: str, album: str) -> str:
    return cover_path(artist, album) + ".miss"


def extract_unique_albums(txt_path):
    albums = set()
    with open(txt_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            artist = row.get("Artist", "").strip()
            album = row.get("Album", "").strip()
            if artist and album:
                albums.add((artist, album))
    return list(albums)


def get_with_backoff(url, **kwargs):
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        r = SESSION.get(url, **kwargs)
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            time.sleep(delay)
            delay *= 2
            continue
        return None
    return None


def search_bandcamp_album(artist, album):
    query = f"{artist} {album}"
    url = "https://bandcamp.com/search"
    params = {"q": query, "item_type": "a"}

    r = get_with_backoff(url, params=params, timeout=15)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    img = soup.select_one("li.searchresult img")
    if not img or not img.get("src"):
        return None

    return img["src"]


def fetch_album_art(img_url):
    r = get_with_backoff(img_url, timeout=15)
    if not r:
        return None

    return Image.open(BytesIO(r.content)).convert("RGB")


def download_covers(albums):
    os.makedirs(TEMP_DIR, exist_ok=True)

    for artist, album in tqdm(albums, desc="Downloading Bandcamp covers"):
        img_path = cover_path(artist, album)
        miss = miss_path(artist, album)

        if os.path.exists(img_path) or os.path.exists(miss):
            continue

        try:
            img_url = search_bandcamp_album(artist, album)
            if not img_url:
                open(miss, "w").close()
                continue

            img = fetch_album_art(img_url)
            if not img:
                open(miss, "w").close()
                continue

            img.save(img_path, "JPEG", quality=90)

        except Exception:
            open(miss, "w").close()

        time.sleep(BASE_DELAY)


def load_images_from_disk():
    images = []
    for fname in sorted(os.listdir(TEMP_DIR)):
        if not fname.endswith(".jpg"):
            continue
        path = os.path.join(TEMP_DIR, fname)
        try:
            images.append(Image.open(path).convert("RGB"))
        except Exception:
            pass
    return images


def build_mosaic(images):
    count = len(images)
    if count == 0:
        print("No images found.")
        return

    grid = math.ceil(math.sqrt(count))
    tile_size = FINAL_SIZE // grid

    mosaic = Image.new("RGB", (FINAL_SIZE, FINAL_SIZE), "black")

    for i, img in enumerate(images):
        img = img.resize((tile_size, tile_size), Image.LANCZOS)
        x = (i % grid) * tile_size
        y = (i // grid) * tile_size
        mosaic.paste(img, (x, y))

    mosaic.save(OUTPUT_IMAGE, quality=95)
    print(f"Saved mosaic: {OUTPUT_IMAGE}")
    print(f"Albums used: {count}")


def main():
    albums = extract_unique_albums(ITUNES_TXT_PATH)
    print(f"Found {len(albums)} unique albums\n")

    download_covers(albums)

    images = load_images_from_disk()
    build_mosaic(images)


if __name__ == "__main__":
    main()
