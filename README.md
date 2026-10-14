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
