# Original Chat control component

The explicit native UI component adapter now exposes
`_chat_controls(selector,intent,run)` through `IOSChatIO` and the shared
`TokenChatUI`. The canonical installed-candidate adapter still refuses this
factory before I/O with `OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`; native UI
component mode is not device/product acceptance.

The existing native Qt survey identifies the original Chat context, TextArea,
Local/Domain MouseAreas and Send/BACK buttons. It emits `chatControlsVersion:1`
and the actual `chatGeneration`. NativeInput validates original frames, source/
PID/epoch/counters, then retains the complete captured draft/channel/focus/token
reference through fresh admission. The same native edit sequence drives ordinary
pointer, focused IME replacement and Return; no duplicate UIKit widget or direct
message/QML-handler route is created. Source tokens also bind actual geometry.
QML `keyboardRequested` remains a request, not measured UIKit keyboard visibility.

Six component cases pass against synthetic Qt state over the original private
HTTP/AFC path. They cover Unicode Send/Return and consumed counters, ignored
effects, stale draft and late geometry, absent/invalid metadata and frames,
fictional keyboard facts, failed intent, incomplete close, process replacement
and canonical refusal before I/O. The permitted iOS host selection passes 312
checks before the view component; five canonical binding-entry checks also pass. Twenty explicitly reviewed
native/compiler-dependent cases are excluded from that selection. No compiler,
IPA/client execution, device, installation or Jenkins job was used. Native
C++/ObjC++ remains source-reviewed and uncompiled.

The passive `_chat_view(selector)` component now reads original UI/model/live
settings source v1 over the original private AFC path. Three additional wrapper
counterexamples exercise original inventories/native epochs, ignored/foreign
observations, lost sessions and explicit canonical refusal before I/O. The source
is documented [with its exact handoff](../native/CHAT_VIEW_OBSERVATION.md). Common
journey v10 corrects the closed-page channel to `none`. The permitted iOS host
selection now passes **315** cases with no failures, skips or compiler attempts.

Actual keyboard/input-route qualification, independent peer stimuli/receipts/
publisher and whole-run ownership/cleanup remain required. The input component never
advertises complete `feature.chat.*` operations or substitutes editor clearing
for acceptance/rendering/delivery. See
[the shared native control contract](../native/NORMAL_CHAT_CONTROLS.md).
