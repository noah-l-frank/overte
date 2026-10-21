"""Bounded independent publisher loop on existing feature ownership journals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.native_feature_observation import need,number
from feature_journeys.witness import Client

VERSION=1


def run(config,*,owner,retirement,actor,pending,retired,observe_during_retirement=False,monotonic=time.monotonic,sleep=time.sleep):
    need(type(observe_during_retirement) is bool and all(callable(value) for value in (owner,retirement,actor,monotonic,sleep)))
    started=previous=monotonic();need(number(started,0,1e15))
    client=Client(config['fixtureUrl'],config['actorToken']);flow=None
    while True:
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<config['durationSeconds']);previous=now
        current=owner()
        if flow is None and current is not None:
            need(current.get('fixtureUrl')==config['fixtureUrl']+'/runs/'+current['runId']+'/')
            flow=actor(current['runId'],client)
        if flow is not None:
            if current is None and flow.role_store.read() is None:return 0
            need(current is not None and current.get('runId')==flow.run)
            plan=retirement()
            if plan is not None:
                need(plan.get('kind')=='retirement' and plan.get('runId')==flow.run and plan.get('fixtureUrl')==flow.fixture_url)
                if not observe_during_retirement:
                    return 0 # These owners already require this role's cleanup originals before the plan.
            try:flow.publish()
            except retired:return 0
            except pending:pass
        sleep(.25)
