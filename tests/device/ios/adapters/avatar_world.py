"""Original Avatar marker/domain/camera/whole-tree reads, without normal input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_observation import validate as script_packet
from adapters.native_avatar_receive import sha
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.scene_inventory import tree,tree_semantics,uint64
from ios.adapters.avatar_state import session,text

VERSION=1
ACTION='feature-ios-avatar-world'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    identifier(value['runId']);return value


def vector(value,count):
    need(type(value) is list and len(value)==count and all(number(v,-1e8,1e8) for v in value))
    if count==4:need(.9<=sum(v*v for v in value)<=1.1)
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosAvatarWorldVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAvatarWorldVersion']) is int and value['iosAvatarWorldVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and type(value['instance']) is str
        and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1,1_000_000_000)
        and value['clockDomain']=='native-main-avatar-world')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','tree','scriptOriginal','markers','sceneUrl','domain','avatar','view','cameraOrbit'}
        | ({'bodies'} if 'bodies' in source else set()))
    need(source['complete'] is True);inventory=tree(source['tree']);need(inventory['complete']);text(source['sceneUrl'],4096)
    script=source['scriptOriginal'];script_packet(script,script['requestId'],pid,after['epochMs'])
    need(before['epochMs']<=script['requestedEpochMs']<=script['capturedEpochMs']<=after['epochMs']
        and script['source'].get('effectSourceVersion')==1)
    effects={r['id']:r for r in script['source']['effects']['entities']}
    need(type(source['markers']) is list and len(source['markers'])<=4)
    ids=set();entries={r['id']:r for r in inventory['entities']}
    for marker in source['markers']:
        exact(marker,{'id','name','type','hostType','sourceUrl','userData','position','rotation','dimensions','visible','collisionless','lastEditedEpochUs'})
        session(marker['id']);need(marker['id'] not in ids);ids.add(marker['id'])
        for field in ('name','type','sourceUrl','userData'):text(marker[field],4096)
        need(marker['hostType'] in ('local','avatar','domain') and type(marker['visible']) is bool and type(marker['collisionless']) is bool)
        vector(marker['position'],3);vector(marker['rotation'],4);vector(marker['dimensions'],3)
        need(all(v>0 for v in marker['dimensions']));uint64(marker['lastEditedEpochUs'])
        need(marker['id'] in effects and marker['id'] in entries)
        effect=effects[marker['id']]
        need(all(marker[k]==effect[k] for k in ('id','name','type','hostType','userData'))
            and int(marker['lastEditedEpochUs'])==effect['lastEditedEpochUs']
            and marker['lastEditedEpochUs']==entries[marker['id']]['lastEditedEpochUs'])
        try:data=json.loads(marker['userData'])
        except (ValueError,UnicodeError):raise NativeUIError('Original Avatar marker owner data is malformed') from None
        exact(data,{'kind','runId','nonce'})
        need(data['kind']=='avatar-marker-v1' and data['runId']==value['runId']);identifier(data['nonce'])
    domain=source['domain'];exact(domain,{'connected','serverless','domainId','selfSha256','avatarMixerSha256'})
    need(type(domain['connected']) is bool and type(domain['serverless']) is bool and sha(domain['selfSha256'])
        and (domain['avatarMixerSha256'] is None or sha(domain['avatarMixerSha256'])))
    need(type(domain['domainId']) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',domain['domainId']))
    avatar=source['avatar'];exact(avatar,{'feetPosition','orientation','velocity','inAir','flying','modelScale','boundsReady','bounds'})
    for field in ('feetPosition','velocity'):vector(avatar[field],3)
    vector(avatar['orientation'],4);need(number(avatar['modelScale'],.0001,1000))
    for field in ('inAir','flying','boundsReady'):need(type(avatar[field]) is bool)
    if avatar['boundsReady']:
        bounds=avatar['bounds'];exact(bounds,{'corner','dimensions'});vector(bounds['corner'],3);vector(bounds['dimensions'],3)
        need(all(v>0 for v in bounds['dimensions']))
    else:need(avatar['bounds'] is None)
    view=source['view'];exact(view,{'position','rotation','mode','fieldOfViewDegrees','aspectRatio','perspective'})
    vector(view['position'],3);vector(view['rotation'],4);text(view['mode'],64)
    need(number(view['fieldOfViewDegrees'],1,179) and number(view['aspectRatio'],.01,100) and type(view['perspective']) is bool)
    orbit=source['cameraOrbit'];exact(orbit,{'lookAtRotation','boomLength','minimumBoomLength','defaultBoomLength'})
    vector(orbit['lookAtRotation'],4)
    for field in ('boomLength','minimumBoomLength','defaultBoomLength'):need(number(orbit[field],0,10000))
    if 'bodies' in source:body_collection(source['bodies'],value)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and before['epochMs']>=previous['clockAfter']['epochMs']
            and before['monotonicMs']>=previous['clockAfter']['monotonicMs'])
        old=previous['source']['tree'];need(inventory['treeInstance']==old['treeInstance']
            and inventory['revisionBefore']>=old['revisionAfter'])
        if inventory['revisionBefore']==old['revisionAfter']:need(inventory==old)
        if 'bodies' in previous['source']:
            need('bodies' in source);left,right=previous['source']['bodies'],source['bodies']
            need(right['instance']==left['instance'] and right['sequence']>left['sequence']
                and right['capturedEpochMs']>=left['capturedEpochMs'])
    return value


def body_collection(value,world):
    exact(value,{'avatarBodyCollectionVersion','instance','sequence','capturedEpochMs','complete','avatars'})
    need(type(value['avatarBodyCollectionVersion']) is int and value['avatarBodyCollectionVersion']==1
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1,1000000000) and value['complete'] is True
        and integer(value['capturedEpochMs'],world['clockBefore']['epochMs'],world['clockAfter']['epochMs'])
        and type(value['avatars']) is list and len(value['avatars'])<=64)
    ids=[];own=[]
    for row in value['avatars']:
        exact(row,{'sessionId','self','replicated','position','orientation','velocity'});session(row['sessionId']);ids.append(row['sessionId'])
        need(type(row['self']) is bool and type(row['replicated']) is bool)
        vector(row['position'],3);vector(row['orientation'],4);vector(row['velocity'],3)
        if row['self']:own.append(row)
    need(ids==sorted(set(ids)) and len(own)==1 and not own[0]['replicated'])
    import hashlib,uuid
    need(hashlib.sha256(uuid.UUID(own[0]['sessionId']).bytes).hexdigest()==world['source']['domain']['selfSha256'])
    return value


def body(value,avatar_id,*,remote=False):
    """Actual root transform even when no render model or bounds are ready."""
    original(value);session(avatar_id);need(type(remote) is bool and 'bodies' in value['source'])
    rows=[row for row in value['source']['bodies']['avatars'] if row['sessionId']==avatar_id]
    need(len(rows)==1 and rows[0]['self'] is (not remote) and not rows[0]['replicated'])
    return deepcopy(rows[0])


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def actual_domain(value):
    original(value);domain=value['source']['domain']
    need(domain['connected'] is True and domain['serverless'] is False and sha(domain['avatarMixerSha256'])
        and domain['domainId']!='00000000-0000-0000-0000-000000000000')
    return deepcopy(domain)


def owned_marker(value,nonce,url):
    original(value);identifier(nonce);text(url);need(url)
    rows=value['source']['markers'];need(len(rows)==1);row=rows[0];data=json.loads(row['userData'])
    need(data['nonce']==nonce and row['name']=='e2e-'+value['runId']+'-script' and row['type']=='Web'
        and row['hostType']=='local' and row['visible'] is True and row['collisionless'] is True and row['sourceUrl']==url)
    return deepcopy(row)


def preserve_unowned(before,after,owned_ids):
    original(before);original(after);need(type(owned_ids) is set and before['runId']==after['runId'])
    for value in owned_ids:session(value)
    maps=[{k:v for k,v in tree_semantics(frame['source']['tree']).items() if k not in owned_ids} for frame in (before,after)]
    need(maps[0]==maps[1]);return maps[1]


class IOSAvatarWorld(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAvatarWorldAcquisitionVersion'
