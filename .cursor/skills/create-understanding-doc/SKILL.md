---
name: create-understanding-doc
description: >-
  Creates plain-English understanding documents that explain a source spec/plan
  vs a status/experiment file: glossary, section-by-section done/results/Q&A
  tables with numeric evidence and Doubts to ask Rohit Sir. Use when the user
  asks for an understanding doc, help understanding a spec/plan PDF or markdown,
  compare plan vs status, or mentions understanding_and_research.
disable-model-invocation: true
---

# Create Understanding Doc

## When to use

Apply when the user wants to **understand** a source spec/plan and what it asks them to do, compared against a **current status** file (experiment results, implementation status, or analysis).

**User typically provides:**
1. **Source spec** — plan PDF, requirements mail, consolidated plan markdown, or similar
2. **Status file** — experiment report, status analysis, manifest JSON, or implementation tracker
3. **Output directory** — where to write the understanding doc (e.g. `testing/<workstream>/understanding_and_research/`)

If any input is missing, read what exists in the workstream folder and ask once for the missing file before writing.

---

## Core user request (honor verbatim intent)

> Help me understand this doc and what it asks me to do. I need simple english with the meaning of all the technical terms explained as they appear. I will provide the source spec and requirements file along with a current status file.

The output is a **plain-English understanding guide**, not a formal sign-off document or executive summary.

---

## Non-negotiable rules

### 1. Plain English + inline glossary

- Explain what the spec asks the reader to **build, validate, or decide**
- Define **every technical term the first time it appears** in each major section (table or parenthetical)
- Prefer short sentences; avoid boardroom jargon unless the spec uses it

### 2. Plan vs status on every section

For **each section and subsection** in the source spec (e.g. Part A, A1, A2, …):

| Block | Required content |
|-------|------------------|
| **What the spec asks** | 2–5 sentences in plain English |
| **What we did** | Shadow run, production, backfill, scripts — cite status file |
| **Old vs new** | Table when the spec changes labels, counts, thresholds, or architecture |
| **Results** | Numbers from status: n, hit rates, distributions, pass/fail flags |
| **Q&A table** | See template below |

### 3. Q&A table format (mandatory)

Use **four columns** — never combine Answer and Doubts:

```markdown
| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
```

**Answer column:**
- State the conclusion backed by **numbers** (n, %, dates, counts, deltas)
- Cite status artifacts (JSON paths, table rows) when available
- 2–4 sentences minimum for non-trivial questions

**Doubts to ask Rohit Sir column:**
- Frame open items as **questions or doubts for Rohit Sir**
- Prefix with `**Doubt:**` when helpful
- Include the numeric evidence that motivates the doubt

**Banned framing (never use):**
- "Rohit sign-off", "sign-off pending", "awaiting approval", "human decision pending"
- "Production blocker", "Owner: Rohit", "GO/NO-GO gate"
- Column name `Gap` — always use **Doubts to ask Rohit Sir**

**Allowed framing:**
- "Doubts to ask Rohit Sir"
- "Rohit Sir" (not bare "Rohit" in doubt columns)
- "Doubt: With PIVOTING n=27, should we merge into EASING or add PAUSING as a fifth state?"

### 4. Answered? column values

Use one of: **Yes** | **No** | **Partial** | **Partially** | **Open** | **Deferred** | **Not yet**

Match the evidence: do not mark **Yes** if status says untested or sample too small.

### 5. Old vs new tables

When the spec refines dimensions, variables, thresholds, or pipelines, add a comparison table:

```markdown
| Aspect | Old / production | New / spec or shadow | Status |
|--------|------------------|----------------------|--------|
| fed_cycle states | 7 legacy labels | 4 v2 labels | Shadow backfill done; production unchanged |
```

Pull old vs new from spec + status; do not invent production state.

### 6. File output

- Write **one primary markdown file**: `<Topic>_Understanding.md`
- Place in user-specified `understanding_and_research/` (create dir if missing)
- Do **not** create PDF/README unless user asks
- Do **not** duplicate the full spec — summarize and point to source paths

### 7. Consolidated doubts section

After all spec parts, add:

```markdown
## Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
```

Deduplicate doubts from per-section tables. Include 10–20 highest-priority doubts with numbers.

Add a short **How to read the experiment tables** note near the top:

> Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the backtest or status file, not sign-off requests.

---

## Workflow

```
1. Read source spec (full — all parts/deliverables)
2. Read status file + any experiment JSON/manifests referenced
3. List spec sections → build doc outline mirroring spec structure
4. Write core concepts glossary (10–20 terms used across spec)
5. For each section/subsection: spec ask → done → old/new → results → Q&A table
6. Write deliverables checklist (spec vs status: shadow vs production)
7. Write consolidated doubts master list
8. Write artifact index (source + status file paths)
9. Verify: no "Gap" column, no sign-off language, all Q&A rows have numbers in Answer
```

---

## Document skeleton

See [TEMPLATE.md](TEMPLATE.md) for the full outline. Minimum sections:

1. What is this document? (purpose, sources, audience)
2. Core concepts (glossary table)
3. [Mirror spec Part A…N — each with subsections]
4. Deliverables checklist (spec ID vs shadow vs production)
5. Recommended build order (if spec includes sequencing)
6. Doubts to ask Rohit Sir (consolidated master list)
7. Key artifact index
8. How this relates to work already done (1 short paragraph)

---

## Pulling evidence from status files

Priority order for numbers:

1. Experiment manifest / rollup JSON (`experiment_manifest.json`, etc.)
2. Status analysis markdown tables
3. Per-part JSON artifacts (`A_*.json`, `B_*.json`, …)
4. Master experiment report markdown

When status and spec disagree, report both in **Answer** and raise a **Doubt**.

When sample size is below spec thresholds (e.g. n<30, n<5 fires), say so in **Answer** and explain in **Doubts** why the question is not fully closed.

---

## Quality checklist (run before finishing)

- [ ] Every spec part/subpart from source has an experiment-status block
- [ ] Glossary defines terms before heavy use in that part
- [ ] All Q&A tables use columns: Question | Answered? | Answer | Doubts to ask Rohit Sir
- [ ] Answer column includes numbers (n, %, pp, bps, row counts, dates)
- [ ] No "sign-off", "blocker", or "Gap" column language
- [ ] Consolidated doubts section present
- [ ] Source + status file paths in header and artifact index
- [ ] Job status files updated per repo rules (if implementation task in MindWealth_UI)

---

## Example Q&A row

```markdown
| Does 4-state fed_cycle collapse give enough observations? | **Partially** | Shadow backfill over **1,901 Fridays**: TIGHTENING **763** (40.1%), EASING **727** (38.2%), EASY **384** (20.2%), PIVOTING **27** (1.4%). Three states exceed the plan's **≥30 obs** minimum; collapse from 7→4 states roughly doubled per-state counts. | **Doubt:** PIVOTING **n=27** is below the **≥30 obs** rule — should we merge PIVOTING into EASING, widen the definition, or accept it as a rare tail state with mechanism-only evidence? |
```

---

## Related project patterns

- Macro regime example: `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md`
- Status analysis pattern: experiment run date, shadow vs production, artifact paths
- For PDF specs: read PDF fully; cross-check with structured summary if present in `docs/`
