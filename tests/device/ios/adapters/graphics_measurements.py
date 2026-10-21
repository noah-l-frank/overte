"""Join independent native Vulkan frames and original iOS screen pixels.

The screen is bound to an observed frame interval, never labelled as the exact
pixels of an unreported GPU frame. All original packet clocks remain untouched.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,fresh,integer,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_completed_frame import validate as frame_packet,storage,absent
from adapters.graphics_subject_geometry import aligned_subject,steady_subject,near,projected_box
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.script_feature.measurements import fixture_scope
from adapters.script_feature.ui_source import validate as tablet_packet
from adapters.script_ui_inventory import validate as tablet_inventory
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys.contract import identifier,state as feature_state
from feature_journeys.evidence import image_observation
from feature_journeys.graphics_resources import validate_status
from feature_journeys.graphics_fixture import subject_ids
from ios.adapters.graphics_source import validate as graphics_packet
from ios.adapters.graphics_images import capture_record
from ios.adapters.native_geometry import validate as geometry_packet
from ios.adapters.viewport import viewport

VERSION=1
FIELDS={'nativeBefore','subjectBefore','graphics','tablet','geometryBefore','frameBefore','retirementBefore',
        'screen','frameAfter','retirementAfter','geometryAfter','subjectAfter','nativeAfter','provider','clockJoin'}


def originals(frame):
    """Original native clocks only; provider and screen host clocks stay separate."""
    return {key:(frame[key]['observation'] if key.startswith('geometry') else frame[key])
            for key in FIELDS-{'provider','clockJoin'}}


def frame_request(packet,operation='read'):
    return dict(schemaVersion=1,action='feature-completed-frame',operation=operation,
                commandId=packet['commandId'],requestId=packet['requestId'])


def screen_viewport(geometry,screen,frame):
    """Map actual UIKit safe content to original screen pixels without resizing."""
    doc=geometry['observation'];native=doc['nativeUi'];logical=viewport(doc,doc['sampleEpochMs'])
    density=native.get('density');need(number(density,1,4) and native.get('keyboardVisible') is False
                                      and number(native.get('imeInsetBottom'),0,0))
    actual=screen['extent'];surface=[native['surfaceWidth'],native['surfaceHeight']]
    need(all(abs(pixels-points*density)<=1 for pixels,points in zip(actual,surface)))
    measured=[logical['width']*density,logical['height']*density]
    target=frame['source']['targetExtent']
    need(all(abs(pixels-points)<=1 for pixels,points in zip(target,measured)))
    offset=[logical['x']*density,logical['y']*density]
    need(all(abs(v-round(v))<.001 for v in offset))
    result=[round(offset[0]),round(offset[1]),round(offset[0])+target[0],round(offset[1])+target[1]]
    need(0<=result[0]<result[2]<=actual[0] and 0<=result[1]<result[3]<=actual[1])
    return result


def compose(run,ticket,fixture_url,binding,frame,raw,policy,*,provider_instance,after_epoch):
    identifier(run);identifier(ticket);fixture_scope(run,fixture_url);context(binding);exact(frame,FIELDS)
    need(integer(after_epoch,1));pid=int(binding['processIdentity']);need(pid>0)
    clock=validate_join(frame['clockJoin'],originals(frame));epoch=clock['nativeAfter']['capturedEpochMs']
    need(clock['nativeBefore']['processId']==pid and clock['hostBeforeEpochMs']>=after_epoch)
    provider=frame['provider']
    validate_status(provider,instance=provider_instance,run=run,url=fixture_url.rsplit('/runs/',1)[0],request=provider['requestId'])
    need(provider['active'] and provider['ticket']==ticket and provider['sceneTicket'] is not None
         and any(row['status']==200 and row['completedEpochMs']<=clock['hostBeforeEpochMs'] for row in provider['responses']))
    fresh(provider['capturedEpochMs'],math.floor(clock['hostAfterEpochMs']))
    need(provider['capturedEpochMs']>=clock['hostBeforeEpochMs'])
    before,after=frame['nativeBefore'],frame['nativeAfter']
    for packet in (before,after):
        native_packet(packet,packet.get('requestId'),pid,epoch)
        need(type(packet['requestId']) is str and packet['requestId'].startswith('ios-'))
    need(before['instance']==after['instance']==clock['nativeBefore']['instance']
         and before['sequence']<after['sequence'] and same(before['graphics'],after['graphics'])
         and same(before['lifecycle'],after['lifecycle']) and same(before['lifecycle'],clock['nativeAfter']['lifecycle']))
    for packet in (frame['subjectBefore'],frame['subjectAfter']):
        need(packet.get('instance')==before['instance'])
        subject_packet(packet,dict(schemaVersion=1,action='feature-graphics-subject-observe',commandId=packet.get('requestId'),runId=run),
                       pid,epoch,require_avatar=True)
        aligned_subject(packet,run,provider['sceneTicket'],fixture_url)
    need(frame['subjectBefore']['sequence']<frame['subjectAfter']['sequence'])
    steady_subject(frame['subjectBefore'],frame['subjectAfter'])
    ui,tablet=frame['graphics'],frame['tablet']
    graphics_packet(ui,ui.get('commandId'),pid,epoch);tablet_packet(tablet,tablet.get('commandId'),pid,epoch)
    need(ui['instance']==tablet['instance'])
    inventory=tablet_inventory(tablet['scriptInventory']);need(inventory['complete'])
    need(not any(row['rootVisible'] for row in inventory['managers'])
         and not any(row['visible'] or row['requestId'] for row in inventory['pickers']))
    first,last=frame['frameBefore'],frame['frameAfter']
    for packet in (first,last):frame_packet(packet,frame_request(packet),pid,epoch)
    need(first['instance']==last['instance'] and first['sequence']<last['sequence']
         and first['requestId']!=last['requestId']
         and first['source']['renderTrace']['frameId']!=last['source']['renderTrace']['frameId'])
    for key in ('sourceExtent','targetExtent','backend','stage','view'):
        need(same(first['source'][key],last['source'][key]))
    for key in ('recordedView','hazeBatches','hazeDrawCalls','mirrorBatches','mirrorDrawCalls'):
        need(same(first['source']['renderTrace'][key],last['source']['renderTrace'][key]))
    for capture,proof in ((first,frame['retirementBefore']),(last,frame['retirementAfter'])):
        storage(proof,frame_request(proof,proof['operation']),pid,epoch)
        need(absent(proof) and proof['requestId']==capture['requestId'] and proof['instance']==capture['instance']
             and proof['sequence']>capture['sequence'])
    source=last['source'];trace=source['renderTrace'];live=frame['subjectBefore']['source']['view'];recorded=trace['recordedView']
    need(trace['forwardDrawCalls']>0 and first['source']['renderTrace']['forwardDrawCalls']>0
         and near(recorded['position'],live['position'],.001)
         and (near(recorded['rotation'],live['rotation'],.0001) or near(recorded['rotation'],[-v for v in live['rotation']],.0001))
         and near(recorded['fieldOfViewDegrees'],live['fieldOfViewDegrees'],.001)
         and near(recorded['aspectRatio'],live['aspectRatio'],.0001))
    screen=frame['screen'];capture_record(screen,raw)
    need(screen['processId']==pid and screen['sessionId']==binding['sessionId']
         and clock['hostBeforeEpochMs']<=screen['hostBeginEpochMs']<=screen['hostEndEpochMs']<=clock['hostAfterEpochMs']
         and clock['hostBeforeMonotonic']<=screen['hostBeginMonotonic']<=screen['hostEndMonotonic']<=clock['hostAfterMonotonic'])
    geometry_before,geometry_after=frame['geometryBefore'],frame['geometryAfter']
    for geometry in (geometry_before,geometry_after):
        geometry_packet(geometry,geometry['commandId'],native_epoch_ms=epoch)
        need(type(geometry['schemaVersion']) is int and geometry['commandId'].startswith('ios-')
             and type(geometry['observation']['schemaVersion']) is int)
    need(geometry_before['commandId']!=geometry_after['commandId']
         and same(geometry_before['observation']['nativeUi'],geometry_after['observation']['nativeUi'])
         and same(geometry_before['observation']['window'],geometry_after['observation']['window']))
    rect=screen_viewport(geometry_after,screen,last)
    need(rect==screen_viewport(geometry_before,screen,first))
    ordered=[before['capturedEpochMs'],frame['subjectBefore']['requestedEpochMs'],frame['subjectBefore']['capturedEpochMs'],
        ui['capturedEpochMs'],tablet['capturedEpochMs'],geometry_before['observation']['sampleEpochMs'],
        first['requestedEpochMs'],first['capturedEpochMs'],frame['retirementBefore']['requestedEpochMs'],
        frame['retirementBefore']['capturedEpochMs'],screen['nativeBeforeMs'],screen['nativeAfterMs'],
        last['requestedEpochMs'],last['capturedEpochMs'],frame['retirementAfter']['requestedEpochMs'],
        frame['retirementAfter']['capturedEpochMs'],geometry_after['observation']['sampleEpochMs'],
        frame['subjectAfter']['requestedEpochMs'],frame['subjectAfter']['capturedEpochMs'],after['requestedEpochMs'],after['capturedEpochMs']]
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
    feature_state('graphics',measured,run);need(type(policy) is dict and policy.get('source')=='native-screen')
    marker_id=subject_ids(run)['marker']
    marker=next(row for row in frame['subjectAfter']['source']['entities'] if row['id']==marker_id)
    box=projected_box(marker,recorded,source['targetExtent'])
    box=[box[0]+rect[0],box[1]+rect[1],box[2]+rect[0],box[3]+rect[1]]
    roi=policy.get('marker');need(type(roi) is list and len(roi)==4
        and box[0]<=roi[0]<roi[2]<=box[2] and box[1]<=roi[1]<roi[3]<=box[3])
    image,_subject=image_observation(raw,run,ticket,policy)
    return deepcopy(dict(state=measured,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=ordered[0],
        lifecycle=after['lifecycle'],resources=['panel:graphics'] if inventory['tabletShown'] else [],image=image,
        frameInterval=[trace_frame['source']['renderTrace']['frameId'] for trace_frame in (first,last)],
        trace=trace,scale=scale,screenViewport=rect))
