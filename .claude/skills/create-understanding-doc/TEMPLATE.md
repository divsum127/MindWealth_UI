# [Topic] — Plain-English Understanding Guide

**For:** [Audience]  
**Source spec:** `[path/to/source.pdf or .md]`  
**Status file:** `[path/to/status_analysis.md]` (run date: YYYY-MM-DD)  
**Purpose:** Explain what the spec asks you to build, what every technical term means, what we already tested, and **what doubts to raise with Rohit Sir**.

---

## 1. What is this document?

[2–3 paragraphs: what the spec is, your job in one sentence, what success looks like.]

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the status/backtest file, not sign-off requests.

---

## 2. Core concepts (read this first)

| Term | Simple meaning |
|------|----------------|
| **[Term]** | [Plain English definition] |

---

## 3. [Part A from spec] — [Title]

**What the spec asks:** [Plain English summary]

### A1. [Subsection title]

[Spec explanation with terms defined inline]

**Deliverable:** [What spec requires]

#### A1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | [From status file] |
| **Results** | [Numbers] |
| **Production** | [Shadow vs live] |

#### A1 — Old vs new (if applicable)

| Aspect | Old / production | New / spec or shadow | Status |
|--------|------------------|----------------------|--------|
| | | | |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| [Question from spec or implied validation] | **Yes/No/Partial** | [Detailed answer with n, %, dates] | **Doubt:** [Question for Rohit Sir with evidence] |

---

## [Repeat for each spec part/subsection …]

---

## N. Deliverables checklist (spec vs status)

| ID | Deliverable | Shadow / experiment | Production |
|----|-------------|---------------------|------------|
| **A** | [One line] | [RUN / FAIL / …] | [Live or not] |

---

## N+1. Recommended build order (from spec)

[If spec includes sequencing]

---

## N+2. Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
| 1 | [Question] | [Numbers] |

---

## N+3. Key artifact index

| File | Purpose |
|------|---------|
| `[source spec]` | Requirements |
| `[status file]` | Experiment / implementation status |
| `[manifest.json]` | Numeric rollup |

---

## N+4. How this relates to work already done

[One short paragraph: shadow vs production, what's complete vs open.]

---

*Understanding doc generated from [source] + [status].*
