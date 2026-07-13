#!/usr/bin/env python3
"""
generate_stats.py
Fetches your GitHub stats via the GitHub GraphQL/REST API and renders
a neofetch-style SVG (light + dark mode) to embed on your profile README.

The ASCII art on the left side is now animated: it cycles through a
sequence of .txt frame files stored in ASCII_ART_FOLDER (e.g.
ASCII_ART_NATTA_1.txt, ASCII_ART_NATTA_2.txt, ASCII_ART_NATTA_3.txt, ...).
Frames are sorted by the trailing number in their filename and played in
that order, looping forever. You can control which frames are used, in
what order, and how long each one is shown — see the CONFIG section below.

Written from scratch — no external repo code reused.
"""

import os
import re
import glob
from datetime import date

import requests

GITHUB_TOKEN = os.environ["GH_TOKEN"]        # set as a repo secret
USERNAME = os.environ.get("GH_USERNAME", "nattaphom0x")

HEADERS = {"Authorization": f"bearer {GITHUB_TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"


# =====================================================================
# ===========================  CONFIG  ================================
# =====================================================================

# Folder holding the ASCII art animation frames (.txt files).
# Each file's *lines* become one animation frame of the neofetch art.
#
# Resolved relative to THIS SCRIPT'S location (not the current working
# directory), so it works the same whether you run it locally from any
# folder, or via GitHub Actions with any `working-directory` setting.
# You can still override it completely with an absolute path or the
# ASCII_ART_FOLDER env var.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ascii_folder_setting = os.environ.get("ASCII_ART_FOLDER", "ASCII_ART_FOLDER")
if os.path.isabs(_ascii_folder_setting):
    ASCII_ART_FOLDER = _ascii_folder_setting
else:
    ASCII_ART_FOLDER = os.path.join(SCRIPT_DIR, _ascii_folder_setting)

# Filename pattern used to find + order frame files inside the folder.
# Files are sorted numerically by the number captured in group 1, so
# ASCII_ART_NATTA_2.txt always plays before ASCII_ART_NATTA_10.txt.
ASCII_ART_FILENAME_PATTERN = r"ASCII_ART_NATTA_(\d+)\.txt"

# Default seconds each frame is shown for, if not overridden below.
ASCII_FRAME_DEFAULT_DURATION = 1.2

# Optional per-frame duration overrides, keyed by the frame *number*
# in its filename (e.g. the "2" in ASCII_ART_NATTA_2.txt).
# Anything not listed here uses ASCII_FRAME_DEFAULT_DURATION.
ASCII_FRAME_DURATIONS = {
    1: 1.5,   # show frame 1 a bit longer
    # 2: 1.0,
    # 3: 0.8,
}

# Optional: explicitly choose which frame numbers to play, and in what
# order (duplicates allowed, e.g. [1, 2, 3, 2] for a ping-pong effect).
# Leave as None to auto-play every frame found, in ascending order.
ASCII_FRAME_ORDER = None  # e.g. [1, 2, 3, 2]

# =====================================================================


def graphql_query(query: str, variables: dict) -> dict:
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def get_basic_stats(username: str) -> dict:
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes { stargazerCount }
        }
        followers { totalCount }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    data = graphql_query(query, {"login": username})["user"]
    stars = sum(r["stargazerCount"] for r in data["repositories"]["nodes"])
    commits = (
        data["contributionsCollection"]["totalCommitContributions"]
        + data["contributionsCollection"]["restrictedContributionsCount"]
    )
    return {
        "repos": data["repositories"]["totalCount"],
        "stars": stars,
        "followers": data["followers"]["totalCount"],
        "commits": commits,
    }


