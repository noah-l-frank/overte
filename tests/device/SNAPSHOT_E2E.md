# Native SNAP output journey

The `snapshot-output-parity` suite uses the existing controlled scene and normal
SNAP app. It captures a PNG still, JPEG still, still plus GIF, 360 panorama and
360 cubemap. It is implemented test logic; native adapters and physical-device
acceptance remain separate work. Each platform enables these actions only
through its explicitly configured owning input/file component.

The native adapter must implement and explicitly advertise:

- `snapshot.open`: open the ordinary SNAP app. Save the initial capture-format
  selection once per module so cleanup can restore it.
- `snapshot.capture`: select the requested mode and format, enter the bounded
  owned name, and activate `snapshotCapture`. Return after native input delivery;
  do not call a capture API, inject a bridge message or return a success verdict.
- `snapshot.files`: observe original files in the actual app snapshot directory,
  restricted to the supplied run prefix. Copy their original bytes into bounded
  private run artifacts, preserving the original basename separately. Reuse
  content-addressed copies instead of accumulating repeated large transfers.
  A fresh native app may not have created `Snapshots` before its first capture;
  that absence inside the verified ordinary app-data parent is an empty list.
  Permission/transport failures, aliases or incomplete result frames are errors.
  Never generate, re-encode or substitute an image.
- `snapshot.close`: cancel any owned outstanding capture, close the owned SNAP
  surface through normal controls and restore the saved capture-format selection.
  Cleanup must work after partial entry or capture failures too.

All UI actions confirm delivery with only `performed: true`. File observations
contain only a bounded list of `{basename, artifact}` pairs; the shared module
owns every assertion. Original private sandbox paths must remain private.

Each case uses an unpredictable run name that fits `snapshotName`'s 48-character
limit. Existing matching files fail the precondition. A bounded poll waits for
the actual complete output set; in-progress encodes may settle. Every original
basename must carry the requested name and a capture ticket. The still and GIF
must carry the same ticket. A stale file, missing GIF or acknowledged tap without
files cannot satisfy the journey.

An empty native reservation remains visible to the pre-capture freshness check.
After capture, its empty original bytes reach the decoder and remain pending
within the bounded poll. They must not become a transport infrastructure failure
or a completed image. Unsafe paths, aliases and oversized artifacts still fail.

The independent decoder checks actual PNG/JPEG/GIF encoding, complete frames,
checksums/end markers, frame timing and nonuniform output from the controlled
scene. Panorama must be 8192x4096; cubemap must be the actual 8192x6144 cross
produced by `interface/src/ui/Snapshot.cpp`. GIF must decode at least two frames
and at least one second of encoded duration. A static controlled scene may
produce identical frames; those conditions do not claim visual motion.

Files, hashes, per-frame decoded RGB hashes, polling and process/foreground
continuity stay bound to the ordinary runner artifacts. Source, built-artifact
and installed-code verification remain required. This journey does not qualify
projection orientation, scene fidelity, cancellation/owner replacement, uploads
or system save/share. Those still require their own normal-UI observations.

## Local input and original-file components

The optional iOS native producer uses the closed `snapshot-files` command
channel. `list` accepts only the owned capture prefix; `read` additionally
accepts an original basename, its native metadata revision and an integer
offset. Reads return at most64KiB. No command accepts a root, output bytes,
capture instruction or success verdict. The native producer must resolve the
actual application Snapshot storage, reject aliases and nonregular/hard-linked
files, and bound its original file count and sizes. Native request receipts
must retain the command nonce, actual process and freshness. The consumer must
join the original content hash, all chunks and a fresh final manifest before
publishing a private artifact. This shared channel alone implements neither
the native producer nor an installed-code association.

The actual review exposes stable `snapshotMode.option.<mode>` and
`snapshotFormat.option.<format>` controls. Tests click the real Qt popup
delegates rather than assigning their selection properties. User mode selection
persists the existing GIF preference; initial settings do not echo a preference
write. Each popup exposes its actual selected radio state, independent of the
translated caption. Input waits for initial settings, supplied both after AppUi
wires the native bridge and in response to the deferred ready request. A late
initialization cannot overwrite a choice the user already made. Both Qt5 and
Qt6 run the original review and selected export backend, including these pointer
and initialization regressions.

`adapters/android_snapshot_files.py` reads only the native private
`files/Snapshots` directory through the original ADB transport. The owning
Phone/Pico adapter must still supply its independently verified installed
candidate/process context and restrict access to its current owned run prefix.
File I/O alone does not advertise Snapshot actions or qualify a capture.

The Android-side scripts reject aliases/hardlinks and bound file count and bytes.
Explicit response framing is required because
[ADB exec-out returns after copying its stream](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/platform-tools-34.0.0/client/commandline.cpp),
without returning the remote script's exit status. An empty success and a failed
list therefore cannot be conflated. Binary framing, actual OS size/SHA256 and
fresh continuity checks reject truncation, replacement and application changes.
Still/GIF companions can arrive separately; an empty reservation may complete
during the bounded read. Content-addressed private artifacts retain the exact
observed bytes and never overwrite unrelated output. The independent image
decoder remains responsible for every output assertion.

Host file tests execute the actual scripts and original ADB transport against
ordinary temporary files with only the SDK/device boundary replaced. They also
model exec-out's success exit for failed remote scripts. Full native
Phone/Pico/iOS operation dispatch, source-specific input bindings, installed
iOS code association and device acceptance remain separate pending work.
