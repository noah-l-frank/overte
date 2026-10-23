# Android Phone source coverage

## Subsequent manual-parity review, 2026-10-23

The [manual-parity findings review](PARITY_FINDINGS_REVIEW.md) corrects the
People REST fixture and domain readiness checks and adds a genuine account-label
QML regression. The unchanged product dependency still fails six account cases;
the pinned People product script also retains an incompatible REST contract.
Visible account-header and Web Undo/Redo/IME observations remain explicit gaps.
The fourteen-area matrix below describes the earlier exact source/scoped-host
baseline. It does not qualify this later branch, the other session's product
fixes, or any physical client. No product fix or source-pin update is included
in this review.

## Current Android Phone closure, 2026-10-23

All **14/14** common v18 areas have Phone source composition and scoped host
journey evidence. Snapshot now joins the other thirteen areas: the unchanged
original SDK26–28 whole module passed **27/27**, and the unchanged original
SDK29+ whole module passed **23/23**, both on source
`7be78768fa023ea88eada5ddfabd1189ff9d665f` and the same twelve actual runtime files.
Their actual before/after runtime-map SHA-256 is
`c3759c9aeba00d8483ff8df2a98b100df2de3a4cc7a4c12c844e6616ac0e347a`.
The strict closed-proof qualifier passed with `sourceComplete=14`; the machine
matrix is taken from its output, rather than reconstructed from expected pins.
The other thirteen areas retain their documented scoped evidence; they were
not all rerun by the final Snapshot qualification.

This is source/test-logic closure with explicit synthetic native/Android seams.
It does not claim a complete registered-suite run, a complete Android native/APK
build, real Android OS behavior or physical acceptance. Required capabilities,
private controls, original evidence and source admission still fail closed;
turning on a flag alone cannot supply them. Pico and iOS have separate sessions
and receive no qualification from this Phone result.

The versioned [JSON matrix](phone-source-coverage.v1.json) records actual public
triples, default-off flags, original catalog foundations and required capability
unions. The final matrix is emitted by the strict closed-proof qualifier; it is
documentation, not another runner or a physical acceptance receipt.

“Implemented” means source composition. “Reported” means prior feature handoffs
provide scoped host evidence with synthetic native/SDK boundaries. This final
Snapshot work did not rerun every other feature or all registered tests.
**Every row remains full-Android-build unverified and device untested.**

| Area | Public facade source | Whole catalog source join | Host facade | Native qualification available | Handoff |
| --- | --- | --- | --- | --- | --- |
| World Navigation | Implemented | Implemented with prerequisites | Reported | Partial Qt components | [Navigation](WORLD_NAVIGATION_FEATURE.md) |
| Authentication | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Authentication](AUTHENTICATION_FEATURE.md) |
| Avatar / People | Implemented | Implemented with prerequisites | Reported | Partial Qt components | [Avatar / People](AVATAR_PEOPLE.md) |
| Create | Implemented | Implemented with prerequisites | Reported | Partial Qt / filesystem components | [Create](CREATE_FEATURE.md) |
| Emotes | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML components | [Emotes](EMOTE_FEATURE.md) |
| World Web | Implemented | Implemented with prerequisites | Reported | Partial Qt / JNI / Java / R8 | [World Web](WORLD_WEB_FEATURE.md) |
| Graphics | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Graphics](GRAPHICS_FEATURE.md) |
| Audio | Implemented | Implemented with prerequisites | Reported | Partial Qt audio components | [Audio](AUDIO_FEATURE.md) |
| Chat | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML / peer / Settings | [Chat](CHAT_FEATURE.md) |
| Snapshots | Implemented | Implemented with prerequisites | Actual whole SDK26 27/27 and SDK29 23/23 | Partial Qt / Java / filesystem / HTTPS | [Snapshots](SNAPSHOT_FEATURE.md) |
| Scripts | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Scripts](SCRIPT_FEATURE.md) |
| Assets | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML / file / geometry / oven components | [Assets](ASSETS_FEATURE.md) |
| Lifecycle / Input | Implemented | Implemented with prerequisites | Reported | Partial original Qt / QML / IME / keyboard / timer | [Lifecycle / Input](LIFECYCLE_INPUT_FEATURE.md) |
| Tablet Web | Implemented | Implemented with prerequisites | Reported | Partial Qt / inline leases / JNI / Java / R8 | [Tablet Web](TABLET_WEB_FEATURE.md) |

All public triples use the existing [Phone Appium dispatcher](appium_adapter.py).
The unchanged [common capability gate](../../modules/feature_capability_gate.py)
requires each suite's full capability union, including `launch-smoke` and every
reused foundation. Installed candidate/artifact/session/PID, private credentials,
source admission, separate Actor, freshness, ordinary input and original file/
image/audio/peer/lifetime obligations remain mandatory. Neither a flag nor an
ACK supplies a measured product effect.

## Evidence scope and history

