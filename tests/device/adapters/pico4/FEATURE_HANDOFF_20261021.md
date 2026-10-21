# Pico adapter handoff: 2026-10-21

This branch completes two source-level Pico feature areas, Scripts and
Authentication. The other twelve remain partial or missing
with concrete missing operations, original evidence, cleanup obligations and
next executable source steps in the
[machine coverage matrix](FEATURE_COVERAGE_20261021.json). Every row separately
records shared v16 test logic, adapter implementation, native compilation and
device qualification. Native code is uncompiled; no device is tested.

| Area | Current Pico implementation | Concrete next boundary |
| --- | --- | --- |
| Worlds/navigation | Partial Go To/history and original reply reader | Actual bookmark/Places storage/model, failure modal, arrival/image and independent observer join |
| Authentication | Complete source; 17-step shared flow and counterexamples host verified | Compile and qualify actual VR Home ray, IME, HTTPS provider and account lifetime on Proxmox |
| Avatar/contacts | Complete adapter missing | Source-bound Avatar/People inputs and independent model/bookmark/wearable/consent observations |
| Create | Partial token controls and entity foundations | Actual JSON picker/export, model/texture/PolyVox, permission actor and original file/image/peer joins |
| Emotes | Partial submitted-code/Rig observations | Actual running source/profile, VR normal controls, timer/caller/pose and stereo avatar evidence |
| Web in world | Partial native DOM source | Actual controller-ray hit/DOM input, original document/echo journals, response receipt and stereo image join |
| Web in tablet | Partial native DOM source | VR DOM input plus original inline carrier/retained callback and complete document/cleanup owner |
| Graphics | Partial normal settings; stereo v2/v3/v4 with executing passes and used camera uniforms | Per-eye effect pixels, original scene/Web lifetimes, independent actor and complete area ownership |
| Audio | Partial normal controls/cycle/history/PCM sources | Whole cycle owner, microphone stimulus, independent acoustic capture/publisher and lifecycle/cleanup join |
| Chat | Partial normal controls, current native view/cache and peer IPC prerequisites | Independent primary/peer UI/storage/keyboard/delivery ledger and owned mixer/distance/recovery coordinator |
| Snapshots | Partial private original-output foundation | Actual OS Save backend/authorization, independently acquired receiver/save/upload originals and callback cleanup |
| Scripts | Complete source; host verified | Review/compile test-gated native source and later qualify the exact installed candidate through Proxmox |
| Assets | Complete adapter missing | Actual Assets UI/bundle picker, original server mapping/oven/permission/model sources and independent actor |
| Lifecycle/input | Partial current token/pending-event owner | A demonstrated normal Create Back route on 3D TabletRoot, actual VR keyboard/tracking/context and full stale-input join |

These are implementation gaps, not successful skips. `--require-complete` must
continue rejecting a full selected run when required capabilities are missing.
No acceptance policy, workflow, safeguard, evidence registry or platform label
was changed to hide them. A normal input ACK never proves its effect.

The exact [Scripts handoff](SCRIPT_FEATURE.md) and
[Authentication handoff](AUTHENTICATION_FEATURE.md) specify every implemented
operation, original inputs/observations, provider/actor configuration, error and
recovery paths, time limits and cleanup. The matrix lists corresponding
obligations for every incomplete area; shared `*_SOURCE.md` contracts remain
normative. No backend, permission, ordinary Back route or independent actor
result is inferred from Phone defaults or historical coverage.

## Isolation and provenance

The new isolated branch is
`test/android-pico/feature-adapters-parallel-20261021`, based on the actual
committed Pico state `de7587093406a49573189e626bd350a12cb3d31f`. Both shared
foundations `7636452f2124029798948aafae70ecff5c5fa7d0` and
`0a52254c0580a1fd28626d23bead55015500c0a7` were verified as ancestors.
The original reference worktree was inspected read-only. Its seven task-related
WIP files were captured twice with matching commit/status/patch/content,
applied only here, reviewed, host-tested and committed with
[original hashes](WIP_PROVENANCE_20261021.json). The private original patch and
file snapshot remain outside the checkout. No original reference, Phone, iOS,
frozen worktree or another session's evidence/progress was edited.

