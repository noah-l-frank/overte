# Once-only original Chat cache lifetime

`ChatCacheLifetime` v1 owns the original native receive-cache mutations for a
whole Chat parent. Construction requires an already admitted original
`OwnedChatCapture`, its unchanged run/binding/native instance/self hash, the
same exact parent `ScriptSourceLock` object and a separate fixed private ledger.
Construction performs no native input. It durably binds capture-owner v2 to the
exact original private lifetime ledger before that lifetime can mutate native
state. Legacy capture-owner v1 remains readable; an admitted original owner
can acquire this binding only after the existing lifetime history validates.
An active owner cannot acquire a new empty lifetime. A different lifetime
filename cannot replace the binding. The parent first establishes the independent
absent-cache baseline, then admits this source; activation belongs to its first
normal Open step. Existing v1/v2 source packets cannot supply this ownership.

Before Observe or Retire dispatch, the owner persists the actual original
request/nonce, original native request epoch and exact original passive
precondition-frame index. That actual absent/active cache frame must remain
fresh both before and after the durable write, including with a frozen host
clock. The native v3 first-mutation
IDs establish the actual effect. A lost answer is resolved only by NEW passive
Inspect queries that report the exact same original open/retirement ID and
native lifetime. A foreign first nonce, absent unapplied mutation, stale source,
PID/birth change or uncertain durable write never permits another Observe or
Retire. The journal remains unresolved. Changing back to a previously accepted
state cannot authorize a repeat of an issued mutation.

Every native result and its original request remain in the bounded compressed
ledger, with sequence/history continuity and original request epochs. Cold
reconstruction validates those historical originals without querying or
retiming them; the next operation obtains new native observations. Full
operation acquisition, durable intent, final copy and guards share the original
1.5 s host/native freshness bound, including frozen-host/native-jump cases.
At most 24 native packets are retained; no truncation or old-state adoption
provides more capacity. The same reader cannot be wrapped by a second owner.

Generic `OwnedChatCapture.observe/retire` refuses a v2 capture owner before any
query or mutation. It cannot issue a second retirement or discard the original
proof after a whole-journey lifetime has taken ownership.

Retirement requires two distinct NEW original passive inspections after the
single Retire attempt, with the original matching fence and actual absent,
empty receive cache. It retains the capture ownership, lifetime ledger and
native historical ID fence. Only the validated retired lifetime can record
capture-owner retirement: actual original open/retire IDs and both distinct
native inspection IDs, sequences and epochs are retained, and `active` becomes
false. A lost owner-write receipt permits only passive reconciliation; later
inspections preserve the first recorded proof. It does not claim Qt-object/global-memory release,
peer input-file/descriptor release, original process destruction, final physical
profile restoration, post-Erase independent publication or complete Chat.
Those remain whole-journey responsibilities. Separate final cache-absence
roles must independently read their own actual sources.

The Pico factory uses the existing candidate/process guards and exact supplied
Chat parent lock. Base cleanup refuses to rerun legacy capture retirement when
this ledger exists. It preserves the original ledger/capture owner, still
reaches ordinary process teardown, and reports unresolved cleanup rather than
hiding it. Force-stop acknowledgement never establishes actual old-PID absence
or retires the saved ownership.

Focused host checks (explicit synthetic native/transport/clock seams):

```sh
cd tests/device
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest self_tests.test_chat_cache_lifetime -v
```

The actual Pico factory check additionally uses the original verifier, live
binding logic and private stores with synthetic APK/native/transport seams.
The preceding native v3 Qt5 harness compiles the actual full observation header
and original MessagesClient source body, and validates its exact serialized
initial/open/retired packets through the Python reader. No product application,
network peer, SDK signing result or physical device was run or qualified here.
