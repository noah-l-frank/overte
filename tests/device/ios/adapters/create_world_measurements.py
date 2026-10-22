"""Original Create world pixels joined to actual entities and GPU retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.graphics_subject_geometry import near,projected_box
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle
from ios.adapters import create_state
from ios.adapters.create_product_state import project
from ios.adapters.create_marker_identity import marker

VERSION = 1
FIELDS = {'createBefore','capture','retirement','createAfter','clockJoin'}


def originals(frame): return {name:frame[name] for name in FIELDS-{'clockJoin'}}


def compose(run,ticket,binding,frame,raw,policy,owned_ids,marker_original,*,voxel_baseline=None,previous=None,changed=False,after_epoch):
    identifier(run); identifier(ticket); context(binding); exact(frame,FIELDS); need(integer(after_epoch,1))
    exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
    clock = validate_join(frame['clockJoin'],originals(frame)); native_first,native_last = clock['nativeBefore'],clock['nativeAfter']
    pid = int(binding['processIdentity']); need(native_first['processId'] == native_last['processId'] == pid
        and clock['hostBeforeEpochMs'] >= after_epoch and same(native_first['lifecycle'],native_last['lifecycle']))
    before,after = frame['createBefore'],frame['createAfter']
    for packet in (before,after):
        create_state.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=create_state.ACTION,runId=run),pid,native_last['capturedEpochMs'])
        need(packet['iosCreateStateVersion'] >= 3)
    create_state.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=create_state.ACTION,runId=run),pid,native_last['capturedEpochMs'],before)
    first,last = create_state.live(before),create_state.live(after)
    # The original map and semantic subject properties are stable across the
    # actual fenced draw. Never place requested geometry into these packets.
    need(same(first['tree']['entities'],last['tree']['entities']) and first['localSessionId'] == last['localSessionId']
         and all(same(first[key],last[key]) for key in ('canRez','canRezTmp','tabletShown')))
    capture,retirement = frame['capture'],frame['retirement']; epoch = native_last['capturedEpochMs']
    query = dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',commandId=capture['commandId'],requestId=capture['requestId'])
    frame_packet(capture,query,pid,epoch); original_pixels(capture,raw)
    storage(retirement,dict(query,operation=retirement['operation'],commandId=retirement['commandId']),pid,epoch)
    need(absent(retirement) and retirement['instance'] == capture['instance'] and retirement['sequence'] > capture['sequence'])
    actual = capture['source']; trace = actual['renderTrace']; recorded = trace['recordedView']; view = first['view']
    rectangle(policy['marker'],actual['targetExtent']);rectangle(policy['subject'],actual['targetExtent'])
    need(trace['forwardDrawCalls'] > 0 and view['perspective'] and near(recorded['position'],view['position'],.001)
         and (near(recorded['rotation'],view['rotation'],.0001) or near(recorded['rotation'],[-v for v in view['rotation']],.0001))
         and near(recorded['fieldOfViewDegrees'],view['fieldOfViewDegrees'],.001) and near(recorded['aspectRatio'],view['aspectRatio'],.0001)
         and all(near(first['view'][key],last['view'][key],.001) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio')))
    times = [before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],
             actual['submittedEpochMs'],actual['fenceObservedEpochMs'],actual['pixelsReadEpochMs'],capture['capturedEpochMs'],
             retirement['requestedEpochMs'],retirement['capturedEpochMs'],after['clockBefore']['epochMs'],after['clockAfter']['epochMs']]
    need(all(integer(stamp,1) for stamp in times) and times == sorted(times)
         and native_first['capturedEpochMs'] <= times[0] <= times[-1] <= epoch)
    exact(marker_original,{'nonce','sourceUrl','id'})
    observed_marker = marker(after,marker_original['nonce'],marker_original['sourceUrl']); need(observed_marker['id'] == marker_original['id'])
    marker_box = projected_box(observed_marker,recorded,actual['targetExtent']); roi = policy['marker']
    need(type(policy) is dict and policy.get('source') == 'world-render-target' and marker_box[0] <= roi[0] < roi[2] <= marker_box[2]
         and marker_box[1] <= roi[1] < roi[3] <= marker_box[3])
    measured = project(after,run,owned_ids,voxel_baseline=voxel_baseline)
    live = [row for row in last['entities'] if row['id'] in owned_ids]
    if live:
        need(len(live) == 1); subject_box = projected_box(live[0],recorded,actual['targetExtent']); subject = policy['subject']
        need(max(subject_box[0],subject[0]) < min(subject_box[2],subject[2]) and max(subject_box[1],subject[1]) < min(subject_box[3],subject[3]))
    image,decoded_subject = image_observation(raw,run,ticket,policy,previous=previous,changed=changed)
    return dict(state=measured,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=times[0],
                image=image,frameId=trace['frameId'],marker=observed_marker,lifecycle=deepcopy(native_last['lifecycle'])),decoded_subject
