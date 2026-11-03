"""Private passive Keyboard1, bound to a genuinely fresh CurrentInput1 focus.

Key labels, layers and geometry are observations, never desired input. Historical
receipts may inspect these originals; only this warm owner may publish from one.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.chat_journey.source_chunks import json_digest
from adapters.pico4 import world_current_document as document
from adapters.pico4.world_current_input import PicoWorldCurrentInput,validate as validate_focus,same

VERSION=1
FILE='feature-world-current-keyboard.json'
LIMIT=65536
HEAD={'picoWorldCurrentKeyboardVersion','commandId','runId','ownerToken','focusNonce','instance','sequence','processId',
      'requestedEpochMs','requestedMonotonicMs','capturedEpochMs','capturedMonotonicMs','status','source'}
ENTITY=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def entity(value):return type(value) is str and re.fullmatch(ENTITY,value) is not None
def nonce(value):return type(value) is str and re.fullmatch(document.HEX,value) is not None


def command(value):
    document.strict(value);exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken','focusNonce'})
    need(value['operation']=='observe-current-keyboard' and nonce(value['focusNonce']) and value['focusNonce']!=value['commandId'])
    base={k:v for k,v in value.items() if k!='focusNonce'};base['operation']='observe-current-document';document.command(base)
    return value


def units(value):
    need(type(value) is str and len(value)<=1024 and re.fullmatch(r'(?:[0-9a-f]{4})*',value) is not None)
    return bytes.fromhex(value).decode('utf-16-be',errors='strict')


def vector(value,count):
    need(type(value) is list and len(value)==count and all(number(v,-1e9,1e9) for v in value))


def keyboard(value,packet,target):
    exact(value,{'keyboardVersion','instance','sequence','capturedEpochMs','created','enabled','raised','inputToHud','inputTarget',
        'focusedEntity','anchor','activeLayer','caps','preferMallets','ready','traceKeyboardObject','acceptedSequence','lastAccepted',
        'sensorToWorld','headPosition','layerMembership','keys','hmd'})
    need(type(value['keyboardVersion']) is int and value['keyboardVersion']==1 and nonce(value['instance'])
         and integer(value['sequence'],1) and integer(value['capturedEpochMs'],1)
         and all(type(value[k]) is bool for k in ('created','enabled','raised','inputToHud','caps','preferMallets','ready'))
         and all(value[k] is None or entity(value[k]) for k in ('inputTarget','focusedEntity')) and entity(value['anchor'])
         and integer(value['activeLayer'],0,31) and integer(value['acceptedSequence'],0,9007199254740991)
         and (value['traceKeyboardObject'] is None or nonce(value['traceKeyboardObject'])))
    fresh(value['capturedEpochMs'],packet['capturedEpochMs'])
    need(packet['requestedEpochMs']-250<=value['capturedEpochMs']<=packet['capturedEpochMs']+250)
    vector(value['sensorToWorld'],16);vector(value['headPosition'],3)
    hmd=value['hmd'];exact(hmd,{'display','active','visible','mounted'})
    need(type(hmd['display']) is str and 0<len(hmd['display'])<=256 and all(type(hmd[k]) is bool for k in ('active','visible','mounted')))
    accepted=value['lastAccepted'];need((accepted is None)==(value['acceptedSequence']==0))
    if accepted is not None:
        exact(accepted,{'sequence','keyEntity','keyType','keyEntityInstance','layerBefore','capsBefore','epochMs'})
        need(accepted['sequence']==value['acceptedSequence'] and entity(accepted['keyEntity']) and integer(accepted['keyType'],0,14)
             and integer(accepted['layerBefore'],0,31) and type(accepted['capsBefore']) is bool
             and (accepted['keyEntityInstance'] is None or nonce(accepted['keyEntityInstance']))
             and integer(accepted['epochMs'],1) and accepted['epochMs']<=packet['capturedEpochMs']+250)
    memberships=value['layerMembership'];need(type(memberships) is list and 0<len(memberships)<=32)
    all_ids=[];active_ids=None
    for index,membership in enumerate(memberships):
        exact(membership,{'layer','entityIds'});need(type(membership['layer']) is int and membership['layer']==index
             and type(membership['entityIds']) is list and all(entity(i) for i in membership['entityIds']))
        all_ids.extend(membership['entityIds'])
        if index==value['activeLayer']:active_ids=membership['entityIds']
    need(0<len(all_ids)<=256 and len(all_ids)==len(set(all_ids)) and active_ids)
    keys=value['keys'];need(type(keys) is list and len(keys)==len(active_ids));identifiers=[];active=[]
    for key in keys:
        exact(key,{'id','layer','type','effectiveUtf16Hex','switchLayer','pressed','ready','visible','hostType','entityType',
                   'parentId','createdEpochUs','entityInstance','geometry'})
        need(entity(key['id']) and key['id']!=value['anchor'] and integer(key['layer'],0,31) and integer(key['type'],0,14)
             and integer(key['switchLayer'],0,31) and all(type(key[k]) is bool for k in ('pressed','ready','visible'))
             and key['hostType']=='local' and key['entityType'] in ('Text','Model') and key['parentId']==value['anchor']
             and type(key['createdEpochUs']) is str and re.fullmatch('[1-9][0-9]{0,19}',key['createdEpochUs']) and nonce(key['entityInstance']))
        units(key['effectiveUtf16Hex']);identifiers.append(key['id'])
        need(key['layer']==value['activeLayer'])
        if key['layer']==value['activeLayer']:
            active.append(key);geometry=key['geometry'];exact(geometry,{'worldCenter','worldRotation','worldDimensions'})
            vector(geometry['worldCenter'],3);vector(geometry['worldRotation'],4);vector(geometry['worldDimensions'],3)
            need(all(v>0 for v in geometry['worldDimensions']) and abs(sum(v*v for v in geometry['worldRotation'])-1)<.001)
        else:need(key['geometry'] is None)
    need(len(identifiers)==len(set(identifiers)) and set(identifiers)==set(active_ids) and active)
    # Readability is distinct from input admission. Hidden/unready/mallet and
    # foreign-target states remain actual original evidence, not desired state.
    return value


def validate(value,request,pid,epoch,focus):
    command(request);document.strict(value);exact(value,HEAD)
    exact(focus,{'raw','request','documentOriginal'});old=decode(focus['raw'])
    validate_focus(old,focus['request'],pid,old['capturedEpochMs'],focus['documentOriginal'])
    need(old['status']=='ready' and focus['request']['operation']=='observe-current-focus' and focus['request']['control']=='text'
         and request['focusNonce']==old['commandId'] and all(request[k]==old[k] for k in ('runId','ownerToken'))
         and request['fixtureUrl']==focus['request']['fixtureUrl'])
    need(type(value['picoWorldCurrentKeyboardVersion']) is int and value['picoWorldCurrentKeyboardVersion']==VERSION
         and all(value[k]==request[k] for k in ('commandId','runId','ownerToken','focusNonce'))
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid and nonce(value['instance'])
         and integer(value['sequence'],1) and value['status'] in ('ready','unavailable')
         and all(integer(value[k],1) for k in ('requestedEpochMs','capturedEpochMs'))
         and all(integer(value[k]) for k in ('requestedMonotonicMs','capturedMonotonicMs')))
    fresh(value['capturedEpochMs'],epoch)
    if value['status']=='unavailable':exact(value['source'],set());return value
    fresh(value['requestedEpochMs'],value['capturedEpochMs']);fresh(old['requestedEpochMs'],value['capturedEpochMs'])
    need(0<=value['capturedMonotonicMs']-value['requestedMonotonicMs']<=1500
         and value['requestedMonotonicMs']>=old['capturedMonotonicMs'])
    source=value['source'];exact(source,{'focusReference','nativeBefore','nativeAfter','nativeEditor','keyboard'})
    exact(source['focusReference'],{'commandId','instance','sequence'})
    need(same(source['focusReference'],{k:old[k] for k in ('commandId','instance','sequence')})
         and same(source['nativeEditor'],old['source']['nativeEditor']) and source['nativeEditor']['focused'] is True)
    for side in ('nativeBefore','nativeAfter'):
        current=source[side];exact(current,{'native','finish'});native=current['native'];exact(native,document.NATIVE);document.identity(native)
        need(same(document.semantic(native),document.semantic(old['source']['authorityAfter']['native']))
             and same(current['finish'],old['source']['originalFinish']) and integer(native['capturedMonotonicMs'])
             and value['requestedMonotonicMs']<=native['capturedMonotonicMs']<=value['capturedMonotonicMs'])
        fresh(native['capturedEpochMs'],value['capturedEpochMs'])
    keyboard(source['keyboard'],value,old['source']['authorityAfter']['native']['sourceIdentity'][len('web-entity:'):])
    return value


class PicoWorldCurrentKeyboard:
    def __init__(self,focus,send,read,retain,capacity):
        need(type(focus) is PicoWorldCurrentInput and all(callable(fn) for fn in (send,read,retain,capacity)))
        self.focus,self.send,self.read_raw,self.retain=focus,send,read,retain
        self.capacity=capacity
        self.lock,self.guard,self.clock_ms,self.pid=focus.lock,focus.guard,focus.clock_ms,focus.pid
        self.monotonic,self.sleep=focus.monotonic,focus.sleep
        self._original=self._anchor=None;self.issued=0;self.failed=False

    def read(self,run,url,owner):
        need(not self.failed and self.lock._owner is None and self.issued<128)
        started=self.monotonic();requested=self.clock_ms()
        try:
            self.focus.read(run,url,owner,'observe-current-focus','text');focus=deepcopy(self.focus.original())
            call=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='pico-world-web',runId=run,
                fixtureUrl=url,operation='observe-current-keyboard',ownerToken=owner,focusNonce=decode(focus['raw'])['commandId']))
            self.issued+=1;request_ref=self.retain(dict(request=deepcopy(call),focusOriginal=deepcopy(focus)))
            def fence():
                need(self.guard() is not False);self.focus.require_warm(focus)
                epoch=self.clock_ms();now=self.monotonic()
                need(number(now,started,started+1.5) and requested-250<=epoch<=requested+1500)
            with self.lock.held():
                self.capacity();fence();self.send(deepcopy(call));value=None
                for attempt in range(31):
                    self.capacity();fence();raw=self.read_raw()
                    raw_ref=self.retain(dict(request=deepcopy(call),raw=raw)) # Raw before ANY parser/refusal.
                    need(type(raw) is str and len(raw.encode())<=LIMIT)
                    packet=decode(raw) if raw else None
                    if type(packet) is dict and packet.get('commandId')==call['commandId']:
                        validate(packet,call,self.pid,self.clock_ms(),focus);need(packet['status']=='ready')
                        need(packet['requestedEpochMs']>=requested-250)
                        value=deepcopy(packet);break
                    need(attempt<30);self.sleep(.05)
                need(value is not None)
                original=dict(raw=raw,request=deepcopy(call),focusOriginal=deepcopy(focus));seal=json_digest(original)
                fence()
            fence();validate(value,call,self.pid,self.clock_ms(),focus)
            self._original,self._anchor=original,(started,requested,seal)
            self._references=dict(request=deepcopy(request_ref),raw=deepcopy(raw_ref))
            self.require_warm(original);return value
        except BaseException:
            self.failed=True;raise

    def original(self):
        need(self._original is not None);return deepcopy(self._original)

    def original_references(self):
        need(self._original is not None);return deepcopy(self._references)

    def require_warm(self,original):
        need(not self.failed and self._anchor is not None)
        started,requested,seal=self._anchor
        need(json_digest(original)==seal and json_digest(self._original)==seal and self.guard() is not False)
        self.focus.require_warm(original['focusOriginal']);packet=decode(original['raw'])
        validate(packet,original['request'],self.pid,self.clock_ms(),original['focusOriginal'])
        epoch=self.clock_ms();now=self.monotonic()
        need(number(now,started,started+1.5) and requested-250<=epoch<=requested+1500)
