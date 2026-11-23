#!/usr/bin/env python3
"""THE WORLD ON SUNDAY - 22 November 2026 in one picture.

A pure-standard-library procedural broadsheet poster. No Pillow, no
system fonts: every glyph is a vector stroke drawn by this program,
every picture is drawn with flat polygons, circles and lines.

The program writes entry.png into MAKEFUN_OUTPUT_DIR when that
variable is set, and beside this file otherwise. It is deterministic:
two runs write the same bytes.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
SS = 2                      # supersample factor for anti-aliasing
BW = W * SS                 # buffer width
BH = H * SS                 # buffer height


# ---------------------------------------------------------------- canvas

class Canvas:
    """An RGB pixel buffer at SS times the final size."""

    def __init__(self):
        self.buf = bytearray(BW * BH * 3)

    def _set(self, x, y, rgb):
        if 0 <= x < BW and 0 <= y < BH:
            i = (y * BW + x) * 3
            self.buf[i] = rgb[0]
            self.buf[i + 1] = rgb[1]
            self.buf[i + 2] = rgb[2]

    def rect(self, x, y, w, h, rgb):
        """Filled rectangle in final-image coordinates."""
        x0 = int(round(x * SS))
        y0 = int(round(y * SS))
        x1 = int(round((x + w) * SS))
        y1 = int(round((y + h) * SS))
        if x1 <= 0 or y1 <= 0 or x0 >= BW or y0 >= BH:
            return
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(BW, x1)
        y1 = min(BH, y1)
        row = bytes(rgb) * (x1 - x0)
        n = len(row)
        buf = self.buf
        for yy in range(y0, y1):
            i = (yy * BW + x0) * 3
            buf[i:i + n] = row

    def poly(self, pts, rgb):
        """Filled polygon; pts are (x, y) in final-image coordinates."""
        sp = [(px * SS, py * SS) for (px, py) in pts]
        ys = [p[1] for p in sp]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(BH - 1, int(math.ceil(max(ys))))
        n = len(sp)
        edges = []
        for i in range(n):
            ax, ay = sp[i]
            bx, by = sp[(i + 1) % n]
            if ay != by:
                edges.append((ax, ay, bx, by))
        if not edges:
            return
        buf = self.buf
        pix = bytes(rgb)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            xs = []
            for (ax, ay, bx, by) in edges:
                if (ay <= yc < by) or (by <= yc < ay):
                    t = (yc - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            if len(xs) < 2:
                continue
            xs.sort()
            base = yy * BW * 3
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(math.floor(xs[k])))
                xb = min(BW - 1, int(math.ceil(xs[k + 1])))
                for xx in range(xa, xb + 1):
                    i = base + xx * 3
                    buf[i:i + 3] = pix

    def circle(self, cx, cy, r, rgb):
        """Filled circle in final-image coordinates."""
        ccx = cx * SS
        ccy = cy * SS
        rr = r * SS
        y0 = max(0, int(math.floor(ccy - rr)))
        y1 = min(BH - 1, int(math.ceil(ccy + rr)))
        buf = self.buf
        pix = bytes(rgb)
        for yy in range(y0, y1 + 1):
            dy = (yy + 0.5) - ccy
            dx = math.sqrt(max(0.0, rr * rr - dy * dy))
            xa = max(0, int(math.floor(ccx - dx)))
            xb = min(BW - 1, int(math.ceil(ccx + dx)))
            base = yy * BW * 3
            for xx in range(xa, xb + 1):
                i = base + xx * 3
                buf[i:i + 3] = pix

    def ellipse(self, cx, cy, rx, ry, rgb):
        ccx = cx * SS
        ccy = cy * SS
        rrx = rx * SS
        rry = ry * SS
        y0 = max(0, int(math.floor(ccy - rry)))
        y1 = min(BH - 1, int(math.ceil(ccy + rry)))
        buf = self.buf
        pix = bytes(rgb)
        for yy in range(y0, y1 + 1):
            dy = ((yy + 0.5) - ccy) / rry
            if abs(dy) >= 1.0:
                continue
            dx = rrx * math.sqrt(1.0 - dy * dy)
            xa = max(0, int(math.floor(ccx - dx)))
            xb = min(BW - 1, int(math.ceil(ccx + dx)))
            base = yy * BW * 3
            for xx in range(xa, xb + 1):
                i = base + xx * 3
                buf[i:i + 3] = pix

    def line(self, x0, y0, x1, y1, wdt, rgb):
        """Thick straight stroke with round joints."""
        hw = wdt / 2.0
        dx = x1 - x0
        dy = y1 - y0
        ln = math.hypot(dx, dy)
        if ln < 1e-9:
            self.circle(x0, y0, hw, rgb)
            return
        nx = -dy / ln * hw
        ny = dx / ln * hw
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], rgb)
        self.circle(x0, y0, hw, rgb)
        self.circle(x1, y1, hw, rgb)

    def stroke(self, pts, wdt, rgb):
        """Polyline through pts, in final-image coordinates."""
        if len(pts) == 1:
            self.circle(pts[0][0], pts[0][1], wdt / 2.0, rgb)
            return
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      wdt, rgb)

    def downsample(self):
        """Box-average the SS buffer down to W x H RGB bytes."""
        out = bytearray(W * H * 3)
        buf = self.buf
        for y in range(H):
            src_rows = []
            for s in range(SS):
                start = ((y * SS + s) * BW) * 3
                src_rows.append(buf[start:start + BW * 3])
            obase = y * W * 3
            for x in range(W):
                r = g = b = 0
                for s in range(SS):
                    row = src_rows[s]
                    i = (x * SS) * 3
                    for t in range(SS):
                        j = i + t * 3
                        r += row[j]
                        g += row[j + 1]
                        b += row[j + 2]
                k = obase + x * 3
                n = SS * SS
                out[k] = r // n
                out[k + 1] = g // n
                out[k + 2] = b // n
        return bytes(out)


def write_png(path, rgb_bytes, w, h):
    """Write an 8-bit RGB PNG with correct chunk checksums."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb_bytes[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------------------ font
