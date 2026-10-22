"""Original Vulkan Avatar pixels, actual geometry and honest absent volumes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
from adapters.graphics_subject_geometry import projected_box,near,rotate
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,need
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,challenge,rectangle,MarkerNotReady
from ios.adapters import avatar_world as world,avatar_renderers
from ios.adapters.emote_marker_measurements import orientation
from ios.adapters.emote_images import avatar_box,within
from ios.adapters.graphics_history import follow_native

VERSION=1
FIELDS={'worldBefore','renderersBefore','capture','retirement','renderersAfter','worldAfter','clockJoin'}


def originals(frame):return {key:frame[key] for key in frame.keys()-{'clockJoin'}}


def physical(before,after,avatar_id,*,remote):
    """Actual root transforms, available independently of render geometry."""
    for value in (before,after):world.original(value)
    need(world.actual_domain(before)==world.actual_domain(after) and before['runId']==after['runId']
        and before['processId']==after['processId'] and before['source']['sceneUrl']==after['source']['sceneUrl'])
    a,b=(world.body(packet,avatar_id,remote=remote) for packet in (before,after))
    need(near(a['position'],b['position'],.005) and orientation(a['orientation'],b['orientation'])
        and sum(v*v for v in a['velocity'])<.0001 and sum(v*v for v in b['velocity'])<.0001)
    return b


def exclusive_subject(packet,avatar_id,policy,view,extent):
    """Another actual rendered avatar cannot supply the subject's pixels."""
    import itertools
    roi=policy['subject'];inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]]
    for row in packet['source']['avatars']:
        if row['sessionId']==avatar_id or not (row['geometryLoaded'] and row['addedToScene'] and row['shouldRender']):continue
        need(row['boundsReady']);bounds=row['bounds'];points=[]
        for sides in itertools.product((0,1),repeat=3):
            world_point=[a+b*c for a,b,c in zip(bounds['corner'],bounds['dimensions'],sides)]
            camera=rotate([a-b for a,b in zip(world_point,view['position'])],inverse)+[1]
            points.append([sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)])
        if any(all(p[axis]<-p[3] for p in points) or all(p[axis]>p[3] for p in points) for axis in range(3)):continue
        box=avatar_box(bounds,view,extent)
        need(max(roi[0],box[0])>=min(roi[2],box[2]) or max(roi[1],box[1])>=min(roi[3],box[3]))


