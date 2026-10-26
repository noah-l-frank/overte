# Ordinary Assets baking and model-import controls

Feature 13 remains closed, source count 5/14. This source packet connects the
existing ordinary baking checkbox, Add to World, Add uploaded model and model
dialog controls. It does not establish native oven output, model/resource
loading, renderer visibility or independent peer publication. Native C++ is
uncompiled; no device, server, oven or compiler was run.

The canonical QML now exposes passive exact pointers behind its existing
default-off E2E observation getter. Existing controls received IDs; their
handlers, enabled/checked bindings, defaults and product behavior are unchanged.
The source reads actual tree/model/selection context, checkbox state, original
dialog/editor/shape/dynamic state and actual prefilled model URL/position/name.
Visible popup input requires the same actual scene window and standard-button
pointers. Hidden properties are read without inventing a visible popup.

`IOSAssetUsageControls` binds the actual `EntityScriptingInterface` object from
the canonical QML context to the existing singleton. Its native canWriteAssets,
canRez and canRezTmp getters plus actual Node session/domain UUIDs are retained
separately from QML's cached permission and real UI-enabled values. A stale UI
flag stays visible as a distinct fact; the test transport adds no permission
policy and never repairs a product binding. Normal negative handlers still
perform their own existing writable/rez checks.

Control metadata 4 is separate from literal readable metadata 1, 2 and 3. The
additional Usage inventory is version 1 and joins the same original weak-root
and full tree inventories. Native source identity, timestamps, process, current
selection and all control metadata must agree. Its source hash binds actual
effective rights, checked state, model URL, shape and dynamic settings, so an
external edit or permission transition invalidates a previously captured token.
Unavailable new hooks expose no empty metadata-4 control rows; old source rows
remain readable while the new source stays explicitly unavailable.

Input uses ordinary existing rendered controls and standard dialog buttons,
never a direct handler call or property setter in the product. Every new input
requires a durable pre-transport intent. The model URL is observed and can be
focused; this packet does not enable replacing it with an arbitrary URL or
introduce a new index setter. The original Add to World handler supplies the
selected URL, simple-compound default, nondynamic setting and actual model
position. An entity-return receipt or the UI's success text is not model or
rendering proof. Cancel and denied/zero entity returns remain distinct outcomes.

## Host validation and exact next dependency

The optional Usage host extension executes original QML baking/import/dialog
JavaScript. Qt binding/lifetime, API permissions, mouse dispatch, service statuses
and entity returns are explicit models. Private temporary files, normal Python
input/intent transport and separate binary GetAll replies execute normally. The
host does not fabricate oven bytes or native model/rendering observations.

The first 43-case selection passed its 36 legacy cases but all seven new cases
stopped during an unnecessary local FBX stage setup. This exposed a real separate
blocker: the pinned 25,196-byte FBX plus inline original sources exceeds the
existing file-owner's 48 KiB packed-WAL ceiling. No pin, body or packing limit
was changed. Isolated browsing/control tests now begin with an explicitly seeded
existing server asset, enter the actual browser with normal menu input and make
no upload claim. The storage prerequisite is now addressed by the
[version-2 file owner](ASSETS_FILE_SOURCES.md), with literal version-1 reads and
exact immutable native originals. Full ordinary FBX upload remains unqualified.

The corrected 43 cases passed in 2.807 seconds. Eleven final Usage cases plus
36 existing tree/bundle/normal-input/Back/Keyboard cases then passed: 47/47 in
3.181 seconds (`.ios-host-tmp/assets-usage-controls-final-20261026.log`). They
cover real original normal checkbox toggles and independent status replies,
deferred busy/disabled UI, actual model defaults and acceptance arguments,
stale text/permission tokens, preserved original permission-denied handlers,
existing uploaded-URL consumption without claiming upload, cancel/zero returns,
strict source/clock/types and required durable intents. Old default host paths
remain literal when the optional Usage extension is absent.

The measured FBX file-owner WAL storage fix preserves existing limits and exact
observation bytes. The [durable normal action owner](ASSETS_USAGE_OWNER.md)
now retains ordinary bake/import input and client recovery separately from
actual worker/meta/output, model/resource consumers,
independent rendering and complete paired cleanup. Full capability admission
and ordinary successful feature publication remain unavailable until that work
is complete.
