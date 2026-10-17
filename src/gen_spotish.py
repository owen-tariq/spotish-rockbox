"""
Spotish - a Spotify desktop-player style Rockbox theme for the iPod Video 5 / 5.5G (320x240).

Now Playing ("concept A"): a rounded "Song" card on black - teal header with album
art, a small "Song" label, big bold title and "artist - year - length", then the
green play button with add / download / more icons and "Next in queue" - above
the desktop player bar (shuffle, prev, white round play/pause, next, repeat, and
the progress line with times on both sides). Changing the volume swaps the
progress line for a volume line.

Menus: the "Your Library" panel - a rounded dark card with a bold title and the
list - above a black mini player (art, title, artist, play/pause, progress).

Original artwork in Spotify's style; no Spotify logos or assets.

Generates every bitmap and the WPS / SBS / theme .cfg from one set of layout
constants, so graphics and skin coordinates can never drift apart.

    python gen_spotish.py        -> writes ./build/.rockbox/... and ./preview/
"""
import os
import shutil
import struct
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 320, 240
# `--name X` builds the same theme under another name (own skin files, image folder
# and .cfg) into build-X/, e.g. to try it next to an installed copy.
NAME = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else "Spotish"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # repository root
OUT = os.path.join(ROOT, "build" if NAME == "Spotish" else f"build-{NAME}", ".rockbox")
IMG_DIR = os.path.join(OUT, "wps", NAME)
FNT_DIR = os.path.join(ROOT, "fonts")              # prebuilt Rockbox fonts (Inter, OFL)
sys.path.insert(0, HERE)
from rbdevice import match_backdrop, device_view, RbFont  # noqa: E402  (RGB565 emulation)

# Inter (SIL Open Font License) for text baked into bitmaps and for the mockups
FONT_DIR = os.path.join(HERE, "fonts")
BOLD_FONT = os.path.join(FONT_DIR, "Inter-Bold.ttf")
SEMI_FONT = os.path.join(FONT_DIR, "Inter-SemiBold.ttf")
BODY_FONT = os.path.join(FONT_DIR, "Inter-Regular.ttf")


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


GREEN, GREY, TRACK, CARD = hx("1ED760"), hx("B3B3B3"), hx("4D4D4D"), hx("121212")
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
TEAL_TOP, TEAL_BOT = hx("26828E"), hx("14525C")       # song header
TEAL_FADE = hx("133C42")                               # lower card starts here, fades to CARD
SEL_BG, SEL_FG = GREEN, BLACK                          # list selection: Spotify green, black text

# line heights of the bundled fonts, read from their .fnt headers ("RB12" format)
def _fnt_height(name):
    with open(os.path.join(FNT_DIR, name), "rb") as fh:
        head = fh.read(12)
    assert head[:4] == b"RB12", name
    return struct.unpack("<HHHH", head[4:12])[1]


FH = {f: _fnt_height(f) for f in os.listdir(FNT_DIR) if f.endswith(".fnt")}

# ================================================================ Now Playing layout
CARD_X, CARD_Y, CARD_W, CARD_H = 4, 4, 312, 174      # the "Song" card
HEAD_H = 92                                          # teal header part of the card
ART_X, ART_Y, ART_S = 14, 14, 72
INFO_X = ART_X + ART_S + 10                          # 96
INFO_W = CARD_X + CARD_W - 10 - INFO_X               # 210
SONG_LABEL_Y = 18
TITLE_Y = 28                                         # 28-Spotish-InterDisplay-Bold, 29 px line
META_Y = 62                                          # 13-Spotish-Inter-SemiBold, 14 px line
LOCK_X, LOCK_Y, LOCK_S = CARD_X + CARD_W - 20, 10, 12

PLAY_X, PLAY_Y, PLAY_D = 14, 98, 34                  # green play button
ACT_Y, ACT_S = 105, 20                               # add / download / more icons
ACT_XS = (60, 88, 116)
NEXT_HEAD_Y = 138                                    # "Next in queue", 15-Spotish-Inter-Bold
NEXT_Y = 158                                         # next track, 13-Spotish-Inter-SemiBold

BAR_Y = CARD_Y + CARD_H + 2                          # 180, black player bar
CTRL_CY = BAR_Y + 16                                 # controls centre line
SM = 16                                              # small control icon
SM_Y = CTRL_CY - SM // 2
TILE_H = SM + 6                                      # icon + gap + "active" dot
SHUF_X, PREV_X, NEXT_X, REP_X = 76, 114, 190, 228
PP_D = 26
PP_X, PP_Y = (W - PP_D) // 2, CTRL_CY - PP_D // 2

