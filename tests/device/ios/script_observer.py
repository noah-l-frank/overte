#!/usr/bin/env python3
"""Independent iOS Script publisher; execution is reserved for the Proxmox lab.

The primary adapter never starts this process. It reads its own original native
sources through an existing, candidate-bound SDK session and its actor token.
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
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.script_feature import ScriptPhasePending,ScriptRunRetired

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosScriptObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'})
    need(type(value['iosScriptObserverVersion']) is int and value['iosScriptObserverVersion']==VERSION
         and type(value['target']) is str and 1<=len(value['target'])<=256
         and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
         and all(type(item) is str and bool(item) for item in value['candidateArguments'])
         and number(value['durationSeconds'],30,1800))
    Client(value['fixtureUrl'],value['actorToken']) # Shape only, no network.
    return value


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSScriptRuntime))
    started=previous=monotonic();need(number(started,0,1e15))
    client=Client(config['fixtureUrl'],config['actorToken']);flow=None
    while True:
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<config['durationSeconds']);previous=now
        owner=runtime.script_feature_store(config['target']).read()
        if flow is None and owner is not None:
            need(owner.get('fixtureUrl')==config['fixtureUrl']+'/runs/'+owner['runId']+'/')
            flow=runtime._script_feature(config['target'],owner['runId'],role='actor',client=client)
        if flow is not None:
            if owner is None and flow.role_store.read() is None:return 0
            need(owner is not None and owner.get('runId')==flow.run)
            retirement=runtime.script_retirement_store(config['target']).read()
            if retirement is not None:
                need(retirement.get('kind')=='retirement' and retirement.get('runId')==flow.run
                     and retirement.get('fixtureUrl')==flow.fixture_url)
                return 0 # Both real cleanup samples precede retirement intent.
            try:flow.publish()
            except ScriptRunRetired:return 0
            except (ScriptPhasePending,ScriptSourceBusy):pass
        sleep(.25)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--config',type=Path,required=True)
    values=parser.parse_args(argv)
    try:
        config=configuration(values.config)
        need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        args,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],
            '--native-binding',*config['candidateArguments']])
        need(args.platform=='ios' and args.action=='describe' and args.target==config['target']
             and args.operation is None and args.arguments=='{}' and args.native_binding is True
             and args.physical_candidate_metadata is not None and args.candidate_manifest is None)
        # Construction verifies candidate inputs only. Never call describe,
        # ensure_session, discovery, installation or a primary feature operation.
        adapter=create_adapter(args,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSScriptRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_SCRIPT_OBSERVER_REJECTED',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
