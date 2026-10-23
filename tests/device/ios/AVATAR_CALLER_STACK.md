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
result is insufficient for that claim.

The optional `avatarCallers` component in Entity Caller1 now records its own
`avatarEntityCallersVersion: 1`, actual resolver completeness, original neutral
V8 stack and indexed module matches. The existing admitted manager/thread scope
captures these originals before the product entity call. Entity observation
records them with the genuine returned UUID or completed local deletion; generic
Create still selects its unchanged Caller1 subset. Legacy Entity originals
without this component remain byte-for-byte readable and cannot pass the new
explicit strong entity qualification. An incomplete present component fails
closed. Its first V8 source observation may occur after the scope's invocation
timestamp and must precede the original entity-return event; it is not a compile
timestamp.

`avatar-callsite-pins.v1.json` independently pins six repository sources and
closed whole-stack profiles, including each frame's source, UTF-16 line/column
and reviewed outgoing call/property token. `avatar_exact_callers.qualify` joins
actual submitted known modules first, then checks every original frame against
one exact profile. It rejects additional unknown or nested frames, wrong
positions, wrong compiled bytes and evaluation/constructor frames. The genuine
installed root from the actual module rows binds the appUi frame's URL hash;
appUi is not fabricated as a submitted-code ledger row. Source pins are never
derived from observed frames. Explicit wrappers qualify owned new timer births,
actual consumed XHR Open/read pairs and the new Entity component; public legacy
component APIs retain their weaker historical interpretation.

The relationship parser likewise branches on the actual HTTP generation: old
1 selects its original legacy chain; current 2 selects URL rows from the actual
referenced indexed stack. It does not reconstruct or insert a legacy chain.
The required People protocol or QML request-service module, submitted bytes,
provider receipt and actual response consumption remain independent checks.

Host Node checks execute the complete unchanged request/request-service modules
and AvatarApp. They independently observe the Open/read sites, actual wearable
add/delete calls, callback-created timers and bookmark callback location at the
modeled native boundary. All profile tokens/compiled-byte identities are also
checked against separate repository bytes. Other approved profiles are pinned
source paths; no native execution or exhaustive real-engine path coverage is
claimed. Whole integration must invoke the strong wrappers for its owned
originals and remains pending.

Host checks cover actual loopback POST, the existing Fixture validator, factory
and fixed AFC transport, original native clocks, literal legacy bytes, table
capacity, reference/prefix/caller counterexamples and source-level entrypoint
wiring. Qt/V8 boundaries are explicitly modeled. No native compilation or
device execution has been performed. Whole Feature 3 timing, full native path
coverage, paired final cleanup and final dispatch remain unqualified; this component
does not advertise a feature capability.
