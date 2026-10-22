"""Independent consent, response consumption and materialized Pal originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from urllib.parse import urlsplit,parse_qsl
from adapters.native_account_observation import validate as account_original
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import context
from ios.adapters import avatar_social_http as http,avatar_scripts,people_model
from ios.adapters.avatar_code import for_worker
from ios.adapters.avatar_peer import state_original

VERSION=1
REQUEST='/api/v1/user/connection_request'
CONNECTIONS='/api/v1/users/connections'


def roles(primary,actor,primary_binding,actor_binding,principals,origin,run,ticket):
    """Actual distinct logged-in processes; controlled names alone are inputs."""
    exact(principals,{'primary','actor'});need(len(set(principals.values()))==2)
    for binding in (primary_binding,actor_binding):context(binding)
    need(primary_binding['sessionId']!=actor_binding['sessionId']
        and primary_binding['targetFingerprint']!=actor_binding['targetFingerprint']
        and primary_binding['artifactSha256']==actor_binding['artifactSha256']
        and primary_binding['sourceRevision']==actor_binding['sourceRevision'])
    result={}
    for role,frame,binding in (('primary',primary,primary_binding),('actor',actor,actor_binding)):
        state,clock=state_original(frame,binding);originals=frame['originals'];username=principals[role]
        need(type(username) is str and username.startswith('e2e-') and http.identifier(username[4:]))
        need(state['runId']==run and frame['phaseBefore']['activations'][-1]['ticket']==ticket
            and frame['phaseAfter']['activations'][-1]['ticket']==ticket)
        native=originals['native'];account=native['account'];account_original(account,native['capturedEpochMs'])
        need(account['loggedIn'] and account['principalSha256']==hashlib.sha256(username.encode()).hexdigest()
            and account['observation']['endpointSha256']==hashlib.sha256(origin.encode()).hexdigest())
        for name,module in (('http',http),('scripts',avatar_scripts),('people',people_model)):
            packet=module.original(originals[name]);need(packet['processId']==int(binding['processIdentity']) and packet['runId']==run
                and clock['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs']
                <=packet['clockAfter']['epochMs']<=clock['nativeAfter']['capturedEpochMs'])
        model=people_model.current(originals['people']);need(model['myData'].get('userName')==username)
        result[role]=dict(frame=frame,state=state,model=model)
    need(result['primary']['state']['source']['sessionId']!=result['actor']['state']['source']['sessionId'])
    return result


def protocol(row,expected_code):
    value=row['frame']['originals']['scripts'];managers=[]
    for worker in value['source']['workers']:
        if any(code['url'].endswith('/system/libraries/peopleConnection.js') for code in worker['avatar']['code']):
            identity=worker['membership']['instance']
            for_worker(value,identity,expected_code,required={'/system/pal.js','/system/libraries/peopleConnection.js'})
            managers.append(identity)
    need(len(managers)==1);return managers[0]


def pending(primary,actor,primary_binding,actor_binding,status,*,principals,owned_origin,provider_instance,run,ticket,expected_code):
    """A real invitation reaches the other SDK's actual incoming prompt."""
    actual=roles(primary,actor,primary_binding,actor_binding,principals,owned_origin,run,ticket)
    http.provider_status(status,instance=provider_instance,run=run)
    need(status['active'] and status['ticket']==ticket and not status['connected'] and not status['pendingRoles'])
    p,a=(actual[role]['model'] for role in ('primary','actor'))
    managers={role:protocol(actual[role],expected_code) for role in ('primary','actor')}
    left,right=p['connectionState'],a['connectionState']
    need(left['phase']=='outgoing' and right['phase']=='incoming'
        and left.get('peer')==actual['actor']['state']['source']['sessionId']
        and right.get('peer')==actual['primary']['state']['source']['sessionId']
        and left.get('requestId')==right.get('requestId') and p['panels']['connectionPrompt'] and a['panels']['connectionPrompt'])
    from ios.adapters.avatar_state import session
    session(left['requestId'])
    return dict(iosAvatarSocialVersion=VERSION,connection='pending',pendingDialog=True,
        requestId=left['requestId'],primaryRoot=p['rootId'],actorRoot=a['rootId'],protocolManagers=managers,consumptions={})