PROG_CY = BAR_Y + 41                                 # times + progress line centre
PB_X, PB_W, PB_H = 50, 220, 10
PB_Y = PROG_CY - PB_H // 2
LINE_H = 4
TIME_H = FH["13-Spotish-Inter-SemiBold.fnt"]
TIME_Y = PROG_CY - TIME_H // 2
SPK_S = 14                                           # volume speaker (replaces elapsed time)
SPK_X, SPK_Y = PB_X - 8 - SPK_S, PROG_CY - SPK_S // 2

# ================================================================ menu (sbs) layout
LIB_X, LIB_Y, LIB_W, LIB_H = 4, 4, 312, 182          # "Your Library" card
# Card header ("status bar") style:
#   "A" small grey clock + battery % in the card corner
#   "C" white clock + battery icon at title size, thin divider under the header
STATUS_STYLE = "C"
LT_Y = 10                                            # 20-Spotish-Inter-Bold title
LT_CY = LT_Y + FH["20-Spotish-Inter-Bold.fnt"] // 2  # header centre line
HDR_DIV_Y = LIB_Y + 33                               # style C divider
LIST_Y = 40 if STATUS_STYLE == "C" else 38
LIST_H = LIB_Y + LIB_H - 4 - LIST_Y                  # 7 rows of 20 px
BATT_W, BATT_H = 22, 11                              # style C battery icon
BATT_X = LIB_X + LIB_W - 12 - BATT_W
BATT_Y = LT_CY - BATT_H // 2
CLK_X = 200
CLK_W = BATT_X - 8 - CLK_X
CLK_Y = LT_CY - FH["16-Spotish-Inter-SemiBold.fnt"] // 2
MINI_Y = LIB_Y + LIB_H + 2                           # 188, black mini player
MART = 40
MART_X, MART_Y = 8, MINI_Y + 6
MTXT_X = MART_X + MART + 8
MPP_D = 26
MPP_X, MPP_Y = W - 6 - MPP_D, MINI_Y + 8
MADD_S = 16
MADD_X, MADD_Y = MPP_X - 10 - MADD_S, MPP_Y + (MPP_D - MADD_S) // 2
MTXT_W = MADD_X - 6 - MTXT_X
MPB_X, MPB_Y, MPB_W, MPB_H = 8, H - 4, W - 16, 2


# ---------------------------------------------------------------- helpers
def lerp(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(img, box, top, bot):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        d.line([(x0, y), (x1 - 1, y)], fill=lerp(top, bot, (y - y0) / max(1, y1 - y0 - 1)))


def font(path, size):
    return ImageFont.truetype(path, size)


def crop(img, x, y, w, h):
    return img.crop((x, y, x + w, y + h)).convert("RGB")


def ss(w, h, painter, k=4):
    """Supersampled RGBA layer: painter(draw, w*k, h*k)."""
    big = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    painter(ImageDraw.Draw(big), w * k, h * k)
    return big.resize((w, h), Image.LANCZOS)


def over(bg, x, y, layer):
    tile = crop(bg, x, y, layer.width, layer.height).convert("RGBA")
    tile.alpha_composite(layer)
    return tile.convert("RGB")


def put(img, x, y, layer):
    img.paste(layer, (x, y), layer)


def stack(tiles):
    out = Image.new("RGB", (tiles[0].width, sum(t.height for t in tiles)))
    y = 0
    for t in tiles:
        out.paste(t, (0, y))
        y += t.height
    return out


def rgba(c, a=255):
    return tuple(c) + (a,)


def rounded_card(img, x, y, w, h, fill_img):
    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=8 * 4, fill=255)
    img.paste(fill_img, (x, y), m.resize((w, h), Image.LANCZOS))


# ---------------------------------------------------------------- icons (painter(d, w, h))
def i_play(col):
    return lambda d, w, h: d.polygon([(w * .3, h * .18), (w * .3, h * .82), (w * .84, h * .5)], fill=col)


def i_pause(col):
    def p(d, w, h):
        d.rounded_rectangle([w * .26, h * .2, w * .42, h * .8], radius=w * .03, fill=col)
        d.rounded_rectangle([w * .58, h * .2, w * .74, h * .8], radius=w * .03, fill=col)
    return p


def i_prev(col):
    def p(d, w, h):
        d.rounded_rectangle([w * .16, h * .16, w * .27, h * .84], radius=w * .03, fill=col)
        d.polygon([(w * .86, h * .16), (w * .3, h * .5), (w * .86, h * .84)], fill=col)
    return p


def i_next(col):
    def p(d, w, h):
        d.polygon([(w * .14, h * .16), (w * .7, h * .5), (w * .14, h * .84)], fill=col)
        d.rounded_rectangle([w * .73, h * .16, w * .84, h * .84], radius=w * .03, fill=col)
    return p


def i_shuffle(col):
    def p(d, w, h):
        lw = max(2, round(w * .085))
        d.line([(w * .05, h * .3), (w * .28, h * .3), (w * .6, h * .7), (w * .78, h * .7)], fill=col, width=lw)
        d.line([(w * .05, h * .7), (w * .28, h * .7), (w * .6, h * .3), (w * .78, h * .3)], fill=col, width=lw)
        for yy in (.3, .7):
            d.polygon([(w * .76, h * (yy - .13)), (w * .95, h * yy), (w * .76, h * (yy + .13))], fill=col)
    return p


