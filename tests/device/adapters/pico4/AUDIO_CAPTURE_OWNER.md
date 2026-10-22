# Normal Audio capture continuation

`PicoAudioCaptureOwner` continues an already normally opened and claimed
`PicoAudioPageOwner` on the exact same parent source-lock instance. It can take
ownership directly after claim, or after the existing normal muted Start
rejection and original unmute restoration, before tap release. Each next cycle
gets its own bounded journal and preserves every preceding native cycle and PCM
file before another normal Start. It delivers
only the existing `AudioPreview` / `TokenAudioUI` normal Record input. It supports
an unmuted capture followed by ordinary Record cancellation, or observation of
the actual automatic capture/play/drain/completion. No device or actor is
started by constructing this component. No complete Audio capability is exposed.

The caller supplies the existing `PhaseFixtureReader` for its actual Audio run.
The immutable original activation journal binds the recording-start ticket and
actual activation time, independently of product results. A different current
ticket or verb prevents Start. The actual new native cycle must follow both
that original activation and the final pre-input native/UI/settings fence.
The original normal action operation ID is durable before delivery; cold
reconciliation reads the existing Preview pending/action originals and never
presses Record again. An intent gap with no Preview original stays unresolved.

Full native, normal page, Audio settings and Lifecycle packets are retained
with original bytes and SHA-256. Their independent cycle/active/mute values must
agree. Canonical page identity, original input peak state, other Audio/mixer
settings, foreground tablet and absent VRKeyboard remain separate observations.
A terminal capture requires three seconds of original quiet across nine native
and host clocks before its original PCM is retained. Read-only `observe()` follows actual
byte progress and automatic terminal events without another Record input. Any gap over 500 ms resets
the window. Final guards, persistence and report construction remain within the
native freshness and independent monotonic bounds.

The input-before-normalization and accepted loopback sink-write PCM remain
separate original files, with the original source DTO and immutable start ticket.
Samples are copied unchanged; no replacement WAV, expected challenge or acoustic
verdict is constructed. Planned and opened ownership are saved before file
creation/writing. Files are mode 0600 under the existing private parent and are
created exclusively. Saved reads compare original descriptor/path device,
inode, size, full mode, owner, links and nanosecond modification/change times
before and after the bounded read. Missing, modified or replaced originals fail.
An interrupted writer remains `reading`; it is never adopted, overwritten,
truncated, deleted or retried as normal input. Orphan originals prevent a new
cycle owner before its first possible input.

After this explicit handoff, the parent muted-rejection continuation refuses to
send its own mute/Record actions. Base cleanup also refuses capture journals or
orphan PCM and skips a competing Preview release. It can still perform the
original adapter teardown, which does not retire these journals or files. The
private factory accepts the existing parent to preserve its exact lock and
original source objects; it does not manufacture a new parent lock alias.

This is a bounded positive capture continuation. The caller must retain this
cycle before starting another and compose the remaining common recipe stages,
actual independent acoustic captures/peer projections, mute and background
interruption, normal final X/peak/settings restoration and original resource
closure. Empty product buffers and terminal events leave the real polling timer,
recording-buffer allocations, contexts and evidence originals owned. There is
no implicit process restart or journal retirement.

The `audio-capture-owner` selection executes these real owner,
Preview, source-reader, normal token and phase-journal classes with explicit
independent host boundaries. Actual original AudioClient/Qt timer and unchanged
Audio.qml checks remain in `audio-settings-source`; simulated host PCM is not
physical or device evidence.
