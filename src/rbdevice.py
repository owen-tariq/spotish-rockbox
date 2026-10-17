"""
Emulates how Rockbox on the iPod Video (RGB565 LCD) turns skin BMPs into pixels,
so generated themes look on the device exactly like they do on the PC.

Source: apps/recorder/bmp.c (LCD_DEPTH 16 path) and apps/gui/skin_engine/skin_parser.c
  level = (31*v + (v >> 3) + d) >> 8      for red/blue  (5 bit)
  level = (63*v + (v >> 2) + d) >> 8      for green     (6 bit)
  d = 127 for normal images; for the skin backdrop (%X, via apps/gui/backdrop.c,
  or an image in a %VB viewport) Rockbox dithers:
  d = DITHERX(col) ^ DITHERY(row), a 16x16 Bayer pattern by image position.

Because only the backdrop is dithered, an overlay cut out of the backdrop (bar,
icon, knob...) shows slightly different colours than the backdrop around it.
match_backdrop() fixes that by giving the overlay's untouched pixels the exact
device colours of the dithered backdrop underneath.
"""
import numpy as np
from PIL import Image

DITHER_TABLE = np.array([0, 192, 48, 240, 12, 204, 60, 252, 3, 195, 51, 243, 15, 207, 63, 255], dtype=np.int32)


def _conv(a, bits, d):
    return (((1 << bits) - 1) * a + (a >> (8 - bits)) + d) >> 8


def levels(img, dither):
    """Device RGB565 levels (H, W, 3) for an image as Rockbox would load it."""
    a = np.asarray(img.convert("RGB"), dtype=np.int32)
    h, w, _ = a.shape
    if dither:
        d = DITHER_TABLE[np.arange(w) & 15][None, :] ^ (DITHER_TABLE[np.arange(h) & 15] & 0xAA)[:, None]
    else:
        d = 127
    return np.stack([_conv(a[..., 0], 5, d), _conv(a[..., 1], 6, d), _conv(a[..., 2], 5, d)], -1)


# smallest 8-bit value that an undithered load maps to each level
_ENC = {b: np.array([next(v for v in range(256) if _conv(v, b, 127) == k) for k in range(1 << b)])
        for b in (5, 6)}


def encode(lv):
    """BMP-ready image whose undithered load gives exactly these levels."""
    out = np.stack([_ENC[5][lv[..., 0]], _ENC[6][lv[..., 1]], _ENC[5][lv[..., 2]]], -1)
    return Image.fromarray(out.astype(np.uint8), "RGB")


def display(lv):
    """What the LCD shows for these levels, as an 8-bit image (for mockups)."""
    r = (lv[..., 0] << 3) | (lv[..., 0] >> 2)
    g = (lv[..., 1] << 2) | (lv[..., 1] >> 4)
    b = (lv[..., 2] << 3) | (lv[..., 2] >> 2)
    return Image.fromarray(np.stack([r, g, b], -1).astype(np.uint8), "RGB")


def device_view(img, dither=False):
    return display(levels(img, dither))


class RbFont:
    """Reads a Rockbox .fnt (RB12) and draws text exactly as the iPod would, for mockups.

    Layout (firmware/font.c, tools/convttf.c): 36-byte header, glyph bits, padding,
    offsets (u16, or u32 for big fonts), widths (u8). Anti-aliased fonts (depth 1)
    store each glyph as height x width 4-bit pixels, row-major, low nibble first,
    value 0 = full ink ... 15 = transparent."""

    def __init__(self, path):
        import struct
        data = open(path, "rb").read()
        if data[:4] != b"RB12":
            raise ValueError(f"{path}: not an RB12 font")
        (self.maxwidth, self.height, self.ascent, self.depth) = struct.unpack("<HHHH", data[4:12])
        (self.first, self.default, self.size, bits_size, noffset, nwidth) = struct.unpack("<IIIIII", data[12:36])
        self.bits = data[36:36 + bits_size]
        pos = 36 + bits_size
        long_off = bits_size >= 0xFFDB
        pos = (pos + 3) & ~3 if long_off else (pos + 1) & ~1
        fmt, step = ("<I", 4) if long_off else ("<H", 2)
        self.offsets = [struct.unpack_from(fmt, data, pos + i * step)[0] for i in range(noffset)] if noffset else None
        pos += noffset * step
        self.widths = data[pos:pos + nwidth] if nwidth else None

    def _index(self, ch):
        i = ord(ch) - self.first
        return i if 0 <= i < self.size else self.default - self.first

    def width(self, text):
        return sum(self.widths[self._index(c)] if self.widths else self.maxwidth for c in text)

    def glyph(self, ch):
        """Alpha mask (0..255) of one glyph as a list of rows."""
        i = self._index(ch)
        w = self.widths[i] if self.widths else self.maxwidth
        off = self.offsets[i] if self.offsets else i * ((self.height * w + 1) // 2)
        rows = []
        for y in range(self.height):
            row = []
            for x in range(w):
                n = y * w + x
                v = self.bits[off + n // 2]
                v = (v >> 4) if n & 1 else (v & 0x0F)
                row.append(round((15 - v) * 255 / 15))
            rows.append(row)
        return w, rows

    def draw(self, img, x, y, text, color, box_w=None, align="left"):
        """Draw text with its line top at y, clipped to box_w, like a Rockbox viewport line."""
        tw = self.width(text)
        if box_w is not None and align != "left":
            x += (box_w - tw) if align == "right" else (box_w - tw) // 2
        right = x + box_w if box_w is not None and align == "left" else None
        px = img.load()
        cx = x
        for ch in text:
            w, rows = self.glyph(ch)
            for gy, row in enumerate(rows):
                for gx, a in enumerate(row):
                    X, Y = cx + gx, y + gy
                    if a and 0 <= X < img.width and 0 <= Y < img.height and (right is None or X < right):
                        b = px[X, Y]
                        px[X, Y] = tuple(round(b[k] + (color[k] - b[k]) * a / 255) for k in range(3))
            cx += w
        return tw


def match_backdrop(img, backdrop, x, y, tolerance=4):
    """Overlay drawn at (x, y) over the skin backdrop: pixels it left (nearly)
    untouched get the backdrop's dithered device colours, everything else
    converts normally. The tolerance absorbs the 1-2 step ripple that
    supersampled (Lanczos) drawing leaves next to shapes."""
    a = np.asarray(img.convert("RGB"), dtype=np.int32)
    h, w = a.shape[:2]
    b = np.asarray(backdrop.convert("RGB"), dtype=np.int32)[y:y + h, x:x + w]
    mask = (np.abs(a - b).max(-1) <= tolerance)[..., None]
    lv = np.where(mask, levels(backdrop, True)[y:y + h, x:x + w], levels(img, False))
    return encode(lv)