def i_repeat(col, badge=None):
    def p(d, w, h):
        lw = max(2, round(w * .085))
        d.rounded_rectangle([w * .08, h * .26, w * .92, h * .76], radius=w * .17, outline=col, width=lw)
        d.rectangle([w * .5, h * .16, w * .66, h * .36], fill=(0, 0, 0, 0))
        d.polygon([(w * .46, h * .1), (w * .68, h * .26), (w * .46, h * .42)], fill=col)
        if badge:  # Spotify's repeat-one: small filled circle with the digit
            r = w * .2
            d.ellipse([w * .5 - r, h * .51 - r, w * .5 + r, h * .51 + r], fill=col)
            f = font(BOLD_FONT, int(w * (.3 if len(badge) == 1 else .2)))
            d.text((w * .5, h * .51), badge, font=f, fill=rgba(BLACK), anchor="mm")
    return p


def i_plus_circle(col):
    def p(d, w, h):
        lw = max(2, round(w * .07))
        d.ellipse([lw, lw, w - lw, h - lw], outline=col, width=lw)
        d.line([(w * .3, h * .5), (w * .7, h * .5)], fill=col, width=lw)
        d.line([(w * .5, h * .3), (w * .5, h * .7)], fill=col, width=lw)
    return p


def i_down_circle(col):
    def p(d, w, h):
        lw = max(2, round(w * .07))
        d.ellipse([lw, lw, w - lw, h - lw], outline=col, width=lw)
        d.line([(w * .5, h * .26), (w * .5, h * .68)], fill=col, width=lw)
        d.line([(w * .32, h * .52), (w * .5, h * .7), (w * .68, h * .52)], fill=col, width=lw, joint="curve")
    return p


def i_dots(col):
    def p(d, w, h):
        for cx in (.22, .5, .78):
            d.ellipse([w * cx - w * .07, h * .43, w * cx + w * .07, h * .57], fill=col)
    return p


def i_speaker(col):
    def p(d, w, h):
        lw = max(2, round(w * .085))
        d.rounded_rectangle([w * .04, h * .36, w * .26, h * .64], radius=w * .04, fill=col)
        d.polygon([(w * .24, h * .36), (w * .5, h * .12), (w * .5, h * .88), (w * .24, h * .64)], fill=col)
        for r in (.15, .3):
            d.arc([w * (.52 - r), h * (.5 - r), w * (.52 + r), h * (.5 + r)], -48, 48, fill=col, width=lw)
    return p


def i_lock(col):
    def p(d, w, h):
        lw = max(2, round(w * .1))
        d.arc([w * .28, h * .06, w * .72, h * .56], 180, 360, fill=col, width=lw)
        d.line([(w * .28, h * .3), (w * .28, h * .46)], fill=col, width=lw)
        d.line([(w * .72, h * .3), (w * .72, h * .46)], fill=col, width=lw)
        d.rounded_rectangle([w * .18, h * .44, w * .82, h * .94], radius=w * .08, fill=col)
    return p


def i_note(col):
    def p(d, w, h):
        q = w / 88
        d.ellipse([18 * q, 54 * q, 38 * q, 70 * q], fill=col)
        d.ellipse([50 * q, 48 * q, 70 * q, 64 * q], fill=col)
        d.rectangle([33 * q, 22 * q, 38 * q, 63 * q], fill=col)
        d.rectangle([65 * q, 16 * q, 70 * q, 57 * q], fill=col)
        d.polygon([(33 * q, 22 * q), (70 * q, 14 * q), (70 * q, 24 * q), (33 * q, 32 * q)], fill=col)
    return p


def icon(s, painter):
    return ss(s, s, painter)


