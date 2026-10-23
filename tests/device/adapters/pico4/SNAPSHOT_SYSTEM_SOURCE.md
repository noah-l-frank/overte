# Original Pico Snapshot OS handoff source

`PicoSnapshotSystemSource` is a private read-only source, not normal chooser
input, recipient consumption or complete Snapshot acceptance. Its factory is
`_snapshot_system_source(target, binding, authority, source_lock=...)`. The
existing `snapshot-save-fences` selection owns its focused source and actual
Pico factory checks; no new capability or selector is added.

The exact parent source-lock instance must already be held. Construction pins
that actual acquisition object, not only its path/inode. `prepare()` requires
the original application foreground and reads the actual package-manager
`android.intent.action.CHOOSER` resolution and assigned UID. It does not launch
anything. `capture()` can then read either the original application or that
exact chooser Activity/UID while the parent continues to hold the same
acquisition. Unlock/relock fails even for the same lock object/inode. There is
no automatic foreground repair, acquisition adoption, sleep/retry, cold input
resend or ownership retirement.

Every query is bounded by the existing Graphics OS source, which rechecks the
actual installed candidate bytes, original kernel PID/start, target and Pico
session without querying foreground-only Qt. The parent's `authority()` must
return the literal `True` before and after that source. This callable is the
future durable Share/actor graph/phase authority; a boolean callback in host
source tests is an explicit ownership seam, never proof of a complete Share
journey. The exact Activity, resolver and UID are checked again after the last
candidate/session guard, followed by native and host clock checks covering the
whole acquisition. Ambiguous resumed activities and same-package replacement
Activities fail. Full original resolver/UID/activity bytes remain in returned
rows, including the final Activity read; version one is recorded as
`pico-snapshot-os-source` in the private version registry.

A future Share parent must separately validate the complete original native
Share packet and join its grant component/UID to this OS resolution. This source
accepts no caller-supplied grant or delivery ACK. Neither the resolver nor a
chosen component callback establishes recipient stream consumption.
The source has no native command sender, Qt observer, touch/controller method,
explicit-target Intent launch, endpoint setter or worker termination input.
The ordinary `NativeNavigationIO` foreground guard is unchanged: an actual
factory host case observes the OS chooser and proves ordinary Qt input still
fails there before returning to the original app window.

## Fixed Phone reuse and precise remaining boundary

Read-only review used frozen Phone
`b62e012f1328e30b80604bb447a60db0d8a748df`, with `97219dbebc90ee95db943e5bf82a577b75a04e8e`
verified as an ancestor. Its actor permits ordinary scheduling unlock only in
foreground baseline/active stages without a current action, handoff or OS
scope. Chooser/receiver/pending acquisition remains inline under the original
source lock. Preparation requalifies the owner headers, complete graph,
originals and latest completed Primary cue before publication; an actual phase
advance discards preparation without adopting facts. Those ownership rules
informed this source. No Phone actor facade, Appium touch, Primary cue,
foreground exception or Phone authority is copied as Pico behavior.

The current source deliberately rejects receiver Activities: the existing
independent receiver accepts the Phone authority and has not been qualified
for `org.overte.pico.snapshot.files`. The normal Pico app-owned OpenXR layer
also cannot drive another process's chooser or reserved system controller
input. The Phone chooser driver uses real Appium accessibility/touch and cannot
be relabeled as Pico VR input. The next Share owner needs an actual permitted
normal Pico OS selection/cancel route, exact parent intent before that input,
original grant/receiver APK/UID/process/stream evidence and actual return/quiet.
See [the existing Share/Upload boundaries](SNAPSHOT_SHARE_UPLOAD_BOUNDARY.md).
This source supplies no claim that those missing operations were executed.

## Device-free verification

The owning Save-fences group passed 36 cases in 3.528 seconds including its
runner. Its actual Pico factory case retains the original candidate verifier,
process/session and normal navigation guards; only OS resolver/activity/UID
responses are explicit host transport seams. The independent source cases
reject foreign windows, the Phone receiver, missing/changed authority/binding,
changed chooser UID/resolution, lock release/reacquisition, ambiguous resumed
activities, final-guard window changes, and slow original-copy work under a
frozen native clock. Returned/archive DTO copies are built before final OS and
clock requalification. Coverage selection also passed (two groups, 3.59 seconds
total); private version-registry validation passed. No device or OS chooser
selection was run.

## Admission integrity and final parent requalification

A follow-up pins the original prepared chooser as canonical strict JSON bytes
and SHA-256. Every later scope guard checks both its exact typed JSON value and
digest before an SDK read; in-memory component, UID, nested raw provenance and
container/string-subclass replacement cannot become new admission authority.
After the last actual Activity/resolution/UID reads and their original copies,
the scope again checks the same lock acquisition and parent authority, then
seals both clocks. This final authority check performs no SDK/native refresh.
No observation is published when a final UID read changes parent authority or
actually releases and reacquires the host lock. Return/pin-copy work is covered
by the final clock seal. Three persistent tests add those counterexamples to the
existing owning selection; no contract version, selector or capability changes.
