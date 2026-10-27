"""Original normal-removal quiet join for mesh/material sharing groups.

No cache/renderer eviction, query, input, write or resource end is performed.
Weak strong-owner expiry does not demonstrate destructor, GPU or OS drainage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import assets_geometry_release as geometry,assets_model_origin as origin

VERSION=1


def strong_history(baseline,packets,lineage):
    """Actual original positive mesh ownership and its subsequent observations."""
    reader=lineage['readerId'];original=origin.strong_consumers(baseline,reader)
    need(original['bodySha256']==lineage['sha256'] and original['bodyBytes']==lineage['bytes']
        and original['processId']==lineage['processId'] and original['runId']==lineage['runId']
        and any(row['kind']=='mesh' and row['strongOwnersAlive'] for row in original['consumers'])
        and type(packets) is list and 1<=len(packets)<=8)
    observations=[];previous=baseline
    for packet in packets:
        origin.validate(packet,dict(schemaVersion=1,action=origin.ACTION,commandId=packet['requestId'],runId=lineage['runId']),
            lineage['processId'],previous=previous)
        earlier=previous['source']['history'];known={row['id']:row for row in earlier['consumerOwnership']['rows']}
        for row in packet['source']['history']['consumerOwnership']['rows']:
            old=known.get(row['id'])
            if old is not None and old['strongOwnersAlive'] and not row['strongOwnersAlive']:
                origin.ordered(earlier['clock'],row['ownershipExpiryObserved'])
        facts=origin.strong_consumers(packet,reader)
        need(facts['bodySha256']==lineage['sha256'] and facts['bodyBytes']==lineage['bytes']
            and facts['processId']==lineage['processId'] and facts['runId']==lineage['runId']
            and same([row['id'] for row in original['consumers']],
                [row['id'] for row in facts['consumers'][:len(original['consumers'])]]))
        observations.append(facts);previous=packet
    return original,observations


def compose(owner,source,references):
    """One guarded parent traversal, all actual original clocks retained."""
    result,lineage,baseline,frames=geometry._context(owner,source,references)
    original,observed=strong_history(baseline,[frame['originals']['origin'] for frame in frames],lineage)
    need(all(row['allKnownStrongOwnersGone'] for row in observed))
    # The existing complete-registry quiet check includes every ownership row;
    # no later sampling clock is substituted for a measured original stamp.
    for child in (owner,owner.sources,source):need(same(child.store.read(),child.previous))
    return dict(assetModelStrongReleaseVersion=VERSION,runId=result['runId'],binding=deepcopy(result['binding']),
        entityId=result['entityId'],readerId=result['readerId'],bodySha256=result['bodySha256'],bodyBytes=result['bodyBytes'],
        geometryRelease=result,originalStrongConsumers=original,observations=observed,
        originalMeshMaterialOwnersGone=True,destructorCompletionAvailable=False,resourceRetirementAvailable=False)
