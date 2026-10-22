# Separate Android Snapshot consumer fixture

This is a standalone debug-only lab APK (`org.overte.e2e.snapshotreceiver`),
not a product source set or manifest fragment. It has no shared user ID. Its
normal exported image ACTION_SEND Activity is labelled **Overte Snapshot
Evidence** in the system chooser. Selecting it exercises the real existing
Phone FileProvider/ClipData/URI grant path. It does not substitute an HTTP
request or a fabricated native export result.

Only the shell/lab DUMP credential can arm/read/control its separate provider.
It must be explicitly armed with run/arm nonces before normal chooser input.
No command accepts a URI, path, bytes, digest, native export ID or desired
result. One original incoming intent is admitted per armed fixture process;
rearming/restart adoption is forbidden. A subsequent run needs a separately
prepared fresh process **after** verified full prior retirement. An orphan
private evidence directory causes startup to fail closed.

The Activity obtains actual EXTRA_STREAM, matching ClipData, read flag,
provider package/UID, own PID/UID/component and real URI read permission. It
independently opens the original ContentResolver AssetFileDescriptor, consumes
the original stream through the shared private-file identity/hash component,
and records successful descriptor and stream close. The Activity finishes
only after this real I/O; onDestroy supplies the actual activity lifetime.
A chooser callback alone never appears as a consumption result.

The DUMP-protected provider exposes only these fixed routes:

- `content call --uri content://org.overte.e2e.snapshotreceiver.evidence --method arm --extra runId:s:RUN --extra armId:s:ARM`
- `content read --uri content://org.overte.e2e.snapshotreceiver.evidence/observations/RUN/FRESH_NONCE`
- `content read --uri content://org.overte.e2e.snapshotreceiver.evidence/originals/RUN/OWNED_COPY/FRESH_NONCE`
- `cancel`, `remove-copy` (with `copyId`) and `retire` calls, all with `runId`.

These are protocol descriptions, not installation or execution instructions.
Controls return ACK only. Observation and binary nonces are fresh and single
use. The process cannot supply old observations under a newly generated nonce.
Private originals have exact directory/inode/mode/link/byte/hash checks before
binary transfer and removal. Transfers have a real close watchdog and their
actual writer/deadline threads are retained through retirement. A new source
response has its own bounded transport pipe; the host requires full EOF and
then another original observation. A retained source/binary pipe prevents
later retirement. Permission checks remain fresh after file/worker retirement.

Compile locally using prepared SDK tools only (no Gradle dependency resolution):

```sh
python3 tests/device/fixture/android-snapshot-receiver/build.py \
  --sdk /path/to/existing/Android/Sdk --build-dir build/new-snapshot-receiver
```

The build directory must be new. The script runs actual API 34 `javac`, `d8`
and `aapt2`, emits an **unsigned, uninstalled** APK and a source/manifest/tool
script digest report. A prepared lab's signed APK needs its own actual APK
SHA pin. Build success proves neither Android execution nor UI/permission
behavior. No signing key, installation or device call is performed here.

`PhoneSnapshotConsumer` and `SnapshotConsumerTransport` implement the strict
host reader. The transport independently reads the installed APK's original
package path/digest, debug-app UID and PID/start ticks. The primary explicitly
arms the fixture. Both primary and separately credentialed read-only observer
must retain `consumer.binding()` (actual installed identity + source instance)
in their durable phase owner and pass it back as `binding=` after host reader
reconstruction. A changed fixture process cannot be silently adopted. The
adapter's `_snapshot_consumer(...)` requires a separate prepared APK SHA pin;
it never enables the complete Snapshot capability or installs a fixture.

`acquire(native_share_grants_row, actual_capture_file)` joins independently
received bytes to original native Share URI/component/UID and actual capture
bytes/SHA. It returns original metadata with source
`snapshot-receiver-original` plus the actual binary payload. The facade must
publish that payload in its private image/file owner, decode/compare it through
the existing Snapshot foundation and retain its artifact identity. The returned
bytes are not a desired image and the reader accepts no expected image input.

Retirement order is: observe original consumption; normally finish the receiver
Activity; issue native owner `revoke-share` once; independently require native
Share and receiver grant absence; remove only observed owned private copy IDs;
retire the receiver and readback file workers; acquire fresh receiver and OS
absence sources; retire the facade's private host artifacts/journal under its
existing closed-phase contract. A lost ACK must be resolved by fresh original
source. A retained permission, missing consumption, changed file, failed close,
pending worker, different UID, foreign URI or resurrected copy remains red.

Host tests execute actual Java file/stream/thread ownership with explicitly
synthetic Android URI/permission boundaries. API compilation/dex packaging is
real. No APK has been installed and no Android chooser, MediaStore, binder
permission or actual ContentProvider has been executed by these host checks.