def circle_button(dia, bg, glyph, gcol):
    layer = ss(dia, dia, lambda d, w, h: d.ellipse([0, 0, w - 1, h - 1], fill=rgba(bg)))
    g = dia // 2
    nudge = 1 if glyph is i_play else 0  # optical centring of the triangle
    layer.alpha_composite(icon(g, glyph(rgba(gcol))), ((dia - g) // 2 + nudge, (dia - g) // 2))
    return layer


def mode_tile(painter, active):
    """Control icon with Spotify's little green 'active' dot under it."""
    layer = Image.new("RGBA", (SM, TILE_H), (0, 0, 0, 0))
    layer.alpha_composite(icon(SM, painter))
    if active:
        layer.alpha_composite(ss(SM, 4, lambda d, w, h: d.ellipse(
            [w / 2 - 1.6 * 4, 0, w / 2 + 1.6 * 4, h - 1], fill=rgba(GREEN))), (0, SM + 2))
    return layer


def line_track(bg, x, y, w, h, col, th):
    def p(d, ww, hh):
        t = th * 4
        top = (hh - t) / 2
        d.rounded_rectangle([0, top, ww - 1, top + t - 1], radius=t / 2, fill=rgba(col))
    return over(bg, x, y, ss(w, h, p))


def no_art(s):
    img = Image.new("RGBA", (s, s), rgba(hx("282828")))
    img.alpha_composite(ss(s, s, i_note(rgba(hx("7F7F7F")))))
    return img.convert("RGB")


# ---------------------------------------------------------------- backdrops
def wps_backdrop():
    img = Image.new("RGB", (W, H), BLACK)
    card = Image.new("RGB", (CARD_W, CARD_H))
    vgrad(card, (0, 0, CARD_W, HEAD_H), TEAL_TOP, TEAL_BOT)
    vgrad(card, (0, HEAD_H, CARD_W, CARD_H), TEAL_FADE, CARD)
    rounded_card(img, CARD_X, CARD_Y, CARD_W, CARD_H, card)
    # album art shadow
    sh = ss(ART_S + 10, ART_S + 10, lambda d, w, h: d.rectangle([8, 14, w - 2, h - 2], fill=(0, 0, 0, 110)))
    put(img, ART_X - 2, ART_Y, sh.filter(ImageFilter.GaussianBlur(2.5)))
    d = ImageDraw.Draw(img)
    d.text((INFO_X, SONG_LABEL_Y), "Song", font=font(SEMI_FONT, 11), fill=WHITE)
    for x, p in zip(ACT_XS, (i_plus_circle, i_down_circle, i_dots)):
        put(img, x, ACT_Y, icon(ACT_S, p(rgba(GREY))))
    put(img, PREV_X, SM_Y, icon(SM, i_prev(rgba(GREY))))
    put(img, NEXT_X, SM_Y, icon(SM, i_next(rgba(GREY))))
    return img


def sbs_backdrop():
    img = Image.new("RGB", (W, H), BLACK)
    rounded_card(img, LIB_X, LIB_Y, LIB_W, LIB_H, Image.new("RGB", (LIB_W, LIB_H), CARD))
    put(img, MADD_X, MADD_Y, icon(MADD_S, i_plus_circle(rgba(GREY))))
    if STATUS_STYLE == "C":
        ImageDraw.Draw(img).line([(LIB_X + 10, HDR_DIV_Y), (LIB_X + LIB_W - 10, HDR_DIV_Y)], fill=hx("2A2A2A"))
    return img


def battery_icon(full):
    """White battery outline + nub; `full` adds the whole inner bar (the %bl image
    bar reveals it from the left, so the outline must be identical in both)."""
    def p(d, w, h):
        k = 4
        d.rounded_rectangle([k, k, w - 4 * k, h - k], radius=2.5 * k, outline=rgba(WHITE), width=k)
        d.rectangle([w - 4 * k, h * .32, w - 1, h * .68], fill=rgba(WHITE))
        if full:
            d.rounded_rectangle([3 * k, 3 * k, w - 6 * k, h - 3 * k], radius=k, fill=rgba(WHITE))
    return ss(BATT_W, BATT_H, p)


# ---------------------------------------------------------------- build images
def save(img, name):
    os.makedirs(IMG_DIR, exist_ok=True)
    img.convert("RGB").save(os.path.join(IMG_DIR, name), "BMP")


def build_images():
    wps, sbs = wps_backdrop(), sbs_backdrop()
    save(wps, "wps_backdrop.bmp")
    save(sbs, "sbs_backdrop.bmp")

    # Everything cut out of a backdrop goes through match_backdrop(): Rockbox
    # dithers the backdrop but not these, so without it they'd show as tinted patches.
    mw = lambda layer, x, y: match_backdrop(over(wps, x, y, layer), wps, x, y)
    ms = lambda layer, x, y: match_backdrop(over(sbs, x, y, layer), sbs, x, y)

    # green play button in the card: stop -> play, play -> pause, pause -> play
    save(stack([mw(circle_button(PLAY_D, GREEN, g, BLACK), PLAY_X, PLAY_Y) for g in (i_play, i_pause)]), "play_big.bmp")
    # white play/pause in the player bar
    save(stack([mw(circle_button(PP_D, WHITE, g, BLACK), PP_X, PP_Y) for g in (i_play, i_pause)]), "pp.bmp")
    # shuffle: off, on ; repeat: off, all, one, A-B
    save(stack([mw(mode_tile(i_shuffle(rgba(GREY)), False), SHUF_X, SM_Y),
                mw(mode_tile(i_shuffle(rgba(GREEN)), True), SHUF_X, SM_Y)]), "shuffle.bmp")
    save(stack([mw(mode_tile(i_repeat(rgba(GREY)), False), REP_X, SM_Y),
                mw(mode_tile(i_repeat(rgba(GREEN)), True), REP_X, SM_Y),
                mw(mode_tile(i_repeat(rgba(GREEN), "1"), True), REP_X, SM_Y),
                mw(mode_tile(i_repeat(rgba(GREEN), "AB"), True), REP_X, SM_Y)]), "repeat.bmp")
    save(mw(icon(LOCK_S, i_lock(rgba(hx("D8E6E8")))), LOCK_X, LOCK_Y), "lock.bmp")

    # progress line (white on grey) and the volume line that replaces it
    save(match_backdrop(line_track(wps, PB_X, PB_Y, PB_W, PB_H, WHITE, LINE_H), wps, PB_X, PB_Y), "pb_fill.bmp")
    save(match_backdrop(line_track(wps, PB_X, PB_Y, PB_W, PB_H, TRACK, LINE_H), wps, PB_X, PB_Y), "pb_back.bmp")
    save(mw(icon(SPK_S, i_speaker(rgba(WHITE))), SPK_X, SPK_Y), "speaker.bmp")

    save(no_art(ART_S), "noart.bmp")
    save(no_art(MART), "noart_small.bmp")

    if STATUS_STYLE == "C":
        save(ms(battery_icon(True), BATT_X, BATT_Y), "bat_fill.bmp")
        save(ms(battery_icon(False), BATT_X, BATT_Y), "bat_back.bmp")

    # mini player (menus)
    save(stack([ms(circle_button(MPP_D, WHITE, g, BLACK), MPP_X, MPP_Y) for g in (i_play, i_pause)]), "mini_pp.bmp")
    save(match_backdrop(line_track(sbs, MPB_X, MPB_Y, MPB_W, MPB_H, WHITE, MPB_H), sbs, MPB_X, MPB_Y), "mini_pb_fill.bmp")
    save(match_backdrop(line_track(sbs, MPB_X, MPB_Y, MPB_W, MPB_H, TRACK, MPB_H), sbs, MPB_X, MPB_Y), "mini_pb_back.bmp")
    return wps, sbs


# ---------------------------------------------------------------- skins
WPS_FONTS = {2: "28-Spotish-InterDisplay-Bold.fnt", 3: "13-Spotish-Inter-SemiBold.fnt", 4: "15-Spotish-Inter-Bold.fnt"}
SBS_FONTS = {2: "20-Spotish-Inter-Bold.fnt", 3: "13-Spotish-Inter-SemiBold.fnt", 4: "16-Spotish-Inter-SemiBold.fnt"}
LIST_FONT = "19-Spotish-Inter-Medium.fnt"
VOL_POPUP_SECS = 1.2  # how long the volume line stays after the last change (musicOS_v2 uses 1.2)


def bar(tag, x, y, w, h, fill_label, back_label):
    # The fill must be a %xl label, not a file name: Rockbox creates file-name bar
    # images without setting their dither flag, so they load unpredictably.
    return f"%{tag}({x},{y},{w},{h},image,{fill_label},backdrop,{back_label})"


def fonts_block(fonts):
    return "\n".join(f"%Fl({i},{f})" for i, f in fonts.items())


def write_wps():
    s = f"""# ==================================================
# {NAME} - Now Playing
# Spotify desktop-player style, iPod Video 320x240
# generated by gen_spotish.py - edit the generator, not this file
# ==================================================

%wd

# ---- preloads
%xl(PbFill,pb_fill.bmp,0,0)
%xl(PbBack,pb_back.bmp,0,0)
%xl(PlayBig,play_big.bmp,0,0,2)
%xl(PP,pp.bmp,0,0,2)
%xl(Shuf,shuffle.bmp,0,0,2)
%xl(Rep,repeat.bmp,0,0,4)
%xl(Spk,speaker.bmp,0,0)
%xl(Lock,lock.bmp,0,0)
%xl(NoArt,noart.bmp,0,0)

{fonts_block(WPS_FONTS)}

# ---- logic: lives in the implicit default viewport, which is evaluated but
# never drawn or cleared (same as musicOS_v2). Putting it in a full-screen %V
# makes every refresh of these lines wipe screen bands -> flicker.
# Times + progress line, or the volume line while the volume changes.
%?mv({VOL_POPUP_SECS})<%Vd(vol)|%Vd(prog)>

# ---- backdrop: %X gives this skin its own backdrop buffer. (Every %VB
# backdrop shares ONE buffer named #backdrop_buffer#, so the menu and Now
# Playing skins overwrote each other and text boxes showed solid colour.)
%X(wps_backdrop.bmp)

# ---- song card: art, title, artist / year / length
%V({ART_X},{ART_Y},{ART_S},{ART_S},-)
%Cl(0,0,{ART_S},{ART_S},c,c)
%?C<%Cd|%xd(NoArt)>

%V({INFO_X},{TITLE_Y},{INFO_W},{FH['28-Spotish-InterDisplay-Bold.fnt']},2)
%Vf(FFFFFF)
%Vb(1F6D78)
%s%?it<%it|%fn>

%V({INFO_X},{META_Y},{INFO_W},{FH['13-Spotish-Inter-SemiBold.fnt']},3)
%Vf(E1EBEC)
%Vb(1A5F69)
%s%?ia<%ia|Unknown artist>%?iy< \u2022 %iy|> \u2022 %pt

%V({LOCK_X},{LOCK_Y},{LOCK_S},{LOCK_S},-)
%?mh<%xd(Lock)|>

# ---- green play button (shows the action: play when stopped/paused)
# (%?mp order is stop|play|pause|ffwd|rew)
%V({PLAY_X},{PLAY_Y},{PLAY_D},{PLAY_D},-)
%?mp<%xd(PlayBig,1)|%xd(PlayBig,2)|%xd(PlayBig,1)|%xd(PlayBig,2)|%xd(PlayBig,2)>

# ---- next in queue
%V(14,{NEXT_HEAD_Y},{CARD_W - 20},{FH['15-Spotish-Inter-Bold.fnt']},4)
%Vf(FFFFFF)
%Vb(141E20)
%?It<Next in queue|>

%V(14,{NEXT_Y},{CARD_W - 20},{FH['13-Spotish-Inter-SemiBold.fnt']},3)
%Vf(B3B3B3)
%Vb(131719)
%s%?It<%It%?Ia< - %Ia|>|>

# ---- player bar: shuffle, (prev), play/pause, (next), repeat
# (%?mm order is off|all|one|shuffle|ab)
%V({SHUF_X},{SM_Y},{SM},{TILE_H},-)
%?ps<%xd(Shuf,2)|%xd(Shuf,1)>

%V({PP_X},{PP_Y},{PP_D},{PP_D},-)
%?mp<%xd(PP,1)|%xd(PP,2)|%xd(PP,1)|%xd(PP,2)|%xd(PP,2)>

%V({REP_X},{SM_Y},{SM},{TILE_H},-)
%?mm<%xd(Rep,1)|%xd(Rep,2)|%xd(Rep,3)|%xd(Rep,2)|%xd(Rep,4)>

# ---- progress row: elapsed | line | length
%Vl(prog,4,{TIME_Y},{PB_X - 10},{TIME_H},3)
%Vf(B3B3B3)
%Vb(000000)
%ar%pc

%Vl(prog,{PB_X},{PB_Y},{PB_W},{PB_H},-)
{bar('pb', 0, 0, PB_W, PB_H, 'PbFill', 'PbBack')}

%Vl(prog,{PB_X + PB_W + 6},{TIME_Y},{W - PB_X - PB_W - 10},{TIME_H},3)
%Vf(B3B3B3)
%Vb(000000)
%al%pt

# ---- volume row: speaker | line
%Vl(vol,{SPK_X},{SPK_Y},{SPK_S},{SPK_S},-)
%xd(Spk)

%Vl(vol,{PB_X},{PB_Y},{PB_W},{PB_H},-)
{bar('pv', 0, 0, PB_W, PB_H, 'PbFill', 'PbBack')}
"""
    with open(os.path.join(OUT, "wps", f"{NAME}.wps"), "w", newline="\n", encoding="utf-8") as fh:
        fh.write(s)


def write_sbs():
    if STATUS_STYLE == "C":
        status_preload = "%xl(BatFill,bat_fill.bmp,0,0)\n%xl(BatBack,bat_back.bmp,0,0)\n"
        status = f"""%V({CLK_X},{CLK_Y},{CLK_W},{FH['16-Spotish-Inter-SemiBold.fnt']},4)
%Vf(FFFFFF)
%Vb(121212)
%ar%cH:%cM

%V({BATT_X},{BATT_Y},{BATT_W},{BATT_H},-)
{bar('bl', 0, 0, BATT_W, BATT_H, 'BatFill', 'BatBack')}"""
    else:
        status_preload = ""
        status = f"""%V(214,{LT_Y + 4},{LIB_X + LIB_W - 10 - 214},{FH['13-Spotish-Inter-SemiBold.fnt']},3)
%Vf(B3B3B3)
%Vb(121212)
%ar%cH:%cM  %bl%"""
    s = f"""# ==================================================
# {NAME} - menus / lists with mini player (status bar skin)
# Spotify desktop "Your Library" style, iPod Video 320x240
# generated by gen_spotish.py - edit the generator, not this file
# ==================================================

# ---- preloads
%xl(MiniFill,mini_pb_fill.bmp,0,0)
%xl(MiniBack,mini_pb_back.bmp,0,0)
%xl(MiniPP,mini_pp.bmp,0,0,2)
%xl(NoArtS,noart_small.bmp,0,0)
{status_preload}
{fonts_block(SBS_FONTS)}

# ---- backdrop: own buffer via %X (see the .wps for why not %VB)
%X(sbs_backdrop.bmp)

# ---- list area inside the library card
%Vi(Menu,8,{LIST_Y},{W - 16},{LIST_H},-)
%Vf(FFFFFF)
%Vb(121212)

# ---- logic: in a 1x1 corner viewport so redrawing it can't wipe anything
# (same trick as musicOS_v2's sbs)
%V(319,239,1,1,-)
%VI(Menu)

# ---- library card header: screen title, clock + battery
%V(14,{LT_Y},{(CLK_X if STATUS_STYLE == "C" else 214) - 6 - 14},{FH['20-Spotish-Inter-Bold.fnt']},2)
%Vf(FFFFFF)
%Vb(121212)
%s%?Lt<%Lt|Your Library>

{status}

# ---- mini player
%V({MART_X},{MART_Y},{MART},{MART},-)
%Cl(0,0,{MART},{MART},c,c)
%?C<%Cd|%xd(NoArtS)>

# (%?mp order is stop|play|pause|ffwd|rew)
%V({MTXT_X},{MART_Y + 1},{MTXT_W},{FH['16-Spotish-Inter-SemiBold.fnt']},4)
%Vf(FFFFFF)
%Vb(000000)
%s%?mp<Not playing|%?it<%it|%fn>|%?it<%it|%fn>|%?it<%it|%fn>|%?it<%it|%fn>>

%V({MTXT_X},{MART_Y + 22},{MTXT_W},{FH['13-Spotish-Inter-SemiBold.fnt']},3)
%Vf(B3B3B3)
%Vb(000000)
%s%?mp<|%?ia<%ia|>|%?ia<%ia|>|%?ia<%ia|>|%?ia<%ia|>>

%V({MPP_X},{MPP_Y},{MPP_D},{MPP_D},-)
%?mp<%xd(MiniPP,1)|%xd(MiniPP,2)|%xd(MiniPP,1)|%xd(MiniPP,2)|%xd(MiniPP,2)>

%V({MPB_X},{MPB_Y},{MPB_W},{MPB_H},-)
{bar('pb', 0, 0, MPB_W, MPB_H, 'MiniFill', 'MiniBack')}
"""
    with open(os.path.join(OUT, "wps", f"{NAME}.sbs"), "w", newline="\n", encoding="utf-8") as fh:
        fh.write(s)


def write_cfg():
    s = f"""# {NAME} - Spotify desktop-player style theme
# Rockbox, iPod Video 5 / 5.5G (320x240)

wps: /.rockbox/wps/{NAME}.wps
sbs: /.rockbox/wps/{NAME}.sbs
backdrop: -
font: /.rockbox/fonts/{LIST_FONT}

foreground color: FFFFFF
background color: 121212

selector type: bar (color)
line selector start color: {'%02X%02X%02X' % SEL_BG}
line selector end color: {'%02X%02X%02X' % SEL_BG}
line selector text color: {'%02X%02X%02X' % SEL_FG}

show icons: off
scrollbar: right
scrollbar width: 3

statusbar: top

# smooth scrolling of long titles: move 1 pixel per step, ~49 steps/s
# (speed 16 in firmware/scroll_engine.c; the default is 6 px at 10 steps/s)
scroll step: 1
scroll speed: 16
"""
    os.makedirs(os.path.join(OUT, "themes"), exist_ok=True)
    with open(os.path.join(OUT, "themes", f"{NAME}.cfg"), "w", newline="\n") as fh:
        fh.write(s)


# ---------------------------------------------------------------- PC mockups (device-accurate)
def sample_cover(s):
    img = Image.new("RGB", (s, s))
    vgrad(img, (0, 0, s, s), (20, 40, 70), (90, 30, 20))
    g = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    d.ellipse([-s * .2, s * .1, s * .6, s * .9], fill=(40, 140, 200, 120))
    d.ellipse([s * .45, -s * .1, s * 1.2, s * .7], fill=(230, 120, 40, 120))
    g = g.filter(ImageFilter.GaussianBlur(max(2, s / 10)))
    img.paste(g, (0, 0), g)
    return img


def preview(wps_bg, sbs_bg):
    """Screenshots as the iPod draws them: RGB565 + backdrop dither, and text rendered
    with the bundled Rockbox .fnt fonts at the exact viewport positions of the skin."""
    pv = os.path.join(ROOT, "screenshots")
    os.makedirs(pv, exist_ok=True)
    F = {f: RbFont(os.path.join(FNT_DIR, f)) for f in FH}
    TITLE, META, HEAD = F[WPS_FONTS[2]], F[WPS_FONTS[3]], F[WPS_FONTS[4]]
    LTITLE, SMALL, MTITLE, LIST = F[SBS_FONTS[2]], F[SBS_FONTS[3]], F[SBS_FONTS[4]], F[LIST_FONT]

    def load(name, frame=None, frames=1):
        im = Image.open(os.path.join(IMG_DIR, name)).convert("RGB")
        if frame is not None:
            hh = im.height // frames
            im = im.crop((0, frame * hh, im.width, (frame + 1) * hh))
        return device_view(im)          # as the iPod shows an undithered image

    def barshot(img, fill, back, x, y, frac):
        img.paste(load(back), (x, y))
        f = load(fill)
        img.paste(f.crop((0, 0, int(f.width * frac), f.height)), (x, y))

    def save(img, name):
        img.resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(pv, name))

    img = device_view(wps_bg, dither=True)
    img.paste(device_view(sample_cover(ART_S)), (ART_X, ART_Y))
    TITLE.draw(img, INFO_X, TITLE_Y, "Ramayana (The Introduction Theme)", WHITE, INFO_W)
    META.draw(img, INFO_X, META_Y, "Hans Zimmer • 2026 • 2:35", hx("E1EBEC"), INFO_W)
    img.paste(load("play_big.bmp", 1, 2), (PLAY_X, PLAY_Y))
    HEAD.draw(img, 14, NEXT_HEAD_Y, "Next in queue", WHITE, CARD_W - 20)
    META.draw(img, 14, NEXT_Y, "Siya Ram - A.R. Rahman", GREY, CARD_W - 20)
    img.paste(load("shuffle.bmp", 0, 2), (SHUF_X, SM_Y))
    img.paste(load("pp.bmp", 1, 2), (PP_X, PP_Y))
    img.paste(load("repeat.bmp", 1, 4), (REP_X, SM_Y))
    META.draw(img, 4, TIME_Y, "1:36", GREY, PB_X - 10, "right")
    barshot(img, "pb_fill.bmp", "pb_back.bmp", PB_X, PB_Y, .62)
    META.draw(img, PB_X + PB_W + 6, TIME_Y, "2:35", GREY, W - PB_X - PB_W - 10)
    save(img, "now-playing.png")

    vimg = img.copy()
    vimg.paste(device_view(wps_bg, dither=True).crop((0, TIME_Y, W, TIME_Y + TIME_H)), (0, TIME_Y))
    vimg.paste(load("speaker.bmp"), (SPK_X, SPK_Y))
    barshot(vimg, "pb_fill.bmp", "pb_back.bmp", PB_X, PB_Y, .7)
    save(vimg, "now-playing-volume.png")

    img = device_view(sbs_bg, dither=True)
    d = ImageDraw.Draw(img)
    LTITLE.draw(img, 14, LT_Y, "Artists", WHITE, 180)
    if STATUS_STYLE == "C":
        F[SBS_FONTS[4]].draw(img, CLK_X, CLK_Y, "21:47", WHITE, CLK_W, "right")
        barshot(img, "bat_fill.bmp", "bat_back.bmp", BATT_X, BATT_Y, .82)
    else:
        SMALL.draw(img, 214, LT_Y + 4, "21:47  82%", GREY, LIB_X + LIB_W - 10 - 214, "right")
    items = ["A. R. Rahman", "Anu Malik", "Hans Zimmer", "Jagjit Singh", "Linkin Park", "Pankaj Udhas", "Shubh"]
    for i, it in enumerate(items):
        y = LIST_Y + i * LIST.height
        if y + LIST.height > LIST_Y + LIST_H:
            break
        fg = WHITE
        if i == 2:
            d.rectangle([8, y, W - 8 - 5, y + LIST.height - 1], fill=SEL_BG)
            fg = SEL_FG
        LIST.draw(img, 8, y, it, fg, W - 16 - 5)
    d.rectangle([W - 8 - 3, LIST_Y, W - 9, LIST_Y + 50], fill=hx("6A6A6A"))
    img.paste(device_view(sample_cover(MART)), (MART_X, MART_Y))
    MTITLE.draw(img, MTXT_X, MART_Y + 1, "Ramayana (The Introduction Theme)", WHITE, MTXT_W)
    SMALL.draw(img, MTXT_X, MART_Y + 22, "Hans Zimmer, A.R. Rahman", GREY, MTXT_W)
    img.paste(load("mini_pp.bmp", 1, 2), (MPP_X, MPP_Y))
    barshot(img, "mini_pb_fill.bmp", "mini_pb_back.bmp", MPB_X, MPB_Y, .62)
    save(img, "library.png")


if __name__ == "__main__":
    wps_bg, sbs_bg = build_images()
    write_wps()
    write_sbs()
    write_cfg()
    os.makedirs(os.path.join(OUT, "fonts"), exist_ok=True)
    for f in sorted(FH):                       # ship the fonts with the theme
        shutil.copy2(os.path.join(FNT_DIR, f), os.path.join(OUT, "fonts", f))
    if NAME == "Spotish":                      # renamed test builds leave the repo screenshots alone
        preview(wps_bg, sbs_bg)
    print("built", OUT)
