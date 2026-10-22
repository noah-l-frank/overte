"""Original Avatar/People sources and token-bound ordinary Qt input.

Closed transport only. These readers do not project requested actions into state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid
from urllib.parse import urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_script_roots import NativeScriptRoots
from adapters.native_account_observation import validate as account_observation
from overte_phone_script_files import PhoneScriptFileIO,nonce
from overte_phone_script_history import same

FILE='phone-avatar-people-observation.json'
UI_FILE='phone-avatar-people-ui.json'
ACTION='phone-avatar-people-observe'
CONTROL=re.compile(r'(?:avatar\.(?:entry|page|url|wearables|settings|scale|settings\.scrollbar|wearable\.add|bookmark\.(?:add|manage|previous|next|row\.(?:0|[1-9][0-9]{0,2}))|dialog\.(?:input|confirm|cancel))|people\.(?:entry|page|nearby|connections|ConnectionAccept|ConnectionDecline|ConnectionCancel|RequestConnection|row\.(?:0|[1-9][0-9]{0,2})|remove\.[A-Za-z0-9_-]{1,128}))')
UUID=re.compile('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
HASH=re.compile('[0-9a-f]{64}')


def digest(text):return hashlib.sha256(text.encode()).hexdigest()

def text(value,limit=4096):return type(value) is str and len(value)<=limit and all(ord(c)>=32 and ord(c)!=127 for c in value)

def session(value):need(type(value) is str and UUID.fullmatch(value) and value!='00000000-0000-0000-0000-000000000000');return value

def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION and nonce(value['commandId']) and nonce(value['runId']))
    return value


def history(value,epoch,*,previous=None):
    exact(value,{'modelLoadsVersion','instance','sequence','capturedEpochMs','complete','currentGeneration','requestedSha256','events'})
    need(type(value['modelLoadsVersion']) is int and value['modelLoadsVersion']==1 and nonce(value['instance']) and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1,epoch) and value['complete'] is True and integer(value['currentGeneration'],0,1000000000)
        and type(value['requestedSha256']) is str and (HASH.fullmatch(value['requestedSha256']) or value['currentGeneration']==0 and value['requestedSha256']=='')
        and type(value['events']) is list and len(value['events'])<=256)
    generation=0;requested='';captured=0
    for index,row in enumerate(value['events'],1):
        exact(row,{'eventSequence','generation','kind','capturedEpochMs','requestedSha256','resourceSha256','success'})
        need(type(row['eventSequence']) is int and row['eventSequence']==index and row['kind'] in ('requested','finished')
            and integer(row['capturedEpochMs'],max(1,captured),value['capturedEpochMs']) and HASH.fullmatch(row['requestedSha256']))
        if row['kind']=='requested':
            need(type(row['generation']) is int and row['generation']==generation+1 and row['success'] is None and row['resourceSha256']=='')
            generation=row['generation'];requested=row['requestedSha256']
        else:need(row['generation']==generation and generation>0 and type(row['success']) is bool and HASH.fullmatch(row['resourceSha256']))
        need(row['requestedSha256']==requested);captured=row['capturedEpochMs']
    need(generation==value['currentGeneration'] and requested==value['requestedSha256'])
    if previous is not None:
        history(previous,epoch)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['capturedEpochMs']>=previous['capturedEpochMs'] and same(value['events'][:len(previous['events'])],previous['events']))
    return value


def model(value,epoch,*,previous=None):
    exact(value,{'sessionId','replicated','requestedUrl','advertisedLoads','modelInstance','modelLoads','rigId','loaded','visible','addedToScene','targetScale','scale','hipsJoint','feetPosition','orientation','shouldRender','geometry'})
    session(value['sessionId']);need(type(value['replicated']) is bool and text(value['requestedUrl']) and nonce(value['modelInstance'])
        and integer(value['rigId']) and all(type(value[k]) is bool for k in ('loaded','visible','addedToScene'))
        and number(value['scale'],.01,1000) and number(value['targetScale'],.01,1000) and type(value['hipsJoint']) is int and -1<=value['hipsJoint']<=65535)
    for key,count in (('feetPosition',3),('orientation',4)):
        need(type(value[key]) is list and len(value[key])==count and all(number(v,-1e6,1e6) for v in value[key]))
    need(type(value['shouldRender']) is bool and abs(sum(v*v for v in value['orientation'])-1)<.001)
    history(value['advertisedLoads'],epoch,previous=previous['advertisedLoads'] if previous else None)
    history(value['modelLoads'],epoch,previous=previous['modelLoads'] if previous and previous['modelInstance']==value['modelInstance'] else None)
    if value['advertisedLoads']['currentGeneration']>0:need(value['advertisedLoads']['requestedSha256']==digest(value['requestedUrl']))
    geometry=value['geometry']
    if geometry is not None:
        exact(geometry,{'instance','url','texturesLoaded','textures'})
        need(nonce(geometry['instance']) and text(geometry['url']) and type(geometry['texturesLoaded']) is bool
            and type(geometry['textures']) is dict and len(geometry['textures'])<=256 and all(text(k,1024) and text(v) for k,v in geometry['textures'].items()))
    need(not value['loaded'] or geometry is not None)
    if previous is not None:need(value['sessionId']==previous['sessionId'] and value['replicated']==previous['replicated'])
    return value


def replies(value,epoch,*,resource,run=None,previous=None):
    version='resourceRepliesVersion' if resource else 'peopleRepliesVersion'
    exact(value,{version,'instance','sequence','capturedEpochMs','complete','events'}|({'runId'} if resource else set()))
    need(type(value[version]) is int and value[version]==1 and nonce(value['instance']) and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1,epoch) and value['complete'] is True and type(value['events']) is list and len(value['events'])<=(1024 if resource else 512))
    if resource:need(value['runId']==run and nonce(run))
    sequence=0;ids=set();captured=0
    for row in value['events']:
        exact(row,{'sequence','runId','ticket','resource','requestedUrlSha256','replyUrlSha256','responseId','httpStatus','networkError','fromCache','redirected','capturedEpochMs','bytes','sha256'} if resource else
            {'eventSequence','responseId','method','requestedUrlSha256','replyUrlSha256','requestBodySha256','httpStatus','networkError','fromCache','redirected','capturedEpochMs','bytes','sha256'})
        key='sequence' if resource else 'eventSequence'
        need(integer(row[key],sequence+1) and nonce(row['responseId']) and row['responseId'] not in ids and integer(row['httpStatus'],100,599)
            and integer(row['networkError'],0,1000) and all(type(row[k]) is bool for k in ('fromCache','redirected'))
            and all(type(row[k]) is str and HASH.fullmatch(row[k]) for k in ('requestedUrlSha256','replyUrlSha256','sha256'))
            and integer(row['capturedEpochMs'],max(1,captured),value['capturedEpochMs']) and integer(row['bytes'],0,16*1024*1024 if resource else 65536))
        if resource:need(row['runId']==run and nonce(row['ticket']) and text(row['resource'],512))
        else:need(row['method'] in ('GET','POST','DELETE') and type(row['requestBodySha256']) is str and HASH.fullmatch(row['requestBodySha256']))
        sequence=row[key];captured=row['capturedEpochMs'];ids.add(row['responseId'])
    if previous is not None:
        replies(previous,epoch,resource=resource,run=run)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs']
            and same(value['events'][:len(previous['events'])],previous['events']))
    return value


def controls(value,request,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence','lastCommandSequence','elapsedMs','capturedEpochMs','processId','avatarPeopleControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==request and value['action']=='observe'
        and nonce(value['instance']) and nonce(value['generation']) and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence'])
        and integer(value['elapsedMs']) and type(value['processId']) is int and value['processId']==pid and type(value['avatarPeopleControlsVersion']) is int
        and value['avatarPeopleControlsVersion']==1 and value['ready'] is True and type(value['controls']) is list and len(value['controls'])<=384)
    fresh(value['capturedEpochMs'],epoch);ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict and type(row.get('id')) is str and CONTROL.fullmatch(row['id']) and nonce(row.get('token'))
            and row['id'] not in ids and row['token'] not in tokens and {'id','token','enabled','focused','inputReady'}<=set(row)
            and set(row)<={'id','token','enabled','focused','inputReady','text','dialogTitle','dialogSource','managing','value','from','to','stepSize','bookmarkName','peerSession','userName','consent','tab'}
            and all(type(row[k]) is bool for k in ('enabled','focused','inputReady')))
        for k in ('text','dialogTitle','dialogSource','bookmarkName','peerSession','userName','tab'):
            if k in row:need(text(row[k]))
        for k in ('value','from','to','stepSize'):
            if k in row:need(number(row[k],0,1000))
        if 'managing' in row:need(type(row['managing']) is bool)
        if 'consent' in row:need(type(row['consent']) is dict)
        ids.add(row['id']);tokens.add(row['token'])
    return value


class PhoneAvatarPeopleIO(PhoneScriptFileIO):
    wire_action='phone-avatar-people-ui'
    validate_capture=staticmethod(controls)
    def input(self,identifier,action,*,token,text_value=None,value=None,direction=None):
        need(type(identifier) is str and CONTROL.fullmatch(identifier) and not identifier.endswith('.page') and nonce(token)
            and action in ('activate','replace','set-value','scroll'))
        if action=='replace':
            need(identifier=='avatar.dialog.input' and type(text_value) is str and len(text_value)<=4096)
            parsed=urlsplit(text_value)
            need(re.fullmatch('(?:e2e-|hidden-)[0-9a-f]{32}',text_value) or parsed.scheme in ('https','qrc') and not parsed.username and not parsed.password and not parsed.fragment and text(text_value) and not re.search(r'[\x00-\x20\x7f]',text_value) and (bool(parsed.netloc) if parsed.scheme=='https' else not parsed.netloc and parsed.path.startswith('/')))
        else:need(text_value is None)
        if action=='set-value':need(identifier=='avatar.scale' and number(value,1,40))
        else:need(value is None)
        if action=='scroll':need(identifier=='avatar.settings.scrollbar' and direction in ('up','down'))
        else:need(direction is None)
        original=self.capture();rows=[r for r in original['controls'] if r['id']==identifier]
        need(len(rows)==1 and rows[0]['token']==token and rows[0]['enabled'] and rows[0]['inputReady'] and (action!='replace' or rows[0]['focused']))
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=original['instance'],generation=original['generation'],
            sequence=original['lastCommandSequence']+1,observedElapsedMs=original['elapsedMs'],controlId=identifier,controlToken=token)
        if action=='replace':request['text']=text_value
        if action=='set-value':request['value']=value
        if action=='scroll':request['direction']=direction
        self.deliver(request,original)


def entities(source,epoch,run,previous=None):
    origins=source['avatarEntityOrigins'];exact(origins,{'avatarEntityOriginsVersion','instance','sequence','capturedEpochMs','runId','complete','events'})
    need(type(origins['avatarEntityOriginsVersion']) is int and origins['avatarEntityOriginsVersion']==1 and nonce(origins['instance'])
        and integer(origins['sequence'],1) and integer(origins['capturedEpochMs'],1,epoch) and origins['runId']==run and origins['complete'] is True
        and type(origins['events']) is list and len(origins['events'])<=256)
    sequence=0;captured=0;seen=set()
    for row in origins['events']:
        exact(row,{'eventSequence','capturedEpochMs','runId','ticket','entityId','parentId','parentJointIndex','treePresent','modelUrlSha256'})
        need(integer(row['eventSequence'],sequence+1) and integer(row['capturedEpochMs'],max(1,captured),origins['capturedEpochMs'])
            and row['runId']==run and nonce(row['ticket']) and integer(row['parentJointIndex'],0,65535) and type(row['treePresent']) is bool
            and type(row['modelUrlSha256']) is str and HASH.fullmatch(row['modelUrlSha256']))
        session(row['entityId']);session(row['parentId']);need(row['entityId'] not in seen);seen.add(row['entityId']);sequence=row['eventSequence'];captured=row['capturedEpochMs']
    if previous is not None:
        old=previous['avatarEntityOrigins'];need(origins['instance']==old['instance'] and origins['sequence']>old['sequence']
            and origins['capturedEpochMs']>=old['capturedEpochMs'] and same(origins['events'][:len(old['events'])],old['events']))
    actual=source['avatarEntities'];exact(actual,{'complete','entities','absentIds','advertisedIds','queriedIds','rememberedIds','retainedIds'})
    need(actual['complete'] is True and type(actual['entities']) is list and len(actual['entities'])<=512 and type(actual['absentIds']) is list and len(actual['absentIds'])<=512)
    ids=set()
    for row in actual['entities']:
        exact(row,{'entityId','type','host','parentId','parentJointIndex','modelUrl','visible','originalObject','localPosition','localRotation','localDimensions','model'})
        session(row['entityId']);session(row['parentId']);need(row['entityId'] not in ids and text(row['type'],128) and row['host'] in ('avatar','local','domain')
            and integer(row['parentJointIndex'],0,65535) and text(row['modelUrl']) and type(row['visible']) is bool and type(row['originalObject']) is bool)
        ids.add(row['entityId'])
        for key,count in (('localPosition',3),('localRotation',4),('localDimensions',3)):
            need(type(row[key]) is list and len(row[key])==count and all(number(v,-1e6,1e6) for v in row[key]))
        if row['model'] is not None:
            m=row['model'];exact(m,{'modelInstance','modelLoads','loaded','visible','addedToScene','geometry'})
            need(nonce(m['modelInstance']) and all(type(m[k]) is bool for k in ('loaded','visible','addedToScene')))
            old=next((r for r in previous['avatarEntities']['entities'] if r['entityId']==row['entityId']),None) if previous else None
            old_model=old.get('model') if old else None
            history(m['modelLoads'],epoch,previous=old_model['modelLoads'] if old_model and old_model['modelInstance']==m['modelInstance'] else None)
            if m['geometry'] is not None:
                g=m['geometry'];exact(g,{'instance','url','texturesLoaded','textures'});need(nonce(g['instance']) and text(g['url'])
                    and type(g['texturesLoaded']) is bool and type(g['textures']) is dict and len(g['textures'])<=256 and all(text(k,1024) and text(v) for k,v in g['textures'].items()))
            need(not m['loaded'] or m['geometry'] is not None)
    for id in actual['absentIds']:session(id);need(id not in ids);ids.add(id)
    for key in ('advertisedIds','queriedIds','rememberedIds','retainedIds'):
        rows=actual[key];need(type(rows) is list and len(rows)<=512 and len(set(rows))==len(rows))
        for id in rows:session(id)
    need(set(actual['queriedIds'])==ids and set(actual['advertisedIds'])<=ids and set(actual['retainedIds'])<=ids
        and {row['entityId'] for row in origins['events']}<=set(actual['rememberedIds'])<=ids
        and {row['entityId'] for row in actual['entities']}<=set(actual['rememberedIds']) and set(actual['retainedIds'])<=set(actual['rememberedIds'])
        and all(not row['originalObject'] or row['entityId'] in actual['retainedIds'] for row in actual['entities']))
    if previous is not None:need(set(previous['avatarEntities']['rememberedIds'])<=set(actual['rememberedIds']))


def validate(value,request,pid,epoch,*,previous=None):
    command(request)
    exact(value,{'avatarPeopleObservationVersion','commandId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['avatarPeopleObservationVersion']) is int and value['avatarPeopleObservationVersion']==1 and value['commandId']==request['commandId']
        and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1,1000000000)
        and type(value['processId']) is int and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs'],value['requestedEpochMs']+1500))
    fresh(value['capturedEpochMs'],epoch);source=value['source'];before=previous['source'] if previous else None
    exact(source,{'view','bookmarks','auth','accountOrigin','avatar','peers','canRezAvatarEntities','attachments','preferredAvatarUrl','preferredAvatarName','domainId','connected','resourceReplies','peopleReplies','avatarEntityOrigins','avatarEntities'})
    need(type(source['connected']) is bool and type(source['canRezAvatarEntities']) is bool and text(source['preferredAvatarUrl'])
        and text(source['preferredAvatarName'],256) and text(source['accountOrigin'],1024)
        and type(source['attachments']) is list and len(source['attachments'])<=128 and all(type(row) is dict for row in source['attachments']))
    session(source['domainId']);account_observation(source['auth'],value['capturedEpochMs'],value['requestedEpochMs'])
    model(source['avatar'],value['capturedEpochMs'],previous=before['avatar'] if before else None)
    need(type(source['peers']) is list and len(source['peers'])<=128);seen={source['avatar']['sessionId']};models={source['avatar']['modelInstance']}
    for peer in source['peers']:
        old=next((row for row in before['peers'] if row['sessionId']==peer.get('sessionId')),None) if before else None
        model(peer,value['capturedEpochMs'],previous=old);need(peer['sessionId'] not in seen and peer['modelInstance'] not in models);seen.add(peer['sessionId']);models.add(peer['modelInstance'])
    storage=source['bookmarks'];exact(storage,{'present','sha256','bytes','bookmarks'})
    need(type(storage['present']) is bool and type(storage['sha256']) is str and HASH.fullmatch(storage['sha256']) and integer(storage['bytes'],0,262144)
        and type(storage['bookmarks']) is dict and len(storage['bookmarks'])<=1000 and all(text(k,256) and type(v) is dict for k,v in storage['bookmarks'].items())
        and (storage['present'] or storage['bytes']==0 and storage['bookmarks']=={}))
    view=source['view'];exact(view,{'avatarPeopleViewVersion','tabletShown','avatar','people','models','preferences'})
    need(type(view['avatarPeopleViewVersion']) is int and view['avatarPeopleViewVersion']==1 and type(view['tabletShown']) is bool)
    avatar=view['avatar'];need(type(avatar) is dict and type(avatar.get('present')) is bool)
    exact(avatar,{'present','dialogs'}|({'current','settings','managing'} if avatar['present'] else set()))
    need(type(avatar['dialogs']) is list and len(avatar['dialogs'])<=4)
    for dialog in avatar['dialogs']:
        exact(dialog,{'title','source'});need((dialog['title'] is None or text(dialog['title'],512)) and text(dialog['source'],256))
    if avatar['present']:
        need(view['tabletShown'] and type(avatar['managing']) is bool and type(avatar['settings']) is dict and type(avatar['current']) is dict)
        if avatar['current']:
            exact(avatar['current'],{'name','avatarUrl','avatarScale'});need(text(avatar['current']['name'],256) and text(avatar['current']['avatarUrl']) and number(avatar['current']['avatarScale'],.01,1000))
    people=view['people'];need(type(people) is dict and type(people.get('present')) is bool)
    exact(people,{'present','dialog'}|({'consent','nearby','self','tab'} if people['present'] else set()))
    need(type(people['dialog']) is bool and (people['present'] or not people['dialog']))
    if people['present']:
        need(view['tabletShown'] and type(people['consent']) is dict and people['consent'].get('phase') in
            ('idle','outgoing','incoming','accepted','submitting','polling','success','declined','cancelled','error')
            and type(people['nearby']) is list and len(people['nearby'])<=1000 and type(people['self']) is dict and people['tab'] in ('nearbyTab','connectionsTab')
            and people['dialog']==(people['consent']['phase']!='idle'))
    expected=({'allAvatars','pageOfAvatars'} if avatar['present'] else set())|({'connectionsUserModel','nearbyUserModel'} if people['present'] else set())
    exact(view['models'],expected)
    for actual in view['models'].values():
        exact(actual,{'complete','count','rows'});need(actual['complete'] is True and integer(actual['count'],0,1000) and type(actual['rows']) is list
            and len(actual['rows'])==actual['count'] and all(type(row) is dict for row in actual['rows']))
    exact(view['preferences'],{'filtered','nearDistance','nearbySortIndicatorColumn','nearbySortIndicatorOrder','connectionsSortIndicatorColumn','connectionsSortIndicatorOrder'})
    for pref in view['preferences'].values():exact(pref,{'present','value'});need(type(pref['present']) is bool and (pref['present'] or pref['value'] is None))
    replies(source['resourceReplies'],value['capturedEpochMs'],resource=True,run=request['runId'],previous=before['resourceReplies'] if before else None)
    entities(source,value['capturedEpochMs'],request['runId'],before)
    replies(source['peopleReplies'],value['capturedEpochMs'],resource=False,previous=before['peopleReplies'] if before else None)
    if previous is not None:
        validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action=ACTION,runId=previous['runId']),pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['runId']==previous['runId'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['requestedEpochMs']>=previous['capturedEpochMs'])
    return value


class PhoneAvatarPeopleObservation(NativeScriptRoots):
    def restore(self,packets):
        need(self.last is None and type(packets) is list and 0<len(packets)<=256 and self.guard() is not False)
        seen=set();run=None
        for value in packets:
            original=dict(schemaVersion=1,commandId=value.get('commandId'),action=ACTION,runId=value.get('runId'))
            validate(value,original,self.pid,value.get('capturedEpochMs'),previous=self.last)
            need(value['commandId'] not in seen and run in (None,value['runId']))
            seen.add(value['commandId']);run=value['runId'];self.last=deepcopy(value)

    def read(self,run):
        need(self.ios is False)
        barrier=self.clock_ms();need(integer(barrier,1) and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,runId=run);command(request)
        start=previous=self.monotonic();need(number(start,0,1e15));self.send(deepcopy(request))
        for attempt in range(51):
            need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=2*1024*1024)
            try:value=decode(raw) if raw else None
            except ValueError:value=None
            now=self.monotonic();need(number(now,previous,1e15) and now-start<5 and self.guard() is not False);previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();validate(value,request,self.pid,epoch,previous=self.last)
                need(value['requestedEpochMs']>=barrier and max(epoch-value['capturedEpochMs'],barrier-value['capturedEpochMs']+(now-start)*1000)<=1500
                    and self.guard() is not False)
                self.last=deepcopy(value);return deepcopy(value)
            if attempt<50:self.sleep(.1)
        need(False)
