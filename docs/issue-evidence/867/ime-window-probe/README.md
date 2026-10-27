# Retained-Gboard investigation for #867

The owner explicitly chose to retain Gboard on 2026-10-26. An app-internal
replacement keyboard is therefore outside the chosen solution. The requested
centering remains unresolved; these experiments do not constitute a keyboard
fix or full acceptance of #867.

## Actual device evidence

All hardware execution used the Proxmox Jenkins wrapper and the existing Pixel
6a device lock. The exact Overte v25 APK stayed installed throughout:
`24a91c50829be4100aec76a73b5a03d4c49a6e62202437f3fd069812f2ae3b8a`.
The separate probe APK was installed only for each experiment and removed
again, without resetting Overte data or writing system/IME settings. Gboard
remained the selected IME before and after every run.

- Device baseline: Pixel 6a, Android 17 / API 37, 2400 × 1080 landscape.
- Gboard: `18.4.4.985164140-release-arm64-v8a`, version code `176027246`.
- Docked-mode probe APK SHA-256:
  `66ab903e1e366e284be1114cd6c1b420bf3f270ec9a604d6a0099828abb8e7e9`.
- Jenkins job: `overte-phone-867-ime-window-probe`.
- Build #2 exercised all six variants with extraction and fullscreen IME modes
  explicitly disabled, matching the normal Overte keyboard mode.

The cutout was on the right in this experiment, so the native keyboard's gap
was also on the right. This differs from the earlier left-cutout Overte
baseline, where the native gap was on the left.

| Public API experiment | App window x interval | Gboard window x interval |
| --- | --- | --- |
| Edge-to-edge, cutout short edges | 0..2400 | 0..2268 |
| Decor fits system windows | 0..2400 | 0..2268 |
| App requests cutout mode NEVER | 0..2400 | 0..2268 |
| Centered app window, width 2136 | 132..2268 | 0..2268 |
| Centered floating app dialog | 132..2268 | 0..2268 |
| App requests horizontal IME animation insets | 0..2400 | 0..2268 |

In particular, an app centered at x=1200 did not center Gboard: its native
window remained centered at x=1134. The [actual screenshot](centered-app-native-gboard.png)
shows the independent borders. [Structured observations](results.json) retain
the artifact identity, window frames, normal IME state and cleanup evidence.
Jenkins SUCCESS means the experiment and cleanup completed; none of the six
variants fixed native keyboard centering.

Build #5 captured an animation callback from the current probe process only.
The request was 132px on each horizontal side, while the observed current and
fully shown insets remained left=0, right=0, bottom=686. This is consistent with
the documented [animation API bounds](https://developer.android.com/reference/android/view/WindowInsetsAnimationController#setInsetsAndAlpha(android.graphics.Insets,%20float,%20float)):
requested values are restricted to the hidden/shown range. They are not a
free horizontal window-placement interface.

Build #1 used fullscreen extraction, so it was followed by the normal docked
comparison. Build #3 collected an unscoped log tail; that sample is not treated
as fresh callback proof. Build #4 failed during process-start observation;
its result is not geometry evidence. Build #5 waited for the actual process
and filtered logs to that process before recording its callback.

## Result and boundary

No supported Overte-side positioning route was established with Gboard
retained. The app window and IME window have separate layout parameters;
changing Overte's safe rectangle or Android app cutout flag does not change
Gboard's rectangle. Android's input-method/window layout policy and Gboard's
own UI remain responsible for native centering. A provider/platform fix or a
documented per-app IME centering capability is needed to satisfy the remaining
requirement without replacing Gboard or changing the user's keyboard settings.
This result is scoped to the identified versions and the tested APIs.

## Rebuilding the standalone probe

`ProbeActivity.java` and `AndroidManifest.xml` are the actual docked-probe
sources; their byte hashes match the producer record. The device-free builder
requires Android platform 36, build-tools 36.0.0 and a JDK:

```text
python3 build-probe.py --sdk /path/to/android-sdk --output /new/private/build-directory
```

It creates an isolated signing key and APK; the output directory must be new.
Rebuilt APK signatures and hashes will differ because a fresh probe key is
created. This script performs no device access. Execute hardware experiments
only through the reviewed Proxmox Jenkins job and `overte-jenkins`; do not run
this probe through workstation device automation.
