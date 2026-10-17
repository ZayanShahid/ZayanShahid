"""
Generates id_badge_dark.svg, id_badge_light.svg, live_desk.svg and refreshes the
auto-managed sections of README.md (between <!-- NAME:START --> / <!-- NAME:END -->).

Everything GitHub can tell us is pulled live. Everything it cannot (email, hobbies,
private/showcase projects, extra tech) lives in CONFIG / ALWAYS_TECH / FEATURED below.
"""
import hashlib
import io
import json
import os
import re
import urllib.request
from urllib.parse import quote
from collections import Counter
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape

from PIL import Image, ImageOps, ImageEnhance

# ───────────────────────── 1. SETTINGS (edit only this block) ─────────────────────────
USERNAME = "ZayanShahid"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", f"{USERNAME}/{USERNAME}")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
RAW = f"https://raw.githubusercontent.com/{REPO_SLUG}/{BRANCH}"
PKT = timezone(timedelta(hours=5))

# Facts GitHub cannot know. Website/email are taken from your GitHub profile if set there.
CONFIG = {
    "os": "Linux / Proxmox VE / WSL",
    "academic": "MS Computing & Data Science",
    "kernel": "AI | Python Backend Engineer",
    "ide": "VS Code / PyCharm",
    "hobbies_software": "DLP Scanners, LLM Agents, Home Lab",
    "hobbies_real": "Gaming, Live Streaming, Travel",
    "email": "shaam.laghari@gmail.com",
    "linkedin": "muhammad-shahid-979961130",
    "domain": "getsol.tech",
    "website": "shahidse.vercel.app",
    "active_hours": (9, 23),                 # PKT, used when no recent public push exists
    "status_active": "Coding & Building APIs",
    "status_away": "Away / Server Running",
}

# Your stack. Only these badges are shown while AUTO_ADD_DETECTED is False.
AUTO_ADD_DETECTED = False   # True = also add languages/topics found in your repos
ALWAYS_TECH = ["Python", "SQL", "LangChain", "MS Presidio (DLP)", "OpenCV", "Flask", "FastAPI",
               "PostgreSQL", "MongoDB", "Docker", "Proxmox VE", "Cloudflare", "n8n"]

# Showcase projects that are private / not pinned. Shown first in "Top Projects".
FEATURED = [
    ("Enterprise DLP & AI Security Suite", f"https://github.com/{USERNAME}",
     "Multi-tiered Data Loss Prevention scanner integrating regex, Shannon entropy, context scoring, and Microsoft Presidio.",
     ["Python", "MS Presidio", "Regex", "Promptfoo"]),
    ("M365 Copilot Governance Suite", f"https://github.com/{USERNAME}",
     "7-pillar security & compliance assessment suite with automated Graph API auditing and dynamic DOCX reporting.",
     ["Python", "Graph API", "Automation"]),
    ("AI Content & Webhook Orchestrator", "https://getsol.tech",
     "Self-hosted multi-node automation workflows connecting LLMs, webhooks, and custom domain routing.",
     ["n8n", "LangChain", "Gemini API", "Docker"]),
    ("Personal Portfolio", "https://shahidse.vercel.app",
     "My personal portfolio showcasing backend engineering projects, skills, and architecture.",
     ["Vercel", "Python", "REST APIs"]),
]
# After deploying the live endpoint (see live-desk/), put its URL here, e.g.
# "https://live-desk-yourname.vercel.app/api/desk". Empty = use the committed live_desk.svg.
DESK_LIVE_URL = "https://live-desk-nine.vercel.app/"
MAX_PROJECTS = 6
MAX_PER_COLUMN = 6
RECENT_PUSH_HOURS = 3

