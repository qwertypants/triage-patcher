---
name: change-risk-anti-patterns
description: Review narrowly scoped repairs before handoff.
---

# Change-risk anti-patterns

Trace requested behavior to touched files. Keep patches minimal, report validation evidence and unrun checks. Reject changes to tests, configuration, locks, generated assets, permissions, and unrelated paths. Focused-test success is never whole-repository proof.