# Stroke font on a 0..9 grid: y=0 cap top, y=2 x-height top, y=7 baseline,
# y=9 descender floor. Each glyph is (advance, [stroke, ...]); a stroke is
# a string of "x,y" points. A one-point stroke draws as a dot.

_BOWL = "1,2 3,2 4,3.5 4,5.5 3,7 1,7 0,5.5 0,3.5 1,2"

FONT = {
    "A": (5, ["0,7 2.5,0 5,7", "1.2,4.8 3.8,4.8"]),
    "B": (5, ["0,0 0,7", "0,0 3,0 4.5,1 4.5,2.2 3,3.2 0,3.2",
              "0,3.2 3.2,3.2 4.5,4.2 4.5,6 3.5,7 0,7"]),
    "C": (5, ["5,1.2 3.5,0 1.5,0 0,1.8 0,5.2 1.5,7 3.5,7 5,5.8"]),
    "D": (5, ["0,0 0,7", "0,0 3,0 4.5,1.8 4.5,5.2 3,7 0,7"]),
    "E": (4, ["4,0 0,0 0,7 4,7", "0,3.4 3.2,3.4"]),
    "F": (4, ["4,0 0,0 0,7", "0,3.4 3.2,3.4"]),
    "G": (5, ["5,1.2 3.5,0 1.5,0 0,1.8 0,5.2 1.5,7 3.5,7 5,5.8 5,4.2 3.4,4.2"]),
    "H": (5, ["0,0 0,7", "5,0 5,7", "0,3.4 5,3.4"]),
    "I": (2, ["1,0 1,7"]),
    "J": (4, ["4,0 4,4.8 3.2,7 1.2,7 0,5.8"]),
    "K": (5, ["0,0 0,7", "4.5,0 0.8,3.2", "1.6,2.6 5,7"]),
    "L": (4, ["0,0 0,7 4,7"]),
    "M": (7, ["0,7 0,0 3.5,4.2 7,0 7,7"]),
    "N": (6, ["0,7 0,0 5,7 5,0"]),
    "O": (6, ["3,0 5,0.8 5.5,3 5,2 3,7 1,7 0,5 0.5,3 1,0.8 3,0"]),
    "P": (5, ["0,7 0,0 3.2,0 4.5,1.2 4.5,2.8 3.2,3.8 0,3.8"]),
    "Q": (6, ["3,0 5,0.8 5.5,3 5,2 3,7 1,7 0,5 0.5,3 1,0.8 3,0",
              "3.4,4.8 5.8,7.2"]),
    "R": (5, ["0,7 0,0 3.2,0 4.5,1.2 4.5,2.8 3.2,3.8 0,3.8", "2.2,3.8 5,7"]),
    "S": (5, ["4.8,1.2 3,0 1.2,0 0,1.2 0,2.6 1.2,3.4 3.8,4.2 4.8,5.4 "
              "4.8,6.2 3.4,7 1,7 0,5.8"]),
    "T": (5, ["0,0 5,0", "2.5,0 2.5,7"]),
    "U": (6, ["0,0 0,4.8 1,7 4,7 5.5,4.8 5.5,0"]),
    "V": (6, ["0,0 3,7 6,0"]),
    "W": (8, ["0,0 1.5,7 4,3 6.5,7 8,0"]),
    "X": (5, ["0,0 5,7", "5,0 0,7"]),
    "Y": (6, ["0,0 3,3.4 6,0", "3,3.4 3,7"]),
    "Z": (5, ["0,0 5,0 0,7 5,7"]),
    "a": (4.5, [_BOWL, "4,2 4,7"]),
    "b": (4.5, ["0,0 0,7", _BOWL]),
    "c": (4, ["4,3 2.8,2 1.2,2 0,3.8 0,5.6 1.2,7 2.8,7 4,6"]),
    "d": (4.5, [_BOWL, "4,0 4,7"]),
    "e": (4.5, ["0,4.2 4.5,4.2", "4.5,4.2 4,2.8 2.5,2 0.8,2.4 0,4.2 "
                "0,6 1,7 3,7 4.5,6.2"]),
    "f": (3.5, ["3.2,0 1.4,0 0.4,1.2 0.4,7", "0,2.6 3,2.6"]),
    "g": (4.5, [_BOWL, "4,2 4,7.6 3.2,9 1.4,9 0.2,8.2"]),
    "h": (4.5, ["0,0 0,7", "0,4.4 1,2.2 3,2 4,3.6 4,7"]),
    "i": (2, ["1,2 1,7", "1,0"]),
    "j": (2.5, ["1.6,2 1.6,7.8 0.8,9 0,8.4", "1.6,0"]),
    "k": (4.5, ["0,0 0,7", "3.8,2 0.6,4.4", "1.4,3.6 4.5,7"]),
    "l": (2, ["1,0 1,7"]),
    "m": (7.5, ["0,2 0,7", "0,4.2 1,2.2 2.8,2 3.4,3.4 3.4,7",
                "3.4,4.2 4.4,2.2 6.2,2 7,3.4 7,7"]),
    "n": (4.5, ["0,2 0,7", "0,4.2 1,2.2 3,2 4,3.6 4,7"]),
    "o": (4.5, [_BOWL]),
    "p": (4.5, [_BOWL, "0,2 0,9"]),
    "q": (4.5, [_BOWL, "4,2 4,9"]),
    "r": (3.5, ["0,2 0,7", "0,4 1,2.2 3.2,2 3.5,2.8"]),
    "s": (4, ["3.8,2.8 2.6,2 1,2 0,2.8 0,3.8 1.2,4.6 3,5.2 3.8,6 "
              "2.8,7 0.8,7 0,6.2"]),
    "t": (3.5, ["1.8,0 1.8,5.8 2.8,7 3.6,6.8", "0,2.6 3.6,2.6"]),
    "u": (4.5, ["0,2 0,5.6 1,7 3,7 4,4.8 4,2", "4,4.8 4,7"]),
    "v": (4.5, ["0,2 2.2,7 4.5,2"]),
    "w": (6.5, ["0,2 1.2,7 3.2,3.6 5.2,7 6.5,2"]),
    "x": (4.5, ["0,2 4.5,7", "4.5,2 0,7"]),
    "y": (4.5, ["0,2 2.2,5.2 4.5,2", "2.2,5.2 1.2,9"]),
    "z": (4.5, ["0,2 4.5,2 0,7 4.5,7"]),
    "0": (5.5, ["2.8,0 4.5,0.8 5,2.6 5,4.4 4,6.2 2.5,7 1,6.2 0,4.4 "
                "0,2.6 1,0.8 2.8,0"]),
    "1": (4, ["0.8,1.6 2.4,0 2.4,7", "0.4,7 3.8,7"]),
    "2": (5, ["0.4,1.4 1.6,0 3.4,0 4.6,1.2 4.6,2.8 0.2,7 4.8,7"]),
    "3": (5, ["0.4,1.2 1.8,0 3.4,0 4.6,1.2 3.8,3 1.8,3.4",
              "3.8,3 4.8,4.2 4.6,6 3.2,7 1,7 0,5.8"]),
    "4": (5, ["3.4,7 3.4,0 0,4.8 5,4.8"]),
    "5": (5, ["4.6,0 0.4,0 0.2,3.2 2.8,2.8 4.4,3.8 4.6,5.6 3.2,7 "
              "1,7 0,5.8"]),
    "6": (5, ["4.4,1.2 3,0 1.2,1 0,3.4 0,5.4 1.2,7 3.2,7 4.6,5.8 "
              "4.4,4 2.8,3.2 0.8,3.8"]),
    "7": (5, ["0,0 4.8,0 1.6,7"]),
    "8": (5, ["2.4,3.2 1,3 0.2,1.6 1,0.2 3.2,0 4.4,1.2 3.6,3.2 2.4,3.2",
              "2.4,3.2 4,3.8 4.6,5.6 3.4,7 1.2,7 0.2,5.8 0.6,4 2.4,3.2"]),
    "9": (5, ["0.6,5.8 2,7 3.8,6 4.8,3.6 4.8,1.6 3.6,0 1.6,0 0.4,1.4 "
              "0.8,3 2.4,3.6 4.2,3"]),
    " ": (3, []),
    ".": (2, ["1,6.6"]),
    ",": (2.2, ["1.4,6.2 0.8,8.4"]),
    ":": (2, ["1,2.4", "1,6.4"]),
    ";": (2.2, ["1.2,2.4", "1.4,6.2 0.8,8.4"]),
    "!": (2, ["1,0 1,4.8", "1,6.6"]),
    "?": (5, ["0.4,1.2 1.8,0 3.4,0 4.6,1.2 4.2,2.8 2.6,3.8 2.4,5.2",
              "2.4,6.8"]),
    "'": (2, ["1,0 0.6,1.6"]),
    '"': (3.4, ["0.6,0 0.2,1.6", "2.8,0 2.4,1.6"]),
    "-": (3.4, ["0,3.6 3.4,3.6"]),
    "–": (4.6, ["0,3.6 4.6,3.6"]),
    "—": (6.5, ["0,3.6 6.5,3.6"]),
    "·": (2, ["1,3.6"]),
    "/": (4, ["0,7 4,0"]),
    "(": (3, ["2.6,0 1,2 1,5 2.6,7"]),
    ")": (3, ["0.4,0 2,2 2,5 0.4,7"]),
    "&": (5.5, ["4.6,0.8 3,0 1.2,0.4 0,1.6 1.4,3.2 4.8,6.4 5.2,7",
                "1.4,3.2 0,5 0.6,6.8 2.2,7 3.4,6.2"]),
    "%": (6, ["0,7 6,0", "1.2,0 2.2,0.4 2,2 1,2.4 0.2,1.6 1.2,0",
              "4.6,4.6 5.6,5 5.4,6.6 4.4,7 3.6,6.2 4.6,4.6"]),
    "$": (5, ["4.8,1.2 3,0 1.2,0 0,1.2 0,2.6 1.2,3.4 3.8,4.2 4.8,5.4 "
              "4.8,6.2 3.4,7 1,7 0,5.8", "2.5,0 2.5,7"]),
    "+": (4.5, ["2.2,1.6 2.2,5.6", "0,3.6 4.5,3.6"]),
    "*": (4, ["2,1 2,5.4", "0.4,2 3.6,4.4", "3.6,2 0.4,4.4"]),
    "=": (4.5, ["0,2.4 4.5,2.4", "0,4.8 4.5,4.8"]),
    "<": (4.5, ["4,1.4 0.4,3.6 4,5.8"]),
    ">": (4.5, ["0.4,1.4 4,3.6 0.4,5.8"]),
    "°": (3, ["1.5,0 2.4,0.5 2.2,1.6 1.2,2 0.4,1.4 0.6,0.4 1.5,0"]),
    "→": (6, ["0,3.6 5.6,3.6", "3.4,1.4 5.8,3.6 3.4,5.8"]),
    "≥": (4.5, ["0.4,1.4 4,3.4 0.4,5.4", "0.4,6.8 4,6.8"]),
    "…": (5, ["0.8,6.6", "2.5,6.6", "4.2,6.6"]),
}

