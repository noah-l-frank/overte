"""Join original Graphics sources; requested settings are never measured passes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import parse_qs,urlsplit

from adapters.native_feature_observation import fresh,integer,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.world_render_evidence import validate as render_packet,original_pixels,measured_scale
from adapters.script_ui_inventory import validate as tablet_inventory
from adapters.token_graphics_ui import TokenGraphicsUI
from feature_journeys.contract import identifier,state as feature_state
from feature_journeys.evidence import image_observation
from feature_journeys.graphics_fixture import scene,VIEW
from feature_journeys.graphics_resources import RESOURCE,validate_status
from overte_phone_graphics import validate as graphics_packet
from overte_phone_script_files import validate as tablet_packet
from overte_phone_script_measurements import fixture_scope

VERSION=2


def near(actual,wanted,tolerance=1e-4):
    if type(wanted) in (int,float):return number(actual,-1e9,1e9) and abs(actual-wanted)<=tolerance
    if type(wanted) is list:return type(actual) is list and len(actual)==len(wanted) and all(near(a,b,tolerance) for a,b in zip(actual,wanted))
    return type(actual) is type(wanted) and actual==wanted


def aligned_subject(packet,run,scene_ticket,fixture_url):
    """Readiness checks compare stimulus with originals; return no feature facts."""
    source=packet['source'];expected=scene(run,scene_ticket,fixture_url)
    need(not source['absentIds'] and len(source['entities'])==7 and not source['scan']['unowned'])
    root=urlsplit(fixture_url);actual=urlsplit(source['sceneUrl']);query=parse_qs(actual.query,strict_parsing=True)
    need(actual.scheme==root.scheme and actual.netloc==root.netloc and actual.username is None
         and actual.password is None and not actual.fragment and set(query)<={'location'}
         and all(len(values)==1 and len(values[0])<=256 for values in query.values())
         and actual.path==root.path+'tickets/'+scene_ticket+'/'+RESOURCE)
    for document in expected['Entities']:
        rows=[row for row in source['entities'] if row['id']==document['id'].strip('{}')];need(len(rows)==1)
        row=rows[0]
        need(row['name']==document['name'] and row['type']==document['type'] and row['hostType'] in ('local','domain') and row['visible'])
        for field,axes in (('position','xyz'),('dimensions','xyz'),('rotation','xyzw')):
            need(near(row[field],[document[field][axis] for axis in axes]))
        if 'color' in document:need(row['color']==[document['color'][axis] for axis in ('red','green','blue')])
        if 'mirrorMode' in document:need(row['mirrorMode']==document['mirrorMode'])
        if 'sourceUrl' in document:need(row['sourceUrl']==document['sourceUrl'])
        if document['type']=='Zone':
            haze=document['haze']
            need(row['hazeMode']==2 and near(row['haze']['range'],haze['hazeRange'])
                 and row['haze']['color']==[haze['hazeColor'][axis] for axis in ('red','green','blue')]
                 and row['haze']['glare']==haze['hazeEnableGlare'] and row['haze']['altitudeEffect']==haze['hazeAltitudeEffect']
                 and near(row['haze']['backgroundBlend'],haze['hazeBackgroundBlend']))
    view=source['view'];need(view['perspective'] and view['mode'] in ('first person','first person look at')
        and near(view['position'],[VIEW['position'][a] for a in 'xyz'],.01))
    # Quaternions q/-q represent the same measured view. Do not rewrite either.
    rotation=[VIEW['rotation'][a] for a in 'xyzw']
    need(near(view['rotation'],rotation,.001) or near(view['rotation'],[-v for v in rotation],.001))


def steady_subject(before,after):
    left,right=before['source'],after['source']
    need(all(left[key]==right[key] for key in ('subjectVersion','sceneUrl','entities','absentIds','scan')))
    a,b=left['view'],right['view']
    need(a['mode']==b['mode'] and a['perspective']==b['perspective'] and near(a['position'],b['position'],.001)
         and near(a['fieldOfViewDegrees'],b['fieldOfViewDegrees'],.001) and near(a['aspectRatio'],b['aspectRatio'],.0001))
    need(near(a['rotation'],b['rotation'],.0001) or near(a['rotation'],[-v for v in b['rotation']],.0001))
    if left['subjectVersion']==2:
        a,b=left['avatarPose'],right['avatarPose']
        need(near(a['feetPosition'],b['feetPosition'],.001) and near(a['modelScale'],b['modelScale'],.0001)
             and (near(a['orientation'],b['orientation'],.0001) or near(a['orientation'],[-v for v in b['orientation']],.0001)))


def compose(run,ticket,fixture_url,pid,provider,provider_instance,provider_request,
            before,subject_before,ui,tablet,capture,pixels,subject_after,after,epoch,after_epoch,image_policy):
    identifier(run);identifier(ticket);fixture_scope(run,fixture_url);need(integer(pid,1) and integer(epoch,1) and integer(after_epoch,1))
    base=fixture_url.rsplit('/runs/',1)[0]
    validate_status(provider,instance=provider_instance,run=run,url=base,request=provider_request)
    need(provider['active'] and provider['ticket']==ticket and provider['sceneTicket'] is not None
         and any(row['status']==200 for row in provider['responses']))
    fresh(provider['capturedEpochMs'],epoch);scene_ticket=provider['sceneTicket']
    for packet in (before,after):native_packet(packet,packet.get('requestId'),pid,epoch)
    for packet in (subject_before,subject_after):
        subject_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),
            action='feature-graphics-subject-observe',runId=run),pid,epoch)
        aligned_subject(packet,run,scene_ticket,fixture_url)
    need(any(row['status']==200 and row['completedEpochMs']<=subject_before['requestedEpochMs'] for row in provider['responses']))
    graphics_packet(ui,ui.get('commandId'),pid,epoch)
    tablet_packet(tablet,tablet.get('commandId'),pid,epoch)
    inventory=tablet_inventory(tablet.get('scriptInventory'));need(inventory['complete'])
    need(not any(row['rootVisible'] for row in inventory['managers']) and not any(row['visible'] or row['requestId'] for row in inventory['pickers']))
    render_packet(capture,capture.get('requestId'),pid,epoch);original_pixels(capture,pixels)
    source=capture['source'];need(source['captureVersion']==2)
    trace=source['renderTrace'];need(trace['forwardDrawCommands']>0 and trace['traceVersion']==2)
    need(before['instance']==after['instance']==subject_before['instance']==subject_after['instance']
         and after['sequence']>before['sequence'] and subject_after['sequence']>subject_before['sequence']
         and before['graphics']==after['graphics'] and before['lifecycle']==after['lifecycle'])
    steady_subject(subject_before,subject_after)
    # Compare the original recording view retained by this exact GPU frame,
    # rather than treating a later live Camera getter as the image's pose.
    recorded=trace['recordedView'];live=subject_before['source']['view']
    need(near(recorded['position'],live['position'],.001)
         and (near(recorded['rotation'],live['rotation'],.0001) or near(recorded['rotation'],[-v for v in live['rotation']],.0001))
         and near(recorded['fieldOfViewDegrees'],live['fieldOfViewDegrees'],.001)
         and near(recorded['aspectRatio'],live['aspectRatio'],.0001))
    ordered=[before['capturedEpochMs'],subject_before['requestedEpochMs'],subject_before['capturedEpochMs'],
        ui['capturedEpochMs'],tablet['capturedEpochMs'],trace['recordedEpochMs'],source['recordedEpochMs'],
        source['capturedEpochMs'],capture['capturedEpochMs'],subject_after['requestedEpochMs'],
        subject_after['capturedEpochMs'],after.get('requestedEpochMs'),after['capturedEpochMs']]
    need(all(integer(value,1) for value in ordered) and ordered==sorted(ordered)
         and capture['requestedEpochMs']>=tablet['capturedEpochMs'])
    clocks=ordered+[provider['capturedEpochMs']]
    need(min(clocks)>=after_epoch and max(clocks)-min(clocks)<=1500)
    fresh(min(clocks),epoch)
    scale=measured_scale(capture);need(abs(scale['x']-scale['y'])<=.01)
    target=source['targetExtent']
    need(abs(subject_before['source']['view']['aspectRatio']-target[0]/target[1])<=.01)
    actual=after['graphics'];page=TokenGraphicsUI.row(ui,'graphics.page')
    need(page is None or page['profile']=='phone-immediate-v1' and inventory['tabletShown'])
    if page is not None:
        for identifier_,field in (('graphics.haze','hazeSetting'),('graphics.mirrors','mirrorsSetting')):
            row=TokenGraphicsUI.row(ui,identifier_);need(row is not None and row['nativeChecked']==actual[field])
        row=TokenGraphicsUI.row(ui,'graphics.resolution')
        need(row is not None and near(row['nativeValue'],actual['requestedResolutionScale']))
    # These booleans describe executed original batches, independently of prefs.
    # The fresh challenge/subject pixels below remain mandatory in every sample.
    measured=dict(resolution=actual['requestedResolutionScale'],renderScale=(scale['x']+scale['y'])/2,
        haze=actual['hazeSetting'],hazePass=trace['hazeDrawCommands']>0,
        mirror=actual['mirrorsSetting'],mirrorPass=trace['mirrorDrawCommands']>0,dialog=page is not None)
    feature_state('graphics',measured,run)
    need(type(image_policy) is dict and image_policy.get('source')=='world-render-target')
    evidence,_subject=image_observation(pixels,run,ticket,image_policy)
    return deepcopy(dict(state=measured,capturedEpochMs=min(clocks),lifecycle=after['lifecycle'],
        resources=['panel:graphics'] if inventory['tabletShown'] else [],image=evidence,
        trace=trace,scale=scale))
