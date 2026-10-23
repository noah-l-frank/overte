"""Existing independent publisher entrypoint through original Browser return.

Only the Proxmox lab owner may provision and bind a candidate. This loop does
not discover/start a target, submit input, reconstruct a live Actor or retry
uncertain source transactions. Never run it against workstation devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time

from adapters.native_feature_observation import need,number
from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
from adapters.script_journey.lock import ScriptSourceBusy
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.witness import Client

VERSION=1


def run(journey,config,*,monotonic=time.monotonic,sleep=time.sleep):
    """One warm original Actor, terminal export, actual Parent nonce, exit."""
    need(config['area']=='tablet-web' and callable(monotonic) and callable(sleep))
    started=previous=monotonic();need(number(started,0,1e15))
    client=Client(config['fixtureUrl'],config['actorToken'])
    source=PhaseFixtureReader(client,config['runId'],'tablet-web',
        epoch_ms=lambda:journey._world_web_clock(config['target']),monotonic=monotonic)
    actor=journey.feature(config['target'],source,config['artifactRoot'],config['foreignFixtureUrl'],
        role='actor',require_new_actor=True)
    need(type(actor) is PicoTabletWebFeature and actor.require_new_actor)
    exported=None
    def bound():
        nonlocal previous
        now=monotonic();need(number(now,previous,started+config['durationSeconds'])
            and now-started<config['durationSeconds']);previous=now
    while True:
        bound()
        if exported is None:
            try:
                with actor.lock.held():
                    if not actor._actor_started:actor.new_actor_sources()
                    current=actor.store.read()
                    if current is not None:
                        need(current.get('runId')==config['runId']
                            and current.get('fixtureUrl')==source.fixture_url)
                if current is not None:
                    try:actor.publish()
                    except PhaseRetired:
                        need(actor._actor_started and actor.actor_retirement is not None
                            and actor.actor_retirement.completed and not actor.actor_retirement.failed)
                        exported=actor.export_original_actor(config['originalRequestId'])
                        exported.publish_return();bound()
            except (PhasePending,ScriptSourceBusy):
                # Pending original input/lock precedes acquisition. Errors from
                # an issued read/publication/export are not retry conditions.
                need(exported is None and actor.actor_retirement is None
                    and (actor.history_cache is None or not actor.history_cache.failed)
                    and (actor.vm_cache is None or not actor.vm_cache.failed))
        if exported is not None:
            exported.verify();exported.sender.control()
            if exported.sender.ack_store.read() is not None:
                exported.consume_return();bound()
                need(exported.sender.consumed and not exported.failed);return 0
        bound();sleep(.25)
