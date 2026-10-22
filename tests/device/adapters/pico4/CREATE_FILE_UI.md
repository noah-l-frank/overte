# Original Pico Create Import and Save controls v1

This source component binds the real `NativeFileBrowser.qml` Import and Save
dialogs to the existing Pico native pointer/IME route. Feature 4/14 remains
partial. The full feature coordinator, independent domain/peer/stereo effects,
native Script/ModalDialog callback joins, model/texture/PolyVox and rez recovery
are still unfinished. No complete Create capability is advertised.

The Pico NavigationUi adds the explicit `createFileControlsVersion: 1`,
`createUiInventory` and distinct `create-file.page`, `.folder`, `.name`,
`.accept`, `.cancel` controls. It identifies only original local/qrc
`dialogs/NativeFileBrowser.qml` roots, with the actual `Select .json to Import`
or `Select Where to Save` caption, `*.json` filter, single-file mode and matching
Save flag. Script bundle roots keep their original separate admission.
An unknown browser matching the Create captions makes the inventory incomplete;
it cannot establish empty resources or grant input.

The bounded native inventory weakly tracks actual Create editor/browser roots
through visibility, detachment and QObject destruction. Its original instance,
monotonic sequence, random root IDs and retired IDs are independent of input
acknowledgements. A retained hidden root remains a live resource. A live root
whose component/profile changes becomes unavailable, including after detachment.
Histories are bounded to sixteen live roots and 256 retired identities, with no
eviction that could qualify false cleanup. No JS callback retirement is inferred
from a missing view; native callback sources must still join the whole feature.

Control tokens include the original browser identity, role, folder, closing and
system-document request state. Normal pointer activation and the existing
`replaceFocusedField`/`submitFocusedField` provide all input; no field setter,
`accept`/`finish` invocation, selected-file signal injection or Clipboard call
is used. Native admission checks the original hit target and focus. Replacement
is restricted to the actual private `feature-create-RUN-TICKET` namespace, its
`entity-import.json` input and distinct `export.json` destination. It cannot
navigate to arbitrary Script roots, foreign paths or parent traversal.

The Python recipe starts with the separately captured pre-input native
inventory with one actual original visible Create editor. A pre-existing, retired, reused or replacement picker cannot be
adopted. Its root must be the sole new original with the correct role, current
tree and visibility. It fills the full original storage path through normal IME
input, reads back the actual field and uses the ordinary Select/Save or Cancel
button. The owner callback receives the original reference before every input;
the future coordinator must persist it. An uncertain call is retained and
cannot be reissued by that recipe. Only an ordinary Cancel for another pending
input may recover; an uncertain Cancel is never repeated.

Retirement requires actual original root destruction and a full three seconds
of fresh complete native inventories. Hidden/closing roots, frozen queries,
missing retired identity or unexpected additional roots cannot pass. The
recipe establishes dialog input and original Qt lifetime only. A selected URL
does not establish an imported domain Model or exported file: those effects
must be read separately through the full feature/domain observers and
[original file source](CREATE_FILES_SOURCE.md).

The existing private `_create_file_controls` factory preserves candidate,
PID/start, OpenXR nonce and original UI-source guards. It performs no automatic
entry, staging, source load or resource retirement. Public full-feature routing
remains disabled until the complete coordinator exists.

Nine bound Pico Python counterexamples verify actual wrapper serialization,
original references, distinct role paths, ignored input, incomplete/frozen
source, retained closing roots, failed intent and no-resend behavior using substituted
native effects. The separate Qt5 harness compiles the original browser QML,
real FileDialogHelper and NativeFieldInput, plus the original extracted Create
input branch and geometry admission. It verifies real normal Import/Save paths,
Cancel, hidden and detached roots, actual selected-file signals and QObject
destruction. Keyboard-platform presentation is stubbed for that isolated host
test, and no actual Clipboard export, domain entity or device is claimed.

Pico's catalog adds `create-file-ui` (pure Python), `create-file-native-ui`
(isolated Qt) and `create-original-files` (isolated Qt Core). The local risk
inventory has 56 cases after the separate callback-source continuation; all
three picker/storage cases map to `tablet-and-create-ui`. These are
test cases, not completed feature areas. Select them explicitly rather than
running unrelated full catalogs. The complete application, OpenXR rendering and
physical Pico qualification remain unverified.