# name, shields color, logo, column
COLUMNS = ["Languages & Core", "AI & Security", "Backend & Data", "Tools & Cloud Lab"]
BADGES = [
    ("Python", "3776AB", "python", COLUMNS[0]), ("SQL", "4479A1", "postgresql", COLUMNS[0]),
    ("JavaScript", "F7DF1E", "javascript", COLUMNS[0]), ("TypeScript", "3178C6", "typescript", COLUMNS[0]),
    ("Jupyter Notebook", "F37626", "jupyter", COLUMNS[0]), ("HTML", "E34F26", "html5", COLUMNS[0]),
    ("CSS", "1572B6", "css3", COLUMNS[0]),
    ("LangChain", "1C3C3C", "langchain", COLUMNS[1]), ("MS Presidio (DLP)", "0078D4", "microsoft", COLUMNS[1]),
    ("OpenCV", "5C3EE8", "opencv", COLUMNS[1]),
    ("Flask", "000000", "flask", COLUMNS[2]), ("FastAPI", "005571", "fastapi", COLUMNS[2]),
    ("PostgreSQL", "4169E1", "postgresql", COLUMNS[2]), ("MongoDB", "47A248", "mongodb", COLUMNS[2]),
    ("Redis", "DC382D", "redis", COLUMNS[2]),
    ("Docker", "2496ED", "docker", COLUMNS[3]), ("Proxmox VE", "E57000", "proxmox", COLUMNS[3]),
    ("Cloudflare", "F38020", "cloudflare", COLUMNS[3]), ("n8n", "EA4B71", "n8n", COLUMNS[3]),
    ("Nginx", "009639", "nginx", COLUMNS[3]),
]
ALIASES = {"dockerfile": "docker", "presidio": "mspresidiodlp", "postgres": "postgresql"}

# Where each badge links. Anything missing falls back to a search of your own repos.
SITES = {
    "Python": "https://www.python.org", "SQL": "https://en.wikipedia.org/wiki/SQL",
    "JavaScript": "https://developer.mozilla.org/docs/Web/JavaScript", "TypeScript": "https://www.typescriptlang.org",
    "Jupyter Notebook": "https://jupyter.org", "HTML": "https://developer.mozilla.org/docs/Web/HTML",
    "CSS": "https://developer.mozilla.org/docs/Web/CSS",
    "LangChain": "https://www.langchain.com", "MS Presidio (DLP)": "https://microsoft.github.io/presidio/",
    "OpenCV": "https://opencv.org",
    "Flask": "https://flask.palletsprojects.com", "FastAPI": "https://fastapi.tiangolo.com",
    "PostgreSQL": "https://www.postgresql.org", "MongoDB": "https://www.mongodb.com", "Redis": "https://redis.io",
    "Docker": "https://www.docker.com", "Proxmox VE": "https://www.proxmox.com/en/proxmox-virtual-environment",
    "Cloudflare": "https://www.cloudflare.com", "n8n": "https://n8n.io", "Nginx": "https://nginx.org",
}

# ───────────────────────── 2. GITHUB DATA ─────────────────────────
def api(path, body=None):
    url = path if path.startswith("http") else f"https://api.github.com{path}"
    headers = {"User-Agent": "profile-readme-generator", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # network / rate limit / auth
        print(f"[warn] {url} -> {e}")
        return None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


BY_KEY = {norm(b[0]): b for b in BADGES}


def resolve(name, generic_column=None):
    k = norm(name)
    k = ALIASES.get(k, k)
    if k in BY_KEY:
        return BY_KEY[k]
    return (name, "555555", None, generic_column) if generic_column else None


def build_tech_columns(lang_bytes, topics):
    cols = {c: [] for c in COLUMNS}

    def add(entry):
        if not entry:
            return
        name, _, _, col = entry
        if name not in [e[0] for e in cols[col]] and len(cols[col]) < MAX_PER_COLUMN:
            cols[col].append(entry)

    for n in ALWAYS_TECH:
        add(resolve(n, COLUMNS[2]))
    if AUTO_ADD_DETECTED:
        total = sum(lang_bytes.values()) or 1
        for lang, b in lang_bytes.most_common(8):
            if b / total >= 0.02:
                add(resolve(lang, COLUMNS[0]))
        for t in sorted(topics):
            add(resolve(t))      # topics only count if we know the badge
    return cols


def fetch_data():
    user = api(f"/users/{USERNAME}")
    if not user:
        raise SystemExit("GitHub API unavailable - keeping the previous generated files.")

    repos, page = [], 1
    while True:
        chunk = api(f"/users/{USERNAME}/repos?per_page=100&page={page}&sort=pushed") or []
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r.get("fork")]

    lang_bytes = Counter()
    for r in own[:20]:
        lang_bytes.update(api(f"/repos/{r['full_name']}/languages") or {})
    topics = {t for r in own for t in (r.get("topics") or [])}

    def total(path):
        res = api(path)
        return res.get("total_count") if res else None

    stats = {
        "repos": user.get("public_repos", len(repos)),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "followers": user.get("followers", 0),
        "commits": total(f"/search/commits?q=author:{USERNAME}"),
        "prs": total(f"/search/issues?q=author:{USERNAME}+type:pr"),
        "issues": total(f"/search/issues?q=author:{USERNAME}+type:issue"),
    }

    last_push = None
    for e in api(f"/users/{USERNAME}/events/public?per_page=30") or []:
        if e.get("type") == "PushEvent":
            ts = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
            last_push = (e["repo"]["name"].split("/")[-1], ts)
            break

    return {"user": user, "own": own, "stats": stats, "last_push": last_push,
            "cols": build_tech_columns(lang_bytes, topics), "pinned": fetch_pinned(own)}


