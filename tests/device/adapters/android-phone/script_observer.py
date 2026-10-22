#!/usr/bin/env python3
"""Separately credentialed Phone feature observer; run only in the device lab.

This entry point is never launched by host self-tests or by the primary adapter.
It acquires its own original native sources and never invokes primary observe.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import argparse
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent)]
from adapter import parse_args, VerifiedCandidate, EVIDENCE_KEYS
from appium_adapter import PhoneAppiumAdapter
from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client
from overte_phone_script_feature import ScriptPhasePending,ScriptRunRetired
from overte_phone_authentication_feature import AuthenticationPhasePending,AuthenticationRunRetired
from overte_phone_graphics_fixture import GraphicsPhasePending,GraphicsRunRetired
from overte_phone_account_fixture import origin as account_origin
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from overte_phone_script_lock import PhoneScriptSourceBusy
from overte_phone_emote_actor import image_policy
from overte_phone_avatar_people_feature import image_policy as avatar_people_image_policy

SCRIPT_VERSION=1
VERSION=8


def configuration(path):
    value=PrivateFeatureState(path).read()
    if type(value) is dict and 'scriptObserverVersion' in value:
        exact(value,{'scriptObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'})
        need(type(value['scriptObserverVersion']) is int and value['scriptObserverVersion']==SCRIPT_VERSION)
    else:
        exact(value,{'featureObserverVersion','area','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'}
            |({'imagePolicy'} if value.get('featureObserverVersion') in (3,4,5,6,7,8) and value.get('area')=='emotes' else set())
            |({'peerTarget','peerImagePolicy'} if value.get('featureObserverVersion') in (4,5,6,7,8) and value.get('area')=='avatar-people' else set()))
        need(type(value['featureObserverVersion']) is int and value['featureObserverVersion'] in (2,3,4,5,6,7,VERSION)
             and value['area'] in (('scripts','authentication','graphics') if value['featureObserverVersion']==2 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','audio') if value['featureObserverVersion']==3 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people') if value['featureObserverVersion']==4 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people','assets') if value['featureObserverVersion']==5 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people','assets','chat') if value['featureObserverVersion']==6 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people','assets','chat','lifecycle-input') if value['featureObserverVersion']==7 else
                 ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people','assets','chat','lifecycle-input','snapshots')))
        if value['area']=='emotes':image_policy(value['imagePolicy'])
        if value['area']=='authentication':account_origin(value['fixtureUrl'])
        if value['area']=='avatar-people':
            need(type(value['peerTarget']) is str and bool(value['peerTarget']) and value['peerTarget']!=value['target'])
            avatar_people_image_policy(value['peerImagePolicy']);account_origin(value['fixtureUrl'])
    need(type(value['target']) is str and bool(value['target'])
         and type(value['candidateArguments']) is list and len(value['candidateArguments'])<=64
         and all(type(item) is str and item for item in value['candidateArguments'])
         and number(value['durationSeconds'],30,1800))
    Client(value['fixtureUrl'],value['actorToken']) # Exact URL/token shape; no network.
    return value


def run(adapter,config,*,monotonic=time.monotonic,sleep=time.sleep):
    """One owned run; no session repair, child launch or device discovery."""
    started=previous=monotonic();need(number(started,0,1e15))
    client=Client(config['fixtureUrl'],config['actorToken']);flow=None
    area=config.get('area','scripts');need(area in ('scripts','authentication','graphics','emotes','world-web','tablet-web','world-navigation','create','audio','avatar-people','assets','chat','lifecycle-input','snapshots'))
    if area=='avatar-people':return run_avatar_people(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area in ('world-web','tablet-web','audio','lifecycle-input'):return run_world_web(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='assets':return run_assets(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='snapshots':return run_snapshots(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='chat':return run_chat(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='create':return run_create(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='emotes':return run_emote(adapter,config,client,monotonic=monotonic,sleep=sleep)
    if area=='authentication':account_origin(config['fixtureUrl'])
    prefix='navigation' if area=='world-navigation' else area
    owner_store=getattr(adapter,'script_feature_store' if area=='scripts' else prefix+'_feature_store')
    retirement_store=getattr(adapter,'script_retirement_store' if area=='scripts' else prefix+'_retirement_store')
    make_flow=getattr(adapter,'_script_feature' if area=='scripts' else '_'+prefix+'_feature')
    while True:
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<config['durationSeconds']);previous=now
        if flow is None:
            metadata=owner_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==config['fixtureUrl']+'/runs/'+metadata['runId']+'/')
                flow=make_flow(config['target'],metadata['runId'],role='actor',client=client)
        if flow is not None:
            # Primary finalization can retire all journals after this actor's
            # actual cleanup sample. A foreign replacement remains an error.
            metadata=owner_store(config['target']).read()
            if metadata is None and flow.role_store.read() is None:return 0
            need(metadata is not None and metadata.get('runId')==flow.run)
            retirement=retirement_store(config['target']).read()
            if retirement is not None:
                need(retirement.get('kind')=='retirement' and retirement.get('runId')==flow.run
                     and retirement.get('fixtureUrl')==flow.fixture_url)
                if area not in ('graphics','world-navigation'):return 0 # Graphics still owes its independent restored-world window.
            try:flow.publish()
            except (ScriptRunRetired,AuthenticationRunRetired,GraphicsRunRetired,PhaseRetired):return 0
            except (ScriptPhasePending,AuthenticationPhasePending,GraphicsPhasePending,PhasePending,PhoneScriptSourceBusy):pass
        sleep(.25)


def run_avatar_people(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """Independent second Phone: separate target, credentials and PNG sources."""
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,started+config['durationSeconds']));previous=now
        metadata=adapter.avatar_people_feature_store(config['target']).read()
        retirement=adapter.avatar_people_retirement_store(config['target']).read()
        if retirement is not None:
            need(flow is not None and retirement.get('runId')==flow.run and retirement.get('fixtureUrl')==flow.fixture_url
                and retirement.get('kind')=='retirement');return 0
        if metadata is None:
            if flow is not None:
                need(flow.role_store.read() is None);return 0
        else:
            if flow is None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._avatar_people_feature(config['target'],metadata['runId'],role='actor',client=client,
                    peer_selector=config['peerTarget'],peer_policy=config['peerImagePolicy'])
            need(metadata.get('runId')==flow.run)
            try:flow.publish()
            except PhaseRetired:return 0
            except (PhasePending,PhoneScriptSourceBusy):pass
        sleep(.25)


def run_chat(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """Separate actor token and original Phone/AC readers; never input repair."""
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,started+config['durationSeconds']));previous=now
        if flow is None:
            metadata=adapter.chat_feature_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._chat_feature(config['target'],metadata['runId'],role='actor',client=client)
        if flow is not None:
            metadata=adapter.chat_feature_store(config['target']).read()
            if metadata is None and flow.role_store.read() is None:return 0
            need(metadata is not None and metadata.get('runId')==flow.run)
            try:flow.publish()
            except PhaseRetired:flow.retire_actor();return 0
            except (PhasePending,PhoneScriptSourceBusy):pass
        sleep(.25)


def run_world_web(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    from feature_journeys.phase_fixture import PhasePending,PhaseRetired
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,started+config['durationSeconds']));previous=now
        if flow is None:
            prefix=config['area'].replace('-','_')
            metadata=getattr(adapter,prefix+'_feature_store')(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=getattr(adapter,'_'+prefix+'_feature')(config['target'],metadata['runId'],role='actor',client=client)
        if flow is not None:
            try:flow.publish()
            except PhaseRetired:return 0
            except (PhasePending,PhoneScriptSourceBusy):pass
        sleep(.25)


def run_emote(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """The same observer entry point, with independent Emote run ownership."""
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,1e15) and now-started<config['durationSeconds']);previous=now
        if flow is None:
            metadata=adapter.emote_feature_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._emote_actor(config['target'],metadata['runId'],client=client,image_policy=config['imagePolicy'])
        if flow is not None:
            try:
                finished=flow.step();end=monotonic()
                need(number(end,previous,1e15) and end-started<config['durationSeconds']);previous=end
                if finished:return 0
            except PhoneScriptSourceBusy:pass
        sleep(.25)


def run_create(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """Independent actor process; no primary observe or permission credential."""
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,1e15) and now-started<config['durationSeconds']);previous=now
        if flow is None:
            metadata=adapter.create_feature_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._create_actor(config['target'],metadata['runId'],client=client)
        if flow is not None:
            try:
                if flow.step():return 0
            except PhoneScriptSourceBusy:pass
        sleep(.25)


def run_assets(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """Separately credentialed source reader; no primary observe/input path."""
    started=previous=monotonic();flow=None
    while True:
        now=monotonic();need(number(now,previous,1e15) and now-started<config['durationSeconds']);previous=now
        if flow is None:
            metadata=adapter.assets_feature_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._assets_actor(config['target'],metadata['runId'],client=client)
        if flow is not None:
            try:
                if flow.step():return 0
            except PhoneScriptSourceBusy:pass
        sleep(.25)


def run_snapshots(adapter,config,client,*,monotonic=time.monotonic,sleep=time.sleep):
    """Separate original reader/actor; finishing requires its own retirement."""
    started=previous=monotonic();need(number(started,0,1e15));flow=None
    while True:
        now=monotonic();need(number(now,previous,1e15) and now-started<config['durationSeconds']);previous=now
        if flow is None:
            metadata=adapter.snapshots_feature_store(config['target']).read()
            if metadata is not None:
                need(metadata.get('fixtureUrl')==client.url+'/runs/'+metadata['runId']+'/')
                flow=adapter._snapshots_actor(config['target'],metadata['runId'],client=client)
        finished=False
        if flow is not None:
            try:finished=flow.step()
            except PhoneScriptSourceBusy:pass
        need(type(finished) is bool)
        end=monotonic();need(number(end,previous,1e15) and end-started<config['durationSeconds']);previous=end
        if finished:return 0
        sleep(.25)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        config=configuration(args.config)
        need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        candidate_args=parse_args(['describe','--target',config['target'],*config['candidateArguments']])
        need(candidate_args.action=='describe' and candidate_args.target==config['target']
             and candidate_args.operation is None and candidate_args.arguments=='{}')
        fields=('record','artifact','expected_inputs','expected_source_sha','expected_version_code',
                'minimum_version_code','channel',*EVIDENCE_KEYS)
        need(all(getattr(candidate_args,key) is not None for key in fields))
        tier=(candidate_args.build_evidence is not None,candidate_args.expected_artifact_sha256 is not None)
        need(not any(tier) or all(tier))
        candidate=VerifiedCandidate(candidate_args);candidate.verify()
        # This process owns only its actor credential and internal read-only
        # factories. It never advertises or invokes the primary feature triple.
        os.environ['OVERTE_PHONE_FEATURE_SCRIPTS']='0'
        os.environ['OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT']='0'
        os.environ['OVERTE_PHONE_FEATURE_AUTHENTICATION']='0'
        os.environ['OVERTE_PHONE_FEATURE_GRAPHICS']='0'
        os.environ['OVERTE_PHONE_FEATURE_EMOTES']='0'
        os.environ['OVERTE_PHONE_FEATURE_WORLD_NAVIGATION']='0'
        os.environ['OVERTE_PHONE_FEATURE_WORLD_WEB']='0'
        os.environ['OVERTE_PHONE_FEATURE_TABLET_WEB']='0'
        os.environ['OVERTE_PHONE_FEATURE_AUDIO']='0'
        os.environ['OVERTE_PHONE_NORMAL_WEB_REFERENCE']='0'
        os.environ['OVERTE_PHONE_FEATURE_CREATE']='0'
        os.environ['OVERTE_PHONE_FEATURE_ASSETS']='0'
        os.environ['OVERTE_PHONE_FEATURE_AVATAR_PEOPLE']='0'
        os.environ['OVERTE_PHONE_FEATURE_CHAT']='0'
        os.environ['OVERTE_PHONE_FEATURE_SNAPSHOTS']='0'
        os.environ.pop('OVERTE_PHONE_ASSETS_CONFIGURATION',None)
        return run(PhoneAppiumAdapter(candidate),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('PHONE_FEATURE_OBSERVER_REJECTED',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
