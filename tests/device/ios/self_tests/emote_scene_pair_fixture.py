"""Schedule independently owned role work only after real SDK leases release.

All product/native producers remain modeled. The actual owners, immutable files,
loopback phase journals, normal W3C input and original temporal joins are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext,contextmanager
from adapters.native_feature_observation import need
from ios.adapters.emote_operation import operation
from ios.adapters.emote_scene_operation import retry_scene


@operation(60)
@retry_scene
def local_retirement(flow,after_sequence=0):
    """Acquire the genuine whole local closure, without publishing expectations."""
    with flow.held():
        flow.load();flow.phase.status();parts=flow.components();flow.clean_local(parts)
        return flow.retirement_sample(parts,after_sequence)


def connect(primary,actor):
    """One actual SDK directory per target, and deterministic outside-lock work."""
    primary.actor=actor;primary.scene_events=[];primary.scene_running=set()
    for fixture in (actor.target.fixture,primary.target.f.fixture):
        fixture.held.__exit__(None,None,None);fixture.held=nullcontext()
    for owner,other in ((primary,actor),(actor,primary)):
        held=owner.flow.held
        @contextmanager
        def diagnosed(*args,held=held,**kwargs):
            with held(*args,**kwargs):
                try:yield
                except Exception:
                    import traceback;traceback.print_exc();raise
        owner.flow.held=diagnosed
        original=owner.target.domain.sleep
        def waiting(seconds,owner=owner,other=other,original=original):
            if owner.flow.lock._owner is None and owner.flow.primary_lock._owner is None:
                need(other.flow.lock._owner is None and other.flow.primary_lock._owner is None)
                role=other.flow.role;need(role not in primary.scene_running)
                primary.scene_running.add(role);primary.scene_events.append((owner.flow.role,role))
                try:
                    owner.flow.phase.status()
                    if owner.flow.phase.previous['active']:
                        other.flow.observe(dict(contractVersion=16,runId=owner.flow.run,afterSequence=0))
                    else:local_retirement(other.flow)
                finally:primary.scene_running.remove(role)
            original(seconds)
        owner.flow.sleep=waiting
    return primary


def paired(test):
    from ios.self_tests.emote_whole_primary_fixture import WholePrimaryFixture
    from ios.self_tests.emote_whole_actor_fixture import WholeActorFixture
    primary=WholePrimaryFixture(test);actor=WholeActorFixture(test,primary)
    return connect(primary,actor)
