import os
import requests
import math
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# CONFIGURATION
# ==========================================

USERNAME = "vuser02454"
TOKEN = os.environ["GH_PROFILE_TOKEN"]

WIDTH = 1200
HEIGHT = 760

BG = (9, 9, 9)
BORDER = (42, 42, 42)
TEXT = (240, 240, 240)
MUTED = (155, 155, 155)

PALETTE = [
    (14, 68, 41),
    (0, 109, 50),
    (38, 166, 65),
    (57, 211, 83)
]

OUTPUT = "generated/contribution-skyline.gif"

# ==========================================
# FONT
# ==========================================

def get_font(size, bold=False):
    path = (
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/"
        "DejaVuSans.ttf"
    )
    return ImageFont.truetype(path, size)

# ==========================================
# FETCH REAL GITHUB CONTRIBUTIONS
# ==========================================

def fetch_contributions():

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=364)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    response = requests.post(
        "https://api.github.com/graphql",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "query": query,
            "variables": {
                "login": USERNAME,
                "from": start.isoformat() + "T00:00:00Z",
                "to": end.isoformat() + "T23:59:59Z"
            }
        },
        timeout=30
    )

    response.raise_for_status()
    result = response.json()

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    user = result["data"]["user"]

    if user is None:
        raise RuntimeError("GitHub user not found")

    calendar = user["contributionsCollection"]["contributionCalendar"]

    contributions = {}

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            contributions[day["date"]] = day["contributionCount"]

    return contributions, calendar["totalContributions"]

# ==========================================
# CALCULATE STATISTICS
# ==========================================

def calculate_stats(data):

    days = sorted(data.items())

    total = sum(data.values())

    busiest = max(days, key=lambda x: x[1])

    longest = 0
    current = 0
    best_start = None
    best_end = None
    run_start = None

    for date, count in days:

        if count > 0:

            if current == 0:
                run_start = date

            current += 1

            if current > longest:
                longest = current
                best_start = run_start
                best_end = date

        else:
            current = 0

    recent = days[-1][1] > 0 if days else False

    if not recent and len(days) > 1:
        recent = days[-2][1] > 0

    streak = 0

    if recent:
        for _, count in reversed(days):
            if count > 0:
                streak += 1
            elif streak:
                break

    return {
        "total": total,
        "busiest": busiest,
        "longest": longest,
        "best_start": best_start,
        "best_end": best_end,
        "current": streak
    }

# ==========================================
# GRID
# ==========================================

def build_grid(data):

    today = datetime.now(timezone.utc).date()

    start = today - timedelta(days=364)

    start -= timedelta(days=(start.weekday() + 1) % 7)

    cells = []

    current = start

    while current <= today:

        key = current.isoformat()
        count = data.get(key, 0)

        cells.append({
            "date": key,
            "count": count,
            "week": (current - start).days // 7,
            "day": (current - start).days % 7
        })

        current += timedelta(days=1)

    values = sorted(
        c["count"] for c in cells if c["count"] > 0
    )

    busy = values[int(0.95 * (len(values) - 1))] if values else 1

    for cell in cells:

        count = cell["count"]

        if count == 0:
            level = 0
        else:
            level = min(3, int(count / busy * 4))

        cell["level"] = level

    return cells

# ==========================================
# ISOMETRIC PROJECTION
# ==========================================

def project(x, y, z):

    yaw = math.pi / 4
    elevation = math.radians(34)

    cs = math.cos(yaw)
    sn = math.sin(yaw)

    se = math.sin(elevation)
    ce = math.cos(elevation)

    sx = x * cs - y * sn
    sy = (x * sn + y * cs) * se - z * ce

    scale = 13

    return (
        360 + sx * scale,
        425 + sy * scale
    )

# ==========================================
# DRAW CUBE
# ==========================================

def draw_cube(draw, x, y, height, color):

    w = 0.85

    top = [
        project(x, y, height),
        project(x + w, y, height),
        project(x + w, y + w, height),
        project(x, y + w, height)
    ]

    left = [
        project(x, y + w, 0),
        project(x + w, y + w, 0),
        top[2],
        top[3]
    ]

    right = [
        project(x + w, y, 0),
        project(x + w, y + w, 0),
        top[2],
        top[1]
    ]

    draw.polygon(
        left,
        fill=tuple(int(c * 0.84) for c in color)
    )

    draw.polygon(
        right,
        fill=tuple(int(c * 0.62) for c in color)
    )

    draw.polygon(top, fill=color)