def load_ascii_frames(folder: str):
    """
    Scan `folder` for files matching ASCII_ART_FILENAME_PATTERN, sort them
    numerically, and return a list of (frame_number, lines, duration)
    tuples in playback order.
    """
    pattern = re.compile(ASCII_ART_FILENAME_PATTERN)
    found = {}
    for path in glob.glob(os.path.join(folder, "*.txt")):
        m = pattern.match(os.path.basename(path))
        if not m:
            continue
        num = int(m.group(1))
        with open(path, "r", encoding="utf-8") as f:
            # rstrip only trailing newline, keep internal spacing intact
            lines = f.read().splitlines()
        found[num] = lines

    if not found:
        resolved = os.path.abspath(folder)
        exists = os.path.isdir(resolved)
        all_txt = sorted(glob.glob(os.path.join(folder, "*.txt"))) if exists else []
        details = [
            f"No files matching pattern '{ASCII_ART_FILENAME_PATTERN}' found.",
            f"Looked in: {resolved}",
            f"Folder exists: {exists}",
        ]
        if exists:
            details.append(
                f".txt files present there: {all_txt if all_txt else '(none)'}"
            )
            details.append(
                "Note: matching is case-sensitive — 'ascii_art_natta_1.txt' will NOT "
                "match 'ASCII_ART_NATTA_1.txt'."
            )
        else:
            details.append(
                "The folder itself doesn't exist at that path. Make sure "
                "ASCII_ART_FOLDER (and its .txt files) is committed to the repo "
                "at the correct location, and that any 'working-directory' set "
                "in your workflow yml isn't pointing somewhere else."
            )
        raise FileNotFoundError("\n".join(details))

    order = ASCII_FRAME_ORDER if ASCII_FRAME_ORDER is not None else sorted(found.keys())

    frames = []
    for num in order:
        if num not in found:
            raise FileNotFoundError(
                f"ASCII_FRAME_ORDER references frame {num}, but no matching "
                f"ASCII_ART_NATTA_{num}.txt was found in '{folder}'."
            )
        duration = ASCII_FRAME_DURATIONS.get(num, ASCII_FRAME_DEFAULT_DURATION)
        frames.append((num, found[num], duration))

    return frames


INFO_LINES = [
    ("nattaphom0x", None),                       # header line, no key
    ("----------------", None),
    ("Role", "Aspiring Penetration Tester"),
    ("Education", "B.S. Computer Science, KU"),
    ("Status", "Year 4 | Open to Junior/Intern"),
    ("Languages", "Python, C, Bash"),
    ("Coursework", "InfoSec, OS, Networks, Theory"),
    ("Platforms", "TryHackMe"),
    ("Tools", "Burp Suite, Nmap, Wireshark"),
]

# Set to False to hide the live "GitHub Stats" block (repos/stars/
# followers/commits) entirely — handy while those numbers are still low.
SHOW_STATS = False


def build_ascii_animation(frames, art_x: int, art_start_y: int, line_height: int, accent: str) -> tuple:
    """
    Builds the SVG markup for a screen split showing looping ASCII art
    animation frames, plus the CSS keyframes that drive it.

    Returns (svg_markup, css_rules, max_line_count).
    """
    total_duration = sum(d for _, _, d in frames)
    max_lines = max(len(lines) for _, lines, _ in frames)

    svg_groups = []
    css_rules = []

    elapsed = 0.0
    for i, (num, lines, duration) in enumerate(frames):
        start_pct = (elapsed / total_duration) * 100
        end_pct = ((elapsed + duration) / total_duration) * 100
        elapsed += duration

        # Tiny epsilon so the transition reads as an instant frame swap
        # rather than a crossfade.
        eps = 0.05

        tspans = "".join(
            f'<tspan x="{art_x}" y="{art_start_y + j * line_height}">{line}</tspan>'
            for j, line in enumerate(lines)
        )
        svg_groups.append(
            f'<g class="ascii-frame frame-{i}">'
            f'<text fill="{accent}" font-size="13px" xml:space="preserve">{tspans}</text>'
            f'</g>'
        )

        # Build keyframe percentages: invisible everywhere except this
        # frame's [start_pct, end_pct) window.
        keyframe_points = []
        if start_pct <= 0.0:
            keyframe_points.append((0.0, 1))
        else:
            keyframe_points.append((0.0, 0))
            keyframe_points.append((max(start_pct - eps, 0.0), 0))
            keyframe_points.append((start_pct, 1))

        keyframe_points.append((min(end_pct - eps, 100.0), 1))
        if end_pct < 100.0:
            keyframe_points.append((end_pct, 0))
            keyframe_points.append((100.0, 0))
        else:
            keyframe_points.append((100.0, 1))

        body = "".join(
            f"{pct:.3f}% {{ opacity: {op}; }}\n      " for pct, op in keyframe_points
        )
        css_rules.append(
            f"""
    @keyframes asciiFrame{i} {{
      {body}
    }}
    .frame-{i} {{
      opacity: 0;
      animation: asciiFrame{i} {total_duration:.3f}s linear infinite;
    }}"""
        )

    svg_markup = "".join(svg_groups)
    css_block = "".join(css_rules)
    return svg_markup, css_block, max_lines


