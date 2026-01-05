#!/usr/bin/env python3

import csv
import math
import os
import re
import time
import requests
import musicbrainzngs
from bs4 import BeautifulSoup
from PIL import Image
from tqdm import tqdm
from io import BytesIO

# ================= CONFIG =================

ITUNES_TXT_PATH = "___2025 Jazz.txt"  # path to your iTunes export
OUTPUT_IMAGE = "bandcamp_jazz_mosaic_2000.png"
TEMP_DIR = "album_covers"

FINAL_SIZE = 2000  # final mosaic size (2000x2000)
USER_AGENT = "Mozilla/5.0 (compatible; AlbumArtMosaic/1.0)"

# =========================================

HEADERS = {"User-Agent": USER_AGENT}

# Set user agent / headers.
musicbrainzngs.set_useragent(
    app="NewYearsAlbumArtMosaic", version="0.0.1", contact="jalen.michalslevy@gmail.com"
)


def normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_unique_albums(txt_path):
    albums = set()
    with open(txt_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            artist = row.get("Artist", "").strip()
            album = row.get("Album", "").strip()
            if artist and album:
                albums.add((normalize(artist), normalize(album), artist, album))
    return list(albums)


def search_bandcamp_album(artist, album):
    query = f"{artist} {album}"
    url = "https://bandcamp.com/search"
    params = {"q": query, "item_type": "a"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    print(r.status_code)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    result = soup.select_one("li.searchresult img")
    print(result)
    if not result:
        return None

    return result["src"]


def fetch_album_art(album_url):
    img_data = requests.get(album_url, headers=HEADERS, timeout=15)

    if img_data.status_code != 200:
        return None

    return Image.open(BytesIO(img_data.content)).convert("RGB")


def main():
    os.makedirs(TEMP_DIR, exist_ok=True)

    albums = extract_unique_albums(ITUNES_TXT_PATH)
    images = []

    print(f"Found {len(albums)} unique albums\n")

    for _, _, artist, album in tqdm(albums, desc="Searching Bandcamp"):
        try:
            album_url = search_bandcamp_album(artist, album)
            if not album_url:
                continue

            img = fetch_album_art(album_url)
            if img:
                images.append(img)
            time.sleep(0.5)  # be polite to Bandcamp

        except Exception:
            print(f"Failed to fetch album art for {artist} - {album}")

    if not images:
        print("No Bandcamp album art found.")
        return

    # ===== Build mosaic =====
    count = len(images)
    grid = math.ceil(math.sqrt(count))
    tile_size = FINAL_SIZE // grid

    mosaic = Image.new("RGB", (FINAL_SIZE, FINAL_SIZE), "black")

    for i, img in enumerate(images):
        img = img.resize((tile_size, tile_size), Image.LANCZOS)
        x = (i % grid) * tile_size
        y = (i // grid) * tile_size
        mosaic.paste(img, (x, y))

    mosaic.save(OUTPUT_IMAGE, quality=95)
    print(f"\nSaved mosaic: {OUTPUT_IMAGE}")
    print(f"Albums used: {count}")


if __name__ == "__main__":
    main()
