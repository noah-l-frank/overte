# Pico World current-document original source

This is a separate, read-only native source, `pico-world-current-document:1`.
It does not change Common16, its background replacement predicate, the normal
foreground/loading bodies, or the old World observe2/ray3/text4 contracts.
There is no new ray, IME, reload, synthetic finish, DOM clear, product setter,
public capability, or complete World journey in this packet.

## Closed operation and scope

The existing private probe accepts a separate seven-field command:
`schemaVersion:1`, 32-lowercase-hex `commandId`, `action:pico-world-web`,
32-hex `runId`, original run `fixtureUrl`,
`operation:observe-current-document`, and original 32-hex `ownerToken`.
The existing exact fixture URL grammar is reused. Tablet/reference operations
cannot enter this channel. The original completed World reservation supplies
the original owner/root and its complete finish-document inventory.

`Test.featurePicoWorldCurrentDocument` uses its own native provider property
and bounded `AudioSettingsQueue`. It returns the unmodified original map;
the probe writes it to private `feature-world-current-document.json`.
The result is never synthesized from a command or an ACK. Test-build and
actual process `--testScript`/private-results/lifecycle gates apply. Non-Pico
returns no source; the Java native gate is false outside the Pico test build.

The exact result header is:

- `picoWorldCurrentDocumentVersion:1`, original `commandId`, `runId`, `ownerToken`;
- native source `instance`, original monotonically increasing `sequence`, actual `processId`;
- immutable `requestedEpochMs`, `requestedMonotonicMs`;
- original `capturedEpochMs`, `capturedMonotonicMs`;
- `status`, `source`.

Status is exactly `pending`, `ready`, or `unavailable`. For `pending` and
`unavailable`, `source` is exactly `{}`. For `ready`, its exact fields are
`authorityBefore`, `originalFinish`, `domRaw`, `dom`, `authorityAfter`, and
`documents`. There is no missing-source success. Expired queries and their
original raw callbacks remain bounded native records; they cannot be reused
with a fresh clock. The TSI expiry gate may consequently return an empty map,
which the reader refuses.

## Independent current authority and exact old finish

Each authority has exactly `native` and `java`. The native authority contains
`handle`, `itemInstance`, `creation`, `grant`, `page`, `url`, `sourceUrl`,
`sourceIdentity`, `created`, `authorized`, `sessionActive`, `suspended`,
`loading`, `capturedEpochMs`, `capturedMonotonicMs`. Java has `handle`,
`creation`, `grant`, `page`, `url`, `sourceUrl`, `ownerCurrent`, `active`,
`foreground`, `windowFocused`, `destroyed`, `closing`, `loading`,
`capturedEpochMs`, `capturedElapsedMs`.

Before and after are two actual captures. Native captures run on the actual
Qt application/item thread. Java captures run on the actual main looper,
using the current host/activity, registered instance, document state and
native editor authority. Only their semantic authority fields must agree;
the original independent clocks are retained separately and ordered.

The original finish is the unique exact six-field inventory row matching the
actual item's `_featureWebFinishedGrant`, `_featureWebFinishedPage`,
`_featureWebFinishedDocument`, actual handle and original creation. Its
`finishedEpochMs` is the original event time. The complete bounded document
inventory is exported, including earlier documents; a latest/arbitrary row
cannot substitute for the exact matching finish. The finish may legitimately
have an older grant than current authority. The observer never assigns to
those finished fields and never uses a grant increment as a new load count.

`domRaw` is the complete original JNI transaction JSON, with exact fields
`before`, `domRaw`, `after`. Its inner `domRaw` preserves the original quoted
WebView `evaluateJavascript` result. The existing readonly
`__overteFeatureWebDOM.read(nonce)` is the sole DOM query. The strict Python
reader rejects duplicate/nonfinite JSON and requires byte-decoded DOM and
Java bookends to equal the exported, strictly typed DTOs. Existing full World
DOM grammar validates the original document, attempt and echo histories.
This source cannot establish independent HTTP delivery or stereo by itself.

## Nonce, clocks and weak lifetime

The native nonce's clock starts before the bounded V8-to-Qt queued dispatch.
The same command always refers to this original clock. A same-nonce poll
never starts another Java read, resets a timer, or retimes a completed packet.
Conflicting commands cannot reuse an anchor. There are at most 4096 anchors,
32 scopes, 128 queries per scope, 256 original finish rows and four raw
callbacks per query. JNI transaction bytes are bounded to 16 KiB, quoted DOM
bytes to 8 KiB, and the output packet to 64 KiB. Capacity refuses new work;
there is no silent eviction or new observation replacing an unresolved one.

