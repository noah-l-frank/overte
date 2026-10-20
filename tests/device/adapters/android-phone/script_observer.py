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
from overte_phone_account_fixture import origin as account_origin
from overte_phone_script_lock import PhoneScriptSourceBusy

SCRIPT_VERSION=1
VERSION=2


def configuration(path):
    value=PrivateFeatureState(path).read()
    if type(value) is dict and 'scriptObserverVersion' in value:
        exact(value,{'scriptObserverVersion','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'})
        need(type(value['scriptObserverVersion']) is int and value['scriptObserverVersion']==SCRIPT_VERSION)
    else:
        exact(value,{'featureObserverVersion','area','target','candidateArguments','fixtureUrl','actorToken','durationSeconds'})
        need(type(value['featureObserverVersion']) is int and value['featureObserverVersion']==VERSION
             and value['area'] in ('scripts','authentication'))
        if value['area']=='authentication':account_origin(value['fixtureUrl'])
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
    area=config.get('area','scripts');need(area in ('scripts','authentication'))
    if area=='authentication':account_origin(config['fixtureUrl'])
    owner_store=adapter.authentication_feature_store if area=='authentication' else adapter.script_feature_store
    retirement_store=adapter.authentication_retirement_store if area=='authentication' else adapter.script_retirement_store
    make_flow=adapter._authentication_feature if area=='authentication' else adapter._script_feature
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
                return 0 # Its actual cleanup observation was verified before this plan.
            try:flow.publish()
            except (ScriptRunRetired,AuthenticationRunRetired):return 0
            except (ScriptPhasePending,AuthenticationPhasePending,PhoneScriptSourceBusy):pass
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
        os.environ['OVERTE_PHONE_FEATURE_AUTHENTICATION']='0'
        return run(PhoneAppiumAdapter(candidate),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('PHONE_FEATURE_OBSERVER_REJECTED',file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
