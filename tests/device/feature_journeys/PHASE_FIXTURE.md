# Original fixture input phases, version 1

`Journal` now retains the original creation and activation times for its existing
closed stimuli. This is input metadata for associating independently observed
native events with the current phase. It contains no product/peer state, effect
verdicts, resource delivery, process lifetime or successful cleanup assertion.
It neither introduces another runner nor changes common journey contract v17.

## Read contract

An authenticated GET of `/feature-fixture/v1/runs/<32hex-run>/phase` requires
exactly one `X-Overte-Phase-Read: <32hex-nonce>` header. Existing reader, actor and
separate read-only adapter credentials can read it. The adapter credential still
cannot activate/delete runs, publish samples or read peer facts. No POST/DELETE
phase operation is available. Missing/duplicate/malformed nonce and unknown run
are errors; unknown data is never a successful empty observation.

The exact response fields are:

| Field | Original meaning |
| --- | --- |
| `fixturePhaseVersion` | Integer 1 |
| `instance` | Original 32hex journal birth, pinned across reads |
| `sequence` | Strictly increasing original journal read sequence |
| `requestId` | Exact caller read nonce |
| `runId`, `area` | Exact existing registered run and one of the fourteen areas |
| `capturedEpochMs` | Actual source clock when this response is acquired |
| `active` | Whether that original input journal is still registered |
| `createdEpochMs` | Original registration time, never retimed |
| `retiredEpochMs` | Original close time, or null while registered |
| `activations` | Complete ordered immutable original closed stimulus history |

Each activation has exactly `sequence`, `ticket`, `activatedEpochMs` and
`stimulus`. Its sequence is one-based, ticket is unique, original epoch is
nondecreasing and stimulus contains exactly the existing `verb` and `inputs`.
The same closed v17 input grammar applies for all fourteen areas; baseline and
cleanup accept only empty inputs. Mutable caller inputs and response copies
cannot change retained originals. Existing 256-ticket/32-active-run bounds remain.
Known registered or retired run identities cannot be reused.

Close keeps at most 64 original input tombstones, without peer entries, to allow
an attached observer to distinguish retirement from transport loss. Repeated
close preserves the original time/history. An evicted or unknown run stays
unavailable. An inactive phase journal proves no target cleanup: native scene,
resources, UI, requests, peer and owned file absence still require their actual
feature-specific observations.

## Reader and ownership

`PhaseFixtureReader(client,run,area,epoch_ms,monotonic)` uses the existing
credential-bearing Client, including the adapter-only subtype. `status(previous)`
performs one fresh nonce-bound GET, validates the entire closed history and pins
original provider birth, run/area, cursor, timestamps and immutable prefix.
Reconstruction must pass its previously persisted complete original packet;
callers must durably retain every accepted floor before another acquisition.
There is no automatic history reset or upgrade from missing originals.

`read(previous)` returns the current actual `ticket`, `verb`, `inputs`, original
activation `afterEpochMs` and complete `status`. It raises `PhasePending` before
any activation and `PhaseRetired(original_status)` after close. Retirement does
not query a removed active endpoint. A feature observer brackets its own native
acquisition with separate original phase reads and refuses a ticket change;
these metadata never substitute for native measurements. Each observer owns its
own reads, process/native history and pre-input causality evidence.

The existing HTTP timeout remains five seconds and bounded response one MiB.
Successful source freshness is stricter: at most 1.5 seconds, at most 250 ms into
the future, and a separate monotonic elapsed-age floor. Regressing clocks/cursors,
reused read responses, provider replacement, truncated/changed history, resumed
retired runs, malformed types and extra expected-result fields fail. The source
provides no product input, fixture control, retry or capability advertisement.

Fifteen device-free cases cover all fourteen stimulus inventories, immutable
inputs/prefixes, original times, two independent roles, retirement, unknown/evicted
runs, old/foreign/changed/malformed originals, frozen/slow clocks and actual
owned loopback authorization. Existing complete common-journey counterexamples
also run through regular Journal registration. These verify test/source logic
only; no native compilation, device, build or external service is exercised.

The closing no-build common selection passes 1,177 tests with zero failures,
errors, skips or compiler attempts. Exactly three compiler-based native voice
checks remain explicitly outside this selection. The 66-test Android regression
also passes, including complete Graphics, Script and Authentication journeys;
documentation and contract-registry validation pass.
