---
name: claude_md_coverage
description: CLAUDE.md coverage gaps, ghost reference findings, and oversized file checks across all 17 nested CLAUDE.md files
type: project
---

## Status as of 2026-03-20

### Coverage Gaps (modules with 5+ source files, no CLAUDE.md)

| Module | Path | Source Files | Verdict |
|--------|------|-------------|---------|
| relationship | backend/src/modules/relationship/ | 7 .py files | MISSING CLAUDE.md |
| external_apis | backend/src/external_apis/ | 4 .py files (base + 3 adapters) | Below threshold, acceptable |
| db | backend/src/db/ | Only session.py + migrations/ | session.py is the only non-migration file; acceptable |
| auth (mobile) | mobile/lib/features/auth/ | 3 subdirs, 12 dart files total | MISSING CLAUDE.md |
| dates (mobile) | mobile/lib/features/dates/ | 3 subdirs, 11 dart files total | MISSING CLAUDE.md |
| gifts (mobile) | mobile/lib/features/gifts/ | 3 subdirs, 13 dart files total | MISSING CLAUDE.md |
| members (mobile) | mobile/lib/features/members/ | 3 subdirs, 20 dart files total | MISSING CLAUDE.md |
| relationships (mobile) | mobile/lib/features/relationships/ | 3 subdirs, 14 dart files total | MISSING CLAUDE.md |

### Ghost References: None Found

All 17 nested CLAUDE.md files were verified. Every key file listed in the "Key Files" tables exists on disk. Zero ghost references.

### File Size: All Under Limit

All 17 nested CLAUDE.md files are under 50 lines. Range: 25–33 lines. Total: 513 lines across all files. Well within limits.

### Signal Count Discrepancy: ai_engine CLAUDE.md vs ARCHITECTURE.md

- `backend/src/ai_engine/CLAUDE.md` line 20: "Classifies mid-conversation user input into **5** intervention types"
- `docs/ARCHITECTURE.md`: Lists **6** signal types (CORRECTION, CANCEL, ADDITIVE, CONFIRM, DIGRESSION, SIDEKICK_INSIGHT)
- The 6th type (SIDEKICK_INSIGHT) comes from the system (sidekick), not user input — so "5 user intervention types" is technically accurate but misleading since the classifier file name suggests all-signal coverage. Should be clarified.
