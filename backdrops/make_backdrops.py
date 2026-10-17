#!/usr/bin/env python3
"""
make_backdrops.py - Spotify-style "now playing" backgrounds for the Spotish Rockbox theme.

Spotify's phone player paints the whole screen in a soft glow taken from the album
cover. Rockbox can't do that by itself (a skin can't read colours from album art),
so this script does it once, on your computer: for every album on the iPod it draws a
320x240 picture - a dark, blurred glow made from the cover's own colours with the
rounded cover on top - and saves it next to the music as `cover.320x240.bmp`.

Rockbox looks for a cover file made for the exact size a theme asks for before it uses
the normal cover (apps/recorder/albumart.c), so Spotish finds these automatically and
shows them full screen. Your own cover.jpg / folder.jpg / embedded art is never changed.

    python make_backdrops.py                 # finds the iPod by itself
    python make_backdrops.py E:\\            # or point it at the iPod (or a music folder)
    python make_backdrops.py --dry-run       # only show what it would do
    python make_backdrops.py --force         # redo every album (e.g. after a theme update)
    python make_backdrops.py --remove        # delete everything this script made

Run it again after you add music; albums that are already done are skipped.
Needs Python 3.8+ and Pillow (`pip install pillow`). Albums whose art is only embedded
in the music files also need mutagen (`pip install mutagen`).

MIT licence - part of Spotish (https://github.com/owen-tariq/spotish-rockbox).
"""
import argparse
import colorsys
import glob
import hashlib
import io
import os
import string
import sys

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError:  # pragma: no cover - message for people running it by hand
    sys.exit("This script needs Pillow. Install it with:  pip install pillow")

try:
    import mutagen
except ImportError:
    mutagen = None

# ------------------------------------------------------------------ geometry
# Shared with src/gen_spotish.py (it imports these), so the cover baked into the
# background and the theme's layout can never disagree.
W, H = 320, 240
ART_X, ART_Y, ART_S = 16, 16, 132          # rounded cover, top left
ART_R = 6                                  # corner radius
SIZE_TAG = f".{W}x{H}"                     # Rockbox's size suffix: cover.320x240.bmp
OUT_NAME = f"cover{SIZE_TAG}.bmp"
MANIFEST = "spotish-backdrops.txt"

AUDIO_EXT = {".mp3", ".m4a", ".m4b", ".mp4", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wav",
             ".aif", ".aiff", ".wma", ".ape", ".wv", ".mpc", ".alac", ".spx", ".tta", ".mp2"}
# what Rockbox itself accepts as cover files (with JPEG support, as on the iPod)
IMG_EXT = (".jpg", ".jpeg", ".bmp")


# ------------------------------------------------------------------ colour
def _ss_mask(w, h, r, k=4):
    m = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r * k, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def palette(cover, n=8):
    """The cover's main colours, most 'Spotify-worthy' first: big areas of real colour
    beat big areas of black, white or grey. Returns [(r, g, b), ...]."""
    small = cover.convert("RGB").resize((64, 64), Image.BILINEAR)
    q = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:n * 3]
    counts = sorted(q.getcolors(), reverse=True)
    scored = []
    for count, idx in counts:
        rgb = tuple(pal[idx * 3:idx * 3 + 3])
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        # vivid, mid-bright colours score high; near-black and near-white low
        weight = (0.15 + s) * (0.25 + min(v, 1.0 - v * 0.5)) * (0.2 if v < 0.12 else 1.0)
        scored.append((count * weight, rgb))
    scored.sort(reverse=True)
    return [rgb for _, rgb in scored]


def _tone(rgb, value, sat_cap=0.85, sat_min=0.0):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    r, g, b = colorsys.hsv_to_rgb(h, max(sat_min, min(s, sat_cap)), value)
    return (round(r * 255), round(g * 255), round(b * 255))


def glow(cover):
    """Full-screen background: the cover's colours, laid out roughly where they sit in
    the cover, blurred into a soft glow and kept dark enough for white text."""
    c = cover.convert("RGB")
    cols = palette(c)
    lead = cols[0]

    # 1. colour field: a 4x3 summary of the cover keeps its layout (red on the left
    #    stays on the left), smoothed into a gradient
    field = c.resize((4, 3), Image.BOX).resize((W, H), Image.BICUBIC)
    field = field.filter(ImageFilter.GaussianBlur(24))
    field = ImageEnhance.Color(field).enhance(1.35)

    # 2. the lead colour glows out from behind the cover, like light spilling off it
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(blob)
    cx, cy = ART_X + ART_S * 0.5, ART_Y + ART_S * 1.0
    d.ellipse([cx - 110, cy - 80, cx + 110, cy + 80], fill=_tone(lead, 0.8, 0.9, 0.4) + (175,))
    if len(cols) > 1:      # a second colour low on the right, as in Spotify's ambient look
        d.ellipse([W - 170, H - 120, W + 40, H + 60], fill=_tone(cols[1], 0.6, 0.85) + (90,))
    blob = blob.filter(ImageFilter.GaussianBlur(45))
    field = field.convert("RGBA")
    field.alpha_composite(blob)
    field = field.convert("RGB")

    # 3. keep it dark: white text needs contrast. Scale down until the brightest part
    #    sits around a third of full brightness, and lift covers that are almost black.
    lum = field.convert("L")
    lo, hi = lum.getextrema()
    if hi > 104:
        field = ImageEnhance.Brightness(field).enhance(104 / hi)
    elif hi < 40:
        field = Image.blend(field, Image.new("RGB", (W, H), _tone(lead, 0.22)), 0.5)

    # 4. Spotify-style fade to near-black towards the controls
    shade = Image.new("L", (1, H))
    for y in range(H):
        t = y / (H - 1)
        shade.putpixel((0, y), round(255 * (0.05 + 0.6 * max(0.0, t - 0.25) / 0.75)))
    shade = shade.resize((W, H))
    field.paste(Image.new("RGB", (W, H), (10, 10, 10)), (0, 0), shade)
    return field


