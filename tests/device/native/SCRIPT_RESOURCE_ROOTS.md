# Original configured Script resource root, version 1

The E2E-only `Test.featureScriptRoots(command)` getter reads the application's
actual `PathUtils::defaultScriptsLocation()` without selecting or changing a
resource path. It never infers the root from a running Script URL or basename.
This supports runtime Emote source association; it is not an animation, UI,
render, peer or complete feature verdict. Native C++ remains uncompiled and all
physical clients remain untested.

## Native request and original response

The closed request has exactly `schemaVersion:1`, `commandId:<32hex>` and
`action:"feature-script-roots-observe"`. The native getter also accepts the
existing `ios-<32hex>` nonce grammar; no iOS adapter is enabled by this component.
No requested root, source path, expected profile or result is accepted. The GUI
owner requires its original active feature-test lifecycle, private test results
location and `--testScript`, with a bounded increasing read counter. A foreign
thread is marshalled to that owner; unavailable owners/getters remain failures.

The exact response fields are `scriptRootsVersion:1`, original `commandId`,
`instance`, `sequence`, `processId`, `requestedEpochMs`, `capturedEpochMs` and
`source:{defaultScriptsUrl:<actual configured URL>}`. Instance is the existing
native feature-observation birth, shared with native Script and Rig observations;
its read counter is independent. The original configured URL and clocks are
retained, without replacement by a preferred URL. The probe saves the result in
`feature-script-roots.json` and deduplicates the command. A missing native getter
saves available:false, which cannot satisfy the complete typed response.

## Existing reader and Pico binding

`NativeScriptRoots` uses the existing guarded nonce/private-result transport.
The Pico `_script_roots_observer(target)` factory binds the existing actual
candidate installation, PID/start and OpenXR session guard through the same
private native feature transport. It sends only the exact observation command,
never a path mutation, installation, launch or session repair. The native owner
retains at most 4,096 original nonces and refuses their reuse. The probe deduplicates
its current command so a repeated poll cannot overwrite an original success with
an unavailable duplicate response.

`read(after_sequence)` sends one new read nonce, with the existing five-second/
51-read limit and 16 KiB response bound. Complete successful capture/transport
freshness is at most 1.5 seconds, including a separate monotonic elapsed-age floor.
Native request time must follow the independently read Android clock barrier.
The original process/birth, strictly advancing sequence, nonregressing clocks
and exact configured URL remain pinned. A changed root cannot be silently
adopted. `restore(original)` accepts only a complete original packet before the
first read; its next live acquisition must advance that original floor and
match its process/birth/root. Callers must durably retain the packet and their
actual session/process ownership before another acquisition. A missing original
cannot be upgraded or replaced by a successful empty observation.

The controlled input profile requires a local file/qrc URL, no authority,
credentials, query, fragment, traversal, escaped alias or control characters,
and an actual scripts directory. `root_url` adds only a trailing separator and
canonical qrc URL spelling to that original configuration. It never derives a
root from an engine filename, falls back to qrc or changes the retained source.
Unsupported/foreign configurations fail before source-profile selection.

## Original Emote code association

`emote_source_profile.select_from_roots(script_packet,before,after,pid,epoch)`
validates three complete originals: a root read, the native submitted Script
observation and another root read. Root counters/nonces must advance, exact
root metadata must remain unchanged, all native births/PIDs must agree and
original request/capture ordering must fit within 1.5 seconds. The original native
engine key may be a physical URL or the exact `file:///~//...` form stored by
`ScriptEngines::normalizeScriptURL`. The root join requires the complete original
all-known-manager membership in either case: the same native manager ID must
have an actual assigned physical URL under the configured root, with a valid
load generation and assignment preceding code submission. A normalized key
alone never selects a root. The descriptor preserves the original table `url`
and original `assignedUrl`, generation and assignment time separately. Submitted
UTF16 code identity must match one reviewed source pin. Wrong code, foreign paths with a
recognized filename, missing packets/nonces, old reads or mixed processes fail.
Returned metadata selects input semantics only; it contains no measured pose.
The v3 Emote selection (fixed integration reference `154b0ca8ce`,
`tests/device/native/EMOTE_SOURCE_PROFILE.md`) separately joins original
compiled code inside the shared Phone default VM. A top-level default-script
assignment alone cannot identify included Emote bytes or caller origin.
Each role's later full measurement owner must independently acquire and persist
these originals alongside its own original Rig, widget, image and phase records.

This passive component owns no product resource, timer or input lease. Its
original observation output and accepted host packets remain private evidence;
complete feature cleanup still requires actual native/UI/input/resource absence
and exact owner-journal retirement. No complete Emote capability is advertised.

Selected root/profile/Rig and actual Pico wrapper tests exercise the real
Python and probe JavaScript with explicit synthetic native boundaries. The new
native getter remains uncompiled; no device qualification is claimed.


Successful read copies are prepared before the final original guard and both
actual clocks. The final native epoch cannot regress from the prior clock read;
the entire acquisition additionally has a strict monotonic 1.5-second floor.
Native age accounts for time after the final epoch read, even when the native
clock freezes during another slow host operation. A late copy or final guard
cannot return an aged packet or advance the accepted original cursor. Targeted
frozen-host/native copy and last-guard clock-jump counterexamples demonstrate
this boundary; no polling deadline or freshness limit is increased.
