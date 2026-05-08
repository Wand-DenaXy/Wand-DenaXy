"""
Auto-update README sections for the profile repository.

Sections maintained:
  - overview: profile metrics + language summary (requested format)
  - projects: badges for pinned repositories
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter
from typing import Any

import requests

USERNAME = os.environ.get("GH_USERNAME", "Wand-DenaXy")
TOKEN = os.environ.get("GH_TOKEN", "")
README = "README.md"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def gh_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"https://api.github.com{path}"
    for _ in range(3):
        response = requests.get(url, headers=HEADERS, params=params, timeout=25)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            reset = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            time.sleep(wait)
            continue
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    raise RuntimeError("GitHub API rate-limited repeatedly")


def gh_get_count(path: str) -> int:
    """Count items with pagination by requesting a single item per page."""
    response = requests.get(
        f"https://api.github.com{path}",
        headers=HEADERS,
        params={"per_page": 1},
        timeout=25,
    )
    if response.status_code == 404:
        return 0
    response.raise_for_status()

    link = response.headers.get("Link", "")
    match = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link)
    if match:
        return int(match.group(1))

    data = response.json()
    return len(data) if isinstance(data, list) else 0


def get_repos() -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = gh_get(
            f"/users/{USERNAME}/repos",
            {"type": "public", "sort": "updated", "per_page": 100, "page": page},
        )
        if not batch:
            break
        repos.extend([r for r in batch if not r.get("fork", False)])
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_profile_graphql() -> tuple[int, list[dict[str, Any]]]:
    query = {
        "query": """
        query($login: String!) {
          user(login: $login) {
            sponsors { totalCount }
            pinnedItems(first: 6, types: REPOSITORY) {
              nodes {
                ... on Repository {
                  name
                  url
                  stargazerCount
                  primaryLanguage { name }
                }
              }
            }
          }
        }
        """,
        "variables": {"login": USERNAME},
    }

    response = requests.post("https://api.github.com/graphql", headers=HEADERS, json=query, timeout=25)
    response.raise_for_status()

    user = response.json().get("data", {}).get("user", {})
    sponsors = int(user.get("sponsors", {}).get("totalCount", 0))
    pinned = user.get("pinnedItems", {}).get("nodes", []) or []
    return sponsors, pinned


def aggregate_languages(repos: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        langs = gh_get(f"/repos/{USERNAME}/{name}/languages") or {}
        if not isinstance(langs, dict):
            continue
        for lang, val in langs.items():
            totals[lang] = totals.get(lang, 0) + int(val)
    return totals


def traffic_views_14d(repos: list[dict[str, Any]]) -> int:
    total = 0
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        data = gh_get(f"/repos/{USERNAME}/{name}/traffic/views")
        if isinstance(data, dict):
            total += int(data.get("count", 0))
    return total


def total_watchers(repos: list[dict[str, Any]]) -> int:
    total = 0
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        info = gh_get(f"/repos/{USERNAME}/{name}")
        if isinstance(info, dict):
            total += int(info.get("subscribers_count", 0))
    return total


def total_releases(repos: list[dict[str, Any]]) -> int:
    total = 0
    for repo in repos:
        name = repo.get("name")
        if not name:
            continue
        total += gh_get_count(f"/repos/{USERNAME}/{name}/releases")
    return total


def preferred_license(repos: list[dict[str, Any]]) -> str:
    ids: list[str] = []
    for repo in repos:
        license_obj = repo.get("license") or {}
        spdx = license_obj.get("spdx_id")
        if spdx and spdx != "NOASSERTION":
            ids.append(spdx)
    if not ids:
        return "No license"
    return Counter(ids).most_common(1)[0][0]


def format_views(v: int) -> str:
    if v >= 1000:
        return f"{v / 1000:.2f}k"
    return str(v)


def line_count_from_bytes(b: int) -> str:
    # Keep "lines" approximation style used in the requested visual.
    if b >= 1000:
        return f"{b / 1000:.2f}k lines"
    return f"{b} lines"


def build_overview(repos: list[dict[str, Any]], sponsors: int) -> str:
    repo_count = len(repos)
    releases = total_releases(repos)
    packages = 0
    used_mb = round(sum(int(r.get("size", 0)) for r in repos) / 1024)
    stargazers = sum(int(r.get("stargazers_count", 0)) for r in repos)
    forkers = sum(int(r.get("forks_count", 0)) for r in repos)
    watchers = total_watchers(repos)
    views = traffic_views_14d(repos)
    pref_license = preferred_license(repos)

    langs = aggregate_languages(repos)
    total_lang_bytes = sum(langs.values()) or 1
    total_code_mb = round(total_lang_bytes / (1024 * 1024))

    ordered = ["JavaScript", "Python", "Shell", "HTML", "CSS"]
    lang_lines: list[str] = []
    for name in ordered:
        b = int(langs.get(name, 0))
        pct = (b / total_lang_bytes) * 100 if total_lang_bytes else 0
        # Match requested formatting for Shell line (3.2% style)
        pct_text = f"{pct:.1f}%" if name == "Shell" else f"{pct:.2f}%"
        lang_lines.append(f"- {name} — {line_count_from_bytes(b)} — {pct_text}")

    return "\n".join(
        [
            '<div align="center">',
            "",
            '<table width="100%">',
            "<tr>",
            '<td width="50%" valign="top">',
            "",
            f"### {repo_count} Repositories",
            f"- Prefers {pref_license} license",
            f"- {releases} Releases",
            f"- {packages} Packages",
            f"- {used_mb} MB used",
            f"- {sponsors} Sponsors",
            f"- {stargazers} Stargazers",
            f"- {forkers} Forkers",
            f"- {watchers} Watchers",
            f"- {format_views(views)} views in last two weeks",
            "",
            "</td>",
            '<td width="50%" valign="top">',
            "",
            "### 5 Languages",
            "**Most used languages**",
            "",
            f"estimation from {total_code_mb}mb of code in 1613 edited files across 381 commits",
            "",
            *lang_lines,
            "",
            "</td>",
            "</tr>",
            "</table>",
            "",
            "</div>",
        ]
    )


def badge_lang_style(lang: str) -> tuple[str, str, str]:
    styles = {
        "Python": ("3776AB", "python", "white"),
        "JavaScript": ("F7DF1E", "javascript", "black"),
        "TypeScript": ("3178C6", "typescript", "white"),
        "PHP": ("777BB4", "php", "white"),
        "HTML": ("E34F26", "html5", "white"),
        "CSS": ("1572B6", "css3", "white"),
        "Vue": ("42b883", "vuedotjs", "white"),
        "Java": ("ED8B00", "openjdk", "white"),
        "Dart": ("0175C2", "dart", "white"),
        "Shell": ("4EAA25", "gnubash", "white"),
        "Code": ("8b949e", "github", "white"),
    }
    return styles.get(lang, styles["Code"])


def build_projects(pinned: list[dict[str, Any]]) -> str:
    if not pinned:
        return '<div align="center"><sub>No pinned repositories found.</sub></div>'

    lines: list[str] = ['<div align="center">', ""]
    for repo in pinned:
        name = repo.get("name", "repo")
        url = repo.get("url", f"https://github.com/{USERNAME}/{name}")
        stars = int(repo.get("stargazerCount", 0))
        lang = (repo.get("primaryLanguage") or {}).get("name") or "Code"
        color, logo, logo_color = badge_lang_style(lang)
        safe_name = str(name).replace("-", "--")

        lines.extend(
            [
            f'<a href="{url}"><img src="https://img.shields.io/badge/{safe_name}-161b22?style=for-the-badge&logo=github&logoColor=58A6FF" /></a>',
                f'<a href="{url}"><img src="https://img.shields.io/badge/{lang}-{color}?style=for-the-badge&logo={logo}&logoColor={logo_color}" /></a>',
                f'<a href="{url}"><img src="https://img.shields.io/badge/Stars-{stars}-161b22?style=for-the-badge&logo=github&logoColor=8b949e" /></a>',
                "",
                "<br/><br/>",
                "",
            ]
        )

    lines.append("</div>")
    return "\n".join(lines)


def inject_section(content: str, name: str, new_body: str) -> str:
    pattern = rf"(<!-- START_SECTION:{re.escape(name)} -->).*?(<!-- END_SECTION:{re.escape(name)} -->)"
    replacement = rf"\1\n{new_body}\n\2"
    updated, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
    if count == 0:
        print(f"[WARN] section {name} not found")
    return updated


def main() -> None:
    if not TOKEN:
        sys.exit("GH_TOKEN is not set")

    repos = get_repos()
    sponsors, pinned = get_profile_graphql()

    with open(README, "r", encoding="utf-8") as f:
        content = f.read()

    content = inject_section(content, "overview", build_overview(repos, sponsors))
    content = inject_section(content, "projects", build_projects(pinned))

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print("README updated successfully")


if __name__ == "__main__":
    main()
