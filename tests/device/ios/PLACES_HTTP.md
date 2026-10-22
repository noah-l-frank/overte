# Original iOS Places HTTP consumption and lifetime, version 1

This is a component of the still-partial Worlds/navigation adapter. It does not
advertise the full area or establish arrival, rendered images, restart,
independent publication or complete cleanup. Native compilation is unverified
and devices are untested.

## Original native source

`PlacesHttpObservation.h` and the existing `XMLHttpRequestClass` record passive
events under `OVERTE_E2E_FEATURE_TESTS`, `Q_OS_IOS` and `--testScript`. The ordinary
XHR return values, callback dispatch, request, timeout, abort and destruction
behavior remain unchanged. In particular, a completed reply does not stop a
product timer or erase a retained callback in order to satisfy a test.

Only asynchronous GETs for the exact Places directory path/query qualify. The
actual first script caller must be the installed `system/places/places.js`,
with a file source inside the running app directory or a qrc source. Its actual
engine manager must have an assigned installed `defaultScripts.js` source and
submitted code. The source retains original manager birth/load generation,
load URL, submission SHA-256/UTF-16 count/time and the actual native protocol
signature. An HTTP probe script or caller-selected source label cannot register
an event. The whole-area owner must still join these originals to its existing
installed candidate/source binding; file suffixes alone do not prove provenance.

One ledger lives in the script-engine library. All updates and snapshots share
its mutex. A snapshot never enters another ScriptEngine heap or waits for a
script thread. Its existing Test interface marshals onto the GUI thread, then
copies the ledger. Event UUIDs, increasing counters, native UTC/monotonic clocks,
XHR/reply UUIDs and original event details are immutable. Backward clocks,
unknown identity, exhausted bounds or an oversized packet invalidate the source;
no historical prefix is trimmed to obtain a successful empty result. Bounds are
128 XHRs, 1,024 events and 262,144 serialized bytes per process.

The history records actual creation, send, finished reply, normal responseText
read, callback entry/exit, timer state, abort, callback release, timer destruction,
reply destruction and XHR destruction. Finished replies retain original native
status/error and the actual unique fixture response header. Only replies with a
valid fixture header retain original body bytes/Base64/SHA-256, bounded to 4,096
bytes. No Authorization header, credential or unrelated response body is exported.
Malformed/duplicate fixture headers and unexpected redirect URLs make the source
unavailable. Reply, timer and XHR destruction come from their actual QObject
signals, separately from a scheduled delete or idle callback depth.

## Input, transport and evidence joins

The private `feature-ios-places-http` command has only schemaVersion 1, an iOS
nonce, action and run ID. The existing probe calls the passive hook once for
the current nonce and writes the fixed atomic private
`feature-ios-places-http.json` file. Missing hooks remain unavailable. The
FeatureObservation factory and existing Script runtime source facade use the
normal private HTTP/AFC path; they neither create an SDK session nor resend an
uncertain command.

The reader reuses the Places model reader's original acquisition mechanism,
with its own closed grammar, parser and receipt version. Separate nonce-bound
native clock acquisitions bracket the snapshot within 1.5 seconds, preserving
PID, source birth, monotonically advancing sampling counters and immutable event
prefixes. Host monotonic time limits acquisition duration only. Server and native
UTC barriers are supplied separately; a server timestamp is never relabeled as
native time. Historical originals need no clock refresh or native factory.

`consumed` joins a same-run/ticket provider receipt, exact body bytes/hash/status,
the actual supported native protocol, a genuine Places callback responseText
read and an independent current [Places model](PLACES_MODEL.md). The native
request must follow the original event/time barrier. The server receipt must
follow its own server-clock barrier. Actual materialized ID, name, address,
description, attendance and capacity must agree with the original parsed record
and wire input, in a current same-PID page after the read. No desired model data
is passed to native instrumentation.

The common provider now implements the supplemental
`feature-navigation-directory-marker` v1 contract: every real response's normal
description field contains `overte-directory-v1:<responseId>`. The body hash in
the provider receipt covers that exact input. Its shape and existing provider
v1 envelope remain compatible; ID/name/destination/search behavior are unchanged.
The actual product parser and actual QML materialization must carry the unique
description into the actual row. This distinguishes a failed parse or ignored
handoff that leaves an old row, even after a new responseText read and a fresh
native snapshot. A server receipt or body read alone cannot satisfy the join.
Reconcile this provider addition and the three new registry entries with the
Phone/Pico registry union; no parallel or protected branch is changed here.

`drained` requires explicit original owned XHR IDs, actual callback release,
timer/XHR destruction, zero active callback stack and every native reply's actual
destruction. An unknown ID, empty ownership list or unfinished lifetime cannot
be retired using an empty history. This is the XHR condition only. A whole-area
owner must still combine [retained QML queues](PLACES_MODEL.md), independent quiet
windows, original settings/bookmark restoration and final OS/SDK retirement.

## Host evidence and limits

Fourteen new host tests execute original product JavaScript/QML filtering
functions, actual probe dispatch, original Python HTTP/AFC codecs and a real
loopback Directory provider. Native XHR, Qt model and SDK boundaries are modeled.
They cover ignored outcomes, stale materialized rows despite a fresh body read,
foreign source/PID/protocol/ticket/response, changed histories, missing evidence,
retained replies/timers/callbacks, one-send timeouts and independent server/native
clock offsets. The shared loopback provider separately tests two fresh markers
with an unchanged destination. These are source/test-logic checks, not native
compilation, Overte execution or device qualification.