def render_svg(stats: dict, theme: str, frames) -> str:
    """theme: 'light' or 'dark'"""
    colors = {
        "dark": {"bg": "#0d1117", "text": "#c9d1d9", "accent": "#58a6ff", "key": "#7ee787"},
        "light": {"bg": "#ffffff", "text": "#24292f", "accent": "#0969da", "key": "#116329"},
    }[theme]

    today = date.today().isoformat()

    # --- Left column: animated ASCII art ---
    art_x = 20
    art_start_y = 70   # pushed down to leave room for the big header name
    line_height = 18

    art_animation_markup, art_animation_css, art_line_count = build_ascii_animation(
        frames, art_x, art_start_y, line_height, colors["accent"]
    )

    # --- Right column: neofetch-style info ---
    info_x = 340
    info_start_y = 70
    info_tspans = []
    y = info_start_y
    for key, value in INFO_LINES:
        if value is None:
            info_tspans.append(
                f'<tspan x="{info_x}" y="{y}" fill="{colors["text"]}">{key}</tspan>'
            )
        else:
            info_tspans.append(
                f'<tspan x="{info_x}" y="{y}" fill="{colors["key"]}">{key}: '
                f'<tspan fill="{colors["text"]}">{value}</tspan></tspan>'
            )
        y += line_height

    # --- Live GitHub stats block (optional — controlled by SHOW_STATS) ---
    if SHOW_STATS:
        y += 10
        stats_header_y = y
        y += line_height
        stats_lines = [
            ("Repos", stats["repos"]),
            ("Stars", stats["stars"]),
            ("Followers", stats["followers"]),
            ("Commits (last yr)", stats["commits"]),
        ]
        for key, value in stats_lines:
            info_tspans.append(
                f'<tspan x="{info_x}" y="{y}" fill="{colors["key"]}">{key}: '
                f'<tspan fill="{colors["text"]}">{value}</tspan></tspan>'
            )
            y += line_height

        info_tspans.insert(
            len(INFO_LINES),
            f'<tspan x="{info_x}" y="{stats_header_y}" fill="{colors["accent"]}">- GitHub Stats -</tspan>',
        )

    info_block = (
        f'<text font-size="13px" font-family="Consolas, monospace" '
        f'xml:space="preserve">{"".join(info_tspans)}</text>'
    )

    art_block_height = art_start_y + art_line_count * line_height
    total_height = max(art_block_height, y) + 40

    # --- Big animated header name with a typing effect ---
    header_text = "nattaphom0x"
    header_font_size = 28
    header_char_width = header_font_size * 0.6  # monospace approx
    header_duration = len(header_text) * 0.12
    header_y = 40

    style_rules = f"""
    <style>
      .fade-in {{
        opacity: 0;
        animation: fadeIn 0.5s ease-out forwards;
      }}
      @keyframes fadeIn {{
        to {{ opacity: 1; }}
      }}
      .cursor {{
        animation: blink 1s steps(1) infinite;
      }}
      @keyframes blink {{
        50% {{ opacity: 0; }}
      }}
      .typing-clip {{
        animation: reveal {header_duration}s steps({len(header_text)}) forwards;
      }}
      @keyframes reveal {{
        from {{ width: 0; }}
        to {{ width: {len(header_text) * header_char_width}px; }}
      }}
      {art_animation_css}
    </style>
    """

    header_block = f"""
  <clipPath id="typingClip">
    <rect class="typing-clip" x="{art_x}" y="{header_y - header_font_size}"
          width="0" height="{header_font_size + 10}"/>
  </clipPath>
  <text x="{art_x}" y="{header_y}" fill="{colors['accent']}"
        font-size="{header_font_size}px" font-weight="bold"
        clip-path="url(#typingClip)">{header_text}</text>
  <text x="{art_x + len(header_text) * header_char_width}" y="{header_y}"
        fill="{colors['accent']}" font-size="{header_font_size}px"
        class="cursor" style="animation-delay:{header_duration}s">_</text>
"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{total_height}"
     font-family="Consolas, monospace" font-size="14px">
  {style_rules}
  <rect width="100%" height="100%" fill="{colors['bg']}" rx="10"/>
  {header_block}
  <g class="fade-in" style="animation-delay:0.1s">{art_animation_markup}</g>
  <line x1="320" y1="15" x2="320" y2="{total_height - 20}" stroke="{colors['text']}" stroke-opacity="0.2"/>
  <g class="fade-in" style="animation-delay:0.3s">{info_block}</g>
  <text x="20" y="{total_height - 10}" fill="{colors['text']}" font-size="10px" opacity="0.5">Last updated: {today}</text>
</svg>"""
    return svg


def main():
    stats = get_basic_stats(USERNAME)
    frames = load_ascii_frames(ASCII_ART_FOLDER)
    for theme in ("light", "dark"):
        svg = render_svg(stats, theme, frames)
        with open(f"{theme}_mode.svg", "w", encoding="utf-8") as f:
            f.write(svg)
    print("Generated light_mode.svg and dark_mode.svg with stats:", stats)
    print(f"Loaded {len(frames)} ASCII animation frame(s) from '{ASCII_ART_FOLDER}':")
    for num, lines, duration in frames:
        print(f"  frame {num}: {len(lines)} lines, {duration}s")


if __name__ == "__main__":
    main()
