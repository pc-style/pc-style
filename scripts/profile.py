"""Render the profile README's SVGs in the pcstyle.dev desktop style.

Usage: GITHUB_TOKEN=... python3 scripts/profile.py <user> <out_dir>
Standard library only. Runs on GitHub Actions; the output goes to the
`output` branch, never to main.
"""

import base64
import json
import os
import sys
import urllib.request
from collections import deque
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = 896
ADV = 0.6364  # Departure Mono advance, in em

# homepage tokens (global.css, night theme) and the aurora palette built from them
BG, GLASS, FG, DIM, FAINT, LINE = "#0a0a0b", "#0a0a0beb", "#e8e6e3", "#8a8782", "#4a4845", "#252327"
ACCENT, VIOLET, INK, SHADE = "#8c1862", "#9d5cff", "#e45aa3", "#2a1a4d"
P1, P2, P3, P4, P5 = "#271846", "#563390", "#8f54ea", "#d7559a", "#f6c5df"
EMPTY = "#16131a"
NEUTRAL, GREYBAR = "#1d1c21", "#5d5a63"
SOLVERS_API = "https://0x7f.pcstyle.dev/api/solvers"

PROJECTS = [
    ("skill-view", "stable", "local-only GUI for inspecting agent skills and their provenance"),
    ("supply-chain-guard", "beta", "local install gate for npm packages and VS Code extensions"),
    ("stream-guard", "beta", "macOS sharing preview that blacks out on sensitive Accessibility text; no OCR"),
    ("x-md", "beta", "public X posts, profiles, search, and graphs as Markdown or JSON"),
    ("cool-my-skills", "beta", "on-demand loading for rarely used agent skills"),
    ("amp-plugins", "experiment", "inspectable Amp agent modes, tools, and context filters"),
]

# 12x12 desktop icons and 8x8 window controls from homepage/src/components/Desktop.astro
PIX = {
    "me": ["............", "....####....", "...#....#...", "...#....#...", "....####....", "..##....##..", ".#........#.", ".#........#.", ".#........#.", ".##########.", "............", "............"],
    "work": ["............", ".#####......", ".#...##.....", ".##########.", ".#........#.", ".#........#.", ".#........#.", ".#........#.", ".#........#.", ".##########.", "............", "............"],
    "oss": ["............", "...##..##...", "..#......#..", "..#......#..", "..#......#..", ".##......##.", "..#......#..", "..#......#..", "..#......#..", "...##..##...", "............", "............"],
    "github": ["............", "..#......#..", "..##....##..", "..#.####.#..", ".#........#.", ".#..#..#..#.", ".#........#.", ".#........#.", "..#......#..", "...######...", "............", "............"],
    "blog": ["............", "..########..", "..#......#..", "..#.####.#..", "..#......#..", "..#.####.#..", "..#......#..", "..#.####.#..", "..#......#..", "..########..", "............", "............"],
    "contact": ["............", "............", ".##########.", ".#........#.", ".#.#....#.#.", ".#..#..#..#.", ".#...##...#.", ".#........#.", ".#........#.", ".##########.", "............", "............"],
    "xmd": ["............", "............", "..#......#..", "...#....#...", "....#..#....", ".....##.....", ".....##.....", "....#..#....", "...#....#...", "..#......#..", "............", "............"],
}
CTL = {
    "min": ["........", "........", "........", "........", "........", "........", ".######.", ".######."],
    "max": ["########", "########", "#......#", "#......#", "#......#", "#......#", "#......#", "########"],
    "x": ["##....##", "###..###", ".######.", "..####..", "..####..", ".######.", "###..###", "##....##"],
}

