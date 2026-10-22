"""Passive original Avatar Handle/cache/writer and physical JSON baselines."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import decode,exact,integer,number,need
from adapters.native_graphics_subject import entity_id
from adapters.pico4.avatar_bookmarks import bytes_of
from adapters.pico4.avatar_state import digest

ACTION='feature-pico-avatar-preferences-observe'
FILE='feature-pico-avatar-preferences.json'
FIELDS=('dominantHand','strafeEnabled','hmdAvatarAlignmentType','headPitch','scale','yawSpeed','hmdYawSpeed','cameraSensitivity','pitchSpeed',
    'fullAvatarURL','fullAvatarModelName','animGraphURL','displayName','collisionSoundURL','useSnapTurn','hoverWhenUnsupported','userHeight',
    'flyingHMD','movementReference','avatarEntityCount','vrWalkSpeed','allowAvatarStandingPreference','allowAvatarLeaningPreference')
FLOAT_FIELDS={'headPitch','scale','yawSpeed','hmdYawSpeed','cameraSensitivity','pitchSpeed','userHeight','vrWalkSpeed'}
BOOL_FIELDS={'strafeEnabled','useSnapTurn','hoverWhenUnsupported','flyingHMD'}
URL_FIELDS={'fullAvatarURL','fullAvatarModelName','animGraphURL','collisionSoundURL'}


def handle_type(field):
    if field.startswith('avatarEntityID/'):return 30,'QUuid'
    if field.startswith('avatarEntityData/'):return 12,'QByteArray'
    if field in FLOAT_FIELDS:return 38,'float'
    if field in BOOL_FIELDS:return 1,'bool'
    if field in URL_FIELDS:return 17,'QUrl'
    if field in ('movementReference','avatarEntityCount'):return 2,'int'
    return 10,'QString'



def normalized(key):return '/'.join(piece for piece in key.split('/') if piece)
def scoped(key):
    return type(key) is str and 0<len(key)<=4096 and (normalized(key) in ('Avatar','fullPrivate/Avatar')
        or normalized(key).startswith(('Avatar/','fullPrivate/Avatar/')))


def raw(value):
    exact(value,{'present','typeId','typeName','base64','sha256'})
    need(value['present'] is True and integer(value['typeId'],0,65535) and (value['typeName'] is None or
        type(value['typeName']) is str and 0<len(value['typeName'])<=256) and digest(value['sha256']))
    data=bytes_of(value['base64'],65536);need(hashlib.sha256(data).hexdigest()==value['sha256'])
    need((value['typeId']==0)==(value['typeName'] is None));return value


def rows(value):
    need(type(value) is dict and len(value)<=512)
    for key,item in value.items():need(scoped(key));raw(item)


def tokens(value):
    exact(value,{'count','values'});need(integer(value['count'],0,512) and type(value['values']) is dict and len(value['values'])==value['count'])
    for key,item in value['values'].items():
        need(scoped(key));exact(item,{'base64','sha256'});need(digest(item['sha256']))
        data=bytes_of(item['base64'],65536);need(hashlib.sha256(data).hexdigest()==item['sha256'])
        decode(data.decode('utf-8'))


def handles(value):
    exact(value,{'nativeAvatarPreferenceHandlesVersion','handles','avatarEntityIDCount','avatarEntityDataCount'})
    need(type(value['nativeAvatarPreferenceHandlesVersion']) is int and value['nativeAvatarPreferenceHandlesVersion']==1
        and integer(value['avatarEntityIDCount'],0,128) and integer(value['avatarEntityDataCount'],0,128))
    expected=set(FIELDS)|{'avatarEntityID/'+str(i) for i in range(value['avatarEntityIDCount'])}|{'avatarEntityData/'+str(i) for i in range(value['avatarEntityDataCount'])}
    exact(value['handles'],expected)
    for field,item in value['handles'].items():
        exact(item,{'nativePreferenceHandleVersion','key','isSet','initialized','managerBound','value','default','deprecated'})
        need(type(item['nativePreferenceHandleVersion']) is int and item['nativePreferenceHandleVersion']==1 and scoped(item['key'])
            and all(type(item[k]) is bool for k in ('isSet','initialized','managerBound','deprecated'))
            and (not item['initialized'] or item['managerBound']) and (not item['isSet'] or item['initialized']))
        expected_key=('Avatar/' if field=='headPitch' else 'fullPrivate/Avatar/fullAvatarURL' if field=='fullAvatarURL' else
            'Avatar/avatarEntityData/size' if field=='avatarEntityCount' else
            'Avatar/avatarEntityData/'+str(int(field.split('/')[1])+1)+('/id' if field.startswith('avatarEntityID/') else '/properties') if '/' in field else 'Avatar/'+field)
        need(item['key']==expected_key)
        raw(item['value']);raw(item['default']);need((item['value']['typeId'],item['value']['typeName'])==handle_type(field)
            and (item['default']['typeId'],item['default']['typeName'])==handle_type(field))



def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action'});need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and nonce(request['commandId']) and request['action']==ACTION)
    envelope(value,request,pid,epoch);source=value['source'];exact(source,{'picoAvatarPreferencesVersion','instance','snapshot'})
    need(type(source['picoAvatarPreferencesVersion']) is int and source['picoAvatarPreferencesVersion']==1 and nonce(source['instance']))
    snapshot=source['snapshot'];exact(snapshot,{'avatarPreferenceBarrierVersion','instance','mutationSequence','capturedEpochMs','elapsedMs','cache','writer','cacheMatchesWriter'})
    need(type(snapshot['avatarPreferenceBarrierVersion']) is int and snapshot['avatarPreferenceBarrierVersion']==1 and nonce(snapshot['instance'])
        and integer(snapshot['mutationSequence'],0,9007199254740991) and integer(snapshot['elapsedMs'],0,1500)
        and integer(snapshot['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']) and type(snapshot['cacheMatchesWriter']) is bool)
    cache=snapshot['cache'];exact(cache,{'rows','encodedRows','native'});rows(cache['rows']);tokens(cache['encodedRows']);native=cache['native'];exact(native,{'handles','modelInstance','sessionId','live'});handles(native['handles'])
    need(nonce(native['modelInstance']) and entity_id(native['sessionId']) and native['sessionId']!='00000000-0000-0000-0000-000000000000')
    live=native['live'];exact(live,{'preferenceUrl','modelName','scale','targetScale','dominantHand','hmdAvatarAlignmentType','collisionsEnabled','otherAvatarsCollisionsEnabled','collisionSoundUrl','animGraphOverrideUrl'})
    need(all(type(live[k]) is str and len(live[k])<=4096 for k in ('preferenceUrl','modelName','dominantHand','hmdAvatarAlignmentType','collisionSoundUrl','animGraphOverrideUrl'))
        and all(type(live[k]) is bool for k in ('collisionsEnabled','otherAvatarsCollisionsEnabled'))
        and number(live['scale'],.0001,1000) and number(live['targetScale'],.0001,1000))
    writer=snapshot['writer'];exact(writer,{'instance','capturedEpochMs','rows','encodedRows','physical','matchesPhysical'})
    need(nonce(writer['instance']) and integer(writer['capturedEpochMs'],value['requestedEpochMs'],snapshot['capturedEpochMs']) and type(writer['matchesPhysical']) is bool)
    rows(writer['rows']);tokens(writer['encodedRows']);physical=writer['physical'];exact(physical,{'avatarPreferenceFileVersion','capturedEpochMs','format','pathSha256','file','fileSha256','rows'})
    need(type(physical['avatarPreferenceFileVersion']) is int and physical['avatarPreferenceFileVersion']==1 and physical['format']=='json'
        and integer(physical['capturedEpochMs'],value['requestedEpochMs'],writer['capturedEpochMs']) and digest(physical['pathSha256']) and digest(physical['fileSha256']))
    tokens(physical['rows']);file=physical['file'];need(type(file) is dict and type(file.get('exists')) is bool)
    if not file['exists']:
        exact(file,{'exists'});need(physical['rows']['count']==0 and physical['fileSha256']==hashlib.sha256(b'').hexdigest())
    else:
        exact(file,{'exists','device','inode','bytes','mode','modified','changed'})
        need(integer(file['bytes'],0,1048576) and type(file['mode']) is int and file['mode']==0o600
            and all(type(file[k]) is str and 0<len(file[k])<=100 for k in ('device','inode','modified','changed')))
    need(writer['matchesPhysical']==(writer['encodedRows']==physical['rows']) and snapshot['cacheMatchesWriter']==(cache['encodedRows']==writer['encodedRows']))
    return value


def baseline(value):
    """No absent/default placeholder may authorize the first normal input."""
    validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),value.get('processId'),value.get('capturedEpochMs'))
    snapshot=value['source']['snapshot'];need(snapshot['cacheMatchesWriter'] and snapshot['writer']['matchesPhysical']);return deepcopy(snapshot)


def continuity(before,after):
    if before is None:return
    need(before['instance']==after['instance'] and after['sequence']>before['sequence'] and before['requestId']!=after['requestId'] and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(a['instance']==b['instance']);a,b=a['snapshot'],b['snapshot']
    need(a['instance']==b['instance'] and b['mutationSequence']>=a['mutationSequence'] and b['capturedEpochMs']>=a['capturedEpochMs']
        and a['writer']['instance']==b['writer']['instance'] and a['writer']['physical']['pathSha256']==b['writer']['physical']['pathSha256']
        and a['cache']['native']['modelInstance']==b['cache']['native']['modelInstance'] and a['cache']['native']['sessionId']==b['cache']['native']['sessionId'])


class NativePicoAvatarPreferences(_OriginalQuery):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.ios is False);self.previous=None;self.last_raw=self.last_sha256=None
        original=self.original
        def capture():
            raw=original();self._last_seen_raw=raw;return raw
        self.original=capture
    def read(self):
        value=self._read(self._request(ACTION),validate);continuity(self.previous,value)
        need(decode(self._last_seen_raw)==value);self.last_raw=self._last_seen_raw;self.last_sha256=hashlib.sha256(self.last_raw.encode()).hexdigest()
        self.previous=deepcopy(value);return value
    def restore(self,frames):
        need(self.last is None and type(frames) is list and 0<len(frames)<=512)
        for value in frames:
            validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),self.pid,value['capturedEpochMs'])
            self._advance(value);continuity(self.previous,value);self.previous=self.last=deepcopy(value)
