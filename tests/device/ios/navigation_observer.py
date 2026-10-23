#!/usr/bin/env python3
"""Independent Worlds originals on one explicitly existing qualified iOS SDK.

The worker pauses acquisitions atomically after the original paired seal. Only
actual historical process/SDK completion permits exit; a fixture ACK does not.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import re
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
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.graphics_resources import fixture_url
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_fixture import NavigationPhasePending
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.adapters.navigation_whole_feature import NavigationWholeFeature

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosNavigationObserverWorkerVersion','target','runId','candidateArguments','fixtureUrl','actorToken',
        'durationSeconds','artifactRoot'})
    need(type(value['iosNavigationObserverWorkerVersion']) is int and value['iosNavigationObserverWorkerVersion']==VERSION
        and type(value['target']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',value['target'])
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800) and type(value['artifactRoot']) is str)
    identifier(value['runId']);fixture_url(value['fixtureUrl']);Client(value['fixtureUrl'],value['actorToken'])
    root=Path(value['artifactRoot']);need(root.is_absolute() and root.resolve()==root and root.is_dir())
    PrivateFeatureState(root/'navigation-worker-configuration-check')._parent();return value


def primary(flow):
    """Reopen the same owner namespace without acquiring a product source."""
    need(type(flow) is IOSNavigationFeature and flow.role=='actor')
    result=IOSNavigationFeature(flow.runtime,flow.selector,flow.client,flow.run,flow.root,role='primary',
        epoch_ms=flow.epoch_ms,monotonic=flow.monotonic,sleep=flow.sleep)
    result.lock=flow.lock;return result


def failure(flow,config,*,record=False):
    flow.lock.assert_held()
    store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-worker-failure.json'))
    expected=dict(iosNavigationWorkerFailureVersion=1,runId=flow.run,target=config['target'],
        fixtureUrl=flow.client.url,artifactRoot=str(flow.root))
    old=store.read()
    if old is not None:need(same(old,expected))
    if record and old is None:store.write(expected,None);need(same(store.read(),expected));old=expected
    return old is not None


def step(whole,config):
    """One publication, or a sealed pause, or fully verified historical end."""
    need(type(whole) is NavigationWholeFeature);flow=whole.flow
    with flow.held():
        failed=failure(flow,config);owner=NavigationTerminal(primary(flow))
        if owner.state is not None and owner.state['seal'] is not None:
            # Do not write even a worker marker after the immutable source-file
            # inventory was admitted. No native, fixture or SDK read while the
            # independent primary finalizer still owns process/SDK completion.
            archive=PrivateFeatureState(flow.store.path.with_name('ios-navigation-final-archive.json'))
            if archive.read() is None:return None
            owner.finish(owner.state['seal']);return 2 if failed else 0
        try:whole.publish()
        except (NavigationFeaturePending,NavigationPhasePending,PhasePending,MarkerNotReady):pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):failure(flow,config,record=True)
    return None


def run_flow(whole,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(type(whole) is NavigationWholeFeature and whole.flow.role=='actor')
    started=previous=monotonic();need(number(started,0,1e15))
    while True:
        now=monotonic()
        if not number(now,previous,started+config['durationSeconds']) or now>=started+config['durationSeconds']:
            # Timeout is failure, never process/resource absence. Preserve the
            # entire ownership graph; an admitted immutable seal stays intact.
            return 2
        previous=now
        try:
            result=step(whole,config)
            if result is not None:return result
        except ScriptSourceBusy:pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):return 2
        sleep(.25)


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSNavigationRuntime))
    flow=IOSNavigationFeature(runtime,config['target'],Client(config['fixtureUrl'],config['actorToken']),
        config['runId'],config['artifactRoot'],role='actor')
    return run_flow(NavigationWholeFeature(flow),config,monotonic=monotonic,sleep=sleep)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True)
    values=parser.parse_args(argv)
    try:
        config=configuration(values.config);need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        args,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],'--native-binding',*config['candidateArguments']])
        need(args.platform=='ios' and args.action=='describe' and args.target==config['target'] and args.operation is None
            and args.arguments=='{}' and args.native_binding is True and args.physical_candidate_metadata is not None and args.candidate_manifest is None)
        adapter=create_adapter(args,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSNavigationRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_NAVIGATION_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
