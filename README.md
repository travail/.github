# .github

Default community health files and issue/PR templates for repositories under the `travail` account.

## Overview

This repository provides default fallback templates that GitHub automatically applies to any repository in the `travail` account that does not define its own templates.

### Issue Templates (`.github/ISSUE_TEMPLATE/`)

- **`general.md`**: Default general-purpose issue template.
- **`bug_report.md`**: Template for reporting reproducible bugs or errors.
- **`feature_request.md`**: Template for proposing new features or enhancements.

### Pull Request Templates (`.github/PULL_REQUEST_TEMPLATE/`)

- **`pull_request_template.md`**: Default pull request template.
- **`bug_fix.md`**: Template tailored for bug fix pull requests (`?template=bug_fix.md`).
- **`release.md`**: Template for release and deployment pull requests (`?template=release.md`).

Individual repositories can override these defaults at any time by defining their own templates in their local `.github/` directory.

### Reusable Workflows (`.github/workflows/`)

Workflows shared by the repositories under the `travail` account. Call them with `uses: travail/.github/.github/workflows/<name>.yml@v1`. Pin to the `v1` tag; do not use `@main`, because a broken change would reach every repository at once.

A reusable workflow cannot choose its own trigger (`on:`). Its token permissions are capped by what the caller grants: the caller writes the `permissions:` block, and the called workflow can only narrow it.

#### `readme-drift-check.yml`

Asks Gemini whether a pull request's diff makes `README.md` out of date, and upserts (or removes) a warning comment on the PR. By default it is advisory only; set `fail-on-drift: true` to fail the job when drift is detected unless the `readme-drift-ack` label is present on the PR. Dependabot PRs are skipped.

| Input / secret | Required | Default | Description |
| --- | --- | --- | --- |
| `timeout-minutes` | no | `1` | Timeout of the step that calls Gemini, in minutes. |
| `tools-ref` | no | `v1` | Ref of this repository to fetch `check_readme_drift.py` from. Leave the default when calling `@v1`; override it only when pinning a fixed ref or testing a branch. |
| `fail-on-drift` | no | `false` | Fail the job when README drift is detected (unless the `readme-drift-ack` label is present). |
| `GEMINI_API_KEY` (secret) | yes | | Passed explicitly by the caller, so each repository keeps its own free-tier quota. |

```yaml
name: README Drift Check

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  check-readme-drift:
    uses: travail/.github/.github/workflows/readme-drift-check.yml@v1
    with:
      timeout-minutes: 3
    secrets:
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

To fail the check on drift and allow acknowledging false positives via the `readme-drift-ack` label, add `labeled` and `unlabeled` to `pull_request.types` and pass `fail-on-drift: true`. The `readme-drift-ack` label must exist in the calling repository.

#### `sync-pr-labels.yml`

Copies the category labels (`bug`, `enhancement`, `maintenance`) of the issues a PR references in its body (`refs #N`, `closes #N`, ...) onto the PR. It only adds labels; it never removes any. References inside code blocks and inline code are ignored. It needs no inputs or secrets.

```yaml
name: Sync PR labels from referenced issue

on:
  pull_request:
    types: [opened, edited, synchronize]

permissions:
  issues: read
  pull-requests: write

jobs:
  sync-labels:
    uses: travail/.github/.github/workflows/sync-pr-labels.yml@v1
```

The label names must exist in the calling repository. Labels are not inherited from this repository.

### Releasing (`.github/workflows/release.yml`)

A manually triggered workflow (`workflow_dispatch`) for tagging releases on `main` and updating the corresponding major tag using only `git` and `gh` with `contents: write` permission.

#### Usage

Run the workflow from the **Actions** tab or via `gh`:

```sh
gh workflow run release.yml -R travail/.github -f version=v1.0.0
```

| Input | Required | Description |
| --- | --- | --- |
| `version` | yes | Release tag in `vX.Y.Z` format (e.g. `v1.0.0`). Must not already exist on `origin`. |

The workflow verifies that it is running on `refs/heads/main`, validates the `vX.Y.Z` format, creates and pushes the annotated tag `vX.Y.Z`, creates a GitHub Release with auto-generated release notes, and then creates or force-updates the major tag (e.g. `v1`) on the same commit.

#### Versioning and Tag Policy

- **Compatible fixes and additions**: Release a fixed tag such as `v1.0.1` or `v1.1.0`. The workflow moves `v1` to the new commit, so callers referencing `@v1` receive updates automatically without a PR.
- **Breaking changes** (removing or renaming inputs, adding required secrets, or incompatible behavior changes): Release `v2.0.0` and create a new `v2` tag without moving `v1`.
- **Caller references**: Reference `@v1` by default; pinning to a SHA or fixed tag is not required. If a caller pins `readme-drift-check.yml` to a fixed tag or SHA, pass the same ref to `tools-ref`.
