"""
update_readme.py
────────────────
Auto-updates README.md sections between comment markers:

  <!-- START_SECTION:name -->
  ...dynamic content...
  <!-- END_SECTION:name -->

Sections updated:
  - currently    → detects what repos were active recently
  - stats        → keeps static (served by github-readme-stats CDN)
  - projects     → top starred + most recent repos as a Markdown table

Requires:
  - GH_TOKEN  : Personal Access Token (repo scope)
  - GH_USERNAME : GitHub username (set in workflow env)
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# ── Config ──────────────────────────────────────────────────────────────────

USERNAME = os.environ.get("GH_USERNAME", "Wand-DenaXy")
TOKEN    = os.environ.get("GH_TOKEN", "")
README   = "README.md"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Repos that should never appear in the featured section (abandoned / forks)
IGNORED_REPOS = {"Wand-DenaXy"}  # profile repo itself

# ── GitHub API helpers ───────────────────────────────────────────────────────

def gh_get(path: str, params: dict | None = None) -> dict | list:
    """GET from GitHub REST API with basic rate-limit handling."""
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
    """Return all public non-fork repos for the user."""
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


# ── Section builders ─────────────────────────────────────────────────────────

def build_currently(repos: list[dict]) -> str:
    """
    Show the 3 most recently pushed-to repos as 'currently working on'.
    Keeps the static lines already in the README and appends a live
    'latest push' line so it's always fresh.
    """
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
        lines.append(
            f"- [`{repo['name']}`]({repo['html_url']}) — {age}"
        )

    return "\n".join(lines)


def build_projects(repos: list[dict]) -> str:
    """
    Build a Markdown table of the best repos.
    Priority: hand-curated list first, then top-starred.
    """
    CURATED = [
        ("WeGreenProject", "WeGreen-Main",
         "Environmental platform — collaborative green initiative",
         "`Next.js` `REST API` `MVC`"),
        (USERNAME, "Federacao",
         "Federation management system",
         "`PHP` `Laravel` `MySQL`"),
        (USERNAME, "FederacaoV2",
         "Rebuilt with multi-tenancy & RBAC architecture",
         "`Laravel` `RBAC` `Multi-Tenancy`"),
        (USERNAME, "Flutter",
         "Cross-platform mobile experiments",
         "`Flutter` `Dart` `Kotlin`"),
    ]

    rows = []
    for owner, name, desc, stack in CURATED:
        url = f"https://github.com/{owner}/{name}"
        rows.append(f"| [**{name}**]({url}) | {desc} | {stack} |")

    # Add any extra high-starred repos not already listed
    curated_names = {n for _, n, _, _ in CURATED}
    extras = sorted(
        [r for r in repos if r["stargazers_count"] > 0 and r["name"] not in curated_names],
        key=lambda r: r["stargazers_count"],
        reverse=True,
    )[:2]
    for repo in extras:
        lang  = f"`{repo['language']}`" if repo.get("language") else "`—`"
        desc  = (repo.get("description") or "—")[:60]
        rows.append(f"| [**{repo['name']}**]({repo['html_url']}) | {desc} | {lang} |")

    header = (
        "<div align=\"center\">\n\n"
        "| Project | Description | Stack |\n"
        "|---------|-------------|-------|\n"
    )
    return header + "\n".join(rows) + "\n\n</div>"


# ── README injection ─────────────────────────────────────────────────────────

def inject_section(content: str, name: str, new_body: str) -> str:
    """Replace everything between START/END markers for a given section name."""
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


# ── Main ─────────────────────────────────────────────────────────────────────

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

    print("Injecting section: projects …")
    content = inject_section(content, "projects", build_projects(repos))

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print("Done — README.md updated.")


if __name__ == "__main__":
    main()
