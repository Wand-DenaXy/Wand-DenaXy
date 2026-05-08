"""
update_readme.py
────────────────
Auto-updates README.md sections between comment markers:

  <!-- START_SECTION:name -->
  ...dynamic content...
  <!-- END_SECTION:name -->

Sections updated:
    currently  → 3 most recently pushed repos with time delta
    overview   → language breakdown badges with live line counts
    projects   → executive project card table
    waka       → GitHub-driven coding rhythm for the last 7 days

Requires env:
  GH_TOKEN       Personal Access Token (repo scope)
  GH_USERNAME    GitHub username
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# ── Config ───────────────────────────────────────────────────────────────────

USERNAME       = os.environ.get("GH_USERNAME", "Wand-DenaXy")
TOKEN          = os.environ.get("GH_TOKEN", "")
README         = "README.md"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

IGNORED_REPOS = {USERNAME}  # profile repo itself

# Hand-curated projects — rendered as an executive 2 + 1 layout
CURATED = [
    {
        "owner": USERNAME,
        "name": "-Manueli-s-Clubes",
        "display": "Manueli's Clubes",
        "tagline": "Full-stack SaaS · Club Management",
        "desc": "Real Stripe payments, async Celery webhooks, multi-tenancy, RBAC and CI with 84% coverage.",
        "badges": [
            ("FastAPI", "009688", "fastapi", "white"),
            ("Nuxt_4", "00DC82", "nuxtdotjs", "white"),
            ("Stripe", "635BFF", "stripe", "white"),
            ("Docker", "2496ED", "docker", "white"),
            ("Redis", "DC382D", "redis", "white"),
        ],
        "snippet": "34 endpoints · 72 tests · 84% coverage\n5 Docker containers · Celery async workers\nRBAC + Multi-Tenancy · Rate limiting",
        "ci_badge": "[![CI](https://github.com/Wand-DenaXy/-Manueli-s-Clubes/actions/workflows/ci.yml/badge.svg)](https://github.com/Wand-DenaXy/-Manueli-s-Clubes/actions)",
    },
    {
        "owner": "WeGreenProject",
        "name": "WeGreen-Main",
        "display": "WeGreen",
        "tagline": "Full-stack Marketplace · Sustainable Fashion",
        "desc": "Cart + subscriptions + refunds via Stripe, dynamic commissions, 5-tier gamified ranking, Leaflet map, 25 email templates.",
        "badges": [
            ("PHP_8", "777BB4", "php", "white"),
            ("MySQL_8", "4479A1", "mysql", "white"),
            ("Stripe", "635BFF", "stripe", "white"),
            ("Leaflet", "199900", "leaflet", "white"),
            ("Bootstrap_5", "7952B3", "bootstrap", "white"),
        ],
        "snippet": "38 controllers · 40 models · 30+ pages\n7-state return machine · Stripe Refunds\nDynamic commissions (4–6%) · Ranking tiers",
        "ci_badge": "",
    },
    {
        "owner": USERNAME,
        "name": "FederacaoV2",
        "display": "FederaçãoV2",
        "tagline": "Federation Management — v2",
        "desc": "Rebuilt from scratch with multi-tenancy and RBAC architecture.",
        "badges": [
            ("Laravel", "FF2D20", "laravel", "white"),
            ("MySQL", "4479A1", "mysql", "white"),
        ],
        "snippet": "RBAC · Multi-Tenancy · MVC",
        "ci_badge": "",
    },
]

# ── GitHub API helpers ────────────────────────────────────────────────────────

def gh_get(path: str, params: dict | None = None) -> dict | list:
    url = f"https://api.github.com{path}"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait  = max(reset - int(time.time()), 1)
            print(f"Rate limited — waiting {wait}s …")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    sys.exit("GitHub API repeatedly rate-limited. Aborting.")


def get_repos() -> list[dict]:
    repos, page = [], 1
    while True:
        batch = gh_get(f"/users/{USERNAME}/repos", {
            "type": "public", "per_page": 100, "page": page,
        })
        if not batch:
            break
        repos.extend(r for r in batch if not r["fork"] and r["name"] not in IGNORED_REPOS)
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_repo_languages(owner: str, name: str) -> dict[str, int]:
    """Return {language: bytes} for a single repo."""
    try:
        return gh_get(f"/repos/{owner}/{name}/languages")
    except Exception:
        return {}


def get_public_events() -> list[dict]:
    try:
        return gh_get(f"/users/{USERNAME}/events/public", {"per_page": 100})
    except Exception:
        return []


def aggregate_languages(repos: list[dict]) -> list[tuple[str, int]]:
    """Return sorted [(language, bytes)] across all repos."""
    totals: dict[str, int] = {}
    for repo in repos:
        langs = get_repo_languages(USERNAME, repo["name"])
        for lang, b in langs.items():
            totals[lang] = totals.get(lang, 0) + b
    total_bytes = sum(totals.values()) or 1
    return sorted(totals.items(), key=lambda x: x[1], reverse=True)


# ── Section builders ──────────────────────────────────────────────────────────

LANG_BADGE_MAP = {
    "JavaScript": ("F7DF1E", "javascript", "black"),
    "TypeScript": ("3178C6", "typescript", "white"),
    "HTML":       ("E34F26", "html5", "white"),
    "CSS":        ("1572B6", "css3", "white"),
    "Python":     ("3776AB", "python", "white"),
    "PHP":        ("777BB4", "php", "white"),
    "Dart":       ("0175C2", "dart", "white"),
    "Kotlin":     ("7F52FF", "kotlin", "white"),
    "C#":         ("239120", "csharp", "white"),
    "Java":       ("ED8B00", "java", "white"),
    "Shell":      ("4EAA25", "gnubash", "white"),
    "SCSS":       ("CC6699", "sass", "white"),
}


def _badge(label: str, color: str, logo: str, logo_color: str) -> str:
    label_enc = label.replace(" ", "+").replace("#", "%23").replace("/", "%2F")
    return (
        f'<img src="https://img.shields.io/badge/{label_enc}-{color}'
        f'?style=flat-square&logo={logo}&logoColor={logo_color}" />'
    )


def _approx_lines(b: int) -> str:
    if b >= 1_000_000:
        return f"{b/1_000_000:.1f}M lines"
    if b >= 1_000:
        return f"{b/1_000:.1f}k lines"
    return f"{b} lines"


def build_overview(repos: list[dict]) -> str:
    print("  Aggregating language data (may take a moment) …")
    langs = aggregate_languages(repos)
    total_bytes = sum(b for _, b in langs) or 1
    top = langs[:6]

    stats_url = (
        "https://github-readme-stats.vercel.app/api"
        f"?username={USERNAME}&show_icons=true&theme=github_dark"
        "&hide_border=true&bg_color=161b22&title_color=58A6FF"
        "&icon_color=58A6FF&text_color=8b949e&ring_color=58A6FF"
        "&hide=issues&count_private=true&include_all_commits=true"
        "&custom_title=GitHub+Stats"
    )
    langs_url = (
        "https://github-readme-stats.vercel.app/api/top-langs/"
        f"?username={USERNAME}&layout=compact&theme=github_dark"
        "&hide_border=true&bg_color=161b22&title_color=58A6FF"
        "&text_color=8b949e&langs_count=8&custom_title=Language+Distribution"
    )

    lines = [
        '<div align="center">',
        "",
        '<table width="100%">',
        "<tr>",
        '<td width="50%" valign="top" align="center">',
        "",
        f'<img src="{stats_url}" width="100%" />',
        "",
        "</td>",
        '<td width="50%" valign="top" align="center">',
        "",
        f'<img src="{langs_url}" width="100%" />',
        "",
        "</td>",
        "</tr>",
        "</table>",
        "",
        "<br/>",
        "",
        '<table width="88%">',
    ]

    # Build rows of 3
    cells = []
    for lang, b in top:
        pct = b / total_bytes * 100
        info = LANG_BADGE_MAP.get(lang, ("888888", lang.lower(), "white"))
        badge = _badge(lang, *info)
        approx = _approx_lines(b)
        cells.append(
            f'<td align="center" width="33%">\n'
            f"  {badge}<br/>\n"
            f"  <sub><code>{pct:.2f}%</code> &nbsp; {approx}</sub>\n"
            f"</td>"
        )

    # pad to even rows of 3
    while len(cells) % 3 != 0:
        cells.append('<td width="33%"></td>')

    for i in range(0, len(cells), 3):
        lines.append("<tr>")
        for cell in cells[i:i+3]:
            lines.append(cell)
        lines.append("</tr>")

    total_kb = total_bytes // 1024
    total_repos = len(repos)
    lines += [
        "</table>",
        "",
        "<br/>",
        f"<sub>{total_kb:,}kb of code · {total_repos} public repos · "
        f"{sum(r.get('stargazers_count', 0) for r in repos)} stargazers</sub>",
        "",
        "</div>",
    ]
    return "\n".join(lines)


def build_currently(repos: list[dict]) -> str:
    active = sorted(
        repos,
        key=lambda r: r.get("pushed_at") or "1970-01-01T00:00:00Z",
        reverse=True,
    )[:3]

    now = datetime.now(tz=timezone.utc)
    lines = [
        "- 🔨 Deepening full-stack architecture patterns",
        "- 📱 Shipping cross-platform mobile with Flutter",
        "- 🎮 Exploring procedural systems in Unity",
        "- ⚡ Automating this very profile with GitHub Actions",
        "",
        "**Recent pushes:**",
    ]
    for repo in active:
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        delta  = now - pushed
        if delta.days == 0:
            age = "today"
        elif delta.days == 1:
            age = "yesterday"
        else:
            age = f"{delta.days}d ago"
        lines.append(f"- [`{repo['name']}`]({repo['html_url']}) — {age}")

    return "\n".join(lines)


def _render_project_card(p: dict) -> str:
    url = f"https://github.com/{p['owner']}/{p['name']}"
    badge_imgs = " ".join(
        _badge(label, color, logo, lc)
        for label, color, logo, lc in p["badges"]
    )
    snippet_block = "\n".join(f"```\n{p['snippet']}\n```".split("\\n"))
    ci = f"\n\n{p['ci_badge']}" if p["ci_badge"] else ""
    return (
        f"### [{p['display']}]({url})\n"
        f"**{p['tagline']}**\n\n"
        f"{p['desc']}\n\n"
        f"{badge_imgs}\n\n"
        f"```\n{p['snippet']}\n```"
        f"{ci}"
    )


def build_projects(repos: list[dict]) -> str:
    # Build the fixed executive table
    cards = [_render_project_card(p) for p in CURATED]
    rows = [
        f'<tr>\n<td width="50%" valign="top">\n\n{cards[0]}\n\n</td>\n'
        f'<td width="50%" valign="top">\n\n{cards[1]}\n\n</td>\n</tr>',
        f'<tr>\n<td width="50%" valign="top">\n\n{cards[2]}\n\n</td>\n'
        f'<td width="50%" valign="top"></td>\n</tr>',
    ]

    table = '<div align="center">\n\n<table width="100%">\n' + "\n".join(rows) + "\n</table>\n\n</div>"
    return table


def build_waka() -> str:
    """Return a GitHub-driven coding rhythm section for the last 7 days."""
    events = get_public_events()
    now = datetime.now(tz=timezone.utc)
    recent = []
    for event in events:
        created = event.get("created_at")
        if not created:
            continue
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if (now - created_dt).days <= 7:
            recent.append(event)

    push_events = [e for e in recent if e.get("type") == "PushEvent"]
    commit_count = sum(len(e.get("payload", {}).get("commits", [])) for e in push_events)
    active_repos = sorted({e.get("repo", {}).get("name", "") for e in recent if e.get("repo")})
    top_repos = active_repos[:3]

    if not recent:
        return "<sub>Last 7 days · no public activity returned by the GitHub API yet</sub>"

    lines = [
        '<div align="center">',
        f"<sub>Last 7 days · {len(push_events)} pushes · {commit_count} commits · {len(active_repos)} active repos</sub>",
        "",
        "</div>",
        "",
    ]

    if top_repos:
        lines.extend([
            "| Active Repositories |",
            "|---------------------|",
        ])
        lines.extend([f"| `{repo}` |" for repo in top_repos])

    return "\n".join(lines)


# ── README injection ──────────────────────────────────────────────────────────

def inject_section(content: str, name: str, new_body: str) -> str:
    pattern = (
        rf"(<!-- START_SECTION:{re.escape(name)} -->)"
        r".*?"
        rf"(<!-- END_SECTION:{re.escape(name)} -->)"
    )
    replacement = rf"\1\n{new_body}\n\2"
    updated, n = re.subn(pattern, replacement, content, flags=re.DOTALL)
    if n == 0:
        print(f"  [WARN] section '{name}' not found in README — skipping")
    return updated


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TOKEN:
        sys.exit("GH_TOKEN is not set. Export it before running.")

    print(f"Fetching repos for {USERNAME} …")
    repos = get_repos()
    print(f"  Found {len(repos)} public repos")

    with open(README, encoding="utf-8") as f:
        content = f.read()

    print("Injecting section: currently …")
    content = inject_section(content, "currently", build_currently(repos))

    print("Injecting section: overview …")
    content = inject_section(content, "overview", build_overview(repos))

    print("Injecting section: projects …")
    content = inject_section(content, "projects", build_projects(repos))

    print("Injecting section: waka …")
    content = inject_section(content, "waka", build_waka())

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print("Done — README.md updated.")


if __name__ == "__main__":
    main()
