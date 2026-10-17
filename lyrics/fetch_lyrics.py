"""
Fetch synced lyrics from LRCLIB (https://lrclib.net) for the iPod's music and
save them where Rockbox's lrcplayer looks for them.

Where lrcplayer looks (apps/plugins/lrcplayer.c, find_lrc_file_helper): this
firmware has multivolume support, so a song's path is "/<HDD0>/Music/Album/Song.flac".
Walking up from the song's folder it checks "<dir>/Song.lrc8" and
"<dir>/Lyrics/Song.lrc8"; at the top level that gives /Lyrics/Song.lrc8. Its
"/Lyrics" mirror tree would be /Lyrics/<HDD0>/Music/... - impossible on FAT
('<' '>' aren't allowed) - so files go FLAT in /Lyrics, and only songs whose file
names clash go into a "Lyrics" folder next to the song. .lrc8 is read as UTF-8.

Songs without lyrics get a one-line placeholder so lrcplayer says so instead of
showing a blank screen (it draws nothing when no lyrics file is found).

The iPod's fonts only cover U+0020..U+052F, so Indic scripts are romanised.

Only synced lyrics are saved (lrcplayer needs timestamps). Results are logged to
lyrics_log.csv; reruns skip songs already fetched or already not found.

    python fetch_lyrics.py <music root on iPod, e.g. E:\\Music> [--limit N]
Writes ./ipod/... laid out like the iPod's root: copy its contents to E:\\.
"""
import csv
import os
import re
import sys
import time
import unicodedata

import requests
import mutagen

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.join(HERE, "ipod")            # mirror of the iPod's drive root
PLACEHOLDER = "[00:00.00]Lyrics aren't available for this song\n"
LOG = os.path.join(HERE, "lyrics_log.csv")
API = "https://lrclib.net/api"
HEADERS = {"User-Agent": "spotish-rockbox-lyrics/1.0 (https://github.com/stylo969/spotish-rockbox; personal library sync)"}
AUDIO_EXT = {".m4a", ".flac", ".mp3", ".ogg", ".opus"}
DELAY = 0.35  # seconds between requests, to be polite to the free service


# ---------------------------------------------------------------- tags
def first(tags, *keys):
    for k in keys:
        v = tags.get(k)
        if v:
            v = v[0] if isinstance(v, list) else v
            return str(v).strip()
    return ""


def read_tags(path):
    f = mutagen.File(path, easy=True)
    if f is None:
        return None
    tags = f.tags or {}
    title = first(tags, "title")
    artist = first(tags, "artist", "albumartist")
    album = first(tags, "album")
    if not title:  # fall back to "NN. Artist - Title" style file names
        stem = os.path.splitext(os.path.basename(path))[0]
        stem = re.sub(r"^\d+[\s.\-_]+", "", stem)
        if " - " in stem and not artist:
            artist, title = stem.split(" - ", 1)
        else:
            title = stem
    return {"title": title, "artist": artist, "album": album, "duration": int(round(f.info.length or 0))}


def primary_artist(artist):
    return re.split(r"\s*(?:,|;|&| feat\.? | ft\.? | x |/)\s*", artist, maxsplit=1)[0].strip()


# ---------------------------------------------------------------- LRCLIB
def lrclib(session, endpoint, params):
    for attempt in range(3):
        try:
            r = session.get(f"{API}/{endpoint}", params=params, headers=HEADERS, timeout=20)
            time.sleep(DELAY)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def find_synced(session, t):
    """Exact match first (title/artist/album/duration), then looser searches."""
    tries = []
    if t["album"]:
        tries.append({"track_name": t["title"], "artist_name": t["artist"], "album_name": t["album"],
                      "duration": t["duration"]})
    tries.append({"track_name": t["title"], "artist_name": t["artist"], "duration": t["duration"]})
    for p in tries:
        hit = lrclib(session, "get", p)
        if readable_synced(hit):
            return hit, "exact"
    # looser searches; the title-only search also finds other uploads of the same
    # song, e.g. a Hindi/romanised version when the exact match was in Urdu script
    searches = [{"track_name": t["title"], "artist_name": a}
                for a in dict.fromkeys([t["artist"], primary_artist(t["artist"])])]
    searches.append({"track_name": t["title"]})
    for params in searches:
        res = lrclib(session, "search", params) or []
        best = None
        for h in res:
            if not readable_synced(h):
                continue
            dd = abs((h.get("duration") or 0) - t["duration"])
            if dd <= 4 and (best is None or dd < best[0]):
                best = (dd, h)
        if best:
            return best[1], "search"
    return None, "not found"


