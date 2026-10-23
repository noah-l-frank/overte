"""Original Pico document and surface bracketed around one submitted stereo frame.

This proves source provenance only. The independent verifier must still measure
the run/ticket challenge and subject in each actual eye's original pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.native_web_runtime import continuity as runtime_continuity
from adapters.normal_script_manager import diagnostic
from adapters.normal_feature_state import context
from adapters.navigation_arrival import stereo_pose
from adapters.pico4.browser_source import validate as browser_packet,continuity
from adapters.pico4.browser_measurements import browser_status,measurement
from adapters.pico4.graphics_source import validate as ui_packet,accept_inventory,PROFILES
from adapters.pico4.graphics_composition import validate as composition

VERSION=1
WORLD_VERSION=1
FIELDS={'picoBrowserStereoSourceVersion','runId','binding','fixtureUrl','foreignFixtureUrl','ownerToken','scriptUrl',
    'before','after','capture','nativeBefore','nativeAfter','uiBefore','uiAfter','browserBefore','browserAfter',
    'runtimeBefore','runtimeAfter','scriptsBefore','scriptsAfter','httpBefore','httpAfter'}


def surface(value):
    need(type(value) is dict)
    tablet='picoBrowserStereoSourceVersion' in value
    world='picoWorldBrowserStereoSourceVersion' in value
    need(tablet != world)
    return 'tablet' if tablet else 'world'


def fields(kind):
    need(type(kind) is str and kind in ('tablet','world'))
    return FIELDS if kind=='tablet' else (FIELDS-{'picoBrowserStereoSourceVersion'})|{'picoWorldBrowserStereoSourceVersion','worldBefore','worldAfter'}


def source_version(kind):
    need(type(kind) is str and kind in ('tablet','world'))
    return {'picoBrowserStereoSourceVersion':VERSION} if kind=='tablet' else {'picoWorldBrowserStereoSourceVersion':WORLD_VERSION}


def world_surface(packet,browser,request,pid,epoch):
    """Actual passive entity/item geometry, never a tablet or desired quad."""
    from adapters.pico4.browser_source import geometry_original,IDENTITY
    browser_packet(packet,request,pid,epoch)
    need(packet['status']=='ready' and packet['picoBrowserVersion']==3)
    current=browser['source']['current'];need(bool(current))
    view=current['source']['nativeView'];ray=packet['source']['worldRay']
    need(packet['instance']==browser['instance'] and packet['source']['nativeView']=={key:view[key] for key in IDENTITY}
        and ray['sourceIdentity']==view['sourceIdentity'] and ray['sourceUrl']==view['sourceUrl'])
    dom=geometry_original(packet['source']['geometryRaw'],request,view['url'],epoch)
    need(dom['document']==current['source']['dom']['document'])
    return ray,dom


def current_document(packet):
    current=packet['source']['current'];need(bool(current))
    # Sequence/request/clock remain originals in the enclosing packet; these
    # actual effect fields must remain unchanged across the exposure.
    source=current['source'];dom=source['dom']
    return dict(nativeView=deepcopy(source['nativeView']),document=deepcopy(dom['document']),
        editor=deepcopy(dom['editor']),attempts=deepcopy(dom['attempts']),echoes=deepcopy(dom['echoes']),
        **({'inline':deepcopy(source['inline'])} if 'inline' in source else {}))


def shown_tablet(ui,pose):
    need(ui['graphicsObservationVersion']==2 and ui['tabletShown'])
    value=composition(ui['composition']);need(value['complete'])
    framework=pose['subject']['source']['framework'];screen=value['screen']
    need(screen['id']==framework['tablet']['screen'] and screen['parentId']==framework['tablet']['frame']
        and screen['visible'] and screen['alpha']==1 and screen['pulseAlphaMode']==0)
    rows={row['id']:row for row in framework['entities']}
    need(screen['id'] in rows and screen['parentId'] in rows and rows[screen['id']]['present']
        and rows[screen['parentId']]['present'] and rows[screen['id']]['type']=='Web'
        and rows[screen['id']]['parentId']==screen['parentId'])
    for ancestor in value['ancestors']:
        need(ancestor['visible'] and ancestor['opacity']==1 and not ancestor['maskPresent'])
    # A raised original VR keyboard is retained, never turned into a closed
    # tablet Navigation prerequisite. Per-eye pixels qualify any occlusion.
    need(ui['graphicsInventory']['keyboard3D']['raised']==framework['keyboard']['raised'])
    return value


def validate(value,raw,run,binding,scene_url):
    kind=surface(value);version=source_version(kind);exact(value,fields(kind));context(binding)
    need(all(type(value[key]) is int and value[key]==number for key,number in version.items())
        and value['runId']==run and value['binding']==binding)
    pid=int(binding['processIdentity'].split(':',1)[0]);a,b=value['nativeBefore'],value['nativeAfter'];end=b['capturedEpochMs']
    before,after,capture=value['before'],value['after'],value['capture']
    facts=stereo_pose(before,capture,after,raw,run,binding,scene_url,end,require_location=False)
    for packet in (a,b):
        native_packet(packet,packet.get('requestId'),pid,end);need(integer(packet.get('requestedEpochMs'),1))
    need(a['instance']==b['instance']==before['subject']['instance'] and b['sequence']>a['sequence']
        and a['requestId']!=b['requestId'] and a['lifecycle']==b['lifecycle'] and a['graphics']==b['graphics']
        and a['capturedEpochMs']<=before['probe']['sampleEpochMs'] and after['subject']['capturedEpochMs']<=b['requestedEpochMs'])
    ui_a,ui_b=value['uiBefore'],value['uiAfter']
    for ui,pose in ((ui_a,before),(ui_b,after)):
        ui_packet(ui,ui.get('commandId'),pid,end)
        if kind=='tablet':shown_tablet(ui,pose)
        else:
            # An actual open tablet can occlude the world surface. Its absence
            # is measured independently; no tablet composition is relabelled.
            need(not ui['tabletShown'] and ui['graphicsInventory']['keyboard3D']['raised']==pose['subject']['source']['framework']['keyboard']['raised'])
    accept_inventory(ui_a['graphicsInventory'],ui_b['graphicsInventory'],profiles=PROFILES)
    need(ui_a['instance']==ui_b['instance'] and ui_a['generation']==ui_b['generation']
        and ui_b['sourceSequence']>ui_a['sourceSequence'] and ui_b['elapsedMs']>=ui_a['elapsedMs']
        and ui_a['lastCommandSequence']==ui_b['lastCommandSequence'] and ui_a['commandId']!=ui_b['commandId']
        and ui_a['composition']==ui_b['composition'] and ui_a['editorFocused']==ui_b['editorFocused']
        and before['subject']['capturedEpochMs']<=ui_a['capturedEpochMs']<=capture['requestedEpochMs']
        and capture['capturedEpochMs']<=ui_b['capturedEpochMs']<=after['probe']['sampleEpochMs'])
    epochs=[a['requestedEpochMs'],before['probe']['sampleEpochMs'],before['probe']['nativeMotion']['sampleEpochMs'],
        before['probe']['render']['lastFrameEpochMs'],before['subject']['requestedEpochMs'],capture['source']['recordedEpochMs']]
    measured=[]
    for suffix in ('Before','After'):
        browser=value['browser'+suffix];runtime=value['runtime'+suffix];http=value['http'+suffix];scripts=value['scripts'+suffix]
        request=dict(schemaVersion=1,commandId=browser['commandId'],action='pico-'+kind+'-web',runId=run,
            fixtureUrl=value['fixtureUrl'],ownerToken=value['ownerToken'],operation='observe')
        browser_packet(browser,request,pid,end);need(browser['status']=='ready' and browser['picoBrowserVersion']==2)
        browser_status(http);diagnostic(scripts,end)
        state,resources=measurement(run,value['fixtureUrl'],value['foreignFixtureUrl'],browser,http,runtime,
            scripts['scripts'],value['scriptUrl'],area=kind+'-web')
        need(state['open']);measured.append(state)
        current=browser['source']['current'];need(bool(current))
        if kind=='world':
            geometry=value['world'+suffix];view=current['source']['nativeView']
            query=dict(schemaVersion=1,commandId=geometry['commandId'],action='pico-world-web',runId=run,
                fixtureUrl=value['fixtureUrl'],ownerToken=value['ownerToken'],operation='measure-ray',control='text',
                **{key:view[key] for key in ('handle','creation','grant','page')})
            ray,dom=world_surface(geometry,browser,query,pid,end)
            original_epochs=(geometry['capturedEpochMs'],ray['capturedEpochMs'],dom['capturedEpochMs'])
            epochs.extend(original_epochs)
            pose=before if suffix=='Before' else after
            need(math.dist(ray['headPosition'],pose['subject']['source']['hmd']['worldPosition'])<=.15)
            need(max(original_epochs)<=capture['requestedEpochMs'] if suffix=='Before' else min(original_epochs)>=capture['capturedEpochMs'])
            need(geometry['sequence']>browser['sequence'] if suffix=='Before' else browser['sequence']>geometry['sequence'])
            need(geometry['capturedEpochMs']>=browser['capturedEpochMs'] if suffix=='Before' else browser['capturedEpochMs']>=geometry['capturedEpochMs'])
        epochs.extend((browser['capturedEpochMs'],current['capturedEpochMs'],current['source']['dom']['capturedEpochMs'],
            runtime['source']['nativeBefore']['capturedEpochMs'],runtime['capturedEpochMs'],scripts['sampleEpochMs']))
        if suffix=='Before':need(max(epochs)<=capture['requestedEpochMs'])
        else:need(min(browser['capturedEpochMs'],runtime['source']['nativeBefore']['capturedEpochMs'],scripts['sampleEpochMs'])>=capture['capturedEpochMs'])
    continuity(value['browserBefore'],value['browserAfter'])
    runtime_continuity(value['runtimeBefore'],value['runtimeAfter'],pid,value['fixtureUrl'])
    browser_status(value['httpAfter'],value['httpBefore'])
    if kind=='world':
        a,b=value['worldBefore'],value['worldAfter'];continuity(a,b)
        need(b['commandId']!=a['commandId'])
        left,right=a['source']['worldRay'],b['source']['worldRay']
        tracking={'capturedEpochMs','sensorToWorld','headPosition'}
        need({key:item for key,item in left.items() if key not in tracking}=={key:item for key,item in right.items() if key not in tracking})
    need(current_document(value['browserBefore'])==current_document(value['browserAfter']) and measured[0]==measured[1]
        and value['scriptsBefore']['instance']==value['scriptsAfter']['instance']
        and value['scriptsAfter']['sampleSequence']>value['scriptsBefore']['sampleSequence']
        and value['scriptsBefore']['scripts']==value['scriptsAfter']['scripts'])
    earliest=min(epochs);need(0<=end-earliest<=1500)
    for epoch in epochs:fresh(epoch,end)
    return dict(**facts,state=measured[0],earliestEpochMs=earliest,latestEpochMs=end)
