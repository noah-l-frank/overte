#!/usr/bin/env python3
"""Independent Graphics publisher and finalization participant for Proxmox.

Attachment uses an existing candidate session and the actor's own credential.
Fixture closure starts paired retirement; only its final receipt permits exit.
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
from adapters.script_feature.lock import ScriptSourceBusy
from adapters.script_feature.history import same
from feature_journeys.witness import Client
from feature_journeys.contract import identifier
from ios.adapters import appium_adapter
from ios.adapters.graphics_configuration import settings
from ios.adapters.graphics_fixture import GraphicsPhasePending,GraphicsRunRetired
from ios.adapters.graphics_finalization import IOSGraphicsFinalization
from ios.adapters.graphics_runtime import IOSGraphicsRuntime

VERSION=1
FAILURE_VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosGraphicsObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds',
                 'artifactRoot','imagePolicy'})
    need(type(value['iosGraphicsObserverVersion']) is int and value['iosGraphicsObserverVersion']==VERSION
         and type(value['target']) is str and 1<=len(value['target'])<=256
         and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
         and all(type(item) is str and bool(item) for item in value['candidateArguments'])
         and number(value['durationSeconds'],30,1800))
    Client(value['fixtureUrl'],value['actorToken']) # Shape only; no connection.
    from feature_journeys.graphics_resources import fixture_url
    fixture_url(value['fixtureUrl'])
    settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
    return value


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSGraphicsRuntime))
    client=Client(config['fixtureUrl'],config['actorToken'])
    selected=settings({key:config[key] for key in ('artifactRoot','imagePolicy')})
    def store(name):return PrivateFeatureState(runtime.state_path(config['target']).with_name(name))
    return run_flow(config,lambda:store('ios-graphics-feature.json').read(),
        lambda:store('ios-graphics-retirement.json').read(),
        lambda run:runtime._graphics_feature(config['target'],run,role='actor',client=client,settings=selected),
        monotonic=monotonic,sleep=sleep)


def failure(flow,config,*,record=False):
    identifier(flow.run)
    store=PrivateFeatureState(Path(config['artifactRoot'])/('graphics-worker-failed-'+flow.run+'.json'))
    expected=dict(iosGraphicsWorkerFailureVersion=FAILURE_VERSION,runId=flow.run,fixtureUrl=flow.fixture_url,
                  artifactRoot=config['artifactRoot'],imagePolicy=config['imagePolicy'])
    previous=store.read()
    if previous is not None:need(same(previous,expected))
    if record and previous is None:store.write(expected,None);previous=store.read();need(same(previous,expected))
    return previous is not None


def run_flow(config,owner,retirement,factory,*,finalizer=IOSGraphicsFinalization,monotonic=time.monotonic,sleep=time.sleep):
    """Keep failures visible while contributing only original actor evidence."""
    started=previous=monotonic();need(number(started,0,1e15));flow=closing=None;failed=False
    while True:
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<config['durationSeconds']);previous=now
        # Read intent first: public control is unavailable once the parent
        # starts retirement, including while feature metadata is being removed.
        plan=retirement();current=owner()
        original=plan if plan is not None else current
        def validate(original):
            need(type(original) is dict and type(original.get('runId')) is str
                 and original.get('fixtureUrl')==config['fixtureUrl']+'/runs/'+original['runId']+'/'
                 and original.get('artifactRoot')==config['artifactRoot'] and same(original.get('imagePolicy'),config['imagePolicy']))
            identifier(original['runId'])
        if original is not None:
            validate(original)
            if flow is None:flow=factory(original['runId'])
            need(original['runId']==flow.run)
        if flow is not None:
            try:
                with flow.lock.held():
                    # Re-read inside the very same reentrant source lock used
                    # by publication/finalization. Retirement cannot race this
                    # choice into a spurious public-operation failure.
                    plan=retirement();current=owner()
                    for original in (plan,current):
                        if original is not None:validate(original);need(original['runId']==flow.run)
                    failed=failure(flow,config) or failed
                    if plan is not None or current is None:closing=True
                    if closing:
                        try:
                            if finalizer(flow).step():return 2 if failed else 0
                        except (GraphicsPhasePending,ScriptSourceBusy):pass
                        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
                            failed=True;failure(flow,config,record=True)
                    elif not failed:
                        try:flow.publish()
                        except GraphicsRunRetired:closing=True
                        except (GraphicsPhasePending,ScriptSourceBusy):pass
                        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
                            # Never replay uncertain delivery to obtain green.
                            failed=True;failure(flow,config,record=True)
            except ScriptSourceBusy:pass
        sleep(.25)


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
        return run(IOSGraphicsRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_GRAPHICS_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
