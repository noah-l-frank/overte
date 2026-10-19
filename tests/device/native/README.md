# Native feature observations, version 1

These are read-only sources for the existing adapter architecture. They are
**not** complete `feature.<area>` implementations or device evidence. The
`OVERTE_E2E_FEATURE_TESTS` CMake option defaults to `OFF`. Both that option and
an explicit `--testScript` / writable `--testResultsLocation` launch are needed.
Nothing builds or installs a client when an adapter requests an observation.

The separate [Script execution observation](SCRIPT_EXECUTION_OBSERVATION.md)
provides actual native manager identities and historical CommonJS completion/
cache/error events. It supplies no code or desired module path to the client.

The separate [world-render acquisition](WORLD_RENDER_ACQUISITION.md) connects a
native request to a later main-mono tone-map GPU callback and retains original
PNG memory with an independently observed release inventory. Its private
platform transport/receipt cleanup and full ownership coordinator remain open;
native code is uncompiled and no area capability is enabled by this source.

The closed `feature-native-observe` command has exactly `schemaVersion:1`,
`commandId:<32hex>` (`ios-<32hex>` on HTTP/AFC) and `action`. It accepts no
expected state, field selection, filename, script, renderer setting or result.
The probe calls `Test.featureNativeObservation(requestId)` and saves its
original completed object to `feature-native-observation.json`. A pending native
animation fence schedules the same read-only request every 50 ms, at most 50
times (2.5 seconds), without blocking the GUI or publishing a pending packet.
A newer request and script shutdown retire the pending timer. Re-reading a
completed native request returns the original cached packet, without retiming.
An absent/failed hook or exhausted fence
writes `{schemaVersion:1,requestId,available:false}` and readers reject it.

The native object has exactly `schemaVersion`, `requestId`, `instance`,
`sequence`, `capturedEpochMs`, `processId`, `lifecycle`, `animation`, `graphics`,
`audio`, `account`, `requestedEpochMs`, `animationFence`. The last two fields are
optional for legacy Android diagnostic readers; iOS requires the native request
epoch and, for animation evidence, the populated native animation fence.
The schema is enforced by
`adapters/native_feature_observation.py`. A read is bounded to 262144 UTF-8
bytes, five seconds and 51 attempts. Duplicate keys, nonfinite numbers,
incorrect types/PID/request/instance, regressing cursors/counters and captures
older than 1500 ms or more than 250 ms in the future are rejected. Input is
never replayed to recover a missing result. Partial original file writes may
be polled; a matching invalid complete observation fails.

* `lifecycle` counts actual Hidden/Suspended and later Active notifications,
  plus one initialization by each new native process. Transient Inactive
  states do not invent a background. The native private
  `feature-lifecycle.v1.json` survives an actual app restart in the same isolated
  results directory. QSaveFile commits the bounded 0600 document atomically;
  a malformed/noncanonical/symlink file or write failure disables this source.
  The runner must provision one private isolated results directory per owned
  test execution and retain its counters until restart checks finish. Counter
  files are owned diagnostic artifacts, not persisted user settings.
* `animation` is a locked copy made on the real animation evaluation thread
  after the animation/IK/flow pass. It carries the actual Rig identity,
  original evaluation sequence/time and up to 256 final joint rotations and
  translations. An active override includes the real selected AnimClip URL,
  first/last/current frame, rate, looping, loaded frame count and the clip's
  own last nonzero-delta evaluation time/sequence. The URL comes from the
  resource actually copied/retargeted into the clip, separately from
  `requestedUrl`; a pending new load cannot relabel old animation frames.
  Reads never stamp an old
  pose current. No selection/timer event is reported as a measured pose.
  Animation consumers require fresh advancing Rig evaluations, a loaded graph
  and, for overrides, a loaded actually evaluated clip. Native joint/image/peer
  evidence must still establish the visible feature effect.
  The native GUI thread records its own request epoch, Rig identity and current
  evaluation sequence at the first call. A populated `animationFence` carries
  `rigId`, `sequence`, `requestedEpochMs`; a completed animation must belong to
  that Rig, advance that counter and postdate that native epoch. Being merely
  less than 1500 ms old is insufficient after an input. iOS never compares a
  host wall clock with a native animation wall clock: its unique correlated
  request, native request-to-capture interval (at most five seconds) and bounded
  local monotonic acquisition establish freshness. All native pose/clip/event
  ages retain the original native clock. A missing native fence cannot qualify
  iOS animation. For legacy Android packets, the reader may request a new
  **read-only** native sample while awaiting
  a later evaluation, within the same five-second/51-attempt bound. Click/key/
  script inputs are never replayed, and old poses are never retimed.
* `graphics` explicitly distinguishes requested resolution and the native
  Application resolution read. Shadows/mirrors/haze/local-light/material flags
  are **settings**, not evidence that a render pass ran or pixels changed.
  Original renderer/framebuffer acquisition remains a separate required source.
* `audio` reads the real AudioClient recording/mute flags on its owning thread.
  Flags do not prove microphone/preview PCM or an independently audible peer.
  The optional `recordedVoice` source separately describes the actual memory-only
  three-second Record-and-Play feature: active/current byte counts and native
  frame format, plus the last real phase event's original sequence/time/counts.
  It does not confuse AudioClient file recording with this memory preview.
  Completed/cancelled event counts are historical; current buffer counts may
  already be zero. Reading never stamps that old event current. Active events
  must be fresh, sequences cannot regress, and consumers requiring this feature
  reject an older producer missing the source. These counters do not replace
  original PCM or acoustic evidence.
  The separate [original preview PCM source](RECORDED_PREVIEW_EVIDENCE.md)
  now supplies capture-before-normalization and actual accepted sink writes,
  with native cycle/event provenance and explicit private-data cleanup. This
  source is E2E-only, uncompiled and still needs platform/device qualification.
* `account` reads login state and a SHA256 of the actual principal on the
  AccountManager thread. It exports no username, token or endpoint. Protected
  access/revocation still needs a real controlled server observation.

All instrumented branches must be compiled and qualified later in the Proxmox
laboratory. Current checks run Python and the actual JavaScript dispatch with
explicit native boundaries. They do not compile C++, deliver Qt notifications,
render a frame, record PCM or establish installed-code identity.
