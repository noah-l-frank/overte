# Mobile Script restart ownership handoff, version 1

`adapters/script_restart_handoff.py` transfers the existing staged-file and
normal file-manager intents after a separately performed normal app restart.
It is an internal ownership component, not an app controller, execution verdict,
full `feature.scripts.*` producer or device qualification. No app/UI input or
file staging/recreation occurs in either handoff method. Existing public
`scripts.*` operations retain their URL grammar and ownership rules.

Before the one normal stop/launch sequence, call `prepare(manager, execution)`
with the real `NormalScriptManager` file-bundle scope and its source-bound native
execution reader. The original four fixture bytes and current native directory
are read independently of the stage ACK. Require the actual bundle primary,
running engine, submitted original UTF-16 code digest/length, loaded relative
companion and current local Box/tick data. Freeze validated original file/manager
records, actual PID/native birth, engine identity and local effect UUID before
any lifecycle input. This snapshot records ownership, not a passed restart.

After ordinary app stop and launch, obtain new independently qualified raw
platform runtime/readers without constructing a live manager from old bindings.
Call `adopt(binding, presence, execution, files, ui, observe, picker)`. These are
the existing actual native process-presence, execution and storage readers,
ordinary Script UI, original service observation callback and file-picker reader.
The selected original target, source revision and installed artifact must match;
process identity must change, generation cannot regress. Explicit component-only
mode stays component-only and cannot acquire invented candidate fields.

Every iteration requires original old-PID `ESRCH` in the new process, a distinct
actual PID/native birth, exact unchanged original directory/token/bytes, no owned
engine (including stopped/stopping rows), no owned relative module, no owned
load callback, no named owned effect or old effect UUID, empty independent owned
service membership and closed original tablet/manager/picker. Aliased file paths
are normalized for membership checks. Missing/partial/foreign/stale/unsupported
native observations fail through the existing strict readers. Permission/unknown
kernel outcomes never count as death. A cached old service instance cannot be
used as the new empty Script manager. No script-stop or UI-close input is issued
to conceal retained state.

The actual Pico native tablet reports `open:false,ready:false,controls:[]` when
closed. `TokenScriptFilePicker.observe_absent()` accepts that original closed
observation only with the existing mandatory source version, identity and
transport freshness checks. A non-ready source without the explicit closed bit
and empty control inventory is unavailable. All ordinary picker capture/input
paths still require `ready:true`; no input gate or native source is weakened.

Continue independent observations for at least three seconds on both host
monotonic time and original native capture time, with multiple samples. The
whole adoption, original I/O, final guards and private record writes have a
twenty-second monotonic bound. Each native reader retains its own five-second
deadline, native-before/after clocks and original PID/nonce/sequence checks.
This is narrower than the full journey's independent actor/lifecycle evidence.

The private `handoffVersion:1` envelope has exactly `componentOnly`, `oldFiles`,
`oldManager`, `oldNative` and `next`. `oldNative` is exactly `pid`, `instance`,
`engineInstance`, `effectId`. `next` starts null; after verification it freezes
exactly `binding`, `nativeInstance`, `pid`, `files`, `manager`. The next manager
retains the immutable `fileOwner` but clears owned panels/dialogs/picker/source,
load attempt and old service cursor. The original file run/token/hash map is
unchanged. Private writes use the existing same-owner, private regular-file,
atomic replace/fsync and compare-against-previous implementation.

Persist `next` before changing either owner, then update the file record and
manager record in order. Discard the handoff only after both exact records and
final original guards/deadline pass. Interrupted writes retain the durable
handoff. Recovery accepts only the exact old or frozen next records (JSON boolean
and numeric types are distinct), pins the same new binding/PID/native birth and
repeats all new native observations and the full quiet window. Foreign owners,
changed originals, a third process or unavailable proof leave all retained
intent unresolved. Lifecycle input must never be replayed during recovery.
Ordinary live context equality is unchanged; only this explicit transaction can
rewrite both bindings.

The [one-send Script controller](RESTART_INPUTS.md) can retain the original
validated prepared snapshot in its separate private input journal. If the final
handoff return is lost after both records were transferred and this transaction
was discarded, `recover_transferred` reconstructs only the host transaction,
requiring the exact already transferred records and original same new binding,
PID and birth. `adopt` then repeats all native proof and the full quiet window;
no product input, fixture byte or native effect is recreated.

After success, construct the ordinary current file owner/manager and perform
the journey's separate `open`/picker cancel/reimport actions. Retained file
ownership still needs independent final release/absence. The complete adapter
must persist one-send lifecycle input intent, aggregate actual native lifecycle
events, produce independent actor facts, observe sticky missing-URL status and
coordinate full uncertain-load/effect/file cleanup. It must refuse general
cleanup while a handoff remains unresolved. These joins remain unimplemented.

Internal prepare/adopt factories are now connected on all three separate local
platform branches. Phone preserves installed APK/PID-start/session guards; Pico
preserves installed candidate/OpenXR/foreground guards and actual closed-unready
tablet semantics. iOS uses original HTTP/AFC plus separate native clocks, retains
explicit component-only binding and guards physical entrypoints before any
session/owner I/O; legacy unbound paths refuse. Every platform's general cleanup
refuses an unresolved handoff even if other host owners are absent. These
factories still do not perform lifecycle input or advertise a complete feature.

Host counterexamples use actual private journals and original temporary fixture
bytes with synthetic OS/native/UI boundaries. They cover old process permission
or presence, wrong candidate/target/source, missing/changed/relocated originals,
retained or delayed replay, owned failed-load history, foreign/old service state,
visible UI/picker, partial writes/recovery/third process, type substitution,
deadline/clock/guard loss and explicit component-only scope. No native C++ is
compiled and no device behavior is established.
