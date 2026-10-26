# Android tablet and keyboard alignment (#867)

The requested visual result is equal visible horizontal margins while retaining
cutout protection. Merely filling an asymmetric safe rectangle leaves the panel
visibly right of the physical screen center.

## Identified baseline (2026-10-26)

Proxmox Jenkins job `overte-phone-867-geometry`, builds #1–5, observed a physical
Pixel 6a running Android 17 / API 37 in 2400 × 1080 landscape at 420 dpi. The
installed APK was independently hashed through the actual agent:

- Source: `7698d80e9899d59c4a2c65d6f108cb8aa98c1515`.
- APK SHA-256: `0a924c3e3ea0dacb321399acd51038a0a7a4a5d1fec5107580eeefe6cbe8dbe3`.
- Android display cutout: left 132 px; right 0 px.
- Application window: `[0,0]–[2400,1080]`.
- Rendered Tablet home panel: x=132 through x=2400, center=1266.
- Native Gboard `INPUT_METHOD` window: `[132,0]–[2400,1080]`.
- Physical screen center: x=1200.

Build #5 repeated three Tablet open, Places search focus, native IME show/hide,
and Tablet close cycles. All three rendered home panels retained x=132..2400.
The same one-sided gap was visible in Gboard. The keyboard was the standard
native docked Gboard UI, not the app's QML keyboard; no keyboard preference or
app-data reset was used.

The normal accessibility tree in this candidate could retain the Tablet home
nodes after navigating to Places. Those stale node rectangles were not used as
proof of the post-navigation or keyboard geometry. WindowManager frames and
actual screenshots provide that evidence instead.

[Tablet before the change](android-pixel6a-tablet-before.png) ·
[Native Gboard on the baseline](android-pixel6a-native-keyboard.png)

## Cause and targeted change

Both symptoms share an asymmetric display cutout. They have separate layout
owners. The Overte presenter used the measured left/right safe insets directly
as panel margins and filled the remaining width. Android independently placed
the native IME window in its cutout-safe rectangle.

The investigated path is Android decor/window measurements → Java metrics
normalization → JNI → native runtime metrics → Phone profile → C++ initial
presenter size and QML `TabletSurfaceGeometry`/`WindowRoot` realignment. The
observed outer panel coordinates are physical pixels. Density and the rounded
content scale affect the inner page, not the outer panel origin. No additional
horizontal offset, double application of the cutout, or logical/physical-pixel
conversion error was established on this candidate. Bottom protection remains
`max(safeBottom, imeBottom)`, not the sum of both insets.

The shared opt-in `centerScreenSpaceHorizontally` policy reserves
`max(safeLeft, safeRight)` at both horizontal edges. Phone enables it; other
profiles retain their existing default. Measured platform insets are preserved.
For this display the expected Tablet interval is x=132..2268, centered at 1200.
If no centered safe rectangle fits, the actual cutout-safe rectangle is retained
rather than weakening protection. Hosts whose origin is already at the safe
area subtract that already-applied origin once.

## Verification and remaining limits

Production QML geometry and WindowRoot tests cover left/right/asymmetric
cutouts, compact and portrait sizes, native safe-area origins, density/content
scaling, repeated reopen and IME transitions. A native Qt fixture executes the
actual C++ presenter resize method with service boundaries substituted,
including startup fallback measurements and stale caller dimensions. The new
QML and native regressions reject the old production implementation and pass
with the change. These host tests do not establish physical-device acceptance.

The fixed candidate was built successfully and passes the Phone APK gate
(signature, package identity and 16 KB native page alignment):

- Source: `af952f1e047e89cf3e57eaaf1af8a6b966e71466` (the identified baseline plus the focused fix).
- APK: `0.1.25-af952f1e04`, version code 25.
- SHA-256: `24a91c50829be4100aec76a73b5a03d4c49a6e62202437f3fd069812f2ae3b8a`.
- Source archive SHA-256: `65b6202d7aae2fb13cd07738e6e2d8b7c6f7de830270344b8d121afd74a647fb`.

Installation job `overte-phone-867-install` #2 independently verified the old
installed bytes, matching old/new signing certificates, version code 23 → 25,
and the final installed APK hash. It used an in-place update with no app-data
reset, no settings writes and no downgrade flag. Job #1 was rejected for a
pipeline syntax error before any agent/device step.

Device job `overte-phone-867-geometry` #7 passed three complete Tablet open,
Places search focus, native IME show/hide and Tablet close cycles on the same
identified Pixel 6a. Pixel measurements of each rendered home panel gave:

| Candidate | Panel x interval | Left margin | Right margin | Center |
| --- | --- | --- | --- | --- |
| Baseline, all three cycles | 132..2400 | 132 px | 0 px | 1266 |
| Fixed, all three cycles | 132..2268 | 132 px | 132 px | 1200 |

Android reported the native IME shown and then hidden in each cycle. Its own
window remained x=132..2400 in all three shown states. This is a Tablet PASS
and a retained native-keyboard limitation, not full acceptance of #867.

[Tablet after the change](android-pixel6a-tablet-after.png) ·
[Tablet with native IME after the change](android-pixel6a-tablet-ime-after.png) ·
[Candidate-bound test record and screenshot hashes](android-pixel6a-centered-tablet-test.json)

The reduced viewport reflows the launcher from six to five columns on this
candidate. Run #6 used an old launcher tap coordinate, remained on Tablet Home
and correctly failed `IME_NOT_OBSERVED`; it provides no IME PASS. Its screenshots
were retained and inspected before the test coordinate was corrected for #7.
The launcher sizing policy itself is unchanged.

The tested v25 APK remains installed. The general Pixel feature job was not
repinned as a side effect: its v23 artifact binding must be requalified before
using it with the new installation. The dedicated #867 job used the explicit
v25 revision and APK hash above.

Native Gboard remains an open part of #867. Overte does not own its window
layout parameters. Android's [window layout implementation](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/view/WindowLayout.java)
applies cutout protection to IME windows independently, and the normal app IME
interface does not expose a horizontal window-position setter. Changing the
Tablet rectangle does not imply a Gboard fix. No system or Gboard setting was
changed to conceal that limit.

The original Pixel 8 Pro screenshot and candidate identity remain preserved in
[issue #867](https://github.com/noah-l-frank/overte/issues/867) and
[android-tablet-right-offset.png](android-tablet-right-offset.png). The requested
iOS/iPadOS physical-device follow-up remains unverified. The new Pixel 6a
results do not establish behavior on the historical Pixel 8 Pro candidate or
other screen sizes, and do not replace the recorded stability observation.