| Final Snapshot evidence | Exact scope |
| --- | --- |
| SDK26–28 original whole module | 27/27 PASS; unittest 170.489 s, outer 170.94254893495236 s; all 15 applicable normal actions, original cleanup/recovery/finalization tests; no skip/timeout. |
| SDK29+ original whole module | 23/23 PASS; unittest 193.012 s (whole-loader 193.01258141500875 s), outer 193.57261233997997 s; original complete Common test 113.06485598394647 s; no skip/timeout. |
| Original late-start Actor finalizer regression | 1/1 PASS on Root `7be78768`; 17.596 s; actual separate child exit and unchanged repeated finalization. It is focused evidence, not a whole backend. |
| Actual source binding | Both wholes use Root `7be78768fa023ea88eada5ddfabd1189ff9d665f`; actual pure twelve-runtime-file pre/post maps match `c3759c9aeba00d8483ff8df2a98b100df2de3a4cc7a4c12c844e6616ac0e347a`. SDK29 maps are explicitly derived from its unchanged actual 408-input pre/post reports, with hash provenance. |
| Original SDK29 test source | SHA-256 `e99ad31a02e90ecf08ccac1edd3fe7135bff40ed8a001294a2f7d4c389acd7fb`; actual invoked whole loader and native argv archived, without selectors or argv rewriting. |
| Final source closure | 402 production paths matched exact Root, zero production differences/unstable reads; 19 unselected support-counter differences remain explicit. The latter were not executed by SDK29. |
| Private preservation | SDK29 retained all 616 actual original files before teardown, raw log/result, invoked loader/harness, actual source archives, before/after pins and empty process-group proof. All prior failed evidence remains unchanged. |

The strict qualifier's final output has `sourceComplete=14`. These are host
source/test-logic measurements: actual Python, private files, separate processes,
loopback services and actual Java helper paths are exercised; native renderer,
Android UID/package/SDK/OS and device boundaries remain explicitly synthetic.
The registered 242 checks (3 dependency-light, 51 prepared, 187 common, 1 extended)
are an inventory, not a claim that one complete 242-check campaign ran.

Earlier progress counts and failed runs describe their original source revisions,
not the current state. The earlier SDK29 whole23 on Root `060cbac1add4653ec491346c8d7cc55716dbbbed`
remains **RED: 22 passed, one failed**. Its separately passing full Common test
does not turn that module green. The subsequent Legacy first-receipt correction,
focused original finalizer regression and new complete 27/23 runs establish the
current source scope. No historical result or byte pin was rewritten.

The 45-case Actor component run passed on source `95e1f3af` (byte-identically
joined as Root `7be78768`), but separately pre-archived only **11/12** runtime
paths. `script_observer.py` was omitted from that component's pre-run archive;
its post-only original and matching source-commit blob remain recorded as such.
A clean commit check is not a substitute for a separate pre-run byte archive.
That component result is not whole-backend qualification. The later complete
27/23 runs have their own actual twelve-file before/after evidence.

At historical Root `060cbac1add4653ec491346c8d7cc55716dbbbed` / map `3fd0f028dc02d20e54f8d56a52ec8d0ca6d7eb8ca68979246c376456caeaea26`,
SDK26 passed 27/27 (161.846 s), while SDK29 remained 22 passed/one failed
(205.63402422703803 s). The failure was the unchanged original late-start Actor
case reaching its 30-second receipt deadline before client close; its separately
passing Common method (104.1559442479629 s) did not qualify that whole module.
Earlier freshness/20-second-cleanup failures likewise remain RED at their
original sources. The newer passes neither erase them nor repair their pins.

Component stages such as the earlier 67 targeted parent checks (88.631 s),
51 marker-refresh checks (29.488 s) and five full-retirement host cases
(90.218 s) retain their original counts and source scopes. They are not rebranded
as the final complete backend runs.

## Native build and physical acceptance

Partial Qt/QML/C++/JNI/Java/R8/filesystem checks cover only the boundaries named
in each feature handoff. They do not build all Android product translation
units or prove a real renderer/IME/OS, microphone, network peer, AssetServer or
oven. Authentication, Graphics and Scripts instrumentation still includes
uncompiled area paths. Assets also documents its unresolved product upload
callback lifetime risk and missing host GLM for a full HFM syntax check; host
composition does not resolve them.

The [dedicated E2E debug option](../../../../android/phone/docs/BUILD.md#dedicated-feature-e2e-debug-build)
is default OFF and forced OFF for non-debug builds; its foundation hooks and
installed-code admission remain mandatory. Prior Gradle-loader/Groovy/CMake and
release component checks, eleven sealed dependency archives and the earlier
resource-admission failure retain their actual scopes. Dependency availability
is not an APK receipt. No complete APK/native build was performed in this closure,
and none is requested now; no new resource-capacity conclusion is asserted.

Future physical acceptance must run through the Proxmox Jenkins laboratory
using the official `overte-jenkins` wrapper. Workstation Jenkins, local Appium
servers and direct local device-test runners must not be started. Host/mock
examples remain device-free; this closure ran no physical laboratory job.
A complete APK build remains unperformed at the user's request.
