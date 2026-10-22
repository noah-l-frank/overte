# Original Emote controls and Pico input, version 2

The reviewed fixed Phone commit `abb7f6b60d97daf17752aadf94e2b5df099bb7ba`
provides the shared `TokenEmoteUI` and passive widget identities. The actual Pico
bootstrap loads that same unchanged `PhoneEmote.qml` through its separate
original Emote VM. No Phone touch/package/session transport is selected. Version
2 preserves strict version-1 readers and supports Pico's original canonical UUID
bridge/control identities; a consumed version cannot be downgraded. Common
whole-feature journey remains v16 and no full Emote capability is enabled.

## Normal input and independent effects

`PicoBoundAdapter._emote_controls(target,intent,receipt=None)` uses the existing
installed-candidate/PID/OpenXR-bound Script tablet source and `PicoNavigation`.
The owner must open and own the actual tablet first. Original Home paging and
EMOTE entry are ordinary controls; the normal retained chooser exposes page,
grid and ten actual Buttons. Cancel activates its original active button again;
Close uses the existing normal Home action. It never calls QML handlers or
`MyAvatar`, and never selects a direct Sit1/Sit2/Sit3 result.

Native discovery binds the real component context, lexical root/model, active
name, actual ten names, original highlighted Buttons and geometry. The unchanged
Pico QML has lexical `emoteGrid` but no `PhoneEmoteGrid` objectName; the source
reads the actual QML id rather than modifying the product. Tokens change with
actual active state, scroll state or geometry. Each native observation advances
`emoteSourceSequence`; projection preserves native capture clock and process.
Navigation row readiness derives only from its measured enabled/visible survey;
actual ownership is checked again at delivery. Captured source/counter/token
must remain the original reference through fresh admission.

Pointer input uses the existing original VR surface Move/Press/Release path.
Scroll enters the original `PointerEvent::Scroll` path through that surface,
with its actual sensitivity conversion and final hover release. A scoped passive
window event filter reports only that the original wheel reached Qt, because the
surface's aggregate mouse/touch/wheel acceptance can be false after wheel delivery.
It returns false and never consumes or modifies an event. This is delivery only:
`TokenEmoteUI` independently requires actual settled `contentY` movement before
continuing. Ignored scrolling fails after one input, without resending it.

The shared original hit-test now respects actual visual z, preserving insertion
order at equal z and refusing unknown/nonfinite stacking. Real Qt5 GridView's
later empty z0 focus item previously hid original z1 delegates from the test
hit-test. Ten actual pointer events now reach their exact original QML messages;
a foreign higher-z overlay still refuses input before a pointer is delivered.
No functional product layout or input handler is changed.

## Ownership, time and qualification

The owner saves each exact original intent before transport and its consumed
receipt afterward. Lost receipts remain unresolved for the whole-run journal;
this component does not authorize replay. A whole input recipe is bounded to
20 seconds, each transition to ten seconds and at most 102 captures. Source
birth, generation, command/source counters and clocks cannot regress. Missing
or foreign source, changed candidate/token, incomplete or expectation-bearing
rows and ignored effects fail closed. UI highlights/messages are never animation,
loaded FBX, advancing Rig pose, pixels, actor delivery or cleanup evidence.

The selected shared 13 widget tests and six actual Pico wrapper cases pass with
synthetic product boundaries. A focused real Qt5 test compiles the entire
original widget helper, actual input branch, geometry and extracted production
surface/pointer bodies. Surface hosting remains an explicit seam; this is not a
full native application or headset run. It verifies ten original button events,
two delivered original Scroll events, source-token geometry changes, hidden-page
refusal and foreign occlusion. In the shrunken hosted Qt5 window, measured
`contentY` remains unchanged after Down; this is explicitly an ignored-effect
counterexample, not scrolling qualification. The production default-height
window exposes all ten tested Buttons without scrolling. The whole adapter must
retain a failure if its actual target viewport needs an ignored scroll.

Whole-feature durable source/role composition, independent actor/stereo evidence,
actual timers/callback retirement, interruption and final cleanup remain open.
