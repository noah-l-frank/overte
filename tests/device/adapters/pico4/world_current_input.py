"""Readonly CurrentInput1 calibration/focus, joined to fresh CurrentDocument1.

No input, desired focus, text operation, generic JS or shared journey is added.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4 import world_current_document as document
from adapters.pico4.browser_source import CONTROLS,geometry_original
from adapters.pico4.world_browser_ray import validate as ray_grammar

VERSION=1
FILE='feature-world-current-input.json'
OPS={'measure-current-ray','observe-current-focus'}
HEAD={'picoWorldCurrentInputVersion','commandId','runId','ownerToken','documentNonce','instance','sequence','processId',
      'requestedEpochMs','requestedMonotonicMs','capturedEpochMs','capturedMonotonicMs','status','source'}


def same(a,b):return json.dumps(a,sort_keys=True,separators=(',',':'))==json.dumps(b,sort_keys=True,separators=(',',':'))


def command(value):
    document.strict(value)
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken','documentNonce','control'})
    need(type(value['operation']) is str and value['operation'] in OPS and type(value['control']) is str and value['control'] in CONTROLS
         and type(value['documentNonce']) is str and re.fullmatch(document.HEX,value['documentNonce'])
         and value['documentNonce']!=value['commandId']
         and (value['operation']!='observe-current-focus' or value['control'] in ('text','foreign')))
    base={k:v for k,v in value.items() if k not in ('documentNonce','control')};base['operation']='observe-current-document';document.command(base)
    return value


def original_document(original,pid):
    exact(original,{'raw','request'});raw=original['raw'];need(type(raw) is str and len(raw.encode())<=65536)
    packet=decode(raw);document.validate(packet,original['request'],pid,packet['capturedEpochMs']);need(packet['status']=='ready')
    return packet


def authority(pair,packet):
    exact(pair,{'native','java'});native=pair['native'];java=pair['java'];exact(native,document.NATIVE);exact(java,document.JAVA)
    for item in (native,java):
        document.identity(item);fresh(item['capturedEpochMs'],packet['capturedEpochMs'])
        need(packet['requestedEpochMs']-250<=item['capturedEpochMs']<=packet['capturedEpochMs']+250)
    need(type(native['itemInstance']) is str and re.fullmatch(document.HEX,native['itemInstance'])
         and type(native['sourceIdentity']) is str and re.fullmatch(r'web-entity:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',native['sourceIdentity'])
         and all(native[k] is True for k in ('created','authorized','sessionActive')) and all(native[k] is False for k in ('suspended','loading'))
         and all(java[k] is True for k in ('ownerCurrent','active','foreground','windowFocused')) and all(java[k] is False for k in ('destroyed','closing','loading'))
         and integer(native['capturedMonotonicMs']) and integer(java['capturedElapsedMs'])
         and packet['requestedMonotonicMs']<=native['capturedMonotonicMs']<=packet['capturedMonotonicMs']
         and all(native[k]==java[k] for k in ('handle','creation','grant','page','url','sourceUrl')))


def validate(value,request,pid,epoch,original):
    command(request);document.strict(value);exact(value,HEAD);doc=original_document(original,pid)
    need(type(value['picoWorldCurrentInputVersion']) is int and value['picoWorldCurrentInputVersion']==VERSION
         and all(value[k]==request[k] for k in ('commandId','runId','ownerToken','documentNonce'))
         and doc['commandId']==request['documentNonce'] and all(doc[k]==request[k] for k in ('runId','ownerToken'))
         and original['request']['fixtureUrl']==request['fixtureUrl'] and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch(document.HEX,value['instance']) and integer(value['sequence'],1)
         and type(value['status']) is str and value['status'] in ('pending','ready','unavailable')
         and all(integer(value[k],1) for k in ('requestedEpochMs','capturedEpochMs'))
         and all(integer(value[k]) for k in ('requestedMonotonicMs','capturedMonotonicMs'))
         and value['capturedMonotonicMs']>=value['requestedMonotonicMs'])
    fresh(value['capturedEpochMs'],epoch)
    if value['status']=='unavailable':exact(value['source'],set());return value
    fresh(value['requestedEpochMs'],value['capturedEpochMs']);fresh(doc['requestedEpochMs'],value['capturedEpochMs'])
    need(value['capturedMonotonicMs']-value['requestedMonotonicMs']<=1500)
    if value['status']=='pending':exact(value['source'],set());return value
    source=value['source'];is_ray=request['operation']=='measure-current-ray';raw_key='geometryRaw' if is_ray else 'focusRaw'
    exact(source,{'documentReference','originalFinish','authorityBefore','authorityAfter',raw_key,'worldRay' if is_ray else 'nativeEditor'})
    exact(source['documentReference'],{'commandId','instance','sequence'})
    need(same(source['documentReference'],{k:doc[k] for k in ('commandId','instance','sequence')})
         and same(source['originalFinish'],doc['source']['originalFinish']))
    a=source['authorityBefore'];b=source['authorityAfter'];authority(a,value);authority(b,value)
    need(all(same(document.semantic(a[k]),document.semantic(b[k])) for k in ('native','java'))
         and same(document.semantic(a['native']),document.semantic(doc['source']['authorityAfter']['native']))
         and same(document.semantic(a['java']),document.semantic(doc['source']['authorityAfter']['java']))
         and a['native']['capturedMonotonicMs']<=b['native']['capturedMonotonicMs']
         and a['native']['capturedEpochMs']-250<=a['java']['capturedEpochMs']<=b['java']['capturedEpochMs']<=b['native']['capturedEpochMs']+250
         and a['java']['capturedElapsedMs']<=b['java']['capturedElapsedMs']<=a['java']['capturedElapsedMs']+1500)
    raw=source[raw_key];need(type(raw) is str and len(raw.encode())<=16384)
    transaction=decode(raw);exact(transaction,{'before','geometryRaw','after'})
    need(same(transaction['before'],a['java']) and same(transaction['after'],b['java'])
         and type(transaction['geometryRaw']) is str and len(transaction['geometryRaw'].encode())<=8192)
    geometry=geometry_original(transaction['geometryRaw'],request,a['native']['url'],value['capturedEpochMs'])
    original_dom=doc['source']['dom']
    need(geometry['instance']==original_dom['instance'] and geometry['sequence']>original_dom['sequence']
         and same(geometry['document'],original_dom['document'])
         and a['java']['capturedEpochMs']-250<=geometry['capturedEpochMs']<=b['java']['capturedEpochMs']+250)
    if is_ray:
        # Pure grammar adapter only: every field is the actual new-protocol
        # original. No old-version wire packet or successful input is minted.
        ray=ray_grammar(dict(capturedEpochMs=value['capturedEpochMs'],source=dict(worldRay=source['worldRay'],
            geometryRaw=transaction['geometryRaw'],nativeView=dict(url=a['native']['url']))),request)
        need(ray['sourceIdentity']==a['native']['sourceIdentity'] and ray['sourceUrl']==a['native']['sourceUrl'])
    else:
        editor=source['nativeEditor'];exact(editor,{'text','cursor','anchor','absoluteCursor','kind','sensitive','focused','enabled'})
        need(type(editor['text']) is str);units=len(editor['text'].encode('utf-16-le'))//2
        need(units<=512 and all(integer(editor[k],0,units) for k in ('cursor','anchor')) and integer(editor['absoluteCursor'],0,16384)
             and type(editor['kind']) is str and editor['kind'] in ('','text','url') and editor['sensitive'] is False
             and type(editor['focused']) is bool and type(editor['enabled']) is bool and editor['focused']==geometry['editor']['focused'])
        if editor['focused']:
            need(editor['enabled'] and editor['absoluteCursor']==editor['cursor'] and editor['kind']==('url' if request['control']=='foreign' else 'text')
                 and all(same(editor[k],geometry['editor'][k]) for k in ('text','cursor','anchor')))
    return value


class PicoWorldCurrentInput:
    """New document original then exactly one readonly geometry source query.

    Each read performs both real outer lock exits. An already-held caller must
    delegate outside, preserving its original input intent; no nested publish.
    """
    def __init__(self,documents,send,read):
        need(type(documents) is document.PicoWorldCurrentDocument and all(callable(fn) for fn in (send,read)))
        self.documents,self.send,self.read_raw=documents,send,read
        self.lock,self.guard,self.clock_ms,self.pid=documents.lock,documents.guard,documents.clock_ms,documents.pid
        self.monotonic,self.sleep=documents.monotonic,documents.sleep;self.raw=self.last_request=self.document_original=self.last=None;self._warm_anchor=None

    def read(self,run,url,owner,operation,control):
        need(self.lock._owner is None and self.guard() is not False)
        # Validate the operation before even the readonly document query.
        command(dict(schemaVersion=1,commandId='1'*32,action='pico-world-web',runId=run,fixtureUrl=url,
                     operation=operation,ownerToken=owner,documentNonce='2'*32,control=control))
        started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        value=self.documents.read(run,url,owner);original=deepcopy(self.documents.original());doc=original_document(original,self.pid)
        need(same(value,doc) and self.lock._owner is None)
        call=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='pico-world-web',runId=run,fixtureUrl=url,
                     operation=operation,ownerToken=owner,documentNonce=doc['commandId'],control=control))
        previous=started
        with self.lock.held():
            need(self.guard() is not False);self.send(deepcopy(call));latest=None;result=None
            for attempt in range(31):
                need(self.guard() is not False);raw=self.read_raw();need(type(raw) is str and len(raw.encode())<=65536)
                packet=decode(raw) if raw else None
                if type(packet) is dict and packet.get('commandId')==call['commandId']:
                    validate(packet,call,self.pid,self.clock_ms(),original);need(packet['status']!='unavailable')
                    if latest is not None:
                        need(packet['instance']==latest['instance'] and packet['sequence']>=latest['sequence']
                             and packet['requestedEpochMs']==latest['requestedEpochMs'] and packet['requestedMonotonicMs']==latest['requestedMonotonicMs']
                             and packet['capturedEpochMs']>=latest['capturedEpochMs'] and packet['capturedMonotonicMs']>=latest['capturedMonotonicMs']
                             and (packet['sequence']!=latest['sequence'] or same(packet,latest)))
                    latest=deepcopy(packet)
                    if packet['status']=='ready':
                        result,saved,saved_call,saved_original=deepcopy(packet),deepcopy(packet),deepcopy(call),deepcopy(original);break
                now=self.monotonic();need(number(now,previous,started+1.5) and now-started<=1.5 and attempt<30);previous=now
                self.sleep(min(.05,1.5-(now-started)))
            need(result is not None)
        validate(result,call,self.pid,self.clock_ms(),original)
        raw_key='geometryRaw' if operation=='measure-current-ray' else 'focusRaw'
        geometry=geometry_original(decode(result['source'][raw_key])['geometryRaw'],call,
            result['source']['authorityBefore']['native']['url'],result['capturedEpochMs'])
        ray_clock=[result['source']['worldRay']['capturedEpochMs']] if operation=='measure-current-ray' else []
        from adapters.chat_journey.source_chunks import json_digest
        warm_seal=json_digest(dict(raw=raw,request=saved_call,documentOriginal=saved_original))
        need(self.guard() is not False);epoch=self.clock_ms();finished=self.monotonic()
        need(number(finished,previous,started+1.5) and finished-started<=1.5)
        clocks=(doc['requestedEpochMs'],doc['capturedEpochMs'],doc['source']['dom']['capturedEpochMs'],
                         result['requestedEpochMs'],result['capturedEpochMs'],geometry['capturedEpochMs'],*ray_clock,
                         *(doc['source'][side][kind]['capturedEpochMs'] for side in ('authorityBefore','authorityAfter') for kind in ('native','java')),
                         *(result['source'][side][kind]['capturedEpochMs'] for side in ('authorityBefore','authorityAfter') for kind in ('native','java')))
        need(max(epoch-min(clocks),requested-min(clocks)+(finished-started)*1000)<=1500)
        for captured in clocks:
            fresh(captured,epoch)
        self.last,self.raw,self.last_request,self.document_original=saved,raw,saved_call,saved_original
        self._warm_anchor=(started,requested,warm_seal)
        return result

    def require_warm(self,original):
        from adapters.chat_journey.source_chunks import json_digest
        need(self._warm_anchor is not None)
        started,requested,seal=self._warm_anchor
        need(json_digest(original)==seal and json_digest(self.original())==seal)
        packet=decode(original['raw']);call=original['request'];doc=original_document(original['documentOriginal'],self.pid)
        validate(packet,call,self.pid,self.clock_ms(),original['documentOriginal'])
        raw_key='geometryRaw' if call['operation']=='measure-current-ray' else 'focusRaw'
        geometry=geometry_original(decode(packet['source'][raw_key])['geometryRaw'],call,packet['source']['authorityBefore']['native']['url'],packet['capturedEpochMs'])
        clocks=[doc['requestedEpochMs'],doc['capturedEpochMs'],doc['source']['dom']['capturedEpochMs'],packet['requestedEpochMs'],packet['capturedEpochMs'],geometry['capturedEpochMs']]
        for value in (doc,packet):
            clocks.extend(value['source'][side][kind]['capturedEpochMs'] for side in ('authorityBefore','authorityAfter') for kind in ('native','java'))
        if call['operation']=='measure-current-ray':clocks.append(packet['source']['worldRay']['capturedEpochMs'])
        need(json_digest(original)==seal and json_digest(self.original())==seal)
        need(self.guard() is not False);epoch=self.clock_ms();now=self.monotonic()
        need(number(now,started,started+1.5) and max(epoch-min(clocks),requested-min(clocks)+(now-started)*1000)<=1500)
        for captured in clocks:fresh(captured,epoch)

    def original(self):
        need(self.raw is not None)
        return dict(raw=self.raw,request=deepcopy(self.last_request),documentOriginal=deepcopy(self.document_original))
