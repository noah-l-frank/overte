# Adapter-only fixture access, version 1

The assertion runner, product adapter and independent observer use separate
credentials. The existing harness continues to remove
`OVERTE_E2E_FEATURE_READER_TOKEN` and expectation-policy variables from adapter
subprocesses. Giving an adapter the runner token is not a supported workaround.
These source/host contracts do not qualify any product or physical client.

| Role | Run registration, activation and deletion | Publish independent samples | Read independent journal facts | Read original phase/provider metadata |
| --- | --- | --- | --- | --- |
| Assertion runner (`readerToken`) | Yes | No | Yes | Yes |
| Independent observer (`actorToken`) | No | Yes | Yes | Yes |
| Product adapter (`adapterToken`) | No | No | No | Yes |

## Controlled service configuration

The existing `feature_journeys/server.py --private-config` file may additionally
contain `adapterToken`. It must be a distinct private ASCII credential of 32..256
non-whitespace printable characters, different from the reader and actor tokens.
Omitting it preserves the existing two-role service and does not silently enable
adapter access. Existing listener, TLS, account-provider and private-file rules
remain unchanged. The second browser listener stays resource-only.

An authenticated `GET /feature-fixture/v1/adapter-reader` is available only to the
adapter credential and returns exactly
`{fixtureAdapterAccessVersion:1,role:"adapter",canMutate:false,canPublish:false,peerFactsVisible:false}`.
This is access metadata, not product evidence. Every adapter request carries
`X-Overte-Fixture-Adapter-Read: 1`; the server checks that the current credential
still has the adapter-only role on every request, including after admission.
A changed role cannot inherit a cached admission or expose peer facts.

Adapter GETs retain original active stimuli, read clocks, provider births,
resource-delivery histories and original backend status. The run-journal
response preserves its schema/ticket/clock but always contains `entries:[]` for
this role. Actual independent observer facts remain available to the assertion
runner and observer only. The adapter cannot register/activate/reopen/delete a
run, publish samples, issue fixture controls, or use earlier account routes to
mutate state with its credential. The independent account proof endpoint remains
actor-only.

Authentication may read only the existing owned/invalid/delayed input credentials
through the adapter role. The account provider still requires trusted HTTPS and
never provisions a personal/public account. Normal client UI input and native
AccountManager request/reply evidence remain mandatory; possession of a fixture
password is not a login result. `AdapterFixtureClient` refuses every mutation
before transport, including attempts to register, activate, publish or clean up.

## Private adapter input

`adapters.feature_fixture_access.client(path,configured_url=...)` reads exactly:

```json
{
  "fixtureAdapterAccessVersion": 1,
  "fixtureUrl": "https://<owned fixture>/feature-fixture/v1",
  "adapterToken": "<private adapter-only credential>"
}
```

The placeholders must be replaced with actual private runtime values. The file
must be an original 0600 regular file under a canonical 0700 parent, with the
existing owner/no-symlink/no-shared-link rules. It accepts no expected result,
runner token, actor token or policy path. A supplied configured URL must match.
Nothing is printed, staged in the checkout, or copied into artifacts/observations.

The resulting `AdapterFixtureClient` validates its actual server role before its
first read, sends the required role marker on every read, and allows only GETs
without request bodies. It never calls fixture registration, activation or
cleanup on behalf of the assertion runner. Missing configuration, the wrong
role, malformed/old access response or a two-token service fails. There is no
fallback to a runner credential or an actor credential.

Phone full-feature factories use the private
`OVERTE_PHONE_FEATURE_FIXTURE_CONFIG` path. The existing
`OVERTE_E2E_FEATURE_FIXTURE_URL` remains an input origin and, when present, must
match the private configuration. The independent worker continues to receive
only its own actor credential and must not inherit the runner token. Runtime
configuration and service activation belong to the later authorized laboratory
phase; the implementation work starts only bounded owned loopback self-tests.

Eleven dedicated host cases plus the account HTTPS case exercise real private
files and actual owned HTTP/HTTPS listeners. They cover distinct role admission,
peer-fact masking, every mutation route, credential-role mistakes, wrong/private
file scopes, role reassignment, optional-role compatibility and retired-provider
reads. These are source/privacy logic checks, without a build, installation,
device connection or laboratory run.