def fetch_pinned(own):
    q = ('{ user(login:"%s"){ pinnedItems(first:6, types:REPOSITORY){ nodes{ ... on Repository{ '
         'name url description primaryLanguage{name} repositoryTopics(first:3){nodes{topic{name}}} } } } } }'
         % USERNAME)
    res = api("https://api.github.com/graphql", {"query": q})
    try:
        nodes = res["data"]["user"]["pinnedItems"]["nodes"]
    except Exception:
        nodes = []
    out = []
    for n in nodes:
        stack = ([n["primaryLanguage"]["name"]] if n.get("primaryLanguage") else []) + \
                [t["topic"]["name"] for t in n["repositoryTopics"]["nodes"]]
        out.append((n["name"], n["url"], n.get("description") or "", stack))
    if out:
        return out
    top = sorted(own, key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at") or ""), reverse=True)
    return [(r["name"], r["html_url"], r.get("description") or "",
             ([r["language"]] if r.get("language") else []) + (r.get("topics") or [])[:3]) for r in top[:4]]

# ───────────────────────── 3. SVG BUILDERS ─────────────────────────
FALLBACK_ASCII = [
    "          ..::--==--::..          ", "        .:-=+*#%@@@@%#*+=-:.      ",
    "       :-+#%@@@@@@@@@@@@%#+-.     ", "      :=#@@@@@@@@@@@@@@@@@@#=:    ",
    "     .=#@@@@@@@@@@@@@@@@@@@@#=.   ", "     :+%@@@#*+==-::-==+*#@@@%+:   ",
    "     -*%@#=-:...    ...:-=#@%*-   ", "     =*#%#*++*#%#==#%#*++*#%#*=   ",
    "     +*#%@@@@@@@#++#@@@@@@@%#*+   ", "     =*#%@@%#*+=:..:=+*#%@@%#*=   ",
    "     :+*%@#*=--:....:--=*#@%*+:   ", "      =*%@#+=+*#%@@%#*+=+#@%*=    ",
    "      :+%@#=*#@@@@@@@@#*=#@%+:    ", "       .+#%=+#%@@@@@@%#+=#%+.     ",
    "        .:+*+=+*#%%#*+=+*+:.      ", "         .:+#%*+====+*#%#:.       ",
    "        .:=+#@@@@@@@@@@#+=:.      ", "      ..-=+*#%@@@@@@@@%#*+=-..    ",
    "    ..:-==+*%@@%####%@@%*+==-..   ", "  ..::--==+#@@@%*++*%@@@#+==--::..",
    ".:::---==+*#@@@@%##%@@@@#*+==---::", ":::----==+*#@@@@%@@%@@@@#*+==----:",
    ":::----==+*#%@@@%@@%@@@%#*+==----:", "::-----==+*#%@@@%@@%@@@%#*+==-----",
    "::-----==+*##@@@%@@%@@@##*+==-----",
]


def get_user_ascii_lines(url, width=34, height=25):
    chars = " .:-=+*#%@"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        img = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=20).read()))
        img = ImageOps.grayscale(img)
        img = ImageEnhance.Contrast(img).enhance(1.6)
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        px = list(img.getdata())
        return ["".join(chars[min(len(chars) - 1, int(p / 256 * len(chars)))]
                        for p in px[r * width:(r + 1) * width]).rstrip() for r in range(height)]
    except Exception:
        return FALLBACK_ASCII


def fmt_line(key, val, total_width=58):
    key, val = str(key), str(val)
    dots = "." * max(2, total_width - len(key) - len(val) - 4)
    return ('<tspan class="dots">.</tspan> '
            f'<tspan class="key">{escape(key)}</tspan><tspan class="dots">: {dots} </tspan>'
            f'<tspan class="val">{escape(val)}</tspan>')


