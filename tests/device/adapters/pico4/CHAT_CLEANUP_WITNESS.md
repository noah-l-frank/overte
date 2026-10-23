# Private original Pico Chat cleanup witness construction v1

`PicoBoundAdapter._chat_observation(target, source, samples, stage=...,
witness=...)` binds the existing private `ChatObservationOwner` to the fixed
Pico flow/admission/sample paths. Independent witness credentials cannot be
replaced by the parent's `AdapterFixtureClient`. Observation and cleanup
publisher roots, including rootless original chunks, keep generic cleanup
closed through `_chat_application_retained`; they are never silently discarded.

`_chat_cleanup_witness(target, original)` constructs `PicoChatCleanupWitness`
from the exact still-live independent `PicoChatWitness`. The original private
parent must already contain the same binding/run/peer/fixture, all 26 consumed
stages and `caches-retired`. Construction does not start/discover a peer or
reconstruct an unknown publisher, result or host descriptor. It reuses the
original peer object, independent actor client, both original lock objects and
original compiled-script reader objects. The fixed final-witness cache-absence
factory creates new primary/peer/view/lifecycle readers. No native observation
or ordinary input is issued by construction itself.

The exact original parent row remains a read-only admission fence. A guard on
the new primary reader qualifies it during actual acquisition and the final
multi-source clock/guard checks immediately before POST. Parent finalization
after the last publishing CAS therefore prevents publication even if the
fixture's cleanup ticket itself has not changed. Target facts still come from
new original native queries, never from the parent row or an ACK.

`publish()` delegates to the strict once-only original cleanup publisher and
retains every unknown operation after failure. `detach()` propagates the
original independent witness's actual host-close result; it cannot infer
closure from the parent's host finalizer. The wrapper has no separate release
or archive receipt. Its declared API versions are `pico-chat-observation` 1 and
`pico-chat-cleanup-witness` 1; stored journals retain their existing versioned
common schemas.

Three original Pico factory cases passed in the six-case 43.633-second run:
independent code/readers/locks, adapter credentials and premature-parent
refusal, and rootless observation/publisher retention. That combined run was
red because a wrapper fixture returned a different phase-reader object than
the original argument. The fixture now follows the actual factory's identity
contract, and all three wrapper cases passed again in 29.596 seconds, including
parent finalization after the final publishing CAS and false host-close
propagation. The factory cases use an actual owned Linux stdin worker and
explicit SDK/native producer seams. The wrapper cases use explicit Pico
parent/adapter identity projection onto the actual compiled-source fixtures;
they do not claim that projection ran the actual full Pico constructor or all
25 target effects. No app, AC, service, device or OpenXR runtime runs.

The next composition must consume the independent three-second baseline,
explicitly freeze the consumed observation/publisher originals, and include
every such root/chunk in the pre-restart/archive inventory. Current strict
inventory refuses unregistered new files; this packet does not supply that
finalization join. Public operation/cold-RPC lifetime, actual stereo evidence
and whole-feature qualification remain closed.
