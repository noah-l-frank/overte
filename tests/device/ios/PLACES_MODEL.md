# Original iOS Places model and retained queues, version 1

This is a passive component of Worlds/navigation, which remains partial. It
neither advertises a full capability nor supplies directory HTTP-consumer,
arrival, image, persistence, restart or whole-journey retirement evidence.
Native compilation is unverified and devices are untested.

`feature-ios-places-model` uses the existing private fixture, probe,
`TestScriptingInterface` and fixed atomic private JSON/AFC transport. Its closed
command has only schemaVersion 1, command nonce, action and run ID. The probe
calls the native hook once per current nonce; a missing hook remains unavailable.
No desired search results or arbitrary paths are accepted. Observation code is
gated by `OVERTE_E2E_FEATURE_TESTS`, `Q_OS_IOS` and `--testScript`.

The native source runs on the GUI thread. It uses existing OffscreenUi and
TabletScriptingInterface dependencies and finds the already existing system
TabletProxy by its actual name among direct QObject children. It does not call
the lazy-creating `getTablet` factory. Both actual iOS roots must be present.
The bounded visual survey includes hidden items and window content. A root with
the Places semantic screen but a foreign QML source makes the survey incomplete.

Each actual selected `PicoPlaces.qml` root has the same weak original UUID used
by [the normal input controls](PLACES_CONTROLS.md). The observer retains QPointers
to all roots it has seen, including roots detached from the current visual tree.
Only actual QObject destruction removes a retained root. A missing item,
oversized traversal/model/packet or unknown property yields unavailable or
incomplete evidence, never a manufactured empty model. The complete flag is
checked before interpreting either active-page or drained-queue results.

For every retained root the source reads original loading/current address,
warning, records, bookmarkAddresses, maturity filters, pendingCommands, timer
running state, selected tab, search text and bookmark modal values. It resolves
actual original QML object IDs, then reads each real ListView's assigned
QAbstractItemModel. Place, bookmark and server roles retain actual row order,
multiplicity and values, with at most 1,000 rows per model. Hidden models remain
separate from their view's actual visibility. Raw records and materialized search
results are independent; the reader never reruns filtering to invent rows.
Likewise, bookmarkAddresses cannot substitute for the actual bookmarks model or
[the independent saved file](LOCATION_BOOKMARKS.md).

Original native UTC/monotonic clocks bracket the read. Packets retain PID,
observer birth, advancing counter, nonce and run; separate nonce-bound native
clock acquisitions bracket the HTTP/AFC result within 1.5 seconds. Host monotonic
time limits transport only. The separate v1 acquisition receipt hashes the
unchanged original packet. Reuse, source replacement, foreign PID, stale clocks,
multiple active roots, duplicate root IDs and invalid typed rows fail closed.
Historical validation preserves the original clocks without refreshing sources.

The input join requires the same original root UUID, QML source and PID, with
a later control snapshot within 1.5 native seconds. It does not replace the
caller-owned control reference or infer an effect from an input ACK. Closing a
page cannot prove a drained queue while any retained root is active, loading,
has queued commands, has a running dispatch timer or retains a visible bookmark
dialog. This is only the QML queue condition: HTTP callbacks and native lifetime
drainage still require their own original source and quiet window.
The [native XHR source](PLACES_HTTP.md) now supplies the independent HTTP/lifetime
condition and a response-specific materialized-description join. The complete
Worlds owner and combined retirement are still pending.

Twelve host tests exercise the Python source, original HTTP/AFC codecs, closed
fixture grammar and actual probe branch with modeled native/SDK boundaries.
They cover ignored effects, raw/filtered-map divergence, duplicate rows, retained
queues after close, incomplete inventory, stale/foreign/reused originals,
changed processes, distinct native clocks and uncertain replies without resend.
They do not execute the native QML/model survey or qualify physical behavior.
