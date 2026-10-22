"""Original per-ticket world marker pixels and changed scene subject.

Acquisition, durable source ownership, independent peer and whole-area outcomes
remain with the feature owner. Historical validation never mints fresh clocks.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import re

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.graphics_subject_geometry import near,rotate
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation
from feature_journeys.navigation_scene import resource_root,scene,validate_status,MARKER_RESOURCE
from navigation_observation import owned_scene
from ios.adapters.navigation_world_measurements import compose,project
from ios.adapters.navigation_state import validate as state_packet

VERSION=1
FIELDS={'frame','raw','captureQuery','url','label','ticket','provider','providerInstance','fixtureUrl'}


def originals(sample):return {key:sample[key] for key in FIELDS-{'raw'}}


def marker(sample,run):
    source=sample['frame']['navigationAfter'];need(source['iosNavigationStateVersion']==2)
    challenge=source['source']['challengeMarker'];need(challenge['present'] is True)
    actual=challenge['entity'];need(actual['type']=='Web' and actual['hostType'] in ('local','domain')
        and actual['visible'] is True and actual['collisionless'] is True)
    root=resource_root(sample['fixtureUrl'],run)
    match=re.fullmatch(re.escape(root)+'tickets/([a-f0-9]{32})/'+re.escape(MARKER_RESOURCE),actual['sourceUrl'])
    need(match is not None);scene_ticket=match[1]
    url=owned_scene(sample['url'],viewpoint_required=True)._replace(query='',fragment='').geturl()
    provider=sample['provider'];validate_status(provider,instance=sample['providerInstance'],run=run,scene_url=url)
    need(provider['active'] is True and provider['ticket']==sample['ticket'])
    expected_document=scene(run,scene_ticket,root)
    raw=json.dumps(expected_document,separators=(',',':'),ensure_ascii=False).encode()
    need(any(row['ticket']==scene_ticket and row['bytes']==len(raw) and row['sha256']==hashlib.sha256(raw).hexdigest()
             for row in provider['responses']))
    expected=expected_document['Entities'][-1]
    need(challenge['id']==expected['id'].strip('{}') and actual['name']==expected['name'])
    for field,axes in (('position','xyz'),('dimensions','xyz'),('rotation','xyzw')):
        need(near(actual[field],[expected[field][axis] for axis in axes]))
    return actual,scene_ticket


def policy(sample,actual):
    """Derive the card interior and wall/floor subject from measured geometry."""
    frame=sample['frame'];source=frame['capture']['source'];view=source['renderTrace']['recordedView'];width,height=source['targetExtent']
    corners=[]
    for x,y in ((-.5,.5),(.5,.5),(-.5,-.5),(.5,-.5)):
        offset=rotate([x*actual['dimensions'][0],y*actual['dimensions'][1],0],actual['rotation'])
        point=project([a+b for a,b in zip(actual['position'],offset)],view,[width,height]);need(point is not None);corners.append(point)
    # This version supports the normal aligned controlled viewpoint. It does
    # not replace a tilted/offscreen card with its conservative bounding box.
    top_left,top_right,bottom_left,bottom_right=corners
    need(abs(top_left[0]-bottom_left[0])<=.5 and abs(top_right[0]-bottom_right[0])<=.5
         and abs(top_left[1]-top_right[1])<=.5 and abs(bottom_left[1]-bottom_right[1])<=.5)
    left,top=top_left;right,bottom=bottom_right;need(left<right and top<bottom)
    marker_roi=[round(left+(right-left)*4/160),round(top+(bottom-top)*4/40),
                round(left+(right-left)*132/160),round(top+(bottom-top)*36/40)]
    wall=next(row for row in frame['navigationAfter']['source']['markers'] if row['name']=='OVERTE_E2E_COLLISION_WALL')
    # The observed front wall's bottom and actual recorded camera locate the
    # floor boundary; actual subject pixels must independently be nonuniform.
    floor=project([view['position'][0],wall['position'][1]-wall['dimensions'][1]/2,
                   wall['position'][2]+wall['dimensions'][2]/2],view,[width,height])
    need(floor is not None and floor[1]<height-8)
    subject_roi=[0,max(0,math.floor(floor[1]-.2*height)),width,height]
    need(marker_roi[2]-marker_roi[0]>=128 and marker_roi[3]-marker_roi[1]>=32
         and marker_roi[3]<subject_roi[1] and height-subject_roi[1]>=32)
    return dict(source='world-render-target',marker=marker_roi,subject=subject_roi)


def evaluate(run,binding,sample,*,previous=None,changed=False):
    identifier(run);exact(sample,FIELDS);identifier(sample['ticket']);need(type(changed) is bool)
    rendered=compose(run,binding,sample['frame'],sample['raw'],url=sample['url'],label=sample['label'],capture_query=sample['captureQuery'])
    actual,scene_ticket=marker(sample,run);image_policy=policy(sample,actual);previous_subject=None
    if changed:
        need(previous is not None);exact(previous,FIELDS);old=previous['frame'];current=sample['frame']
        old_result,previous_subject=evaluate(run,binding,previous)
        current_before=current['navigationBefore']
        state_packet(current_before,dict(schemaVersion=1,commandId=current_before['requestId'],action='feature-ios-navigation-state',runId=run),
                     int(binding['processIdentity']),previous=old['navigationAfter'])
        validate_status(sample['provider'],instance=sample['providerInstance'],run=run,
            scene_url=owned_scene(sample['url'])._replace(query='',fragment='').geturl(),previous=previous['provider'])
        need(old_result['ticket']!=sample['ticket'] and previous['providerInstance']==sample['providerInstance']
             and old['capture']['instance']==current['capture']['instance']
             and old['capture']['requestId']!=current['capture']['requestId']
             and old['capture']['sequence']<current['capture']['sequence']
             and old_result['rendered']['frameId']!=rendered['frameId']
             and old['navigationAfter']['instance']==current['navigationBefore']['instance']
             and old['navigationAfter']['sequence']<current['navigationBefore']['sequence']
             and old['navigationAfter']['clockAfter']['epochMs']<=current['navigationBefore']['clockBefore']['epochMs']
             and old['clockJoin']['hostAfterMonotonic']<=current['clockJoin']['hostBeforeMonotonic'])
    else:need(previous is None)
    image,subject=image_observation(sample['raw'],run,sample['ticket'],image_policy,previous=previous_subject,changed=changed)
    need(image['sha256']==rendered['imageSha256'])
    return dict(iosNavigationChallengeVersion=VERSION,runId=run,ticket=sample['ticket'],sceneTicket=scene_ticket,
                originalsSha256=digest(originals(sample)),rendered=rendered,policy=image_policy,image=deepcopy(image)),subject
