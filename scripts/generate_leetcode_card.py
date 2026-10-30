#!/usr/bin/env python3
"""
Generate a modern, single-card LeetCode profile SVG.

The card contains:
- Problem counts (All / Easy / Medium / Hard)
- Global ranking
- 365-day submission heatmap
- Actual LeetCode badge artwork (downloaded from each badge's icon URL
  and embedded as base64 data inside the SVG)

LeetCode's GraphQL endpoint is undocumented and may change.
"""
import base64
import html
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = os.getenv("LEETCODE_USERNAME", "QZVx2lKXnu")
OUTPUT = Path(os.getenv("OUTPUT_PATH", "assets/leetcode-card.svg"))

BG = "#0b1118"
CARD = "#111a24"
CARD_ALT = "#141f2b"
BORDER = "#263443"
TEXT = "#edf3f8"
MUTED = "#91a0af"
ORANGE = "#ffa116"
GREEN = "#32d583"
YELLOW = "#f5b942"
RED = "#ff6b6b"
BLUE = "#58a6ff"

QUERY = """
query userCard($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    badges { id displayName icon }
    submitStats {
      acSubmissionNum { difficulty count submissions }
    }
    userCalendar {
      streak
      totalActiveDays
      submissionCalendar
    }
  }
}
"""

def request_json(url, payload=None, headers=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()

def get_profile():
    body = request_json(
        "https://leetcode.com/graphql",
        {"query": QUERY, "variables": {"username": USERNAME}},
        {
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/{USERNAME}/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    result = json.loads(body.decode("utf-8"))
    if result.get("errors"):
        raise RuntimeError("LeetCode GraphQL error: " + json.dumps(result["errors"])[:1000])
    user = (result.get("data") or {}).get("matchedUser")
    if not user:
        raise RuntimeError(f"LeetCode profile '{USERNAME}' was not found or is not public.")
    return user

def integer(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default

def esc(value):
    return html.escape(str(value), quote=True)

def svg_text(x, y, value, size=14, color=TEXT, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        f'font-family="Inter,Segoe UI,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">'
        f'{esc(value)}</text>'
    )

def rounded_rect(x, y, width, height, fill=CARD, radius=16, stroke=BORDER):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )

def download_badge_as_data_uri(icon_url):
    """Download official badge artwork and embed it in the SVG."""
    if not icon_url:
        return None
    if icon_url.startswith("//"):
        icon_url = "https:" + icon_url
    if not icon_url.startswith("https://"):
        return None
    try:
        raw = request_json(
            icon_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://leetcode.com/",
            },
        )
        if len(raw) > 1_500_000:
            return None
        lower = icon_url.lower().split("?")[0]
        if lower.endswith(".svg") or raw.lstrip().startswith(b"<svg"):
            mime = "image/svg+xml"
        elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
            mime = "image/jpeg"
        elif lower.endswith(".webp"):
            mime = "image/webp"
        else:
            mime = "image/png"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    except Exception as exc:
        print(f"Warning: unable to download badge artwork {icon_url}: {exc}")
        return None

def parse_calendar(user):
    raw = (user.get("userCalendar") or {}).get("submissionCalendar") or "{}"
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return {}

def generate_svg(user):
    stats = user.get("submitStats") or {}
    by_difficulty = {
        item.get("difficulty"): item
        for item in stats.get("acSubmissionNum", [])
    }

    all_count = integer((by_difficulty.get("All") or {}).get("count"))
    easy = integer((by_difficulty.get("Easy") or {}).get("count"))
    medium = integer((by_difficulty.get("Medium") or {}).get("count"))
    hard = integer((by_difficulty.get("Hard") or {}).get("count"))
    if not all_count:
        all_count = easy + medium + hard

    rank = integer((user.get("profile") or {}).get("ranking"))
    calendar = parse_calendar(user)
    calendar = {integer(k): integer(v) for k, v in calendar.items()}
    user_calendar = user.get("userCalendar") or {}
    active_days = integer(user_calendar.get("totalActiveDays"))
    streak = integer(user_calendar.get("streak"))

    badges = (user.get("badges") or [])[:8]
    accepted_submissions = sum(
        integer((item or {}).get("submissions"))
        for item in by_difficulty.values()
    )

    width, height = 1000, 690
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="100%" height="auto" viewBox="0 0 {width} {height}">',
        '<title>LeetCode profile statistics, activity heatmap and earned badges</title>',
        '<defs>',
        '<linearGradient id="headerGlow" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0%" stop-color="#ffa116" stop-opacity=".16"/>',
        '<stop offset="100%" stop-color="#ffa116" stop-opacity="0"/>',
        '</linearGradient>',
        '<linearGradient id="cardGlow" x1="0" y1="0" x2="1" y2="0">',
        '<stop offset="0%" stop-color="#1a2a39"/>',
        '<stop offset="100%" stop-color="#111a24"/>',
        '</linearGradient>',
        '</defs>',
        rounded_rect(1, 1, 998, 688, BG, 22, BORDER),
        '<rect x="2" y="2" width="996" height="150" rx="20" fill="url(#headerGlow)"/>',
    ]

    # Header
    svg += [
        svg_text(34, 54, "Leet", 35, TEXT, 750),
        svg_text(103, 54, "Code", 35, ORANGE, 750),
        svg_text(36, 82, f"@{USERNAME}", 15, MUTED, 500),
        svg_text(36, 108, "SOLVE  ·  LEARN  ·  IMPROVE  ·  REPEAT", 11, MUTED, 600),
        f'<a xlink:href="https://leetcode.com/u/{esc(USERNAME)}/" target="_blank">',
        rounded_rect(810, 30, 155, 43, ORANGE, 12, ORANGE),
        svg_text(887, 57, "VIEW PROFILE ↗", 12, "#151515", 750, "middle"),
        '</a>',
    ]

    # Metric cards
    metric_y, metric_h = 132, 132
    cards = [
        (28, 250, "PROBLEMS SOLVED", f"{all_count:,}", "ACCEPTED PROBLEMS", TEXT),
        (290, 155, "EASY", f"{easy:,}", "SOLVED", GREEN),
        (455, 155, "MEDIUM", f"{medium:,}", "SOLVED", YELLOW),
        (620, 155, "HARD", f"{hard:,}", "SOLVED", RED),
        (785, 187, "GLOBAL RANK", f"#{rank:,}" if rank else "N/A", "LEETCODE RANK", BLUE),
    ]
    for x, w, label, value, foot, color in cards:
        svg.append(rounded_rect(x, metric_y, w, metric_h, "url(#cardGlow)", 15, BORDER))
        svg.append(svg_text(x + 18, metric_y + 31, label, 10, MUTED, 700))
        svg.append(svg_text(x + 18, metric_y + 78, value, 29 if w > 200 else 26, color, 750))
        svg.append(svg_text(x + 18, metric_y + 108, foot, 10, MUTED, 500))

    svg += [
        svg_text(30, 291, f"{accepted_submissions:,} accepted submissions", 11, MUTED),
        svg_text(970, 291, f"{active_days} active days  ·  {streak}-day streak", 11, MUTED, 500, "end"),
    ]

    # Heatmap panel
    svg += [
        rounded_rect(28, 310, 944, 225, CARD, 17, BORDER),
        svg_text(50, 345, "ACTIVITY HEATMAP", 14, TEXT, 750),
        svg_text(950, 345, "LAST 365 DAYS", 10, MUTED, 600, "end"),
    ]

    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=364)
    first_day -= timedelta(days=first_day.weekday())
    heat_x, heat_y, cell, gap = 52, 370, 11, 5
    max_value = max(calendar.values(), default=1)
    palette = ["#202b36", "#0e4429", "#006d32", "#26a641", "#39d353"]

    # Month labels
    last_month = None
    for day_index in range(371):
        date = first_day + timedelta(days=day_index)
        if date > today or date < today - timedelta(days=364):
            continue
        col, row = day_index // 7, day_index % 7
        if date.month != last_month and date.day <= 7:
            svg.append(svg_text(heat_x + col * (cell + gap), 365, date.strftime("%b"), 10, MUTED, 500))
            last_month = date.month

        timestamp = int(datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp())
        count = calendar.get(timestamp, 0)
        if not count:
            # LeetCode may serialize timestamps using a different day-boundary timezone.
            for ts, value in calendar.items():
                try:
                    if datetime.fromtimestamp(ts, timezone.utc).date() == date:
                        count = value
                        break
                except (ValueError, OSError):
                    continue
        level = 0 if count == 0 else min(4, 1 + int((count / max_value) * 3))
        svg.append(rounded_rect(
            heat_x + col * (cell + gap),
            heat_y + row * (cell + gap),
            cell, cell, palette[level], 3, "none"
        ))

    svg += [
        svg_text(50, 505, f"{active_days} active days in the available activity history", 10, MUTED),
        svg_text(950, 505, "Less   ▪ ▪ ▪ ▪   More", 10, MUTED, 500, "end"),
    ]

    # Badge panel: use actual icon images supplied by LeetCode.
    svg += [
        rounded_rect(28, 550, 944, 115, CARD, 17, BORDER),
        svg_text(50, 580, "EARNED BADGES", 14, TEXT, 750),
        svg_text(950, 580, f"{len(badges)} BADGES", 10, MUTED, 600, "end"),
    ]

    if not badges:
        svg.append(svg_text(50, 625, "No public badges were returned for this profile.", 12, MUTED))
    else:
        badge_width = 105
        gap_x = 10
        start_x = 48
        for index, badge in enumerate(badges):
            x = start_x + index * (badge_width + gap_x)
            icon_data = download_badge_as_data_uri(badge.get("icon"))
            display_name = badge.get("displayName") or "LeetCode Badge"
            svg.append(rounded_rect(x, 592, badge_width, 61, CARD_ALT, 11, BORDER))
            if icon_data:
                svg.append(
                    f'<image x="{x + 8}" y="600" width="42" height="42" '
                    f'preserveAspectRatio="xMidYMid meet" xlink:href="{icon_data}"/>'
                )
            else:
                # If LeetCode's badge CDN is unavailable, retain a visible fallback.
                svg.append(f'<circle cx="{x + 29}" cy="621" r="17" fill="#3b2b12" stroke="{ORANGE}"/>')
                svg.append(svg_text(x + 29, 627, "★", 18, ORANGE, 700, "middle"))

            label = display_name if len(display_name) <= 13 else display_name[:12] + "…"
            svg.append(svg_text(x + 57, 627, label, 9, TEXT, 600))

    svg += [
        svg_text(30, 680, "Generated with GitHub Actions", 9, MUTED),
        svg_text(970, 680, "leetcode.com", 9, MUTED, 400, "end"),
        "</svg>",
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated {OUTPUT} | solved={all_count} | badges={len(badges)}")

if __name__ == "__main__":
    try:
        generate_svg(get_profile())
    except Exception as error:
        raise SystemExit(f"LeetCode card generation failed: {error}")