_ALIASES = {"‘": "'", "’": "'", "“": '"', "”": '"', "×": "x", "−": "-"}


def _glyph(ch):
    ch = _ALIASES.get(ch, ch)
    return FONT.get(ch, FONT["?"])


def text_width(text, size, tracking=0.14, weight=1.0):
    """Width in final-image pixels of a string at the given cap size."""
    unit = size / 7.0
    total = 0.0
    for ch in text:
        adv, _ = _glyph(ch)
        total += adv + tracking
    return total * unit


def draw_text(cv, x, y, text, size, rgb, weight=1.0, tracking=0.14,
              anchor="left"):
    """Draw text; (x, y) is the top of the cap height at the anchor."""
    w = text_width(text, size, tracking)
    if anchor == "center":
        x -= w / 2.0
    elif anchor == "right":
        x -= w
    unit = size / 7.0
    wdt = size * 0.135 * weight
    cx = x
    for ch in text:
        adv, strokes = _glyph(ch)
        for st in strokes:
            pts = []
            for pair in st.split():
                px, py = pair.split(",")
                pts.append((cx + float(px) * unit, y + float(py) * unit))
            if len(pts) == 1:
                cv.circle(pts[0][0], pts[0][1], wdt * 0.62, rgb)
            else:
                cv.stroke(pts, wdt, rgb)
        cx += (adv + tracking) * unit
    return w


