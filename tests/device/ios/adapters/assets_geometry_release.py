"""Original post-Delete Geometry-consumer quiet proof, never whole retirement.

Actual parent/source files provide every fact. No input, query, cache eviction,
process/SDK close, source write or fresh timestamp is produced by this join.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import assets_model_origin as origin
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.adapters.graphics_history import follow_native

VERSION=1


def parent(owner):
    need(isinstance(owner,OwnedAssetsModelRemoval));owner.lock.assert_held()
    parsed=owner.parsed;source=owner.sources
    need(owner.previous is not None and same(owner.store.read(),owner.previous)
        and source.previous is not None and same(source.store.read(),source.previous)
        and same(source.decode(source.previous),source.state)
        and source.state['pending'] is None and source.raws.pending is None)
    parsed.authoritative();state=owner.decode(owner.previous)
    need(same(state,owner.state) and state['phase']=='model-gone' and state['contextClosedBy'] is not None)
    lineage=parsed.state['result'];baseline=parsed.frame(parsed.state['sourceIndex'])['originals']['origin']
    original=origin.geometry_consumers(baseline,lineage['readerId'])
    need(original['bodySha256']==lineage['sha256'] and original['bodyBytes']==lineage['bytes']
        and original['processId']==lineage['processId'] and original['runId']==lineage['runId'])
    closed=owner.frame(state['contextClosedBy'])
    reference=next(ref for ref in source.state['frames'] if ref['index']==state['contextClosedBy'])
    return lineage,baseline,closed,deepcopy(source.originals.expand(reference))


def source_frames(source,references):
    need(isinstance(source,AssetsSceneSources) and source.role=='primary');source.lock.assert_held()
    need(source.previous is not None and same(source.store.read(),source.previous)
        and same(source.decode(source.previous),source.state)
        and source.state['pending'] is None and source.raws.pending is None
        and type(references) is list and 1<=len(references)<=8 and source.state['frames']
        and references[-1]==source.state['frames'][-1])
    result=[];indexes=[]
    for reference in references:
        need(reference in source.state['frames']);expanded=source.originals.expand(reference)
        frame=source.originals.read(expanded);source.frame(frame)
        indexes.append(expanded['index']);result.append(frame['scene'])
    need(indexes==sorted(set(indexes)))
    return result


def original_consumers(baseline,current,lineage):
    """Scoped actual weak consumers and mapped QObjects, not requested flags."""
    origin.validate(current,dict(schemaVersion=1,action=origin.ACTION,commandId=current['requestId'],runId=current['runId']),
        lineage['processId'],previous=baseline)
    facts=origin.geometry_consumers(current,lineage['readerId'])
    need(facts['bodySha256']==lineage['sha256'] and facts['bodyBytes']==lineage['bytes'])
    before=origin.geometry_consumers(baseline,lineage['readerId'])
    need(same([row['id'] for row in before['geometries']],[row['id'] for row in facts['geometries'][:len(before['geometries'])]]))
    downloads={row['id']:row for row in current['source']['history']['downloads']}
    mappings=sorted({id_ for row in facts['geometries'] for id_ in row['mappingIds']})
    retained=[]
    for id_ in mappings:
        row=downloads[id_];need(row['kind']=='mapping')
        retained.append(dict(id=id_,originalLeaseAlive=row['resourceAlive'],resourceObjectAlive=row['resourceObjectAlive']))
    facts['mappingResources']=retained
    facts['originalConsumersGone']=(facts['allKnownGeometryDead'] and not any(facts[key] for key in
        ('readerAlive','originalLeaseAlive','resourceObjectAlive','hfmAlive'))
        and all(not row['originalLeaseAlive'] and not row['resourceObjectAlive'] for row in retained))
    return facts


def quiet(first,last):
    """Three seconds strictly between acquisitions, in both actual clocks."""
    a,b=first['clockJoin'],last['clockJoin'];left,right=first['originals'],last['originals']
    return (b['hostBeforeMonotonic']-a['hostAfterMonotonic']>=3
        and b['hostBeforeEpochMs']-a['hostAfterEpochMs']>=3000
        and b['nativeBefore']['capturedEpochMs']-a['nativeAfter']['capturedEpochMs']>=3000
        and right['origin']['source']['history']['clock']['monotonicMs']-left['origin']['source']['history']['clock']['monotonicMs']>=3000
        and right['domain']['clockBefore']['monotonicMs']-left['domain']['clockAfter']['monotonicMs']>=3000)


def _context(owner,source,references):
    """One pure caller's fully guarded ancestry and exact source originals."""
    need(isinstance(owner,OwnedAssetsModelRemoval) and isinstance(source,AssetsSceneSources)
        and source.lock is owner.lock and source.store.path.parent==owner.store.path.parent
        and source.run==owner.sources.run and same(source.binding,owner.sources.binding))
    lineage,baseline,closed,parent_ref=parent(owner);frames=source_frames(source,references)
    previous=closed;observations=[];prior_origin=baseline
    for frame in frames:
        window=frame['clockJoin'];old_window=previous['clockJoin'];originals=frame['originals']
        need(window['hostBeforeEpochMs']>=old_window['hostAfterEpochMs']
            and window['hostBeforeMonotonic']>=old_window['hostAfterMonotonic'])
        follow_native(old_window['nativeAfter'],window['nativeBefore'])
        for packet in (originals['createBefore'],originals['createAfter']):
            need(not any(row['id']==lineage['entityId'] for row in packet['source']['entities'])
                and same(packet['source']['tree']['entities'],closed['originals']['createAfter']['source']['tree']['entities']))
        need(not any(row['entityId']==lineage['entityId'] for row in originals['origin']['source']['models']))
        facts=original_consumers(prior_origin,originals['origin'],lineage)
        need(facts['originalConsumersGone'])
        observations.append(facts);previous=frame;prior_origin=originals['origin']
    need(len(frames)>=3 and quiet(frames[0],frames[-1]))
    # The complete actual native registry must stay quiet, including unrelated
    # returned/dead work. Its changing sample clock is kept separately intact.
    first=frames[0]['originals']['origin']['source']['history']
    for frame in frames[1:]:
        current=frame['originals']['origin']['source']['history']
        need(same({k:v for k,v in first.items() if k!='clock'},{k:v for k,v in current.items() if k!='clock'}))
    for child in (owner,owner.sources,source):need(same(child.store.read(),child.previous))
    result=dict(assetModelGeometryReleaseVersion=VERSION,runId=source.run,binding=deepcopy(source.binding),
        entityId=lineage['entityId'],readerId=lineage['readerId'],bodySha256=lineage['sha256'],bodyBytes=lineage['bytes'],
        removalCommandId=owner.state['result']['inputCommandId'],closedOriginal=parent_ref,sourceOriginals=deepcopy(references),
        observations=observations,capturedEpochMs=frames[-1]['clockJoin']['hostBeforeEpochMs'],
        originalConsumersGone=True,resourceRetirementAvailable=False)

    return result,lineage,baseline,frames


def compose(owner,source,references):
    """Reopen actual normal-removal ancestry and exact latest scene originals."""
    result,*_=_context(owner,source,references)
    return result
