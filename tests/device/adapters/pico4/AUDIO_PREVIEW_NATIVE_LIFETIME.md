# Original native Audio preview lifetime

The dedicated feature build and actual test-script runtime instrument the
existing `AudioClient::startRecordedVoiceTest` cleanup functor. Its original
`QTimer::singleShot(30000, this, ...)` remains unchanged in duration, target and
product action. The passive registry records its actual registration/cycle,
actual callback entry/completion, and final destruction of the captured Qt
lease. It never infers retirement from requested time, receiver destruction or
private PCM release. No external command can create or retire these originals.

Each actual native receiver and callback has an immutable weak identity. The
registry keeps at most 64 originals, accepts only its actual owner thread, and
fails unavailable on replacement, source-clock regression or incomplete history.
An active callback cannot be mistaken for a retired functor. The lease lives
with the original Qt capture, rather than with the registry; final capture
release is the recorded retirement event. A dead original AudioClient remains
unavailable to the existing weak reader instead of becoming a new client.

`AudioClient::featureRecordedVoiceLifetime()` independently reads the original
preview polling timer's construction identity, weak liveness and actual active
state, loopback pending byte size/capacity and assigned-device pointer, original
recorded-buffer byte size/capacity, and private tap-state emptiness. The timer ID
and construction timestamp come from the actual `new QTimer` point. A broken
raw/weak timer association is unavailable. Cleared buffer size is not allocated
capacity retirement. These queries initialize no audio device, set no property,
start/stop no timer and delete no product or Qt object.

The host contract compiles entire original AudioClient preview/callback/getter
bodies with real Qt Core, the original recorded-preview observer and processor,
and explicit format/input/output/reverb seams. It executes the actual original
30-second cleanup timer naturally, proves that PCM release leaves the callback
pending, and waits for actual invocation and capture retirement. It also observes
real preview polling-timer construction/start/stop, a broken partial timer
association, and actual cancellation/destruction of a separate Qt context.
The latter can leave its functor retained until Qt's later cleanup; the test
waits for the original lease rather than deleting an internal Qt timer. No audio
engine or device runs. This check is part of `audio-settings-source`.

This native API is preparation for the Pico source/owner cleanup join. The
normal page segment still reports partial Audio qualification and retains all
journals, Qt contexts and process scopes. Full qualification also needs the
independent acoustic/peer recipe and original process/resource closure. Native
polling timers and reusable recording-buffer allocations can remain retained;
no size-only or callback-only result retires those scopes.

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=<existing-qt5-root> \
python3 tests/device/contracts/audio/test_recorded_preview_lifetime.py
```
