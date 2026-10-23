# Original Avatar V8 callers

`ScriptManager::featureAvatarV8Stack()` is a passive C++ accessor to the existing
engine-local `IOSV8ScriptStack` version 1. It requires the E2E/iOS build gates,
the original test-script/results-location gates, the actual manager thread and
that manager's actual V8 engine thread. It delegates to the current-isolate
snapshot and adds no JavaScript API, observation route or compile/evaluate hook.

The unchanged native stack component contains indexed actual V8 frames, script
IDs, line/column, source-URL hashes and hashes/UTF-16 units of the actual compiled
source returned by V8. `firstObservedEpochMs` means first source observation in
that engine; it does not claim compilation time or closure identity.

The Avatar script ledger, its outer native source, Avatar timer-work component
and social HTTP source now write 2 and read 1 and 2. Actual timer births and
XHR open/responseText reads capture that manager's actual stack on the original
engine thread. Frame URL hashes and compiled bytes resolve against that same
manager's actual submitted code. Missing/incomplete stacks cannot produce a
complete relevant source. No product evaluator, callback or timer is replaced.
Actual submitted module relevance is established before marking a timer source
incomplete. Global XHR observation first requires the actual engine/thread,
assigned default-script manager, submitted manager code and observed relevant
modules. A foreign/native context without those originals cannot poison the
global Avatar HTTP ledger. An incomplete stack in that same relevant manager
remains unqualified because hidden relevant frames cannot be excluded.

Each version-2 component retains an append-only `callerStacks` table containing
nonce IDs, the complete original stack and indexed actual module URL matches.
Exact repeated stack/module values share one entry. Created timers and XHR
events retain `callerStackId`; references, table prefixes, engine births,
ScriptIds and compiled first-observation identities are immutable. Unknown V8
frames remain in the original stack. No expected caller chain or restamped
clock enters the producer. A 120-timer/600-event typed host fixture occupies
149,493 canonical source-body bytes under the unchanged 250,000-byte native
body and 262,144-byte transport limits. The earlier repeated-stack draft already
exceeded the limit at 120 timers and 240 events; it was not committed.

The unchanged literal version-1 producers remain independently readable through
the public component readers and actual HTTP/AFC path. They never gain stack
tables or stronger provenance. Snapshot retains its separate native instance,
original QStringList overload and schema 1 without a table. The old
`callerChain` helpers remain available for legacy consumers. Their parent
wrapper traversal can repeat the current top frame; it is not an exact parent
stack. Code-only `avatarCode` projections read their actual generation 1 or 2
directly, without fabricating an empty timer-event ledger.

`avatar_call_stack.bound` and `require_actual=True` establish actual module
origin from original V8 frames, independently reviewed module hashes/UTF-16
units, manager birth and actual evaluation logs. This is deliberately distinct
from exact whole-stack provenance: it does not pin every line/column, reject all
unknown frames or establish a complete approved call-path shape. Whole Feature
3 must additionally qualify independent exact callsite profiles. An origin-only
result is insufficient for that claim. Entity Caller1 also remains legacy;
actual indexed entity-frame evidence requires its separately reviewed component.

Host checks cover actual loopback POST, the existing Fixture validator, factory
and fixed AFC transport, original native clocks, literal legacy bytes, table
capacity, reference/prefix/caller counterexamples and source-level entrypoint
wiring. Qt/V8 boundaries are explicitly modeled. No native compilation or
device execution has been performed. Whole Feature 3 timing, exact call paths,
paired final cleanup and final dispatch remain unqualified; this component
does not advertise a feature capability.
