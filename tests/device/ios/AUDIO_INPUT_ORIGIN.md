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
