---
name: sweep_trends
description: Recurring entropy patterns and institutional knowledge built across sweep sessions
type: project
---

## Trends as of 2026-03-20 (Sweeps 5, 6, 7)

### Pattern: Skipped Tests as Permanent Dead Weight

The architecture test file has 3 permanently skipped tests. These tests were presumably written when violations were first discovered, then skipped instead of fixing the violations. This is a known trap: skipped tests give false confidence that enforcement exists. The `|| true` in `.pre-commit-config.yaml` compounds this — even the non-skipped tests cannot block a commit.

**Recommendation**: Either fix the violations and unskip, or convert to warning-only CI step that reports counts without blocking, so the number can be tracked over time.

### Pattern: Well-Maintained CLAUDE.md (Positive Signal)

All 17 nested CLAUDE.md files:
- Are well under the 50-line limit (25–33 lines each)
- Have zero ghost references — every listed key file exists
- Follow a consistent format (Purpose / Layer Rules / Key Files / Module Conventions)

This is a strong positive signal. The team is keeping these files current as code evolves.

### Pattern: Mobile Feature Modules Grow Without Documentation

5 mobile feature modules (auth, dates, gifts, members, relationships) have 11–20 Dart files each with no CLAUDE.md. These are likely older modules that predate the CLAUDE.md convention. Members (20 files) is the most critical gap.

### Pattern: Migration Numbers as Implicit Assertions

The active exec plan (briefing-collapse-lazy-history) asserts migration number 129. Migration 129 already exists (`129_add_conversation_message_id_index.py`). Exec plans that assert migration file numbers will produce false-passing structural tests if the number is already used for a different migration. Plans should assert migration content, not just number.

### Pattern: Rule Documentation Outpaces Enforcement

CONVENTIONS.md explicitly states "every rule here should be testable by a structural test or lint rule" — but at least 9 rules have no mechanical check. The document is aspirational, not descriptive. This gap is known but not tracked.
