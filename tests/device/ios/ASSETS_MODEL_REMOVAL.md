# Ordinary local Model removal and retained cached resources

The new `OwnedAssetsModelRemoval` child is a checkpointed, unqualified
integration draft. It uses existing normal Create tokens through `IOSCreateUI` and
`NativeInput.deliver`; it invokes no Entity service, QML handler or cache API.
Only the actually adopted Assets UUID may be selected or deleted. The first
route admits no pre-existing editor, avoiding changes to foreign selections or
drafts until their exact restoration is supported.

Each normal command is bound to its exact freshly captured native admission
and saved before delivery. Original receipts and UI frames remain separate.
Original Home/Create/tab/refresh/owned-row/Delete inputs belong to this child;
the earlier picker phase remains unchanged. Unknown commands are not replayed.

After ordinary Delete, independent whole-tree originals must contain exactly
the previous foreign rows and no owned target. Actual observed entity and
Model weak lifetimes must be destroyed. The separate origin history version 2
then records the remaining original lease, actual QObject and HFM lifetimes.
The product cache can still own its QObject/HFM after the Model is gone; that
is retained responsibility, not successful resource retirement.

Normal Home closes the child's new Create context. Parent client cleanup must
independently observe the old Assets page/picker roots gone, actual upload
holders and both native/host input-file quiet intervals before releasing its
files. Cached resources, the remote entity, server mappings/blobs/meta/workers,
rendering and actor proof remain separate and blocking. No full feature route
is enabled; source completion stays 5/14.

## Current host evidence

The first three component attempts were rejected by existing strict guards:
the new fixture initially omitted its original observation receipt/intent
(1.119 seconds), the new channel mixed two captured elapsed-time scopes
(22.089 seconds), and its initial allowlist omitted the existing readonly
Create Refresh recipe button (45.182 seconds). Only those measured fixture/
scope issues were corrected; no existing admission or source limit changed.

The ordinary local removal case then passed in 82.835 seconds; private log:
`.ios-host-tmp/assets-model-removal-refresh-20261026.log`. It observed the actual
local entity/Model gone while the original shared lease expired and the actual
cached QObject/HFM remained alive. The expanded context/parent-client closure
and lost/ignored input recovery are still being qualified.

The expanded case subsequently reached normal Home closure and parent cleanup,
then was correctly rejected for the actual pre-existing-server upload child's
`ready` phase (122.787 seconds). Its existing abort cleanup flag is now used
for that phase; no uploaded phase was invented. The next case completed those
methods but ended at a test-only wrong `parsed.usage` accessor after 133.214
seconds. That assertion now uses `parsed.model.usage`; it has not yet been
rerun. Neither expanded failure is a passing qualification. Exact continuation
is in [the removal resume checkpoint](ASSETS_REMOVAL_RESUME_20261026.md).

Assets upload/import QML and actual Python owners, original files, journals and
weak objects run. The Create Qt widgets/controller/deletion and native APIs are
explicit SDK models. No native compiler, renderer, device, service or server/
oven executes. The native history-v2 hook remains uncompiled/unexecuted.
