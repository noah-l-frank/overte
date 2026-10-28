# Ordinary preview input callback originals

Feature 9 remains partial. This optional observation connects the existing
ordinary Qt input callback to the existing preview PCM tap. It creates no
recording, input, acoustic mode or parallel audio service. Legacy digital
preview packets remain literal version one; version two adds a closed
`inputOrigin` subprofile, which can explicitly remain unavailable.

A noncopyable stack ticket brackets the actual input-device `readAll()` and
travels only through its synchronous processing call to the tap. Weak source
and device references, replacement generation, owner thread, recording cycle,
format, route revision and admission epoch must still match at append time.
The original read digest is checked again. Each row separately hashes the
transformed bytes actually appended, with an exact contiguous offset and
original read/tap epoch and monotonic times. Raw input and converted tap bytes
are distinct operands; resampling history is not qualified by this profile.

The actual TestResults/FeatureLifecycle GUI owner supplies an immutable,
revocable diagnostic token to the Audio owner through its existing Qt queue.
Admission requires the feature, voice and dedicated iOS test build, normal
test-script argument, private results directory and valid lifecycle owner.
The iOS build macro belongs to the executable, so the Audio library receives
this owner token rather than consulting an unavailable library macro. Current
directory checks also run at cached return and before final atomic publication.
The origin path uses the existing read-only OS/session state observation;
it does not refresh permissions or activate the audio session.

Unowned or repeated tickets, source/format/route changes, gaps, clock regression,
revocation and bounded-trace overflow cannot produce a complete
origin. The limits remain 384 rows, the existing PCM bounds and the existing
262,144-byte JSON reader ceiling. The native writer uses compact JSON and
refuses an oversized observation. No deadline or recording limit is enlarged.

The existing [PCM lease](AUDIO_PCM_LEASE.md) and WAV/common-detector path reopen
the same original PCM bytes. Both current transport and archived PCM validation
check each retained fragment digest. Optional old digital results never become
required origin facts. Physical ADC, acoustic output, peer reception and
resampler-history qualification explicitly remain false.

## Host verification and native boundary

All 45 selected cases pass in 24.327 seconds: eight new origin codec/JSON/PCM
counterexamples, ten legacy preview cases, five clock joins, five actual WAV
detector cases and seventeen original PCM-lease/recovery cases. They preserve
551 original files in 27 actual fixture roots through two final censuses and
all 5,986 source/launcher/reference pins. Owned processes have exited.

These execute Python codecs, real files, locks, WAV analysis and declared native
producer models. They do not execute the C++ ticket, Qt queue, native directory
gate, permission state or callback-thread matrix. Source review found and
corrected the final directory recheck and executable-only iOS build admission
before publication; neither correction is presented as a native runtime test.
Compilation, physical microphone identity, acoustic/peer measurements, complete
resource retirement and the whole Audio journey remain unqualified.

## Required origin in the existing PCM lease

The existing `ios.adapters.audio_pcm_runtime.lease` factory accepts the explicit
`profile='qt-source-read-to-preview-tap'`. It stores PCM lease version two with
that profile before allocation. The same original snapshot, native-clock join,
PCM chunks and fragment validator must then establish available version-two
callback provenance. A legacy packet, unavailable origin or fragment mismatch
cannot supply the required capture. Cleanup can still retire the original
allocation without claiming a captured result; uncertain allocation or release
is never sent again.

Default new leases retain literal version one. Default reopening of an existing
version-two lease preserves its original strict requirement. An explicit strict
request cannot reclassify an existing version-one allocation. Unknown profiles
refuse before runtime source acquisition, and changed requested profile fields
refuse before allocation. Chunk, snapshot, absence and public result grammars
remain unchanged. The required profile introduced lease version two; the
separate [normal Close cleanup](AUDIO_PCM_LEASE.md#normal-close-and-later-cycle-evidence-memory)
now adds readable cleanup-only version three. The native observer, limits and
deadlines of this required-profile path are unchanged.

All 25 selected component cases pass in 24.724 seconds: eight new required-profile
and recovery cases plus seventeen existing PCM cases, preserving 520 original
files in 24 roots. The connected fourteen-action recording/resume flow passes
with required origin in 112.218 seconds and with the unchanged default profile
in 111.544 seconds. Each preserves 131 original files in one root. All three
selections preserve 7,686 source/launcher/reference pins; owned processes and
new threads are gone. The test-only fixture import correction prevents duplicate
collection of the reused test classes.

These are real host ownership/byte/ordinary-action checks over declared native,
callback, SDK, OS and timer models. Later recording cycles create separately owned
evidence memory; the normal Close path now retires the latest owned cycle. Independent acoustic/peer artifacts, full settings restoration,
resource/process/SDK retirement, native compilation and the complete Audio
adapter remain open. No complete capability is enabled by this profile.
