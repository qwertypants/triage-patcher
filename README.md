# Safe CI Repair Agent Prototype

`repair-agent` is a fail-closed CI helper for one supplied failing-test context.
It writes either a validated, minimal patch or a plain-language diagnosis; it
never changes the checkout it was given.

## Quick start

```sh
python3 -m unittest discover -s tests -v
python3 -m repair_agent run --request examples/request.json --source examples/fixture --output /tmp/repair-output
```

The request is a version-1 JSON manifest. CI must supply an immutable checkout
reference, focused failure evidence, canonical production targets, explicit
commands, a runtime profile, static checks, and hard budgets. Candidate patches
are a stand-in for the platform-managed sidecar broker in this prototype; the
runner accepts no shell snippets or free-form command arguments.

For containers, mount a CI-sanitized checkout, a request file, and an output
directory as `CHECKOUT`, `REQUEST`, and `OUTPUT`. The image has no network,
runs without privileges, uses a read-only root filesystem, and gives commands
only an ephemeral work copy.

Exit codes: `0` patch produced; `10` diagnosis produced; `20` rejected request;
`30` cancelled.

Only the declared focused command and static checks establish validation. Normal
PR CI remains responsible for wider regression confidence after a team applies
the returned patch.
