# Phone Authentication input/observer owner v1

`PhoneAuthenticationFeature` currently composes the normal input owner and the
two independent source ledgers under the existing native-channel lock. It is an
internal part of the [complete Phone Authentication adapter](AUTHENTICATION_FEATURE.md).
Whole-run cleanup, final journal retirement, the shared standalone observer and
the complete `feature.authentication.act/observe/cleanup` triple are now joined.
Phone Script and Authentication are source-implemented; native code is uncompiled
and all physical qualification remains pending.

## Scope and transaction ownership

Private owner/primary/actor envelopes use `authenticationFeatureVersion: 1`,
an exact run and fixture URL, a closed kind and the existing bounded original
JSON archive encoding. The owner records preparing/baseline/acting/active/
cleaning/cleaned phases, current binding, stage, ticket, exact input, original
backend status and cleanup provenance. Unknown, foreign or interrupted scope
cannot be adopted as a clean run. General cleanup always attempts SDK teardown
and refuses green while any owner, role, source, input, restart or retirement
journal remains; it never discards these files to report success.

The owner admits only the fixture's actual active input. It persists acting
intent before invoking the existing one-send input owner and publishes no state
while an input or cleanup transaction is incomplete. A duplicated acknowledged
call revalidates original scope without replaying input.

Each observer role has its own phase, global sequence, process stage, capture
floor, backend status, last successful original frame and restart archive.
Every returned public field is recomposed from fresh native/Login UI/tablet/
protected HTTP/provider originals. An actor acquires its own HTTP response and
matching original provider fact. The primary cannot borrow or publish that
fact. A new native request nonce also requires a strictly advancing actor
provider-event cursor; a recently captured old event is insufficient.

The active phase is read again after capture. A retired sample is dropped
without changing its ticket or capture time. A protected acquisition rejected
after an actual phase change can use only the still-live source owner's v2
retirement path. A same-ticket source failure remains a failure with retained
reading intent. Actor waiting exceptions leave the source lock before reaching
the publisher, rather than being mistaken for transport failure.

## Independent restart history

For each restart every role must have its own completed original old-process
frame in its own stage journal. The native Test birth, AccountManager birth,
PID and binding must match the original normal-input restart plan. The role
then requests its own new-process kernel ESRCH observation. A primary handoff
cannot fill an absent actor history. New native/account sources must match the
actual new process; global role sequence and capture time never reset.

Archived role transfers retain their old binding/frame, new binding and original
exit receipt. Recreating the owner validates the complete chain, candidate/SDK
immutability and historical source joins before another read. Changed exit
errors, missing old observations or skipped process stages fail closed.

The common journey engine now retains actual mobile visibility counters for
every explicit restart, applying the same already-tested Script rule: exact
launch increment, minimum required activation, no regressed counters and a
settled final window. Original extra backgrounds/activations are not overwritten
with requested increments. New positive coverage includes every area with a
restart; Authentication adds negative launch/activation/regression/unsettled
counterexamples.

The existing native account request timer is an absolute 15 seconds. Pending
dismiss/reopen steps must complete within that real deadline; instrumentation
does not extend it or reinterpret a timeout as a pending request. Host checks do
not qualify device observation latency.

## Verification

Forty `test_authentication_feature.py` cases cover fixture attachment and
input/observer composition with actual shared journal reduction and explicit
synthetic native/SDK/HTTPS seams. Together with source, input and causal tests,
105 focused Authentication cases pass. Native code remains uncompiled, and no
device, installation, build or Jenkins execution was performed.

The complete integration now verifies fresh native/UI/request/file/provider
absence, preserves both roles' own cleanup frames, retires only known hashed
host journals after a new absence verification on each retry, uses the shared
standalone actor and registers the existing triple. The entire unchanged
seventeen-step Authentication journey passes through the existing entrypoint
with synthetic native/SDK/HTTPS seams. See the complete handoff for exact
configuration, cleanup and device-free evidence limits.
