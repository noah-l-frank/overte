# Original Pico Create Script callback resources v1

Feature 4/14 remains partial. This read-only source separately measures the real
Window-to-Script callback boundary needed by Import/Save. It does not infer
callback retirement from a missing picker, restore settings or advertise a
complete Create capability. Native modal/listener delivery and QML context lifetime
are separately available from the [original dialog source](CREATE_DIALOG_SOURCE.md).
The complete owner and domain/render/actor joins remain necessary.

The dedicated `OVERTE_E2E_FEATURE_TESTS` build and `--testScript` gate records
only actual `WindowScriptingInterface` `browseChanged(QString)` and
`saveFileChanged(QString)` signal proxies. Ordinary builds have no added fields,
connections or dispatcher instrumentation. Each original proxy and actual
connection receives a random immutable native identity, actual creation and
disconnection times, target class and the original callback's V8 `ScriptId()`.
The actual V8 compile-boundary records independently retain that Script's
resource name and original UTF-16 code digest. Names or expected code supplied
by an adapter cannot populate this source. No callback arguments or selected
private paths are recorded.

Connection publication precedes real connection-list admission; disconnection
publication follows real removal. A separately held native dispatch lease starts
before the original signal dispatcher copies its callback list and ends on all
returns. A callback that disconnects itself remains an active resource until its
original dispatcher returns. Nested dispatches retain separate counts. A lost
manager, inconsistent retirement, clock reversal or exhausted history remains
unavailable. There is no count eviction or generated completion.

`ScriptEngines::featureCreateCallbackObservation` reads all known actual managers,
including pending and stopped managers, under the existing membership lock. It
reads each manager's locked sources without entering V8 or waiting on foreign
Script threads, then fences callback and manager membership again. There are at
most 128 managers, 128 original proxies and 512 connections per manager; retired
records remain original. These finite limits fail closed. The accounting can
also support later typed Tablet signal profiles at this same shared dispatcher;
the v1 admission currently includes only the two Window signals.

The separate Pico getter/probe command `feature-create-callbacks-observe` accepts
only schema, action and a fresh request nonce. The getter requires the existing
private test-results/lifecycle launch boundary, records actual native process
and acquisition clocks, refuses a foreign thread with no running event loop,
and reads only an already registered ScriptEngines dependency. A passive read
cannot instantiate a missing engine manager. It retains up to 512 original nonce results. Replaying
a nonce returns its original packet and times. Exhaustion returns unavailable;
it never evicts or retimes a prior acquisition. The probe only saves the original
native result to private `feature-create-callbacks.json`.

The private bound adapter factory `_create_callback_observer` retains candidate,
PID/start and the original private Pico transport checks. Its strict reader
preserves original raw bytes and SHA-256, requires fresh original native packets,
joins callback Script IDs to actual compilations and rejects lost managers,
rewritten history, source replacement or callback resurrection. `active` returns
measured connection and dispatch resources; it does not claim complete picker
cleanup. A full owner must persist the acquired identities and join them to
native modal/listener and QML-root/context resources before retiring ownership.

Six selected Python/Node counterexamples cover original bytes, live disconnected
dispatches, compiled provenance, history loss, process replacement, stale reads
and closed probe commands. They are imported into Pico's existing `normal-create`
case. The separate `create-callback-native` QtCore case compiles the actual native
collector and extracts the original ScriptEngines/TSI getter implementations.
Its native original packets pass through the real Python reader validators.
It tests nested/self-disconnected dispatch accounting, all-known membership,
thread-safe reads, disabled gates, stopped target threads, missing dependencies,
bounded histories and immutable replay.
The actual V8 signal proxy and complete application have not been compiled by
this isolated harness, and no device behavior is qualified.
