# Original normal Chat controls v1

`NormalChatControls.h`, `NormalControlUi::Surface::Chat` and `TokenChatUI` add an
input component for the actual mobile `armored_chat.qml` page. Native code is
uncompiled. Its Python checks use synthetic widgets and real private intent
files, and qualify test logic only. Platform command/transport hooks, independently
read original storage/UI history, actual OS/VR keyboard observations, independent
peer stimuli/delivery, publisher and complete-run cleanup still need composition.
No complete `feature.chat.*` capability is enabled by these helpers.

## Source and input

The source is the original local/qrc `armored-chat/armored_chat.qml` context,
actual root/tablet mode, typed channel/keyboard request, original TextArea and
normal Send/BACK buttons. Local/Domain inputs resolve the actual original QML-id
MouseAreas; labels alone do not select those tabs. Unsupported original QML,
missing model aliases, ambiguous control IDs or private/nonfixture editor text
make acquisition unavailable, never a fabricated default page. Home/entry input
uses the existing original tablet control survey; the caller must qualify the
actual private profile, installed source/process and original Chat app ownership.

The normal native input surface recognizes only ordinary pointer activation,
focused IME replacement and focused Return. It never invokes a QML handler,
`toScript`, a message API, a setter or a fixture observer as an input shortcut.
Text admits only empty text and the existing closed run-scoped Chat inventory;
the Python owner additionally pins its exact run. Arbitrary messages/credentials
cannot enter the command or public observation contract.

Captured control tokens bind the original native widget, actual draft/channel/
focus/keyboard request, actual scene geometry and current input counter. Original tokens/elapsed time
are retained through fresh backend admission; an implementation must not replace
a captured reference with a newly observed widget. Old (>5-second), changed,
foreign-process, already-consumed or expired references fail. Existing native
counter/epoch/privacy/normal hit-test rules remain authoritative.

Before every actual input the caller's mandatory intent callback persists
control/action/source/generation/next-counter ownership, never text or a verdict.
The actual backend command must consume exactly that next counter on the same
native instance/PID. An ACK with an unchanged counter fails. After input, the
recipe separately waits up to ten seconds for the actual editor text/focus,
selected channel or removed original page. A consumed but ignored input fails
its effect check. An uncertain ACK is never replayed. The full feature still
needs independent history/peer effects; editor clearing proves only that local
input effect, never message acceptance/rendering/delivery.

## Snapshot and original model reads

The normalized input snapshot is exactly:

```
{chatControlsVersion:1, open:<boolean>, ready:<boolean>,
 scope:{instance,generation,sequence,elapsedMs,processId}, controls:[...]}
```

`open` means the containing normal tablet surface is available; presence of the
original `chat.page` row identifies an actual Chat page. It is not the normalized
full-feature `open` verdict. Scope is the existing normal-control source context;
`sequence` is the actual consumed input counter, not poll count. Closed/hidden
container snapshots cannot contain controls. No duplicate IDs/tokens, boolean
integer fields, unsupported versions or invented keyboard facts are accepted.

Every Chat row has actual `id`, opaque `token`, `enabled`, `focused` and
`inputReady`. `chat.input` additionally carries actual controlled `text`.
`chat.page` is noninteractive and additionally carries:
`profile:"armored-chat-native-v1"`, actual `channel:"local"|"domain"|"settings"`,
`keyboardRequested`, actual `localRowCount`/`domainRowCount` (0..1000) and
`componentSourceSha256`. The latter hashes the actual QML source **location**;
it is not installed executable/QML-byte association. The existing artifact/source
and actual process guards remain mandatory.

`keyboardRequested` is the original QML request. It is deliberately not named
`keyboard` and cannot establish actual Android/iOS/VR keyboard visibility or
world-input isolation. A full adapter must independently observe that UI and its
native input/lifecycle route. Likewise a page/root's disappearance does not by
itself establish keyboard/world-input cleanup.

The separate native `chatOriginalHistory(page,run)` helper reads the real
`localHistory`/`domainHistory` aliases as actual GUI-thread QAbstractItemModels,
using their original `text` roles, bounded row counts and original row order.
It returns actual controlled run text preserving multiplicity, plus total row
counts; it never copies a request into rows or retains other/private message
content. Missing/wrong models or roles fail. This helper is not yet a complete
private observation endpoint and cannot substitute for independently read
persistent `ArmoredChat-Messages`/settings when the page is closed.

The current full v9 closed-page `channel:local` normalization is not an actual
read of a destroyed QML property. A breaking source-contract correction should
represent the absent active channel explicitly and independently inspect actual
persisted history. Do not fill absent UI observations with checkpoint defaults.
Normal tab pointer focus/keyboard aftermath also must be measured on the actual
Qt/platform route, rather than inferred from the requested channel.

## Host checks and remaining work

Fifteen cases cover normal Unicode/channel/Send/BACK, actual Return input,
no invented receive rows, native-consumed-counter freshness, ignored effects,
original-context/draft/channel/focus/geometry changes, expired/replayed references,
foreign/private text, failed durable intent, uncertain Send ACK without replay,
PID/instance/clock regression, closed metadata/types, incomplete close and missing
sources. All pass on synthetic widget state with actual private files. They do
not execute the C++ controls, QML, native models, keyboard, product networking or
a device. Platform transport/source wrappers and full feature composition must
retain these rejection rules and remain closed until all required joins exist.
