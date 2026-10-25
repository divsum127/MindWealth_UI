# WhatsApp to Ahil (draft, not sent) — paste into the MindWealth group and tag him

@Ahil the conviction engine on dev is recalculated on Rohit sir's 24 Sep decisions, so it's ready for your live test now. Please test against dev API 8507 / UI 8514, not prod, because prod still has the old numbers. The pack is in reports/conviction_engine_closeout_2026-09-17/AHIL_LIVE_TEST_PACK.md and the full before/after list is in reports/conviction_recalc_2026-10-25/. Two things I need from you: whether the engine in this form adds value to the portfolio results, and your call on the qualification questions (252 vs 365, R_REF and the clips, E[R] floors, Tier A cut, hard vs flag gates) so the prompt can be merged once. The new payload field definitions are parked in MindWealth/instruction_docs_2/signals_master_spec/pending_prompt_merge.md for that merge

### Note for Divyanshu (not part of the message)

- Rohit asked on 1 Sep to "TAG HIM ON OUR WHATS APP GROUP … AND ALSO MENTION ON THE GOOGLE DOC"; the Google Doc mention is still yours to add.
- Check that `AHIL_LIVE_TEST_PACK.md` still matches dev before sending; it was written on 17 Sep, before today's recalc.