def wrap_text(text, size, max_w, tracking=0.14):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    words = text.split()
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_width(trial, size, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, text, size, rgb, max_w, line_h=None, weight=1.0,
              tracking=0.14, max_lines=None):
    """Draw a wrapped paragraph; returns the y just below it."""
    if line_h is None:
        line_h = size * 1.32
    lines = wrap_text(text, size, max_w, tracking)
    if max_lines is not None:
        lines = lines[:max_lines]
    for ln in lines:
        draw_text(cv, x, y, ln, size, rgb, weight, tracking)
        y += line_h
    return y


# ------------------------------------------------------------- palette

PAPER = (247, 240, 222)
PAPER_D = (238, 228, 203)
INK = (22, 19, 14)
RED = (178, 30, 40)
GOLD = (197, 156, 44)
GRAY = (104, 97, 82)
WHITE = (250, 248, 242)
TEAL = (14, 62, 70)
NAVY = (16, 24, 48)


def fit_size(text, size, max_w, tracking=0.14):
    """Shrink a font size until the text fits max_w."""
    while size > 6 and text_width(text, size, tracking) > max_w:
        size -= 0.5
    return size


def hline(cv, x, y, w, t, rgb=INK):
    cv.rect(x, y, w, t, rgb)


# --------------------------------------------------------- illustrations

def _flag_us(cv, x, y, w, h):
    cv.rect(x, y, w, h, (240, 238, 232))
    for i in range(3):
        cv.rect(x, y + h * (2 * i) / 7.0, w, h / 7.0, (178, 34, 52))
    cv.rect(x, y, w * 0.45, h * 4 / 7.0, (40, 48, 110))
    for r in range(3):
        for c in range(4):
            cv.circle(x + 5 + c * (w * 0.45 - 8) / 3.0,
                      y + 4.5 + r * (h * 4 / 7.0 - 8) / 2.0, 1.1,
                      (245, 245, 245))


