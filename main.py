#!/usr/bin/env python3
"""The World in One Day -- Monday 23 November 2026. Version 2.

A one-page newspaper drawn entirely in code (Python 3.13, standard
library only). It sums up the world news of Monday 23 November 2026
in a single 1024x1024 image, written to /output/entry.png
(MAKEFUN_OUTPUT_DIR outside the grader).

This is the second version of the entry. It was drawn late on
Monday night WIB, once the day had actually happened, so it leads
with what Monday really produced: Nvidia's board voting to bring
Jensen Huang back as chief executive, Kyiv confirming it sank a
Russian corvette off Libya, and the Wellington Test ending in a
draw. Thirty-eight verified stories across seven regions, no
forecasts dressed up as news, and a DATE CHECK box that says
plainly which big stories belong to other days.

Every story on the page was verified against a real wire or outlet
(Reuters, AP, AFP, CNN, WSJ, BBC, ESPNcricinfo, S&P Global,
Stats NZ, USGS, UN News, Radio Nepal, IANS, Newspoll, BOM, PCHR,
CAF, official releases). One-sided claims are labelled CLAIM and
attributed; everything else is REPORTED or OFFICIAL.

Layout follows the classic one-page front page: a top bar, a
count strip naming the stories and regions, a serif masthead with
the day, a red subhead with the three top stories, a key-numbers
strip, a coloured region bar, a timeline of the day in UTC, three
hero stories with drawn illustrations, ten secondaries, a world
map with numbered pins, a numbered list of the remaining stories,
a DATE CHECK box and a sources footer.

Everything is drawn by hand in this file: its own framebuffer
rasterizer, its own hand-typed 5x7 bitmap font, its own vector
serif face for the masthead, and its own PNG encoder. No network,
no randomness, no wall-clock time: two runs write identical bytes.
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (248, 244, 234)      # warm newsprint cream
PANEL = (255, 253, 247)      # lighter cream panel
INK = (24, 24, 24)           # near-black text
NAVY = (20, 36, 76)          # masthead + top bar
NAVY2 = (28, 50, 100)
RED = (176, 32, 26)          # subhead, banners, rules
REDDK = (138, 20, 16)
GOLD = (200, 160, 64)
GREY = (108, 106, 98)
LGREY = (212, 208, 196)
RULE = (58, 56, 50)
TEAL = (16, 108, 108)
BLUE = (36, 88, 166)
ORANGE = (194, 108, 18)
PURPLE = (108, 72, 148)
GREEN = (44, 126, 64)
SKY = (170, 206, 233)
SEA = (94, 148, 194)
SEADK = (70, 120, 170)
LAND = (233, 223, 197)
LAND2 = (212, 198, 166)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
NVGRN = (118, 185, 0)        # Nvidia green
FLAME = (255, 120, 20)
SAND = (214, 196, 150)


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
            dy = yy - cy
            if abs(dy) > r:
                continue
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, yy, 2 * dx + 1, 1, c)

    def circle(self, cx, cy, r, c):
        n = max(16, int(2 * math.pi * r))
        px, py = None, None
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            qx = int(cx + r * math.cos(a))
            qy = int(cy + r * math.sin(a))
            if px is not None:
                self.line(px, py, qx, qy, c)
            px, py = qx, qy

    def poly(self, pts, c):
        """Fill a polygon with a scanline fill."""
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

    def stroke(self, x0, y0, x1, y1, w, c):
        """A square-capped thick segment, drawn as a filled quad.

        Used for the serif masthead, where round caps would look
        handwritten. Joints between segments are filled with a disc
        by the caller.
        """
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        if length < 0.5:
            self.disc(x0, y0, max(1, w // 2), c)
            return
        nx = -dy / length * w / 2
        ny = dx / length * w / 2
        self.poly([(int(x0 + nx), int(y0 + ny)),
                   (int(x1 + nx), int(y1 + ny)),
                   (int(x1 - nx), int(y1 - ny)),
                   (int(x0 - nx), int(y0 - ny))], c)


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
# Each glyph: 7 rows of 5 cells, '1' = ink. Hand-typed.
FONT = {}


def _f(ch, rows):
    FONT[ch] = rows


_f('A', ("01110", "10001", "10001", "11111", "10001", "10001", "10001"))
_f('B', ("11110", "10001", "10001", "11110", "10001", "10001", "11110"))
_f('C', ("01110", "10001", "10000", "10000", "10000", "10001", "01110"))
_f('D', ("11110", "10001", "10001", "10001", "10001", "10001", "11110"))
_f('E', ("11111", "10000", "10000", "11110", "10000", "10000", "11111"))
_f('F', ("11111", "10000", "10000", "11110", "10000", "10000", "10000"))
_f('G', ("01110", "10001", "10000", "10111", "10001", "10001", "01111"))
_f('H', ("10001", "10001", "10001", "11111", "10001", "10001", "10001"))
_f('I', ("01110", "00100", "00100", "00100", "00100", "00100", "01110"))
_f('J', ("00111", "00010", "00010", "00010", "00010", "10010", "01100"))
_f('K', ("10001", "10010", "10100", "11000", "10100", "10010", "10001"))
_f('L', ("10000", "10000", "10000", "10000", "10000", "10000", "11111"))
_f('M', ("10001", "11011", "10101", "10101", "10001", "10001", "10001"))
_f('N', ("10001", "11001", "10101", "10011", "10001", "10001", "10001"))
_f('O', ("01110", "10001", "10001", "10001", "10001", "10001", "01110"))
_f('P', ("11110", "10001", "10001", "11110", "10000", "10000", "10000"))
_f('Q', ("01110", "10001", "10001", "10001", "10101", "10010", "01101"))
_f('R', ("11110", "10001", "10001", "11110", "10100", "10010", "10001"))
_f('S', ("01111", "10000", "10000", "01110", "00001", "00001", "11110"))
_f('T', ("11111", "00100", "00100", "00100", "00100", "00100", "00100"))
_f('U', ("10001", "10001", "10001", "10001", "10001", "10001", "01110"))
_f('V', ("10001", "10001", "10001", "10001", "10001", "01010", "00100"))
_f('W', ("10001", "10001", "10001", "10101", "10101", "11011", "10001"))
_f('X', ("10001", "10001", "01010", "00100", "01010", "10001", "10001"))
_f('Y', ("10001", "10001", "01010", "00100", "00100", "00100", "00100"))
_f('Z', ("11111", "00001", "00010", "00100", "01000", "10000", "11111"))
_f('a', ("00000", "00000", "01110", "00001", "01111", "10001", "01111"))
_f('b', ("10000", "10000", "11110", "10001", "10001", "10001", "11110"))
_f('c', ("00000", "00000", "01110", "10000", "10000", "10001", "01110"))
_f('d', ("00001", "00001", "01111", "10001", "10001", "10001", "01111"))
_f('e', ("00000", "00000", "01110", "10001", "11111", "10000", "01110"))
_f('f', ("00110", "01001", "01000", "11110", "01000", "01000", "01000"))
_f('g', ("00000", "01111", "10001", "10001", "01111", "00001", "01110"))
_f('h', ("10000", "10000", "11110", "10001", "10001", "10001", "10001"))
_f('i', ("00100", "00000", "01100", "00100", "00100", "00100", "01110"))
_f('j', ("00010", "00000", "00110", "00010", "00010", "00010", "01100"))
_f('k', ("10000", "10000", "10010", "10100", "11000", "10100", "10010"))
_f('l', ("01100", "00100", "00100", "00100", "00100", "00100", "01110"))
_f('m', ("00000", "00000", "11010", "10101", "10101", "10101", "10101"))
_f('n', ("00000", "00000", "11110", "10001", "10001", "10001", "10001"))
_f('o', ("00000", "00000", "01110", "10001", "10001", "10001", "01110"))
_f('p', ("00000", "11110", "10001", "10001", "11110", "10000", "10000"))
_f('q', ("00000", "00000", "01111", "10001", "10001", "01111", "00001"))
_f('r', ("00000", "00000", "10110", "11001", "10000", "10000", "10000"))
_f('s', ("00000", "00000", "01111", "10000", "01110", "00001", "11110"))
_f('t', ("01000", "01000", "11110", "01000", "01000", "01001", "00110"))
_f('u', ("00000", "00000", "10001", "10001", "10001", "10011", "01101"))
_f('v', ("00000", "00000", "10001", "10001", "10001", "01010", "00100"))
_f('w', ("00000", "00000", "10001", "10101", "10101", "10101", "01010"))
_f('x', ("00000", "00000", "10001", "01010", "00100", "01010", "10001"))
_f('y', ("00000", "00000", "10001", "10001", "01111", "00001", "01110"))
_f('z', ("00000", "00000", "11111", "00010", "00100", "01000", "11111"))
_f('0', ("01110", "10001", "10011", "10101", "11001", "10001", "01110"))
_f('1', ("00100", "01100", "00100", "00100", "00100", "00100", "01110"))
_f('2', ("01110", "10001", "00001", "00110", "01000", "10000", "11111"))
_f('3', ("11110", "00001", "00001", "01110", "00001", "00001", "11110"))
_f('4', ("00010", "00110", "01010", "10010", "11111", "00010", "00010"))
_f('5', ("11111", "10000", "11110", "00001", "00001", "10001", "01110"))
_f('6', ("01110", "10000", "10000", "11110", "10001", "10001", "01110"))
_f('7', ("11111", "00001", "00010", "00100", "01000", "01000", "01000"))
_f('8', ("01110", "10001", "10001", "01110", "10001", "10001", "01110"))
_f('9', ("01110", "10001", "10001", "01111", "00001", "00001", "01110"))
_f('.', ("00000", "00000", "00000", "00000", "00000", "01100", "01100"))
_f(',', ("00000", "00000", "00000", "00000", "01100", "00100", "01000"))
_f(':', ("00000", "01100", "01100", "00000", "01100", "01100", "00000"))
_f(';', ("00000", "01100", "01100", "00000", "01100", "00100", "01000"))
_f('!', ("00100", "00100", "00100", "00100", "00100", "00000", "00100"))
_f('?', ("01110", "10001", "00001", "00110", "00100", "00000", "00100"))
_f("'", ("00100", "00100", "01000", "00000", "00000", "00000", "00000"))
_f('"', ("01010", "01010", "00000", "00000", "00000", "00000", "00000"))
_f('-', ("00000", "00000", "00000", "01110", "00000", "00000", "00000"))
_f('(', ("00010", "00100", "01000", "01000", "01000", "00100", "00010"))
_f(')', ("01000", "00100", "00010", "00010", "00010", "00100", "01000"))
_f('/', ("00001", "00010", "00010", "00100", "01000", "01000", "10000"))
_f('%', ("11001", "11010", "00010", "00100", "01000", "01011", "10011"))
_f('&', ("01100", "10010", "10100", "01000", "10101", "10010", "01101"))
_f('+', ("00000", "00100", "00100", "11111", "00100", "00100", "00000"))
_f('=', ("00000", "00000", "11111", "00000", "11111", "00000", "00000"))
_f('*', ("00000", "10101", "01110", "11111", "01110", "10101", "00000"))
_f('#', ("01010", "01010", "11111", "01010", "11111", "01010", "01010"))
_f('@', ("01110", "10001", "10111", "10101", "10110", "10000", "01110"))
_f('_', ("00000", "00000", "00000", "00000", "00000", "00000", "11111"))
_f('[', ("01110", "01000", "01000", "01000", "01000", "01000", "01110"))
_f(']', ("01110", "00010", "00010", "00010", "00010", "00010", "01110"))
_f('$', ("00100", "01111", "10100", "01110", "00101", "11110", "00100"))
_f(' ', ("00000", "00000", "00000", "00000", "00000", "00000", "00000"))

CELL = 6  # 5 px glyph + 1 px gap, times scale


def text_w(s, scale):
    return len(s) * CELL * scale


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
        cx += CELL * scale
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
    lh = leading if leading is not None else 9 * scale
    lines = wrap(s, scale, max_w)
    if max_lines is not None:
        lines = lines[:max_lines]
    for ln in lines:
        draw_text(fb, x, y, ln, scale, color)
        y += lh
    return y


# ------------------------------------------------------- vector serif face
# The masthead is set in a hand-drawn serif face: each glyph is a
# list of strokes, each stroke a polyline on a 0..64 wide, 0..80
# tall grid (baseline 80, x-height top 30, descenders to 100).
# Strokes are drawn with square caps and small serif ticks at the
# feet and heads of the stems, so the big date reads as a newspaper
# serif rather than a pixel font or handwriting.
SERIF_W = {
    'M': 64, 'o': 48, 'n': 48, 'd': 48, 'a': 46, 'y': 48, ' ': 22,
    '2': 48, '3': 46, 'N': 62, 'v': 50, 'e': 46, 'm': 66, 'b': 48,
    'r': 40, '6': 46, '0': 48,
}
# Each entry: list of (points, closed) strokes.
SERIF = {
    'M': [([(4, 78), (4, 4), (31, 44), (58, 4), (58, 78)], False)],
    'o': [([(22, 30), (32, 30), (40, 38), (42, 54), (40, 68), (32, 76),
           (22, 76), (12, 68), (10, 54), (12, 38)], True)],
    'n': [([(6, 78), (6, 40), (10, 32), (20, 30), (30, 32), (38, 40),
           (42, 52), (42, 78)], False)],
    'd': [([(20, 30), (30, 32), (36, 42), (36, 62), (30, 74), (20, 76),
           (10, 74), (4, 62), (4, 42), (10, 32)], True),
          ([(42, 4), (42, 78)], False)],
    'a': [([(20, 32), (32, 34), (38, 46), (38, 64), (32, 76), (20, 78),
           (10, 74), (4, 62), (4, 46), (10, 34)], True),
          ([(38, 34), (38, 78)], False)],
    'y': [([(6, 30), (22, 62), (40, 30)], False),
          ([(22, 62), (12, 96)], False)],
    '2': [([(8, 14), (16, 4), (30, 4), (40, 12), (36, 26), (14, 62),
           (8, 78), (42, 78)], False)],
    '3': [([(10, 6), (22, 2), (34, 6), (40, 16), (34, 30), (24, 34),
           (34, 40), (40, 52), (36, 68), (26, 78), (12, 76), (6, 68)],
          False)],
    'N': [([(6, 78), (6, 4), (56, 78), (56, 4)], False)],
    'v': [([(4, 30), (24, 78), (44, 30)], False)],
    'e': [([(40, 52), (36, 34), (28, 30), (16, 30), (6, 38), (4, 54),
           (8, 70), (20, 78), (34, 76), (42, 66)], False),
          ([(6, 52), (38, 52)], False)],
    'm': [([(4, 78), (4, 40), (8, 32), (18, 30), (26, 34), (30, 42),
           (30, 78)], False),
          ([(30, 42), (36, 32), (46, 30), (54, 34), (60, 42), (60, 78)],
           False)],
    'b': [([(4, 4), (4, 78)], False),
          ([(4, 54), (12, 32), (24, 30), (36, 34), (42, 48), (42, 62),
           (36, 76), (24, 78), (12, 76), (4, 64)], True)],
    'r': [([(4, 78), (4, 40), (8, 32), (18, 30), (28, 32), (34, 38)],
          False)],
    '6': [([(38, 10), (26, 2), (14, 8), (6, 22), (4, 42), (8, 60),
           (18, 76), (30, 78), (40, 70), (44, 56), (40, 42), (30, 38),
           (18, 40), (10, 48), (8, 58)], False)],
    '0': [([(24, 2), (36, 4), (44, 16), (44, 62), (36, 76), (24, 78),
           (12, 76), (4, 62), (4, 16), (12, 4)], True)],
}
# Serif ticks: (x, y, half-length) horizontal bars at stem ends.
SERIF_TICKS = {
    'M': [(4, 4, 6), (58, 4, 6), (4, 78, 6), (58, 78, 6)],
    'N': [(6, 4, 6), (56, 4, 6), (6, 78, 6), (56, 78, 6)],
    'n': [(6, 78, 5), (42, 78, 5), (6, 32, 5)],
    'd': [(42, 4, 5), (42, 78, 5)],
    'a': [(38, 78, 5)],
    'y': [(12, 96, 5)],
    '2': [(8, 78, 6), (42, 78, 6)],
    '3': [(10, 6, 5), (12, 76, 5)],
    'v': [(4, 30, 5), (44, 30, 5)],
    'e': [(4, 54, 5)],
    'm': [(4, 78, 5), (30, 78, 5), (60, 78, 5)],
    'b': [(4, 4, 5), (4, 78, 5)],
    'r': [(4, 78, 5)],
    '6': [(38, 10, 5)],
    'o': [],
    '0': [],
}


def serif_w(s, scale):
    tot = 0
    for ch in s:
        tot += SERIF_W.get(ch, 40) * scale // 50
    return tot


def draw_serif(fb, x, y, s, scale, color):
    """Draw the masthead face. Grid units map at scale/50 px."""
    w = max(3, scale // 4)  # bold stroke weight
    cx = x
    for ch in s:
        if ch == ' ':
            cx += SERIF_W[' '] * scale // 50
            continue
        for pts, closed in SERIF[ch]:
            scaled = [(cx + px * scale // 50, y + py * scale // 50)
                      for px, py in pts]
            segs = list(zip(scaled, scaled[1:]))
            if closed:
                segs.append((scaled[-1], scaled[0]))
            for (x0, y0), (x1, y1) in segs:
                fb.stroke(x0, y0, x1, y1, w, color)
            for (jx, jy) in scaled:
                fb.disc(jx, jy, max(1, w // 2), color)
        for (tx, ty, hl) in SERIF_TICKS.get(ch, []):
            fb.rect(cx + (tx - hl) * scale // 50, y + ty * scale // 50,
                    2 * hl * scale // 50, max(2, w // 2), color)
        cx += SERIF_W[ch] * scale // 50
    return cx - x


# ------------------------------------------------------------- story data
# Every story verified against a real outlet on 23-24 Nov 2026.
# Status: OFFICIAL / REPORTED / CLAIM. No forecasts on this page:
# what had not happened yet when the page was drawn is named in
# the DATE CHECK box instead.
HEROES = [
    dict(
        n=1, place="SANTA CLARA, USA", region="NORTH AMERICA",
        kicker="BOARD VOTES MONDAY", badge="REPORTED",
        head="Huang is back: Nvidia reinstates its ousted chief",
        body=("The board voted unanimously to bring Jensen Huang back as "
              "chief executive, 11 days after he quit over affairs "
              "including one with an alleged Chinese spy. Shares jumped "
              "33% and the Nasdaq 6%."),
        src="Reuters - WSJ - CNN",
        scene="chip",
    ),
    dict(
        n=2, place="OFF BENGHAZI, LIBYA", region="EUROPE",
        kicker="SEVEN SEA DRONES", badge="REPORTED",
        head="Kyiv says it sank a Russian corvette off Libya",
        body=("Zelensky confirmed on Monday that seven naval drones sank "
              "the Merkury, a corvette commissioned in 2023, off "
              "Benghazi, destroying a Ka-27 helicopter. A cargo ship "
              "said to carry weapons was also hit."),
        src="CNN - France 24 - UN News",
        scene="ship",
    ),
    dict(
        n=3, place="WELLINGTON, NEW ZEALAND", region="OCEANIA",
        kicker="DAY 5 - DRAWN", badge="REPORTED",
        head="Mitchell and Phillips bat out a draw for New Zealand",
        body=("The hosts closed on 239 for 5, batting 120 overs to save "
              "the Test after India's 720 for 9 declared, the biggest "
              "innings total ever in New Zealand. Mitchell made 49 off "
              "186 balls, Phillips 26 off 126."),
        src="ESPNcricinfo - AP - ICC",
        scene="cricket",
    ),
]

SECONDARIES = [
    dict(n=4, place="SERANG, INDONESIA", region="ASIA", kicker="24 DEAD",
         badge="REPORTED",
         head="Serang fire: 24 dead confirmed as search goes on",
         body="About 30 are still missing at the candy factory.",
         src="Reuters - AP", scene="factory"),
    dict(n=5, place="NEW DELHI, INDIA", region="ASIA", kicker="STATE VISIT",
         badge="REPORTED",
         head="Modi offers Nepal $1.6bn for flood rebuilding",
         body="Shah and Modi talk energy, rail and trade in Delhi.",
         src="Radio Nepal - IANS", scene="delhi"),
    dict(n=6, place="KYIV, UKRAINE", region="EUROPE", kicker="DAY 1,734",
         badge="REPORTED",
         head="Russian strikes kill 14 across Ukraine",
         body="Ten die as a five-storey block collapses in Dymer.",
         src="Reuters - AP", scene="kyiv"),
    dict(n=7, place="GAZA", region="MIDDLE EAST", kicker="JABALIA CAMP",
         badge="REPORTED",
         head="Israeli strike kills UNRWA worker in Gaza",
         body="Adel Al-Helo dies near a water well; three wounded.",
         src="Reuters", scene="gaza"),
    dict(n=8, place="MEXICO CITY, MEXICO", region="NORTH AMERICA",
         kicker="SUNDAY NIGHT", badge="REPORTED",
         head="49ers rout Vikings 35-10 in Mexico City",
         body="Purdy throws three touchdowns; 49ers now 9-1.",
         src="NBC Sports - AP", scene="football"),
    dict(n=9, place="EUROPE", region="EUROPE", kicker="FLASH PMI",
         badge="OFFICIAL",
         head="Eurozone holds at 51.7; Germany hits 55.0",
         body="France falls to 46.2, a six-month low.",
         src="S&P Global - Reuters", scene="chart"),
    dict(n=10, place="NEW YORK, USA", region="NORTH AMERICA",
         kicker="FLASH PMI", badge="OFFICIAL",
         head="US growth cools: flash PMI down to 54.6",
         body="A four-month low, yet still near 3% GDP pace.",
         src="S&P Global - Reuters", scene="chart2"),
    dict(n=11, place="WELLINGTON, NZ", region="OCEANIA", kicker="Q3 RETAIL",
         badge="OFFICIAL",
         head="NZ shops enjoy best quarter since 2021",
         body="Sales volumes jump 2.2%, four times forecast.",
         src="Stats NZ", scene="retail"),
    dict(n=12, place="CANBERRA, AUSTRALIA", region="OCEANIA",
         kicker="NEWSPOLL", badge="REPORTED",
         head="Taylor passes Albanese as preferred PM",
         body="The Coalition leader leads 42-41 for the first time.",
         src="Newspoll - The Australian", scene="poll"),
    dict(n=13, place="VANUATU", region="OCEANIA", kicker="M6.5",
         badge="REPORTED",
         head="Deep M6.5 quake shakes Vanuatu region",
         body="The tremor struck 598 km down; no tsunami alert.",
         src="USGS", scene="quake"),
]

# The rest of the day, numbered on from the secondaries.
MORE = [
    ("BRASILIA, BRAZIL", "SOUTH AMERICA",
     "Bolsonaro stable in ICU; endoscopy 'positive'", "The Times", "REPORTED"),
    ("BRASILIA, BRAZIL", "SOUTH AMERICA",
     "Lower house votes on Lula's fiscal bill", "Rio Times", "REPORTED"),
    ("CUCUTA, COLOMBIA", "SOUTH AMERICA",
     "Drones reportedly hit police command", "Rio Times", "REPORTED"),
    ("LIMA, PERU", "SOUTH AMERICA",
     "Bank group IFS profit flat at $134m in Q3", "Rio Times", "REPORTED"),
    ("CENTRAL ANDES, PERU", "SOUTH AMERICA",
     "Quake toll stands at one as aftershocks go on", "Rio Times", "REPORTED"),
    ("ABUJA, NIGERIA", "AFRICA",
     "Central bank sets $11m floor for stablecoins", "Rio Times", "REPORTED"),
    ("SAO TOME", "AFRICA",
     "Americo Ramos reappointed prime minister", "C54 News", "REPORTED"),
    ("NAIROBI, KENYA", "AFRICA",
     "Kenya discharges its last Ebola patient", "C54 News", "REPORTED"),
    ("ACCRA, GHANA", "AFRICA",
     "Ghana unveils 'Heritage Series' banknotes", "C54 News", "REPORTED"),
    ("LAGOS, NIGERIA", "AFRICA",
     "AFRIFF film festival opens with 23 features", "C54 News", "REPORTED"),
    ("BANJUL, GAMBIA", "AFRICA",
     "Gambia declares a monkeypox outbreak", "Access24", "REPORTED"),
    ("NAIROBI, KENYA", "AFRICA",
     "Police fire tear gas at small Nairobi protest", "Access24", "REPORTED"),
    ("SEOUL, KOREA", "ASIA",
     "Korail slowdown starts; metro strike set Wed", "Aju Press", "REPORTED"),
    ("TOKYO, JAPAN", "ASIA",
     "Japan's markets shut for Labor Thanksgiving", "JPX", "OFFICIAL"),
    ("SYDNEY, AUSTRALIA", "OCEANIA",
     "Severe storm warning: hail, gusts, floods", "BOM", "OFFICIAL"),
    ("HONG KONG", "ASIA",
     "Beijing hails Sunday's election committee vote", "China Daily", "REPORTED"),
    ("ANTALYA, TURKIYE", "EUROPE",
     "COP31 fallout: focus shifts to COP32 in Addis", "UN News", "REPORTED"),
    ("GAZA", "MIDDLE EAST",
     "Report: 15 Palestinians killed 19-22 Nov", "PCHR", "REPORTED"),
    ("PERM, RUSSIA", "EUROPE",
     "Ukrainian drone kills one in Perm region", "Reuters", "REPORTED"),
    ("ABU DHABI", "MIDDLE EAST",
     "Kremlin: new trilateral talks may be held soon", "Reuters", "REPORTED"),
    ("MELBOURNE, AUSTRALIA", "OCEANIA",
     "Victoria: Coalition leads 58-42, six days out", "Redbridge", "REPORTED"),
    ("LONDON, UK", "EUROPE",
     "UK flash PMI eases to 52.3 from 52.9", "S&P Global", "OFFICIAL"),
    ("MEXICO CITY, MEXICO", "NORTH AMERICA",
     "Mexico keeps arresting CJNG commanders", "Rio Times", "REPORTED"),
    ("ABUJA, NIGERIA", "AFRICA",
     "Tinubu vows power and water fix after outage", "Rio Times", "REPORTED"),
    ("CAIRO, EGYPT", "AFRICA",
     "Coca-Cola named AFCON 2027 sponsor", "CAF - APO", "REPORTED"),
]

# Region counts, in bar order. They sum to TOTAL_STORIES.
REGIONS = [
    ("AFRICA", 9, GREEN),
    ("OCEANIA", 6, BLUE),
    ("EUROPE", 6, PURPLE),
    ("ASIA", 5, TEAL),
    ("SOUTH AMERICA", 5, ORANGE),
    ("NORTH AMERICA", 4, NAVY2),
    ("MIDEAST", 3, REDDK),
]
TOTAL_STORIES = 38

DATE_CHECK = (
    "Left out on purpose -- they belong to other days: COP31 talks collapse "
    "with no deal (Sun 22 Nov); Liverpool 4-0 Man Utd (Sun 22 Nov); Hong Kong "
    "elects its Election Committee, 98.79% turnout (Sun 22 Nov); the Merkury "
    "is hit at Benghazi port (Sun 22 Nov) -- Kyiv confirmed it Monday; the "
    "Serang factory fire (Sat 21 Nov) -- Monday's death toll is on this "
    "page; Bolsonaro is admitted to intensive care (Fri 20 Nov) -- Monday's "
    "update is on this page; Peru's 6.7 quake (Fri 20 Nov); Norway court "
    "voids three oil licences (Fri 13 Nov); Nigeria boat disaster, 24 dead "
    "(Sun 22 Nov); Sparta II ablaze off Finland (Sun 22 Nov); Cyclone Akvan "
    "(Sat 21 Nov). NOT YET DECIDED WHEN DRAWN (late Monday, WIB): HPE's Q4 "
    "results, due after the close; Dell and HP report Tuesday; the Seoul "
    "Metro strike decision, Wednesday."
)


# ---------------------------------------------------------------- scenes
def person(fb, x, y, h, shirt, skin=(214, 164, 120), pants=INK):
    """A small standing figure: head, torso, legs."""
    r = max(2, h // 8)
    fb.disc(x, y - h + r, r, skin)
    fb.rect(x - r, y - h + 2 * r, 2 * r, h // 2, shirt)
    fb.rect(x - r, y - h // 2 + 2 * r, r - 1, h // 2 - 2 * r, pants)
    fb.rect(x + 1, y - h // 2 + 2 * r, r - 1, h // 2 - 2 * r, pants)


def scene_chip(fb, x, y, w, h):
    """A GPU on a dark board, with a green arrow climbing."""
    fb.rect(x, y, w, h, (14, 22, 44))
    # gold circuit traces
    for ty in (y + 12, y + h - 12):
        fb.hline(x + 8, ty, w - 16, (150, 120, 50))
    fb.vline(x + 14, y + 8, h - 16, (150, 120, 50))
    fb.vline(x + w - 14, y + 8, h - 16, (150, 120, 50))
    # climbing arrow, drawn before the chip so the chip sits on top
    ax0, ay0 = x + 16, y + h - 16
    fb.thick_line(ax0, ay0, x + w - 40, y + 14, 4, NVGRN)
    fb.tri((x + w - 40, y + 14), (x + w - 56, y + 16), (x + w - 42, y + 30), NVGRN)
    # the chip
    cx, cy, s = x + w // 2 - 30, y + h // 2 - 26, 52
    for i in range(6):
        fb.rect(cx - 6, cy + 4 + i * 8, 6, 4, GOLD)
        fb.rect(cx + s, cy + 4 + i * 8, 6, 4, GOLD)
    fb.rect(cx, cy, s, s, NVGRN)
    fb.rect(cx + 8, cy + 8, s - 16, s - 16, (60, 110, 0))
    draw_text(fb, cx + 14, cy + 22, "NVDA", 1, WHITE)
    draw_text(fb, x + w - 62, y + 30, "+33%", 2, NVGRN)


def scene_ship(fb, x, y, w, h):
    """A corvette at sea, hit: blast, smoke, drone boats."""
    fb.rect(x, y, w, h * 55 // 100, SKY)
    fb.rect(x, y + h * 55 // 100, w, h - h * 55 // 100, SEADK)
    fb.disc(x + 26, y + 14, 10, (250, 214, 120))
    # hull with a pointed bow (right) and flat stern (left)
    hy = y + h - 34
    fb.poly([(x + 28, hy), (x + w - 60, hy), (x + w - 24, hy + 8),
             (x + w - 34, hy + 16), (x + 40, hy + 16)], (96, 100, 108))
    fb.rect(x + 28, hy, w - 88, 3, (120, 124, 132))  # deck edge
    # superstructure: bridge block, funnel, mast with flag
    fb.rect(x + w // 2 - 20, hy - 18, 48, 18, (120, 124, 132))
    fb.rect(x + w // 2 + 30, hy - 30, 10, 12, (70, 74, 80))
    fb.rect(x + w // 2 + 8, hy - 34, 3, 34, (70, 74, 80))
    fb.rect(x + w // 2 + 11, hy - 34, 12, 7, RED)
    fb.rect(x + w // 2 - 14, hy - 14, 8, 6, (200, 220, 240))
    fb.rect(x + w // 2 - 2, hy - 14, 8, 6, (200, 220, 240))
    # blast at the stern
    bx, by = x + 52, hy - 6
    fb.disc(bx, by, 16, FLAME)
    fb.disc(bx, by, 9, (255, 210, 60))
    fb.tri((bx - 18, by + 4), (bx, by - 24), (bx + 18, by + 4), FLAME)
    fb.tri((bx - 8, by + 2), (bx + 4, by - 16), (bx + 14, by + 2), (255, 210, 60))
    # smoke
    for sx, sy, sr in ((bx - 8, by - 26, 9), (bx + 6, by - 34, 11),
                       (bx + 18, by - 26, 8)):
        fb.disc(sx, sy, sr, (140, 140, 145))
    # drone boats with wakes
    for dx in (x + w - 92, x + w - 62, x + 120):
        fb.rect(dx, y + h - 14, 18, 6, (30, 34, 40))
        fb.rect(dx + 4, y + h - 18, 8, 4, (50, 54, 60))
        fb.hline(dx - 20, y + h - 11, 20, WHITE)
    fb.hline(x + 10, y + h - 22, 30, WHITE)
    fb.hline(x + w - 120, y + h - 26, 26, WHITE)


def scene_cricket(fb, x, y, w, h):
    """The final day at the Basin Reserve: bat, ball, draw."""
    fb.rect(x, y, w, h, SKY)
    fb.disc(x + 24, y + 16, 11, (250, 214, 120))
    fb.rect(x, y + h - 58, w, 58, (74, 148, 74))
    fb.rect(x + w // 2 - 14, y + h - 58, 28, 58, SAND)
    for sx in (x + w // 2 - 8, x + w // 2 - 2, x + w // 2 + 4):
        fb.rect(sx, y + h - 40, 2, 12, (250, 220, 130))
    person(fb, x + w // 2 - 36, y + h - 22, 36, (30, 90, 170))
    fb.thick_line(x + w // 2 - 32, y + h - 40, x + w // 2 - 18, y + h - 22,
                  3, (160, 110, 60))
    person(fb, x + w - 34, y + h - 22, 30, RED)
    for i in range(14):
        cx = x + 8 + (i * 23) % (w - 16)
        fb.disc(cx, y + h - 52, 2, (200, 60, 60) if i % 3 == 0 else WHITE)
    fb.rect(x + 8, y + 8, 76, 20, INK)
    draw_text(fb, x + 12, y + 13, "239/5", 1, (255, 220, 90))
    draw_text(fb, x + 90, y + 13, "DRAW", 1, WHITE)


def _mini_sky(fb, x, y, w, h):
    fb.rect(x, y, w, h, SKY)
    fb.rect(x, y + h - 12, w, 12, (120, 150, 110))


def scene_factory(fb, x, y, w, h):
    fb.rect(x, y, w, h, (44, 44, 52))
    fb.disc(x + w - 22, y + 12, 7, (240, 230, 200))
    fb.rect(x + 6, y + h - 22, w - 12, 22, (120, 96, 70))
    fb.rect(x + 6, y + h - 26, w - 12, 5, (96, 76, 56))
    for wx in range(x + 14, x + w - 14, 22):
        fb.rect(wx, y + h - 18, 12, 8, (255, 196, 90))
    for sx, sy, sr in ((x + 36, y + 10, 8), (x + 54, y + 5, 10),
                       (x + w - 52, y + 8, 8)):
        fb.disc(sx, sy, sr, (150, 150, 155))
    fb.tri((x + 26, y + h - 22), (x + 36, y + h - 34), (x + 46, y + h - 22), FLAME)
    fb.tri((x + w - 56, y + h - 22), (x + w - 46, y + h - 32), (x + w - 36, y + h - 22),
           (255, 170, 40))
    person(fb, x + w - 30, y + h, 22, (255, 220, 40))
    fb.disc(x + w - 30, y + h - 20, 4, WHITE)
    person(fb, x + 20, y + h, 20, (40, 120, 200))
    fb.disc(x + 20, y + h - 18, 4, WHITE)


def scene_delhi(fb, x, y, w, h):
    _mini_sky(fb, x, y, w, h)
    fb.disc(x + w - 22, y + 10, 7, (250, 214, 120))
    ax, ay, aw, ah = x + w // 2 - 16, y + h - 34, 32, 24
    fb.rect(ax, ay, aw, ah, (196, 164, 120))
    fb.rect(ax + 9, ay + 12, 14, 12, SKY)
    fb.disc(ax + 16, ay + 12, 7, SKY)
    fb.rect(ax - 3, ay - 3, aw + 6, 4, (170, 138, 96))
    for fx, c1, c2 in ((x + 10, (255, 153, 51), (19, 136, 8)),
                       (x + w - 26, (220, 20, 60), (0, 56, 147))):
        fb.rect(fx, y + 6, 2, 26, (90, 70, 50))
        fb.rect(fx + 2, y + 6, 14, 4, c1)
        fb.rect(fx + 2, y + 10, 14, 4, WHITE)
        fb.rect(fx + 2, y + 14, 14, 4, c2)
    person(fb, x + w // 2 - 34, y + h - 12, 18, NAVY2)
    person(fb, x + w // 2 + 34, y + h - 12, 18, REDDK)


def scene_kyiv(fb, x, y, w, h):
    fb.rect(x, y, w, h, (196, 168, 140))
    fb.rect(x, y + h - 8, w, 8, (90, 80, 70))
    for bx, bw, bh in ((x + 6, 26, 22), (x + 36, 20, 28), (x + 60, 30, 18),
                       (x + 94, 22, 26), (x + 120, 28, 20), (x + 152, 24, 30)):
        fb.rect(bx, y + h - 8 - bh, bw, bh, (70, 66, 62))
    for sx, sy, sr in ((x + 46, y + 6, 8), (x + 56, y + 2, 9),
                       (x + 164, y + 4, 8), (x + 172, y + 10, 6)):
        fb.disc(sx, sy, sr, (130, 128, 124))
    fb.tri((x + 40, y + h - 34), (x + 46, y + h - 44), (x + 52, y + h - 34), FLAME)
    fb.tri((x + 158, y + h - 36), (x + 164, y + h - 46), (x + 170, y + h - 36),
           (255, 170, 40))


def scene_gaza(fb, x, y, w, h):
    fb.rect(x, y, w, h, SAND)
    fb.rect(x, y + h - 8, w, 8, (170, 150, 110))
    # damaged building
    fb.poly([(x + 8, y + h - 8), (x + 8, y + 10), (x + 20, y + 6),
             (x + 30, y + 12), (x + 44, y + 8), (x + 52, y + 14),
             (x + 52, y + h - 8)], (150, 144, 132))
    fb.rect(x + 18, y + 18, 8, 8, (60, 56, 50))
    # water well
    fb.rect(x + w - 60, y + h - 22, 4, 14, (90, 70, 50))
    fb.rect(x + w - 34, y + h - 22, 4, 14, (90, 70, 50))
    fb.rect(x + w - 62, y + h - 24, 32, 3, (90, 70, 50))
    fb.circle(x + w - 46, y + h - 10, 9, (120, 116, 108))
    fb.disc(x + w - 46, y + h - 10, 6, (80, 120, 170))
    # blue flag
    fb.rect(x + w - 14, y + 6, 2, 22, (90, 70, 50))
    fb.rect(x + w - 12, y + 6, 12, 7, (60, 120, 200))
    person(fb, x + 76, y + h - 8, 18, (200, 120, 60))
    person(fb, x + 100, y + h - 8, 18, TEAL)


def scene_football(fb, x, y, w, h):
    fb.rect(x, y, w, h, (74, 148, 74))
    for lx in range(x + 20, x + w - 10, 28):
        fb.vline(lx, y, h, (140, 200, 140))
    # goalpost: two uprights, a crossbar, a centre post
    fb.rect(x + w - 24, y + 4, 3, 10, (250, 220, 90))
    fb.rect(x + w - 6, y + 4, 3, 10, (250, 220, 90))
    fb.rect(x + w - 24, y + 12, 21, 3, (250, 220, 90))
    fb.rect(x + w - 14, y + 14, 3, 14, (250, 220, 90))
    fb.disc(x + w // 2, y + h // 2, 7, (120, 90, 50))
    fb.hline(x + w // 2 - 7, y + h // 2, 14, WHITE)
    person(fb, x + 16, y + h - 4, 18, WHITE)
    person(fb, x + w - 34, y + h - 4, 18, NAVY2)
    draw_text(fb, x + 6, y + 4, "35-10", 1, WHITE)


def scene_chart(fb, x, y, w, h):
    fb.rect(x, y, w, h, PANEL)
    fb.rect(x, y + h - 4, w, 4, RULE)
    vals = [8, 12, 11, 16, 15, 20]
    for i, v in enumerate(vals):
        fb.rect(x + 8 + i * 12, y + h - 6 - v, 9, v,
                BLUE if i % 2 == 0 else TEAL)
    fb.line(x + 8, y + h - 14, x + w - 8, y + 8, RED)
    draw_text(fb, x + 6, y + 3, "51.7", 1, INK)


def scene_chart2(fb, x, y, w, h):
    fb.rect(x, y, w, h, PANEL)
    fb.rect(x, y + h - 4, w, 4, RULE)
    vals = [20, 17, 18, 14, 13, 10]
    for i, v in enumerate(vals):
        fb.rect(x + 8 + i * 12, y + h - 6 - v, 9, v,
                NAVY2 if i % 2 == 0 else GREY)
    fb.line(x + 8, y + 8, x + w - 8, y + h - 14, RED)
    draw_text(fb, x + 6, y + 3, "54.6", 1, INK)


def scene_retail(fb, x, y, w, h):
    fb.rect(x, y, w, h, PANEL)
    fb.rect(x + 20, y + 6, w - 40, h - 10, (220, 210, 190))
    for i in range(6):
        fb.rect(x + 20 + i * 12, y + 6, 12, 7,
                RED if i % 2 == 0 else WHITE)
    fb.rect(x + w // 2 - 8, y + h - 14, 16, 10, (90, 70, 50))
    fb.rect(x + 28, y + 18, 14, 10, SKY)
    fb.rect(x + w - 42, y + 18, 14, 10, SKY)
    fb.rect(x + 34, y + h - 10, 10, 8, TEAL)
    fb.rect(x + w - 48, y + h - 10, 10, 8, ORANGE)
    draw_text(fb, x + 6, y + 3, "+2.2%", 1, GREEN)


def scene_poll(fb, x, y, w, h):
    fb.rect(x, y, w, h, PANEL)
    fb.rect(x, y + h - 4, w, 4, RULE)
    fb.rect(x + 22, y + h - 6 - 26, 26, 26, RED)
    fb.rect(x + 58, y + h - 6 - 25, 26, 25, BLUE)
    draw_text(fb, x + 26, y + h - 6 - 34, "42", 1, REDDK)
    draw_text(fb, x + 62, y + h - 6 - 33, "41", 1, NAVY2)
    draw_text(fb, x + w - 46, y + 4, "42-41", 1, INK)


def scene_quake(fb, x, y, w, h):
    fb.rect(x, y, w, h, PANEL)
    fb.rect(x, y + h // 2, w, 2, LGREY)
    pts = [(x + 4, y + h // 2), (x + 16, y + h // 2), (x + 24, y + 5),
           (x + 32, y + h - 5), (x + 40, y + h // 2), (x + 54, y + 7),
           (x + 62, y + h - 7), (x + 74, y + h // 2), (x + w - 4, y + h // 2)]
    for i in range(len(pts) - 1):
        fb.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], RED)
    draw_text(fb, x + 6, y + 3, "M6.5", 1, INK)


SCENES = {
    "chip": scene_chip, "ship": scene_ship, "cricket": scene_cricket,
    "factory": scene_factory, "delhi": scene_delhi, "kyiv": scene_kyiv,
    "gaza": scene_gaza, "football": scene_football, "chart": scene_chart,
    "chart2": scene_chart2, "retail": scene_retail, "poll": scene_poll,
    "quake": scene_quake,
}


# ------------------------------------------------------------------- map
CONTINENTS = [
    # North America
    [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 80), (-80, 73),
     (-70, 62), (-55, 52), (-60, 45), (-75, 35), (-80, 25), (-90, 20),
     (-97, 16), (-105, 20), (-115, 28), (-125, 40), (-125, 49), (-140, 60),
     (-155, 58), (-165, 60)],
    # Greenland
    [(-58, 64), (-45, 60), (-30, 68), (-40, 76), (-58, 74)],
    # South America
    [(-80, 10), (-70, 12), (-60, 5), (-50, 0), (-40, -5), (-35, -10),
     (-40, -20), (-50, -30), (-60, -38), (-70, -50), (-73, -40), (-72, -20),
     (-80, -5)],
    # Europe
    [(-10, 36), (-10, 44), (0, 48), (-5, 50), (5, 53), (8, 57), (18, 56),
     (21, 55), (28, 59), (30, 70), (40, 68), (45, 60), (40, 55), (30, 45),
     (28, 40), (23, 36), (18, 40), (12, 44), (8, 44), (3, 42), (-2, 37)],
    # Africa
    [(-17, 15), (-10, 30), (0, 36), (10, 37), (20, 32), (30, 31), (35, 28),
     (43, 12), (51, 10), (48, 0), (40, -10), (35, -20), (30, -28),
     (20, -35), (15, -30), (12, -18), (8, -5), (9, 4), (-8, 5)],
    # Asia
    [(40, 68), (50, 70), (60, 70), (70, 73), (90, 75), (110, 76), (130, 72),
     (160, 70), (178, 66), (170, 60), (162, 55), (158, 50), (142, 45),
     (140, 38), (130, 35), (127, 33), (122, 38), (120, 30), (115, 22),
     (108, 18), (105, 10), (100, 8), (97, 15), (90, 22), (88, 22), (80, 15),
     (77, 8), (72, 20), (66, 25), (60, 25), (55, 26), (52, 28), (48, 30),
     (44, 29), (40, 36), (36, 36), (30, 36), (35, 42), (40, 45), (42, 55),
     (40, 60)],
    # Australia
    [(113, -22), (114, -30), (115, -35), (124, -33), (130, -32), (137, -35),
     (140, -38), (147, -39), (150, -37), (153, -27), (150, -22), (146, -19),
     (142, -15), (142, -11), (136, -12), (132, -12), (126, -14), (122, -17),
     (118, -20)],
]
ISLANDS = [(95, 0), (102, -2), (110, -7), (118, -5), (125, -3), (132, -4),
           (167, -38), (172, -41), (178, -18), (139, 35), (141, 38)]

# Story number -> (lon, lat) for the map pins.
PINS = [
    (1, -122.0, 37.4), (2, 20.1, 32.1), (3, 174.8, -41.3),
    (4, 106.1, -6.1), (5, 77.2, 28.6), (6, 30.5, 50.5),
    (7, 34.5, 31.5), (8, -99.1, 19.4), (9, 4.3, 50.8),
    (10, -74.0, 40.7), (11, 172.6, -43.5), (12, 149.1, -35.3),
    (13, 167.5, -15.5), (14, -47.9, -15.8), (15, -47.9, -15.8),
    (16, -72.5, 7.9), (17, -77.0, -12.0), (18, -75.5, -11.0),
    (19, 7.5, 9.1), (20, 6.7, 0.3), (21, 36.8, -1.3),
    (22, -0.2, 5.6), (23, 3.4, 6.5), (24, -16.6, 13.5),
    (25, 36.8, -1.3), (26, 127.0, 37.5), (27, 139.7, 35.7),
    (28, 151.2, -33.9), (29, 114.2, 22.3), (30, 30.7, 36.9),
    (31, 34.5, 31.5), (32, 56.3, 58.0), (33, 54.4, 24.5),
    (34, 145.0, -37.8), (35, -0.1, 51.5), (36, -99.1, 19.4),
    (37, 7.5, 9.1), (38, 31.2, 30.0),
]


def draw_map(fb, x, y, w, h):
    fb.rect(x, y, w, h, SEA)
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
    seen = {}
    for n, lo, la in PINS:
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
                     "Huang back at Nvidia  -  Kyiv sinks a Russian corvette  -  Wellington Test drawn",
                     2, RED)
    fb.hline(M, 124, CW, RULE)
    # --- key numbers
    nums = [("+33%", "NVDA SHARES"), ("24", "SERANG DEAD"),
            ("7", "DRONES SANK SHIP"), ("720/9", "INDIA'S TOTAL"),
            ("2.2%", "NZ RETAIL SALES"), ("42-41", "TAYLOR LEADS PM")]
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
    used = 0
    for j, (name, cnt, col) in enumerate(REGIONS):
        if j == len(REGIONS) - 1:
            seg = CW - used
        else:
            seg = CW * cnt // TOTAL_STORIES
        used += seg
        fb.rect(bx, 172, seg, 18, col)
        lab = "%s %d" % (name, cnt)
        if seg >= text_w(lab, 1) + 4:
            draw_text(fb, bx + (seg - text_w(lab, 1)) // 2, 177, lab, 1, WHITE)
        bx += seg
    # --- timeline strip
    fb.rect(M, 194, CW, 20, NAVY)
    draw_text(fb, M + 6, 200, "THE DAY IN UTC", 1, GOLD)
    draw_text(fb, M + 108, 200,
              "01:20 49ers kick off  -  02:40 M6.5 quake off Vanuatu  -  "
              "09:00 Eurozone PMI 51.7  -  12:01 UNRWA worker killed in Gaza  -  "
              "14:45 US PMI 54.6", 1, WHITE)
    # --- heroes
    hy, hh = 218, 214
    colw = (CW - 16) // 3
    for i, st in enumerate(HEROES):
        hx = M + i * (colw + 8)
        SCENES[st["scene"]](fb, hx, hy, colw, 92)
        fb.rect(hx, hy + 92, colw, 2, RULE)
        fb.rect(hx, hy + 94, colw, 15, RED)
        draw_text(fb, hx + 6, hy + 98, st["kicker"], 1, WHITE)
        badge(fb, hx + colw - text_w(st["badge"], 1) - 15, hy + 4, st["badge"])
        draw_text(fb, hx, hy + 114,
                  "%d %s - %s" % (st["n"], st["place"], st["region"]), 1, RED)
        y = hy + 128
        for ln in wrap(st["head"], 2, colw)[:2]:
            draw_text_bold(fb, hx, y, ln, 2, INK)
            y += 17
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
    fb.rect(M, my, 330, 264, PANEL)
    fb.rect(M, my, 330, 2, RULE)
    draw_text(fb, M + 8, my + 8, "WHERE IT HAPPENED", 2, INK)
    draw_text(fb, M + 8, my + 24, "Pins match story numbers", 1, GREY)
    draw_map(fb, M + 6, my + 38, 318, 218)
    lx = M + 338
    draw_text(fb, lx, my + 8,
              "ALSO ON MONDAY 23 NOVEMBER - %d MORE STORIES" % len(MORE), 2, INK)
    fb.hline(lx, my + 26, W - M - lx, RULE)
    # two columns of the more-list, 13 rows each
    colw2 = (W - M - lx - 12) // 2
    for i, (place, region, head, src, status) in enumerate(MORE):
        cidx, ridx = divmod(i, 13)
        ix = lx + cidx * (colw2 + 12)
        iy = my + 34 + ridx * 17
        n = 14 + i
        draw_text_bold(fb, ix, iy, "%d." % n, 1, RED)
        tx = ix + text_w("%d. " % n, 1)
        draw_text(fb, tx, iy, head, 1, INK)
        draw_text(fb, tx, iy + 8, "%s - %s [%s]" % (place, src, status),
                  1, GREY)
    # --- DATE CHECK
    dy = 922
    fb.rect(M, dy, CW, 78, PANEL)
    fb.rect(M, dy, CW, 2, RED)
    fb.rect(M, dy + 76, CW, 2, RED)
    fb.rect(M, dy, 2, 78, RED)
    fb.rect(M + CW - 2, dy, 2, 78, RED)
    draw_text(fb, M + 8, dy + 7, "DATE CHECK - READ THIS FIRST", 1, REDDK)
    y = dy + 19
    for ln in wrap(DATE_CHECK, 1, CW - 16)[:6]:
        draw_text(fb, M + 8, y, ln, 1, INK)
        y += 9
    # --- footer
    draw_text(fb, M, 1006,
              "Sources: Reuters, AP, AFP, CNN, WSJ, BBC, ESPNcricinfo, S&P Global, "
              "Stats NZ, USGS, UN News, Radio Nepal, IANS, Newspoll, BOM, PCHR, CAF, "
              "official releases.", 1, GREY)
    draw_text(fb, M, 1016,
              "REPORTED = the day's wires  -  CLAIM = one side's account  -  "
              "OFFICIAL = the body itself. "
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
