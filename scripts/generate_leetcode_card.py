#!/usr/bin/env python3
"""Generate a self-contained LeetCode profile SVG for a GitHub README.

LeetCode's GraphQL endpoint is undocumented and may change. The script fails
clearly if the response shape changes; it never fabricates statistics.
"""
import json
import os
import html
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = os.getenv("LEETCODE_USERNAME", "QZVx2lKXnu")
OUTPUT = Path(os.getenv("OUTPUT_PATH", "assets/leetcode-card.svg"))
THEME_BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ORANGE = "#ffa116"
GREEN = "#39d353"
YELLOW = "#d29922"
BLUE = "#58a6ff"

QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    badges { id displayName icon }
    submitStats {
      acSubmissionNum { difficulty count submissions }
    }
    userCalendar {
      activeYears
      streak
      totalActiveDays
      submissionCalendar
    }
  }
  allQuestionsCount {
    difficulty
    count
  }
}
"""

def fetch_profile():
    payload = json.dumps({"query": QUERY, "variables": {"username": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://leetcode.com/graphql",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/{USERNAME}/",
            "User-Agent": "Mozilla/5.0 (compatible; GitHubReadmeStats/1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach LeetCode GraphQL endpoint: {exc}") from exc
    if body.get("errors"):
        raise RuntimeError("LeetCode GraphQL returned errors: " + json.dumps(body["errors"])[:1200])
    data = body.get("data") or {}
    user = data.get("matchedUser")
    if not user:
        raise RuntimeError(f"LeetCode user '{USERNAME}' was not found or profile is private.")
    return user

def safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default

def esc(value):
    return html.escape(str(value), quote=True)

def text(x, y, value, size=14, fill=TEXT, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{esc(value)}</text>')

def rect(x, y, w, h, fill, rx=8, stroke="none"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>'

def generate(user):
    stats = user.get("submitStats") or {}
    rows = {r.get("difficulty"): r for r in stats.get("acSubmissionNum", [])}
    easy = safe_int((rows.get("Easy") or {}).get("count"))
    medium = safe_int((rows.get("Medium") or {}).get("count"))
    hard = safe_int((rows.get("Hard") or {}).get("count"))
    total = safe_int((rows.get("All") or {}).get("count"), easy + medium + hard)
    if total == 0:
        total = easy + medium + hard
    ranking = safe_int((user.get("profile") or {}).get("ranking"))
    calendar_raw = (user.get("userCalendar") or {}).get("submissionCalendar") or "{}"
    try:
        calendar = json.loads(calendar_raw) if isinstance(calendar_raw, str) else calendar_raw
    except json.JSONDecodeError:
        calendar = {}
    calendar = {safe_int(k): safe_int(v) for k, v in calendar.items()}
    active_days = safe_int((user.get("userCalendar") or {}).get("totalActiveDays"))
    streak = safe_int((user.get("userCalendar") or {}).get("streak"))
    badges = (user.get("badges") or [])[:8]

    # LeetCode's acceptance rate is not exposed consistently by the public profile query.
    # Avoid inventing it; show total accepted submissions instead.
    accepted_submissions = sum(safe_int((r or {}).get("submissions")) for r in rows.values())

    width, height = 900, 510
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<title>LeetCode statistics and badges</title>',
        rect(1, 1, 898, 508, THEME_BG, 16, BORDER),
        text(30, 42, "LeetCode", 25, ORANGE, 700),
        text(30, 67, f"@{USERNAME}", 13, MUTED),
        f'<a href="https://leetcode.com/u/{esc(USERNAME)}/" target="_blank">',
        rect(745, 24, 125, 34, ORANGE, 8),
        text(807, 46, "VIEW PROFILE", 11, "#111111", 700, "middle"),
        '</a>',
        rect(24, 88, 852, 112, PANEL, 12, BORDER),
    ]
    # Main metrics
    metrics = [
        ("PROBLEMS SOLVED", f"{total:,}", TEXT),
        ("EASY", f"{easy:,}", GREEN),
        ("MEDIUM", f"{medium:,}", YELLOW),
        ("HARD", f"{hard:,}", "#ff6b6b"),
        ("GLOBAL RANK", f"#{ranking:,}" if ranking else "N/A", BLUE),
    ]
    xs = [48, 220, 370, 525, 700]
    for x, (label, value, color) in zip(xs, metrics):
        out += [text(x, 120, label, 10, MUTED, 700), text(x, 160, value, 25, color, 700)]
    out += [
        text(48, 184, f"{accepted_submissions:,} accepted submissions", 11, MUTED),
        text(530, 184, f"{active_days} active days  •  {streak}-day streak", 11, MUTED),
        text(30, 235, "ACTIVITY HEATMAP", 12, TEXT, 700),
        text(870, 235, "Last 365 days", 10, MUTED, 400, "end"),
    ]

    # 53 columns x 7 rows, ending today (UTC); align Monday-first.
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    start -= timedelta(days=start.weekday())
    cell, gap = 10, 4
    heat_x, heat_y = 30, 253
    max_count = max(calendar.values(), default=1)
    for day_index in range(371):
        date = start + timedelta(days=day_index)
        if date > today or date < today - timedelta(days=364):
            continue
        count = calendar.get(int(datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp()), 0)
        # LeetCode calendar keys are Unix timestamps at day boundaries; account for timezone offsets.
        if count == 0:
            for ts, val in calendar.items():
                try:
                    if datetime.fromtimestamp(ts, timezone.utc).date() == date:
                        count = val
                        break
                except (ValueError, OSError):
                    pass
        intensity = 0 if count == 0 else min(4, 1 + int((count / max_count) * 3))
        colors = ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"]
        col, row = day_index // 7, day_index % 7
        out.append(rect(heat_x + col * (cell + gap), heat_y + row * (cell + gap),
                        cell, cell, colors[intensity], 2))
    out += [
        text(30, 365, f"{active_days} active days in the available activity history", 11, MUTED),
        text(30, 402, "EARNED BADGES", 12, TEXT, 700),
    ]

    if not badges:
        out.append(text(30, 440, "No public badges returned by LeetCode for this profile.", 12, MUTED))
    else:
        badge_y = 416
        badge_w = 100
        for i, badge in enumerate(badges):
            x = 30 + i * 106
            out.append(rect(x, badge_y, 96, 70, PANEL, 9, BORDER))
            icon = badge.get("icon") or ""
            # Badge icons are referenced from LeetCode's CDN. GitHub may not render
            # remote SVG images embedded inside SVGs, so show a reliable local-style
            # medallion and the real badge title instead of a broken external image.
            out.append(f'<circle cx="{x+48}" cy="{badge_y+23}" r="13" fill="#3b2b12" stroke="{ORANGE}" stroke-width="1.5"/>')
            out.append(text(x+48, badge_y+28, "★", 16, ORANGE, 700, "middle"))
            name = badge.get("displayName") or "LeetCode Badge"
            if len(name) > 15:
                name = name[:14] + "…"
            out.append(text(x+48, badge_y+56, name, 9, TEXT, 600, "middle"))
    out += [
        text(30, 496, "Generated automatically with GitHub Actions", 9, MUTED),
        text(870, 496, "leetcode.com", 9, MUTED, 400, "end"),
        "</svg>",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUTPUT} for {USERNAME}: {total} solved, {len(badges)} badges")

if __name__ == "__main__":
    generate(fetch_profile())
