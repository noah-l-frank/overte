# Troubleshoot the Pico 4 port

Start with:

```bash
cd android/vr/pico
./build.sh doctor
```

Use the phase-specific guidance in
[`android/vr/pico/docs/BUILD.md`](../../../android/vr/pico/docs/BUILD.md#troubleshooting).

- For missing or rejected source inputs, check the four explicit environment
  values, exact checkout revision, binding digest, and completed graph receipts
  in [SOURCE_INPUTS.md](../../../android/vr/pico/release/SOURCE_INPUTS.md).
  Downloading the legacy bundle does not repair this contract.
- For Gradle failures, use `./build.sh build --stacktrace`.
- For `unauthorized` ADB state, unlock the headset and accept the USB debugging
  prompt.
- With multiple devices, set `ANDROID_SERIAL`; do not rely on ADB's implicit
  target selection.
- Keep raw Logcat, screenshots, device identifiers, and account-related output
  private and temporary.