def fmt_stat_pair(k1, v1, k2, v2):
    s1, s2 = str(v1), str(v2)
    d1 = "." * max(2, 24 - len(k1) - len(s1))
    d2 = "." * max(2, 26 - len(k2) - len(s2))
    return ('<tspan class="dots">.</tspan> '
            f'<tspan class="key">{k1}</tspan><tspan class="dots">: {d1} </tspan><tspan class="val">{s1}</tspan>'
            ' <tspan class="dots">|</tspan> '
            f'<tspan class="key">{k2}</tspan><tspan class="dots">: {d2} </tspan><tspan class="val">{s2}</tspan>')


def join_fit(names, limit=36):
    out = ""
    for n in names:
        nxt = f"{out}, {n}" if out else n
        if len(nxt) > limit:
            break
        out = nxt
    return out or "-"


def clean_url(u):
    return re.sub(r"^https?://", "", (u or "").strip()).rstrip("/")


def build_id_badge(d, theme="dark"):
    if theme == "dark":
        bg, border, text_col, key_col, val_col, dot_col = "#161b22", "#30363d", "#c9d1d9", "#f0883e", "#79c0ff", "#484f58"
    else:
        bg, border, text_col, key_col, val_col, dot_col = "#ffffff", "#d0d7de", "#24292f", "#bc4c00", "#0969da", "#8c959f"

    s, c, u = d["stats"], d["cols"], d["user"]
    show = lambda v: "-" if v is None else v
    names = lambda col: join_fit([e[0] for e in c[col]])
    site = clean_url(u.get("blog")) or CONFIG["website"]
    email = u.get("email") or CONFIG["email"]
    dot = '<tspan class="dots">.</tspan>'
    head = lambda t, n: f'<tspan class="dots">-</tspan> <tspan class="title">{t}</tspan> <tspan class="dots">{"-" * n}</tspan>'

    rows = [
        f'<tspan class="title">{USERNAME.lower()}@github</tspan> <tspan class="dots">{"-" * 40}</tspan>', dot,
        fmt_line("OS", CONFIG["os"]), fmt_line("Academic", CONFIG["academic"]), fmt_line("Host", site),
        fmt_line("Kernel", CONFIG["kernel"]), fmt_line("IDE", CONFIG["ide"]), dot,
        fmt_line("Languages.Programming", names(COLUMNS[0])), fmt_line("Backend.And.Data", names(COLUMNS[2])),
        fmt_line("AI.And.Security", names(COLUMNS[1])), fmt_line("Infrastructure", names(COLUMNS[3])), dot,
        fmt_line("Hobbies.Software", CONFIG["hobbies_software"]), fmt_line("Hobbies.Real", CONFIG["hobbies_real"]), dot,
        head("Contact", 49), fmt_line("Email", email), fmt_line("LinkedIn", CONFIG["linkedin"]),
        fmt_line("Domain", CONFIG["domain"]), fmt_line("Website", site), dot,
        head("GitHub Stats", 44),
        fmt_stat_pair("Repos", s["repos"], "Stars", s["stars"]),
        fmt_stat_pair("Commits", show(s["commits"]), "Followers", s["followers"]),
        fmt_stat_pair("PRs", show(s["prs"]), "Issues", show(s["issues"])),
    ]

    ascii_lines = get_user_ascii_lines(u.get("avatar_url") or f"https://github.com/{USERNAME}.png")
    n = max(len(rows), len(ascii_lines))
    height = 36 + 20 * (n - 1) + 29
    ascii_svg = "\n".join(f'    <text x="35" y="{36 + i * 20}">{escape(l)}</text>' for i, l in enumerate(ascii_lines))
    right_svg = "\n".join(f'    <text x="380" y="{36 + i * 20}">{r}</text>' for i, r in enumerate(rows))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}">
  <style>
    .bg {{ fill: {bg}; rx: 12px; stroke: {border}; stroke-width: 1.5px; }}
    text {{ font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace; font-size: 14px; fill: {text_col}; white-space: pre; }}
    .ascii {{ fill: {text_col}; font-size: 13.5px; }}
    .title {{ fill: {text_col}; font-weight: bold; }}
    .key {{ fill: {key_col}; }}
    .val {{ fill: {val_col}; }}
    .dots {{ fill: {dot_col}; }}
  </style>
  <rect width="956" height="{height - 4}" x="2" y="2" class="bg"/>
  <g class="ascii">
{ascii_svg}
  </g>
  <g>
{right_svg}
  </g>
