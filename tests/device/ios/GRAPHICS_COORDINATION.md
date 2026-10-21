# Whole-run iOS Graphics coordination and remaining finalization

`graphics_feature.py` composes the existing scene, preference, calibration,
background, restart, original observer, independent publisher and resource
lifetime owners. It supplies the three shared Graphics operations internally.
It is not yet registered as a complete capability: worker/dispatch configuration,
final stop, paired process quiet windows and recoverable metadata retirement
remain required. Scripts and Authentication remain the two complete areas.

## Inputs, roles and recovery

Preparation uses ordinary Go To and View-menu inputs and preserves the original
world, avatar pose, camera and measured preferences. Both roles must acquire
their own off-reference images before the first public baseline. Calibration
captures both features, including actual mixed and all-off settings, and restores
the measured settings before observations. The actor has its own fixture reader
and publication credential; primary results and expected values are not passed
to it.

Ordinary Graphics actions retain their existing one-send intent and source-token
ownership. Reconstructing an uncertain action does not send it again. Only
proven source-lock contention is retried. Nested preparation cannot extend the
current public deadline: preparation/observation/publication use 20 seconds;
ordinary actions and cleanup use 60 seconds. Source acquisitions retain their
independent 1500 ms bounds and original native clocks.

Restart has two barriers. Before Stop, both roles acquire additional original
old-process images after calibration restores the actual settings. Their exact
before/after observer copies are retained as immutable version-1 records. A new
native settings packet must join both originals before Stop is authorized.
After actual old-PID death and source/owner transfer, both roles independently
acquire their first new-process frame and lifetime admission. Version-1 rejoined
records preserve each original observer, binding and old-frame transfer. The
primary validates both records and role lifetime histories before acknowledging
the restart. A lost committed copy can be adopted without recapturing; a foreign
role record cannot be hidden by two nominal acknowledgments.

Cleanup restores the actual original preferences while the controlled scene
remains visible. Each invocation starts a new three-second quiet window of
fresh original images, native settings and independent host/native/monotonic
clock intervals. Earlier elapsed time is not reused. This is the shared
journey's observable cleanup; it does not claim that retained Web surface caches
or all native resources have been freed.

## Original world images and archives

`graphics_restored_frame.py` owns one role's separate final Vulkan image after
ordinary world/camera restoration. Version-1 owner and immutable record preserve
the original world, source floors, actual settings, before/after subject and
scene-load packets, completed original PNG, native release receipt and complete
native/host clock join. The measured recorded camera must match the restored
subject. Stage 1 preserves the old world's actual old PID and requires the
strict restart proof for current-process images. No controlled fixture marker
or public feature result is invented for a world that no longer contains it.

Intent precedes acquisition. An unknown capture remains owned and cannot be
repeated by reconstruction; its actual native buffers are still released.
An immutable record committed before a lost return is adopted unchanged.
Historical archive validation requires the original PNG/inode and all exact
records, works after runtime metadata removal, and supplies no current fact.
Missing originals, changed pixels, stale fixture-camera images and foreign
scope fail closed. The whole finalizer still has to call this component for
both roles before its owned stop.

`IOSGraphicsSamples.archive_owned` additionally validates an exact retained
request-to-original-sample/owner mapping after runtime metadata removal. It
retains marker-pending and abandoned states, original cursors and seen-frame
history. The existing live `archive_index` keeps its strict current-index CAS.
No archive path creates a native command, advances a clock or makes historical
evidence fresh.

## Host verification and integration boundary

The unchanged fifteen-step shared journey passes on real private host files,
loopback HTTP and separate synthetic iOS SDK role threads, including background,
restart, restore-original, independent publication and double cleanup. The
passing run took 578.990 seconds of host wall time. Its synthetic SDK clocks
exercise protocol deadlines; this is not physical iOS timing qualification.
The image policy is fixed before capture for both roles: its subject band covers
the actual haze-board and reflector interiors and excludes the challenge card.
The shared five-percent changed-subject assertion is unchanged.

Focused cases cover ignored inputs, source/orphan rejection, nested deadlines,
initially enabled settings, independent old/new-process barriers, lost committed
copies, foreign role originals, current restored-camera images, original archive
retirement and changed/missing evidence. Native/GPU/Qt/OS/driver boundaries and
pixels remain synthetic. Native code is uncompiled; devices are untested.

The final focused selection passes 25 cases in 184.103 seconds across coordinator,
both restart barriers, exact sample archives and restored-world images, including
stage-1 old-world/new-process ownership. All five selected no-build repository
suites, the contract registry and whitespace checks pass. These results remain
separate from the earlier broad aggregate; no new aggregate pass is claimed.

The added shared reconciliation surface includes the five version-1 registry entries
`ios-graphics-feature`, `ios-graphics-restart-barrier-record`,
`ios-graphics-restart-rejoined`, `ios-graphics-restored-frame` and
`ios-graphics-restored-record`. The common feature contract remains version 16;
no Phone/Pico input or ownership is imported. Sample archive validation is an
additive API; sample/index writers now emit v3 with v1/v2/v3 readers. The additional `ios-graphics-run-retirement` v1 entry describes the separate
original closed-authority acquisition. All changes remain solely in the
isolated local iOS branch.

Final integration must compose both original-world image/lifetime snapshots,
durable one-send final Stop, independent original numeric-PID/OS quiet windows,
all role/stage immutable archives and recoverable CAS metadata retirement.
Retained pre-exit cache counters must remain unchanged. No post-death zero native
packet, fixture retirement alone or bundle lookup can replace that proof. The
worker must remain available until its role's responsibility has actually
retired. Only then may configuration/dispatch advertise the whole capability.

The sample owner now supports actual inactive-run retirement using the original
retired journal authority plus original native release, preserving uncertain
acquisitions as abandoned history. See [the v3 sample handoff](GRAPHICS_SAMPLES.md).
Uncertain actor POSTs now have the separate original-authority retirement path
described in [the publication handoff](GRAPHICS_PUBLICATION.md). It records no
publication outcome after journal deletion. The remaining finalizer/worker must
call these paths before stopping the process, preserve their exact originals,
and then compose both role image/lifetime snapshots, one-send Stop, independent
process quiet windows and complete paired archive/metadata retirement.