def compose(cover):
    """The finished 320x240 picture: glow + soft shadow + rounded cover."""
    img = glow(cover).convert("RGBA")
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [ART_X, ART_Y + 4, ART_X + ART_S - 1, ART_Y + ART_S + 3], radius=ART_R + 2, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    art = cover.convert("RGB").resize((ART_S, ART_S), Image.LANCZOS)
    img.paste(art, (ART_X, ART_Y), _ss_mask(ART_S, ART_S, ART_R))
    return img.convert("RGB")


def _square(img):
    """Covers that aren't square get centre-cropped, like Spotify does."""
    w, h = img.size
    if w == h:
        return img
    s = min(w, h)
    return img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))


# ------------------------------------------------------------------ finding art
def embedded_art(path):
    """Raw bytes of the first picture embedded in a music file, or None."""
    if mutagen is None:
        return None
    try:
        f = mutagen.File(path)
    except Exception:
        f = None
    if f is None:                                # mutagen couldn't tell the format: try plain ID3
        try:
            from mutagen.id3 import ID3
            f = type("F", (), {"tags": ID3(path)})()
        except Exception:
            return None
    tags = getattr(f, "tags", None)
    pics = getattr(f, "pictures", None)          # FLAC
    if pics:
        front = [p for p in pics if p.type == 3]
        return (front or pics)[0].data
    if tags is None:
        return None
    try:
        if hasattr(tags, "getall"):              # ID3 (mp3, aiff, wav)
            apic = tags.getall("APIC")
            if apic:
                front = [p for p in apic if p.type == 3]
                return (front or apic)[0].data
        if "covr" in tags:                       # MP4 / m4a
            return bytes(tags["covr"][0])
        for key in ("metadata_block_picture", "METADATA_BLOCK_PICTURE"):  # Ogg / Opus
            if key in tags:
                import base64
                from mutagen.flac import Picture
                return Picture(base64.b64decode(tags[key][0])).data
        for key in ("WM/Picture",):              # WMA
            if key in tags:
                raw = tags[key][0].value
                # WM/Picture: type(1) size(4) mime(utf16z) desc(utf16z) data
                i = 5
                for _ in range(2):
                    while raw[i:i + 2] != b"\x00\x00":
                        i += 2
                    i += 2
                return raw[i:]
    except Exception:
        return None
    return None


def first_image(folder, names):
    for n in names:
        for ext in IMG_EXT:
            for cand in (n + ext, n + ext.upper()):
                p = os.path.join(folder, cand)
                if os.path.isfile(p):
                    return p
    return None


def open_image(src):
    try:
        im = Image.open(io.BytesIO(src) if isinstance(src, bytes) else src)
        im.load()
        return im
    except Exception:
        return None


def plan_folder(folder, tracks):
    """What to make for one folder of music, following the order Rockbox uses when
    "album art: prefer image file" is on. Returns [(output_path, source, mtime)]."""
    jobs = []
    leftover = []
    # track-specific image files (<track>.jpg) win first
    for t in tracks:
        base = os.path.splitext(t)[0]
        img = first_image(folder, [os.path.basename(base)])
        if img:
            jobs.append((base + SIZE_TAG + ".bmp", img, os.path.getmtime(img)))
        else:
            leftover.append(t)
    if not leftover:
        return jobs
    # then the folder's own cover, then the parent's (multi-disc albums)
    parent = os.path.dirname(folder.rstrip("\\/"))
    img = first_image(folder, ["cover", "folder", "Cover", "Folder"]) or \
        (first_image(parent, ["cover", "Cover"]) if parent and parent != folder else None)
    if img:
        jobs.append((os.path.join(folder, OUT_NAME), img, os.path.getmtime(img)))
        return jobs
    # then art embedded in the files: one picture for the whole folder when they
    # all share it, otherwise one per track
    arts = {}
    for t in leftover:
        data = embedded_art(t)
        if data:
            arts.setdefault(hashlib.sha1(data).hexdigest(), [data, []])[1].append(t)
    if len(arts) == 1:
        data, ts = next(iter(arts.values()))
        jobs.append((os.path.join(folder, OUT_NAME), data, max(os.path.getmtime(t) for t in ts)))
    else:
        for data, ts in arts.values():
            for t in ts:
                jobs.append((os.path.splitext(t)[0] + SIZE_TAG + ".bmp", data, os.path.getmtime(t)))
    return jobs


