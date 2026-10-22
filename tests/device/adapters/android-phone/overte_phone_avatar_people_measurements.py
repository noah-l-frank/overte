"""Avatar/People public state from independent native, storage and wire facts.

No requested outcome or expected feature state is accepted by this projection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from urllib.parse import urlsplit
from adapters.native_feature_observation import need,fresh
from feature_journeys.contract import state as public_state
from feature_journeys.fixtures import context,pinned_resource
from feature_journeys.avatar_people_service import validate_status
from feature_journeys.phase_fixture import PhasePending
from overte_phone_avatar_people_native import validate,ACTION,digest
from overte_phone_script_history import same


def request(packet):return dict(schemaVersion=1,commandId=packet['commandId'],runId=packet['runId'],action=ACTION)


def resources(run,phase,fixture_url):
    """Only the immutable original phase inputs identify owned resource URLs."""
    urls={'A':set(),'missing':set(),'wearable':set()}
    for row in phase['activations']:
        stimulus=row['stimulus'];inputs=stimulus['inputs'];verb=stimulus['verb']
        if verb=='avatar-url':
            key={'avatar-a.fst':'A','missing.fst':'missing'}.get(inputs.get('resource'));need(key is not None)
            urls[key].add(fixture_url+'tickets/'+row['ticket']+'/'+inputs['resource'])
        elif verb=='wearable-add':
            need(inputs.get('resource')=='gltf-bundle/main.gltf');urls['wearable'].add(fixture_url+'tickets/'+row['ticket']+'/'+inputs['resource'])
    return urls


def native_model_semantics(model):
    result={key:deepcopy(model[key]) for key in ('sessionId','replicated','requestedUrl','modelInstance','rigId','loaded','visible','addedToScene','targetScale','scale','hipsJoint','feetPosition','orientation','shouldRender','geometry')}
    for key in ('advertisedLoads','modelLoads'):
        result[key]={field:deepcopy(model[key][field]) for field in ('instance','currentGeneration','requestedSha256','events')}
    return result


def entity_semantics(source):
    result=deepcopy(source)
    for row in result['entities']:
        if row['model'] is not None:
            history=row['model']['modelLoads']
            row['model']['modelLoads']={key:history[key] for key in ('instance','currentGeneration','requestedSha256','events')}
    return result


def body(model,initial,urls):
    requested=model['requestedUrl'];geometry=model['geometry'];loaded=model['loaded']
    label='original' if requested==initial['requestedUrl'] else 'A' if requested in urls['A'] else 'missing' if requested in urls['missing'] else None
    need(label is not None and not model['replicated'])
    if geometry is None:
        need(not loaded);actual='unavailable'
    else:
        if not loaded:raise PhasePending('The original avatar geometry is not loaded yet')
        need(geometry['texturesLoaded'] and model['visible'] and model['addedToScene'] and model['hipsJoint']>=0)
        loaded_url=geometry['url'];a_models={url.rsplit('/',1)[0]+'/mannequin/mannequin.fbx' for url in urls['A']}
        if loaded_url in a_models:actual='A'
        elif loaded_url==initial['geometry']['url']:actual='fallback' if label=='missing' else 'original'
        else:need(False)
        need((actual=='A' and label=='A') or (actual=='original' and label=='original') or (actual=='fallback' and label=='missing'))
    generation=model['advertisedLoads']['currentGeneration'];failure=False
    if label=='missing':
        failure=any(row['generation']==generation and row['kind']=='finished' and row['success'] is False
            and row['requestedSha256']==digest(requested) and row['resourceSha256']==digest(requested) for row in model['advertisedLoads']['events'])
    need(abs(model['scale']-model['targetScale'])<=.005)
    return dict(avatar=actual,requestedAvatar=label,modelLoaded=loaded,loadFailed=failure,scale=round(model['scale'],2))


def consumed(run,url,native,backend,*,status=200):
    """Join real product consumption, completed service write and repository pin."""
    parsed=urlsplit(url);prefix='/feature-fixture/v1/runs/'+run+'/tickets/'
    need(parsed.scheme=='https' and parsed.path.startswith(prefix) and not parsed.query and not parsed.fragment)
    relative=parsed.path[len(prefix):].split('/',1);need(len(relative)==2)
    ticket,name=relative;expected=None
    if status==200:
        raw=pinned_resource(name);expected=(len(raw),hashlib.sha256(raw).hexdigest())
    candidates=[row for row in native['events'] if row['requestedUrlSha256']==digest(url) and row['replyUrlSha256']==digest(url)
        and row['runId']==run and row['ticket']==ticket and row['resource']==name and row['httpStatus']==status
        and not row['fromCache'] and not row['redirected'] and (row['networkError']==0 if status==200 else row['networkError']!=0)]
    originals=[]
    for actual in candidates:
        writes=[row for row in backend['responses'] if row['responseId']==actual['responseId']]
        if len(writes)!=1:continue
        write=writes[0]
        if write['role']=='resource' and write['method']=='GET' and write['path']==parsed.path and write['requestTarget']==parsed.path and write['ticket']==ticket and write['status']==status and write['bytes']==actual['bytes'] and write['sha256']==actual['sha256']:
            if expected is None or expected==(actual['bytes'],actual['sha256']):originals.append((actual,write))
    need(originals);return originals


def model_resources(run,model,urls,native,backend):
    geometry=model['geometry']
    if model['requestedUrl'] in urls['missing']:consumed(run,model['requestedUrl'],native,backend,status=404)
    if geometry is None:return
    if model['requestedUrl'] in urls['A']:
        consumed(run,model['requestedUrl'],native,backend)
        consumed(run,geometry['url'],native,backend)
        need(geometry['textures'])
        for url in set(geometry['textures'].values()):consumed(run,url,native,backend)


def wearable(run,source,urls,backend):
    origins=[row for row in source['avatarEntityOrigins']['events'] if row['modelUrlSha256'] in {digest(url) for url in urls['wearable']}]
    need(len(origins)<=1 and all(row['treePresent'] for row in origins))
    if not origins:return False,[]
    original=origins[0];owned=original['entityId'];actual=source['avatarEntities']
    if owned in actual['absentIds']:raise PhasePending('An advertised avatar entity is not available in the actual tree yet')
    rows=[row for row in actual['entities'] if row['entityId']==owned];need(len(rows)<=1)
    if not rows:return False,[owned]
    row=rows[0];avatar=source['avatar'];need(row['type']=='Model' and row['host']=='avatar' and row['visible']
        and row['parentId']==original['parentId']==avatar['sessionId'] and row['parentJointIndex']==original['parentJointIndex']==avatar['hipsJoint']
        and row['modelUrl'] in urls['wearable'] and digest(row['modelUrl'])==original['modelUrlSha256'])
    model=row['model']
    if model is None or not model['loaded'] or model['geometry'] is None or not model['geometry']['texturesLoaded']:
        raise PhasePending('The original owned wearable Model and textures are not loaded yet')
    need(model['visible'] and model['addedToScene'] and model['geometry']['url']==row['modelUrl'] and model['geometry']['textures'])
    consumed(run,row['modelUrl'],source['resourceReplies'],backend)
    base=row['modelUrl'].rsplit('/',1)[0]+'/'
    consumed(run,base+'mesh/triangle.bin',source['resourceReplies'],backend)
    for url in set(model['geometry']['textures'].values()):consumed(run,url,source['resourceReplies'],backend)
    return True,[owned]


def social_replies(source,backend,origin,role):
    """Actual service writes are insufficient without original XHR completion."""
    writes=[row for row in backend['responses'] if row['role']==role]
    for actual in source['peopleReplies']['events']:
        rows=[row for row in writes if row['responseId']==actual['responseId']]
        need(len(rows)==1);write=rows[0]
        need(actual['method']==write['method'] and actual['httpStatus']==write['status'] and actual['bytes']==write['bytes']
            and actual['sha256']==write['sha256'] and not actual['redirected'] and not actual['fromCache']
            and actual['requestedUrlSha256']==actual['replyUrlSha256'])
        need(actual['requestedUrlSha256']==digest(origin+write['requestTarget'])
            and actual['requestBodySha256']==write['requestBodySha256'])
        need(actual['networkError']==0 if actual['httpStatus']==200 else actual['networkError']!=0)
    return [row for row in writes if any(actual['responseId']==row['responseId'] for actual in source['peopleReplies']['events'])]


def measurement(run,before,after,backend,phase,baseline,fixture_url,provider_instance,*,pid,epoch,after_epoch):
    validate(before,request(before),pid,epoch);validate(after,request(after),pid,epoch,previous=before)
    need(before['runId']==after['runId']==run and before['requestedEpochMs']>=after_epoch)
    origin=urlsplit(fixture_url);origin=origin.scheme+'://'+origin.netloc
    validate_status(backend,run=run,request=backend['requestId'],instance=provider_instance);fresh(backend['capturedEpochMs'],epoch)
    left,right=before['source'],after['source'];initial=baseline['source']
    for source in (left,right):
        need(source['connected'] and source['domainId']==backend['domainId'] and source['canRezAvatarEntities']
            and source['accountOrigin'].rstrip('/')==origin and source['auth']['loggedIn']
            and source['auth']['principalSha256']==digest(backend['principals']['primary']) and not source['auth']['observation']['loginPending']
            and not source['auth']['observation']['refreshPending'])
    if not same(native_model_semantics(left['avatar']),native_model_semantics(right['avatar'])) or not same(left['view'],right['view']) or not same(left['bookmarks'],right['bookmarks']) or not same(entity_semantics(left['avatarEntities']),entity_semantics(right['avatarEntities'])):
        raise PhasePending('Original Avatar/People facts changed inside the acquisition bracket')
    need(left['avatar']['sessionId']==initial['avatar']['sessionId'])
    urls=resources(run,phase,fixture_url);actual=body(left['avatar'],initial['avatar'],urls)
    model_resources(run,left['avatar'],urls,left['resourceReplies'],backend)
    actual['wearable'],owned_ids=wearable(run,left,urls,backend)
    name=context(run)['name'];bookmarks=left['bookmarks']['bookmarks'];actual['bookmarked']=name in bookmarks
    if actual['bookmarked']:
        record=bookmarks[name];need(record.get('version')==3 and record.get('avatarUrl') in urls['A'] and record.get('avatarScale')==initial['avatar']['scale']
            and type(record.get('avatarEntites')) is list)
        # The main bookmark precedes the owned wearable and cannot retain it.
        need(not any(row.get('properties',{}).get('modelURL') in urls['wearable'] for row in record['avatarEntites']))
    view=left['view']['people'];dialog=view['dialog'];consent=view['consent'] if view['present'] else dict(phase='idle')
    connected=bool(backend['relationships']['primary']);pending=consent['phase'] in ('outgoing','incoming','accepted','submitting','polling')
    actual['connection']='connected' if connected else 'pending' if pending else 'none';actual['dialog']=dialog
    receipts=social_replies(left,backend,origin,'primary')
    if connected:
        need(view['present'] and not backend['pending'] and any(row['method']=='POST' and row['status']==200 for row in receipts))
        rows=left['view']['models']['connectionsUserModel']['rows']
        need(sum(row.get('userName')==backend['principals']['peer'] and row.get('connection')=='connection' for row in rows)==1)
    if pending:need(dialog and view['present'] and consent.get('peer') not in ('',left['avatar']['sessionId']) and consent.get('requestId'))
    if not connected and not pending:need(not dialog and not backend['pending'])
    return deepcopy(public_state('avatar-people',actual,run))
