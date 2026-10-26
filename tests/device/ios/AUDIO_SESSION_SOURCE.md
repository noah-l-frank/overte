# Passive iOS Audio session and OS authorization originals

`feature-ios-audio-session` is a read-only native source with an exact nonce,
run, process, instance, sequence, lifecycle and native UTC/monotonic bracket.
The installed foreground factory joins its AFC original to actual native clock
reads. Host file time is never used as the permission sample time. This source
does not activate the complete Audio capability.

The native seam reads the existing AVAudioSession permission getter directly.
It preserves that actual OS enum separately from the Audio adapter's cached
gate permission/outcome, foreground/interruption flags, capture/playback flags
and output revision. The OS and cached gate can disagree during transitions;
neither field overwrites the other. The pure definite-permission projection
accepts only actual OS Granted/Denied with an available adapter. Unknown,
Revoked or unavailable results do not become permission denial or a grant.
An OS grant alone supplies no active capture, buffers or audible output.

Calling `microphonePermissionGranted()` would refresh permission and could apply
the session; calling the old voice-test status route touches its watchdog.
This source calls neither. It cannot request permission, change mute, activate,
deactivate, prepare a voice test, clear a buffer or alter a product gate. Its
new interface/implementation seam exists only under `OVERTE_E2E_VOICE_TESTS`.
The exposed method additionally requires `OVERTE_E2E_FEATURE_TESTS`, iOS and
the dedicated iOS E2E configuration, plus an active explicit test-script launch.
Non-test configurations cannot write this source file. The dedicated writer
uses compact atomic replacement; the probe consumes each original nonce once.

The strict Python codec reuses the existing original-source reader and its
1.5-second acquisition bound. It rejects PID/instance/nonce/sequence changes,
clock rollback, late originals, output-revision rollback, Boolean enum aliases
and private extra fields. The source factory retains the existing installed
candidate and foreground guard, creating no SDK session or launch. A returned
original does not independently attest installed execution; that remains the
factory's candidate binding. Pure projections retain historical meaning and
cannot claim a new current permission reading.

Ten focused host cases pass through the actual Python codec, fixture command
validator, JavaScript probe and HTTP/AFC runtime paths. They cover definite OS
permission against a contrary cached gate, unknown/revoked/unavailable sources,
stale/foreign input, missing getter and once-only nonce handling. The combined
keyboard, world and pending-command compatibility selection also passes. Native
Audio/OS/candidate producers are explicit models. The new C++/Objective-C++ is
uncompiled; no native, build, device or permission-dialog qualification follows.

Still compose these originals with durable recording authorization ownership,
ordinary Settings denial/recovery across actual process replacement, independent
Actor/acoustic evidence and complete Audio lifetime/quiet/SDK retirement. The
source is an observation component, not that complete protocol.