def consumed(row,status,*,role,provider_instance,owned_origin,run,ticket,barrier,expected_code):
    exact(barrier,{'nativeEpochMs','providerEpochMs','httpEvent'})
    need(integer(barrier['nativeEpochMs'],1) and integer(barrier['providerEpochMs'],1) and integer(barrier['httpEvent'],0))
    originals=row['frame']['originals'];found=http.consumed_responses(originals['http'],status,
        provider_instance=provider_instance,owned_origin=owned_origin,run=run,ticket=ticket,role=role,
        after_native_epoch=barrier['nativeEpochMs'],after_provider_epoch=barrier['providerEpochMs'],after_event=barrier['httpEvent'])
    result=[]
    for receipt in found:
        sent=receipt['nativeSent']['details'];path=urlsplit(sent['url']).path
        if path not in (REQUEST,CONNECTIONS) and sent['method']!='DELETE':continue
        suffix='/system/libraries/peopleConnection.js' if path==REQUEST else '/system/request-service.js' if path==CONNECTIONS else '/system/pal.js'
        source=receipt['nativeCreated']['details'];need(any(caller.endswith(suffix) for caller in source['callerChain']))
        selected=for_worker(originals['scripts'],source['engine']['instance'],expected_code,required={'/modules/request.js',suffix})
        code=avatar_scripts.join_http_code(originals['scripts'],originals['http'],receipt,selected)
        response=decode(http.body(receipt['nativeReply']['details']['body']).decode('utf-8'))
        need(type(response) is dict and response.get('status')=='success')
        result.append(dict(original=receipt,code=code,response=response))
    return result


def directory(row,receipts,peer,*,present):
    """Exact original PSF page bytes must become the actual complete table."""
    originals=row['frame']['originals'];model=row['model'];matches=[];candidates=[]
    for item in receipts:
        sent=item['original']['nativeSent']['details'];url=urlsplit(sent['url'])
        if url.path!=CONNECTIONS or sent['method']!='GET':continue
        pairs=parse_qsl(url.query,keep_blank_values=True);query=dict(pairs)
        if len(query)!=len(pairs) or query.get('page','1')!='1' or query.get('sort')!='username,ASC':continue
        if set(query)-{'page','sort','per_page','search'} or query.get('search',''):continue
        candidates.append((item,query))
    for item,query in candidates[-1:]:
        response=item['response'];exact(response,{'status','data','current_page','total_pages','total_entries'})
        exact(response['data'],{'users'});users=response['data']['users'];need(type(users) is list and response['current_page']==response['total_pages']==1
            and type(response['total_entries']) is int and response['total_entries']==len(users))
        rows=[]
        for user in users:
            need(type(user) is dict and type(user.get('images')) is dict and type(user.get('location')) is dict)
            location=user['location'];place=location.get('root') or location.get('domain') or {}
            rows.append(dict(userName=user.get('username'),connection=user.get('connection'),
                profileUrl=user['images'].get('thumbnail'),placeName=place.get('name','')))
        need(model['connectionRows']==rows and model['pagination']['sortKey']=='username,ASC'
            and str(model['pagination']['itemsPerPage'])==query.get('per_page') and not model['pagination']['searchFilter']
            and not model['httpCallbacks'])
        people_model.relationship(originals['people'],peer,present=present,
            after_epoch=item['original']['nativeRead']['clock']['epochMs'])
        matches.append(item)
    need(matches);return matches[-1]


