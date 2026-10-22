"""Selector-free facts from independently acquired original input/UI histories.

No requested verb/checkpoint/state is an argument. Intent only restricts which
actual native original events may be owned; it supplies no measured outcome.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import exact,need,integer,fresh,validate as native_packet
from adapters.pending_commit_owner import validate as pending_packet
from feature_journeys.contract import state as public_state
from overte_phone_lifecycle_editor import validate as editor_packet,advance as editor_advance
from overte_phone_lifecycle_world import validate as world_packet,advance as world_advance
from adapters.native_phone_scene_loads import validate as scene_packet,committed,continuity as scene_continuity
from adapters.native_account_observation import accept as account_continuity
from navigation_observation import FreshNavigation,FIXTURE_MARKERS


def validate_sources(run,frame,pid,epoch):
    exact(frame,{'editor','world','pending','native','sdk','probe','scene'})
    editor,world,pending,native=(frame[key] for key in ('editor','world','pending','native'))
    editor_packet(editor,run,pid,epoch);need(editor['performed'] is False)
    world_packet(world,dict(schemaVersion=1,commandId=world['requestId'],action='phone-lifecycle-world-input',operation='observe',runId=run,gestureId=''),pid,epoch)
    pending_packet(pending,dict(schemaVersion=1,commandId=pending['commandId'],action='feature-pending-commit-owner',operation='observe',runId=run,eventId=''),pid,epoch)
    native_packet(native,native['requestId'],pid,epoch)
    need(editor['instance']==world['instance']==native['instance'])
    sdk=frame['sdk'];exact(sdk,{'tabletVisible','homeVisible','capturedEpochMs'})
    need(type(sdk['tabletVisible']) is bool and type(sdk['homeVisible']) is bool and (not sdk['homeVisible'] or sdk['tabletVisible']))
    fresh(sdk['capturedEpochMs'],epoch)
    need(editor['source']['canonicalSources']['scripts']==pending['canonicalComponentUrl'])
    probe=frame['probe'];exact(probe,{'capturedEpochMs','source'});FreshNavigation().accept(probe['source'])
    actual=probe['source'];need(probe['capturedEpochMs']==actual['sampleEpochMs']);fresh(probe['capturedEpochMs'],epoch)
    need(actual['foreground'] and actual['domain']['serverless'] and not actual['domain']['connected']
        and actual['fixtureMarkers']==FIXTURE_MARKERS and actual['fixtureMarkerCount']==len(FIXTURE_MARKERS)
        and not actual['inAir'] and not actual['flying'] and actual['render']['frameCount']>0)
    need(math.dist(world['motion']['feetPosition'],[actual['feetPosition'][key] for key in ('x','y','z')])<=.025)
    fresh(actual['render']['lastFrameEpochMs'],epoch)
    scene=frame['scene'];scene_packet(scene,dict(schemaVersion=1,commandId=scene['commandId'],action='feature-scene-load-observe',runId=run),pid,epoch)
    need(scene['instance']==native['instance']);committed(scene,actual['sceneUrl'])
    return frame


def continuity_sources(before,after,pid):
    for frame in (before,after):validate_sources(frame['editor']['runId'],frame,pid,max(v['capturedEpochMs'] for v in frame.values()))
    editor_advance(before['editor'],after['editor']);world_advance(before['world'],after['world']);scene_continuity(before['scene'],after['scene'],pid)
    progress=FreshNavigation();progress.accept(before['probe']['source']);progress.accept(after['probe']['source'])
    need(after['probe']['source']['render']['frameCount']>before['probe']['source']['render']['frameCount'])
    a,b=before['native'],after['native'];need(b['instance']==a['instance'] and b['processId']==a['processId'] and b['sequence']>a['sequence']
        and b['capturedEpochMs']>=a['capturedEpochMs'] and all(b['lifecycle'][key]>=a['lifecycle'][key] for key in a['lifecycle'])
        and all(b['account'][key]==a['account'][key] for key in ('loggedIn','principalSha256')))
    if 'observation' in a['account']:need('observation' in b['account']);account_continuity(a['account']['observation'],b['account'])
    a,b=before['pending'],after['pending'];need(b['instance']==a['instance'] and b['sequence']>a['sequence'] and b['canonicalComponentUrl']==a['canonicalComponentUrl']
        and b['capturedEpochMs']>=a['capturedEpochMs'] and b['lastIntentSequence']>=a['lastIntentSequence'])
    if a['commit']:
        need(b['commit'] and all(b['commit'][key]==a['commit'][key] for key in ('fieldToken','captureCommandId')))
        a,b=a['commit']['observation'],b['commit']['observation']
        need(all(b[key]==a[key] for key in ('instance','eventId','processId','createdEpochMs','source')) and b['sequence']>a['sequence']
            and b['elapsedMs']>=a['elapsedMs'] and b['events'][:len(a['events'])]==a['events'])


def measurement(run,frame,baseline,intents,origin,*,pid,epoch,after_epoch):
    validate_sources(run,frame,pid,epoch);validate_sources(run,baseline,pid,max(packet['capturedEpochMs'] for packet in baseline.values()))
    need(type(intents) is list and len(intents)<=256 and type(origin) is list and len(origin)==3 and origin==baseline['world']['motion']['feetPosition'])
    for key in ('editor','world','native'):
        need(frame[key]['instance']==baseline[key]['instance'] and frame[key]['processId']==baseline[key]['processId'])
    need(frame['editor']['source']['instance']==baseline['editor']['source']['instance']
        and frame['world']['source']['instance']==baseline['world']['source']['instance']
        and frame['world']['motion']['instance']==baseline['world']['motion']['instance']
        and frame['pending']['instance']==baseline['pending']['instance'])
    need(all(frame[key]['capturedEpochMs']>=after_epoch for key in ('editor','world','native'))
        and frame['pending']['capturedEpochMs']>=after_epoch and frame['world']['motion']['capturedEpochMs']>=after_epoch
        and frame['probe']['capturedEpochMs']>=after_epoch and frame['scene']['capturedEpochMs']>=after_epoch)
    source=frame['editor']['source'];previous={row['token'] for row in baseline['editor']['source']['contexts']}
    contexts=[row for row in source['contexts'] if row['token'] not in previous]
    need(len(contexts)<=4 and [row['editor'] for row in contexts]==['create','chat','scripts','scripts'][:len(contexts)])
    current=source['current'];generation=0;editor='none';text='';focused=False
    if current['status']=='ready':
        positions=[index for index,row in enumerate(contexts,1) if row['token']==current['token']];need(len(positions)==1)
        generation=positions[0];editor=current['editor'];text=current['text'];focused=current['focused']
        need(frame['sdk']['tabletVisible'] and not frame['sdk']['homeVisible'])
    pending=frame['pending'];native_current=pending['current'];need(native_current['status']!='unavailable')
    if native_current['status']=='ready':
        need(editor=='scripts' and native_current['token']==current['fieldToken'] and native_current['componentUrl']==current['sourceUrl']
            and native_current['text']==current['text'] and native_current['focused']==current['focused']
            and all(abs(a-b)<=.01 for a,b in zip(native_current['frame'],current['frame'])))
    else:need(editor!='scripts')
    commands={row['commandId']:row for row in intents if row.get('action')=='phone-lifecycle-world-input' and row.get('operation')=='hold'}
    actual=frame['world']['source'];owned=[row for row in actual['gestures'] if row['runId']==run]
    need(not any(row['runId']==run for row in baseline['world']['source']['gestures']) and all(row['commandId'] in commands for row in owned)
        and (not actual['pending'] or actual['pendingRun']==run))
    stale=0;deferred=0;commit=pending['commit']
    if commit:
        need(len(contexts)>=3 and contexts[2]['editor']=='scripts' and commit['fieldToken']==contexts[2]['fieldToken'])
        inputs=[row for row in intents if row.get('action')=='feature-pending-commit-owner' and row.get('operation')=='hold']
        need(len(inputs)==1 and commit['captureCommandId']==inputs[0]['commandId'])
        original=commit['observation'];deferred=int(original['pending'])
        if len(original['events'])==2 and original['events'][-1]['kind']=='rejected' and original['events'][-1]['reason']=='context-retired':
            need(len(contexts)==4 and contexts[2]['retiredEpochMs']>0 and not contexts[2]['active']
                and contexts[3]['fieldToken']!=commit['fieldToken'] and contexts[3]['createdEpochMs']>=original['createdEpochMs'])
            stale=1
    need(pending['resources']['pendingRuns']==([run] if deferred else []))
    motion=frame['world']['motion'];need(motion['grounded'] and motion['keyboardPluginActive'])
    x,y,z=motion['effectiveDrive'];need(abs(x)<=1e-6 and abs(y)<=1e-6 and z>=-1e-6)
    held=['forward'] if z>1e-6 else []
    delta={key:motion['feetPosition'][index]-origin[index] for index,key in enumerate(('x','y','z'))}
    distance=math.sqrt(sum(value*value for value in delta.values()))
    facts=public_state('lifecycle-input',dict(editor=editor,text=text,keyboard=source['osKeyboardVisible'],focused=focused,
        heldInputs=held,worldDisplacement=distance,positionDelta=delta,generation=generation,deferredInputs=deferred,
        worldAttempts=sum(row['pressObserved'] for row in owned),staleAttempts=stale),run)
    resources=[]
    if frame['sdk']['tabletVisible']:resources.append('panel:lifecycle-tablet')
    if actual['pending']:resources.append('input:lifecycle-world')
    if deferred:resources.append('input:lifecycle-editor')
    return deepcopy(facts),resources
