#!/usr/bin/env python3
"""The World in One Day -- Monday 23 November 2026.

A one-page newspaper drawn entirely in code (Python 3.13, standard
library only). It sums up the world news of Monday 23 November 2026
in a single 1024x1024 image, written to /output/entry.png
(MAKEFUN_OUTPUT_DIR outside the grader).

The paper was drawn early on Monday morning WIB, while the news day
was still developing, so it leads with what Monday had already
produced -- the Nepal-India talks in Delhi, the search resuming at
dawn in Serang, the final day of the Wellington Test -- and it says
plainly, in its DATE CHECK box, which big stories belong to other
days and were left out on purpose, and which outcomes were still
undecided when the paper was drawn.

Every story on the page was verified against a real wire or outlet
(Reuters, AP, AFP, Al Jazeera, BBC, ABC, AAP, ESPNcricinfo, Xinhua,
government releases). One-sided claims are labelled CLAIM and
attributed; forecasts are labelled FORECAST.

Layout follows the classic one-page front page: serif masthead with
the day, a top strip naming the story and region counts, a red
subhead with the three top stories, a key-numbers strip, a coloured
region bar, a timeline of the day in UTC, three hero stories with
drawn illustrations, ten secondaries, a world map with numbered
pins, a numbered list of the remaining stories, a DATE CHECK box
and a sources footer.

Everything is drawn by hand in this file: its own framebuffer
rasterizer, its own hand-typed 5x7 bitmap font, its own vector
serif face for the masthead, and its own PNG encoder. No network,
no randomness, no wall-clock time: two runs write identical bytes.
"""

import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 232)      # warm newsprint cream
PAPER2 = (255, 253, 246)     # lighter cream panel
INK = (26, 26, 26)           # near-black text
NAVY = (22, 38, 78)          # masthead + top bar
NAVY2 = (30, 52, 104)
RED = (178, 34, 28)          # subhead, banners, rules
RED2 = (140, 22, 18)
GOLD = (198, 158, 62)
GREY = (110, 108, 100)
LGREY = (210, 206, 194)
RULE = (60, 58, 52)
TEAL = (18, 110, 110)
BLUE = (38, 90, 168)
ORANGE = (196, 110, 20)
PURPLE = (110, 74, 150)
GREEN = (46, 128, 66)
SKY = (168, 205, 232)
SKYD = (120, 170, 210)
SEA = (96, 150, 196)
LAND = (232, 222, 196)
LAND2 = (214, 200, 168)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class FB:
    """A plain RGB framebuffer with a small rasterizer."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) * (yy - cy)) ** 0.5) if abs(yy - cy) <= r else -1
            if dx >= 0:
                self.rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def circle(self, cx, cy, r, c):
        # outline only
        n = max(12, int(6.28 * r))
        pts = []
        for i in range(n + 1):
            a = 6.2831853 * i / n
            pts.append((int(cx + r * _cos(a)), int(cy + r * _sin(a))))
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c)

    def poly(self, pts, c):
        """Fill a polygon (scanline)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = min(ys), max(ys)
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, yy0 = pts[i]
                x1, yy1 = pts[(i + 1) % n]
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    t = (y - yy0) / (yy1 - yy0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), y, int(xs[i + 1]) - int(xs[i]) + 1, 1, c)

    def tri(self, a, b, c, col):
        self.poly([a, b, c], col)

    def thick_line(self, x0, y0, x1, y1, w, c):
        """A line with round caps, drawn by stamping discs along it."""
        r = max(1, w // 2)
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            t = i / steps
            self.disc(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t), r, c)


def _sin(a):
    # small sine via Taylor around 0..2pi is overkill; use math-free table
    return _SIN[int((a % 6.2831853) / 6.2831853 * 256) % 256]


def _cos(a):
    return _SIN[int(((a + 1.5707963) % 6.2831853) / 6.2831853 * 256) % 256]


_SIN = []
for _i in range(256):
    _a = 6.2831853 * _i / 256
    # Taylor series for sin, good to ~1e-4 here
    _x = _a
    _s = _x
    _t = _x
    for _k in range(1, 6):
        _t *= -_x * _x / ((2 * _k) * (2 * _k + 1))
        _s += _t
    _SIN.append(_s)


