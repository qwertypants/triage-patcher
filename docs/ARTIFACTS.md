# CI repair artifacts

`fix.patch` appears only after reproduction and focused plus declared-static validation. `result.json` records status, observations, hypotheses, bounded command output, and scope. `diagnosis.md` is emitted for rejected requests, non-reproduction, timeout, cancellation, policy rejection, or validation failure, separating observations from hypotheses and naming the smallest next check.

Teams apply patches through normal review. The runner does not write to the original checkout, install packages, call a VCS host, or claim full-suite confidence.