Only the frozen Phone reference
`fe4684bf46585088370b3a328a738f147e670b97` was used. Its status confirms three
complete source adapters (Scripts, Authentication, Graphics); Emote is component
work. Its historical instruction to pause Pico does not override this task's
explicit parallel authorization. No moving Phone branch or uncommitted Phone
file was imported. The historical 2026-10-18 overview was read as context only;
actual sources determine this matrix. The frozen main reference lacks these
later complete adapters and was not used to fabricate integration.

## Shared changes for later Phone reconciliation

The [selected-source manifest](STABLE_PHONE_SELECTION.json) records original
paths/hashes and narrower dependency commits. The
[shared extraction manifest](../script_journey/PROVENANCE.json) records the
frozen coordinator sources. There was no Phone sibling merge or protected
integration.

- Shared Script coordination now lives in `adapters/script_journey/`. Phone's
  existing named modules were not modified. A later integration should switch
  those imports to this shared package through an explicit Phone migration,
  preserving existing Phone journals rather than interpreting the new neutral
  `script-*` schemas as old `phone-script-*` ownership. No automatic migration
  or duplicate Phone feature registration is introduced here.
- Original query identities are checked across complete source transcripts,
  and the Pico native UI source retains a bounded no-recapture nonce set. A
  changed cursor cannot make a reused original query fresh.
- The extracted resource join retains hidden native manager/picker objects as
  actual owned panel resources. Hiding the tablet cannot qualify release or
  cleanup; this stricter behavior needs later Phone reconciliation.
- Native all-known manager membership and assigned-load identity come from
  dependency commit `0c2cecbc3f`. Unneeded later Script work/timer/native-caller
  instrumentation was excluded. All new native observations are test gated.
- Native fixture location, original Script HTTP404 receipts, phase history and
  adapter-only read authority are shared prerequisites. The existing fixture
  server also depends on its frozen Graphics resource generator; those source
  files are selected without activating a Pico Graphics adapter.
- Whole-tree Script manager/picker inventory is now available to the actual
  Pico tablet. The shared inventory walker remains usable by Phone; concrete
  callers still supply their own actual tablet-presence/showing observations.
  The Pico fixed nonce-only channel is independent of Phone private transport.
- Restart handoff v2 optionally requires all-known membership and retains v1
  readers. The Pico complete feature opts into the strict requirement; older
  foundation operations retain their existing compatibility.
- The common engine's restart comparison preserves exactly one new native
  launch while allowing actual nonregressing mobile visibility transitions and
  requiring a settled window. It does not manufacture requested counters.
- Shared source/extraction/binding/worker contracts are explicitly registered.
  `feature-journey` remains v16. Original native render acquisition v2/v3 now adds
  actual executing stereo Frame matrices, packed original two-eye pixels and
  matching successful OpenXR submission. Default mono readers retain v1.
  The Pico factory requires v2. Its 46 acquisition/storage/receipt host tests
  and eight stereo counterexample tests do not qualify native GPU behavior or
  complete the Graphics area. Version 3 additionally joins actual executed
  stereo Forward/Haze/Mirror batch provenance to that same frame and preserves
  v1 mono/v2 stereo readers. Version 4 adds actual bound Forward/Mirror camera uniforms after late pose
  correction and jitter, retaining older readers. Source-dependent per-eye effects and the whole-area
  coordinator remain open. See the shared acquisition document.

Review the shared server/witness/fixture and native header dependencies together
when integrating later. The common regression selection and the owning Pico
checks are required; no Phone/iOS product compatibility or native compilation is
inferred from host-only checks.