# ==========================================
# DRAW STATISTICS
# ==========================================

def draw_stats(draw, stats):

    big = get_font(46, True)
    small = get_font(14)
    medium = get_font(18)

    # Right statistics

    draw.text((830, 75), "1 year total", fill=MUTED, font=small)

    draw.text(
        (830, 95),
        f"{stats['total']:,}",
        fill=(57, 211, 83),
        font=big
    )

    draw.text(
        (830, 150),
        "contributions",
        fill=TEXT,
        font=medium
    )

    draw.text((830, 190), "Busiest day", fill=MUTED, font=small)

    draw.text(
        (830, 210),
        str(stats["busiest"][1]),
        fill=(57, 211, 83),
        font=big
    )

    draw.text(
        (830, 265),
        stats["busiest"][0],
        fill=TEXT,
        font=small
    )

    # Left statistics

    draw.text((45, 565), "Longest streak", fill=MUTED, font=small)

    draw.text(
        (45, 585),
        str(stats["longest"]),
        fill=(57, 211, 83),
        font=big
    )

    draw.text((45, 650), "days", fill=TEXT, font=small)

    draw.text((45, 680), "Current streak", fill=MUTED, font=small)

    draw.text(
        (200, 680),
        str(stats["current"]) + " days",
        fill=(57, 211, 83),
        font=medium
    )

# ==========================================
# RENDER FRAME
# ==========================================

def render_frame(cells, stats, progress):

    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BG
    )

    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (20, 20, WIDTH - 20, HEIGHT - 20),
        radius=15,
        outline=BORDER,
        width=2
    )

    draw.text(
        (45, 45),
        f"{stats['total']:,} contributions in the last year",
        fill=TEXT,
        font=get_font(19, True)
    )

    maximum = max((c["count"] for c in cells), default=1)

    # Draw from back to front.

    ordered = sorted(
        cells,
        key=lambda c: c["week"] + c["day"]
    )

    for cell in ordered:

        count = cell["count"]

        if count == 0:
            height = 0.12
            color = (25, 25, 25)
        else:

            full_height = 0.4 + (
                (count / maximum) ** 0.85
            ) * 7.2

            delay = (
                cell["week"] / 53 * 0.36
                + cell["day"] / 6 * 0.06
            )

            rise = max(
                0,
                min(1, (progress - delay) / 0.58)
            )

            rise = 1 - (1 - rise) ** 3

            height = full_height * rise

            color = PALETTE[cell["level"]]

        draw_cube(
            draw,
            cell["week"],
            cell["day"],
            height,
            color
        )

    # Month labels

    previous = -1

    for cell in cells:

        month = int(cell["date"][5:7])

        if month != previous and cell["day"] == 0:

            x, y = project(
                cell["week"] + 0.5,
                8.0,
                0
            )

            label = datetime.strptime(
                cell["date"],
                "%Y-%m-%d"
            ).strftime("%b")

            draw.text(
                (x, y),
                label,
                fill=MUTED,
                font=get_font(12)
            )

        previous = month

    draw_stats(draw, stats)

    # Legend

    draw.text(
        (830, 690),
        "Less",
        fill=MUTED,
        font=get_font(12)
    )

    for i, color in enumerate(PALETTE):

        x = 875 + i * 24

        draw.rounded_rectangle(
            (x, 691, x + 15, 706),
            radius=2,
            fill=color
        )

    draw.text(
        (980, 690),
        "More",
        fill=MUTED,
        font=get_font(12)
    )

    return image

# ==========================================
# MAIN
# ==========================================

def main():

    print("Fetching GitHub contributions...")

    data, _ = fetch_contributions()

    print("Calculating statistics...")

    stats = calculate_stats(data)

    cells = build_grid(data)

    os.makedirs("generated", exist_ok=True)

    frames = []

    print("Rendering animation...")

    # Morph animation

    for i in range(21):

        progress = i / 20

        frame = render_frame(
            cells,
            stats,
            progress
        )

        frames.append(frame)

    # Hold the final 3D view

    for _ in range(8):
        frames.append(frames[-1].copy())

    print("Saving GIF...")

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=65,
        loop=0,
        optimize=True
    )

    print("Generated:", OUTPUT)


if __name__ == "__main__":
    main()