# ---------------------------------------------------------------- romanisation
# The Indic Unicode blocks (Devanagari U+0900, Gurmukhi U+0A00, Tamil U+0B80, ...)
# share the ISCII-derived layout, so other scripts are shifted onto Devanagari
# first, then one table romanises them all.
_CONS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch",
         "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny", "ट": "t", "ठ": "th",
         "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
         "ध": "dh", "न": "n", "ऩ": "n", "प": "p", "फ": "ph", "ब": "b",
         "भ": "bh", "म": "m", "य": "y", "र": "r", "ऱ": "r", "ल": "l",
         "ळ": "l", "ऴ": "zh", "व": "v", "श": "sh", "ष": "sh", "स": "s",
         "ह": "h",
         "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "r", "ढ़": "rh",
         "फ़": "f", "य़": "y"}
# Unicode normalisation splits nukta letters (U+0958 -> U+0915 U+093C), so the
# keys must be normalised the same way as the text or they never match.
CONS = {unicodedata.normalize("NFC", k): v for k, v in _CONS.items()}
VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
          "ऋ": "ri", "ऎ": "e", "ए": "e", "ऐ": "ai", "ऒ": "o", "ओ": "o",
          "औ": "au", "ऑ": "o", "ॲ": "e"}
MATRAS = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
          "ॆ": "e", "े": "e", "ै": "ai", "ॊ": "o", "ो": "o", "ौ": "au",
          "ॉ": "o", "ॅ": "e"}
SIGNS = {"ं": "n", "ँ": "n", "ः": "h", "ॐ": "om", "।": ".", "॥": ".",
         "ऽ": "'", "़": ""}
VIRAMA, NUKTA = "्", "़"


def indic_to_devanagari(s):
    out = []
    for i, ch in enumerate(s):
        o = ord(ch)
        if ch == "ੰ":            # Gurmukhi tippi -> anusvara
            out.append("ं")
        elif ch == "ੱ":          # Gurmukhi addak: doubles the next consonant
            nxt = s[i + 1] if i + 1 < len(s) else " "
            if 0x0A00 <= ord(nxt) <= 0x0A6F:
                out.append(chr(ord(nxt) - 0x100) + VIRAMA)
        elif 0x0980 <= o <= 0x0D7F and (o & 0x7F) <= 0x6F:
            out.append(chr(0x0900 + (o & 0x7F)))   # same slot in the Devanagari block
        else:
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def romanise_word(w):
    w = unicodedata.normalize("NFC", w)
    res, i = [], 0
    while i < len(w):
        ch = w[i]
        if i + 1 < len(w) and w[i + 1] == NUKTA and ch + NUKTA in CONS:
            ch, i = ch + NUKTA, i + 1
        if ch in CONS:
            nxt = w[i + 1] if i + 1 < len(w) else ""
            if nxt == VIRAMA:
                res.append(CONS[ch]); i += 2; continue
            if nxt in MATRAS:
                res.append(CONS[ch] + MATRAS[nxt]); i += 2; continue
            res.append(CONS[ch] + "a")    # inherent vowel, trimmed below (schwa deletion)
        elif ch in VOWELS:
            res.append(VOWELS[ch])
        elif ch in MATRAS:
            res.append(MATRAS[ch])
        elif ch in SIGNS:
            res.append(SIGNS[ch])
        elif "०" <= ch <= "९":           # Devanagari digits
            res.append(str(ord(ch) - 0x0966))
        else:
            res.append(ch)
        i += 1
    out = "".join(res)
    # Hindi schwa deletion, simplified: drop a final inherent 'a' after a consonant
    if len(out) > 2 and out.endswith("a") and not out.endswith("aa") and w[-1] in CONS:
        out = out[:-1]
    return out


def has_indic(s):
    return any(0x0900 <= ord(c) <= 0x0D7F for c in s)


def has_arabic(s):
    """Urdu/Arabic script: an abjad, so it can't be romanised readably by rule."""
    return sum(0x0600 <= ord(c) <= 0x06FF for c in s) > 20


def romanise(text):
    if not has_indic(text):
        return text
    text = indic_to_devanagari(text)
    return re.sub(r"[\u0900-\u097F]+", lambda m: romanise_word(m.group(0)), text)


# typography the iPod fonts (U+0020..U+052F) don't have
ASCII_MAP = {"\u2018": "'", "\u2019": "'", "\u201A": "'", "\u201B": "'", "\u201C": '"', "\u201D": '"',
             "\u201E": '"', "\u2026": "...", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2010": "-",
             "\u2011": "-", "\u00A0": " ", "\u2009": " ", "\u200A": " ", "\u202F": " ", "\u205F": " ",
             "\u200B": "", "\u200C": "", "\u200D": "", "\uFEFF": "", "\u2022": "*",
             "\u266A": "*", "\u266B": "*", "\U0001F3B5": "*", "\U0001F3B6": "*", "\u060C": ",", "\u061F": "?"}