def _flag_cn(cv, x, y, w, h):
    cv.rect(x, y, w, h, (206, 32, 40))
    cv.circle(x + w * 0.2, y + h * 0.3, 3.2, (250, 208, 60))
    for (dx, dy) in [(0.38, 0.14), (0.44, 0.3), (0.44, 0.48), (0.36, 0.6)]:
        cv.circle(x + w * dx, y + h * dy, 1.5, (250, 208, 60))


def _flag_ru(cv, x, y, w, h):
    cv.rect(x, y, w, h / 3.0, (240, 240, 240))
    cv.rect(x, y + h / 3.0, w, h / 3.0, (30, 62, 160))
    cv.rect(x, y + 2 * h / 3.0, w, h / 3.0, (200, 36, 44))


def illo_summit(cv, x, y, w, h):
    cv.rect(x, y, w, h, TEAL)
    # pale globe behind the table
    cv.circle(x + w / 2, y + h * 0.52, h * 0.52, (30, 92, 102))
    cv.ellipse(x + w / 2, y + h * 0.52, h * 0.2, h * 0.52, (38, 106, 118))
    cv.ellipse(x + w / 2, y + h * 0.52, h * 0.38, h * 0.52, (38, 106, 118))
    hline(cv, x + w / 2 - h * 0.5, y + h * 0.52, h, 1.4, (38, 106, 118))
    # chandelier dots
    for i in range(9):
        cv.circle(x + w * (0.14 + 0.09 * i), y + 12, 2.2, GOLD)
    hline(cv, x + w * 0.1, y + 12, w * 0.8, 1.2, GOLD)
    # flags on poles
    fw, fh = 56, 37
    fx = [x + w * 0.13, x + w * 0.47, x + w * 0.81]
    for i, fx0 in enumerate(fx):
        cv.rect(fx0 - 7, y + 26, 2.4, 74, (210, 200, 170))
        if i == 0:
            _flag_us(cv, fx0 - 4, y + 26, fw, fh)
        elif i == 1:
            _flag_cn(cv, fx0 - 4, y + 26, fw, fh)
        else:
            _flag_ru(cv, fx0 - 4, y + 26, fw, fh)
    # the long table
    ty = y + h - 52
    cv.poly([(x + 18, ty + 18), (x + w - 18, ty + 18), (x + w - 34, ty + 44),
             (x + 34, ty + 44)], (74, 48, 30))
    cv.rect(x + 26, ty + 6, w - 52, 14, (104, 70, 42))
    # three seated figures
    for cxr in (0.24, 0.5, 0.76):
        cx = x + w * cxr
        cv.circle(cx, ty - 12, 11, (12, 16, 26))
        cv.poly([(cx - 17, ty + 8), (cx + 17, ty + 8), (cx + 10, ty - 6),
                 (cx - 10, ty - 6)], (12, 16, 26))
    # name plates
    for cxr in (0.24, 0.5, 0.76):
        cv.rect(x + w * cxr - 9, ty + 11, 18, 5, (232, 220, 180))


def illo_climate(cv, x, y, w, h):
    cv.rect(x, y, w, h, (18, 66, 52))
    cx, cy, r = x + w * 0.34, y + h / 2, h * 0.42
    cv.circle(cx, cy, r, (96, 168, 120))
    cv.ellipse(cx, cy, r * 0.45, r, (74, 148, 104))
    cv.ellipse(cx, cy, r * 0.8, r, (74, 148, 104))
    hline(cv, cx - r, cy, 2 * r, 1.4, (74, 148, 104))
    # the crack: the talks split apart
    crack = [(cx - r * 0.3, cy - r), (cx - r * 0.05, cy - r * 0.45),
             (cx - r * 0.34, cy - r * 0.1), (cx + r * 0.02, cy + r * 0.4),
             (cx - r * 0.12, cy + r)]
    cv.stroke(crack, 4.4, (16, 40, 30))
    # thermometer, deep in the red
    tx = x + w * 0.78
    cv.rect(tx - 4, y + 8, 8, h - 26, (232, 228, 214))
    cv.rect(tx - 4, y + h * 0.3, 8, h * 0.7 - 12, RED)
    cv.circle(tx, y + h - 11, 9, RED)
    for i in range(4):
        hline(cv, tx + 6, y + 12 + i * (h - 30) / 3.0, 7, 1.6,
              (232, 228, 214))


def illo_cyber(cv, x, y, w, h):
    cv.rect(x, y, w, h, (10, 14, 30))
    # server racks
    for i in range(3):
        rx = x + 14 + i * (w * 0.24)
        cv.rect(rx, y + 8, w * 0.19, h - 16, (38, 48, 74))
        for r in range(4):
            cv.rect(rx + 5, y + 13 + r * (h - 24) / 4.0, w * 0.19 - 10, 3,
                    (70, 88, 124))
            cv.circle(rx + 9, y + 15 + r * (h - 24) / 4.0, 1.6,
                      (86, 220, 130) if (r + i) % 3 else (240, 90, 80))
    # red breach bolt
    bx = x + w * 0.82
    cv.poly([(bx, y + 6), (bx - 13, y + h * 0.52), (bx - 3, y + h * 0.52),
             (bx - 10, y + h - 6), (bx + 12, y + h * 0.4),
             (bx + 2, y + h * 0.4)], (232, 60, 54))
    # warning triangle
    tx, ty = x + w * 0.62, y + h - 20
    cv.poly([(tx, ty - 13), (tx + 11, ty + 6), (tx - 11, ty + 6)],
            (246, 196, 60))
    draw_text(cv, tx - 1.5, ty - 9, "!", 13, (20, 16, 8), 1.6)


