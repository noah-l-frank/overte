# Private Avatar target and authority configuration

Whole Avatar coordination uses the existing qualified primary and actor SDK
selectors. Configuration requires `artifactRoot`, `imagePolicy` and the other
target selector: `actorTarget` for the primary role or `primaryTarget` for the
actor. The target selectors must differ. The image policy uses the existing
closed world-render-target policy and private absolute artifact directory.

The actor additionally requires a separate private `authorityRead` object:

```json
{"mode":"adapter","token":"<private adapter read token>"}
```

The closed modes are `adapter` and `reader`. The former uses the existing
adapter token and `X-Overte-Fixture-Adapter-Read: 1` marker. The latter uses an
existing reader token. This changes no server rights. An actor publisher token
alone cannot read account credentials; absent separate read authority fails
before SDK preparation. The primary may use its existing reader client.

The runtime receives two live clients with the same controlled HTTPS fixture
URL: the existing phase/publication client, and the separately scoped account
authority client. The scoped client permits only GET of this run's Avatar
account status and this SDK role's credentials. It cannot publish, mutate
session bindings, revoke authority or read the other role's credentials.
Tokens remain live private configuration; feature metadata and evidence must
never serialize them.

Host tests verify the closed configuration and actual loopback TLS behavior:
the publisher alone and a falsely marked publisher fail account reads, while
the separately scoped adapter client reads its original account scope and own
credentials. These are input-authority tests, not login or peer effects.
