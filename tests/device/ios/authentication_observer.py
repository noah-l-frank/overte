#!/usr/bin/env python3
"""Independent original Authentication publisher, reserved for Proxmox execution.

No primary credential, desired facts, session creation or target setup is used.
The actor acquires and releases its own original native probe and source frames.
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
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client
from ios import script_observer
from ios.adapters import appium_adapter
from ios.adapters.authentication_runtime import IOSAuthenticationRuntime
from ios.adapters.authentication_origin import origin
from ios.adapters.authentication_feature import AuthenticationPhasePending,AuthenticationRunRetired

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosAuthenticationObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'})
    need(type(value['iosAuthenticationObserverVersion']) is int and value['iosAuthenticationObserverVersion']==VERSION)
    # Reuse the same closed candidate/credential/deadline schema without
    # changing this observer's separate versioned private configuration.
    from adapters.native_feature_observation import number
    need(type(value['target']) is str and 1<=len(value['target'])<=256
         and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
         and all(type(item) is str and bool(item) for item in value['candidateArguments'])
         and number(value['durationSeconds'],30,1800))
    origin(value['fixtureUrl']);Client(value['fixtureUrl'],value['actorToken'])
    return value


def run(adapter,config,*,monotonic=time.monotonic,sleep=time.sleep):
    client=Client(config['fixtureUrl'],config['actorToken'])
    def store(target):return PrivateFeatureState(adapter.state_path(target).with_name('ios-authentication-feature.json'))
    def retirement(target):return PrivateFeatureState(adapter.state_path(target).with_name('ios-authentication-retirement.json'))
    def factory(run):return IOSAuthenticationRuntime(adapter,client,run)._authentication_feature(config['target'],run,role='actor')
    return script_observer.run_flow(config,store,retirement,factory,AuthenticationPhasePending,AuthenticationRunRetired,
        monotonic=monotonic,sleep=sleep)


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
        return run(adapter,config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_AUTHENTICATION_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