def illo_factory(cv, x, y, w, h):
    cv.rect(x, y, w, h, (52, 44, 54))
    # smoke
    for (sx, sy, sr) in [(0.3, 0.2, 9), (0.38, 0.13, 12), (0.68, 0.16, 10)]:
        cv.circle(x + w * sx, y + h * sy, sr, (104, 98, 104))
    base = y + h
    # factory silhouette
    cv.rect(x + w * 0.08, base - h * 0.42, w * 0.62, h * 0.42, (14, 12, 16))
    cv.poly([(x + w * 0.08, base - h * 0.42), (x + w * 0.24, base - h * 0.58),
             (x + w * 0.4, base - h * 0.42), (x + w * 0.56, base - h * 0.58),
             (x + w * 0.7, base - h * 0.42)], (14, 12, 16))
    cv.rect(x + w * 0.76, base - h * 0.78, w * 0.07, h * 0.78, (14, 12, 16))
    cv.rect(x + w * 0.87, base - h * 0.66, w * 0.06, h * 0.66, (14, 12, 16))
    # flames on the roofline
    for fxr in (0.16, 0.3, 0.46, 0.6):
        fx = x + w * fxr
        fy = base - h * 0.44
        cv.poly([(fx - 9, fy), (fx - 3, fy - h * 0.3), (fx + 1, fy - h * 0.14),
                 (fx + 5, fy - h * 0.34), (fx + 10, fy)], (240, 122, 30))
        cv.poly([(fx - 4.5, fy), (fx, fy - h * 0.17), (fx + 4.5, fy)],
                (250, 198, 74))
    # lit windows
    for i in range(5):
        cv.rect(x + w * (0.13 + 0.11 * i), base - h * 0.26, 7, 5,
                (250, 190, 84))


def illo_boat(cv, x, y, w, h):
    cv.rect(x, y, w, h, (196, 222, 226))
    cv.circle(x + w * 0.85, y + h * 0.26, 10, (246, 196, 84))
    # water
    cv.rect(x, y + h * 0.52, w, h * 0.48, (22, 104, 122))
    for i in range(3):
        yy = y + h * (0.62 + 0.13 * i)
        for j in range(6):
            xx = x + w * (0.06 + 0.16 * j) + (8 if i % 2 else 0)
            cv.stroke([(xx, yy), (xx + 9, yy - 2.6), (xx + 18, yy)], 1.7,
                      (150, 206, 216))
    # hull and canopy
    hx, hy = x + w * 0.2, y + h * 0.56
    cv.poly([(hx, hy), (hx + w * 0.56, hy), (hx + w * 0.47, hy + h * 0.24),
             (hx + w * 0.08, hy + h * 0.24)], (112, 70, 40))
    cv.rect(hx + w * 0.1, hy - h * 0.2, w * 0.36, 4, (150, 96, 54))
    cv.rect(hx + w * 0.13, hy - h * 0.2, 3, h * 0.2, (90, 58, 34))
    cv.rect(hx + w * 0.42, hy - h * 0.2, 3, h * 0.2, (90, 58, 34))
    # mourners: dark figures under the canopy
    for i in range(4):
        fx = hx + w * (0.16 + 0.09 * i)
        cv.circle(fx, hy - h * 0.1, 3.4, (30, 28, 30))
        cv.rect(fx - 3, hy - h * 0.07, 6.5, h * 0.07, (30, 28, 30))


def illo_f1(cv, x, y, w, h):
    cv.rect(x, y, w, h, (24, 24, 30))
    # checkered strip
    sq = 7
    for r in range(2):
        for c in range(6):
            col = (238, 238, 238) if (r + c) % 2 == 0 else (16, 16, 18)
            cv.rect(x + w - 6 * sq - 4 + c * sq, y + 5 + r * sq, sq, sq, col)
    # speed lines
    for i in range(3):
        yy = y + h * (0.24 + 0.14 * i)
        hline(cv, x + 10 + i * 9, yy, w * (0.2 - 0.03 * i), 2.2,
              (120, 124, 140))
    gy = y + h * 0.78
    hline(cv, x, gy + 9, w, 3, (200, 60, 54))
    # car body
    bx, by = x + w * 0.3, gy - h * 0.3
    cv.poly([(bx, by + 16), (bx + 14, by + 2), (bx + w * 0.2, by - 3),
             (bx + w * 0.3, by + 6), (bx + w * 0.42, by + 10),
             (bx + w * 0.44, by + 16)], (206, 34, 44))
    cv.poly([(bx + w * 0.16, by - 3), (bx + w * 0.21, by - 12),
             (bx + w * 0.28, by - 11), (bx + w * 0.3, by + 4)],
            (150, 24, 34))
    cv.rect(bx - 8, by - 12, 5, 26, (206, 34, 44))          # rear wing
    cv.rect(bx + w * 0.44, by + 4, 12, 4, (206, 34, 44))     # nose wing
    for wx in (bx + 8, bx + w * 0.36):
        cv.circle(wx, gy, 10.5, (10, 10, 12))
        cv.circle(wx, gy, 4.5, (140, 144, 156))


