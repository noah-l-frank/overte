#!/usr/bin/env python3
"""Independent Emote actor on two already prepared candidate-qualified SDKs.

Start before the journey's baseline barrier. This worker creates no session,
installs nothing and obtains no normalized feature facts from the Primary.
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
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhasePending
from ios.adapters import appium_adapter
from ios.adapters.emote_configuration import settings,selector
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_runtime import IOSEmoteRuntime

VERSION=3
READS=(1,2,3)


def configuration(path):
    value=PrivateFeatureState(path).read()
    need(type(value) is dict and type(value.get('iosEmoteObserverVersion')) is int and value['iosEmoteObserverVersion'] in READS)
    version=value['iosEmoteObserverVersion']
    exact(value,{'iosEmoteObserverVersion','target','primaryTarget','runId','candidateArguments','fixtureUrl','actorToken',
                 'durationSeconds','artifactRoot','imagePolicy'}|({'primaryArtifactRoot','primaryImagePolicy'} if version>=2 else set())|({'targetPair'} if version>=3 else set()))
    need(type(value['iosEmoteObserverVersion']) is int and value['iosEmoteObserverVersion'] in READS
        and type(value['candidateArguments']) is list and 1<=len(value['candidateArguments'])<=96
        and all(type(item) is str and bool(item) for item in value['candidateArguments'])
        and number(value['durationSeconds'],30,1800))
    identifier(value['runId']);selector(value['target']);Client(value['fixtureUrl'],value['actorToken'])
    from feature_journeys.graphics_resources import fixture_url
    fixture_url(value['fixtureUrl'])
    settings({key:value[key] for key in ('artifactRoot','imagePolicy','primaryTarget')},role='actor',target=value['target'])
    if version>=2:
        settings(dict(artifactRoot=value['primaryArtifactRoot'],imagePolicy=value['primaryImagePolicy'],actorTarget=value['target']),
            role='primary',target=value['primaryTarget'])
        need(value['primaryArtifactRoot']!=value['artifactRoot'])
    if version>=3:
        from ios.adapters.emote_target_pair import configuration as pair_configuration
        pair=pair_configuration(value['targetPair'])
        need(pair['primaryTarget']==value['primaryTarget'] and pair['actorTarget']==value['target']
            and pair['primaryArtifactRoot']==value['primaryArtifactRoot'] and pair['actorArtifactRoot']==value['artifactRoot'])
    return value


def rooted_step(flow,config):
    """Publish before sealing; only the exact paired completed end permits exit."""
    from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
    from ios.adapters.emote_canonical_end import completed
    from adapters.script_feature.history import unpack
    from feature_journeys.retirement_receipts import binding_from_context
    from feature_journeys import terminal
    need(type(flow) is IOSEmoteRootedFeature and flow.role=='actor')
    with flow.held(30):
        flow.load()
        primary=IOSEmoteRootedFeature(flow.runtime,config['primaryTarget'],flow.client,flow.run,'primary',
            config['primaryArtifactRoot'],config['primaryImagePolicy'],actor_selector=flow.selector,
            epoch_ms=flow.epoch_ms,monotonic=flow.monotonic,sleep=flow.sleep,target_pair=getattr(flow,'configured_pair',None))
        primary.lock=primary.primary_lock=flow.primary_lock
        end=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-'+flow.run+'-rooted-end.json')).read()
        if end is not None:
            exact(end,{'iosEmoteRootedEndArchiveVersion','runId','archiveSha256','seal','payload'})
            need(type(end['iosEmoteRootedEndArchiveVersion']) is int and end['iosEmoteRootedEndArchiveVersion']==1
                and end['runId']==flow.run)
            rows=unpack(end['payload']);need(len(rows)==1 and type(rows[0]) is dict
                and rows[0].get('phase') in ('prepared','retiring','complete'))
            terminal.sealed(end['seal']);need(end['seal']['description']['runId']==flow.run)
            if rows[0]['phase']=='complete':
                actual=completed(primary,end['seal'],actor=flow);need(actual['stage']=='finish');return 'complete'
            return 'sealed'
        original=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-'+flow.run+'-terminal.json')).read()
        if original is not None:
            exact(original,{'iosEmoteTerminalJournalVersion','runId','artifactRoot','bindings','locks','payload'})
            need(type(original['iosEmoteTerminalJournalVersion']) is int and original['iosEmoteTerminalJournalVersion']==1
                and original['runId']==flow.run and original['artifactRoot']==str(primary.root)
                and same(original['locks'],dict(primary=str(flow.primary_lock.path),actor=str(flow.lock.path))))
            need(flow.state is not None and same(original['bindings'],
                dict(primary=flow.state['primaryBinding'],actor=flow.state['binding'])))
            rows=unpack(original['payload']);need(len(rows)==1 and type(rows[0]) is dict)
            state=rows[0];terminal.description(state.get('description'),area='emotes',run=flow.run)
            need(all(same(state['description']['roles'][role]['binding'],binding_from_context(binding))
                for role,binding in (('primary',flow.state['primaryBinding']),('actor',flow.state['binding']))))
            if state.get('phase') in ('sealing','sealed'):
                terminal.sealed(state['seal'],state['description']);return 'sealed'
            need(state.get('phase')=='inspected')
        # No live query follows an actual sealed journal or typed end. An
        # inactive fixture without that end remains unresolved responsibility.
        if not flow.phase.status()['active']:return 'inactive'
    # Ordinary observation may have to yield for an original effect or peer.
    # Its own leases/deadline must unwind before that readiness poll; the
    # control-journal read above cannot leave an enclosing SDK lease behind.
    flow.publish();return 'published'


def failure(flow,config,*,record=False):
    store=PrivateFeatureState(flow.root/('emote-worker-failed-'+flow.run+'.json'))
    expected=dict(iosEmoteWorkerFailureVersion=1,runId=flow.run,fixtureUrl=flow.phase.fixture_url,
        target=config['target'],primaryTarget=config['primaryTarget'],artifactRoot=str(flow.root),imagePolicy=flow.policy)
    previous=store.read()
    if previous is not None:need(same(previous,expected))
    if record and previous is None:store.write(expected,None);need(same(store.read(),expected));previous=expected
    return previous is not None


def run_flow(flow,config,*,monotonic=time.monotonic,sleep=time.sleep):
    started=previous=monotonic();need(number(started,0,1e15));failed=False
    while True:
        now=monotonic()
        if not number(now,previous,started+config['durationSeconds']) or now>=started+config['durationSeconds']:
            failure(flow,config,record=True);return 2
        previous=now
        failed=failure(flow,config) or failed
        try:
            if config.get('iosEmoteObserverVersion',1)>=2:
                if rooted_step(flow,config)=='complete':return 2 if failed else 0
                sleep(.25);continue
            # publish() owns original acquisition/publication and independently
            # switches to final archival only on actual fixture retirement.
            result=flow.publish()
            if result=={'performed':True}:
                with flow.held():
                    value=PrivateFeatureState(flow.runtime.state_path(flow.selector).with_name(
                        'ios-emote-actor-'+flow.run+'-finalization.json')).read()
                    if value is not None:
                        from adapters.script_feature.history import unpack
                        rows=unpack(value['payload'])
                        if len(rows)==1 and rows[0].get('phase')=='complete':return 2 if failed else 0
        except (EmoteObservationPending,ScriptSourceBusy,PhasePending):pass
        except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
            # An uncertain once delivery stays in its original owner. Retain
            # failure durably while later ordinary cleanup/finalization runs.
            failed=True;failure(flow,config,record=True)
        sleep(.25)


def run(runtime,config,*,monotonic=time.monotonic,sleep=time.sleep):
    need(isinstance(runtime,IOSEmoteRuntime))
    selected=settings({key:config[key] for key in ('artifactRoot','imagePolicy','primaryTarget')},role='actor',target=config['target'])
    factory=runtime._emote_rooted_feature if config.get('iosEmoteObserverVersion',1)>=2 else runtime._emote_feature
    flow=factory(config['target'],config['runId'],role='actor',
        client=Client(config['fixtureUrl'],config['actorToken']),settings=selected,
        **({'target_pair':config['targetPair']} if config.get('iosEmoteObserverVersion',1)>=3 else {}))
    return run_flow(flow,config,monotonic=monotonic,sleep=sleep)


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
        return run(IOSEmoteRuntime(adapter),config)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError,RecursionError):
        print('IOS_EMOTE_OBSERVER_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
