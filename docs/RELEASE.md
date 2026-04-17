# Release-Workflow

Cutting a new ImageRect release is almost fully automated through
`.github/workflows/release.yml`. Pushing a `vX.Y.Z` tag triggers a
matrix build on `ubuntu-22.04`, `windows-latest`, and `macos-latest`,
then assembles a GitHub Release with the portable binaries plus the
Windows Inno Setup installer.

## TL;DR

```bash
# 1. Bump version in three files (see below).
# 2. Commit + push to main.
git commit -am "release: bump version to X.Y.Z"
git push origin main

# 3. Tag + push. CI does the rest.
git tag vX.Y.Z -m "ImageRect vX.Y.Z — <short subject>"
git push origin vX.Y.Z

# 4. Wait ~8 minutes. Watch the run:
gh run watch $(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')

# 5. Override the auto-generated release notes with your own (optional).
gh release edit vX.Y.Z --notes-file docs/release-notes/vX.Y.Z.md

# 6. Verify assets.
gh release view vX.Y.Z --json assets --jq '.assets[] | "\(.size / 1024 / 1024 | floor) MB  \(.name)"'
```

## Version-Bump — three call sites

These have to agree, otherwise the installer, the packaged app version
string, and the Python distribution metadata drift apart:

| File | Line pattern |
|------|--------------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `imagerect.spec` | `APP_VERSION = "X.Y.Z"` |
| `installer/imagerect.iss` | `#define MyAppVersion "X.Y.Z"` |

Quick sanity check:

```bash
grep -RnE '(0|[1-9][0-9]*)\.[0-9]+\.[0-9]+' pyproject.toml imagerect.spec installer/imagerect.iss
```

## What the release workflow produces

Five assets land on the GitHub Release:

| Asset | Purpose |
|-------|---------|
| `ImageRect.exe` | Windows portable GUI (no installer needed) |
| `ImageRect-cli.exe` | Windows portable CLI |
| `ImageRect` | Linux portable GUI (chmod +x, run directly) |
| `ImageRect-cli` | Linux portable CLI |
| `ImageRect-X.Y.Z-Setup.exe` | Windows installer, built with Inno Setup 6 via `choco install innosetup` in the `build-windows-installer` job |

macOS is built but currently not surfaced as a release asset — the
matrix job runs to catch regressions, the app is not distributed that
way yet.

## Common pitfalls

**Do not `gh release create` manually before the workflow finishes.**
`softprops/action-gh-release@v2` also creates the release (if it does
not exist) and uploads the artifacts. Manual creation races with the
workflow and leads to one of two messy states: the manual release
blocks the automatic one, or your local asset upload is overwritten by
the CI artifact with the same name.

**Release notes.** The workflow uses `generate_release_notes: true`,
which produces GitHub's automatic changelog. If you want curated notes
(the usual case), run `gh release edit vX.Y.Z --notes-file ...` **after**
the workflow completes.

**Tagging first is fine.** You can also tag from a release branch or a
specific SHA. `git tag vX.Y.Z -m "..." <SHA>` followed by
`git push origin vX.Y.Z` triggers the same pipeline.

**Rolling back a bad release.** If the CI run failed mid-matrix or you
tagged the wrong commit:
```bash
gh release delete vX.Y.Z --yes
git push --delete origin vX.Y.Z
git tag -d vX.Y.Z
# fix whatever was wrong, re-tag, re-push.
```

## Local dev loop vs. release loop

These are two different pipelines. Don't confuse them.

- **Local dev** (this host + `ssh win11` to the Win11 VM): run `pytest`,
  `ruff`, `mypy`, and the `--smoke-test` entry point after every commit.
  No tagging. No installer build. See `~/.claude/.../memory/projekte/project_imagerect.md`
  for the exact commands.
- **Release** (`git tag v*` → GitHub Actions): matrix build on three
  runners, Inno Setup installer built on `windows-latest`, all assets
  uploaded by the workflow itself.

The VM build loop is not the source of release artifacts. It exists
to catch "works on Linux, breaks on Windows" regressions *before* they
hit CI, so tagged releases do not fail mid-matrix.

## When to bump major vs. minor vs. patch

- **Patch (`0.2.0 → 0.2.1`)**: security hardening, bug fixes, build
  fixes, no user-visible behaviour change. The current v0.2.1 release is
  a patch because the changes are internal.
- **Minor (`0.2.x → 0.3.0`)**: new user-visible features on the roadmap
  shortlist (auto-feature-detection, DXF export, batch processing,
  etc.).
- **Major (`0.x → 1.0`)**: signals the project considers itself stable
  for external users. Needs a full `TESTING.md` pass on real data, a
  promo pack, and written release notes people can read in two minutes.
