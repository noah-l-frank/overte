#!/usr/bin/env python3
"""Independent Avatar actor using two already qualified existing iOS SDKs.

Publisher and authority-read credentials have separate explicit roles. This
worker creates no SDK session and treats peer handoffs only as ordering.
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
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.avatar_configuration import settings,selector
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_login_owner import AvatarLoginPending
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_sources import AvatarPhaseChanged,AvatarSourcePending
from ios.adapters.avatar_samples import AvatarImagePhaseChanged
from ios.adapters.avatar_surface import AvatarSurfacePending

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosAvatarObserverVersion','target','primaryTarget','runId','candidateArguments','fixtureUrl','actorToken',
        'authorityRead','durationSeconds','artifactRoot','imagePolicy'})
    need(type(value['iosAvatarObserverVersion']) is int and value['iosAvatarObserverVersion']==VERSION
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800))
    identifier(value['runId']);selector(value['target']);Client(value['fixtureUrl'],value['actorToken'])
    from feature_journeys.graphics_resources import fixture_url
    fixture_url(value['fixtureUrl'])
    settings({key:value[key] for key in ('artifactRoot','imagePolicy','primaryTarget','authorityRead')},role='actor',target=value['target'])
    return value


def failure(flow,config,*,record=False):
    store=PrivateFeatureState(flow.root/('avatar-worker-failed-'+flow.run+'.json'))
    expected=dict(iosAvatarWorkerFailureVersion=1,runId=flow.run,fixtureUrl=flow.phase.fixture_url,
        target=config['target'],primaryTarget=config['primaryTarget'],artifactRoot=str(flow.root),imagePolicy=flow.policy)
    old=store.read()
    if old is not None:need(same(old,expected))
    if record and old is None:store.write(expected,None);need(same(store.read(),expected));old=expected
    return old is not None


def run_flow(flow,config,*,monotonic=time.monotonic,sleep=time.sleep):
    started=previous=monotonic();need(number(started,0,1e15));failed=False
    while True:
        now=monotonic()
        if not number(now,previous,started+config['durationSeconds']) or now>=started+config['durationSeconds']:
            failure(flow,config,record=True);return 2
        previous=now;failed=failure(flow,config) or failed
        try:
            # An actual stored end is already a complete historical authority.
            # It does not depend on the fixture HTTP server still being alive.
            aborted=getattr(flow,'failed_preparation_ended',None)
            if callable(aborted) and aborted():return 2
            with flow.held():flow.load();held=flow.state is not None and flow.state['phase']=='terminal-ready'
            if held and flow.terminal_actor_ended():return 2 if failed else 0
            status=flow.phase.status()
            if not status['active']:
                aborted=getattr(flow,'failed_preparation_ended',None)
                if callable(aborted) and aborted():return 2
                with flow.held():flow.load();held=flow.state is not None and flow.state['phase']=='terminal-ready'
                if held:
                    if flow.terminal_actor_ended():return 2 if failed else 0
                elif flow.finalize()==dict(performed=True):return 2 if failed else 0
            elif status['activations'] and status['activations'][-1]['stimulus']['verb']=='cleanup':
                with flow.held():flow.load();cleaned=flow.state is not None and flow.state['phase'] in ('cleaned','terminal-ready')
                if not cleaned:flow.cleanup(dict(contractVersion=CONTRACT_VERSION,runId=flow.run))
                with flow.held():flow.load();held=flow.state['phase']=='terminal-ready'
                if held:flow.observe(dict(contractVersion=CONTRACT_VERSION,runId=flow.run,afterSequence=0))
                # Complete is distinct from fixture retirement. Keep this
                # original SDK alive for the independent canonical finalizer.
            else:
                flow.observe(dict(contractVersion=CONTRACT_VERSION,runId=flow.run,afterSequence=0))
        except (AvatarFeaturePending,AvatarLoginPending,ScriptSourceBusy,PhasePending,MarkerNotReady,AvatarPhaseChanged,AvatarSourcePending,AvatarImagePhaseChanged,AvatarSurfacePending):pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
            # A failed return stays in its original owner. Later cleanup must
            # reconcile actual sources rather than repeat an uncertain input.
            failed=True;failure(flow,config,record=True)
        sleep(.25)


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSAvatarRuntime))
    selected=settings({key:config[key] for key in ('artifactRoot','imagePolicy','primaryTarget','authorityRead')},role='actor',target=config['target'])
    flow=IOSAvatarFeature(runtime,config['target'],Client(config['fixtureUrl'],config['actorToken']),config['runId'],'actor',selected)
    return run_flow(flow,config,monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True)
    values=parser.parse_args(argv)
    try:
        config=configuration(values.config);need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        args,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],'--native-binding',*config['candidateArguments']])
        need(args.platform=='ios' and args.action=='describe' and args.target==config['target'] and args.operation is None
            and args.arguments=='{}' and args.native_binding is True and args.physical_candidate_metadata is not None and args.candidate_manifest is None)
        adapter=create_adapter(args,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSAvatarRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_AVATAR_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
