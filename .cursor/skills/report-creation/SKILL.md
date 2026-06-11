---
name: report-creation
description: Generates structured analytical reports for MindWealth UI with human-like tone, data-backed observations, and clean formatting. Use when the user asks to create a report, write an analysis, generate a summary document, or produce any written analytical output.
disable-model-invocation: true
---

# Report Creation

## Core Rules (Non-Negotiable)

Apply ALL six rules to every report generated:

### Rule 1 — Human Tone with Naturalistic Imperfections

Write as if the report was authored by a knowledgeable human analyst, not an AI.

- Use natural, conversational-but-professional language
- Introduce occasional minor imperfections to simulate real human writing:
  - A subtle spelling error (e.g., "occured" instead of "occurred", "seperate" instead of "separate")
  - A mild grammatical slip (e.g., "data shows" instead of "data show", a slightly run-on sentence)
  - An informal connector phrase (e.g., "That said,", "Worth noting here is...", "On the flip side,")
- Do NOT overdo it — max 2-3 imperfections per report, spread out naturally
- Vary sentence length. Mix short punchy sentences with longer ones that carry more context
- Avoid corporate filler phrases like "it is worth noting that", "leverage synergies", "holistic approach"

### Rule 2 — Human Authorship (No Cursor / AI Fingerprints)

The report is written **by the user**, for their colleagues. It must read as their own analytical work.

- Write in **first person** when describing actions, decisions, or findings: "I ran…", "We fixed…", "I found…"
- **Never** mention Cursor, AI, assistants, agents, chatbots, or automated generation
- **Never** use passive distancing that implies a tool did the work: "the system was updated", "the pipeline was fixed" (unless referring to a literal software system, not who did it)
- **Do not** add meta lines like "Report prepared by…", "Generated with…", or "Analysis automated by…"
- **Do not** unnecessarily disclaim or assert human authorship; just write naturally as the author throughout
- Ownership applies to implementation, analysis, testing, and conclusions alike

**Bad:**
> Cursor implemented the Combo C cancel logic and generated this report.

**Good:**
> I implemented the Combo C cancel logic and documented the results below.

### Rule 3 — No Em Dashes

Em dashes (—) are strictly prohibited anywhere in the report.

- Replace em dashes with:
  - A comma: "The results, which were unexpected, suggest..."
  - A colon: "One key issue: the data was incomplete"
  - Parentheses: "The results (which were unexpected) suggest..."
  - A period and new sentence: "The results were unexpected. They suggest..."
- Before finalizing, do a final scan and confirm zero (—) characters exist in the output

### Rule 4 — Every Claim Must Be Backed by Data

Every observation, conclusion, finding, or recommendation must be supported by concrete data shown directly in the report.

- Preferred format: Markdown tables
- Use tables to present the supporting data immediately before or after the claim it supports
- If exact numbers are unavailable, state the limitation explicitly rather than making unsupported assertions
- Do NOT write vague statements like "performance improved significantly" without a table or metric

### Rule 5 — No Formal Corporate Section Names

The report should NOT read like a business document or academic paper. Avoid formal section headers that belong in boardroom decks or sign-off documents.

**Banned section names (do not use these):**
- Overview
- Executive Summary
- Sign-off
- Conclusion
- Methodology
- Introduction
- Abstract
- Scope
- Objectives
- Deliverables

**Instead, use descriptive, specific, lower-key titles** that say exactly what the section is about:

- Bad: "Overview" → Good: "What we tested and why"
- Bad: "Executive Summary" → Good: "The short version"
- Bad: "Conclusions" → Good: "What the numbers actually say"
- Bad: "Recommendations" → Good: "What I'd change based on this"

Write section headings the way a smart colleague would label a document they were sharing internally, not the way a consultant would title a slide deck.

### Rule 6 — Export a PDF Version After Markdown

After the Markdown report is written and passes the checklist, always export a PDF using the project export script:

```bash
python3.12 .cursor/skills/report-creation/scripts/export_pdf.py <report.md> [report.pdf]
```

