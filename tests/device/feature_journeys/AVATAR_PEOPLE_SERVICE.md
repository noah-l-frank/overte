# Controlled Avatar/People HTTPS service v1

This is the default-off protocol fixture used by the Phone Avatar/People
adapter. It is a source component, not a complete adapter or device result.
The existing trusted HTTPS/account fixture accepts an additional private config
key `avatarPeopleService: {"domainId": "<owned-domain-uuid>"}`. It requires the
same original account provider and TLS owner, and never changes endpoint or TLS
policy. Without this explicit opt-in, service routes and Avatar/People fixture
registration are unavailable. Snapshot upload remains outside this component.

Registration provisions two distinct temporary OAuth principals. The existing
AccountProvider alone issues genuine grants. The adapter-only credential can
read the primary's input credentials; the separate actor credential can read
only the peer's credentials. Neither fixture-role credential can establish a
relationship, publish with the primary role, or control account cleanup.
Credentials and native request details remain private; no request is logged.

Owned FST/FBX/texture/glTF resource responses use the same completed-wire
receipt mechanism. Their immutable body digests and response IDs are original
service facts; the adapter must separately join actual native consumption.
A DELETE before any original session POST returns a bounded 409 response.

The normal original People protocol sends authenticated POSTs to
`/api/v1/user/connection_request`, then bounded GET polls. The first actual POST
binds its declared session pair to the two owned principals; the native adapter
must separately compare both sessions and the controlled domain to independently
observed actual participants. Two distinct principals must submit reciprocal
session IDs within the same active ticket and real twelve-second pending
lifetime. One sender, a GET poll, mismatched sessions, a stale phase or fixture
control cannot create a relationship. Ordinary cancel/reject before both consent
produces no server relationship. Pending expiration follows the provider clock.

The actual `/api/v1/users` and `/api/v1/users/connections` reads return current
mutual relationships; the normal DELETE endpoint removes the relationship for
both accounts. HTTP response status, identity, written byte count and digest
are recorded only by the original completed HTTP write callback. A missing or
partial response increments an immutable failure count; it is never promoted
to completed proof. Each private source read uses a new nonce and validates
complete immutable history. Source-only receipts do not establish native
consumption, UI consent, peer replication or rendered geometry.

Cleanup must first remove the actual relationship normally, read both accounts,
then let the runner revoke the two owned OAuth authorities. Fixture retirement
checks zero relationships, pending requests, in-flight writes, tokens, grants
and live accounts before removing control ownership. Original failed delivery
history remains retained even after successful resource retirement. A failed
phase cannot become product success by erasing that history.

Host verification executes actual loopback TLS, OAuth grants and independent
HTTP requests, with a temporary certificate trusted only by the test process:

```sh
PYTHONPATH=tests/device python3 -m unittest self_tests.test_avatar_people_service.AvatarPeopleServiceTests -v
```

No native client, device, installed trust store or product behavior runs here.
The complete Phone public facade, native observations, independent peer/actor,
mandatory multi-user foundation and common Journey remain separate obligations.
