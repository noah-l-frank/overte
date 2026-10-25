#!/usr/bin/env python3
"""Independent original Tablet sources on one already prepared physical SDK.

Start before the normal first open. No session is created, no app is staged,
no normalized Primary facts are read and no app Stop/SDK deletion is issued.
The whole owner keeps host worker/query responsibility private. After a genuine
paired live seal this same process obtains its own old-PID OS originals; only
Primary can Stop/delete the shared SDK.
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
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.phase_witness_publisher import PublicationPending
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.witness import Client
from ios.adapters import appium_adapter
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime,TabletObservationPending
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.adapters.tablet_web_terminal_finish import actor_step
from ios.adapters.tablet_web_source_owner import TabletSourcePhaseChanged
from ios.adapters.world_web_measurements import origin

VERSION=1


def configuration(path):
    value=PrivateFeatureState(path).read()
    exact(value,{'iosTabletWebObserverVersion','target','runId','candidateArguments','fixtureUrl','actorToken',
        'durationSeconds','physicalBinding','setupNative','origins','screen'})
    need(type(value['iosTabletWebObserverVersion']) is int and value['iosTabletWebObserverVersion']==VERSION
        and type(value['target']) is str and 0<len(value['target'])<=256
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800))
    identifier(value['runId']);Client(value['fixtureUrl'],value['actorToken']);context(value['physicalBinding'])
    from feature_journeys.navigation_scene import resource_root
    resource_root(value['fixtureUrl']+'/runs/'+value['runId']+'/',value['runId'])
    exact(value['origins'],{'primary','foreign'});need(origin(value['origins']['primary'])!=origin(value['origins']['foreign']))
    from adapters.native_feature_observation import validate
    native=value['setupNative'];validate(native,native['requestId'],int(value['physicalBinding']['processIdentity']),native['capturedEpochMs'])
    exact(value['screen'],{'artifactRoot','policy'});root=Path(value['screen']['artifactRoot']);need(root.is_absolute() and root.resolve()==root and root.is_dir())
    exact(value['screen']['policy'],{'source','marker','subject'});need(value['screen']['policy']['source']=='native-screen')
    return value


def run(runtime,config,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSTabletWebRuntime));started=last=monotonic();need(number(started,0,1e15))
    client=Client(config['fixtureUrl'],config['actorToken'])
    feature=IOSTabletWebFeature(runtime,config['target'],client,config['runId'],'actor',config['physicalBinding'],config['setupNative'],config['origins'],
        epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,screen=config['screen'])
    failed=PrivateFeatureState(runtime.state_path(config['target']).with_name('tabletweb-worker-failed-'+config['runId']+'.json'))
    expected=dict(tabletWebWorkerFailureVersion=1,runId=config['runId'],binding=config['physicalBinding'],hostProcessId=os.getpid())
    while True:
        now=monotonic()
        if not number(now,last,started+config['durationSeconds']) or now>=started+config['durationSeconds']:return 2
        last=now
        try:
            previous=failed.read()
            if previous is not None:need(same(previous,expected));return 2
            with feature.operation():
                terminal=actor_step(feature)
                if terminal is True:return 0
                if terminal is None:feature.publish()
        except (ScriptSourceBusy,TabletSourcePhaseChanged,TabletObservationPending,PublicationPending):pass
        except PhaseRetired:
            # A real prior paired seal can park this worker until Primary's
            # once-Stop intent arrives. Retirement alone is never permission.
            with feature.operation():
                terminal=actor_step(feature)
                if terminal is True:return 0
                if terminal is None:return 2
        except PhasePending:pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
            old=failed.read()
            if old is None:failed.write(expected,None)
            else:need(same(old,expected))
            return 2  # Preserve the failed source; never start a replacement query.
        sleep(.25)


def main(argv=None):
    parser=PrivateParser(description=__doc__,allow_abbrev=False);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        config=configuration(args.config);need('OVERTE_E2E_FEATURE_READER_TOKEN' not in os.environ)
        selected,binding=appium_adapter.cli(['--platform','ios','describe','--target',config['target'],'--native-binding',*config['candidateArguments']])
        need(selected.platform=='ios' and selected.action=='describe' and selected.target==config['target']
            and selected.operation is None and selected.arguments=='{}' and selected.native_binding is True
            and selected.physical_candidate_metadata is not None and selected.candidate_manifest is None)
        adapter=create_adapter(selected,binding,appium_adapter.AppiumAdapter,'ios')
        return run(IOSTabletWebRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_TABLET_WEB_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
