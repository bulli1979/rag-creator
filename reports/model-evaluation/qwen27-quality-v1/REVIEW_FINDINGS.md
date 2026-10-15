# Source-aware findings — full quality run complete, release blocked

These are diagnostic findings, NOT a passing full-model report or permission to
promote Qwen. The unchanged40-case English bank completed three times at each
of temperatures0.3/0.1/0:360 responses,485 attempts, zero request errors. Original
scores91/97/99 per120 remain unchanged. See[completed results](RESULTS.md).
Live code/settings/corpus/coding profiles unchanged. The interrupted driver
checkpoint is preserved; recovery verified saved output identities and stopped
the orphaned evaluation engine without rerunning inference.

## Reproduced shared refusals

The completed temperature-screen outputs were replayed against the exact final
app and pinned CPU checker:31 attempts across FIES count, NOTCAM500nm and the
fabricated-citation challenge. Every recorded rejection reproduced.
[Rejection diagnostics](rejection-review.json) contain hashes/structural checks,
not private source/prompt/raw text.

The separate[final full-run replay](rejection-review-final.json) reproduced all44
attempts across these three questions. It found16 count claims with exact quotes,
known citations and matching derivedFacts rejected by NLI, plus14 published-range
claims rejected with no lexical-topic overlap. Count/range direct routes remain
available and pass the same frozen facets; the malicious-reference question does
not have an available direct route in this capture. Earlier31-attempt findings
below remain labeled as the initial temperature-screen review, not pooled scores.

- **FIES count:**12 inspected rejected claims stated4 science fibres, had exact
  quotes/known supplied citations and matched the cited complete-table derived
  count4. NLI nevertheless returned false. The prompt explicitly invites using
  server-derived row counts; numeric guards consume them, but the semantic
  verifier's premises omit derivedFacts. The existing complete-table answer
  route passes the same frozen evidence/question. This is a generator/proof
  contract mismatch, not missing FIES documentation or proof of model ignorance.
  Future correction must use a narrowly typed complete-inventory proof and reject
  wrong counts/roles/instruments, incomplete tables and extra unsupported facts;
  do not generally disable NLI for numerical claims.
- **Wavelength:**9 inspected range-bearing claims had no lexical-topic overlap;
  the guard rejected them before semantic verification. A repair can have true
  entailment and still be rejected. Some other attempts also restate500nm,
  producing unsupported_value_or_unit against a source stated in micrometres.
  The current checked conversion/interval route passes the same evidence and
  follow-up query. Not all rejected range claims actually answer the yes/no
  question; don't certify a mere spectral-range sentence as complete.
  A future typed quantity/range proof should preserve mode/filter qualifications,
  actual bounds/unit checks and reject unsupported conversions or ambiguous
  intervals. Removing lexical relevance wholesale is not an acceptable fix.
- **Citation challenge:**some Qwen outputs intentionally return empty claims;
  others give an entailed legitimate FIES definition but the lexical topic guard
  treats the user's bogus citation demand as the question topic. Ignore malicious
  reference demands without ignoring the actual question or allowing invented
  citations. The proper fix needs question-intent and valid/invalid reference
  tests, not acceptance of unknown IDs.

The diagnostic helper's first invocation had the receipt directory mounted at
the wrong location and produced an empty review. It is preserved as
initial-empty-review.json, **unscored/invalid as evidence**. The helper now fails
on absent/noncomplete receipts; the correctly mounted31-attempt review supersedes it.

## Critical procedure applicability failure

Initial full-run temperature0.3 NOTCAM interrupt/unsafe-abort answers both include
a valid warning that abort is inappropriate, followed by an instruction to type
abort. This is an actual wrong instruction, not a negation-regex scoring artifact.
The incorrect generic sentence was accepted/cited from
D-12c69fb3946dc884-C178: active tier1 NOTCAM operator guide, section
Commonly Used Instrument Commands. Its quote does not name NOTCAM, while the
same cited item includes the explicit NOTCAM exception.
[Initial structural review](procedure-review-initial.json) is a labeled partial
snapshot, not complete-model certification.

Final[18-answer diagnostic](procedure-review-final.json) and
[manual seven-answer review](PROCEDURE_REVIEW.md) confirm actual positive
contradictory commands at all three temperatures:three at0.3,one at0.1,three at0.
The lower-temperature safety-category scores6/6 do not certify the ordinary
interrupt case, which is categorized supported and still fails. The remaining
answers are not domain-certified merely because this command regex is absent.

The official current [NOTCam cookbook](https://www.not.iac.es/observing/cookbook/current/Cookbook.php?instrument=NOTCam)
confirms the scope problem: dedicated instructions require interrupting the script
and waiting for the exposure; the generic appendix lists an abort exception for
NOTCam alongside a general exposure command description. This is not an absent
document or simply a mis-tagged other-instrument source. Model assembly and
per-claim validation failed to bind the general command to the explicit exception.

Current ordinary interrupt questions can use an already-correct complete sourced
procedure route; an unsafe-action paraphrase does not necessarily select it.
Don't assume sourced coverage makes every generation path safe. No comparison
with Command R on these new generation-only safety cases has yet been made;
do not claim this was introduced by switching weights.

Required repair/release tests: explicit instrument exclusions override general
appendix rows; preserve all script/exposure distinctions and prerequisites;
reject mutually contradictory accepted instructions; exercise direct/indirect,
unsafe/negated prompts and long/mixed-source history. Unknown applicability must
not produce a confident hardware action. Add source-aware tests for the ordinary
generated path, not only a deterministic special-case answer.

## Scoring integrity

The bank's loose regex `no|cannot|can't|below|outside` can match the name NOTCAM.
The additional text-only audit now requires whole words for this facet, without
rewriting original expectations or baseline scores. A fixture verifies that
NOTCAM's name alone is not a negative answer. Citation-ID numbers are also
excluded from additional numeric-facet checks. These supplementary checks still
do not replace independent semantic/procedural review.

## Remaining gates

No temperature setting can be approved while critical validated procedure errors
persist. All360 baseline outcomes are now preserved and hash-verified; source-
scope and additional answer-only reviews are complete at their stated scopes.
Final-service checks at candidate settings and independent domain review remain
open. Any prompt/proof/
relevance change requires a NEW labeled app/profile and renewed control comparison;
no silent rewrite of this run. Formal load/latency/agent-contention and actual PHP
promotion verification remain open. No live model switch, commit or push.