- If the output path is omitted, the script saves the PDF in the same directory as the `.md` file with the same base name.
- The script handles styling (fonts, table colours, heading hierarchy) automatically.
- Dependencies (`weasyprint`, `markdown`) are already installed system-wide via `python3.12 --break-system-packages`.

**PDF naming convention:**
- Markdown: `signal_accuracy_report_2026-06-06.md`
- PDF: `signal_accuracy_report_2026-06-06.pdf`

**After export:**
- Confirm the script prints `[OK] PDF exported:` with a non-zero byte count
- Tell the user the full path to both the `.md` and `.pdf` files

---

## Report Structure

Use this template as the default layout:

```
# [Report Title]

[1-2 sentence opener — what this is about and why it matters, written conversationally, no heading needed]

## [Descriptive section title — what specifically is being looked at]
[Findings, data tables, interpretation]

| Metric | Value | Notes |
|--------|-------|-------|
| ...    | ...   | ...   |

## [Next section — another specific topic]
...

## What I'd change / what this means
[Takeaways and any suggested actions, grounded in the findings above]

## My doubts and questions
[Genuine open questions and doubts from the author's point of view. Things that feel uncertain,
things the data does not fully answer, things worth investigating further, or assumptions that
may not hold. Write these as actual questions, not hedged corporate disclaimers.
If there are no real doubts, still include a short honest list of what is not proven or what
the data cannot tell us.]
```

---

## Writing Checklist

Before finalising the report, verify:

- [ ] Tone sounds like a human wrote it (not AI-generated corporate prose)
- [ ] Written as the user's own work (first person where appropriate; zero Cursor/AI/agent references)
- [ ] 2-3 naturalistic imperfections are present and spread across the report
- [ ] Zero em dashes (—) anywhere in the output
- [ ] Every finding or conclusion has a supporting table or data reference
- [ ] No unsupported qualitative claims (e.g., "significantly better" with no numbers)
- [ ] Tables are clean and readable in Markdown
- [ ] No banned section names (Overview, Executive Summary, Sign-off, Conclusion, Methodology, Introduction, Abstract, Scope, Objectives, Deliverables)
- [ ] Section headings are descriptive and specific, not generic corporate titles
- [ ] "My doubts and questions" section exists at the end with genuine open questions
- [ ] PDF exported successfully and file is non-zero bytes
- [ ] Both `.md` and `.pdf` paths reported to the user

---

## Examples of What to Avoid

**Bad (em dash):**
> The portfolio returned 12% — well above the benchmark.

**Good (rewritten):**
> The portfolio returned 12%, which was well above the benchmark.

**Bad (unsupported claim):**
> Signal accuracy improved notably over the past quarter.

**Good (data-backed):**
> Signal accuracy improved over the past quarter, as shown below:
>
> | Quarter | Accuracy |
> |---------|----------|
> | Q1 2026 | 61%      |
> | Q2 2026 | 68%      |

**Bad (AI tone):**
> It is imperative to leverage these insights to holistically optimise the portfolio strategy.

**Good (human tone):**
> These findings suggest a few practical changes worth making to how positions are sized.

**Bad (Cursor / AI authorship):**
> The assistant updated the nightly pipeline and this report was auto-generated from the analysis.

**Good (user authorship):**
> I updated the nightly pipeline and summarised the results below.

**Bad (overly formal section heading):**
> ## Executive Summary

**Good (specific and plain):**
> ## The short version

**Bad (no doubts section, or a fake one):**
> ## Limitations
> This analysis may not account for all variables.

**Good (genuine doubts section):**
> ## My doubts and questions
> - The sample size for short signals (n=7 at >=85 pctile) feels too small to be confident. What would change if 2022 or 2020 data shifted those counts?
> - I am not sure the z-score vs percentile switch is as clear-cut as Test 9 implies. The percentile version picks up a lot of crisis days but does that mean it would have fired earlier or just more often?
> - Is it possible the CNN greed data gap (0 crossings above 80) is a data ingestion bug rather than a genuine absence of greed readings since 2015?
