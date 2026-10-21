"""Independent two-eye Graphics PNG verification using original native metadata.

Metadata is a separate bounded original-source artifact. It carries no requested
state or adapter-provided photometry. Recompute pixels at their original source
interval; a caller must separately bind the result to its current acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from collections import OrderedDict
import hashlib
import json
import math
import time
import threading
from adapters.native_feature_observation import exact,integer,need,validate as native_packet
from adapters.normal_feature_state import context
from adapters.pico4.graphics_source import validate as ui_packet
from adapters.script_journey.measurements import fixture_scope
from adapters.stereo_graphics_pixels import reduce_original,cameras
from adapters.vr_graphics_subject import first_person_head,separate_inventory
from adapters.pico4.graphics_scene import PicoGraphicsScenePolicy
from adapters.pico4.graphics_composition import admit as admit_composition
from adapters.world_render_evidence import measured_scale
from .contract import identifier,json_document,result,typed_equal
from .graphics_resources import validate_status

VERSION=2
PROFILE={'source':'world-render-target','profile':'pico-stereo-graphics-v1'}
SURFACE_PROFILE={'source':'world-render-target','profile':'pico-stereo-graphics-v2'}
LIMIT=2*1024*1024
FIELDS={'stereoGraphicsEvidenceVersion','runId','ticket','sceneTicket','fixtureUrl','binding','role','stage',
    'nativeBefore','nativeAfter','subjectBefore','subjectAfter','graphics','capture','provider'}
SURFACE_FIELDS=FIELDS|{'graphicsAfter'}
_ORIGINAL_CLOCK=time.monotonic
_ORIGINAL_CACHE=OrderedDict()
_ORIGINAL_CACHE_LOCK=threading.RLock()
_ORIGINAL_CACHE_BYTES=0
_ORIGINAL_CACHE_LIMIT=16*1024*1024
_ORIGINAL_CACHE_ENTRIES=64


def policy(value):exact(value,PROFILE);need(value in (PROFILE,SURFACE_PROFILE));return value


def analyse(raw,metadata,run,ticket,fixture_url,*,role='primary',monotonic=time.monotonic):
    """Pure historical analysis, bounded memoization of exact original bytes.

    Current acquisition/age/guard, original file identity and source replay
    checks belong to callers and are never cached. Custom clocks always execute
    the original analysis so an injected clock failure cannot be hidden.
    """
    global _ORIGINAL_CACHE_BYTES
    if (monotonic is not _ORIGINAL_CLOCK or type(raw) is not bytes or type(metadata) is not bytes
            or not all(type(value) is str for value in (run,ticket,fixture_url,role))):
        return _analyse_uncached(raw,metadata,run,ticket,fixture_url,role=role,monotonic=monotonic)
    started=monotonic();key=(raw,metadata,run,ticket,fixture_url,role)
    with _ORIGINAL_CACHE_LOCK:
        cached=_ORIGINAL_CACHE.get(key)
        if cached is not None:_ORIGINAL_CACHE.move_to_end(key)
    if cached is not None:
        value=json.loads(cached[0]) # A new result; callers cannot mutate cached facts.
    else:
        value=_analyse_uncached(raw,metadata,run,ticket,fixture_url,role=role,monotonic=monotonic)
    finished=monotonic()
    need(type(started) in (int,float) and math.isfinite(started) and started>=0
        and type(finished) in (int,float) and math.isfinite(finished) and started<=finished and finished-started<5)
    if cached is None:
        encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        charge=len(raw)+len(metadata)+len(encoded)+sum(len(item.encode()) for item in key[2:])
        # Store serialized facts rather than mutable decoded objects. The byte
        # budget accounts for both original inputs, output and context strings.
        if charge<=_ORIGINAL_CACHE_LIMIT and json.loads(encoded)==value:
            with _ORIGINAL_CACHE_LOCK:
                if key not in _ORIGINAL_CACHE:
                    while _ORIGINAL_CACHE and (_ORIGINAL_CACHE_BYTES+charge>_ORIGINAL_CACHE_LIMIT
                            or len(_ORIGINAL_CACHE)>=_ORIGINAL_CACHE_ENTRIES):
                        _old,(_encoded,cost)=_ORIGINAL_CACHE.popitem(last=False);_ORIGINAL_CACHE_BYTES-=cost
                    _ORIGINAL_CACHE[key]=(encoded,charge);_ORIGINAL_CACHE_BYTES+=charge
    finished=monotonic()
    need(type(finished) in (int,float) and math.isfinite(finished) and started<=finished and finished-started<5)
    return value


def _analyse_uncached(raw,metadata,run,ticket,fixture_url,*,role='primary',monotonic=time.monotonic):
    """Historical original facts; never a current sampler, clock or input API."""
    need(type(metadata) is bytes and 0<len(metadata)<=LIMIT and callable(monotonic) and role in ('primary','actor'))
    started=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    identifier(run);identifier(ticket);fixture_scope(run,fixture_url)
    body=json_document(metadata);version=body.get('stereoGraphicsEvidenceVersion') if type(body) is dict else None
    exact(body,SURFACE_FIELDS if version==2 else FIELDS)
    need(type(body['stereoGraphicsEvidenceVersion']) is int and version in (1,2)
        and body['runId']==run and body['ticket']==ticket and body['fixtureUrl']==fixture_url and body['role']==role
        and type(body['stage']) is int and body['stage'] in (0,1))
    identifier(body['sceneTicket']);context(body['binding']);pid=int(body['binding']['processIdentity'].split(':')[0])
    before,after=body['nativeBefore'],body['nativeAfter'];first,last=body['subjectBefore'],body['subjectAfter']
    ui,capture,provider=body['graphics'],body['capture'],body['provider']
    need(all(type(value) is dict for value in (before,after,first,last,ui,capture,provider)))
    ui_after=body['graphicsAfter'] if version==2 else ui
    need(type(ui_after) is dict)
    epochs=[value.get('capturedEpochMs') for value in (after,last,ui,ui_after,capture,provider)]
    need(all(integer(value,1) for value in epochs));epoch=max(epochs)
    for packet in (before,after,first,last,capture):identifier(packet.get('requestId'))
    identifier(ui.get('commandId'))
    for packet in (before,after):native_packet(packet,packet.get('requestId'),pid,epoch)
    need(before['requestId']!=after['requestId'] and before['instance']==after['instance']==first.get('instance')==last.get('instance')
        and after['sequence']>before['sequence'] and before['graphics']==after['graphics'] and before['lifecycle']==after['lifecycle'])
    first_person_head(first);first_person_head(last)
    scene=separate_inventory(first)['scene'];need(scene==separate_inventory(last)['scene'])
    ui_packet(ui,ui.get('commandId'),pid,epoch)
    # Pico's actual tablet is world geometry drawn before ToneMapping. This
    # legacy photometry profile has no original per-surface visibility proof;
    # a near-marker and pass counts cannot attribute an open UI's colors.
    if version==1:need(not ui['tabletShown'])
    else:
        ui_packet(ui_after,ui_after.get('commandId'),pid,epoch)
        need(ui_after['instance']==ui['instance'] and ui_after['generation']==ui['generation']
            and ui_after['commandId']!=ui['commandId'] and ui_after['sourceSequence']>ui['sourceSequence']
            and ui_after['elapsedMs']>=ui['elapsedMs'] and ui_after['tabletShown']==ui['tabletShown']
            and typed_equal(admit_composition(ui,first),admit_composition(ui_after,last)))
    validate_status(provider,instance=provider.get('instance'),run=run,url=fixture_url.rsplit('/runs/',1)[0],request=provider.get('requestId'))
    from .graphics_fixture import LEGACY_PROFILE,PICO_PROFILE,PICO_RESOURCE
    from .graphics_resources import RESOURCE
    resource=PICO_RESOURCE if version==2 else RESOURCE
    need(provider['active'] and provider['ticket']==ticket and provider['sceneTicket']==body['sceneTicket']
        and provider.get('profile',LEGACY_PROFILE)==(PICO_PROFILE if version==2 else LEGACY_PROFILE)
        and any(row['resource']==resource and row['status']==200 and row['completedEpochMs']<=first['requestedEpochMs'] for row in provider['responses']))
    from adapters.pico4.graphics_scene import PicoGraphicsSurfaceScenePolicy
    scene_policy=PicoGraphicsSurfaceScenePolicy if version==2 else PicoGraphicsScenePolicy
    for packet in (first,last):scene_policy.aligned_subject(packet,run,body['sceneTicket'],fixture_url)
    ordered=[before.get('requestedEpochMs'),before['capturedEpochMs'],first['requestedEpochMs'],first['capturedEpochMs'],ui['capturedEpochMs'],
        capture.get('requestedEpochMs'),capture.get('capturedEpochMs'),*([ui_after['capturedEpochMs']] if version==2 else []),
        last['requestedEpochMs'],last['capturedEpochMs'],after.get('requestedEpochMs'),after['capturedEpochMs']]
    need(all(integer(value,1) for value in ordered) and ordered==sorted(ordered))
    recorded=capture.get('source',{}).get('recordedEpochMs');need(integer(recorded,1))
    if version==2:
        from .graphics_surface_cues import RESOURCES
        for surface,stem in RESOURCES.items():
            resources=[(stem+'.html',body['sceneTicket'],first['requestedEpochMs'])]
            # Mirror-off needs absence of any valid reflected code, rather
            # than assuming that a current reflected PNG was consumed.
            if surface=='haze' or capture['source']['renderTrace']['mirrorDrawCommands']>0:
                resources.append((stem+'.png',ticket,recorded))
            for name,original_ticket,deadline in resources:
                need(any(row['resource']==name and row['ticket']==original_ticket and row['status']==200
                    and row['completedEpochMs']<=deadline for row in provider['responses']))
    clocks=ordered+[recorded,provider['capturedEpochMs']];need(max(clocks)-min(clocks)<=1500)
    if version==2:
        from adapters.stereo_graphics_surfaces import reduce_original as reducer
    else:reducer=reduce_original
    pixels=reducer(capture,raw,first,last,run=run,ticket=ticket,scene_ticket=body['sceneTicket'],
        fixture_url=fixture_url,pid=pid,monotonic=monotonic)
    scale=measured_scale(capture);need(abs(scale['x']-scale['y'])<=.01)
    pages=[row for row in ui['controls'] if row['id']=='graphics.page'];need(len(pages)<=1)
    fields=after['graphics'];actual=dict(resolution=fields['requestedResolutionScale'],renderScale=(scale['x']+scale['y'])/2,
        haze=fields['hazeSetting'],hazePass=capture['source']['renderTrace']['hazeDrawCommands']>0,
        mirror=fields['mirrorsSetting'],mirrorPass=capture['source']['renderTrace']['mirrorDrawCommands']>0,
        dialog=bool(pages) and ui['tabletShown'])
    if pages:
        need(pages[0]['profile']=='generic-immediate-v1')
        for control,field in (('graphics.haze','hazeSetting'),('graphics.mirrors','mirrorsSetting')):
            rows=[row for row in ui['controls'] if row['id']==control];need(len(rows)==1 and rows[0]['nativeChecked']==fields[field])
        rows=[row for row in ui['controls'] if row['id']=='graphics.resolution'];need(len(rows)==1
            and abs(rows[0]['nativeValue']-fields['requestedResolutionScale'])<1e-4)
    if version==2:
        def actual_controls(packet):
            return [{k:v for k,v in row.items() if k not in ('token','focused','enabled','inputReady','viewport')}
                for row in packet['controls']]
        need(typed_equal(actual_controls(ui),actual_controls(ui_after)))
    finished=monotonic();need(type(finished) in (int,float) and math.isfinite(finished) and started<=finished and finished-started<5)
    return dict(body=body,pixels=pixels,state=actual,earliestEpochMs=min(clocks),latestEpochMs=max(clocks),
        nativeGraphics=deepcopy(fields),lifecycle=deepcopy(after['lifecycle']),
        sceneSha256=hashlib.sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        entitiesSha256=hashlib.sha256(json.dumps(first['source']['entities'],sort_keys=True,separators=(',',':')).encode()).hexdigest())


def original_name(body):
    return 'graphics-'+body['runId']+'-'+body['role']+'-'+str(body['stage'])+'-'+body['capture']['requestId']


def _subject(value):
    body=value['body'];source=body['capture']['source']
    value_version=body['stereoGraphicsEvidenceVersion']
    subject=dict(stereoGraphicsSubjectVersion=value_version,runId=body['runId'],ticket=body['ticket'],sceneTicket=body['sceneTicket'],
        binding=deepcopy(body['binding']),role=body['role'],stage=body['stage'],nativeGraphics=deepcopy(value['nativeGraphics']),
        lifecycle=deepcopy(value['lifecycle']),earliestEpochMs=value['earliestEpochMs'],latestEpochMs=value['latestEpochMs'],
        sceneSha256=value['sceneSha256'],dialog=value['state']['dialog'],
        sourceExtent=deepcopy(source['sourceExtent']),sourceViewport=deepcopy(source['sourceViewport']),
        entitiesSha256=value['entitiesSha256'],captureInstance=body['capture']['instance'],
        requestId=body['capture']['requestId'],nativeInstance=body['nativeBefore']['instance'],providerInstance=body['provider']['instance'],
        passes=dict(haze=value['state']['hazePass'],mirror=value['state']['mirrorPass']),
        frameIndex=source['stereo']['frameIndex'],executionSequence=source['stereo']['executionSequence'],
        cursors=dict(capture=body['capture']['sequence'],acquisition=source['acquisitionSequence'],
            submission=source['presentation']['submissionSequence'],
            cameraFirst=min(row['sequence'] for row in source['renderTrace']['cameraBatches']),
            cameraLast=max(row['sequence'] for row in source['renderTrace']['cameraBatches']),
            nativeBefore=body['nativeBefore']['sequence'],nativeAfter=body['nativeAfter']['sequence'],
            subjectBefore=body['subjectBefore']['sequence'],subjectAfter=body['subjectAfter']['sequence'],ui=body['graphics']['sourceSequence']),
        requests=dict(nativeBefore=body['nativeBefore']['requestId'],nativeAfter=body['nativeAfter']['requestId'],
            subjectBefore=body['subjectBefore']['requestId'],subjectAfter=body['subjectAfter']['requestId'],
            ui=body['graphics']['commandId'],capture=body['capture']['requestId'],provider=body['provider']['requestId']),
        uiInstance=body['graphics']['instance'],
        cameras=cameras(source,'forward'),extent=deepcopy(source['targetExtent']),eyes=deepcopy(value['pixels']['eyes']))
    if value_version==2:
        subject['cursors']['uiAfter']=body['graphicsAfter']['sourceSequence']
        subject['requests']['uiAfter']=body['graphicsAfter']['commandId']
    return subject


def advance(previous,current):
    """Original per-source cursors and births, without sampling or retiming."""
    need(all(previous[key]==current[key] for key in
        ('stereoGraphicsSubjectVersion','runId','binding','role','stage','captureInstance','nativeInstance','providerInstance','uiInstance'))
        and current['earliestEpochMs']>=previous['earliestEpochMs'] and current['latestEpochMs']>=previous['latestEpochMs']
        and current['executionSequence']>previous['executionSequence'])
    a,b=previous['cursors'],current['cursors']
    need(all(b[key]>a[key] for key in ('capture','acquisition','submission','ui'))
        and b['cameraFirst']>a['cameraLast'] and b['nativeBefore']>a['nativeAfter'] and b['subjectBefore']>a['subjectAfter'])
    if current['stereoGraphicsSubjectVersion']==2:need(b['ui']>a['uiAfter'])


def _same_cameras(left,right):
    need(type(left) is dict and type(right) is dict and set(left)==set(right)=={'left','right'})
    def near(a,b):
        return a['viewport']==b['viewport'] and all(abs(x-y)<=.001 for x,y in zip(a['view'],b['view'])) \
            and all(abs(x-y)<=.005 for x,y in zip(a['projection'],b['projection']))
    for eye in ('left','right'):
        need(len(left[eye])==len(right[eye]) and all(any(near(a,b) for b in right[eye]) for a in left[eye])
            and all(any(near(a,b) for a in left[eye]) for b in right[eye]))


def changes(previous,current):
    """Per-eye normalized color-histogram lower bounds and effect direction.

    No crop, resize, alignment or claim of pixel-to-pixel correspondence. The
    original used Forward cameras must stay near the same physical pose, while
    original jitter/projection noise is explicitly bounded.
    """
    need(type(previous) is dict and previous.get('stereoGraphicsSubjectVersion')==current['stereoGraphicsSubjectVersion'] in (1,2)
        and all(previous[key]==current[key] for key in ('runId','sceneTicket','binding','role','stage','entitiesSha256','sceneSha256','dialog','sourceExtent','sourceViewport','captureInstance','extent','lifecycle'))
        and previous['ticket']!=current['ticket'] and current['earliestEpochMs']>=previous['latestEpochMs']
        and current['latestEpochMs']-previous['earliestEpochMs']<=45000
        and (previous['frameIndex'],previous['executionSequence'])!=(current['frameIndex'],current['executionSequence']))
    fields=[field for field in current['nativeGraphics'] if previous['nativeGraphics'][field]!=current['nativeGraphics'][field]]
    need(len(fields)==1 and fields[0] in ('hazeSetting','mirrorsSetting'))
    field=fields[0];feature='haze' if field=='hazeSetting' else 'mirror';direction=1 if current['nativeGraphics'][field] else -1
    need(all(packet['nativeGraphics'][field]==packet['passes'][feature] for packet in (previous,current)))
    _same_cameras(previous['cameras'],current['cameras']);measured={}
    for eye in ('left','right'):
        old,new=(packet['eyes'][eye][feature] for packet in (previous,current))
        if current['stereoGraphicsSubjectVersion']==2:
            if feature=='mirror':
                need(old['current']==previous['nativeGraphics'][field] and new['current']==current['nativeGraphics'][field])
                measured[eye]=dict(reflectedCodeBefore=old['current'],reflectedCodeAfter=new['current']);continue
            deltas=[b['blueDominance']-a['blueDominance'] for a,b in zip(old['calibrationRows'],new['calibrationRows'])]
            need(len(deltas)==8 and all(direction*delta>10 for delta in deltas))
            measured[eye]=dict(calibrationBlueDominanceDeltas=deltas);continue
        distance=sum(abs(a/old['pixels']-b/new['pixels']) for a,b in zip(old['histogram'],new['histogram']))/2
        delta=(new['blueDominance']-old['blueDominance']) if feature=='haze' else (new['orangeFraction']-old['orangeFraction'])
        need(distance>=.05 and direction*delta>(10 if feature=='haze' else .005))
        measured[eye]=dict(histogramChangeLowerBound=distance,blueDominanceDelta=new['blueDominance']-old['blueDominance'],
            orangeFractionDelta=new['orangeFraction']-old['orangeFraction'])
    return dict(feature=feature,eyes=measured)


def observation(raw,metadata,run,ticket,fixture_url,external_policy,sample,*,previous=None,changed=False,role='primary',monotonic=time.monotonic):
    policy(external_policy);result('feature.graphics.observe',sample)
    need(sample['runId']==run and type(changed) is bool)
    started=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    value=analyse(raw,metadata,run,ticket,fixture_url,role=role,monotonic=monotonic);body=value['body']
    need(body['stereoGraphicsEvidenceVersion']==(2 if external_policy==SURFACE_PROFILE else 1))
    artifacts={item['kind']:item for item in sample['artifacts']};need('image' in artifacts and 'file' in artifacts)
    name=original_name(body)
    for kind,suffix in (('image','.png'),('file','.native.json')):
        item=artifacts[kind];need(item['name']==name+suffix and item['ticket']==ticket
            and item['capturedEpochMs']==body['capture']['capturedEpochMs'])
    need(typed_equal(sample['state'],value['state']) and sample['lifecycle']==value['lifecycle']
        and sample['capturedEpochMs']==value['earliestEpochMs'])
    subject=_subject(value);difference=changes(previous,subject) if changed else None
    finished=monotonic();need(type(finished) in (int,float) and math.isfinite(finished) and started<=finished and finished-started<5)
    return dict(stereoGraphicsEvidenceVersion=body['stereoGraphicsEvidenceVersion'],sha256=value['pixels']['sha256'],
        metadataSha256=hashlib.sha256(metadata).hexdigest(),subjectChangedFraction=None,
        change=difference,eyes=deepcopy(value['pixels']['eyes']),frameIndex=subject['frameIndex'],
        executionSequence=subject['executionSequence']),subject
