# Wand-DenaXy — Profile README

Auto-updating GitHub profile powered by GitHub Actions.

## Architecture

```
Wand-DenaXy/              ← public profile repo (username == repo name)
├── README.md             ← rendered on github.com/Wand-DenaXy
├── .github/
│   └── workflows/
│       └── update-readme.yml   ← GitHub Actions pipeline
├── scripts/
│   ├── update_readme.py        ← injects dynamic sections into README
│   └── requirements.txt
└── Github-Fotos/               ← static assets (buttons, photos)
    └── button/
```

## Setup

### 1. Create a Personal Access Token

Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** and create a token with:

- **Repository access:** Only `Wand-DenaXy/Wand-DenaXy`
- **Permissions:** `Contents → Read and write`
- **Permissions:** `Metadata → Read-only`
- **Permissions:** `Workflows → Read and write`

Copy the token.

### 2. Add the secret to this repo

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|------|-------|
| `GH_TOKEN` | *your token from step 1* |

> `GITHUB_TOKEN` (built-in) is used for committing back; `GH_TOKEN` (your PAT) is used for reading all public repos without hitting anonymous rate limits.
> Do not paste the token into `README.md`, workflow files, or commit history. Store it only as a repository secret.

### 3. Push to main

The workflow runs automatically on push, every day at midnight UTC, and on `workflow_dispatch` (manual trigger from the Actions tab).

## How it works

| Section marker | What gets updated |
|----------------|-------------------|
| `currently` | Static intent lines + 3 most recently pushed repos with time delta |
| `overview` | Repo stats + language distribution + language breakdown |
| `projects` | Executive project cards for the strongest repos |
| `waka` | GitHub-driven coding rhythm for the last 7 days |

The script uses comment markers to inject content:

```markdown
<!-- START_SECTION:currently -->
…injected here…
<!-- END_SECTION:currently -->
```

## Adding a new section

1. Add markers to `README.md`:
   ```markdown
   <!-- START_SECTION:mysection -->
   <!-- END_SECTION:mysection -->
   ```
2. Write a `build_mysection(repos)` function in `scripts/update_readme.py`
3. Call `inject_section(content, "mysection", build_mysection(repos))` in `main()`