def _unavailable_pixels(raw,run,ticket,policy):
    """A uniform background is honest when native geometry is truly absent.

    This path retains the actual bytes and decodes the full fresh challenge.
    It never fills an image, changes its hash or invents a foreground subject.
    The caller has already required two actual unavailable renderer originals.
    """
    from PIL import Image
    exact(policy,{'marker','subject','source'});need(policy['source']=='world-render-target'
        and raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[-8:-4]==b'IEND')
    with Image.open(io.BytesIO(raw)) as source:
        need(source.width*source.height<=16000000);source.load();image=source.convert('RGB')
    mark=rectangle(policy['marker'],image.size);subject=rectangle(policy['subject'],image.size)
    need(max(mark[0],subject[0])>=min(mark[2],subject[2]) or max(mark[1],subject[1])>=min(mark[3],subject[3]))
    marker=image.crop(mark);need(marker.width>=128 and marker.height>=32);bits=[]
    for index in range(128):
        pixel=marker.getpixel((int((index%32+.5)*marker.width/32),int((index//32+.5)*marker.height/4)))
        if max(pixel)<70:bits.append('0')
        elif min(pixel)>185:bits.append('1')
        else:raise MarkerNotReady('ambiguous',cell=index,rgb=list(pixel))
    if ''.join(bits)!=''.join(f'{byte:08b}' for byte in challenge(run,ticket)):
        raise MarkerNotReady('mismatch',observed=hex(int(''.join(bits),2))[2:].zfill(32))
    return dict(sha256=hashlib.sha256(raw).hexdigest(),subjectChangedFraction=None),image.crop(subject).resize((128,96))


def compose(run,ticket,binding,frame,raw,policy,*,marker_nonce,marker_url,avatar_id=None,absence_basis=None):
    """Actual self or remote subject; absent bounds come only from an original."""
    identifier(run);identifier(ticket);context(binding);exact(frame,FIELDS)
    need(type(policy) is dict and policy.get('source')=='world-render-target')
    clock=validate_join(frame['clockJoin'],originals(frame));pid=int(binding['processIdentity']);epoch=clock['nativeAfter']['capturedEpochMs']
    need(clock['nativeBefore']['processId']==clock['nativeAfter']['processId']==pid)
    before,after=frame['worldBefore'],frame['worldAfter']
    for packet in (before,after):world.original(packet);need(packet['processId']==pid and packet['runId']==run)
    world.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=world.ACTION,runId=run),pid,epoch,before)
    need(before['source']['tree']==after['source']['tree'])
    markers=[world.owned_marker(packet,marker_nonce,marker_url) for packet in (before,after)];need(same(markers[0],markers[1]))
    a,b=before['source']['view'],after['source']['view']
    need(a['mode']==b['mode']=='look at' and a['perspective'] is b['perspective'] is True
        and near(a['position'],b['position'],.001) and orientation(a['rotation'],b['rotation'])
        and near([a['fieldOfViewDegrees']],[b['fieldOfViewDegrees']],.001)
        and near([a['aspectRatio']],[b['aspectRatio']],.0001) and same(before['source']['cameraOrbit'],after['source']['cameraOrbit']))
    capture,retirement=frame['capture'],frame['retirement']
    query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',commandId=capture.get('commandId'),requestId=capture.get('requestId'))
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(retirement,dict(query,operation=retirement.get('operation'),commandId=retirement.get('commandId')),pid,epoch)
    need(absent(retirement) and retirement['instance']==capture['instance'] and retirement['sequence']>capture['sequence'])
    source=capture['source'];trace=source['renderTrace'];view=trace['recordedView']
    need(trace['forwardDrawCalls']>0 and near(view['position'],a['position'],.001) and orientation(view['rotation'],a['rotation'])
        and near([view['fieldOfViewDegrees']],[a['fieldOfViewDegrees']],.001)
        and near([view['aspectRatio']],[a['aspectRatio']],.0001))
    left,right=frame['renderersBefore'],frame['renderersAfter'];avatar_renderers.original(left)
    avatar_renderers.validate(right,dict(schemaVersion=1,commandId=right['requestId'],action=avatar_renderers.ACTION,runId=run),pid,epoch,left)
    need(left['processId']==pid and left['runId']==run)
    for packet,rendered in ((before,left),(after,right)):
        own=[row for row in rendered['source']['avatars'] if row['self']];need(len(own)==1)
        actual=packet['source']['avatar'];body=world.body(packet,own[0]['sessionId'])
        need(abs(own[0]['modelScale']-actual['modelScale'])<.0001
            and own[0]['boundsReady']==actual['boundsReady'] and same(own[0]['bounds'],actual['bounds'])
            and orientation(body['orientation'],actual['orientation']) and near(body['velocity'],actual['velocity'],.00001))
    order=[before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],left['clockBefore']['epochMs'],left['clockAfter']['epochMs'],
        capture['requestedEpochMs'],trace['recordedEpochMs'],source['submittedEpochMs'],source['fenceObservedEpochMs'],source['pixelsReadEpochMs'],
        capture['capturedEpochMs'],retirement['requestedEpochMs'],retirement['capturedEpochMs'],right['clockBefore']['epochMs'],right['clockAfter']['epochMs'],
        after['clockBefore']['epochMs'],after['clockAfter']['epochMs']]
    need(order==sorted(order) and clock['nativeBefore']['capturedEpochMs']<=order[0]<=order[-1]<=epoch
        and abs(a['aspectRatio']-source['targetExtent'][0]/source['targetExtent'][1])<=.01)
    marker_box=projected_box(markers[0],view,source['targetExtent']);within(policy['marker'],marker_box)
    # The whole original Web quad can change with the challenge, including
    # pixels outside the selected challenge crop. None can count as Avatar.
    subject=policy['subject']
    need(max(marker_box[0],subject[0])>=min(marker_box[2],subject[2])
        or max(marker_box[1],subject[1])>=min(marker_box[3],subject[3]))
    remote=avatar_id is not None
    if not remote:
        own=[row for row in left['source']['avatars'] if row['self']];need(len(own)==1);avatar_id=own[0]['sessionId']
    rows=[avatar_renderers.avatar(packet,avatar_id,remote=remote) for packet in (left,right)]
    need(all(same(rows[0][key],rows[1][key]) for key in ('requestedUrl','resourceUrl','geometryLoaded','rigReady','modelScale','targetScale','addedToScene','shouldRender')))
    physical(before,after,avatar_id,remote=remote)
    for packet in (left,right):exclusive_subject(packet,avatar_id,policy,view,source['targetExtent'])
    loaded=rows[0]['geometryLoaded'] and rows[0]['rigReady'];basis_id=None
    if loaded:
        need(absence_basis is None and all(row['addedToScene'] and row['shouldRender'] for row in rows))
        bounds=[avatar_renderers.bounds(packet,avatar_id,remote=remote) for packet in (left,right)]
        measured,subject=image_observation(raw,run,ticket,policy)
    else:
        need(all(not row['geometryLoaded'] and not row['rigReady'] and not row['addedToScene'] for row in rows)
            and type(absence_basis) is tuple and len(absence_basis)==3)
        previous,prior_raw,prior_ticket=absence_basis
        prior,_=compose(run,prior_ticket,binding,previous,prior_raw,policy,marker_nonce=marker_nonce,marker_url=marker_url,
            avatar_id=avatar_id if remote else None)
        need(prior['modelLoaded'] and prior['sessionId']==avatar_id and prior['frameId']!=trace['frameId'])
        follow_native(previous['clockJoin']['nativeAfter'],clock['nativeBefore'])
        physical(previous['worldAfter'],before,avatar_id,remote=remote)
        old=avatar_renderers.avatar(previous['renderersAfter'],avatar_id,remote=remote)
        need(abs(old['modelScale']-rows[0]['modelScale'])<.0001)
        bounds=[prior['actualAvatarBounds']];basis_id=prior['frameId'];measured,subject=_unavailable_pixels(raw,run,ticket,policy)
    for bound in bounds:within(policy['subject'],avatar_box(bound,view,source['targetExtent']))
    return dict(iosAvatarImageVersion=VERSION,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=order[0],
        frameId=trace['frameId'],image=measured,markerId=markers[0]['id'],sessionId=avatar_id,remote=remote,modelLoaded=loaded,
        actualAvatarBounds=deepcopy(bounds[-1]) if loaded else None,subjectBounds=deepcopy(bounds[-1]),
        subjectBoundsSource='current-rendered-avatar' if loaded else 'previously-rendered-avatar',basisFrameId=basis_id),subject


def changed(run,binding,before,raw_before,ticket_before,after,raw_after,ticket_after,policy,*,marker_nonce,marker_url,avatar_id=None,owned_ids=None,absence_basis=None):
    left,subject=compose(run,ticket_before,binding,before,raw_before,policy,marker_nonce=marker_nonce,marker_url=marker_url,
        avatar_id=avatar_id,absence_basis=absence_basis)
    right,_=compose(run,ticket_after,binding,after,raw_after,policy,marker_nonce=marker_nonce,marker_url=marker_url,avatar_id=avatar_id)
    need(before['capture']['requestId']!=after['capture']['requestId'] and left['frameId']!=right['frameId'] and left['sessionId']==right['sessionId']
        and after['clockJoin']['hostBeforeMonotonic']>=before['clockJoin']['hostAfterMonotonic'])
    follow_native(before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
    world.preserve_unowned(before['worldAfter'],after['worldBefore'],set() if owned_ids is None else owned_ids)
    # Avatar scale/model changes can move the automatic camera. The original
    # user-controlled orbit and graphics options must remain unchanged; each
    # image separately joins its actual recorded view and genuine mesh box.
    a,b=before['worldAfter']['source'],after['worldBefore']['source']
    need(world.actual_domain(before['worldAfter'])==world.actual_domain(after['worldBefore'])
        and a['sceneUrl']==b['sceneUrl'] and same(a['cameraOrbit'],b['cameraOrbit']) and a['view']['mode']==b['view']['mode']
        and a['view']['fieldOfViewDegrees']==b['view']['fieldOfViewDegrees'] and a['view']['aspectRatio']==b['view']['aspectRatio']
        and same(before['capture']['source']['targetExtent'],after['capture']['source']['targetExtent'])
        and same(before['clockJoin']['nativeAfter']['graphics'],after['clockJoin']['nativeBefore']['graphics']))
    measured,_=image_observation(raw_after,run,ticket_after,policy,previous=subject,changed=True)
    return dict(iosAvatarImageChangeVersion=VERSION,before=left,after=right,subjectChangedFraction=measured['subjectChangedFraction'])
