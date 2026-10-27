"""Actual present/absent PNGs joined to the owned ordinary Model Delete.

This reads existing originals and derives a historical image result. It sends
no input, takes no image and retires no resource, source, actor or SDK owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from PIL import ImageChops
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import assets_model_images as images,assets_model_renderers as models,avatar_renderers
from ios.adapters.assets_image_basis import parsed_original,marker_original
from ios.adapters.assets_image_sample import AssetsImageSample
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.graphics_history import follow_native

VERSION=1


def avatar_semantics(packet):
    """Remove only original sampling metadata, retaining every pose and flag."""
    rows=deepcopy(packet['source']['avatars'])
    for row in rows:
        for key in ('rigPose','externalPose'):
            pose=row.get(key)
            if pose is not None:
                del pose['capturedEpochMs'];del pose['evaluationSequence']
    return dict(avatars=rows,avatarEntities=packet['source']['avatarEntities'])


def pair(run,ticket,binding,before,raw_before,after,raw_after,policy,parsed_proof,marker,*,after_epoch):
    """Pure image/source join; ordinary input ownership remains a separate join."""
    left,subject=images.compose(run,ticket,binding,before,raw_before,policy,parsed_proof,marker,after_epoch=after_epoch)
    right,current=images.compose(run,ticket,binding,after,raw_after,policy,parsed_proof,marker,
        after_epoch=after_epoch,absence_basis=(before,raw_before))
    target=parsed_proof['entityId'];a,b=before['createAfter'],after['createBefore'];old,new=a['source'],b['source']
    need(a['instance']==b['instance'] and a['sequence']<b['sequence'] and a['requestId']!=b['requestId']
        and old['domainId']==new['domainId'] and old['localSessionId']==new['localSessionId']
        and b['clockBefore']['epochMs']>=a['clockAfter']['epochMs']
        and b['clockBefore']['monotonicMs']>=a['clockAfter']['monotonicMs']
        and same([row for row in old['entities'] if row['id']!=target],new['entities']))
    old_tree,new_tree=old['tree'],new['tree']
    need(old_tree['treeInstance']==new_tree['treeInstance'] and new_tree['revisionBefore']>old_tree['revisionAfter']
        and same([row for row in old_tree['entities'] if row['id']!=target],new_tree['entities']))
    for module,first,last in ((models,before['modelsAfter'],after['modelsBefore']),
                              (avatar_renderers,before['avatarsAfter'],after['avatarsBefore'])):
        module.validate(last,dict(schemaVersion=1,commandId=last['requestId'],action=module.ACTION,runId=run),
            int(binding['processIdentity']),previous=first)
    need(same([row for row in before['modelsAfter']['source']['models'] if row['entityId']!=target],after['modelsBefore']['source']['models'])
        and same(avatar_semantics(before['avatarsAfter']),avatar_semantics(after['avatarsBefore']))
        and same(before['clockJoin']['nativeAfter']['graphics'],after['clockJoin']['nativeBefore']['graphics'])
        and same(before['clockJoin']['nativeAfter']['lifecycle'],after['clockJoin']['nativeBefore']['lifecycle']))
    delta=ImageChops.difference(current,subject);pixels=delta.load()
    fraction=sum(max(pixels[x,y])>25 for y in range(96) for x in range(128))/(128*96)
    need(fraction>=.05)
    right['image']['subjectChangedFraction']=fraction
    return left,right,fraction


def original_sample(sample):
    need(isinstance(sample,AssetsImageSample));sample.lock.assert_held()
    need(sample.previous is not None and same(sample.store.read(),sample.previous))
    state=sample.decode(sample.previous)
    need(same(state,sample.state) and state['phase'] in ('captured','qualified') and sample.raws.pending is None
        and state['original'] is not None and state['original']['phase']=='saved'
        and state['frameOwnership'] is not None and same(sample.frame_owner.store.read(),state['frameOwnership']))
    frame,raw=sample.source_frame(state)
    return state,frame,raw


def compose(owner,before,after,policy):
    """Reopen both image originals and the exact completed normal Delete WAL."""
    need(isinstance(owner,OwnedAssetsModelRemoval) and isinstance(before,AssetsImageSample) and isinstance(after,AssetsImageSample)
        and before is not after and owner.lock is before.lock is after.lock
        and owner.parsed is before.parsed is after.parsed and before.marker is after.marker
        and before.store.path.parent==after.store.path.parent==owner.store.path.parent
        and same(before.binding,after.binding) and before.run==after.run and before.request!=after.request)
    owner.lock.assert_held()
    source=owner.sources
    need(source.previous is not None and same(source.store.read(),source.previous)
        and same(source.decode(source.previous),source.state)
        and source.state['pending'] is None and source.raws.pending is None
        and owner.previous is not None and same(owner.store.read(),owner.previous))
    state=owner.decode(owner.previous)
    need(same(state,owner.state) and state['phase']=='model-gone' and state['contextClosedBy'] is not None)
    left,before_frame,raw_before=original_sample(before);right,after_frame,raw_after=original_sample(after)
    need(left['ticket']==right['ticket'] and same(left['parsedSnapshot'],right['parsedSnapshot']))
    proof=parsed_original(owner.parsed,left['parsedSnapshot'])
    mark=marker_original(before.marker,left['markerSnapshot']);other_mark=marker_original(after.marker,right['markerSnapshot'])
    need(same(mark,other_mark) and proof['entityId']==owner.target())
    baseline=owner.frame(state['baseline']);closed=owner.frame(state['contextClosedBy'])
    follow_native(before_frame['clockJoin']['nativeAfter'],baseline['clockJoin']['nativeBefore'])
    follow_native(closed['clockJoin']['nativeAfter'],after_frame['clockJoin']['nativeBefore'])
    need(before_frame['clockJoin']['hostAfterEpochMs']<=baseline['clockJoin']['hostBeforeEpochMs']
        and before_frame['clockJoin']['hostAfterMonotonic']<=baseline['clockJoin']['hostBeforeMonotonic']
        and closed['clockJoin']['hostAfterEpochMs']<=after_frame['clockJoin']['hostBeforeEpochMs']
        and closed['clockJoin']['hostAfterMonotonic']<=after_frame['clockJoin']['hostBeforeMonotonic'])
    present,absent,fraction=pair(before.run,left['ticket'],before.binding,before_frame,raw_before,after_frame,raw_after,policy,proof,mark,
        after_epoch=left['hostBarrier'])
    result=dict(assetModelRemovalImageChangeVersion=VERSION,before=present,after=absent,subjectChangedFraction=fraction,
        removal=deepcopy(state['result']),resourceRetirementAvailable=False)
    for child in (owner,source,before,after):need(same(child.store.read(),child.previous))
    return result
