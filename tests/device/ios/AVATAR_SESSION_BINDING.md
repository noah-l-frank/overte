# Original controlled Avatar session inputs

Accounts1 may include the closed optional `sessionBinding` component after the
actual fixture authority stores both controlled session UUIDs and Domain UUID.
The component (`feature-avatar-session-binding`, write/read 1) copies the real
stored input binding. It is neither client login proof, received peer metadata,
loaded geometry nor a consent result. Legacy Accounts1 snapshots without the
component remain readable; a reader that actually saw it requires the same
component thereafter, including during authority revocation.

The original `/avatar/sessions` POST still binds at most once. Its empty input
ACK is not sufficient for recovery. After a lost POST socket return, a fresh
private Accounts GET can independently show the same actual stored inputs and
ready phase. A different, missing or changed original binding cannot be adopted
as the issued preparation. A whole durable preparation owner must retain its
issued responsibility and never repeat that POST just because its return was
lost. Credentials/profile proofs and genuine distinct SDK/mixer sources remain
separate mandatory obligations.

Five host tests use the real optional fixture server and short-lived private
loopback TLS. They cover actual stored readback with zero grants/consent,
a socket closed after the real POST mutation, actual HTTPS reader continuity,
legacy missing-component decoding, source downgrade/foreign binding refusal,
strict component shape and original binding after authority revocation. Existing
backend/account HTTP/runtime suites also pass (25 total tests). Certificates
remain test-local; system trust, native devices, installations and builds are
not used. This component advertises no complete Avatar capability.
