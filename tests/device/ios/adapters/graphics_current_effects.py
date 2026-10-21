"""Current enabled-effect pixels over a recent original controlled off frame.

This is an observational component, not input, calibration or a feature verdict.
Unlike an explicit enable phase, the current frame can belong to baseline,
resolution, background, restart or restoration. Raw originals are never changed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time

from adapters.graphics_subject_geometry import aligned_entities, near, projected_box
from adapters.graphics_subject_pixels import measure_pair
from adapters.native_clock_join import digest
from adapters.native_feature_observation import fresh, integer, need, number
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_history import follow_native
from ios.adapters.graphics_restart_proof import validate as restart_packet
from ios.adapters.graphics_world_effects import GraphicsWorldEffectPending
from ios.adapters.graphics_world_measurements import compose

VERSION=1
DISABLED_VERSION=1


def view_equal(left,right):
    for key in ('position','projection','fieldOfViewDegrees','aspectRatio','nearClip','farClip'):
        need(near(left[key],right[key],.0001))
    need(left['perspective'] is True and right['perspective'] is True
         and (near(left['rotation'],right['rotation'],.0001) or near(left['rotation'],[-v for v in right['rotation']],.0001)))


def world_equal(left,right,*,replaced):
    """Compare actual geometry without rewriting original source timestamps."""
    a,b=left['source'],right['source']
    need(a['subjectVersion']==b['subjectVersion']==3 and same(a['scan'],b['scan']) and a['absentIds']==b['absentIds']==[])
    old={r['id']:r for r in a['entities']};new={r['id']:r for r in b['entities']};need(set(old)==set(new))
    for key in old:
        before,after=old[key],new[key]
        if replaced:
            # A newly loaded entity keeps its actual new edit timestamp. Only
            # the geometry projection is compared across proven process death.
            need(all(same(v,after[k]) for k,v in before.items() if k!='lastEditedEpochUs'))
        else:need(same(before,after))
    for key in ('view','avatarPose','cameraOrbit'):
        before,after=a[key],b[key]
        need(set(before)==set(after))
        for field,v in before.items():
            other=after[field]
            if field in ('rotation','orientation','lookAtRotation'):
                need(near(v,other,.0001) or near(v,[-n for n in other],.0001))
            else:need(near(v,other,.001))


def process_pair(old_binding,new_binding,before,after,restart):
    old,new=context(old_binding),context(new_binding);replaced=old['processIdentity']!=new['processIdentity']
    need(all(same(old[k],new[k]) for k in old if k!='processIdentity'))
    if replaced:
        receipt=restart_packet(restart)
        need(same(receipt['input']['oldBinding'],old) and same(receipt['input']['newBinding'],new))
        first,last=before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore']
        need(first['instance']==receipt['oldNative']['instance'] and last['instance']==receipt['native']['instance']
             and first['sequence']<=receipt['oldNative']['sequence'] and first['capturedEpochMs']<=receipt['oldNative']['requestedEpochMs']
             and last['requestedEpochMs']>=receipt['exit']['capturedEpochMs'])
        for key in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','capture','retirement','graphics','tablet'):
            need(before[key]['instance']!=after[key]['instance'])
    else:
        need(restart is None and same(old,new));follow_native(before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
        need(before['nativeAfter']['lifecycle']['launches']==after['nativeBefore']['lifecycle']['launches'])
        for key in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','capture','retirement'):
            need(before[key]['instance']==after[key]['instance'] and after[key]['sequence']>before[key]['sequence'])
        for key in ('graphics','tablet'):
            need(before[key]['instance']==after[key]['instance'] and after[key]['sourceSequence']>before[key]['sourceSequence'])
    return replaced


def compare(run,feature,fixture_url,old_binding,before,raw_before,binding,current,raw_current,policy,provider_instance,
            epoch_ms,guard,*,restart=None,monotonic=time.monotonic):
    return _compare(run,feature,fixture_url,old_binding,before,raw_before,binding,current,raw_current,policy,
        provider_instance,epoch_ms,guard,enabled=True,restart=restart,monotonic=monotonic)


def compare_disabled(run,feature,fixture_url,old_binding,before,raw_before,binding,current,raw_current,policy,provider_instance,
                     epoch_ms,guard,*,restart=None,monotonic=time.monotonic):
    """A fresh disabled frame must not retain the previously enabled signature.

    The original off reference stays original. The controlled effect targets
    are disjoint; changes to resolution or the other effect can alter ordinary
    pixels, but cannot substitute for absence of this target's effect signature.
    """
    return _compare(run,feature,fixture_url,old_binding,before,raw_before,binding,current,raw_current,policy,
        provider_instance,epoch_ms,guard,enabled=False,restart=restart,monotonic=monotonic)


def _compare(run,feature,fixture_url,old_binding,before,raw_before,binding,current,raw_current,policy,provider_instance,
             epoch_ms,guard,*,enabled,restart,monotonic):
    identifier(run);need(feature in ('haze','mirror') and all(callable(f) for f in (epoch_ms,guard,monotonic)))
    start=previous=monotonic();need(number(start,0,1e15))
    def bound():
        nonlocal previous
        now=monotonic();need(number(now,previous,1e15) and now-start<5 and guard() is not False);previous=now
    bound();epoch=epoch_ms();need(integer(epoch,1))
    first=compose(run,before['provider']['ticket'],fixture_url,old_binding,before,raw_before,policy,
                  provider_instance=provider_instance,after_epoch=math.floor(before['clockJoin']['hostBeforeEpochMs']))
    last=compose(run,current['provider']['ticket'],fixture_url,binding,current,raw_current,policy,
                 provider_instance=provider_instance,after_epoch=math.floor(current['clockJoin']['hostBeforeEpochMs']))
    fresh(math.floor(last['capturedEpochMs']),epoch)
    need(0<=current['clockJoin']['hostBeforeEpochMs']-before['clockJoin']['hostAfterEpochMs']<=45000)
    if not same(before['provider'],current['provider']):
        validate_status(current['provider'],instance=provider_instance,run=run,url=fixture_url.rsplit('/runs/',1)[0],
                        request=current['provider']['requestId'],previous=before['provider'])
    replaced=process_pair(old_binding,binding,before,current,restart)
    field='hazeSetting' if feature=='haze' else 'mirrorsSetting'
    need(first['state'][feature] is False and first['state'][feature+'Pass'] is False
         and last['state'][feature] is enabled and last['state'][feature+'Pass'] is enabled)
    allowed={'requestedResolutionScale','applicationResolutionScale','hazeSetting','mirrorsSetting'}
    left,right=before['nativeAfter']['graphics'],current['nativeBefore']['graphics']
    need(left[field] is False and right[field] is enabled
         and all(same(v,right[k]) for k,v in left.items() if k not in allowed))
    # Both actual scenes independently match the controlled resource. Differences
    # in resolution or the other effect cannot introduce a foreign orange object,
    # light or an overlapping effect target into this observation.
    for frame in (before,current):
        for key in ('subjectBefore','subjectAfter'):
            aligned_entities(frame[key],run,frame['provider']['sceneTicket'],fixture_url)
    need(before['provider']['sceneTicket']==current['provider']['sceneTicket'])
    world_equal(before['subjectAfter'],current['subjectBefore'],replaced=replaced)
    a,b=before['capture']['source'],current['capture']['source']
    need(before['capture']['requestId']!=current['capture']['requestId']
         and a['renderTrace']['frameId']!=b['renderTrace']['frameId'] and same(a['targetExtent'],b['targetExtent']))
    view_equal(a['renderTrace']['recordedView'],b['renderTrace']['recordedView'])
    rows={r['id']:r for r in current['subjectBefore']['source']['entities']};ids=subject_ids(run)
    target=rows[ids['fog-board' if feature=='haze' else 'reflector']]
    other=rows[ids['reflector' if feature=='haze' else 'fog-board']]
    target_box=projected_box(target,b['renderTrace']['recordedView'],b['targetExtent'])
    other_box=projected_box(other,b['renderTrace']['recordedView'],b['targetExtent'])
    need(target_box[2]<=other_box[0] or other_box[2]<=target_box[0] or target_box[3]<=other_box[1] or other_box[3]<=target_box[1])
    stats=measure_pair(raw_before,raw_current,target,rows[ids['marker']],b['renderTrace']['recordedView'],b['targetExtent'],
                       [0,0],b['targetExtent'],policy,bound)
    if enabled:
        ready=stats['changedFraction']>=.05 and (stats['blueDominanceAfter']-stats['blueDominanceBefore']>10 if feature=='haze'
            else stats['orangeFractionAfter']-stats['orangeFractionBefore']>.005)
    else:
        ready=(stats['blueDominanceAfter']-stats['blueDominanceBefore']<=10 if feature=='haze'
            else stats['orangeFractionAfter']-stats['orangeFractionBefore']<=.005)
    version={'iosGraphicsCurrentEffectsVersion':VERSION} if enabled else {'iosGraphicsDisabledEffectsVersion':DISABLED_VERSION}
    result=dict(**version,feature=feature,referenceTicket=before['provider']['ticket'],
        currentTicket=current['provider']['ticket'],referenceBindingSha256=digest(old_binding),bindingSha256=digest(binding),
        restartSha256=digest(restart) if replaced else None,referenceSha256=hashlib.sha256(raw_before).hexdigest(),
        currentSha256=hashlib.sha256(raw_current).hexdigest(),targetId=target['id'],**stats)
    bound();now=epoch_ms();need(integer(now,epoch));fresh(math.floor(last['capturedEpochMs']),now);bound()
    need(max(now-last['capturedEpochMs'],epoch-last['capturedEpochMs']+(previous-start)*1000)<=1500)
    if not ready:raise GraphicsWorldEffectPending(result)
    return deepcopy(result)
