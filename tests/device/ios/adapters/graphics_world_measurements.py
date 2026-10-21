"""Original pre-HUD Vulkan PNG and ordinary visible Graphics state join.

This source does not use WDA screenshots or alter/hide the tablet to acquire
pixels. Acquisition, durable ownership and full-area publication remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.graphics_subject_geometry import aligned_subject,steady_subject,near,projected_box
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.script_feature.measurements import fixture_scope
from adapters.script_feature.ui_source import validate as tablet_packet
from adapters.script_ui_inventory import validate as tablet_inventory
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys.contract import identifier,state as feature_state
from feature_journeys.evidence import image_observation
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_source import validate as graphics_packet

VERSION=1
FIELDS={'nativeBefore','subjectBefore','graphics','tablet','capture','retirement','subjectAfter','nativeAfter','provider','clockJoin'}


def originals(frame):return {key:frame[key] for key in FIELDS-{'provider','clockJoin'}}


def compose(run,ticket,fixture_url,binding,frame,raw,policy,*,provider_instance,after_epoch):
    identifier(run);identifier(ticket);fixture_scope(run,fixture_url);context(binding);exact(frame,FIELDS)
    need(integer(after_epoch,1));pid=int(binding['processIdentity']);need(pid>0)
    clock=validate_join(frame['clockJoin'],originals(frame));epoch=clock['nativeAfter']['capturedEpochMs']
    need(clock['nativeBefore']['processId']==pid and clock['hostBeforeEpochMs']>=after_epoch)
    provider=frame['provider'];validate_status(provider,instance=provider_instance,run=run,
        url=fixture_url.rsplit('/runs/',1)[0],request=provider['requestId'])
    need(provider['active'] and provider['ticket']==ticket and provider['sceneTicket'] is not None
         and any(row['status']==200 and row['completedEpochMs']<=clock['hostBeforeEpochMs'] for row in provider['responses']))
    fresh(provider['capturedEpochMs'],math.floor(clock['hostAfterEpochMs']));need(provider['capturedEpochMs']>=clock['hostBeforeEpochMs'])
    before,after=frame['nativeBefore'],frame['nativeAfter']
    for packet in (before,after):
        native_packet(packet,packet.get('requestId'),pid,epoch);need(packet['requestId'].startswith('ios-'))
    need(before['instance']==after['instance']==clock['nativeBefore']['instance']
         and before['sequence']<after['sequence'] and same(before['graphics'],after['graphics'])
         and same(before['lifecycle'],after['lifecycle']) and same(before['lifecycle'],clock['nativeAfter']['lifecycle']))
    for packet in (frame['subjectBefore'],frame['subjectAfter']):
        need(packet.get('instance')==before['instance'])
        subject_packet(packet,dict(schemaVersion=1,action='feature-graphics-subject-observe',commandId=packet.get('requestId'),runId=run),
                       pid,epoch,require_avatar=True)
        aligned_subject(packet,run,provider['sceneTicket'],fixture_url)
    need(frame['subjectBefore']['sequence']<frame['subjectAfter']['sequence']);steady_subject(frame['subjectBefore'],frame['subjectAfter'])
    ui,tablet=frame['graphics'],frame['tablet'];graphics_packet(ui,ui.get('commandId'),pid,epoch)
    tablet_packet(tablet,tablet.get('commandId'),pid,epoch);need(ui['instance']==tablet['instance'])
    inventory=tablet_inventory(tablet['scriptInventory']);need(inventory['complete'])
    need(not any(row['rootVisible'] for row in inventory['managers'])
         and not any(row['visible'] or row['requestId'] for row in inventory['pickers']))
    capture,proof=frame['capture'],frame['retirement']
    query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
               commandId=capture.get('commandId'),requestId=capture.get('requestId'))
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(proof,dict(query,operation=proof.get('operation'),commandId=proof.get('commandId')),pid,epoch)
    need(absent(proof) and proof['instance']==capture['instance'] and proof['sequence']>capture['sequence'])
    source=capture['source'];trace=source['renderTrace'];live=frame['subjectBefore']['source']['view'];recorded=trace['recordedView']
    need(trace['forwardDrawCalls']>0 and near(recorded['position'],live['position'],.001)
         and (near(recorded['rotation'],live['rotation'],.0001) or near(recorded['rotation'],[-v for v in live['rotation']],.0001))
         and near(recorded['fieldOfViewDegrees'],live['fieldOfViewDegrees'],.001) and near(recorded['aspectRatio'],live['aspectRatio'],.0001))
    ordered=[before['capturedEpochMs'],frame['subjectBefore']['requestedEpochMs'],frame['subjectBefore']['capturedEpochMs'],
        ui['capturedEpochMs'],tablet['capturedEpochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],
        source['submittedEpochMs'],source['fenceObservedEpochMs'],source['pixelsReadEpochMs'],capture['capturedEpochMs'],
        proof['requestedEpochMs'],proof['capturedEpochMs'],frame['subjectAfter']['requestedEpochMs'],frame['subjectAfter']['capturedEpochMs'],
        after['requestedEpochMs'],after['capturedEpochMs']]
    need(all(integer(v,1) for v in ordered) and ordered==sorted(ordered)
         and clock['nativeBefore']['capturedEpochMs']<=ordered[0]<=ordered[-1]<=epoch)
    scale=[a/b for a,b in zip(source['sourceExtent'],source['targetExtent'])];need(abs(scale[0]-scale[1])<=.01)
    need(abs(live['aspectRatio']-source['targetExtent'][0]/source['targetExtent'][1])<=.01)
    actual=after['graphics'];page=TokenGraphicsUI.row(ui,'graphics.page')
    need(page is None or page['profile']=='generic-immediate-v1' and inventory['tabletShown'])
    if page is not None:
        for control,field in (('graphics.haze','hazeSetting'),('graphics.mirrors','mirrorsSetting')):
            row=TokenGraphicsUI.row(ui,control);need(row is not None and row['nativeChecked']==actual[field])
        row=TokenGraphicsUI.row(ui,'graphics.resolution');need(row is not None and near(row['nativeValue'],actual['requestedResolutionScale']))
    measured=dict(resolution=actual['requestedResolutionScale'],renderScale=sum(scale)/2,haze=actual['hazeSetting'],
        hazePass=trace['hazeDrawCalls']>0,mirror=actual['mirrorsSetting'],mirrorPass=trace['mirrorDrawCalls']>0,dialog=page is not None)
    feature_state('graphics',measured,run);need(type(policy) is dict and policy.get('source')=='world-render-target')
    marker=next(row for row in frame['subjectAfter']['source']['entities'] if row['id']==subject_ids(run)['marker'])
    box=projected_box(marker,recorded,source['targetExtent']);roi=policy.get('marker')
    need(type(roi) is list and len(roi)==4 and box[0]<=roi[0]<roi[2]<=box[2] and box[1]<=roi[1]<roi[3]<=box[3])
    image,_subject=image_observation(raw,run,ticket,policy)
    return deepcopy(dict(state=measured,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=ordered[0],
        lifecycle=after['lifecycle'],resources=['panel:graphics'] if inventory['tabletShown'] else [],image=image,
        trace=trace,scale=scale,frameId=trace['frameId']))