Both the Java asynchronous instance/host captures and the native QObject item
are weak. The DOM callback re-resolves both Java weak references and the
current VIEWS/host association before use. A separate retained dispatch receiver keeps a safe
queued destination alive, without keeping the product item alive. The
receiver is released through actual `deleteLater`; outstanding callbacks
retain their bounded source records. Callback processing checks the actual
thread before dereferencing original item state. Wrong grant, owner, page,
creation, source, expired clock, destroyed item or changed document history
cannot become ready. Unknown callback nonces do not allocate a query.

Both native wall/elapsed clocks and host elapsed age are at most 1500 ms;
future skew remains at most 250 ms. The actual final monotonic reading uses
a fresh `QElapsedTimer` clock read, not the rounded sum of start and elapsed.
Java's own elapsed bound begins before its actual main-queue dispatch.

`PicoWorldCurrentDocument.read` uses the exact parent's existing
`ScriptSourceLock` instance and refuses entry already inside an outer owner.
It sends one readonly nonce, reads the original source file, and copies the
result before real outer lock release. It then rechecks the actual guard,
native clock, host clock and complete original DTO. It commits reader state
only after this final fence. It never acquires a new DOM/source frame to
make old data fresh. The caller must keep this same source lock domain and
retain `original()` bytes; this packet does not yet wire the source into a
World action/coordinator or claim an old owner can be adopted.

## Verification and limits

Three additive selectors cover the original Qt5/JNI source, production Java
method bodies, and strict Python/outer-exit grammar. The unchanged earlier
`world-web-retained-resume-source` remains its own regression. The native
counter runs the original old retained-page path first: foreground rotates
the grant, retains creation/page/finish, old observe2 is pending, and the
old getter sends no extra Java DOM/geometry request. The new channel then
reads the same retained DOM with current authority and separately accepts an
actually delivered new finished callback. Same-nonce polls, stale old grant,
foreign nonce, weak death, delayed clocks and actual receiver deletion are
checked. Native tests expose the Java WebView/DOM boundary as an explicit
recorder; no real page/network/render is inferred from it.

The Java body test compiles the four complete original production methods
without edits, the original `WebDocumentState`, and existing Android's actual
`JSONObject`. Android looper/host/view/JNI are explicit host seams. It checks
two actual bookend calls, unchanged grant/page, original readonly script,
actual owner/current-grant/focus refusal, and delayed main-queue/callback
refusal. A separate existing API test compiles the complete production Java
against installed Android/WebKit APIs. None is physical-device evidence.

The Python counters retain original reply types/bytes, exact finish epoch,
full ledger and actual shared-lock exit. Frozen-host/native+2000,
real-host+2000, native−2000 and changed final guard must refuse publication
without a second input or new frame. Mutable returned copies cannot change
the saved original.

The unchanged Common16 step15 replacement requirement remains unavailable
for the proven retained-page lifecycle. This source only supplies an honest
future retained/current-authority observation. Versioned common dispatch,
normal post-resume ray/IME authority, independent Actor/HTTP/stereo association,
19-step journey, original resource/VM retirement and host cleanup remain
separate work. No old finished event, source count or legacy callback is
relabelled to cross those boundaries.

## Local evidence, 2026-10-24

The final functional packet's eleven cases passed together in **15.790 s**:
one original Native/JNI case (including Pico/non-Pico whole TSI getter builds),
one original Java-body case and nine strict reader cases. The unchanged old
retained-page selector also passed separately in **7.148 s**. The complete
production Java API compilation passed in **1.026 s** (existing annotation
warnings); it preceded the final callback weak-reference refinement, whose
complete original methods were subsequently compiled/executed in the final
Java-body case. This is not a complete Android application build.

The final eleven-case source freeze is
`797db7b628af01f442396edddaa8f9c7ccf5a3b474582dc66d2f0e6c9f5b51c3`,
covering **13,540** tracked/new files, complete bytes and original physical
signatures. Source verification after terminal completion matched exactly.
Private original stages and preceding failures are retained under
`/home/user/.local/state/overte-pico-world-current-document-agent-20261024.x79cm7q7`.
No pre-existing journal/source generation was replaced.

The initial compiler failure found a mixed `auto` declaration. The next
original Native run completed its assertions but strict Python validation
caught a real one-millisecond final monotonic inversion from adding two
rounded durations. The final native clock now reads the real clock directly.
Subsequent pure harness failures were a missing opt-in Qt environment, a
reader method/attribute collision, and an invalid same-sequence pending/ready
fixture. Those failures and exact source freezes remain preserved; neither
runtime grammar nor age limits were relaxed. Final review also added weak
Java callback captures and delayed-final-parser/outer-exit counters before
publication.

Coverage's ten checks, explicit contract registry, probe Node syntax and four
selected repository suites passed (repository selection **2.70 s**). Exactly
three new catalog selectors are added to this isolated 249-case base; Root's
newer unrelated additions must remain additive during integration.
Only this native packet should be selected: the parent `ad03baed2bd087eb876313b0b44ac404b0552949`
and its prior World source/Actor/stereo chain are dependencies already
reviewed separately, not new selections from this packet.