def connected(primary,actor,primary_binding,actor_binding,status,*,principals,owned_origin,provider_instance,run,ticket,barriers,expected_code):
    """Both real POSTs and parsed/materialized reciprocal tables are required."""
    actual=roles(primary,actor,primary_binding,actor_binding,principals,owned_origin,run,ticket)
    http.provider_status(status,instance=provider_instance,run=run);exact(barriers,{'primary','actor'})
    need(status['active'] and status['ticket']==ticket and status['connected'] and not status['pendingRoles'])
    result={}
    for role,other in (('primary','actor'),('actor','primary')):
        row=actual[role];receipts=consumed(row,status,role=role,provider_instance=provider_instance,
            owned_origin=owned_origin,run=run,ticket=ticket,barrier=barriers[role],expected_code=expected_code)
        posts=[];confirmed=[]
        for item in receipts:
            sent=item['original']['nativeSent']['details'];url=urlsplit(sent['url'])
            if url.path!=REQUEST:continue
            body=decode(http.body(sent['body'],4096).decode('utf-8')) if sent['method']=='POST' else dict(parse_qsl(url.query))
            if sent['method']=='POST':exact(body,{'user_connection_request'});body=body['user_connection_request']
            exact(body,{'node_id','proposed_node_id'})
            need(body==dict(node_id=row['state']['source']['sessionId'],proposed_node_id=actual[other]['state']['source']['sessionId']))
            response=item['response'];connection=response.get('connection')
            need(connection=='pending' or type(connection) is dict and connection.get('username')==principals[other])
            if sent['method']=='POST':posts.append(item)
            if type(connection) is dict:confirmed.append(item)
        need(posts and confirmed)
        table=directory(row,receipts,principals[other],present=True)
        need(row['model']['connectionState']['phase']=='idle' and not row['model']['panels']['connectionPrompt'])
        need(avatar_scripts.drained(row['frame']['originals']['scripts'],{protocol(row,expected_code)}))
        result[role]=dict(post=posts[-1],confirmation=confirmed[-1],directory=table)
    return dict(iosAvatarSocialVersion=VERSION,connection='connected',pendingDialog=False,consumptions=deepcopy(result))


def absent(primary,actor,primary_binding,actor_binding,status,*,principals,owned_origin,provider_instance,run,ticket,barriers,expected_code,require_delete):
    """Actual fresh empty tables on both SDKs, with original deletion if used."""
    actual=roles(primary,actor,primary_binding,actor_binding,principals,owned_origin,run,ticket)
    http.provider_status(status,instance=provider_instance,run=run);exact(barriers,{'primary','actor'})
    need(type(require_delete) is bool and status['active'] and status['ticket']==ticket
        and not status['connected'] and not status['pendingRoles'])
    result={}
    for role,other in (('primary','actor'),('actor','primary')):
        row=actual[role];receipts=consumed(row,status,role=role,provider_instance=provider_instance,
            owned_origin=owned_origin,run=run,ticket=ticket,barrier=barriers[role],expected_code=expected_code)
        table=directory(row,receipts,principals[other],present=False)
        need(row['model']['connectionState']['phase']=='idle' and not any(row['model']['panels'].values())
            and avatar_scripts.drained(row['frame']['originals']['scripts'],{protocol(row,expected_code)}))
        result[role]=dict(directory=table)
        if role=='primary' and require_delete:
            deletions=[item for item in receipts if item['original']['nativeSent']['details']['method']=='DELETE'
                and urlsplit(item['original']['nativeSent']['details']['url']).path=='/api/v1/user/connections/'+principals[other]
                and http.body(item['original']['nativeSent']['details']['body'],4096)==b''
                and item['response']=={'status':'success'}]
            need(deletions and table['original']['nativeRead']['clock']['epochMs']>=deletions[-1]['original']['nativeRead']['clock']['epochMs'])
            result[role]['deletion']=deletions[-1]
    return dict(iosAvatarSocialVersion=VERSION,connection='none',pendingDialog=False,consumptions=deepcopy(result))