The shared [Authentication extraction](../authentication_journey/PROVENANCE.json)
adds neutral account sampling, causality, durable inputs and full cleanup. Its
new journals are not old Phone ownership. Concrete login/UI, native process,
origin launch and Home ray inputs remain Pico factories. The shared Android
launcher hook defaults to no extra arguments; only an explicitly configured
Pico account fixture supplies the validated process-only HTTPS origin. No saved
preference or certificate trust is changed. The gated native QML component/callback inventory observes original loads and
weak destruction, alongside actual locked VR keyboard state; it never cancels
a callback or changes a keyboard. The common independent observer
loop is also reused by the existing Script publisher without adding input
privileges. A later Phone integration must reconcile these sources explicitly.

## Verification and next qualification

The [verification record](VERIFICATION_20261021.json) records exact permitted
commands, counts, exclusions and limitations. Native/compiler suites, QML build
harnesses, builds, installs, devices and Jenkins were intentionally excluded.
The ordinary quick project profile was not run wholesale because its
`native-smoke` and device voice/native cases invoke compilers. Dependency-light
documentation, contract, inventory, whitespace and selected host checks were run
explicitly. No dependencies were installed.

A future separately authorized owner must review the final source, compile its
existing dedicated test configuration and bind the exact installed APK/source
identity. Then provision the fixture and separate observer through the Proxmox
laboratory, exercise error/restart/cleanup on real Pico input/render/lifecycle
paths and retain original evidence through the existing acceptance pipeline.
Use the official `overte-jenkins` wrapper; never start the retired workstation
laboratory as a fallback. Host simulations cannot promote acceptance.

The historical 77-case normal-Scripts group was selected with an explicit
600-second **host group** allowance (about 397 seconds measured). Its existing
runner default was not changed, and default whole-catalog timing is unqualified.
The new nine-case adapter group and one-case shared-engine group both pass
within their unchanged 120-second per-group budget. Native getter, input,
readiness, common journey and quiet-window deadlines were not widened.

## Graphics original subject source

The neutral frozen subject v2 reader and original Test source are now selected
with hashes in `GRAPHICS_SUBJECT_SELECTION.json`. The Pico factory uses its
existing candidate/OpenXR/PID-start guards and original private probe channel.
Only a run and fresh nonce cross the source boundary. Original properties of the
seven derived UUIDs, bounded unowned spatial hashes, actual camera and avatar
feet/orientation/scale are preserved; missing roots are unavailable. Native
nonce history is bounded at 4096 per observer birth and never recaptures an old
request. The existing probe and controlled fixture dispatch support this source.

The full Graphics scene owner still requires actual VR framework entity
ownership, callback/resource retirement and original scene-load observation.
Do not copy Phone's moving-tablet-free scan or fixed-camera restoration checks.
This source adds no feature capability. Native compilation and devices remain
unverified.

## Original Pico scene-load lifetime

`_scene_load_observer()` now reads the neutral `native-scene-loads` v1 source
through the existing private channel and candidate/OpenXR/PID-start guards.
`SCENE_LOAD_SELECTION.json` records the frozen original lease/validator hashes.
The instrumentation is gated by both `OVERTE_E2E_FEATURE_TESTS` and the Pico
application configuration; other platforms retain their original paths.

The actual synchronous local-file load, ResourceRequest callback, cross-thread
serverless/error handoff and Pico deferred-import closure each carry an original
observational lease. Commit acknowledgement cannot remove it: only original
callback/closure destruction retires it. Original request generation, resource
hash with only the location query omitted, phases, result, byte count, native
birth/cursor and capture epochs survive reads. Requests are bounded at 128 per
native observer birth; exhaustion is unavailable. Nonces are retained up to 4096
and never recapture. No request is cancelled, retried, reordered or repaired.

The source records the actual Pico flow and does not import Phone's request
cancellation/ticket/handoff product changes. A committed current scene plus zero
live leases is required before scene restoration can be claimed; actual subject,
provider and pixels remain separate. Native sources are uncompiled, and no
complete Graphics or Worlds capability is enabled by this prerequisite.

## Actual common Web backend and retained renderer lifetime

