import os
import io
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageOps, ImageEnhance
from xml.sax.saxutils import escape

USERNAME = "zayanshahid"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PKT = timezone(timedelta(hours=5))

def get_user_ascii_lines(image_source=f"https://github.com/{USERNAME}.png", width=34, height=25):
    chars = " .:-=+*#%@"
    try:
        req = urllib.request.Request(image_source, headers={"User-Agent": "Mozilla/5.0"})
        img_bytes = urllib.request.urlopen(req).read()
        img = Image.open(io.BytesIO(img_bytes))

        img = ImageOps.grayscale(img)
        img = ImageEnhance.Contrast(img).enhance(1.6)
        img = img.resize((width, height), Image.Resampling.LANCZOS)

        pixels = list(img.getdata())
        ascii_lines = []
        for r in range(height):
            row_pixels = pixels[r * width : (r + 1) * width]
            line = "".join(chars[min(len(chars) - 1, int(p / 256 * len(chars)))] for p in row_pixels)
            ascii_lines.append(line.rstrip())
        return ascii_lines
    except Exception:
        return [
            "          ..::--==--::..          ",
            "        .:-=+*#%@@@@%#*+=-:.      ",
            "       :-+#%@@@@@@@@@@@@%#+-.     ",
            "      :=#@@@@@@@@@@@@@@@@@@#=:    ",
            "     .=#@@@@@@@@@@@@@@@@@@@@#=.   ",
            "     :+%@@@#*+==-::-==+*#@@@%+:   ",
            "     -*%@#=-:...    ...:-=#@%*-   ",
            "     =*#%#*++*#%#==#%#*++*#%#*=   ",
            "     +*#%@@@@@@@#++#@@@@@@@%#*+   ",
            "     =*#%@@%#*+=:..:=+*#%@@%#*=   ",
            "     :+*%@#*=--:....:--=*#@%*+:   ",
            "      =*%@#+=+*#%@@%#*+=+#@%*=    ",
            "      :+%@#=*#@@@@@@@@#*=#@%+:    ",
            "       .+#%=+#%@@@@@@%#+=#%+.     ",
            "        .:+*+=+*#%%#*+=+*+:.      ",
            "         .:+#%*+====+*#%#:.       ",
            "        .:=+#@@@@@@@@@@#+=:.      ",
            "      ..-=+*#%@@@@@@@@%#*+=-..    ",
            "    ..:-==+*%@@%####%@@%*+==-..   ",
            "  ..::--==+#@@@%*++*%@@@#+==--::..",
            ".:::---==+*#@@@@%##%@@@@#*+==---::",
            ":::----==+*#@@@@%@@%@@@@#*+==----:",
            ":::----==+*#%@@@%@@%@@@%#*+==----:",
            "::-----==+*#%@@@%@@%@@@%#*+==-----",
            "::-----==+*##@@@%@@%@@@##*+==-----"
        ]

