"""Assets mesh/reader originals joined to a fenced image, never Create state.

The enclosing owner must independently recompose the supplied baked-input proof
and original marker child. This pure join owns no acquisition, retry, resource
retirement or whole-journey verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import itertools
import re
from adapters.graphics_subject_geometry import near,projected_box,rotate
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle
from ios.adapters import assets_model_renderers as models,avatar_renderers,create_state
from ios.adapters.create_marker_identity import marker
from ios.adapters.emote_images import avatar_box,within

VERSION=1
FIELDS={'createBefore','modelsBefore','avatarsBefore','capture','retirement','avatarsAfter','modelsAfter','createAfter','clockJoin'}
PROOF={'assetModelBakedInputProofVersion','runId','processId','domainId','entityId','creationRequestId','originRequestId','readerId',
    'nativeGeometryRequestId','backendRequestId','bakeRequestId','path','outputPath','sha256','bytes'}


def originals(frame):return {key:frame[key] for key in FIELDS-{'clockJoin'}}


def disjoint(left,right):return max(left[0],right[0])>=min(left[2],right[2]) or max(left[1],right[1])>=min(left[3],right[3])


def box(bounds,view,extent):
    """Conservative actual world AABB, including fully offscreen objects."""
    inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]];points=[]
    for sides in itertools.product((0,1),repeat=3):
        world=[a+b*c for a,b,c in zip(bounds['corner'],bounds['dimensions'],sides)]
        camera=rotate([a-b for a,b in zip(world,view['position'])],inverse)+[1]
        points.append([sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)])
    if any(all(p[axis]<-p[3] for p in points) or all(p[axis]>p[3] for p in points) for axis in range(3)):return None
    return avatar_box(bounds,view,extent)


def exclusions(create,model_packet,avatar_packet,entity_id,marker_id,roi,view,extent):
    renderers={row['entityId']:row for row in model_packet['source']['models']}
    for row in create['source']['entities']:
        if row['id'] in (entity_id,marker_id) or not row['visible']:continue
        if row['type']=='Model':
            actual=renderers.get(row['id']);need(actual is not None)
            if not actual['present'] or not actual['addedToScene'] or not actual['visible']:continue
            need(actual['boundsReady']);bounds=actual['bounds']
        else:
            # Unknown geometry, environment/light effects and procedural
            # contributors remain unavailable until separately observed.
            need(row['type'] in ('Web','Shape','Box','Sphere'))
            corners=[]
            for signs in itertools.product((-1,1),repeat=3):
                local=[sign*size/2 for sign,size in zip(signs,row['dimensions'])]
                corners.append([a+b for a,b in zip(rotate(local,row['rotation']),row['position'])])
            minimum=[min(point[axis] for point in corners) for axis in range(3)]
            bounds=dict(corner=minimum,dimensions=[max(point[axis] for point in corners)-minimum[axis] for axis in range(3)])
        projected=box(bounds,view,extent)
        if projected is not None:need(disjoint(roi,projected))
    for row in avatar_packet['source']['avatars']:
        if not (row['addedToScene'] and row['shouldRender']):continue
        need(row['boundsReady']);projected=box(row['bounds'],view,extent)
        if projected is not None:need(disjoint(roi,projected))
    # Existing AvatarRenderer originals do not expose independent attachment
    # mesh bounds. Never turn their missing bounds into an empty scene.
    need(not any(row['visible'] and row['addedToScene'] for row in avatar_packet['source']['avatarEntities']))


def compose(run,ticket,binding,frame,raw,policy,parsed_proof,marker_original,*,after_epoch,previous=None,changed=False):
    identifier(run);identifier(ticket);context(binding);exact(frame,FIELDS);exact(parsed_proof,PROOF)
    for key in ('domainId','entityId'):create_state.uuid(parsed_proof[key])
    for key in ('creationRequestId','originRequestId','nativeGeometryRequestId'):
        need(type(parsed_proof[key]) is str and re.fullmatch('ios-[a-f0-9]{32}',parsed_proof[key]))
    for key in ('backendRequestId','bakeRequestId'):
        need(type(parsed_proof[key]) is str and re.fullmatch('assets-[a-f0-9]{32}',parsed_proof[key]))
    need(type(parsed_proof['assetModelBakedInputProofVersion']) is int and parsed_proof['assetModelBakedInputProofVersion']==1
        and parsed_proof['runId']==run and parsed_proof['processId']==int(binding['processIdentity'])
        and integer(parsed_proof['bytes'],1) and type(parsed_proof['sha256']) is str and re.fullmatch('[a-f0-9]{64}',parsed_proof['sha256'])
        and type(parsed_proof['readerId']) is str and re.fullmatch('[a-f0-9]{32}',parsed_proof['readerId'])
        and type(parsed_proof['path']) is str and len(parsed_proof['path'])<=4096 and parsed_proof['path'].startswith('/')
        and type(parsed_proof['outputPath']) is str and len(parsed_proof['outputPath'])<=4096 and parsed_proof['outputPath'].startswith('/.baked/'))
    exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target' and integer(after_epoch,1))
    clock=validate_join(frame['clockJoin'],originals(frame));first,last=clock['nativeBefore'],clock['nativeAfter'];pid=int(binding['processIdentity'])
    epoch=last['capturedEpochMs'];need(first['processId']==last['processId']==pid and clock['hostBeforeEpochMs']>=after_epoch
        and same(first['lifecycle'],last['lifecycle']) and same(first['graphics'],last['graphics']))
    before,after=frame['createBefore'],frame['createAfter']
    for packet in (before,after):
        create_state.original(packet);need(packet['iosCreateStateVersion']>=3 and packet['runId']==run and packet['processId']==pid)
    create_state.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=create_state.ACTION,runId=run),pid,epoch,before)
    need(same(before['source'],after['source']) and before['source']['complete'] and not before['source']['tabletShown']
        and not before['source']['roots'] and before['source']['domainId']==parsed_proof['domainId'])
    entity_id=parsed_proof['entityId'];rows=[row for row in before['source']['entities'] if row['id']==entity_id]
    need(len(rows)==1);entity=rows[0];need(entity['type']=='Model' and entity['hostType']=='domain' and entity['visible']
        and entity['modelURL']=='atp:'+parsed_proof['path'] and entity['model']['present'] and entity['model']['loaded']
        and entity['model']['addedToScene'] and not entity['model']['failed'])
    left,right=frame['modelsBefore'],frame['modelsAfter']
    models.validate(right,dict(schemaVersion=1,commandId=right['requestId'],action=models.ACTION,runId=run),pid,epoch,left)
    rendered=[models.model(value,entity_id) for value in (left,right)]
    need(same(rendered[0],rendered[1]) and rendered[0]['origin']['geometry']['readerId']==parsed_proof['readerId']
        and rendered[0]['origin']['modelUrl']==entity['modelURL'])
    a,b=frame['avatarsBefore'],frame['avatarsAfter']
    avatar_renderers.validate(b,dict(schemaVersion=1,commandId=b['requestId'],action=avatar_renderers.ACTION,runId=run),pid,epoch,a)
    need(a['iosAvatarRenderersVersion']>=4 and b['iosAvatarRenderersVersion']>=4)
    for create,model_packet,avatar_packet in ((before,left,a),(after,right,b)):
        need(model_packet['processId']==avatar_packet['processId']==pid and model_packet['runId']==avatar_packet['runId']==run
            and model_packet['source']['domainId']==create['source']['domainId']
            and model_packet['source']['localSessionId']==create['source']['localSessionId']
            and model_packet['source']['tree']==avatar_packet['source']['tree']==create['source']['tree']
            and avatar_packet['source']['complete'])
        own=[row for row in avatar_packet['source']['avatars'] if row['self']]
        need(len(own)==1 and own[0]['sessionId']==create['source']['localSessionId'])
    exact(marker_original,{'nonce','sourceUrl','id'});marks=[marker(value,marker_original['nonce'],marker_original['sourceUrl']) for value in (before,after)]
    need(same(marks[0],marks[1]) and marks[0]['id']==marker_original['id'] and entity_id!=marker_original['id'])
    capture,retirement=frame['capture'],frame['retirement'];query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',commandId=capture['commandId'],requestId=capture['requestId'])
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(retirement,dict(query,operation=retirement['operation'],commandId=retirement['commandId']),pid,epoch)
    need(absent(retirement) and capture['instance']==retirement['instance'] and retirement['sequence']>capture['sequence'])
    source=capture['source'];trace=source['renderTrace'];view=trace['recordedView'];camera=before['source']['view'];extent=source['targetExtent']
    need(trace['forwardDrawCalls']>0 and camera['perspective'] and near(view['position'],camera['position'],.001)
        and (near(view['rotation'],camera['rotation'],.0001) or near(view['rotation'],[-v for v in camera['rotation']],.0001))
        and near(view['fieldOfViewDegrees'],camera['fieldOfViewDegrees'],.001) and near(view['aspectRatio'],camera['aspectRatio'],.0001)
        and abs(camera['aspectRatio']-extent[0]/extent[1])<=.01)
    order=[before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],left['clockBefore']['epochMs'],left['clockAfter']['epochMs'],a['clockBefore']['epochMs'],a['clockAfter']['epochMs'],
        capture['requestedEpochMs'],trace['recordedEpochMs'],source['submittedEpochMs'],source['fenceObservedEpochMs'],source['pixelsReadEpochMs'],capture['capturedEpochMs'],
        retirement['requestedEpochMs'],retirement['capturedEpochMs'],b['clockBefore']['epochMs'],b['clockAfter']['epochMs'],right['clockBefore']['epochMs'],right['clockAfter']['epochMs'],after['clockBefore']['epochMs'],after['clockAfter']['epochMs']]
    need(order==sorted(order) and first['capturedEpochMs']<=order[0]<=order[-1]<=epoch)
    rectangle(policy['marker'],extent);rectangle(policy['subject'],extent)
    mark_box=projected_box(marks[0],view,extent);within(policy['marker'],mark_box);need(disjoint(policy['subject'],mark_box))
    subject_box=box(rendered[0]['bounds'],view,extent);need(subject_box is not None);within(policy['subject'],subject_box)
    for create,model_packet,avatar_packet in ((before,left,a),(after,right,b)):
        exclusions(create,model_packet,avatar_packet,entity_id,marker_original['id'],policy['subject'],view,extent)
    image,subject=image_observation(raw,run,ticket,policy,previous=previous,changed=changed)
    return dict(assetModelImageVersion=VERSION,runId=run,processId=pid,domainId=parsed_proof['domainId'],entityId=entity_id,
        readerId=parsed_proof['readerId'],bodySha256=parsed_proof['sha256'],bodyBytes=parsed_proof['bytes'],renderItemIds=deepcopy(rendered[0]['renderItemIds']),
        meshBounds=deepcopy(rendered[0]['bounds']),markerId=marker_original['id'],frameId=trace['frameId'],capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=order[0],image=image),subject