FONT_MAX = 0x052F  # many Rockbox fonts stop here (Latin, Greek, Cyrillic); stay safe


def clean_for_ipod(text):
    text = romanise(text)
    text = "".join(ASCII_MAP.get(c, c) for c in text)
    return "".join(c for c in text if ord(c) <= FONT_MAX or c == "\n")


TIMESTAMP = re.compile(r"^\[\d+:\d+(?:\.\d+)?\]", re.M)


def readable_synced(hit):
    """Synced lyrics that are timestamped and not in a script we can't romanise."""
    s = (hit or {}).get("syncedLyrics") or ""
    return bool(TIMESTAMP.search(s)) and not has_arabic(s)


# ---------------------------------------------------------------- main
def lyrics_rel(rel, clashes):
    """Where lrcplayer will find the lyrics for the song at drive-relative path rel."""
    folder, name = os.path.split(rel)
    stem = os.path.splitext(name)[0]
    if stem.lower() in clashes:                     # same file name elsewhere: keep it next to the song
        return os.path.join(folder, "Lyrics", stem + ".lrc8")
    return os.path.join("Lyrics", stem + ".lrc8")


def write_lrc(lrc_rel, text):
    out = os.path.join(OUT_ROOT, lrc_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def find_clashes(rels):
    seen = {}
    for r in rels:
        s = os.path.splitext(os.path.basename(r))[0].lower()
        seen[s] = seen.get(s, 0) + 1
    return {s for s, n in seen.items() if n > 1}


def load_log():
    done = {}
    if os.path.exists(LOG):
        with open(LOG, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                done[row["file"]] = row
    return done


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    music_root = os.path.abspath(sys.argv[1])
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    drive_root = os.path.splitdrive(music_root)[0] + os.sep        # E:\
    done = load_log()
    files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(music_root) for f in fs
                   if os.path.splitext(f)[1].lower() in AUDIO_EXT)
    clashes = find_clashes(os.path.relpath(p, drive_root) for p in files)
    new_log = not os.path.exists(LOG)
    logf = open(LOG, "a", newline="", encoding="utf-8")
    log = csv.DictWriter(logf, fieldnames=["file", "status", "how", "romanised", "title", "artist", "lrc"])
    if new_log:
        log.writeheader()
    session = requests.Session()
    counts = {}
    processed = 0
    for path in files:
        rel = os.path.relpath(path, drive_root)                          # Music\Album\Song.m4a
        if rel in done:
            counts[done[rel]["status"]] = counts.get(done[rel]["status"], 0) + 1
            continue
        if limit is not None and processed >= limit:
            break
        if not os.path.isdir(music_root):
            # the iPod dropped off USB: stop without logging, so a rerun resumes here
            print("music folder disappeared (iPod disconnected?) - stopping; rerun to resume", flush=True)
            break
        processed += 1
        try:
            t = read_tags(path)
        except mutagen.MutagenError:
            if not os.path.isdir(music_root):
                print("music folder disappeared (iPod disconnected?) - stopping; rerun to resume", flush=True)
                break
            t = None  # genuinely unreadable file: logged as "no tags"
        lrc_rel = lyrics_rel(rel, clashes)
        if not t or not t["title"]:
            status, how, roman = "no tags", "", ""
            write_lrc(lrc_rel, PLACEHOLDER)
        else:
            hit, how = find_synced(session, t)
            if not hit:
                status, roman = "not found", ""
                write_lrc(lrc_rel, PLACEHOLDER)
            else:
                lyrics = hit["syncedLyrics"]
                roman = "yes" if has_indic(lyrics) else ""
                lyrics = clean_for_ipod(lyrics)
                header = f"[ti:{t['title']}]\n[ar:{t['artist']}]\n[al:{t['album']}]\n"
                write_lrc(lrc_rel, clean_for_ipod(header) + lyrics.strip() + "\n")
                status = "saved"
        log.writerow({"file": rel, "status": status, "how": how, "romanised": roman,
                      "title": (t or {}).get("title", ""), "artist": (t or {}).get("artist", ""), "lrc": lrc_rel})
        logf.flush()
        counts[status] = counts.get(status, 0) + 1
        print(f"[{processed}] {status:9s} {rel}", flush=True)
    logf.close()
    print("summary:", counts)


if __name__ == "__main__":
    main()
