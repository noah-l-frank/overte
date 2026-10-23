# Pico original Snapshot capture context

This private source is an observation component, not Snapshot acceptance.
`snapshotScriptOriginalsVersion: 3` binds the current original Setting manager to
the same manager's entries recorded at each actual `featureCaptureEvent` VM call.
`snapshotScriptHistoryVersion: 2` stores those immutable event entries.

The three closed keys are `previousSnapshotDomainID`, `previousSnapshotHref` and
`previousStillSnapPath`. Every entry retains actual presence separately from its
original string value. Missing entries are JSON null, never replacement strings.
The native read also records the actual manager birth, capture clock and
`QUrl(originalHref).toString()` used by the native upload path. The latter does
not replace the original string or assert that the domain is open.

`Setting::Manager::featureSnapshotCaptureContext()` reads only the existing
in-memory settings under the original read lock, with a 25 ms try-lock bound.
It neither creates a settings dependency nor starts its writer. Missing manager,
blocked lock, unsupported value, runtime gate failure or invalid VM context is
unavailable; an invalid event permanently marks its existing recorder incomplete.
The existing private source command/run/nonce/owner-thread gates are unchanged.
Both the dedicated test-build macro and Pico macro are required for the settings
source, and `--testScript` is required at runtime. Non-Pico keeps wrapper 2 and
history 1. Readers retain legacy archive support without upgrading old evidence.

The frozen Phone comparison is
`b62e012f1328e30b80604bb447a60db0d8a748df`:
`PhoneSnapshotSettingsKeys.h` supplies the same keys and
`Setting::Manager::featureSnapshotEntries()` supplies the original presence/value
pattern. This Pico implementation narrows the key set, bounds lock acquisition
and adds original manager identity plus event-time binding. No Phone restore
setter or Phone UI/source authority is selected.

The product `snapshot.js` writes the original location/domain at capture entry
(lines 545–547), records the pending VM event after registering its actual timers
(line 591), and later reads those settings before normal upload (lines 163–175).
Its domain check slices braces from the original domain string (line 627).
Consequently a provider domain UUID or a current UI permission alone cannot prove
which capture context the upload used. The upload owner must join the original
pending event, current manager/context, original Still path and actual uploader
href; original backend permission and reply/PNG evidence remain separate joins.

The focused native test compiles the unchanged real read, birth initializer,
read/write-lock classes, VM scope, history recorder and Snapshot bridge bodies.
It checks a genuinely blocked writer, consumed unavailable query, missing
dependency, absent values, invalid original types, immutable event/current-read
separation and the runtime gate. Manager construction/storage/DI and VM identity
are explicit host seams; global settings writers, V8, APKs, devices and product
functional behavior are not exercised. Python cases additionally reject manager
replacement across event/current/empty-history reads and malformed DTOs.