def illo_exam(cv, x, y, w, h):
    cv.rect(x, y, w, h, (40, 44, 96))
    # exam sheet
    px, py, pw, ph = x + w * 0.3, y + h * 0.1, w * 0.42, h * 0.8
    cv.poly([(px, py), (px + pw, py + 5), (px + pw - 4, py + ph),
             (px - 3, py + ph - 4)], (242, 240, 232))
    for i in range(4):
        hline(cv, px + 10, py + 12 + i * (ph - 20) / 4.0, pw - 22, 2,
              (150, 150, 158))
    # the big red X: answers under suspicion
    cv.stroke([(px + pw * 0.24, py + ph * 0.3), (px + pw * 0.72, py + ph * 0.78)],
              5, RED)
    cv.stroke([(px + pw * 0.72, py + ph * 0.3), (px + pw * 0.24, py + ph * 0.78)],
              5, RED)
    # graduation cap, set aside
    cx, cy = x + w * 0.14, y + h * 0.34
    cv.poly([(cx - 15, cy), (cx, cy - 8), (cx + 15, cy), (cx, cy + 8)],
            (16, 16, 22))
    cv.poly([(cx - 8, cy + 3), (cx + 8, cy + 3), (cx + 8, cy + 11),
             (cx - 8, cy + 11)], (16, 16, 22))
    cv.stroke([(cx + 15, cy), (cx + 15, cy + 13)], 2, GOLD)
    cv.circle(cx + 15, cy + 15, 2.4, GOLD)
    # pencil
    cv.stroke([(x + w * 0.82, y + h * 0.72), (x + w * 0.93, y + h * 0.3)],
              5, (240, 178, 60))


# ------------------------------------------------------------- the poster

PANELS = [
    ("CLIMATE · ANTALYA, TURKEY", "COP31 TALKS COLLAPSE WITHOUT A DEAL",
     "Two days into overtime, nearly 200 nations failed to agree on fossil "
     "fuels and finance. Guterres: 'deeply disappointed'.", illo_climate),
    ("CYBER · WASHINGTON", "HACKERS BREACH FBI CRIMINAL DATABASE",
     "Intruders hit the NCIC files - fingerprints, wanted and missing "
     "persons. Trump confirmed it; an FBI probe is under way.", illo_cyber),
    ("DISASTER · INDONESIA", "FACTORY FIRE: DOZENS STILL MISSING",
     "Fire tore through a confectionery factory, killing at least 3 "
     "workers; rescuers still search for over 30 missing.", illo_factory),
    ("DISASTER · NIGERIA", "FUNERAL BOAT CAPSIZES - 24 DEAD",
     "A boat carrying mourners to a funeral overturned in southern "
     "Nigeria. At least 24 people drowned.", illo_boat),
    ("SPORT · LAS VEGAS", "VERSTAPPEN WINS A VEGAS THRILLER",
     "An extraordinary Grand Prix: 34 lead changes and a Ferrari "
     "collision - and Max Verstappen still took the chequered flag.",
     illo_f1),
    ("POLITICS · SEOUL", "MINISTER QUITS OVER EXAM SCANDAL",
     "Education Minister Choi Kyo-jin resigned after last-minute "
     "anti-AI-cheating rules threw college entrance exams into chaos.",
     illo_exam),
]


def _frame(cv):
    for inset, t in ((11, 2.6), (16.5, 1.1)):
        cv.rect(inset, inset, W - 2 * inset, t, INK)
        cv.rect(inset, H - inset - t, W - 2 * inset, t, INK)
        cv.rect(inset, inset, t, H - 2 * inset, INK)
        cv.rect(W - inset - t, inset, t, H - 2 * inset, INK)


def _panel(cv, x, y, w, kicker, head, body, illo):
    illo(cv, x, y, w, 54)
    cv.rect(x, y, w, 1.2, INK)
    cv.rect(x, y + 53, w, 1.2, INK)
    cv.rect(x, y, 1.2, 54, INK)
    cv.rect(x + w - 1.2, y, 1.2, 54, INK)
    draw_text(cv, x + 2, y + 64, kicker, 10.5, RED, 1.5, 0.2)
    draw_para(cv, x + 2, y + 82, head, 16, INK, w - 4, 22, 1.35, 0.1, 2)
    draw_para(cv, x + 2, y + 128, body, 11.5, INK, w - 4, 14.8, 1.0, 0.1, 3)


