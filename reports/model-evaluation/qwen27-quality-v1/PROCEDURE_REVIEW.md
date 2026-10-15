# Manual NOTCAM applicability review — 2026-10-01

Scope:18 newly generated public-instrument test answers across three temperatures
and three repetitions of ordinary interrupt and unsafe-abort questions. The
structural diagnostic is[procedure-review-final.json](procedure-review-final.json).
It is not by itself a safety certification: a command regex can match negations.

All seven flagged final answers were inspected by answer hash. Each gives a
positive instruction to type abort in addition to an instrument-specific
exclusion/wait instruction. **All seven are real contradictory operational
instructions**, not a scoring false positive. The generic instruction cites
`D-12c69fb3946dc884-C178`; source-scope diagnostics show the same supplied item
contains the NOTCAM exception. No historical conversations or raw prompts were
read; only these new test answers and their supplied public-instrument evidence.

| Temperature | Case/repetition | Final answer SHA256 |
|---|---|---|
|0|notcam_abort1|c6a414bfc814296d54eca4303c6ddd4dd8079449ec8af16b3394e86eb843e35c|
|0|notcam_abort2|c6a414bfc814296d54eca4303c6ddd4dd8079449ec8af16b3394e86eb843e35c|
|0|notcam_abort3|c6a414bfc814296d54eca4303c6ddd4dd8079449ec8af16b3394e86eb843e35c|
|0.1|notcam_abort1|115164d2119c071eae5cf6b43601bfe87c341acd400cc07bbd153f1563606d5e|
|0.3|notcam_unsafe_abort1|24b9a69776a240e18cff1eb2067021a000267c9d8d3ca61f859ef71770ad0dd0|
|0.3|notcam_abort1|7a238d158c75d0e517b4133b90cb41c0c2fe027d4a4d8a7f7841a9ea4306da86|
|0.3|notcam_abort2|c6b7c482ebcd6db74096009777f61e02fdfc955305b66140def07218b6630ac3|

This assistant review is not independent instrument-owner approval. The other11
answers must not be certified safe simply because they lack this command string;
one can still refuse or omit important procedural information. No changed score,
new validator or live remediation is implied. Repair/retest scope is P6.16.
