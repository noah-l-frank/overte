"""Independent original pre-HUD Vulkan haze/reflection pixel comparison."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time

from adapters.native_feature_observation import fresh,integer,need,number
from adapters.graphics_subject_geometry import steady_subject
from adapters.graphics_subject_pixels import measure_pair
from adapters.script_feature.history import same
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_world_measurements import compose

VERSION=1


class GraphicsWorldEffectPending(NativeUIError):
    """Qualified original pixels do not yet show the measured setting effect."""
    def __init__(self,observation):
        self.observation=deepcopy(observation)
        super().__init__('Original Graphics effect pixels are not ready')


def compare(run,feature,fixture_url,binding,before,raw_before,after,raw_after,policy,provider_instance,
            epoch_ms,guard,*,monotonic=time.monotonic):
    identifier(run);need(feature in ('haze','mirror') and all(callable(fn) for fn in (epoch_ms,guard,monotonic)))
    started=previous=monotonic();need(number(started,0,1e15))
    def bound():
        nonlocal previous
        current=monotonic();need(number(current,previous,1e15) and current-started<5 and guard() is not False);previous=current
    bound();epoch=epoch_ms();need(integer(epoch,1));bound()
    first=compose(run,before['provider']['ticket'],fixture_url,binding,before,raw_before,policy,
                  provider_instance=provider_instance,after_epoch=math.floor(before['clockJoin']['hostBeforeEpochMs']))
    last=compose(run,after['provider']['ticket'],fixture_url,binding,after,raw_after,policy,
                 provider_instance=provider_instance,after_epoch=math.floor(after['clockJoin']['hostBeforeEpochMs']))
    fresh(math.floor(last['capturedEpochMs']),epoch)
    need(before['provider']['ticket']!=after['provider']['ticket']
         and 0<=after['clockJoin']['hostBeforeEpochMs']-before['clockJoin']['hostAfterEpochMs']<=45000)
    validate_status(after['provider'],instance=provider_instance,run=run,url=fixture_url.rsplit('/runs/',1)[0],
                    request=after['provider']['requestId'],previous=before['provider'])
    for source in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','capture','retirement'):
        need(before[source]['instance']==after[source]['instance'] and after[source]['sequence']>before[source]['sequence'])
    for source in ('graphics','tablet'):
        need(before[source]['instance']==after[source]['instance']
             and after[source]['sourceSequence']>before[source]['sourceSequence'])
    need(before['clockJoin']['nativeAfter']['instance']==after['clockJoin']['nativeBefore']['instance']
         and after['clockJoin']['nativeBefore']['sequence']>before['clockJoin']['nativeAfter']['sequence']
         and same(before['nativeAfter']['lifecycle'],after['nativeBefore']['lifecycle']))
    field='hazeSetting' if feature=='haze' else 'mirrorsSetting'
    left,right=before['nativeAfter']['graphics'],after['nativeBefore']['graphics']
    need(left[field]!=right[field] and all(same(left[key],right[key]) for key in left if key!=field)
         and all(actual['state'][feature]==actual['state'][feature+'Pass'] for actual in (first,last)))
    steady_subject(before['subjectAfter'],after['subjectBefore'])
    a,b=before['capture']['source'],after['capture']['source']
    need(before['capture']['requestId']!=after['capture']['requestId']
         and a['renderTrace']['frameId']!=b['renderTrace']['frameId']
         and all(same(a[key],b[key]) for key in ('sourceExtent','targetExtent'))
         and same(a['renderTrace']['recordedView'],b['renderTrace']['recordedView']))
    rows={row['id']:row for row in after['subjectBefore']['source']['entities']};ids=subject_ids(run)
    target=rows[ids['fog-board' if feature=='haze' else 'reflector']]
    stats=measure_pair(raw_before,raw_after,target,rows[ids['marker']],b['renderTrace']['recordedView'],
                       b['targetExtent'],[0,0],b['targetExtent'],policy,bound)
    direction=1 if right[field] else -1
    ready=stats['changedFraction']>=.05 and (direction*(stats['blueDominanceAfter']-stats['blueDominanceBefore'])>10 if feature=='haze'
        else direction*(stats['orangeFractionAfter']-stats['orangeFractionBefore'])>.005)
    result=dict(graphicsWorldEffectsVersion=VERSION,feature=feature,beforeTicket=before['provider']['ticket'],afterTicket=after['provider']['ticket'],
                beforeSha256=hashlib.sha256(raw_before).hexdigest(),afterSha256=hashlib.sha256(raw_after).hexdigest(),targetId=target['id'],**stats)
    bound();current=epoch_ms();need(integer(current,epoch));fresh(math.floor(last['capturedEpochMs']),current);bound()
    need(max(current-last['capturedEpochMs'],epoch-last['capturedEpochMs']+(previous-started)*1000)<=1500)
    if not ready:raise GraphicsWorldEffectPending(result)
    return deepcopy(result)
