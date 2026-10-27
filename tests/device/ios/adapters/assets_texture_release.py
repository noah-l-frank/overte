"""Scoped History5 texture quiet join after original normal Model removal.

Pure caller only: no query, input, write, flush or product owner retirement.
Weak map/source expiry is not decoder, destructor, GPU, OS or SDK completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import assets_geometry_release as geometry,assets_model_origin as origin
from ios.adapters import assets_strong_release as strong,assets_texture_ownership as texture

VERSION=1


def texture_history(baseline,packets,lineage):
    """Original positive linked groups and every subsequent actual source."""
    reader=lineage['readerId'];original=texture.consumers(baseline,reader)
    need(original['bodySha256']==lineage['sha256'] and original['bodyBytes']==lineage['bytes']
        and original['processId']==lineage['processId'] and original['runId']==lineage['runId']
        and type(packets) is list and 1<=len(packets)<=8)
    known={row['id']:row for row in original['nodes']}
    need(any(row['mapId'] in known and row['sourceId'] in known
        and known[row['mapId']]['strongOwnersAlive'] and known[row['sourceId']]['strongOwnersAlive']
        for row in original['links']))
    observations=[];previous=baseline
    for packet in packets:
        origin.validate(packet,dict(schemaVersion=1,action=origin.ACTION,commandId=packet['requestId'],runId=lineage['runId']),
            lineage['processId'],previous=previous)
        facts=texture.consumers(packet,reader)
        need(facts['bodySha256']==lineage['sha256'] and facts['bodyBytes']==lineage['bytes']
            and facts['processId']==lineage['processId'] and facts['runId']==lineage['runId']
            and set(known)<={row['id'] for row in facts['nodes']})
        # The globally append-only inventory can contain an older shared group
        # first linked to this reader later. Do not invent a selected-row prefix.
        observations.append(facts);previous=packet
    return original,observations


def compose(owner,source,references):
    """One guarded History5 traversal with all original quiet clocks retained."""
    result,lineage,baseline,frames=geometry._texture_context(owner,source,references)
    packets=[frame['originals']['origin'] for frame in frames]
    original_strong,strong_observations=strong._texture_strong_history(baseline,packets,lineage)
    original_texture,texture_observations=texture_history(baseline,packets,lineage)
    need(all(row['allKnownStrongOwnersGone'] for row in strong_observations)
        and all(row['allKnownTextureOwnersGone'] for row in texture_observations))
    for child in (owner,owner.sources,source):need(same(child.store.read(),child.previous))
    return dict(assetModelTextureReleaseVersion=VERSION,runId=result['runId'],binding=deepcopy(result['binding']),
        entityId=result['entityId'],readerId=result['readerId'],bodySha256=result['bodySha256'],bodyBytes=result['bodyBytes'],
        removalCommandId=result['removalCommandId'],closedOriginal=result['closedOriginal'],sourceOriginals=result['sourceOriginals'],
        capturedEpochMs=result['capturedEpochMs'],
        geometryObservations=result['observations'],originalStrongConsumers=original_strong,strongObservations=strong_observations,
        originalTextureConsumers=original_texture,textureObservations=texture_observations,
        originalMeshMaterialTextureOwnersGone=True,decoderCompletionAvailable=False,destructorCompletionAvailable=False,
        gpuCompletionAvailable=False,resourceRetirementAvailable=False)
