"""Original independently read Assets world/parser facts, never rendered pixels.

The sampled getters scan actual complete inventories. The adopted UUID enters
only this pure join, after its normal-input/backend lineage is established.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.asset_backend_source import digest
from feature_journeys.contract import identifier
from ios.adapters import create_state,emote_world,assets_model_origin
from ios.adapters.create_peer import independent,domains,replicated

VERSION=1
ORIGINALS={'nativeBarrier','createBefore','domain','origin','createAfter'}
LINEAGE={'assetModelBakedInputProofVersion','runId','processId','domainId','entityId','creationRequestId','originRequestId',
    'readerId','nativeGeometryRequestId','backendRequestId','bakeRequestId','path','outputPath','sha256','bytes'}


def scene(value):
    exact(value,{'assetSceneSourceFrameVersion','binding','runId','role','clockJoin','originals'})
    need(type(value['assetSceneSourceFrameVersion']) is int and value['assetSceneSourceFrameVersion']==VERSION
        and value['role'] in ('primary','actor','actor-primary'))
    binding=context(value['binding']);run=identifier(value['runId']);pid=int(binding['processIdentity']);need(str(pid)==binding['processIdentity'] and pid>0)
    originals=value['originals'];exact(originals,ORIGINALS);clock=validate_join(value['clockJoin'],originals);epoch=clock['nativeAfter']['capturedEpochMs']
    need(same(originals['nativeBarrier'],clock['nativeBefore']) and clock['nativeBefore']['processId']==clock['nativeAfter']['processId']==pid
        and same(clock['nativeBefore']['lifecycle'],clock['nativeAfter']['lifecycle']))
    before,after=originals['createBefore'],originals['createAfter']
    for packet,prior in ((before,None),(after,before)):
        create_state.validate(packet,dict(schemaVersion=1,action=create_state.ACTION,commandId=packet['requestId'],runId=run),pid,epoch,prior)
        need(packet['iosCreateStateVersion']>=3 and packet['source']['complete'])
    domain,origin=originals['domain'],originals['origin']
    emote_world.validate(domain,dict(schemaVersion=1,action=emote_world.ACTION,commandId=domain['requestId'],runId=run),pid,epoch)
    assets_model_origin.validate(origin,dict(schemaVersion=1,action=assets_model_origin.ACTION,commandId=origin['requestId'],runId=run),pid,epoch)
    observed=emote_world.actual_domain(domain);left,right=before['source'],after['source'];native=origin['source']
    need(native['complete'] and native['history']['complete'] and left['domainId']==right['domainId']==native['domainId']==observed['domainId']
        and left['localSessionId']==right['localSessionId']==native['localSessionId']
        and observed['selfSha256']==hashlib.sha256(uuid.UUID(left['localSessionId']).bytes).hexdigest()
        and same(left['tree']['entities'],right['tree']['entities']) and same(left['tree'],native['tree'])
        and same(left['tree']['entities'],domain['source']['tree']['entities']))
    times=[clock['nativeBefore']['capturedEpochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],
        domain['clockBefore']['epochMs'],domain['clockAfter']['epochMs'],origin['clockBefore']['epochMs'],origin['clockAfter']['epochMs'],
        after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],epoch]
    need(times==sorted(times));return value


def peer_model(primary,peer,lineage):
    """Actual replicated entity and each independent original parser body.

    Callers must resolve lineage from OwnedAssetsParsedInput, not request input.
    Native loading flags and source bytes remain distinct from actual pixels.
    """
    scene(primary);scene(peer);exact(lineage,LINEAGE)
    need(type(lineage['assetModelBakedInputProofVersion']) is int and lineage['assetModelBakedInputProofVersion']==1
        and primary['role']=='actor-primary' and peer['role']=='actor' and primary['runId']==peer['runId']==lineage['runId'])
    digest(lineage['sha256']);need(integer(lineage['bytes'],1,32768));create_state.uuid(lineage['entityId']);create_state.uuid(lineage['domainId'])
    a,b=primary['originals'],peer['originals'];left,right=a['createAfter'],b['createAfter'];id_=lineage['entityId']
    # PIDs are local to each operating system and may coincide on independent
    # targets. Actual native clock instances still must identify two apps.
    need(primary['clockJoin']['nativeBefore']['instance']!=peer['clockJoin']['nativeBefore']['instance'])
    independent(left,right,primary['binding'],peer['binding']);domains(left,right,a['domain'],b['domain'])
    need(lineage['processId']==left['processId'] and lineage['domainId']==left['source']['domainId'] and len(replicated(left,right,[id_],primary['binding'],peer['binding']))==1)
    parsed=[assets_model_origin.parsed_input(frame['origin'],id_) for frame in (a,b)]
    need(a['origin']['instance']!=b['origin']['instance'] and a['origin']['source']['history']['instance']!=b['origin']['source']['history']['instance']
        and parsed[0]['readerId']!=parsed[1]['readerId'])
    for frame,body in zip((a,b),parsed):
        entities=[row for row in frame['createAfter']['source']['entities'] if row['id']==id_];need(len(entities)==1)
        need(body['processId']==frame['createAfter']['processId'] and body['runId']==lineage['runId'] and body['entityId']==id_
            and body['modelUrl']==body['watcherUrl']==entities[0]['modelURL']=='atp:'+lineage['path']
            and body['sha256']==lineage['sha256'] and body['bytes']==lineage['bytes'])
    return dict(assetModelPeerObservationVersion=VERSION,runId=lineage['runId'],entityId=id_,domainId=lineage['domainId'],
        primaryBinding=deepcopy(primary['binding']),peerBinding=deepcopy(peer['binding']),primaryRequestId=left['requestId'],peerRequestId=right['requestId'],
        primaryOriginRequestId=parsed[0]['requestId'],peerOriginRequestId=parsed[1]['requestId'],primaryReaderId=parsed[0]['readerId'],peerReaderId=parsed[1]['readerId'],
        sha256=lineage['sha256'],bytes=lineage['bytes'],renderedPixelsAvailable=False,resourceRetirementAvailable=False)