GQL = """query($login: String!) { user(login: $login) {
  followers { totalCount }
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { date weekday contributionLevel } } } }
  starred: repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
    totalCount nodes { name stargazerCount } }
  recent: repositories(first: 60, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, orderBy: {field: PUSHED_AT, direction: DESC}) {
    nodes { name pushedAt languages(first: 6, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } } }
  public: repositories(privacy: PUBLIC, ownerAffiliations: OWNER) { totalCount }
} }"""
REPO_GQL = """repository(owner: $login, name: "%s") { name stargazerCount forkCount pushedAt url primaryLanguage { name color } }"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def gql(query, login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "pc-style-profile"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch(login, token):
    data = gql(GQL, login, token)["user"]
    repos_q = "query($login: String!) {" + "".join(
        f"r{i}: " + REPO_GQL % name for i, (name, _, _) in enumerate(PROJECTS)
    ) + "}"
    repos = gql(repos_q, login, token)
    data["projects"] = [repos[f"r{i}"] for i in range(len(PROJECTS))]
    return data


# ── svg helpers ─────────────────────────────────


def font_face():
    b64 = base64.b64encode((ROOT / "assets/DepartureMono-Regular.woff2").read_bytes()).decode()
    return f"@font-face{{font-family:D;src:url(data:font/woff2;base64,{b64}) format('woff2')}}"


def svg(width, height, body, css="", label=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(label)}" font-family="D, ui-monospace, Menlo, monospace" shape-rendering="crispEdges">'
        f"<title>{escape(label)}</title>"
        f"<style>{font_face()}text{{white-space:pre}}{css}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
        f"{defs()}{body}</svg>"
    )


def defs():
    # 2px checkerboards: the homepage's title-bar texture plus the dither ramps
    def checker(pid, on, off=None):
        back = f'<rect width="4" height="4" fill="{off}"/>' if off else ""
        return (
            f'<pattern id="{pid}" width="4" height="4" patternUnits="userSpaceOnUse">{back}'
            f'<rect width="2" height="2" fill="{on}"/><rect x="2" y="2" width="2" height="2" fill="{on}"/></pattern>'
        )

    def sparse(pid, on, off=None):
        back = f'<rect width="8" height="8" fill="{off}"/>' if off else ""
        return (
            f'<pattern id="{pid}" width="8" height="8" patternUnits="userSpaceOnUse">{back}'
            f'<rect width="2" height="2" fill="{on}"/><rect x="4" y="4" width="2" height="2" fill="{on}"/></pattern>'
        )

    return "<defs>" + "".join([
        checker("bar", NEUTRAL),
        checker("bar-on", "#3a2470"),
        checker("l1", P2, EMPTY),
        checker("l3", P3, P2),
        checker("hi", P5, P4),
        checker("fade1", GREYBAR),
        sparse("fade2", GREYBAR),
        checker("fade1-hot", P4),
        sparse("fade2-hot", P4),
        sparse("shade", NEUTRAL),
    ]) + "</defs>"


def pix(name, x, y, scale, fill, grid=PIX):
    rows = grid[name]
    d = "".join(f"M{c} {r}h1v1h-1z" for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "#")
    return f'<path transform="translate({x} {y}) scale({scale})" fill="{fill}" d="{d}"/>'


def text(x, y, s, size=11, fill=FG, anchor="start", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}"{a} {extra}>{s}</text>'


def tw(s, size=11):
    return len(s) * size * ADV


def window(x, y, w, h, key, title, meta="", focus=False, meta_fill=FAINT):
    """A homepage window: glass body, dithered 20px title bar, boxed labels, controls."""
    edge = VIOLET if focus else LINE
    parts = [f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" fill="{GLASS}" stroke="{edge}"/>']
    if focus:
        parts.append(f'<rect x="{x - 2.5}" y="{y - 2.5}" width="{w + 5}" height="{h + 5}" fill="none" stroke="{VIOLET}" stroke-opacity=".45" stroke-dasharray="1 1"/>')
    parts.append(f'<rect x="{x + 1}" y="{y + 1}" width="{w - 2}" height="20" fill="url(#{"bar-on" if focus else "bar"})"/>')
    parts.append(f'<line x1="{x + 1}" y1="{y + 21.5}" x2="{x + w - 1}" y2="{y + 21.5}" stroke="{LINE}"/>')
    cx = x + 7
    for s, fill in ((key, VIOLET), (title, FG if focus else DIM)):
        bw = tw(s) + 10
        parts.append(f'<rect x="{cx}" y="{y + 3}" width="{bw:.1f}" height="16" fill="{BG}"/>')
        parts.append(text(cx + 5, y + 15, escape(s), 11, fill))
        cx += bw + 6
    right = x + w - 1 - 60
    if meta:
        mw = tw(meta) + 12
        parts.append(f'<rect x="{right - mw - 6:.1f}" y="{y + 3}" width="{mw:.1f}" height="16" fill="{BG}"/>')
        parts.append(text(right - 12, y + 15, escape(meta), 11, meta_fill, "end"))
    for i, c in enumerate(("min", "max", "x")):
        bx = right + i * 20
        parts.append(f'<rect x="{bx}" y="{y + 1}" width="20" height="20" fill="{BG}"/>')
        parts.append(pix(c, bx + 6, y + 7, 1, DIM, CTL))
    return "".join(parts)


def typed(x, y, s, size, begin, per, fill, cid, cursor=False):
    """Text revealed one character at a time with a discrete SMIL clip."""
    n = len(s)
    cw = size * ADV
    widths = ";".join(f"{i * cw:.1f}" for i in range(n + 1))
    keys = ";".join(f"{i / n:.4f}" for i in range(n + 1))
    dur = per * n
    out = (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y - size}" height="{size * 1.5}" width="0">'
        f'<animate attributeName="width" values="{widths}" keyTimes="{keys}" calcMode="discrete" begin="{begin}s" dur="{dur:.2f}s" fill="freeze"/>'
        f"</rect></clipPath>"
        f'<g clip-path="url(#{cid})">{text(x, y, s, size, fill)}</g>'
    )
    if cursor:
        xs = ";".join(f"{x + i * cw + 1:.1f}" for i in range(n + 1))
        out += (
            f'<rect class="blink" x="{x}" y="{y - size + 2}" width="{cw:.1f}" height="{size}" fill="{VIOLET}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{begin}s"/>'
            f'<animate attributeName="x" values="{xs}" keyTimes="{keys}" calcMode="discrete" begin="{begin}s" dur="{dur:.2f}s" fill="freeze"/></rect>'
        )
    return out, begin + dur


def ago(iso, now):
    d = now - datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = d.total_seconds()
    for unit, size in (("y", 31536000), ("mo", 2592000), ("d", 86400), ("h", 3600), ("m", 60)):
        if s >= size:
            return f"{int(s // size)}{unit} ago"
    return "just now"


# ── header ──────────────────────────────────────


def header():
    H = 380
    frames, frame_h = 24, 190
    sprite = base64.b64encode((ROOT / "assets/aurora.png").read_bytes()).decode()
    css = (
        f".sky{{animation:sky 4.2s steps({frames},jump-none) infinite alternate}}"
        f"@keyframes sky{{to{{transform:translateY(-{(frames - 1) * H}px)}}}}"
        ".blink{animation:blink 1.06s steps(1) infinite}@keyframes blink{50%{fill-opacity:0}}"
    )
    parts = [
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<svg width="{W}" height="{H}"><image class="sky" width="{W}" height="{frames * H}" preserveAspectRatio="none" '
        f'style="image-rendering:pixelated" href="data:image/png;base64,{sprite}"/></svg>',
    ]
    assert frame_h * 2 == H
    # top bar, as on the site
    parts += [
        f'<rect width="{W}" height="22" fill="{BG}" fill-opacity=".85"/>',
        f'<line x1="0" y1="22.5" x2="{W}" y2="22.5" stroke="{LINE}"/>',
        text(10, 15, '<tspan fill="#8a8782">~/</tspan>pcstyle', 11, FG),
        text(W - 10, 15, "pcstyle.dev", 11, DIM, "end"),
    ]
    # the "me" window
    x, y, w, h = (W - 600) // 2, 92, 600, 236
    parts.append(window(x, y, w, h, "1", "me", "~/pcstyle", focus=True))
    bx = x + 22
    parts.append(text(bx, y + 66, "Adam Krupa", 33, FG))
    parts.append(text(bx, y + 92, '(pcstyle) · freelance <tspan fill="#e8e6e3">full-stack developer</tspan>', 13, DIM))
    ux = bx + tw("(pcstyle) · freelance ", 13)
    parts.append(f'<rect x="{ux:.1f}" y="{y + 96}" width="{tw("full-stack developer", 13):.1f}" height="1" fill="{ACCENT}"/>')
    rows = [
        ("now", "building local-first tools for AI-agent workflows"),
        ("where", "Poznań, Poland · CET · remote, worldwide"),
        ("day job", "full-stack at appto.ai · freelance on the side"),
        ("status", "■ available for freelance work"),
    ]
    t = 0.6
    for i, (k, v) in enumerate(rows):
        ry = y + 128 + i * 22
        parts.append(f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s"/>'
                     + text(bx, ry, f'<tspan fill="{INK}">$</tspan> <tspan fill="{FAINT}">{k}</tspan>', 12, DIM) + "</g>")
        frag, t = typed(bx + tw("$ day job  ", 12), ry, escape(v), 12, t, 0.028, FG if i else P5, f"t{i}", cursor=i == len(rows) - 1)
        parts.append(frag)
        t += 0.15
    # resize grip: a stair of 2px dots
    for i in range(3):
        for j in range(i + 1):
            parts.append(f'<rect x="{x + w - 4 - 3 * j}" y="{y + h - 4 - 3 * (2 - i)}" width="2" height="2" fill="{VIOLET}"/>')
    return svg(W, H, "".join(parts), css, "Adam Krupa (pcstyle), freelance full-stack developer")


# ── snake ───────────────────────────────────────

CELL, DOT = 16, 12
STEP_MS = 100
SEGMENTS, LAG, BODY = 18, 0.28, 5


def calendar(data):
    cal = data["contributionsCollection"]["contributionCalendar"]
    cells = {}
    for x, week in enumerate(cal["weeks"]):
        for day in week["contributionDays"]:
            cells[(x, day["weekday"])] = (LEVELS[day["contributionLevel"]], date.fromisoformat(day["date"]))
    return cal["totalContributions"], len(cal["weeks"]), cells


def plan(width, cells):
    """Walk to the nearest uneaten cell (BFS around its own body) until the grid is clear, then home."""
    lo_x, hi_x, lo_y, hi_y = -1, width, -1, 7
    start = (-1, -1)
    path, body = [start], deque([start] * BODY)
    food = {p for p, (lvl, _) in cells.items() if lvl > 0}
    eaten = {}

    def bfs(goal, avoid):
        head = path[-1]
        prev, q = {head: None}, deque([head])
        while q:
            cur = q.popleft()
            if cur != head and goal(cur):
                route = []
                while cur != head:
                    route.append(cur)
                    cur = prev[cur]
                return route[::-1]
            x, y = cur
            for nxt in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
                if lo_x <= nxt[0] <= hi_x and lo_y <= nxt[1] <= hi_y and nxt not in prev and nxt not in avoid:
                    prev[nxt] = cur
                    q.append(nxt)
        return None

    def walk(route):
        for p in route:
            path.append(p)
            body.append(p)
            body.popleft()
            if p in food:
                food.discard(p)
                eaten[p] = len(path) - 1

    while food:
        walk(bfs(lambda p: p in food, set(list(body)[1:])) or bfs(lambda p: p in food, set()))
    walk(bfs(lambda p: p == start, set(list(body)[1:])) or bfs(lambda p: p == start, set()))
    return path, eaten


def pct(step, n):
    return f"{max(0, min(step, n)) / n * 100:.4f}".rstrip("0").rstrip(".") + "%"


def snake(data):
    total, width, cells = calendar(data)
    path, eaten = plan(width, cells)
    n = len(path) - 1
    dur = n * STEP_MS
    gx, gy = (W - width * CELL) // 2, 66
    H = gy + 7 * CELL + 46
    fills = [EMPTY, "url(#l1)", P2, "url(#l3)", P4]

    def corner(p):
        return gx + p[0] * CELL + (CELL - DOT) / 2, gy + p[1] * CELL + (CELL - DOT) / 2

    frames = []
    for i, p in enumerate(path):
        if 0 < i < n:
            a, b = path[i - 1], path[i + 1]
            if (p[0] - a[0], p[1] - a[1]) == (b[0] - p[0], b[1] - p[1]):
                continue
        x, y = corner(p)
        frames.append(f"{pct(i, n)}{{transform:translate({x:g}px,{y:g}px)}}")

    css = [
        f".s{{animation:m {dur}ms linear infinite}}@keyframes m{{{''.join(frames)}}}",
        f".c{{transform-box:fill-box;transform-origin:center;animation:{dur}ms linear infinite}}",
        f".bar{{transform-origin:{gx}px 0;animation:bar {dur}ms linear infinite}}@keyframes bar{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}",
    ]
    dots = []
    for i, ((x, y), (lvl, _)) in enumerate(sorted(cells.items())):
        cx, cy = corner((x, y))
        dots.append(f'<rect x="{cx:g}" y="{cy:g}" width="{DOT}" height="{DOT}" fill="{EMPTY}"/>')
        if lvl == 0:
            continue
        k = eaten[(x, y)]
        css.append(
            f"@keyframes e{i}{{0%,{pct(k - 0.6, n)}{{fill:{fills[lvl]};opacity:1;transform:none}}"
            f"{pct(k, n)}{{fill:{P5};opacity:1;transform:scale(1.5)}}"
            f"{pct(k + 3, n)},100%{{fill:{P5};opacity:0;transform:scale(.4)}}}}"
        )
        dots.append(f'<rect class="c" style="animation-name:e{i}" x="{cx:g}" y="{cy:g}" width="{DOT}" height="{DOT}" fill="{fills[lvl]}"/>')

    ramp = [P5, P4, P4, P3, P3, P2, P2, P1]
    segs = []
    for s in reversed(range(SEGMENTS)):
        f = s / (SEGMENTS - 1)
        size = DOT - 6 * f
        off = (DOT - size) / 2
        fill = ramp[min(len(ramp) - 1, int(f * len(ramp)))]
        delay = -(dur - s * LAG * STEP_MS) if s else 0
        segs.append(
            f'<g class="s" style="animation-delay:{delay:g}ms"><rect x="{off:g}" y="{off:g}" width="{size:g}" height="{size:g}" fill="{fill}"/></g>'
        )

    months, seen = [], set()
    for (x, y), (_, d) in sorted(cells.items()):
        if y == 0 and d.day <= 7 and d.month not in seen and 0 < x < width - 2:
            seen.add(d.month)
            months.append(text(gx + x * CELL, gy - 22, d.strftime("%b").lower(), 11, FAINT))

    body = [
        window(0, 0, W, H, "2", "activity", f"{total:,} contributions · last 12 months"),
        "".join(months),
        "".join(dots),
        "".join(segs),
        f'<rect x="{gx}" y="{H - 22}" width="{width * CELL}" height="4" fill="url(#shade)"/>',
        f'<rect class="bar" x="{gx}" y="{H - 22}" width="{width * CELL}" height="4" fill="url(#l3)"/>',
    ]
    return svg(W, H, "".join(body), "".join(css), f"{total} contributions in the last year, eaten by a snake"), total


# ── stats ───────────────────────────────────────


def stats(data, total, now, login):
    H = 214
    stars = sum(r["stargazerCount"] for r in data["starred"]["nodes"])
    original = data["starred"]["totalCount"]
    recent = data["recent"]["nodes"]
    latest = next(r for r in recent if r["name"].lower() != login.lower())  # skip this profile repo
    # each repo counts once, split by its own byte mix, so one huge repo can't drown the rest
    langs = {}
    for r in recent:
        edges = r["languages"]["edges"]
        repo_total = sum(e["size"] for e in edges) or 1
        for e in edges:
            name = e["node"]["name"]
            share, color = langs.get(name, (0, e["node"]["color"]))
            langs[name] = (share + e["size"] / repo_total, color or DIM)
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]
    lang_total = sum(v[0] for v in langs.values()) or 1

    parts = [window(0, 0, W, H, "3", "stats", "~/pc-style")]
    rows = [
        ("contribs", f"{total:,}", "in the last 12 months"),
        ("stars", f"★ {stars:,}", f"across {original} original repos"),
        ("repos", f"{data['public']['totalCount']}", "public"),
        ("followers", f"{data['followers']['totalCount']}", ""),
        ("last push", latest["name"], ago(latest["pushedAt"], now)),
    ]
    for i, (k, v, note) in enumerate(rows):
        y = 56 + i * 28
        parts.append(text(22, y, f'<tspan fill="{INK}">$</tspan> <tspan fill="{FAINT}">{k}</tspan>', 12, DIM))
        parts.append(text(140, y, f'{escape(v)} <tspan fill="{DIM}">{escape(note)}</tspan>', 12, FG))

    # languages: dithered bars that fade out at the tip
    lx = 470
    bx, track = lx + 112, W - 70 - (lx + 112)
    parts.append(f'<line x1="{lx - 24}" y1="38" x2="{lx - 24}" y2="{H - 18}" stroke="{LINE}"/>')
    parts.append(text(lx, 52, f'<tspan fill="{INK}">$</tspan> languages <tspan fill="{FAINT}">· share of my 60 latest repos</tspan>', 11, DIM))
    for i, (name, (size, color)) in enumerate(top):
        y = 80 + i * 22
        share = size / lang_total
        bw = max(8, round(track * size / top[0][1][0] / 2) * 2)
        parts.append(f'<rect x="{lx}" y="{y - 7}" width="6" height="6" fill="{color}"/>')
        parts.append(text(lx + 12, y, escape(name.lower()), 11, FG))
        solid = max(0, bw - 24)
        parts.append(f'<rect x="{bx}" y="{y - 9}" width="{track}" height="10" fill="url(#shade)"/>')
        if solid:
            parts.append(f'<rect x="{bx}" y="{y - 9}" width="{solid}" height="10" fill="{P4 if i == 0 else GREYBAR}"/>')
        hot = "-hot" if i == 0 else ""
        parts.append(f'<rect x="{bx + solid}" y="{y - 9}" width="{min(12, bw)}" height="10" fill="url(#fade1{hot})"/>')
        parts.append(f'<rect x="{bx + solid + 12}" y="{y - 9}" width="{max(0, min(12, bw - 12))}" height="10" fill="url(#fade2{hot})"/>')
        parts.append(text(W - 22, y, f"{share * 100:.0f}%", 11, DIM, "end"))
    return svg(W, H, "".join(parts), "", "GitHub stats and top languages")


# ── open-source list ────────────────────────────

# 12x12 icons for the projects, drawn on the same grid as the desktop set
PROJECT_PIX = {
    "skill-view": PIX["oss"],
    "supply-chain-guard": ["............", "..########..", ".#........#.", ".#...##...#.", ".#..####..#.", ".#...##...#.", ".#........#.", "..#......#..", "...#....#...", "....#..#....", ".....##.....", "............"],
    "stream-guard": ["............", "............", "............", "...######...", "..#......#..", ".#...##...#.", "#...####...#", ".#...##...#.", "..#......#..", "...######...", "............", "............"],
    "x-md": PIX["xmd"],
    "cool-my-skills": ["............", ".....#......", "..#..#..#...", "...#.#.#....", "....###.....", ".#########..", "....###.....", "...#.#.#....", "..#..#..#...", ".....#......", "............", "............"],
    "amp-plugins": ["............", "...#...#....", "...#...#....", "..#######...", "..#.....#...", "..#.....#...", "...#...#....", "....###.....", ".....#......", ".....#......", ".....##.....", "............"],
}
COL_STATUS, COL_LANG, COL_END = 624, 722, W - 16


def projects_head(count, original):
    h = 46
    parts = [
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h}" fill="{GLASS}" stroke="{LINE}"/>',
        window(0, 0, W, 23, "4", "open-source", f"{count} picks of {original} repos"),
        text(62, 39, "project", 11, FAINT),
        text(COL_STATUS, 39, "status", 11, FAINT),
        text(COL_LANG, 39, "lang", 11, FAINT),
        text(COL_END, 39, "★ · pushed", 11, FAINT, "end"),
    ]
    return svg(W, h, "".join(parts), "", "open-source projects")


def project_row(project, maturity, blurb, max_stars, now):
    h = 46
    name, stars = project["name"], project["stargazerCount"]
    lang = project["primaryLanguage"] or {"name": "", "color": DIM}
    hot = stars == max_stars
    parts = [
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" fill="{GLASS}" stroke="{LINE}"/>',
        f'<rect x="1" y="1" width="42" height="{h - 2}" fill="url(#{"bar-on" if hot else "bar"})"/>',
        f'<line x1="43.5" y1="1" x2="43.5" y2="{h - 1}" stroke="{LINE}"/>',
        f'<rect x="8" y="{h / 2 - 14}" width="28" height="28" fill="{BG}"/>',
        pix(name, 10, h / 2 - 12, 2, P5 if hot else FG, PROJECT_PIX),
        text(58, 20, escape(name), 13, FG),
        text(58, 36, escape(blurb), 11, DIM),
    ]
    tag = f"[{maturity}]"
    tag_fill = P5 if maturity == "stable" else (FG if maturity == "beta" else DIM)
    parts.append(text(COL_STATUS, 20, tag, 11, tag_fill))
    if lang["name"]:
        parts.append(f'<rect x="{COL_LANG}" y="13" width="6" height="6" fill="{lang["color"] or DIM}"/>')
        parts.append(text(COL_LANG + 11, 20, escape(lang["name"].lower()), 11, FG))
    parts.append(text(COL_END, 20, f"★ {stars}", 11, P5 if hot else FG, "end"))
    # stars as a dithered bar, relative to the most starred project
    track = 150
    bw = max(4, round(track * stars / max_stars / 2) * 2)
    solid = max(0, bw - 12)
    heat = "-hot" if hot else ""
    parts.append(f'<rect x="{COL_STATUS}" y="29" width="{track}" height="6" fill="url(#shade)"/>')
    if solid:
        parts.append(f'<rect x="{COL_STATUS}" y="29" width="{solid}" height="6" fill="{P4 if hot else GREYBAR}"/>')
    parts.append(f'<rect x="{COL_STATUS + solid}" y="29" width="{min(6, bw)}" height="6" fill="url(#fade1{heat})"/>')
    parts.append(f'<rect x="{COL_STATUS + solid + 6}" y="29" width="{max(0, min(6, bw - 6))}" height="6" fill="url(#fade2{heat})"/>')
    parts.append(text(COL_END, 36, ago(project["pushedAt"], now), 11, FAINT, "end"))
    return svg(W, h, "".join(parts), "", f"{name}: {blurb}")


# ── link badges ─────────────────────────────────

BADGES = [("site", "me", "pcstyle.dev"), ("blog", "blog", "blog"), ("xmd", "xmd", "x.md"), ("hire", "contact", "hire me")]
# 5x5 outbound arrow, as on the homepage's external links
ARROW = [".####", "...##", "..#.#", ".#..#", "#...."]


def badge(icon, label, hot=False):
    h, size = 30, 13
    w = round(30 + 10 + tw(label, size) + 22)
    edge = VIOLET if hot else LINE
    parts = [
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" fill="{BG}" stroke="{edge}"/>',
        f'<rect x="1" y="1" width="28" height="28" fill="url(#{"bar-on" if hot else "bar"})"/>',
        f'<line x1="29.5" y1="1" x2="29.5" y2="{h - 1}" stroke="{edge}"/>',
        pix(icon, 3, 3, 2, VIOLET if hot else FG),
        text(40, 20, escape(label), size, FG),
        pix("arrow", w - 14, 9, 1, VIOLET if hot else DIM, {"arrow": ARROW}),
    ]
    return svg(w, h, "".join(parts), "", label)


# ── 0x7f board ──────────────────────────────────


def solvers():
    """The quest site's board; an outage renders as nobody rather than failing the run."""
    try:
        req = urllib.request.Request(SOLVERS_API, headers={"User-Agent": "pc-style-profile"})
        with urllib.request.urlopen(req, timeout=15) as res:
            return [(r["handle"], r["at"][:10]) for r in json.load(res)]
    except Exception as err:  # noqa: BLE001
        print(f"solvers unavailable: {err}")
        return []


