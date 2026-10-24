#!/usr/bin/env python3
"""Independent World Web actor on two existing physical candidate SDKs.

Primary-local Web originals are independently queried on that exact primary
SDK. The actor's own SDK retains its separate untouched inventories and OS
retirement. Publication never converts network facts into native observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import sys
import time

DEVICE_ROOT=Path(__file__).resolve().parents[1]
if str(DEVICE_ROOT) not in sys.path:sys.path.insert(0,str(DEVICE_ROOT))
from adapters.native_binding import PrivateParser,create_adapter
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.contract import identifier,VERSION as CONTRACT_VERSION
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.world_web_configuration import settings
from ios.adapters.world_web_resource_disposition import ResourceAdmissionPending
from ios.adapters.world_web_runtime import IOSWorldWebRuntime


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosWorldWebObserverVersion','target','runId','candidateArguments','fixtureUrl','actorToken','durationSeconds','worldWeb'})
    need(type(value['iosWorldWebObserverVersion']) is int and value['iosWorldWebObserverVersion']==1
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800))
    identifier(value['runId']);settings(value['worldWeb'],role='actor',target=value['target']);Client(value['fixtureUrl'],value['actorToken'])
    return value


def failure(flow,*,record=False):
    store=PrivateFeatureState(flow.root/('world-web-worker-failed-'+flow.run+'.json'))
    expected=dict(iosWorldWebWorkerFailureVersion=1,runId=flow.run,fixtureUrl=flow.phase.fixture_url,artifactRoot=str(flow.root),
        imagePolicy=flow.policy,origins=flow.origins,peerTarget=flow.settings['primaryTarget'])
    old=store.read()
    if old is not None:need(same(old,expected))
    if record and old is None:store.write(expected,None);need(same(store.read(),expected));old=expected
    return old is not None


def step(flow):
    """Atomically select live publication or a passive sealed-window wait.

    A seal is control ownership, never a resource-absence receipt. Only the
    existing full historical terminal verifier can permit worker completion.
    """
    from feature_journeys.retirement_receipts import binding_from_context
    from ios.adapters.world_web_terminal import WorldWebTerminal
    with flow.held():
        flow.load()
        store=flow.runtime._world_web_store(flow.primary_selector,'ios-world-web-primary-'+flow.run+'-terminal.json')
        original=store.read()
        if original is not None:
            owner=WorldWebTerminal.from_actor(flow);need(same(original,owner.previous))
            with owner.held():
                state=owner.state;need(state is not None)
                descriptor=state['description'];need(descriptor is not None
                    and descriptor['roles']['primary']['binding']==binding_from_context(owner.flow.state['binding'])
                    and descriptor['roles']['actor']['binding']==binding_from_context(flow.state['binding']))
                if state['phase']=='complete':
                    completed=owner.finish(state['seal'])
                    need(completed['stage']=='finish' and same(completed['end'],state['end']));return 'complete'
                if state['phase'] in ('sealing','sealed','ending'):return 'sealed'
                need(state['phase'] in ('inspecting','inspected'))
        status=flow.phase.status()
        if not status['active']:return 'inactive'
        # The actual publication API owns once-only Actor scene retirement
        # during cleanup and then continues independently acquired live facts.
        # Both source locks stay held from the seal check through acquisition.
        flow.publish();return 'published'


def run_flow(flow,config,*,monotonic=time.monotonic,sleep=time.sleep):
    from ios.adapters.world_web_feature import IOSWorldWebFeature
    need(isinstance(flow,IOSWorldWebFeature) and flow.role=='actor');started=previous=monotonic();need(number(started,0,1e15))
    failed=False
    while True:
        now=monotonic()
        if not number(now,previous,started+config['durationSeconds']) or now>=started+config['durationSeconds']:
            failure(flow,record=True);return 2
        previous=now;failed=failure(flow) or failed
        try:
            selected=step(flow)
            if selected=='complete':return 2 if failed else 0
            if selected=='inactive':failed=True;failure(flow,record=True)
        except (PhasePending,ScriptSourceBusy,ResourceAdmissionPending):pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
            # Ordinary input/publication/Stop/DELETE uncertainty remains in its
            # owning durable once-intent. Retry reads cannot replay any send.
            failed=True;failure(flow,record=True)
        sleep(.15)


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSWorldWebRuntime))
    chosen=settings(config['worldWeb'],role='actor',target=config['target'])
    flow=runtime._world_web_feature(config['target'],config['runId'],role='actor',client=Client(config['fixtureUrl'],config['actorToken']),settings=chosen)
    return run_flow(flow,config,monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True);args=parser.parse_args(argv)
    try:
        config=configuration(args.config);need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        values,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],'--native-binding',*config['candidateArguments']])
        need(values.platform=='ios' and values.action=='describe' and values.target==config['target'] and values.operation is None
            and values.arguments=='{}' and values.native_binding is True and values.physical_candidate_metadata is not None and values.candidate_manifest is None)
        adapter=create_adapter(values,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSWorldWebRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_WORLD_WEB_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
