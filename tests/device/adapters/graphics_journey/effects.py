"""Historical original stereo effects, with a separate currentness boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.graphics_journey.measurements import compose,metadata_bytes,frame_fields
from adapters.graphics_journey.originals import record as original_record,content
from adapters.graphics_journey.samples import retirement
from feature_journeys.graphics_resources import validate_status
from feature_journeys.stereo_graphics_evidence import advance,changes
from adapters.script_journey.history import same

VERSION=1


def original(run,frame,raw,binding,role,fixture_url,image_policy):
    """Original historical facts; no fabricated current time/guard is accepted."""
    exact(frame,frame_fields(frame));context(binding)
    for field,kind in (('image','image'),('metadata','file')):
        record=original_record(frame[field])
        need(record['binding']==binding and record['role']==role and record['runId']==run and record['kind']==kind
            and record['phase']=='saved' and record['ticket']==frame['ticket'] and same(record['capture'],frame['capture']))
    content(frame['image'],raw)
    content(frame['metadata'],metadata_bytes(frame,binding,run,role,frame['image']['stage'],fixture_url))
    proof=frame['retirement'];retirement(proof,proof['owner'],int(binding['processIdentity'].split(':')[0]),binding,role)
    need(proof['owner']['capture']['commandId']==frame['capture']['requestId'] and proof['memory']['instance']==frame['capture']['instance'])
    return compose(run,frame,raw,binding,role,frame['image']['stage'],fixture_url,image_policy)


def compare_original(run,feature,fixture_url,binding,role,before,raw_before,after,raw_after,image_policy):
    need(feature in ('haze','mirror') and before['image']['stage']==after['image']['stage'])
    left=original(run,before,raw_before,binding,role,fixture_url,image_policy)
    right=original(run,after,raw_after,binding,role,fixture_url,image_policy)
    validate_status(after['provider'],instance=before['provider']['instance'],run=run,url=fixture_url.rsplit('/runs/',1)[0],
        request=after['provider']['requestId'],previous=before['provider'])
    advance(left['subject'],right['subject']);value=changes(left['subject'],right['subject']);need(value['feature']==feature)
    return deepcopy(dict(graphicsEffectsVersion=VERSION,feature=feature,beforeTicket=before['ticket'],afterTicket=after['ticket'],
        beforeSha256=hashlib.sha256(raw_before).hexdigest(),afterSha256=hashlib.sha256(raw_after).hexdigest(),eyes=value['eyes']))


def compare(run,feature,fixture_url,binding,role,before,raw_before,after,raw_after,image_policy,epoch_ms,guard,*,monotonic=time.monotonic):
    """Live admission around pure original comparison, retaining actual clocks."""
    need(all(callable(v) for v in (epoch_ms,guard,monotonic)))
    started=previous=monotonic();need(number(started,0,1e15))
    def bound():
        nonlocal previous
        need(guard() is not False);current=monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
    bound();first_clock=previous;epoch=epoch_ms();need(integer(epoch,1)
        and epoch>=max(after['nativeAfter']['capturedEpochMs'],after['provider']['capturedEpochMs']));bound()
    result=compare_original(run,feature,fixture_url,binding,role,before,raw_before,after,raw_after,image_policy);bound()
    oldest=min(after['nativeBefore']['requestedEpochMs'],after['capture']['source']['recordedEpochMs'])
    final_clock=previous;final_epoch=epoch_ms();need(integer(final_epoch,epoch));fresh(oldest,final_epoch);bound()
    need(max(final_epoch-oldest+math.ceil((previous-final_clock)*1000),epoch-oldest+math.ceil((previous-first_clock)*1000))<=1500)
    return result
