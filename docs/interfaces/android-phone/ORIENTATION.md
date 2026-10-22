# Android Phone orientation contract

The current `PermissionsActivity` and `PhoneInterfaceActivity` request
`android:screenOrientation="landscape"` in
[AndroidManifest.xml](../../../android/phone/apps/phoneInterface/src/main/AndroidManifest.xml).
This is the source contract reviewed on October 20, 2026; the earlier
`fullSensor` description is obsolete.

| Classification | Current contract |
| --- | --- |
| Supported | Normal full-screen landscape is the declared Phone layout. Verify safe insets, reachable controls, and keyboard behavior on the selected candidate. |
| Not yet qualified | Reverse-landscape behavior, vendor overrides, rotation transitions, cutouts, and IME behavior need their own current-device evidence. |
| Unsupported / no claim | Portrait and reverse portrait are not declared supported modes by these Activities. Foldable, freeform, split-screen, and non-phone layouts have no general production claim. |

Android defines `landscape` separately from `sensorLandscape` and `fullSensor`;
windowing/device policy can also affect how a request is applied. See the
[Android activity orientation reference](https://developer.android.com/guide/topics/manifest/activity-element#screen).
Responsive QML or an emulator result does not by itself establish a different
orientation contract or physical-device acceptance. A future orientation change
must update the manifest, documentation, checker, and relevant runtime evidence
together.
