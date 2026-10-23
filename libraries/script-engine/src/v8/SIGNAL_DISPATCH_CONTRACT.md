# SH-005 Qt-to-V8 signal dispatch boundary v001

The existing `ScriptSignalV8Proxy::qt_metacall` production callback rejects more
than `Q_METAMETHOD_INVOKE_MAX_ARGS` (10) arguments before array access/conversion,
missing argument storage/types and empty or terminated conversions. Invalid
empty/non-function callbacks are skipped without a context pop or script-driven
diagnostic conversion. Empty/non-object receivers retain global receiver behavior.
Qt 5 and Qt 6 use their respective QVariant constructors.

An observed V8 termination after a callback stops this emission immediately:
no subsequent connection delivery, diagnostic call or uncaught-exception
notification. Ordinary exceptions retain existing captured diagnostic behavior
and continue to later connections. This requires the captured-diagnostics v001
contract (source ecae47c374da16654b6bde9229953e4f889afbed, manifest
5b83a57703be7a640873c4c82aeaed6f38517d9c05cbeaee2a35218cbd6afcb0).

Focused check: `V8_TEST_ROOT=<host tools root> python3
tests/device/contracts/lifecycle/test_v8_signal.py`. All 13 isolated cases pass
with real V8 and Qt 6, QT_NO_DEBUG, original complete callback, original abstract
base passed through moc, actual QMetaObject connection/emission and original
ReadWriteLockable. The fixture substitutes value ownership, engine conversion,
diagnostic receivers, connection registration and signal names. Cases cover
0/1/10/11 parameters, invalid callbacks, missing arguments/conversion, ordinary
throw, termination and released locks. Host Node 22.23.1 is not candidate 22.22.3.

No platform-native hook is added. Pending: whole engine/Qt5/platform compilation,
optional performance-statistics build, registration/disconnection and QObject/
V8 lifetime safety, sticky cancellation, blocking native callback behavior,
informed consent/grant/finite revoke and original artifact/device acceptance.
This is a callback failure-path prerequisite, not a complete revoke backend.

Method-proxy retirement now distinguishes an already cleared weak handle from a
live persistent handle. Deferred QObject deletion after the weak callback does
not enter V8 or dereference the retired engine. A live handle is reset under the
existing engine Locker/Isolate guard. The existing signal fixture additionally
executes the complete production destructor, weak callback, and scope guard with
real V8 garbage collection and Qt DeferredDelete outside the preceding Locker.
Both prior deletion paths reproduce the native HandleScope locking fatal error;
the repaired paths destroy the object exactly once. The 17 signal cases remain
passing alongside these two lifetime cases using the cached native producer's
libnode. Whole application shutdown and device acceptance remain separate.

Avatar bookmark serialization now owns the fresh engine's scope while converting
wearable entity properties. The existing host suite executes the complete
production bookmark producer with the real V8 scope guard and isolate/context:
empty bookmarks, one wearable with missing/filtered entries, and a distinct
caller isolate. Before the guard, both wearable cases abort at the current-engine
invariant; after it, all three preserve the bookmark data and restore the caller
isolate. Entity lookup and serialization boundaries remain host fixtures; normal
favorite creation with a wearable still requires device acceptance.