</svg>'''


def pick_status(last_push, now):
    if last_push:
        repo, ts = last_push
        if now - ts < timedelta(hours=RECENT_PUSH_HOURS):
            return f"Coding: {repo if len(repo) <= 16 else repo[:15] + '…'}"
    lo, hi = CONFIG["active_hours"]
    return CONFIG["status_active"] if lo <= now.astimezone(PKT).hour <= hi else CONFIG["status_away"]


def build_live_desk(last_push=None):
    now = datetime.now(PKT)
    time_str = now.strftime("%H:%M PKT")
    status = escape(pick_status(last_push, now))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="220" viewBox="0 0 600 220">
  <style>
    .bg {{ fill: #0d1117; rx: 12px; stroke: #30363d; stroke-width: 2px; }}
    .txt {{ font-family: 'JetBrains Mono', monospace; fill: #c9d1d9; font-size: 13px; }}
    .steam {{ stroke: #8b949e; stroke-width: 2; fill: none; stroke-linecap: round; opacity: 0.7; }}
  </style>
  <rect width="596" height="216" x="2" y="2" class="bg"/>
  <rect x="140" y="35" width="320" height="105" rx="6" fill="#161b22" stroke="#58a6ff" stroke-width="2"/>
  <text x="160" y="65" class="txt" fill="#79c0ff">&gt;_ {USERNAME.lower()}.py</text>
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

# ───────────────────────── 4. README SECTIONS ─────────────────────────
def badge_md(entry):
    name, color, logo, _ = entry
    label = name.replace("-", "--").replace("_", "__").replace(" ", "_")
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    img = f"![{name}](https://img.shields.io/badge/{label}-{color}?style=flat{logo_part})"
    url = SITES.get(name) or f"https://github.com/search?q=user%3A{USERNAME}+language%3A{quote(name)}&type=repositories"
    return f"[{img}]({url})"


def tech_block(cols):
    cells = ["<br>".join(badge_md(e) for e in cols[c]) or "-" for c in COLUMNS]
    return ('<div align="center">\n\n'
            "| " + " | ".join(f"**{c}**" for c in COLUMNS) + " |\n"
            "| " + " | ".join([":---:"] * len(COLUMNS)) + " |\n"
            "| " + " | ".join(cells) + " |\n\n</div>")


def projects_block(pinned):
    rows, seen = [], set()
    for name, url, desc, stack in FEATURED + pinned:
        if name.lower() in seen or len(rows) >= MAX_PROJECTS:
            continue
        seen.add(name.lower())
        desc = (desc or "-").replace("|", "\\|").replace("\n", " ")
        tags = " ".join(f"`{t}`" for t in stack) or "-"
        rows.append(f"| **[{name}]({url})** | {desc} | {tags} |")
    return "| Project | Description | Tech Stack |\n| :--- | :--- | :--- |\n" + "\n".join(rows)


def short_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]


def replace_block(text, name, body):
    pat = re.compile(rf"(<!-- {name}:START -->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pat.search(text):
        print(f"[warn] README marker '{name}' not found - skipped")
        return text
    return pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def update_readme(d, dark, light, desk, path="README.md"):
    if not os.path.exists(path):
        print("[warn] README.md not found - skipped")
        return
    text = open(path, encoding="utf-8").read()
    hd, hl, hk = short_hash(dark), short_hash(light), short_hash(desk)
    badge = (f'  <picture>\n'
             f'    <source media="(prefers-color-scheme: dark)" srcset="{RAW}/id_badge_dark.svg?v={hd}">\n'
             f'    <source media="(prefers-color-scheme: light)" srcset="{RAW}/id_badge_light.svg?v={hl}">\n'
             f'    <img src="{RAW}/id_badge_dark.svg?v={hd}" width="100%" alt="Developer Profile Neofetch Terminal" />\n'
             f'  </picture>')
    text = replace_block(text, "BADGE", badge)
    text = replace_block(text, "TECH", tech_block(d["cols"]))
    text = replace_block(text, "PROJECTS", projects_block(d["pinned"]))
    desk_src = DESK_LIVE_URL or f"{RAW}/live_desk.svg?v={hk}"
    text = replace_block(text, "DESK", f"[![Live Developer Desk]({desk_src})]({DESK_LIVE_URL or RAW + '/live_desk.svg'})")
    open(path, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    data = fetch_data()
    dark, light = build_id_badge(data, "dark"), build_id_badge(data, "light")
    desk = build_live_desk(data["last_push"])
    for fname, content in (("id_badge_dark.svg", dark), ("id_badge_light.svg", light), ("live_desk.svg", desk)):
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
    update_readme(data, dark, light, desk)
