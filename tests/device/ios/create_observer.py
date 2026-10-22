#!/usr/bin/env python3
"""Independent Create actor on an existing candidate-bound iOS SDK session.

Execution belongs to the Proxmox laboratory. The primary does not start this
process, create a session or supply its own expected facts to this reader.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import time

DEVICE_ROOT=Path(__file__).resolve().parents[1]
if str(DEVICE_ROOT) not in sys.path:sys.path.insert(0,str(DEVICE_ROOT))
from adapters.native_binding import PrivateParser,create_adapter
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.create_configuration import settings
from ios.adapters.create_runtime import IOSCreateRuntime


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosCreateObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds','create'})
    need(type(value['iosCreateObserverVersion']) is int and value['iosCreateObserverVersion']==1
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and item for item in value['candidateArguments']) and number(value['durationSeconds'],30,1800))
    settings(value['create'],role='actor',target=value['target']);Client(value['fixtureUrl'],value['actorToken']);return value


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSCreateRuntime));client=Client(config['fixtureUrl'],config['actorToken'])
    primary=config['create']['primaryTarget'];flow=None;started=previous=monotonic()
    while True:
        now=monotonic();need(number(now,previous,started+config['durationSeconds']) and now-started<config['durationSeconds']);previous=now
        # This is run/ownership metadata only. Native sources and independent
        # facts are acquired by the actor's own typed owners after admission.
        owner=runtime._create_store(primary,'ios-create-primary-feature.json').read()
        if flow is None and owner is not None:
            need(owner.get('role')=='primary' and owner.get('fixtureUrl')==config['fixtureUrl']+'/runs/'+owner['runId']+'/')
            flow=runtime._create_feature(config['target'],owner['runId'],role='actor',client=client,settings=config['create'])
        if flow is not None:
            need(owner is not None and owner['runId']==flow.run)
            try:
                flow.publish()
                with flow.held():
                    flow.load()
                    if flow.state['phase']=='retired':return 0
            except (PhasePending,ScriptSourceBusy):pass
        sleep(.15)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True);args=parser.parse_args(argv)
    try:
        config=configuration(args.config)
        values,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],'--native-binding',*config['candidateArguments']])
        need(values.platform=='ios' and values.action=='describe' and values.target==config['target'] and values.operation is None
            and values.arguments=='{}' and values.native_binding is True and values.physical_candidate_metadata is not None and values.candidate_manifest is None)
        adapter=create_adapter(values,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSCreateRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_CREATE_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