def music_folders(root):
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))   # skips .rockbox, .Trashes...
        tracks = sorted(os.path.join(folder, f) for f in files
                        if os.path.splitext(f)[1].lower() in AUDIO_EXT and not f.startswith("._"))
        if tracks:
            yield folder, tracks


# ------------------------------------------------------------------ the iPod
def find_ipods():
    """Mounted drives that have a .rockbox folder."""
    cands = []
    if os.name == "nt":
        cands = [f"{c}:\\" for c in string.ascii_uppercase[2:]]
    else:
        user = os.environ.get("USER", "*")
        for pat in ("/Volumes/*", f"/media/{user}/*", "/media/*", f"/run/media/{user}/*", "/mnt/*"):
            cands += glob.glob(pat)
    seen, hits = set(), []
    for c in cands:
        try:
            if os.path.isdir(os.path.join(c, ".rockbox")):
                real = os.path.realpath(c)
                if real not in seen:
                    seen.add(real)
                    hits.append(c)
        except OSError:
            pass
    return hits


def manifest_path(root):
    rb = os.path.join(root, ".rockbox")
    return os.path.join(rb if os.path.isdir(rb) else root, MANIFEST)


def read_manifest(root):
    p = manifest_path(root)
    if not os.path.isfile(p):
        return set()
    with open(p, encoding="utf-8") as fh:
        return {line.rstrip("\n") for line in fh if line.strip() and not line.startswith("#")}


def write_manifest(root, entries):
    with open(manifest_path(root), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# files made by Spotish make_backdrops.py - `--remove` deletes exactly these\n")
        for e in sorted(entries):
            fh.write(e + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make Spotify-style Now Playing backgrounds for the Spotish Rockbox theme.")
    ap.add_argument("path", nargs="?", help="the iPod (e.g. E:\\ or /Volumes/IPOD) or a music folder; found automatically if left out")
    ap.add_argument("--dry-run", action="store_true", help="only list what would be made")
    ap.add_argument("--force", action="store_true", help="remake albums that are already done")
    ap.add_argument("--remove", action="store_true", help="delete every file this script made")
    a = ap.parse_args(argv)

    root = a.path
    if not root:
        found = find_ipods()
        if len(found) == 1:
            root = found[0]
            print(f"Found the iPod at {root}")
        elif not found:
            sys.exit("Couldn't find an iPod with Rockbox. Plug it in (disk mode), or give the path, e.g.\n"
                     "  python make_backdrops.py E:\\\n  python make_backdrops.py /Volumes/IPOD")
        else:
            sys.exit("More than one Rockbox drive is connected - say which one:\n  " + "\n  ".join(found))
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")

    made = read_manifest(root)

    if a.remove:
        n = 0
        for rel in sorted(made):
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                if not a.dry_run:
                    os.remove(p)
                n += 1
        if not a.dry_run and os.path.isfile(manifest_path(root)):
            os.remove(manifest_path(root))
        print(f"{'Would remove' if a.dry_run else 'Removed'} {n} background file(s).")
        return 0

    stats = dict(made=0, skipped=0, kept=0, noart=0, bad=0)
    need_mutagen = False
    for folder, tracks in music_folders(root):
        jobs = plan_folder(folder, tracks)
        if not jobs:
            stats["noart"] += 1
            if mutagen is None:
                need_mutagen = True
            continue
        for out, src, mtime in jobs:
            rel = os.path.relpath(out, root).replace("\\", "/")
            exists = os.path.isfile(out)
            if exists and rel not in made and not a.force:
                stats["kept"] += 1          # someone else's file with this name: leave it alone
                continue
            if exists and not a.force and os.path.getmtime(out) >= mtime:
                stats["skipped"] += 1
                continue
            label = os.path.relpath(out, root)
            if a.dry_run:
                print(f"would make  {label}")
                stats["made"] += 1
                continue
            im = open_image(src)
            if im is None:
                print(f"can't read the cover for {os.path.relpath(folder, root)} - skipped")
                stats["bad"] += 1
                continue
            compose(_square(im)).save(out, "BMP")
            made.add(rel)
            stats["made"] += 1
            print(f"made  {label}")

    if not a.dry_run:
        write_manifest(root, made)
    print()
    print(f"{'Would make' if a.dry_run else 'Made'} {stats['made']} background(s); "
          f"{stats['skipped']} already up to date; {stats['noart']} folder(s) without art.")
    if stats["kept"]:
        print(f"{stats['kept']} existing {OUT_NAME} file(s) weren't made by this script and were left alone (use --force to replace them).")
    if stats["bad"]:
        print(f"{stats['bad']} cover(s) couldn't be read.")
    if need_mutagen:
        print("Some folders have no cover file; to use art embedded in the songs, install mutagen:  pip install mutagen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
