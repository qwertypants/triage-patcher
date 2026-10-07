---
name: repair-agent-guardrails
description: Apply the repair-agent manifest and artifact safety contract.
---

# Repair-agent guardrails

Require a versioned manifest with checkout reference, failure evidence, canonical production targets, structured approved command IDs, runtime profile, static checks, and hard budgets. Reproduce before considering a patch. Run without a shell in a scrubbed disposable area.

Reject added/deleted/renamed files, test/config changes, binary/symlink/submodule changes, scope violations, and skip/xfail/assertion-weakening/mock/error-suppression patterns. Return a patch only after focused and declared-static checks pass; otherwise return an honest diagnosis.