# ---------------------------------------------------------------- PNG out
def write_png(fb, path):
    raw = bytearray()
    for y in range(fb.h):
        raw.append(0)  # filter: none
        raw += fb.px[y * fb.w * 3:(y + 1) * fb.w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", fb.w, fb.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------- 5x7 bitmap font
# Each glyph: 7 rows of 5 cells, '#' = ink. Hand-typed.
FONT = {}
def _g(ch, rows):
    FONT[ch] = rows

_g('A', ("01110","10001","10001","11111","10001","10001","10001"))
_g('B', ("11110","10001","10001","11110","10001","10001","11110"))
_g('C', ("01110","10001","10000","10000","10000","10001","01110"))
_g('D', ("11110","10001","10001","10001","10001","10001","11110"))
_g('E', ("11111","10000","10000","11110","10000","10000","11111"))
_g('F', ("11111","10000","10000","11110","10000","10000","10000"))
_g('G', ("01110","10001","10000","10111","10001","10001","01111"))
_g('H', ("10001","10001","10001","11111","10001","10001","10001"))
_g('I', ("01110","00100","00100","00100","00100","00100","01110"))
_g('J', ("00111","00010","00010","00010","00010","10010","01100"))
_g('K', ("10001","10010","10100","11000","10100","10010","10001"))
_g('L', ("10000","10000","10000","10000","10000","10000","11111"))
_g('M', ("10001","11011","10101","10101","10001","10001","10001"))
_g('N', ("10001","11001","10101","10011","10001","10001","10001"))
_g('O', ("01110","10001","10001","10001","10001","10001","01110"))
_g('P', ("11110","10001","10001","11110","10000","10000","10000"))
_g('Q', ("01110","10001","10001","10001","10101","10010","01101"))
_g('R', ("11110","10001","10001","11110","10100","10010","10001"))
_g('S', ("01111","10000","10000","01110","00001","00001","11110"))
_g('T', ("11111","00100","00100","00100","00100","00100","00100"))
_g('U', ("10001","10001","10001","10001","10001","10001","01110"))
_g('V', ("10001","10001","10001","10001","10001","01010","00100"))
_g('W', ("10001","10001","10001","10101","10101","11011","10001"))
_g('X', ("10001","10001","01010","00100","01010","10001","10001"))
_g('Y', ("10001","10001","01010","00100","00100","00100","00100"))
_g('Z', ("11111","00001","00010","00100","01000","10000","11111"))
_g('a', ("00000","00000","01110","00001","01111","10001","01111"))
_g('b', ("10000","10000","11110","10001","10001","10001","11110"))
_g('c', ("00000","00000","01110","10000","10000","10001","01110"))
_g('d', ("00001","00001","01111","10001","10001","10001","01111"))
_g('e', ("00000","00000","01110","10001","11111","10000","01110"))
_g('f', ("00110","01001","01000","11110","01000","01000","01000"))
_g('g', ("00000","01111","10001","10001","01111","00001","01110"))
_g('h', ("10000","10000","11110","10001","10001","10001","10001"))
_g('i', ("00100","00000","01100","00100","00100","00100","01110"))
_g('j', ("00010","00000","00110","00010","00010","00010","01100"))
_g('k', ("10000","10000","10010","10100","11000","10100","10010"))
_g('l', ("01100","00100","00100","00100","00100","00100","01110"))
_g('m', ("00000","00000","11010","10101","10101","10101","10101"))
_g('n', ("00000","00000","11110","10001","10001","10001","10001"))
_g('o', ("00000","00000","01110","10001","10001","10001","01110"))
_g('p', ("00000","11110","10001","10001","11110","10000","10000"))
_g('q', ("00000","00000","01111","10001","10001","01111","00001"))
_g('r', ("00000","00000","10110","11001","10000","10000","10000"))
_g('s', ("00000","00000","01111","10000","01110","00001","11110"))
_g('t', ("01000","01000","11110","01000","01000","01001","00110"))
_g('u', ("00000","00000","10001","10001","10001","10011","01101"))
_g('v', ("00000","00000","10001","10001","10001","01010","00100"))
_g('w', ("00000","00000","10001","10101","10101","10101","01010"))
_g('x', ("00000","00000","10001","01010","00100","01010","10001"))
_g('y', ("00000","00000","10001","10001","01111","00001","01110"))
_g('z', ("00000","00000","11111","00010","00100","01000","11111"))
_g('0', ("01110","10001","10011","10101","11001","10001","01110"))
_g('1', ("00100","01100","00100","00100","00100","00100","01110"))
_g('2', ("01110","10001","00001","00110","01000","10000","11111"))
_g('3', ("11110","00001","00001","01110","00001","00001","11110"))
_g('4', ("00010","00110","01010","10010","11111","00010","00010"))
_g('5', ("11111","10000","11110","00001","00001","10001","01110"))
_g('6', ("01110","10000","10000","11110","10001","10001","01110"))
_g('7', ("11111","00001","00010","00100","01000","01000","01000"))
_g('8', ("01110","10001","10001","01110","10001","10001","01110"))
_g('9', ("01110","10001","10001","01111","00001","00001","01110"))
_g('.', ("00000","00000","00000","00000","00000","01100","01100"))
_g(',', ("00000","00000","00000","00000","01100","00100","01000"))
_g(':', ("00000","01100","01100","00000","01100","01100","00000"))
_g(';', ("00000","01100","01100","00000","01100","00100","01000"))
_g('!', ("00100","00100","00100","00100","00100","00000","00100"))
_g('?', ("01110","10001","00001","00110","00100","00000","00100"))
_g("'", ("00100","00100","01000","00000","00000","00000","00000"))
_g('"', ("01010","01010","00000","00000","00000","00000","00000"))
_g('-', ("00000","00000","00000","01110","00000","00000","00000"))
_g('(', ("00010","00100","01000","01000","01000","00100","00010"))
_g(')', ("01000","00100","00010","00010","00010","00100","01000"))
_g('/', ("00001","00010","00010","00100","01000","01000","10000"))
_g('%', ("11001","11010","00010","00100","01000","01011","10011"))
_g('&', ("01100","10010","10100","01000","10101","10010","01101"))
_g('+', ("00000","00100","00100","11111","00100","00100","00000"))
_g('=', ("00000","00000","11111","00000","11111","00000","00000"))
_g('*', ("00000","10101","01110","11111","01110","10101","00000"))
_g('#', ("01010","01010","11111","01010","11111","01010","01010"))
_g('@', ("01110","10001","10111","10101","10110","10000","01110"))
_g('_', ("00000","00000","00000","00000","00000","00000","11111"))
_g('[', ("01110","01000","01000","01000","01000","01000","01110"))
_g(']', ("01110","00010","00010","00010","00010","00010","01110"))
_g('\u00b7', ("00000","00000","00000","01100","01100","00000","00000"))
_g('\u2014', ("00000","00000","00000","11111","00000","00000","00000"))
_g(' ', ("00000","00000","00000","00000","00000","00000","00000"))

CHAR_W = 6  # 5 px glyph + 1 px gap, times scale


def text_w(s, scale):
    return len(s) * CHAR_W * scale


def draw_text(fb, x, y, s, scale, color):
    """Draw text with the bitmap font; returns width in px."""
    cx = x
    for ch in s:
        rows = FONT.get(ch)
        if rows is None:
            rows = FONT[' ']
        for r in range(7):
            row = rows[r]
            for c in range(5):
                if row[c] == '1':
                    fb.rect(cx + c * scale, y + r * scale, scale, scale, color)
        cx += CHAR_W * scale
    return cx - x


def draw_text_center(fb, cx, y, s, scale, color):
    draw_text(fb, cx - text_w(s, scale) // 2, y, s, scale, color)


def draw_text_bold(fb, x, y, s, scale, color):
    draw_text(fb, x, y, s, scale, color)
    draw_text(fb, x + 1, y, s, scale, color)


def wrap(s, scale, max_w):
    """Greedy word wrap; returns a list of lines."""
    words = s.split(' ')
    lines = []
    cur = ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def para(fb, x, y, s, scale, max_w, color, leading=None, max_lines=None):
    """Draw a wrapped paragraph; returns the y after the last line."""
    lh = (leading if leading is not None else 9 * scale)
    lines = wrap(s, scale, max_w)
    if max_lines is not None:
        lines = lines[:max_lines]
    for ln in lines:
        draw_text(fb, x, y, ln, scale, color)
        y += lh
    return y


# ------------------------------------------------------- vector serif face
# The masthead is set in a hand-drawn serif face: each glyph is a list
# of polylines on a 0..64 wide, 0..80 tall grid (baseline 80, x-height
# top 30, descenders to 100). Strokes are drawn thick with small serif
# ticks at the feet and heads of the stems, so the big date reads as a
# newspaper serif rather than a pixel font.
SERIF_W = {
    'M': 66, 'o': 46, 'n': 48, 'd': 48, 'a': 46, 'y': 48, ' ': 22,
    '2': 48, '3': 46, 'N': 62, 'v': 50, 'e': 46, 'm': 68, 'b': 48,
    'r': 40, '6': 46, '0': 48,
}
SERIF = {
    # (points, closed?) -- strokes drawn thick; serifs added separately
    'M': ([(6, 2), (6, 78), (33, 40), (60, 2), (60, 78)], False),
    'o': ([(23, 30), (36, 32), (43, 44), (43, 62), (36, 76), (23, 78),
           (10, 76), (3, 62), (3, 44), (10, 32), (23, 30)], True),
    'n': ([(5, 78), (5, 40), (10, 32), (20, 30), (30, 32), (38, 40),
           (43, 52), (43, 78)], False),
    'd': ([(24, 30), (37, 32), (44, 44), (44, 62), (37, 76), (24, 78),
           (11, 76), (4, 62), (4, 44), (11, 32), (24, 30)], True),
    'a': ([(23, 34), (36, 36), (41, 48), (41, 64), (34, 76), (21, 78),
           (10, 74), (5, 62), (5, 48), (12, 36), (23, 34)], True),
    'y': ([(5, 30), (23, 62), (41, 30)], False),
    '2': ([(8, 16), (16, 4), (30, 4), (40, 12), (36, 26), (12, 64),
           (6, 78), (42, 78)], False),
    '3': ([(10, 6), (22, 2), (34, 6), (40, 16), (34, 30), (24, 34),
           (34, 40), (40, 52), (36, 68), (26, 78), (12, 76), (6, 68)],
          False),
    'N': ([(6, 2), (6, 78), (56, 2), (56, 78)], False),
    'v': ([(5, 30), (25, 78), (45, 30)], False),
    'e': ([(40, 50), (38, 34), (30, 30), (16, 30), (6, 38), (4, 54),
           (8, 70), (20, 78), (34, 76), (42, 66)], False),
    'm': ([(5, 78), (5, 40), (10, 32), (20, 30), (28, 34), (32, 42),
           (32, 78), (32, 42), (38, 32), (48, 30), (56, 34), (62, 42),
           (62, 78)], False),
    'b': ([(5, 2), (5, 78), (5, 54), (14, 32), (26, 30), (38, 34),
           (44, 48), (44, 62), (36, 76), (24, 78), (12, 76), (5, 64)],
          False),
    'r': ([(5, 78), (5, 40), (10, 32), (20, 30), (30, 32), (36, 38)],
          False),
    '6': ([(38, 8), (26, 2), (14, 8), (6, 20), (4, 40), (8, 58),
           (18, 76), (30, 78), (40, 70), (44, 56), (40, 42), (30, 38),
           (18, 40), (10, 48), (8, 58)], False),
    '0': ([(24, 2), (36, 4), (44, 16), (44, 62), (36, 76), (24, 78),
           (12, 76), (4, 62), (4, 16), (12, 4), (24, 2)], True),
}
# serif ticks: (x, y, half-length) horizontal bars at stem ends
SERIF_TICKS = {
    'M': [(6, 2, 6), (60, 2, 6), (6, 78, 6), (60, 78, 6)],
    'N': [(6, 2, 6), (56, 2, 6), (6, 78, 6), (56, 78, 6)],
    'n': [(5, 78, 5), (43, 78, 5), (5, 30, 5)],
    'd': [(44, 2, 5), (44, 78, 5)],
    'a': [(41, 78, 5)],
    'y': [(23, 96, 5)],
    '2': [(6, 78, 6), (42, 78, 6)],
    '3': [(10, 6, 5), (12, 76, 5)],
    'v': [(5, 30, 5), (45, 30, 5)],
    'e': [(4, 54, 5)],
    'm': [(5, 78, 5), (32, 78, 5), (62, 78, 5)],
    'b': [(5, 2, 5), (5, 78, 5)],
    'r': [(5, 78, 5)],
    '6': [(38, 8, 5)],
    '0': [],
    'o': [],
}


def serif_w(s, scale):
    tot = 0
    for ch in s:
        tot += SERIF_W.get(ch, 40) * scale // 50
    return tot


def draw_serif(fb, x, y, s, scale, color):
    """Draw the masthead face. scale: cap-height in px / 80."""
    cap = 80 * scale // 50  # not used directly; strokes scale below
    cx = x
    for ch in s:
        if ch == ' ':
            cx += SERIF_W[' '] * scale // 50
            continue
        pts, _closed = SERIF[ch]
        w = max(2, scale // 6)  # stroke width
        for i in range(len(pts) - 1):
            x0 = cx + pts[i][0] * scale // 50
            y0 = y + pts[i][1] * scale // 50
            x1 = cx + pts[i + 1][0] * scale // 50
            y1 = y + pts[i + 1][1] * scale // 50
            fb.thick_line(x0, y0, x1, y1, w, color)
        if _closed:
            x0 = cx + pts[-1][0] * scale // 50
            y0 = y + pts[-1][1] * scale // 50
            x1 = cx + pts[0][0] * scale // 50
            y1 = y + pts[0][1] * scale // 50
            fb.thick_line(x0, y0, x1, y1, w, color)
        # 'y' tail: the diagonal polyline ends at the join; draw the tail
        if ch == 'y':
            fb.thick_line(cx + 23 * scale // 50, y + 62 * scale // 50,
                          cx + 12 * scale // 50, y + 96 * scale // 50, w, color)
        for (tx, ty, hl) in SERIF_TICKS.get(ch, []):
            fb.rect(cx + (tx - hl) * scale // 50, y + ty * scale // 50,
                    2 * hl * scale // 50, max(2, w // 2), color)
        cx += SERIF_W[ch] * scale // 50
    return cx - x


# ------------------------------------------------------------- story data
# Every story verified against a real outlet on 23 Nov 2026 (or, for
# scheduled items, set to happen that day). Status: OFFICIAL / REPORTED
# / CLAIM / FORECAST. Sources are named on the page itself.
HEROES = [
    dict(
        n=1, place="NEW DELHI, INDIA", region="ASIA-PACIFIC",
        kicker="TALKS TODAY", badge="REPORTED",
        head="Shah meets Modi in Delhi on his first state visit",
        body=("Nepal's Balendra Shah holds delegation-level talks with "
              "Narendra Modi today, with MoUs on education, health, "
              "energy and farming to be signed and a joint press "
              "conference to follow."),
        src="IANS - New Kerala - Radio Nepal",
        scene="delhi",
    ),
    dict(
        n=2, place="SERANG, INDONESIA", region="ASIA-PACIFIC",
        kicker="24 BODY BAGS OUT", badge="REPORTED",
        head="Search resumes at dawn in the burnt-out candy factory",
        body=("Rescuers go back in at 7am after a night's halt at the "
              "PT Fonusa Agung Mulia plant in Cikande, where Saturday's "
              "fire left 29 workers missing and eight more unaccounted "
              "for. Police have removed 24 body bags."),
        src="Reuters - AP - Detik",
        scene="factory",
    ),
    dict(
        n=3, place="WELLINGTON, NEW ZEALAND", region="OCEANIA",
        kicker="DAY 5 - INDIA NEED 8 WICKETS", badge="REPORTED",
        head="New Zealand fight to save the Test after India's 720",
        body=("India declared on 720 for 9, the highest Test total ever "
              "in New Zealand, with centuries from Rahul (136) and Pant "
              "(128). The hosts were 119 for 2 at stumps, still 233 "
              "behind, with Conway unbeaten on 59."),
        src="ESPNcricinfo - Cricbuzz - IANS",
        scene="cricket",
    ),
]

SECONDARIES = [
    dict(n=4, place="SYDNEY, AUSTRALIA", region="OCEANIA", kicker="FIRST FLIGHT",
         badge="OFFICIAL",
         head="Wong lands on the first flight into Western Sydney",
         body="Singapore's PM arrives for a three-day visit.",
         src="PM of Australia", scene="plane"),
    dict(n=5, place="CANBERRA, AUSTRALIA", region="OCEANIA", kicker="NEWSPOLL",
         badge="REPORTED",
         head="Albanese trails Taylor as preferred PM for the first time",
         body="The PM falls behind the Coalition leader in a new poll.",
         src="The Squiz - SMH", scene="poll"),
    dict(n=6, place="TOKYO, JAPAN", region="ASIA-PACIFIC", kicker="HOLIDAY",
         badge="OFFICIAL",
         head="Japan's markets shut for Labor Thanksgiving Day",
         body="Tokyo equities and bonds do not trade today.",
         src="JPX - InvestingLive", scene="gate"),
    dict(n=7, place="SUVA, FIJI", region="OCEANIA", kicker="M4.6",
         badge="REPORTED",
         head="Quake shakes the sea south of Fiji at 7.03am local time",
         body="A magnitude 4.6 tremor south of the Fiji Islands.",
         src="Volcano Discovery", scene="quake"),
    dict(n=8, place="SYDNEY, AUSTRALIA", region="OCEANIA", kicker="FORECAST",
         badge="FORECAST",
         head="Storms, hail and 45-knot gusts due over Sydney today",
         body="A 30% chance of heavy afternoon thunderstorms.",
         src="Sydney Airport bulletin", scene="storm"),
    dict(n=9, place="EUROPE", region="EUROPE", kicker="DUE TODAY",
         badge="FORECAST",
         head="Flash PMIs land today in the eurozone, Britain and Germany",
         body="November's first read on factories and services.",
         src="S&P Global - Dow Jones", scene="chart"),
    dict(n=10, place="MELBOURNE, AUSTRALIA", region="OCEANIA", kicker="POLLS",
         badge="REPORTED",
         head="Victoria: Coalition leads Labor 55-45 six days out",
         body="Polls point to a Coalition majority on Saturday.",
         src="InSnip - Herald Sun", scene="ballot"),
    dict(n=11, place="CANBERRA, AUSTRALIA", region="OCEANIA", kicker="LAST WEEK",
         badge="REPORTED",
         head="Parliament's final sitting week opens with a gas fight",
         body="Labor pushes its gas reservation plan this week.",
         src="The Squiz - SMH", scene="parliament"),
    dict(n=12, place="DELHI, INDIA", region="ASIA-PACIFIC", kicker="GURPURAB",
         badge="REPORTED",
         head="Sikhs mark Guru Nanak's birth with processions in Delhi",
         body="A Nagar Kirtan winds from Chandni Chowk to Nanak Piao.",
         src="Delhi Police - Observer Voice", scene="procession"),
    dict(n=13, place="SANTA CLARA, USA", region="AMERICAS", kicker="01:20 UTC",
         badge="FORECAST",
         head="Vikings at 49ers kick off after midnight UTC",
         body="Sunday-night football starts at 8.20pm in California.",
         src="NFL - Reuters", scene="football"),
]

# The rest of the day, numbered on from the secondaries.
MORE = [
    ("WELLINGTON, NZ", "OCEANIA", "NZ retail sales due today", "Stats NZ", "FORECAST"),
    ("SYDNEY, AUSTRALIA", "OCEANIA", "Australia's flash PMIs due today", "S&P Global", "FORECAST"),
    ("TAIPEI, TAIWAN", "ASIA-PACIFIC", "Jobless rate and M2 money due today", "DGBAS", "FORECAST"),
    ("BEIJING, CHINA", "ASIA-PACIFIC", "China's PMIs due today", "NBS", "FORECAST"),
    ("NEW YORK, USA", "AMERICAS", "NY Fed's Williams speaks today", "Fed", "FORECAST"),
    ("SEOUL, KOREA", "ASIA-PACIFIC", "Five-year bond auction today", "MoEF", "FORECAST"),
    ("ANTALYA, TURKIYE", "WORLD", "COP31 fallout: Bowen faces a $150m cost row", "The Squiz", "REPORTED"),
    ("ADDIS ABABA, ETHIOPIA", "WORLD", "COP32 inherits the deadlock next year", "UN News", "REPORTED"),
    ("WASHINGTON, USA", "AMERICAS", "Schumer turns 76 today; Senate vote on 1 Dec", "Reuters", "REPORTED"),
    ("PHNOM PENH, CAMBODIA", "ASIA-PACIFIC", "Cambodia shut today for the water festival", "Govt", "OFFICIAL"),
    ("NEW YORK, USA", "AMERICAS", "US data week: core PCE and Q3 GDP on Wed", "Dow Jones", "FORECAST"),
    ("NEW YORK, USA", "AMERICAS", "Earnings today: Medtronic, Zoom, HPE report", "Substack", "FORECAST"),
    ("SEOUL, KOREA", "ASIA-PACIFIC", "Rail strike put off to Thu; trains run today", "Aju Press", "REPORTED"),
    ("SEOUL, KOREA", "ASIA-PACIFIC", "Metro strike threat hangs over Wednesday", "Aju Press", "REPORTED"),
    ("PARBHANI, INDIA", "ASIA-PACIFIC", "Mourners pay respects to MP Wadkute today", "News Nation", "REPORTED"),
    ("DELHI, INDIA", "ASIA-PACIFIC", "Traffic curbs for VIP movement at Rajghat", "Delhi Police", "OFFICIAL"),
    ("NEW YORK, USA", "AMERICAS", "US flash PMIs due today", "S&P Global", "FORECAST"),
    ("HYDERABAD, INDIA", "ASIA-PACIFIC", "Students' protest over casteist remarks goes on", "Observer Voice", "REPORTED"),
    ("BUJUMBURA, BURUNDI", "AFRICA", "Burundi begins vetting election candidates", "Khusoko", "REPORTED"),
]

# Region counts, in bar order.
REGIONS = [
    ("ASIA-PACIFIC", 13, TEAL),
    ("OCEANIA", 9, BLUE),
    ("AMERICAS", 6, ORANGE),
    ("WORLD", 2, GREY),
    ("EUROPE", 1, PURPLE),
    ("AFRICA", 1, GREEN),
]
TOTAL_STORIES = 32

DATE_CHECK = (
    "Left out on purpose -- they belong to other days: COP31 collapses with no deal "
    "(Sun 22 Nov); 186 drones over Ukraine, 4 killed in Dymer (Sun 22 Nov); "
    "Hong Kong elects its Election Committee, 98.79% turnout (Sun 22 Nov); DRC and Kenya "
    "restore ties (Sun 22 Nov); Korea's education minister resigns (Sun 22 Nov); "
    "Gaza ground push (Wed 18 Nov); Hormuz: IRGC claims an MQ-9 shot down, two tankers "
    "ablaze (Sat 21 Nov); Peru 6.8 quake (Fri 20 Nov); Maluku 7.2 quake (Sat 21 Nov); "
    "EU-Indonesia trade deal (Sat 21 Nov); Fred Nile dies, 92, and MP Wadkute dies "
    "(Sat 21 Nov); Kota crash, 9 dead (Sat night); Princess of Wales 'Heal' (Sat 21 Nov); "
    "Bigfoot files (Fri 20 Nov); Wallabies beat Wales 29-26 (Sat 21 Nov); Verstappen wins "
    "in Las Vegas, ATP final, Liverpool-Man Utd (Sun 22 Nov). "
    "NOT YET DECIDED WHEN DRAWN (early Monday, WIB): the Nepal-Modi talks; the "
    "Wellington Test; the Vikings-49ers score; the flash PMIs."
)


# ---------------------------------------------------------------- scenes
def person(fb, x, y, h, shirt, skin=(214, 164, 120), pants=INK):
    """A small standing figure: head, torso, legs."""
    r = max(2, h // 8)
    fb.disc(x, y - h + r, r, skin)
    fb.rect(x - r, y - h + 2 * r, 2 * r, h // 2, shirt)
    fb.rect(x - r, y - h // 2 + 2 * r, r - 1, h // 2 - 2 * r, pants)
    fb.rect(x + 1, y - h // 2 + 2 * r, r - 1, h // 2 - 2 * r, pants)


def scene_delhi(fb, x, y, w, h):
    fb.rect(x, y, w, h, SKY)
    fb.disc(x + w - 26, y + 20, 13, (250, 214, 120))  # sun
    fb.rect(x, y + h - 26, w, 26, (120, 150, 110))    # lawn
    # India Gate-ish arch
    ax, ay, aw, ah = x + w // 2 - 26, y + h - 78, 52, 52
    fb.rect(ax, ay, aw, ah, (196, 164, 120))
    fb.rect(ax + 14, ay + 26, 24, 26, SKY)
    fb.disc(ax + 26, ay + 26, 12, SKY)
    fb.rect(ax - 4, ay - 6, aw + 8, 8, (170, 138, 96))
    # two flags
    for fx, c1, c2 in ((x + 16, (255, 153, 51), (19, 136, 8)),
                       (x + w - 30, (220, 20, 60), (0, 56, 147))):
        fb.rect(fx, y + 18, 2, 62, (90, 70, 50))
        fb.rect(fx + 2, y + 18, 22, 8, c1)
        fb.rect(fx + 2, y + 26, 22, 8, WHITE)
        fb.rect(fx + 2, y + 34, 22, 8, c2)
    # two figures shaking hands
    person(fb, x + w // 2 - 52, y + h - 26, 34, NAVY2)
    person(fb, x + w // 2 + 52, y + h - 26, 34, RED2)


def scene_factory(fb, x, y, w, h):
    fb.rect(x, y, w, h, (44, 44, 52))  # night sky
    fb.disc(x + w - 24, y + 16, 9, (240, 230, 200))
    # factory block
    fb.rect(x + 8, y + h - 52, w - 16, 52, (120, 96, 70))
    fb.rect(x + 8, y + h - 62, w - 16, 12, (96, 76, 56))
    for wx in range(x + 18, x + w - 18, 26):
        fb.rect(wx, y + h - 44, 16, 12, (255, 196, 90))
    # smoke
    for i, (sx, sy, sr) in enumerate(((x + 40, y + 22, 12), (x + 62, y + 12, 15),
                                      (x + 88, y + 26, 10), (x + w - 60, y + 18, 13))):
        fb.disc(sx, sy, sr, (150, 150, 155))
        fb.disc(sx + 6, sy - 6, sr - 3, (170, 170, 175))
    # flames
    fb.tri((x + 30, y + h - 52), (x + 44, y + h - 74), (x + 58, y + h - 52), (255, 120, 20))
    fb.tri((x + w - 70, y + h - 52), (x + w - 56, y + h - 68), (x + w - 42, y + h - 52), (255, 170, 40))
    # rescue figures with helmets
    person(fb, x + w - 40, y + h, 30, (255, 220, 40))
    fb.disc(x + w - 40, y + h - 28, 5, WHITE)
    person(fb, x + 26, y + h, 28, (40, 120, 200))
    fb.disc(x + 26, y + h - 26, 5, WHITE)


def scene_cricket(fb, x, y, w, h):
    fb.rect(x, y, w, h, SKY)
    fb.disc(x + 24, y + 16, 11, (250, 214, 120))
    fb.rect(x, y + h - 58, w, 58, (74, 148, 74))   # outfield
    fb.rect(x + w // 2 - 14, y + h - 58, 28, 58, (214, 196, 150))  # pitch
    # stumps
    for sx in (x + w // 2 - 8, x + w // 2 - 2, x + w // 2 + 4):
        fb.rect(sx, y + h - 40, 2, 12, (250, 220, 130))
    # batsman
    person(fb, x + w // 2 - 34, y + h - 22, 36, (30, 90, 170))
    fb.thick_line(x + w // 2 - 30, y + h - 40, x + w // 2 - 18, y + h - 22, 3, (160, 110, 60))
    # fielder + crowd dots
    person(fb, x + w - 34, y + h - 22, 30, RED)
    for i in range(14):
        cx = x + 8 + (i * 23) % (w - 16)
        fb.disc(cx, y + h - 52, 2, (200, 60, 60) if i % 3 == 0 else WHITE)
    # scoreboard
    fb.rect(x + 8, y + 8, 74, 20, INK)
    draw_text(fb, x + 12, y + 13, "720/9", 1, (255, 220, 90))


def _mini_sky(fb, x, y, w, h):
    fb.rect(x, y, w, h, SKY)
    fb.rect(x, y + h - 12, w, 12, (120, 150, 110))


def scene_plane(fb, x, y, w, h):
    _mini_sky(fb, x, y, w, h)
    fb.rect(x, y + h - 6, w, 3, (80, 80, 80))
    fb.poly([(x + 8, y + 18), (x + w - 14, y + 14), (x + w - 8, y + 20),
             (x + 30, y + 26), (x + 12, y + 26)], WHITE)
    fb.tri((x + w - 22, y + 12), (x + w - 10, y + 12), (x + w - 14, y + 20), RED)
    fb.disc(x + 16, y + 30, 3, (40, 40, 40))
    fb.disc(x + 34, y + 30, 3, (40, 40, 40))


def scene_poll(fb, x, y, w, h):
    fb.rect(x, y, w, h, PAPER2)
    fb.rect(x, y + h - 4, w, 4, RULE)
    bars = [(8, 26, RED), (30, 20, BLUE), (52, 14, TEAL)]
    for bx, bh, c in bars:
        fb.rect(x + bx, y + h - 6 - bh, 16, bh, c)
    draw_text(fb, x + 8, y + 4, "55-45", 1, INK)


def scene_gate(fb, x, y, w, h):
    fb.rect(x, y, w, h, (226, 220, 204))
    for gx in range(x + 6, x + w - 6, 10):
        fb.vline(gx, y + 8, h - 16, (120, 110, 96))
    fb.rect(x, y + 8, w, 4, INK)
    fb.rect(x + w // 2 - 16, y + h // 2 - 6, 32, 12, RED)
    draw_text(fb, x + w // 2 - 13, y + h // 2 - 3, "SHUT", 1, WHITE)


def scene_quake(fb, x, y, w, h):
    fb.rect(x, y, w, h, PAPER2)
    fb.rect(x, y + h // 2, w, 2, LGREY)
    pts = [(x + 4, y + h // 2), (x + 14, y + h // 2), (x + 20, y + 6),
           (x + 28, y + h - 6), (x + 36, y + h // 2), (x + 48, y + 8),
           (x + 56, y + h - 8), (x + 66, y + h // 2), (x + w - 4, y + h // 2)]
    for i in range(len(pts) - 1):
        fb.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], RED)
    draw_text(fb, x + 6, y + 4, "M4.6", 1, INK)


def scene_storm(fb, x, y, w, h):
    fb.rect(x, y, w, h, (90, 100, 120))
    fb.disc(x + 20, y + 12, 10, (220, 224, 230))
    fb.disc(x + 34, y + 9, 12, (235, 238, 242))
    fb.disc(x + 48, y + 13, 9, (220, 224, 230))
    fb.poly([(x + 34, y + 22), (x + 26, y + h - 4), (x + 34, y + h - 4),
             (x + 28, y + 26)], (255, 220, 60))
    fb.rect(x, y + h - 8, w, 8, (60, 90, 130))


def scene_chart(fb, x, y, w, h):
    fb.rect(x, y, w, h, PAPER2)
    fb.rect(x, y + h - 4, w, 4, RULE)
    vals = [10, 18, 14, 24, 20, 30]
    for i, v in enumerate(vals):
        fb.rect(x + 6 + i * 11, y + h - 6 - v, 8, v,
                BLUE if i % 2 == 0 else TEAL)
    fb.line(x + 4, y + 6, x + w - 6, y + h - 12, RED)


def scene_ballot(fb, x, y, w, h):
    fb.rect(x, y, w, h, PAPER2)
    fb.rect(x + 14, y + h - 20, w - 28, 16, (150, 110, 70))
    fb.rect(x + 14, y + h - 24, w - 28, 4, (120, 86, 52))
    fb.rect(x + w // 2 - 12, y + 4, 24, 12, WHITE)
    fb.line(x + w // 2 - 8, y + 8, x + w // 2 - 2, y + 14, RED)
    fb.line(x + w // 2 - 2, y + 14, x + w // 2 + 10, y + 4, RED)
    draw_text(fb, x + 8, y + h - 34, "VOTE", 1, INK)


def scene_parliament(fb, x, y, w, h):
    _mini_sky(fb, x, y, w, h)
    fb.rect(x + 10, y + h - 22, w - 20, 10, (200, 190, 160))
    for cx in range(x + 16, x + w - 12, 12):
        fb.rect(cx, y + h - 34, 4, 12, (220, 210, 180))
    fb.rect(x + 10, y + h - 36, w - 20, 3, (200, 190, 160))
    fb.disc(x + w // 2, y + h - 36, 12, (200, 190, 160))
    fb.rect(x + w // 2 - 1, y + h - 52, 2, 6, GOLD)


def scene_procession(fb, x, y, w, h):
    _mini_sky(fb, x, y, w, h)
    fb.rect(x, y + h - 10, w, 10, (150, 130, 100))
    for i, fx in enumerate((x + 12, x + 34, x + 56)):
        fb.rect(fx, y + 6, 2, 22, (90, 70, 50))
        fb.rect(fx + 2, y + 6, 12, 6, (255, 153, 51) if i % 2 == 0 else (30, 90, 170))
    person(fb, x + 18, y + h - 10, 22, (255, 153, 51))
    person(fb, x + 40, y + h - 10, 22, (30, 90, 170))
    person(fb, x + 62, y + h - 10, 22, RED)


def scene_football(fb, x, y, w, h):
    fb.rect(x, y, w, h, (74, 148, 74))
    fb.rect(x, y + h // 2 - 1, w, 2, WHITE)
    fb.disc(x + w // 2, y + h // 2, 10, (120, 90, 50))
    fb.line(x + w // 2 - 10, y + h // 2, x + w // 2 + 10, y + h // 2, WHITE)
    fb.line(x + w // 2 - 6, y + h // 2 - 6, x + w // 2 - 6, y + h // 2 + 6, WHITE)
    fb.line(x + w // 2 + 6, y + h // 2 - 6, x + w // 2 + 6, y + h // 2 + 6, WHITE)
    person(fb, x + 16, y + h - 6, 20, WHITE)
    person(fb, x + w - 16, y + h - 6, 20, NAVY2)


SCENES = {
    "delhi": scene_delhi, "factory": scene_factory, "cricket": scene_cricket,
    "plane": scene_plane, "poll": scene_poll, "gate": scene_gate,
    "quake": scene_quake, "storm": scene_storm, "chart": scene_chart,
    "ballot": scene_ballot, "parliament": scene_parliament,
    "procession": scene_procession, "football": scene_football,
}

# ------------------------------------------------------------------- map
CONTINENTS = [
    [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 80), (-80, 73),
     (-70, 62), (-55, 52), (-60, 45), (-75, 35), (-80, 25), (-90, 20),
     (-97, 16), (-105, 20), (-115, 28), (-125, 40), (-125, 49), (-140, 60),
     (-155, 58), (-165, 60)],
    [(-58, 64), (-45, 60), (-30, 68), (-40, 76), (-58, 74)],
    [(-80, 10), (-70, 12), (-60, 5), (-50, 0), (-40, -5), (-35, -10),
     (-40, -20), (-50, -30), (-60, -38), (-70, -50), (-73, -40), (-72, -20),
     (-80, -5)],
    [(-10, 36), (-10, 44), (0, 48), (-5, 50), (5, 53), (8, 57), (18, 56),
     (21, 55), (28, 59), (30, 70), (40, 68), (45, 60), (40, 55), (30, 45),
     (28, 40), (23, 36), (18, 40), (12, 44), (8, 44), (3, 42), (-2, 37)],
    [(-17, 15), (-10, 30), (0, 36), (10, 37), (20, 32), (30, 31), (35, 28),
     (43, 12), (51, 10), (48, 0), (40, -10), (35, -20), (30, -28),
     (20, -35), (15, -30), (12, -18), (8, -5), (9, 4), (-8, 5)],
    [(40, 68), (50, 70), (60, 70), (70, 73), (90, 75), (110, 76), (130, 72),
     (160, 70), (178, 66), (170, 60), (162, 55), (158, 50), (142, 45),
     (140, 38), (130, 35), (127, 33), (122, 38), (120, 30), (115, 22),
     (108, 18), (105, 10), (100, 8), (97, 15), (90, 22), (88, 22), (80, 15),
     (77, 8), (72, 20), (66, 25), (60, 25), (55, 26), (52, 28), (48, 30),
     (44, 29), (40, 36), (36, 36), (30, 36), (35, 42), (40, 45), (42, 55),
     (40, 60)],
    [(113, -22), (114, -30), (115, -35), (124, -33), (130, -32), (137, -35),
     (140, -38), (147, -39), (150, -37), (153, -27), (150, -22), (146, -19),
     (142, -15), (142, -11), (136, -12), (132, -12), (126, -14), (122, -17),
     (118, -20)],
]
ISLANDS = [(95, 0), (102, -2), (110, -7), (118, -5), (125, -3), (132, -4),
           (167, -38), (172, -41), (178, -18), (139, 35), (141, 38)]


def draw_map(fb, x, y, w, h):
    fb.rect(x, y, w, h, SEA)
    # graticule
    for gx in range(x + 30, x + w, 30):
        fb.vline(gx, y, h, (120, 165, 205))
    for gy in range(y + 30, y + h, 30):
        fb.hline(x, gy, w, (120, 165, 205))
    def proj(lon, lat):
        px = x + int((lon + 170) / 360.0 * w)
        py = y + int((75 - lat) / 130.0 * h)
        return (px, py)
    for cont in CONTINENTS:
        fb.poly([proj(lo, la) for lo, la in cont], LAND)
        pts = [proj(lo, la) for lo, la in cont]
        for i in range(len(pts)):
            fb.line(pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0],
                    pts[(i + 1) % len(pts)][1], LAND2)
    for lo, la in ISLANDS:
        px, py = proj(lo, la)
        fb.disc(px, py, 3, LAND)
    pins = [(1, 77, 28.6), (2, 106, -6.1), (3, 174.8, -41.3),
            (4, 151.2, -33.9), (6, 139.7, 35.7), (7, 178.4, -18.1),
            (9, 4.3, 50.8), (10, 145, -37.8), (12, 77, 28.6),
            (13, -122, 37.4), (14, 140.7, 40.8), (17, 121.5, 25),
            (18, 116.4, 39.9), (19, -74, 40.7), (20, 127, 37.5),
            (21, 30.7, 36.9), (22, 38.7, 9), (23, -77, 38.9),
            (24, 104.9, 11.5), (29, 76.8, 19.3), (32, 29.4, -3.4)]
    seen = {}
    for n, lo, la in pins:
        px, py = proj(lo, la)
        key = (px // 12, py // 12)
        if key in seen:
            px += 10
            py -= 8
        seen[key] = True
        fb.disc(px, py, 8, RED)
        fb.circle(px, py, 8, WHITE)
        s = str(n)
        draw_text(fb, px - text_w(s, 1) // 2, py - 3, s, 1, WHITE)


# ------------------------------------------------------------------ layout
M = 14
CW = W - 2 * M  # 996


def badge(fb, x, y, s):
    w = text_w(s, 1) + 10
    fb.rect(x, y, w, 13, RED if s in ("REPORTED", "CLAIM") else NAVY)
    draw_text(fb, x + 5, y + 3, s, 1, WHITE)
    return w


def build():
    fb = FB(W, H, PAPER)
    # --- top bar
    fb.rect(0, 0, W, 20, NAVY)
    draw_text(fb, M, 6, "THE WORLD IN ONE DAY", 1, GOLD)
    draw_text(fb, W - M - text_w("ONE PAGE - EVERY STORY DATED", 1), 6,
              "ONE PAGE - EVERY STORY DATED", 1, WHITE)
    # --- count strip
    draw_text_center(fb, W // 2, 26,
                     "%d STORIES  -  %d REGIONS  -  EVERY ONE DATED MONDAY 23 NOVEMBER 2026"
                     % (TOTAL_STORIES, len(REGIONS)), 2, INK)
    fb.hline(M, 40, CW, RULE)
    # --- masthead (serif)
    title = "Monday 23 November 2026"
    tw = serif_w(title, 32)
    draw_serif(fb, (W - tw) // 2, 44, title, 32, NAVY)
    # --- red subhead
    draw_text_center(fb, W // 2, 108,
                     "Shah meets Modi  -  Search resumes in Serang  -  India hunt eight wickets",
                     2, RED)
    fb.hline(M, 124, CW, RULE)
    # --- key numbers
    nums = [("32", "STORIES"), ("6", "REGIONS"), ("24", "BODY BAGS"),
            ("29", "STILL MISSING"), ("720/9", "INDIA'S TOTAL"),
            ("8", "WICKETS NEEDED")]
    cell = CW // 6
    for i, (big, small) in enumerate(nums):
        cx = M + i * cell
        draw_text_center(fb, cx + cell // 2, 132, big, 4, RED)
        draw_text_center(fb, cx + cell // 2, 158, small, 1, INK)
        if i:
            fb.vline(cx, 128, 38, LGREY)
    fb.hline(M, 168, CW, RULE)
    # --- region bar
    bx = M
    for name, cnt, col in REGIONS:
        seg = CW * cnt // TOTAL_STORIES
        fb.rect(bx, 172, seg, 18, col)
        lab = "%s %d" % (name if cnt >= 2 else name[:2], cnt)
        if seg >= text_w(lab, 1) + 4:
            draw_text(fb, bx + (seg - text_w(lab, 1)) // 2, 177, lab, 1, WHITE)
        bx += seg
    # --- timeline strip
    fb.rect(M, 194, CW, 20, NAVY)
    draw_text(fb, M + 6, 200, "THE DAY IN UTC", 1, GOLD)
    draw_text(fb, M + 108, 200,
              "00:00 Serang search resumes  -  01:20 Vikings at 49ers kick off  -  "
              "MIDDAY Sydney storms due  -  21:00 NY Fed's Williams speaks", 1, WHITE)
    # --- heroes
    hy, hh = 218, 214
    colw = (CW - 16) // 3
    for i, st in enumerate(HEROES):
        hx = M + i * (colw + 8)
        # illustration
        SCENES[st["scene"]](fb, hx, hy, colw, 92)
        fb.rect(hx, hy + 92, colw, 2, RULE)
        # red banner
        fb.rect(hx, hy + 94, colw, 15, RED)
        draw_text(fb, hx + 6, hy + 98, st["kicker"], 1, WHITE)
        badge(fb, hx + colw - text_w(st["badge"], 1) - 15, hy + 4, st["badge"])
        # kicker line
        draw_text(fb, hx, hy + 114,
                  "%d %s - %s" % (st["n"], st["place"], st["region"]), 1, RED)
        # headline, bold, max 2 lines
        y = hy + 128
        for ln in wrap(st["head"], 2, colw)[:2]:
            draw_text_bold(fb, hx, y, ln, 2, INK)
            y += 17
        # body, max 4 lines
        y = hy + 166
        for ln in wrap(st["body"], 1, colw)[:4]:
            draw_text(fb, hx, y, ln, 1, INK)
            y += 9
        draw_text(fb, hx, hy + hh - 10, "Sources: " + st["src"], 1, GREY)
    # --- secondaries: 2 rows x 5
    sy, sh, sgap = 440, 100, 6
    scolw = (CW - 4 * 4) // 5
    for i, st in enumerate(SECONDARIES):
        row, col = divmod(i, 5)
        sx = M + col * (scolw + 4)
        yy = sy + row * (sh + sgap)
        SCENES[st["scene"]](fb, sx, yy, scolw, 40)
        fb.rect(sx, yy + 40, scolw, 1, LGREY)
        draw_text(fb, sx, yy + 44,
                  "%d %s" % (st["n"], st["place"]), 1, RED)
        y = yy + 55
        for ln in wrap(st["head"], 1, scolw)[:2]:
            draw_text_bold(fb, sx, y, ln, 1, INK)
            y += 9
        y = yy + 74
        for ln in wrap(st["body"], 1, scolw)[:2]:
            draw_text(fb, sx, y, ln, 1, INK)
            y += 9
        draw_text(fb, sx, yy + sh - 8, st["src"], 1, GREY)
    # --- map + more list
    my = 652
    fb.rect(M, my, 330, 264, PAPER2)
    fb.rect(M, my, 330, 2, RULE)
    draw_text(fb, M + 8, my + 8, "WHERE IT HAPPENED", 2, INK)
    draw_text(fb, M + 8, my + 24, "Pins match story numbers", 1, GREY)
    draw_map(fb, M + 6, my + 38, 318, 218)
    lx = M + 338
    draw_text(fb, lx, my + 8,
              "ALSO ON MONDAY 23 NOVEMBER - 19 MORE STORIES", 2, INK)
    fb.hline(lx, my + 26, W - M - lx, RULE)
    # two columns of the more-list
    colw2 = (W - M - lx - 12) // 2
    for i, (place, region, head, src, status) in enumerate(MORE):
        cidx, ridx = divmod(i, 10)
        ix = lx + cidx * (colw2 + 12)
        iy = my + 34 + ridx * 23
        n = 14 + i
        draw_text_bold(fb, ix, iy, "%d." % n, 1, RED)
        tx = ix + text_w("%d. " % n, 1)
        for j, ln in enumerate(wrap(head, 1, colw2 - text_w("%d. " % n, 1))[:1]):
            draw_text(fb, tx, iy, ln, 1, INK)
        draw_text(fb, tx, iy + 10, "%s - %s [%s]" % (place, src, status),
                  1, GREY)
    # --- DATE CHECK
    dy = 922
    fb.rect(M, dy, CW, 78, PAPER2)
    fb.rect(M, dy, CW, 2, RED)
    fb.rect(M, dy + 76, CW, 2, RED)
    fb.rect(M, dy, 2, 78, RED)
    fb.rect(M + CW - 2, dy, 2, 78, RED)
    draw_text(fb, M + 8, dy + 7, "DATE CHECK - READ THIS FIRST", 1, RED2)
    y = dy + 19
    for ln in wrap(DATE_CHECK, 1, CW - 16)[:6]:
        draw_text(fb, M + 8, y, ln, 1, INK)
        y += 9
    # --- footer
    draw_text(fb, M, 1006,
              "Sources: Reuters, AP, AFP, Al Jazeera, BBC, The Guardian, ABC, AAP, "
              "ESPNcricinfo, Cricbuzz, Xinhua, IANS, official releases.", 1, GREY)
    draw_text(fb, M, 1016,
              "REPORTED = the day's wires  -  CLAIM = one side's account  -  "
              "FORECAST = still to happen when drawn. "
              "Pictures and map: original, drawn in code.", 1, GREY)
    return fb


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    fb = build()
    path = os.path.join(outdir, "entry.png")
    size = write_png(fb, path)
    print("wrote %s (%d bytes)" % (path, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