def board(rows):
    shown = rows[:8]
    h = 64 + max(1, len(shown)) * 20
    parts = [window(0, 0, W, h, "5", "0x7f", f"solved by {len(rows)}", meta_fill=P5 if rows else FAINT)]
    parts.append(text(22, 46, f'<tspan fill="{INK}">$</tspan> <tspan fill="{FAINT}">cat</tspan> solvers', 12, DIM))
    if not shown:
        parts.append(text(22, 72, "nobody yet. nine steps, one board. it starts in the 0x7f block below.", 11, DIM))
        parts.append(f'<rect class="blink" x="{22 + tw("nobody yet. nine steps, one board. it starts in the 0x7f block below.") + 4:.1f}" y="62" width="7" height="11" fill="{VIOLET}"/>')
    for i, (handle, day) in enumerate(shown):
        y = 72 + i * 20
        parts.append(text(22, y, f"{i + 1:>2}", 11, VIOLET))
        parts.append(text(52, y, escape(handle), 11, P5 if i == 0 else FG))
        parts.append(text(W - 22, y, escape(day), 11, FAINT, "end"))
    # dithered floor, the aurora's ground
    parts.append(f'<rect x="1" y="{h - 9}" width="{W - 2}" height="8" fill="url(#shade)"/>')
    css = ".blink{animation:blink 1.06s steps(1) infinite}@keyframes blink{50%{fill-opacity:0}}"
    return svg(W, h, "".join(parts), css, f"0x7f puzzle: solved by {len(rows)}")


def main():
    login, out = sys.argv[1], Path(sys.argv[2])
    data = fetch(login, os.environ["GITHUB_TOKEN"])
    now = datetime.now(timezone.utc)
    out.mkdir(parents=True, exist_ok=True)
    (out / "header.svg").write_text(header())
    snake_svg, total = snake(data)
    (out / "snake.svg").write_text(snake_svg)
    (out / "stats.svg").write_text(stats(data, total, now, login))
    max_stars = max(p["stargazerCount"] for p in data["projects"]) or 1
    (out / "oss.svg").write_text(projects_head(len(PROJECTS), data["starred"]["totalCount"]))
    for project, (_, maturity, blurb) in zip(data["projects"], PROJECTS):
        (out / f"oss-{project['name']}.svg").write_text(project_row(project, maturity, blurb, max_stars, now))
    (out / "board.svg").write_text(board(solvers()))
    for name, icon, label in BADGES:
        (out / f"badge-{name}.svg").write_text(badge(icon, label, hot=name == "hire"))
    for f in sorted(out.iterdir()):
        print(f"{f.name:32} {f.stat().st_size / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
