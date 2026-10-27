# Measured domain policy before normal Snapshot Upload

Feature 11 remains capability-closed; five of fourteen areas are source-complete.
This component reads an already owned domain's identity/effective policy and
connects that source to the actual normal Snapshot Script preflight. It does
not establish external metaverse registration or complete the Snapshot journey.

`fixture/domain.py` exposes the opt-in, default-disabled
`--feature-snapshot-domain-policy` reader. It reuses the existing actual online
process admission: owned PID/start identity, live process, exact executable,
configuration argument, HTTP port and observed domain ID. Defining this reader
does not enable Create rez, call its preparation, change permissions, transition
a domain or start another service. Its separate passive credential appears only
in the private ready receipt, never the printed receipt or observation packets.

The reader accepts only bounded GETs to `/id` and `/settings.json`, with redirect
refusal and identity checks before and after each request. It derives `open`,
`hifi` or `acl` from actual effective anonymous/logged-in `id_can_connect` bits,
following `DomainMetadata.cpp`. Missing, duplicate, nonboolean or unavailable
policy remains unavailable. Raw settings may contain credentials: only their
length/hash and the two policy bits are returned. Original nonces preserve the
first packet and clocks; a late cached original cannot become fresh evidence.

The separate Snapshot-domain client validates the first actual PID/start/domain
binding, source instance, exact version, monotonic/UTC order and independent
host acquisition clocks. It has no domain-control operation or credential.
The optional upload provider projects this genuine online identity/policy into
the Script's fixed concurrency query, bound to an existing actual account.
The requested domain is a filter, never a source measurement. A foreign domain,
ACL policy, revoked account or missing source cannot produce an allowed share.
Every result explicitly identifies a controlled fixture projection and retains
the external-registration and resource-retirement obligations.

`snapshot_upload_preflight.js` executes the original `onMessage`, `isDomainOpen`,
revision wrapper and `request.js` from the checkout. Its explicit XHR boundary
passes the original GET URL to the existing actual authenticated HTTP serializer
and then delivers that response once to the persistent Script context. The
actual VM return is observed with no pending native upload before the async
response callback runs; no Script stack is held across that response. No
Bearer reaches Node or its output. Actual Script decisions determine whether
`Window.shareSnapshot` is invoked; a desired `canShare`/count is never supplied.
The ordinary Upload fixture creates its native job/body FD only after that
actual Script call, while preserving the existing default fixture behavior.
Qt, TLS, process identity and effective domain settings remain declared host
boundaries; this runs no real domain service, listener or device.

Final focused host evidence includes eighteen actual Script/request-module,
policy and concurrency cases in 0.261 seconds; the normal Capture→preflight→
Upload and Capture→preflight→Cancel components in 14.202 seconds; and all eleven
existing provider/HTTP cases in 0.014 seconds. The components retain the exact
capture body, known QObject/body-FD quiet and remaining transport-process proof
requirement. Cancel releases the actual native FD while the uploaded backend
body remains owned; it creates no story or invented native DELETE.
They cover process drift, malformed effective permissions, original/late nonce
handling, passive credential separation, unauthorized accounts, foreign query
domains, missing writes, actual ACL denial and stale-review callback exclusion.
Private logs are
`.ios-host-tmp/snapshot-domain-preflight-resume-20261027-{final05,flow06,compat07}.log`.
An earlier run reached a test-only cross-clock comparison: the genuine backend
UTC was 26 ms later than the existing declared native fixture timestamp. That
assertion was replaced by the actual enforced order (observed response write
and handler departure before native job construction). Neither source clock,
production deadline nor original evidence was adjusted. A subsequent source
review corrected the new fixture's VM-return publication to precede the async
response, as the actual Script does. The final cases above include that change.

The explicit version-2 profile of the existing backend owner now admits
preflight originals through the same closed private GET, nonce, frame-store
and parent-CAS machinery. It pins the independently supplied domain-reader
public binding; literal default/version-1 records and transport envelopes stay
unchanged. Version-2 history requires that same independent binding and rejects
a version-1/default reader. A failed policy read retains its original query
bytes and unresolved response fields. A prepared response retains its actual
bytes separately, including missing-write responsibility. This evidence never
comes from reserializing a parsed response into a purported original.

The join requires the exact upload ticket/account and first backend PID/scope,
one allowed preflight, observed complete write/departure, and the subsequent
actual multipart request. Only those backend events share a clock domain;
policy, native jobs and frontend callbacks retain their independent clocks.
It proves backend chronology and preserves the actual response/query/policy
bytes. Actual frontend response consumption and external metaverse registration
remain explicitly required; a GET acknowledgment is not a native effect.

The new original codec passed seven focused byte/binding/chronology cases as
part of an eighteen-case selection in 0.054 seconds. The version-2 normal
Script→Upload→durable original→pure history component passed in 9.685 seconds;
three recovery/negative components passed in 27.599 seconds. They cover lost
same-nonce GET returns, original inode adoption after saved-frame/parent-CAS
interruption, and an independently wrong domain PID before body acquisition.
The final affected selection passed thirty-seven cases in 9.385 seconds,
including the original default/version-1 backend owner and provider/HTTP,
policy, concurrency, byte-codec and actual Script boundaries.
Private logs are
`.ios-host-tmp/snapshot-preflight-original-resume-20261027-{source01,owner02,recovery03,compat04}.log`.

Failed then successful upload composition, actual frontend consumption,
rendered review/Actor evidence, fixture and source-journal retirement,
background return and paired main process/SDK closure remain open. Neither a
local concurrency row nor an input ACK supplies those proofs.
