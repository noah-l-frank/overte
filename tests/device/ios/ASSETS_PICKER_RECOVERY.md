# Assets picker continuation and image-source assembly

Normal upload preparation now resumes the existing picker input journal after
a lost return. Completed slots are reused. An uncertain delivered command
requires its original passive effect before preparation proceeds; an unissued
or unresolved slot never authorizes another delivery. A foreign page cannot
be adopted as the result of opening Assets.

Before submitting the folder, preparation still independently observes that
the original folder control contains the selected directory. A successful
input receipt alone cannot satisfy this check. Selection, upload reservation
and file staging retain their existing owners and journals.

[The runtime](adapters/assets_runtime.py) also assembles the four existing
primary image-source owners: reader lifecycle, processing, storage and pool.
Each keeps independent native and source cursors under the original session
lock. Assembly performs no acquisition or resource reservation. Every existing
image responsibility must match the same binding, primary role and run;
foreign owners, unknown original files and changed original bytes or inodes
refuse assembly before source I/O.

## Host verification

Thirteen selected tests passed: seven canonical image-owner assembly checks
and six normal picker checks, including lost replies, an unrelated page,
ignored opening and ignored folder replacement despite a successful receipt.
They retained 139 original files in seven genuine `mkdtemp` roots and six
genuine `TemporaryDirectory` roots. All 8,128 source/launcher pins remained
unchanged. All six original QML Node hosts completed their existing
terminate/wait/stream-close cleanup; no normal zero exit is inferred from
that termination. No fixture threads or owned processes remained.

The frozen local packet is
`.ios-host-tmp/assets-four-owner-picker-field-guard-root13-preparation-20261029`.
The earlier source proposal and the separate field-observation correction
remain preserved.

These checks qualify upload preparation and source-owner assembly components.
The image histories retain partial resource responsibilities. Global pool,
byte, GPU, backend, paired process/SDK end and the complete public Assets
journey remain open. Qt/native/SDK boundaries are declared host models;
no native compilation or device execution was performed. Complete areas
remain 5/14.
