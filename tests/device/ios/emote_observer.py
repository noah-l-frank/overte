#!/usr/bin/env python3
"""Independent Emote actor on two already prepared candidate-qualified SDKs.

Start before the journey's baseline barrier. This worker creates no session,
installs nothing and obtains no normalized feature facts from the Primary.
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
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhasePending
from ios.adapters import appium_adapter
from ios.adapters.emote_configuration import settings,selector
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_runtime import IOSEmoteRuntime

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosEmoteObserverVersion','target','primaryTarget','runId','candidateArguments','fixtureUrl','actorToken',
                 'durationSeconds','artifactRoot','imagePolicy'})
    need(type(value['iosEmoteObserverVersion']) is int and value['iosEmoteObserverVersion']==VERSION
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800))
    identifier(value['runId']);selector(value['target']);Client(value['fixtureUrl'],value['actorToken'])
    from feature_journeys.graphics_resources import fixture_url
    fixture_url(value['fixtureUrl'])
    settings({key:value[key] for key in ('artifactRoot','imagePolicy','primaryTarget')},role='actor',target=value['target'])
    return value


def failure(flow,config,*,record=False):
    store=PrivateFeatureState(flow.root/('emote-worker-failed-'+flow.run+'.json'))
    expected=dict(iosEmoteWorkerFailureVersion=1,runId=flow.run,fixtureUrl=flow.phase.fixture_url,
        target=config['target'],primaryTarget=config['primaryTarget'],artifactRoot=str(flow.root),imagePolicy=flow.policy)
    previous=store.read()
    if previous is not None:need(same(previous,expected))
    if record and previous is None:store.write(expected,None);need(same(store.read(),expected));previous=expected
    return previous is not None


def run_flow(flow,config,*,monotonic=time.monotonic,sleep=time.sleep):
    started=previous=monotonic();need(number(started,0,1e15));failed=False
    while True:
        now=monotonic()
        if not number(now,previous,started+config['durationSeconds']) or now>=started+config['durationSeconds']:
            failure(flow,config,record=True);return 2
        previous=now
        failed=failure(flow,config) or failed
        try:
            # publish() owns original acquisition/publication and independently
            # switches to final archival only on actual fixture retirement.
            result=flow.publish()
            if result=={'performed':True}:
                with flow.held():
                    value=PrivateFeatureState(flow.runtime.state_path(flow.selector).with_name(
                        'ios-emote-actor-'+flow.run+'-finalization.json')).read()
                    if value is not None:
                        from adapters.script_feature.history import unpack
                        rows=unpack(value['payload'])
                        if len(rows)==1 and rows[0].get('phase')=='complete':return 2 if failed else 0
        except (EmoteObservationPending,ScriptSourceBusy,PhasePending):pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
            # An uncertain once delivery stays in its original owner. Retain
            # failure durably while later ordinary cleanup/finalization runs.
            failed=True;failure(flow,config,record=True)
        sleep(.25)


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSEmoteRuntime))
    selected=settings({key:config[key] for key in ('artifactRoot','imagePolicy','primaryTarget')},role='actor',target=config['target'])
    flow=runtime._emote_feature(config['target'],config['runId'],role='actor',
        client=Client(config['fixtureUrl'],config['actorToken']),settings=selected)
    return run_flow(flow,config,monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True)
    values=parser.parse_args(argv)
    try:
        config=configuration(values.config);need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        args,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],
            '--native-binding',*config['candidateArguments']])
        need(args.platform=='ios' and args.action=='describe' and args.target==config['target']
            and args.operation is None and args.arguments=='{}' and args.native_binding is True
            and args.physical_candidate_metadata is not None and args.candidate_manifest is None)
        adapter=create_adapter(args,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSEmoteRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_EMOTE_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