def fetch_github_stats():
    headers = {"User-Agent": "Mozilla/5.0"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = urllib.request.Request(f"https://api.github.com/users/{USERNAME}", headers=headers)
    user = json.loads(urllib.request.urlopen(req).read().decode())
    repos_count = user.get("public_repos", 0)
    followers_count = user.get("followers", 0)

    req_repos = urllib.request.Request(f"https://api.github.com/users/{USERNAME}/repos?per_page=100", headers=headers)
    repos = json.loads(urllib.request.urlopen(req_repos).read().decode())
    stars_count = sum(r.get("stargazers_count", 0) for r in repos if isinstance(r, dict))

    def search_count(query):
        try:
            url = f"https://api.github.com/search/issues?q={query}"
            r = urllib.request.Request(url, headers=headers)
            return json.loads(urllib.request.urlopen(r).read().decode()).get("total_count", 0)
        except Exception:
            return 0

    prs_count = search_count(f"author:{USERNAME}+type:pr")
    issues_count = search_count(f"author:{USERNAME}+type:issue")

    try:
        req_commits = urllib.request.Request(
            f"https://api.github.com/search/commits?q=author:{USERNAME}",
            headers={**headers, "Accept": "application/vnd.github.cloak-preview+json"}
        )
        commits_count = json.loads(urllib.request.urlopen(req_commits).read().decode()).get("total_count", 0)
    except Exception:
        commits_count = 150

    return {
        "repos": repos_count,
        "stars": stars_count,
        "commits": commits_count,
        "followers": followers_count,
        "prs": prs_count,
        "issues": issues_count,
    }

def fmt_line(key, val, total_width=58):
    dots_count = max(2, total_width - len(key) - len(val) - 4)
    dots = "." * dots_count
    return (
        f'<tspan class="dots">.</tspan> '
        f'<tspan class="key">{key}</tspan>'
        f'<tspan class="dots">: {dots} </tspan>'
        f'<tspan class="val">{val}</tspan>'
    )

def fmt_stat_pair(k1, v1, k2, v2):
    s1, s2 = str(v1), str(v2)
    d1 = "." * max(2, 24 - len(k1) - len(s1))
    d2 = "." * max(2, 26 - len(k2) - len(s2))
    return (
        f'<tspan class="dots">.</tspan> '
        f'<tspan class="key">{k1}</tspan><tspan class="dots">: {d1} </tspan><tspan class="val">{s1}</tspan>'
        f' <tspan class="dots">|</tspan> '
        f'<tspan class="key">{k2}</tspan><tspan class="dots">: {d2} </tspan><tspan class="val">{s2}</tspan>'
    )

def build_id_badge(stats, theme="dark"):
    if theme == "dark":
        bg, border, text_col, key_col, val_col, dot_col = "#161b22", "#30363d", "#c9d1d9", "#f0883e", "#79c0ff", "#484f58"
    else:
        bg, border, text_col, key_col, val_col, dot_col = "#ffffff", "#d0d7de", "#24292f", "#bc4c00", "#0969da", "#8c959f"

    ascii_lines = get_user_ascii_lines()
    ascii_svg = "\n".join(
        f'    <text x="35" y="{36 + i*20}">{line.replace("&", "&amp;").replace("<", "&lt;")}</text>'
        for i, line in enumerate(ascii_lines)
    )

    right_rows = [
        (36, f'<tspan class="title">zayanshahid@github</tspan> <tspan class="dots">{"-"*40}</tspan>'),
        (56, '<tspan class="dots">.</tspan>'),
        (76, fmt_line("OS", "Linux / Proxmox VE / WSL")),
        (96, fmt_line("Academic", "MS Computing &amp; Data Science")),
        (116, fmt_line("Host", "shahidse.vercel.app")),
        (136, fmt_line("Kernel", "AI | Python Backend Engineer")),
        (156, fmt_line("IDE", "VS Code / PyCharm")),
        (176, '<tspan class="dots">.</tspan>'),
        (196, fmt_line("Languages.Programming", "Python, Flask, FastAPI, SQL")),
        (216, fmt_line("AI.And.Security", "LangChain, Gemini, MS Presidio")),
        (236, fmt_line("Infrastructure", "Docker, Cloudflare, Nginx, n8n")),
        (256, '<tspan class="dots">.</tspan>'),
        (276, fmt_line("Hobbies.Software", "DLP Scanners, LLM Agents, Home Lab")),
        (296, fmt_line("Hobbies.Real", "Gaming, Live Streaming, Travel")),
        (316, '<tspan class="dots">.</tspan>'),
        (336, f'<tspan class="dots">-</tspan> <tspan class="title">Contact</tspan> <tspan class="dots">{"-"*49}</tspan>'),
        (356, fmt_line("Email", "shaam.laghari@gmail.com")),
        (376, fmt_line("LinkedIn", "muhammad-shahid-979961130")),
        (396, fmt_line("Domain", "cyberverse.space")),
        (416, fmt_line("Website", "shahidse.vercel.app")),
        (436, '<tspan class="dots">.</tspan>'),
        (456, f'<tspan class="dots">-</tspan> <tspan class="title">GitHub Stats</tspan> <tspan class="dots">{"-"*44}</tspan>'),
        (476, fmt_stat_pair("Repos", stats["repos"], "Stars", stats["stars"])),
        (496, fmt_stat_pair("Commits", stats["commits"], "Followers", stats["followers"])),
        (516, fmt_stat_pair("PRs", stats["prs"], "Issues", stats["issues"])),
    ]

    right_svg = "\n".join(f'    <text x="380" y="{y}">{content}</text>' for y, content in right_rows)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="545" viewBox="0 0 960 545">
  <style>
    .bg {{ fill: {bg}; rx: 12px; stroke: {border}; stroke-width: 1.5px; }}
    text {{ font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace; font-size: 14px; fill: {text_col}; white-space: pre; }}
    .ascii {{ fill: {text_col}; font-size: 13.5px; }}
    .title {{ fill: {text_col}; font-weight: bold; }}
    .key {{ fill: {key_col}; }}
    .val {{ fill: {val_col}; }}
    .dots {{ fill: {dot_col}; }}
  </style>
  <rect width="956" height="541" x="2" y="2" class="bg"/>
  <g class="ascii">
{ascii_svg}
  </g>
  <g>
{right_svg}
  </g>
</svg>'''



def build_live_desk():
    now = datetime.now(PKT)
    time_str = now.strftime("%H:%M PKT")
    status = escape("Coding & Building APIs" if 9 <= now.hour <= 23 else "Away / Server Running")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="220" viewBox="0 0 600 220">
  <style>
    .bg {{ fill: #0d1117; rx: 12px; stroke: #30363d; stroke-width: 2px; }}
    .txt {{ font-family: 'JetBrains Mono', monospace; fill: #c9d1d9; font-size: 13px; }}
    .steam {{ stroke: #8b949e; stroke-width: 2; fill: none; stroke-linecap: round; opacity: 0.7; }}
  </style>
  <rect width="596" height="216" x="2" y="2" class="bg"/>
  <rect x="140" y="35" width="320" height="105" rx="6" fill="#161b22" stroke="#58a6ff" stroke-width="2"/>
  <text x="160" y="65" class="txt" fill="#79c0ff">&gt;_ zayanshahid.py</text>
  <text x="160" y="88" class="txt" fill="#a371f7">status: "{status}"</text>
  <text x="160" y="111" class="txt" fill="#3fb950">time:   "{time_str}"</text>
  <rect x="285" y="140" width="30" height="25" fill="#30363d"/>
  <rect x="250" y="165" width="100" height="6" rx="3" fill="#484f58"/>
  <rect x="490" y="130" width="28" height="35" rx="4" fill="#f0883e"/>
  <path d="M518 138 h8 a6 6 0 0 1 6 6 v8 a6 6 0 0 1 -6 6 h-8" fill="none" stroke="#f0883e" stroke-width="4"/>
  <path class="steam" d="M498 122 Q494 112 500 102"><animate attributeName="d" values="M498 122 Q494 112 500 102;M498 122 Q502 112 496 102;M498 122 Q494 112 500 102" dur="2.5s" repeatCount="indefinite"/></path>
  <path class="steam" d="M508 122 Q512 112 506 102"><animate attributeName="d" values="M508 122 Q512 112 506 102;M508 122 Q504 112 510 102;M508 122 Q512 112 506 102" dur="2.5s" repeatCount="indefinite"/></path>
  <line x1="40" y1="171" x2="560" y2="171" stroke="#30363d" stroke-width="4"/>
  <text x="300" y="200" text-anchor="middle" class="txt">⚡ Live Status Desk • Auto-Updated via GitHub Actions</text>
</svg>'''

if __name__ == "__main__":
    s = fetch_github_stats()
    with open("id_badge_dark.svg", "w", encoding="utf-8") as f:
        f.write(build_id_badge(s, "dark"))
    with open("id_badge_light.svg", "w", encoding="utf-8") as f:
        f.write(build_id_badge(s, "light"))
    with open("live_desk.svg", "w", encoding="utf-8") as f:
        f.write(build_live_desk())
