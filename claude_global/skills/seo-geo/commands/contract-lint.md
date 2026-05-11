---
name: contract-lint
description: Validate auditor Runbook inline copies, handoff schema compliance, and jargon leaks across all SKILL.md files. Produces drift report.
argument-hint: "[--skill <name>] [--strict]"
parameters:
  - name: skill
    type: string
    required: false
    description: Limit the scan to a single skill directory. If omitted, scans all skills in the library.
  - name: strict
    type: boolean
    required: false
    description: Exit with non-zero status if ANY drift is found (for CI use). Default is report-only.
---

# Contract Lint

> Validates auditor Runbook inline copies, handoff schema compliance, and user-facing jargon leaks across all SKILL.md files. Part of the [SEO & GEO Skills Library](https://github.com/aaron-he-zhu/seo-geo-claude-skills).

**Authoritative check list**: this command validates [references/auditor-runbook.md §6 Lint Coverage Manifest](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/auditor-runbook.md). When the Runbook §6 manifest changes, update this command's check list in the same commit. If the two disagree, the Runbook wins.

## What It Checks

### Runbook drift (high severity)

| Check | Target | Method |
|---|---|---|
| **Source sha256 match** (Attack A) | Both auditor-class SKILL.md files carry the same `source_sha256` in `<!-- runbook-sync start: source_sha256=... block_sha256=... -->` and that hash matches the current Runbook file | Run `shasum -a 256 references/auditor-runbook.md`; compare to each auditor's `source_sha256` marker. Detects "runbook was edited but inlined copies not re-synced." |
| **Block sha256 match** (Attack B — the harder case) | The content between `<!-- runbook-sync start -->` and `<!-- runbook-sync end -->` in each auditor matches the declared `block_sha256`. This catches tampering inside the inlined block even when the source file is unchanged. | Extract the bytes between the sync markers (excluding the markers themselves); run `shasum -a 256` on that extract; compare to declared `block_sha256`. |
| **Block sha256 matches extracted §1-5** | The `block_sha256` in the marker should also equal the sha256 of the §1-5 range extracted from the current Runbook source file (so that `source_sha256` + `block_sha256` together uniquely pin both the file and the inlined region). | Extract §1-5 from the source runbook (`awk '/^## §1 · Handoff Schema/,/^## §6 · Lint Coverage Manifest/' references/auditor-runbook.md \| sed '$d'`); run `shasum -a 256`; compare to the `block_sha256` values. |
| **Runbook block present** | Every auditor-class skill has a `<!-- runbook-sync start -->` / `<!-- runbook-sync end -->` pair and both the `source_sha256` and `block_sha256` attributes are present | Glob `**/SKILL.md` filtered by `class: auditor` frontmatter; regex-check both attributes |
| **Inlined §1-5 sections present** | Within each sync block: §1 Handoff Schema, §2 Decision Table + 3 Worked Examples, §3 Guardrail table, §4 Artifact Gate 7-item checklist, §5 Translation Layer | Regex for section headers |

### Handoff schema drift (high severity)

| Check | Target | Method |
|---|---|---|
| **Cap fields declared for auditors** | Auditor-class SKILL.md mentions `cap_applied`, `raw_overall_score`, `final_overall_score` | Grep |
| **Non-auditor skills do NOT emit cap fields** | Non-auditor SKILL.md files do not reference `cap_applied` in example handoffs | Grep with exclusion list |
| **Handoff array shape** | `key_findings` with `title` + `severity` + `evidence` appears in auditor handoffs | Regex |

### Source of truth drift (medium severity)

| Check | Target | Method |
|---|---|---|
| **No restated cap numbers** | `60/100`, `cap at 60`, `capped at 60` appear ONLY in `references/auditor-runbook.md` §2 and `references/contract-fail-caps.md` (if present). Benchmarks and auditor SKILL.md must LINK to runbook, not restate | Grep repo-wide; exclude allowed files |
| **Veto item definition consolidation** | T04/C01/R10 defined in `core-eeat-benchmark.md`; T03/T05/T09 in `cite-domain-rating.md`. No other file defines these as vetos | Grep |

### User-facing jargon leaks (medium severity)

| Check | Target | Method |
|---|---|---|
| **Veto IDs in example outputs** | Strings `T04`, `C01`, `R10`, `T03`, `T05`, `T09` must not appear inside example user output blocks in auditor SKILL.md | Scan Markdown code blocks labeled as user-facing examples |
| **Internal field names in examples** | `cap_applied`, `raw_overall_score`, `final_overall_score`, `gap_type` must not appear in user-facing example blocks | Same as above |
| **Raw-to-capped numeric deltas** | Patterns like `82 → 60`, `82 -> 60`, `capped at 60` must not appear in user-facing example blocks | Same |

### Guardrail windowing (medium severity)

| Check | Target | Method |
|---|---|---|
| **Year rule is windowed** | Runbook §3 Guardrail entry for year markers includes `current_year − 2` or equivalent windowing language | Grep Runbook source |
| **No unconditional year positives** | No SKILL.md says "year markers are always positive" or equivalent | Regex scan |

## Ownership Rule (do not lint against)

These patterns are ALLOWED to restate the cap number `60`, veto IDs, and Runbook content because they are either source definitions or architecturally-required inlined copies:

**Source files (single source of truth)**:
- `references/auditor-runbook.md` — Runbook source, can contain everything
- `references/contract-fail-caps.md` (v7.2.0+) — cap numbers source
- `references/core-eeat-benchmark.md` — CORE-EEAT item definitions
- `references/cite-domain-rating.md` — CITE item definitions
- `references/decisions/` — ADRs historically captured; exempt from current-state lint

**Inlined copies (architecturally required by ADR-001)**:
- `cross-cutting/content-quality-auditor/SKILL.md` — the `<!-- runbook-sync start --> ... <!-- runbook-sync end -->` region is an authorized inline of Runbook §1-5. Restatements OF cap numbers / veto IDs / arithmetic inside this block are expected. Drift is detected via the dual-hash mechanism above, not via grep for restated content.
- `cross-cutting/domain-authority-auditor/SKILL.md` — same treatment.

**Informational mentions (allowed outside sync blocks)**:
- `VERSIONS.md` — changelog prose can say "caps at 60" when explaining the rule
- `memory/hot-cache.md` — may summarize "Critical Fail Cap (60/100)" in the active index
- `references/AUDITOR-AUTHORS.md` — may reference "60" in anti-pattern examples for instructional purposes
- `README.md` top-level descriptions are exempt

These exemptions prevent contract-lint from false-positive-flagging the inlined Runbook blocks (which ADR-001 explicitly requires to contain restatements) and allow one-line informational mentions in user-facing documentation.

## Usage

```
/seo:contract-lint                              # full scan
/seo:contract-lint --skill content-quality-auditor   # single skill
/seo:contract-lint --strict                     # exit non-zero on any drift (CI mode)
```

## Output

Report written to `references/lint-latest.md` (committed location — not `memory/` which is runtime only).

### Output format

```markdown
# Contract Lint Report — YYYY-MM-DD HH:MM

**Runbook source sha256**: <hash>
**Runbook version**: <version from Runbook frontmatter>

## Runbook Drift (N found)

| # | File | Check | Expected | Actual | Action |
|---|------|-------|----------|--------|--------|
| 1 | content-quality-auditor/SKILL.md | source_sha256 | 5bdea697... | a1b2c3d4... | Re-run sync procedure from AUDITOR-AUTHORS.md |
| 2 | domain-authority-auditor/SKILL.md | block_sha256 | ebd83df6... | 9d8e7f6a... | Block content was edited directly — re-inline from source |

## Handoff Schema Drift (N found)

| # | Skill | Missing field | Required by |
|---|-------|--------------|------------|

## Source of Truth Drift (N found)

| # | File | Restated content | Correct source |
|---|------|-----------------|---------------|
| 1 | optimize/foo/SKILL.md | "cap at 60" | references/contract-fail-caps.md |

## User-Facing Jargon Leaks (N found)

| # | Skill | Leak pattern | Location |
|---|-------|-------------|---------|
| 1 | content-quality-auditor/SKILL.md | "T04 failed" in example output | line 520 |

## Summary

- Skills scanned: N
- Runbook drift: N
- Handoff drift: N
- SoT drift: N
- Jargon leaks: N
- **Total issues: N**
- **Exit status**: clean | warnings | drift (strict mode fails here)
```

## What It Does NOT Do

- No auto-fix. Drift reports are surfaced for human review.
- No runtime validation of actual handoffs. That is the job of the PostToolUse Artifact Gate hook (v7.2.0).
- No validation of non-auditor skills beyond the handoff schema check.
- No validation of the Runbook source file itself — the source is authoritative by definition.

## Self-Maintenance

**Important**: when [references/auditor-runbook.md §6 Lint Coverage Manifest](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/auditor-runbook.md) changes, this command's check list must be updated in the same commit. If they disagree, the Runbook §6 wins and contract-lint is out of date.

Drift between this command and Runbook §6 is itself a lintable condition — contract-lint opens by verifying that its internal check list matches §6. If it doesn't, it refuses to run and recommends the maintainer update this file.

## Notes

> **For new auditor-class skill authors**: to register a new auditor-class skill with contract-lint, add `class: auditor` to your SKILL.md frontmatter. The lint discovers auditor skills by frontmatter glob, not by hardcoded manifest. See [AUDITOR-AUTHORS.md](https://github.com/aaron-he-zhu/seo-geo-claude-skills/blob/main/references/AUDITOR-AUTHORS.md) for the full onboarding guide.