def build():
    cv = Canvas()
    cv.rect(0, 0, W, H, PAPER)
    _frame(cv)
    cx = W / 2

    # masthead
    draw_text(cv, cx, 30, "LATE CITY EDITION · No. 47 · ONE DAY - ONE PICTURE",
              12.5, INK, 1.1, 0.34, "center")
    hline(cv, 28, 52, W - 56, 1.1)
    hline(cv, 28, 55.5, W - 56, 3)
    title = "THE WORLD ON SUNDAY"
    ts = fit_size(title, 67, 940, 0.1)
    draw_text(cv, cx, 66, title, ts, INK, 1.55, 0.1, "center")
    hline(cv, 28, 143, W - 56, 3, RED)
    hline(cv, 28, 149, W - 56, 1.1)
    # date bar
    cv.rect(28, 158, W - 56, 42, INK)
    draw_text(cv, 46, 172, "ALL THE DAY'S NEWS", 11, WHITE, 1.2, 0.2)
    draw_text(cv, cx, 167, "SUNDAY · 22 NOVEMBER 2026", 24, WHITE, 1.5, 0.16,
              "center")
    draw_text(cv, W - 46, 172, "IN ONE PICTURE", 11, WHITE, 1.2, 0.2, "right")

    # lead story
    draw_text(cv, 28, 216, "THE SUMMIT FALLOUT · SHENZHEN - WASHINGTON - KYIV",
              13.5, RED, 1.5, 0.2)
    h1 = "PEACE ON PAPER IN SHENZHEN,"
    h2 = "WAR AT FULL VOLUME IN UKRAINE"
    hs = fit_size(h1, 47, 950, 0.08)
    hs = min(hs, fit_size(h2, 47, 950, 0.08))
    draw_text(cv, 28, 234, h1, hs, INK, 1.5, 0.08)
    draw_text(cv, 28, 234 + hs * 1.32, h2, hs, INK, 1.5, 0.08)
    illo_summit(cv, 28, 362, 470, 190)
    cv.rect(28, 362, 470, 1.4, INK)
    cv.rect(28, 550.6, 470, 1.4, INK)
    cv.rect(28, 362, 1.4, 190, INK)
    cv.rect(496.6, 362, 1.4, 190, INK)
    tx = 522
    tw = W - 28 - tx
    y = draw_para(cv, tx, 362,
                  "Trump, Xi and Putin's 'declaration of peace' - no nuclear "
                  "war, more oil, a weaker world court - met its verdicts "
                  "on Sunday.", 14, INK, tw, 19.5)
    y = draw_para(cv, tx, y + 9,
                  "Trump hailed 'one of the most momentous summits in many "
                  "years'; Zelensky called it 'very unsuccessful for "
                  "Russia'.", 14, INK, tw, 19.5)
    # stat box
    by = 498
    cv.rect(tx, by, tw, 52, PAPER_D)
    cv.rect(tx, by, 6, 52, RED)
    cv.rect(tx, by, tw, 1.4, INK)
    cv.rect(tx, by + 50.6, tw, 1.4, INK)
    cv.rect(tx + tw - 1.4, by, 1.4, 52, INK)
    draw_text(cv, tx + 18, by + 8, "KYIV AND KRYVYI RIH STRIKES: 5 DEAD",
              12.5, INK, 1.5, 0.12)
    draw_text(cv, tx + 18, by + 29, "RUSSIA'S BIGGEST ATTACK DAY OF THE YEAR",
              12.5, INK, 1.5, 0.12)
    hline(cv, 28, 566, W - 56, 1.6)

    # divider
    dtext = "SIX MORE STORIES THAT SHAPED THE DAY"
    dw = text_width(dtext, 12.5, 0.3)
    hline(cv, 28, 584, (W - 56 - dw) / 2 - 14, 1.2, GRAY)
    hline(cv, cx + dw / 2 + 14, 584, (W - 56 - dw) / 2 - 14, 1.2, GRAY)
    draw_text(cv, cx, 578, dtext, 12.5, INK, 1.4, 0.3, "center")

    # panels
    pw = 313
    xs = [28, 355, 682]
    ys = [602, 782]
    for i, (kicker, head, body, illo) in enumerate(PANELS):
        _panel(cv, xs[i % 3], ys[i // 3], pw, kicker, head, body, illo)
    for sx in (348, 675):
        cv.rect(sx, 602, 1.1, 348, GRAY)
    hline(cv, 28, 776, W - 56, 1.1, GRAY)

    # footer
    cv.rect(28, 958, W - 56, 40, INK)
    draw_text(cv, 46, 965, "ALSO TODAY", 11.5, (240, 120, 110), 1.5, 0.18)
    rest = ("NEPAL'S PM IN DELHI FOR TALKS WITH MODI · UKRAINIAN SEA "
            "DRONES HIT RUSSIAN WARSHIP OFF BENGHAZI, LIBYA")
    rx = 46 + text_width("ALSO TODAY", 11.5, 0.18) + 16
    rs = fit_size(rest, 11.5, W - 46 - rx, 0.1)
    draw_text(cv, rx, 965, rest, rs, WHITE, 1.1, 0.1)
    draw_text(cv, cx, 982,
              "ROHINGYA WELCOME THE ICJ GENOCIDE VERDICT - AND ASK TO GO "
              "HOME · DRAWN BY A PROGRAM IN PURE PYTHON",
              11, WHITE, 1.05, 0.1, "center")
    return cv


def main():
    cv = build()
    rgb = cv.downsample()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not out_dir:
        out_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    n = write_png(path, rgb, W, H)
    print("wrote %s (%d bytes)" % (path, n))


if __name__ == "__main__":
    main()
