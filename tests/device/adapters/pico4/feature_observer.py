#!/usr/bin/env python3
"""Independent Pico feature publisher for a prebound Proxmox-owned run only.

No target discovery, launching, SDK repair, OpenXR input or credentials for
runner control. Never run this entrypoint against workstation devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_observer import run as publish_owned
from adapters.pico4.authentication_journey import PicoAuthenticationJourney
from adapters.pico4.graphics_journey import PicoGraphicsJourney,artifact_directory
from adapters.graphics_journey.fixture import GraphicsPhasePending,GraphicsRunRetired
from adapters.authentication_journey.fixture import origin
from adapters.authentication_journey.feature import AuthenticationPhasePending,AuthenticationRunRetired
from adapters.script_journey.lock import ScriptSourceBusy
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.pico4.script_observer import run as publish_scripts
from feature_journeys.witness import Client

VERSION=3


def configuration(path):
    value=PrivateFeatureState(path).read()
    graphics=type(value) is dict and value.get('area')=='graphics'
    chat=type(value) is dict and value.get('area')=='chat'
    exact(value,{'picoFeatureObserverVersion','area','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'}
        |({'artifactRoot'} if graphics else set())|({'peerConfig'} if chat else set()))
    need(type(value['picoFeatureObserverVersion']) is int and value['picoFeatureObserverVersion'] in (1,2,3)
         and (not graphics or value['picoFeatureObserverVersion']==2)
         and (not chat or value['picoFeatureObserverVersion']==3)
         and value['area'] in ('authentication','scripts','graphics','chat') and type(value['target']) is str and 1<=len(value['target'])<=256
         and all(33<=ord(c)<127 for c in value['target'])
         and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=80
         and all(type(item) is str and bool(item) for item in value['candidateArguments'])
         and number(value['durationSeconds'],30,1800))
    Client(value['fixtureUrl'],value['actorToken']) # Parse only; no transport.
    if value['area']=='authentication':origin(value['fixtureUrl'])
    if graphics:artifact_directory(value['artifactRoot'])
    if chat:
        need(type(value['peerConfig']) is str)
        peer=Path(value['peerConfig']);need(peer.is_absolute() and peer.resolve(strict=True)==peer)
        need(PrivateFeatureState(peer).read() is not None)
    return value


def run(journey,config,*,monotonic=time.monotonic,sleep=time.sleep):
    if config['area']=='chat':
        from adapters.pico4.chat_cursor_actor import run as publish_chat
        return publish_chat(journey,config,monotonic=monotonic,sleep=sleep)
    if config['area']=='scripts':return publish_scripts(journey,config,monotonic=monotonic,sleep=sleep)
    if config['area']=='graphics':
        return publish_owned(config,owner=lambda:journey.graphics_feature_store(config['target']).read(),
            retirement=lambda:journey.graphics_retirement_store(config['target']).read(),
            actor=lambda run,client:journey._graphics_feature(config['target'],run,role='actor',client=client),
            pending=(GraphicsPhasePending,ScriptSourceBusy),retired=GraphicsRunRetired,observe_during_retirement=True,
            monotonic=monotonic,sleep=sleep)
    need(config['area']=='authentication')
    return publish_owned(config,owner=lambda:journey.authentication_feature_store(config['target']).read(),
        retirement=lambda:journey.authentication_retirement_store(config['target']).read(),
        actor=lambda run,client:journey._authentication_feature(config['target'],run,role='actor',client=client),
        pending=(AuthenticationPhasePending,ScriptSourceBusy),retired=AuthenticationRunRetired,
        monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--config',type=Path,required=True);args=parser.parse_args(argv)
    try:
        need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        config=configuration(args.config)
        from adapters.android import adapter
        candidate,binding=adapter.cli(['--kind','pico','--native-binding',*config['candidateArguments'],
            'describe','--target',config['target']])
        need(candidate.native_binding and candidate.kind=='pico' and candidate.action=='describe'
             and candidate.target==config['target'] and candidate.operation is None and candidate.arguments=='{}')
        os.environ['OVERTE_PICO_FEATURE_SCRIPTS']=os.environ['OVERTE_PICO_FEATURE_AUTHENTICATION']='0'
        os.environ['OVERTE_PICO_FEATURE_GRAPHICS']='0'
        original=binding.create_adapter(candidate,adapter.AndroidAdapter)
        journey=(original if config['area']=='chat' else PicoAuthenticationJourney(original) if config['area']=='authentication' else
            PicoGraphicsJourney(original,artifact_root=config['artifactRoot']) if config['area']=='graphics' else PicoScriptJourney(original))
        return run(journey,config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('OVT_PICO_FEATURE_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
