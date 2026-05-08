"""
Dynamic README updater for GitHub profile.

Updates sections between markers:
  <!-- START_SECTION:overview --> ... <!-- END_SECTION:overview -->
  <!-- START_SECTION:projects --> ... <!-- END_SECTION:projects -->

Required env:
  GH_TOKEN
  GH_USERNAME
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import Counter

import requests

USERNAME = os.environ.get("GH_USERNAME", "Wand-DenaXy")
TOKEN = os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
README = "README.md"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

CURATED_PROJECTS = [
    {
        "owner": "Wand-DenaXy",
        "name": "-Manueli-s-Clubes",
        "title": "Manueli's Clubes",
        "badges": [
            ("FastAPI", "009688", "fastapi", "white"),
            ("Nuxt_4", "00DC82", "nuxtdotjs", "white"),
            ("Stripe", "635BFF", "stripe", "white"),
            ("Docker", "2496ED", "docker", "white"),
            ("Redis", "DC382D", "redis", "white"),
        ],
    },
    {
        "owner": "WeGreenProject",
        "name": "WeGreen-Main",
        "title": "WeGreen",
        "badges": [
            ("PHP_8", "777BB4", "php", "white"),
            ("MySQL_8", "4479A1", "mysql", "white"),
            ("Stripe", "635BFF", "stripe", "white"),
            ("Leaflet", "199900", "leaflet", "white"),
            ("Bootstrap_5", "7952B3", "bootstrap", "white"),
        ],
    },
    {
        "owner": "Wand-DenaXy",
        "name": "FederacaoV2",
        "title": "FederacaoV2",
        "badges": [
            ("Laravel", "FF2D20", "laravel", "white"),
            ("MySQL", "4479A1", "mysql", "white"),
        ],
    },
    {
        "owner": "Wand-DenaXy",
        "name": "Flutter",
        "title": "Flutter",
        "badges": [
            ("Flutter", "02569B", "flutter", "white"),
            ("Dart", "0175C2", "dart", "white"),
            ("Kotlin", "7F52FF", "kotlin", "white"),
        ],
    },
]

PACKAGE_TYPES = ["container", "npm", "maven", "nuget", "rubygems"]


def gh_get(path: str, params: dict | None = None) -> requests.Response:
    url = f"https://api.github.com{path}"
    for _ in range(3):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset_at = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_s = max(reset_at - int(time.time()), 1)
            print(f"Rate limited; waiting {wait_s}s")
            time.sleep(wait_s)
            continue
        # Some endpoints can deny fine-grained tokens for user-scoped metadata.
        # Fallback to unauthenticated request for public data.
        if TOKEN and resp.status_code in (401, 403):
            anon_headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            anon_resp = requests.get(url, headers=anon_headers, params=params, timeout=20)
            return anon_resp
        return resp
    return resp


def resp_json(resp: requests.Response) -> dict | list:
    if not resp.content:
        return []
    try:
        return resp.json()
    except ValueError:
        return []


def gh_json(path: str, params: dict | None = None) -> dict | list:
    resp = gh_get(path, params)
    resp.raise_for_status()
    return resp_json(resp)


def get_user() -> dict:
    return gh_json(f"/users/{USERNAME}")


def get_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        batch = gh_json(
            f"/users/{USERNAME}/repos",
            {"type": "public", "per_page": 100, "page": page},
        )
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def badge(label: str, color: str, logo: str, logo_color: str) -> str:
    safe = label.replace(" ", "+").replace("#", "%23").replace("/", "%2F")
    return (
        f'<img src="https://img.shields.io/badge/{safe}-{color}'
        f'?style=flat-square&logo={logo}&logoColor={logo_color}" />'
    )


def compact_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}k"
    return str(n)


def pct(value: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{(value / total) * 100:.2f}%"


def meter(value: int, total: int, width: int = 18) -> str:
    if total <= 0:
        return "░" * width
    filled = int(round((value / total) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def parse_last_page(link_header: str | None) -> int:
    if not link_header:
        return 1
    m = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link_header)
    return int(m.group(1)) if m else 1


def count_releases(owner: str, repo: str) -> int:
    resp = gh_get(f"/repos/{owner}/{repo}/releases", {"per_page": 1, "page": 1})
    if resp.status_code == 404:
        return 0
    if resp.status_code >= 400:
        return 0
    data = resp_json(resp)
    if not data:
        return 0
    last_page = parse_last_page(resp.headers.get("Link"))
    if last_page == 1:
        return len(data)
    last_resp = gh_get(f"/repos/{owner}/{repo}/releases", {"per_page": 1, "page": last_page})
    if last_resp.status_code >= 400:
        return last_page
    return (last_page - 1) + len(resp_json(last_resp))


def count_packages() -> int:
    total = 0
    for pkg_type in PACKAGE_TYPES:
        resp = gh_get(f"/users/{USERNAME}/packages", {"package_type": pkg_type, "per_page": 100, "page": 1})
        if resp.status_code in (403, 404):
            continue
        if resp.status_code >= 400:
            continue
        items = resp_json(resp)
        if not isinstance(items, list):
            continue
        total += len(items)
        # Rare to exceed 100; if needed, paginate.
        if len(items) == 100:
            page = 2
            while True:
                r = gh_get(f"/users/{USERNAME}/packages", {"package_type": pkg_type, "per_page": 100, "page": page})
                if r.status_code >= 400:
                    break
                batch = resp_json(r)
                if not isinstance(batch, list) or not batch:
                    break
                total += len(batch)
                if len(batch) < 100:
                    break
                page += 1
    return total


def get_total_views_last_14_days(repos: list[dict]) -> int:
    total = 0
    for repo in repos:
        owner = repo.get("owner", {}).get("login", USERNAME)
        name = repo["name"]
        resp = gh_get(f"/repos/{owner}/{name}/traffic/views")
        if resp.status_code >= 400:
            continue
        payload = resp_json(resp)
        if not isinstance(payload, dict):
            continue
        total += int(payload.get("count", 0))
    return total


def get_language_totals(repos: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for repo in repos:
        owner = repo.get("owner", {}).get("login", USERNAME)
        name = repo["name"]
        resp = gh_get(f"/repos/{owner}/{name}/languages")
        if resp.status_code >= 400:
            continue
        langs = resp_json(resp)
        if not isinstance(langs, dict):
            continue
        for lang, b in langs.items():
            totals[lang] = totals.get(lang, 0) + int(b)
    return totals


def get_commits_last_7_days(repos: list[dict]) -> int:
    from datetime import datetime, timezone, timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    total = 0
    for repo in repos:
        owner = repo.get("owner", {}).get("login", USERNAME)
        name = repo["name"]
        resp = gh_get(
            f"/repos/{owner}/{name}/commits",
            {"since": since, "author": USERNAME, "per_page": 1},
        )
        if resp.status_code >= 400:
            continue
        data = resp_json(resp)
        if not isinstance(data, list):
            continue
        link = resp.headers.get("Link")
        if link:
            total += parse_last_page(link)
        else:
            total += len(data)
    return total


def get_repo_commit_count(owner: str, repo: str) -> int:
    # Uses contributor totals as a robust commit approximation without fetching every commit detail.
    resp = gh_get(f"/repos/{owner}/{repo}/contributors", {"per_page": 100, "anon": "true"})
    if resp.status_code >= 400:
        return 0
    data = resp_json(resp)
    if not isinstance(data, list):
        return 0
    return sum(int(c.get("contributions", 0)) for c in data)


def get_repo_file_count(owner: str, repo: str, default_branch: str) -> int:
    resp = gh_get(f"/repos/{owner}/{repo}/git/trees/{default_branch}", {"recursive": "1"})
    if resp.status_code >= 400:
        return 0
    payload = resp_json(resp)
    if not isinstance(payload, dict):
        return 0
    tree = payload.get("tree", [])
    return sum(1 for item in tree if item.get("type") == "blob")


def preferred_license(repos: list[dict]) -> str:
    counter = Counter()
    for repo in repos:
        lic = repo.get("license")
        if lic and lic.get("spdx_id") and lic.get("spdx_id") != "NOASSERTION":
            counter[lic["spdx_id"]] += 1
    if not counter:
        return "No preferred license"
    return counter.most_common(1)[0][0]


def build_overview(repos: list[dict], user: dict) -> str:
    repo_count = int(user.get("public_repos", len(repos)))
    stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    forks = sum(int(r.get("forks_count", 0)) for r in repos)
    used_mb = sum(int(r.get("size", 0)) for r in repos) / 1024.0

    # subscribers_count is not present on list endpoint; fetch per-repo summary.
    watchers = 0
    releases = 0
    commits = 0
    tracked_files = 0
    for repo in repos:
        owner = repo.get("owner", {}).get("login", USERNAME)
        name = repo["name"]

        details_resp = gh_get(f"/repos/{owner}/{name}")
        if details_resp.status_code < 400:
            details_payload = resp_json(details_resp)
            if isinstance(details_payload, dict):
                watchers += int(details_payload.get("subscribers_count", 0))

        releases += count_releases(owner, name)
        commits += get_repo_commit_count(owner, name)
        tracked_files += get_repo_file_count(owner, name, repo.get("default_branch", "main"))

    packages = count_packages()
    views_2w = get_total_views_last_14_days(repos)
    commits_7d = get_commits_last_7_days(repos)
    top_license = preferred_license(repos)

    lang_totals = get_language_totals(repos)
    total_lang_bytes = sum(lang_totals.values())
    top_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    if top_license == "No preferred license":
        license_value = "No preferred license"
    else:
        license_value = top_license

    language_rows = []
    for lang, b in top_langs:
        approx_lines = int(round(b / 30.0))
        language_rows.append(
            "| "
            + f"**{lang}** | {compact_number(approx_lines)} lines | {pct(b, total_lang_bytes)} | `{meter(b, total_lang_bytes)}` |"
        )

    return "\n".join([
        '<div align="center">',
        "",
        f"### {repo_count} Repositories",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| License | `{license_value}` |",
        f"| Releases | `{releases}` |",
        f"| Packages | `{packages}` |",
        f"| Used Space | `{int(round(used_mb))} MB` |",
        "| Sponsors | `0` |",
        f"| Stargazers | `{stars}` |",
        f"| Forkers | `{forks}` |",
        f"| Watchers | `{watchers}` |",
        f"| Views (14d) | `{compact_number(views_2w)}` |",
        f"| Commits (7d) | `{commits_7d}` |",
        "",
        "<br/>",
        "",
        f"### {len(top_langs)} Languages",
        "",
        "**Most used languages**",
        "",
        (
            f"<sub>estimation from {int(round(used_mb))}mb of code in {tracked_files} edited files "
            f"across {commits} commits</sub>"
        ),
        "",
        "| Language | Lines | Share | Distribution |",
        "|---|---:|---:|---|",
        *language_rows,
        "",
        "</div>",
    ])


def build_projects() -> str:
    cards = []
    for p in CURATED_PROJECTS:
        url = f"https://github.com/{p['owner']}/{p['name']}"
        badges = " ".join(badge(*b) for b in p["badges"])
        cards.append(
            "\n".join([
                f"### [{p['title']}]({url})",
                badges,
            ])
        )

    rows = []
    for i in range(0, len(cards), 2):
        left = cards[i]
        right = cards[i + 1] if i + 1 < len(cards) else ""
        rows.append(
            "\n".join([
                "<tr>",
                '<td width="50%" valign="top">',
                "",
                left,
                "",
                "</td>",
                '<td width="50%" valign="top">',
                "",
                right,
                "",
                "</td>",
                "</tr>",
            ])
        )

    return "\n".join([
        '<div align="center">',
        "",
        '<table width="100%">',
        *rows,
        "</table>",
        "",
        "</div>",
    ])


def inject_section(content: str, name: str, new_body: str) -> str:
    pattern = rf"(<!-- START_SECTION:{re.escape(name)} -->).*?(<!-- END_SECTION:{re.escape(name)} -->)"
    repl = rf"\1\n{new_body}\n\2"
    updated, n = re.subn(pattern, repl, content, flags=re.DOTALL)
    if n == 0:
        print(f"[WARN] marker not found for section: {name}")
    return updated


def main() -> None:
    if not TOKEN:
        print("[WARN] GH_TOKEN/GITHUB_TOKEN not set. Using unauthenticated GitHub API.")

    print(f"Loading GitHub data for {USERNAME}...")
    user = get_user()
    repos = get_repos()

    with open(README, "r", encoding="utf-8") as f:
        content = f.read()

    content = inject_section(content, "overview", build_overview(repos, user))
    content = inject_section(content, "projects", build_projects())

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print("README updated successfully.")


if __name__ == "__main__":
    main()
