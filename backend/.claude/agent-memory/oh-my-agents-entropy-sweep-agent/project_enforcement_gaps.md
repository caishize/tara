---
name: enforcement_gaps
description: Rules documented in CONVENTIONS.md/ARCHITECTURE.md that lack active mechanical enforcement — tests skipped or CI workflows missing
type: project
---

## Status as of 2026-03-20

### Permanently Skipped Tests (backend/tests/test_architecture.py)

Three of five architecture tests are permanently skipped with TODO comments:

1. `TestLayerBoundaries.test_no_upward_imports` — skipped: "fix pre-existing cross-layer imports (ai_engine↔modules)". The layer boundary rule is THE core architectural rule but has no active enforcement.

2. `TestFileSizeLimits.test_file_size` — skipped: "30+ pre-existing files exceed 500-line limit. Enforce for new files only." The 500-line Python / 400-line Dart limits in CONVENTIONS.md are entirely unenforced. No new-file-only enforcement mechanism exists either.

3. `TestImportStyle.test_src_uses_relative_imports` — skipped: "audit existing absolute imports within src/". The relative import rule inside `src/` has no active check.

### Rules With Zero Enforcement

| Rule | Documented In | Enforcement |
|------|--------------|-------------|
| No cross-feature imports (mobile Dart) | CONVENTIONS.md | None — no flutter_analyze rule or structural test |
| No mock data in production | CONVENTIONS.md | None |
| Agents must use PendingAction for sensitive ops | ARCHITECTURE.md | None |
| No long-lived in-memory agents | ARCHITECTURE.md | None |
| Family isolation via `verify_member_belongs_to_family()` | CONVENTIONS.md | None |
| Python type union `X \| Y` ban | CONVENTIONS.md | None (mypy does not catch this) |
| `asyncio.timeout()` ban | CONVENTIONS.md | None |
| `str(Enum)` ban | CONVENTIONS.md | None |
| Dart 400-line file limit | CONVENTIONS.md | None |

### What IS Enforced (pre-commit + active tests)

- Black formatter (pre-commit)
- Flake8 linter (pre-commit)
- Mypy type check (pre-commit, `--ignore-missing-imports`)
- Python file snake_case naming (`TestNamingConventions` — active)
- SQLAlchemy DateTime(timezone=True) (`TestDatetimeUsage` — active)
- Architecture guard runs but 3/5 tests are skipped

### CI Gap

`docs/LINTING.md` claims GitHub Actions runs all linting. `.github/workflows/test.yml` exists but its content has not been verified. The pre-commit `architecture-guard` hook uses `|| true` — meaning it NEVER blocks a commit even if architecture tests fail.

**Why:** `|| true` on the architecture-guard means it runs for show only. A failing architecture test will not block any commit.
