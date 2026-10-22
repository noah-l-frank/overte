# Original normal Chat controls v2

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
MouseAreas; labels alone do not select those tabs. Version 2 also resolves the
original `settings_page` MouseArea and its actual normal **Erase** button in the
same qualified original QML page. Unsupported original QML,
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
{chatControlsVersion:2, open:<boolean>, ready:<boolean>,
 scope:{instance,generation,sequence,elapsedMs,processId}, controls:[...]}
```

`open` means the containing normal tablet surface is available; presence of the
original `chat.page` row identifies an actual Chat page. It is not the normalized
full-feature `open` verdict. Scope is the existing normal-control source context;
`sequence` is the actual consumed input counter, not poll count. Closed/hidden
container snapshots cannot contain controls. No duplicate IDs/tokens, boolean
integer fields, unsupported versions or invented keyboard facts are accepted.
The shared Python/Pico readers retain explicit v1 input compatibility and refuse
new Settings/Erase controls relabeled as v1; v2 cannot downgrade in one reader.
The generic native and Pico producers now emit v2. Frozen Phone/iOS component
wrappers must adopt their corresponding v2 producer reader explicitly before
selecting this new native packet; no complete Chat capability exists there.

Every Chat row has actual `id`, opaque `token`, `enabled`, `focused` and
`inputReady`. `chat.input` additionally carries actual controlled `text`.
`chat.erase` additionally carries `historySha256`, computed from all original
Local and Domain model rows, their original order/multiplicity and channel.
It hashes the bounded original QDataStream representation and never exports
private row text. Missing roles/models, non-string/oversized values and a
serialized inventory above 256 KiB refuse the source. The native control token
retains that digest, so even a same-count history replacement cannot retarget
an admitted Erase click.
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
content. Missing/wrong models or roles fail. The separate
[Chat view observation](CHAT_VIEW_OBSERVATION.md) endpoint exposes these models
and independently reads live `ArmoredChat-Messages`/settings with the page closed.
Neither source is a complete adapter or a peer delivery proof.

Historical v9 closed-page `channel:local` normalization was not an actual read
of a destroyed QML property. Full journey v10 now represents absent active channel
as `none` and requires independent history. Do not fill absent UI observations
with checkpoint defaults.
Normal tab pointer focus/keyboard aftermath also must be measured on the actual
Qt/platform route, rather than inferred from the requested channel.

## Host checks and remaining work

`TokenChatUI.erase_history(authorize)` selects Settings normally and requires
the whole owner's independent authority on the exact original Erase snapshot.
`authorize_erase` supplies the pure original-source join: a separately acquired
fresh v2 Chat view must match the exact frozen model digest, process, Settings
page, both model counts and ordered stored histories. It requires no unowned
rows, unchanged original configuration, draft, focus or measured keyboard.
Older passive v2 views without the additive digest cannot authorize this input.
The caller must use its admitted original reader and retained original config;
this helper does not acquire sources or supply the missing whole-run owner.
The ordinary generic `input` method refuses Erase. The captured snapshot remains
unchanged through post-authority/backend admission; changed history, scope or
digest fails instead of being recaptured. Erase is issued at most once per UI
owner, and its ordinary persisted input intent survives a lost result. An input
ACK or zero model rows does not prove actual stored/closure history restoration:
the complete owner must separately read original storage, ordinarily close and
reopen Chat, prove empty reconstructed history, restore exact original setting
presence/value and verify the actual pending writer/resource/quiet window.

Eight new no-build counterexamples cover the normal Settings/Erase recipe,
independent refusal, same-count foreign replacement, changed backend admission,
ignored effects, lost result without replay, private draft/old producer and
closed metadata. One separate focused Qt5 compiler check executes the original
digest body against actual QAbstractListModels, with page/model association as
an explicit seam. It checks actual order/multiplicity/channel/replacement,
roles/types and byte bounds. This compiles that helper only; the native app,
actual QML input, settings writer and devices remain unqualified.

Fifteen cases cover normal Unicode/channel/Send/BACK, actual Return input,
no invented receive rows, native-consumed-counter freshness, ignored effects,
original-context/draft/channel/focus/geometry changes, expired/replayed references,
foreign/private text, failed durable intent, uncertain Send ACK without replay,
PID/instance/clock regression, closed metadata/types, incomplete close and missing
sources. All pass on synthetic widget state with actual private files. They do
not execute the C++ controls, QML, native models, keyboard, product networking or
a device. Platform transport/source wrappers and full feature composition must
retain these rejection rules and remain closed until all required joins exist.
