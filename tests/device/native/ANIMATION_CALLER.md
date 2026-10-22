# Original VM-to-native animation caller, version 2

This source exists only under `OVERTE_E2E_FEATURE_TESTS` with `--testScript`.
It changes no animation parameters, input semantics, Script source or completion
policy. C++ remains uncompiled; host tests exercise Python joins and synthetic
native boundaries only. No complete Emote adapter is enabled.

## Native origin and thread handoff

Immediately before the real V8 `QMetaMethod::invoke`, a native RAII scope obtains
the actual engine's `ScriptManager`. For actual methods `overrideAnimation` and
`restoreAnimation`, on that manager's own thread, it snapshots original assigned
membership and submitted UTF16 code, increments its own bounded call cursor and
captures native invocation time. No JavaScript argument, observation command or
requested manager ID supplies these facts. Other native-method invocations clear
this context for their scope; exit restores any enclosing context.

Version 2 additionally reads the nearest actual V8 JS frame's original Script ID
at native method dispatch. Only `overrideAnimation` and `restoreAnimation` collect
this bounded one-frame trace. The manager looks that ID up in its own original
[compilation inventory](SCRIPT_COMPILATIONS.md). A matching filename or forged
`sourceURL` cannot supply origin. Unknown dynamic/native origins or invalid/lost
compilation inventory produce explicit `compilation:null`; the real product call
still proceeds. No caller accepts a requested Script ID through the test protocol.

`MyAvatar` preserves a copy of this original metadata alongside its existing
queued ordinary call when it must marshal to its owner thread. A scoped context
at actual execution makes it available to `Rig`, which records it in the same
locked original override/active-to-inactive restore event as the existing call
history. Metadata owns no manager, QObject, timer or callback. The queued call
has the same context-bound receiver lifetime and same product arguments as
before. Non-E2E builds retain the original invocation implementation.

Actual native calls outside a Script method scope have `caller:null`. Missing
or invalid assignments/code also cannot acquire Script origin. Native internal
calls remain in the history; they are not silently assigned to the expected
Emote manager. Empty origin never suppresses the underlying product call.

## Exact record and checks

History version 2 requires a `caller` field per event. A non-null record has
exactly `callerVersion:2`, `method`, `sequence`, `invokedEpochMs`, `manager`, `code`,
and `compilation` (the exact original compiled row or null).
Method is the actual `overrideAnimation` or `restoreAnimation` and must match
the event kind. Sequence is a native per-manager cursor from 1 through 1e9;
failed/non-effectful calls may leave gaps. Invocation time precedes actual Rig
execution time and cannot predate submitted code or original assignment.

Manager has the original native membership fields `instance`, `assigned`, `url`,
`loadGeneration`, `assignedEpochMs`. Code has the existing original source fields
`submitted`, `encoding`, `codeUnits`, `sha256`, `submittedEpochMs`. Full closed
validation rejects invented result fields, malformed identities, numeric booleans,
wrong methods, missing assignment and incomplete code. Native origin is private;
raw source/manager identities must not appear in public feature facts.

Compilation has exactly the inventory's `scriptId`, `resourceName`, `encoding`,
`codeUnits`, `sha256`, `compiledEpochMs` and must predate invocation. Manager/code
continue identifying the owning top-level VM; compilation independently identifies
the actual calling code within that VM. Compilation is not inferred from the
manager filename, a requested feature or the selected animation URL.

Legacy version 1 callers remain readable for existing historical standalone
proofs. A profile with an independently observed compilation requires version 2
and exact original compilation equality. It cannot use version 1 or null origin.
A version 2 caller cannot qualify a legacy profile by ignoring its compilation.
Caller versions cannot switch inside one actual manager history.

Within a history and across reader replay, each actual manager's caller cursor
and invocation clock advance monotonically; original assignment/code cannot
change. Immutable overlap checks cover surviving rows. Reader cursor state
retains previously observed callers after bounded ring trimming, so a fresh Rig
event cannot reuse an earlier original call after that row disappears.
It additionally retains up to 4,096 original `(manager instance, Script ID)` rows;
their original name/hash/size/compilation time cannot change after ring trimming.
Different actual scripts within one manager and equal numeric IDs in different
managers remain distinct. Exhaustion fails; there is no eviction or rebinding.

The Emote join separately matches this original caller against independently
acquired configured-root/submitted-source/complete-membership facts. Actual
invocation must follow the action barrier. A queued call invoked before cancel
but executed later cannot prove cancel. Loaded clips and changed evaluated
joints remain mandatory; caller metadata alone never proves an effect.

## Scope and cleanup

There is no new operation, setter, file, timer or fixture lease. Existing native
observation retains the bounded 64-event/32-frame history, existing private
transport, 256 KiB response limit and original clocks. Version 1 histories remain
readable generically but cannot satisfy the version 2 Emote join. Version changes
inside one Rig/history birth fail. A future Pico source journal must retain and
replay these original cursors without transport. No Phone journal or platform
binding is imported by this source packet, and existing unresolved ownership
must not be overwritten or deleted.

Normal input causality, actual current avatar pixels, independent peer effects,
background/resume and complete quiet resource retirement remain separate
mandatory checks. No history reset or native animation restoration test setter
is introduced. Full cleanup must use ordinary controls and verify actual effects.