The original shared Web runtime source has been selected into a neutral namespace
and attached to the actual Pico common backend. The provenance is in
`WEB_RUNTIME_SELECTION.json`; [source v2](../../native/WEB_RUNTIME_OBSERVATION.md)
records its operations, freshness/deadlines, bounds and cleanup obligations.
The original `Web3DSurface` selector resolves this common backend on Pico.
The legacy OffscreenWebView backend is a separate source boundary.

Pico's private factory requires v2, independently reading both native snapshots,
the original Android MAIN fence and actual renderer/worker/callback/EGL release
state. A deleted view, delivered JS result or release request cannot hide the
original expiry lambda, live worker, pending MAIN/GL callback, retained Chromium
callback or failed release. Source-only helper tests do not qualify product
cleanup; no full Graphics/Web capability is enabled. Native C++/JNI/Java sources
remain uncompiled. The canonical no-build catalog now has 52 groups; only the
explicit safe selection was run.

The explicit version-registry validator now registers the selected subject v2,
scene-load v1 and neutral Web-runtime v2 contracts as well as their readers.
The initial dedicated registry run caught those missing declarations; the light
project documentation suites alone did not run that exact check. They are now
included and the dedicated registry/governance checks pass. The three original
private result filenames also use the existing gated atomic owner-only native
save path.

## Per-eye original challenge and photometry

[The stereo pixel reducer](../../native/STEREO_GRAPHICS_PIXELS.md) now joins
original full PNG/pixel hashes, v4 executing camera uniforms and independent
subject snapshots. It decodes the current world marker separately in both eyes,
uses all original camera candidates, preserves late HMD/jitter values and maps
the original source viewport without creating replacement evidence images.
Haze and the final reflector rectangle use their actual Forward/Mirror camera
roles; zero original Mirror draws are handled explicitly as Forward geometry.

Source-bound polygon interiors yield measured per-eye RGB/histogram statistics,
with marker polygons excluded. Candidate/process, clock, processing and oldest
source freshness remain guarded. A missing/stale pixel marker raises the shared
`MarkerNotReady`; an owning sampler may acquire another original frame only
within its existing deadline and after retiring the failed original acquisition.
No ordinary input is resent. Invalid source/camera ownership remains fatal.

This supplies original challenge and photometry, not whole-area completion or
proof of a requested setting. The full coordinator must still join preference
changes, static foreign scene state, independent actor samples, lifetime/restart
ownership and the complete restoration/quiet window. Native rendering and all
physical output are unqualified.

## Passive generic VR Graphics UI and weak lifetimes

[The original UI source](GRAPHICS_UI_SOURCE.md) observes the actual VR generic
controls, original Render values and the separation of tablet hiding, Qt page
visibility and QObject retirement. Its weak root/menu tracker is shared with
the existing Login implementation through a compatible default/alias. Normal
control reads observe Graphics roots before possible replacement; passive
publishers share that exact native weak registry. The original scrollbar Timer,
QML component/status callbacks, keyboard and editor focus remain resources until
their actual source shows retirement. Input is unavailable on this channel.

The native source remains uncompiled; host seams and Authentication regressions
pass. The complete Graphics owner still needs the ordinary Home/Settings/Go To
recipe, original Go To/request-service backend callback lifetime, HMD/framework
entity ownership, per-role sampling/restart and verified scene restoration.
These concrete remaining sources are required before advertising the full triple.

## Original Go To HTTP callback lifetime

The [native tablet HTTP source](../../native/TABLET_HTTP_OBSERVATION.md) now
covers actual original QML callback maps/execution, the system request service,
native XHR callbacks/timers and weak original reply retirement, including
redirect ancestors. `_tablet_http_observer()` uses the existing Pico guarded
transport. Node tests execute the actual modified service/module/QML function
bodies, preserving response and exception behavior; synthetic source tests
reject retained roots, callbacks, handlers, timers, missing binding, outstanding
reply destruction and stale/foreign history. No full Graphics or navigation
capability is added. Whole ordinary input/actor/restart restoration, HMD/framework
entity ownership and quiet-window composition remain required. Native source
is uncompiled and all devices remain untested.
