# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""One current-focus IME attempt; actual input delivery is not an effect verdict.

Born typed provider owns the SAME Root intent/Raw/event/trace work. No second
command, old focus adoption,clock renewal,expected editor setter or recovery.
"""
from copy import deepcopy
import re,time,uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4 import world_current_document as document
from adapters.pico4.world_current_input import PicoWorldCurrentInput,original_document,validate as validate_focus,same

VERSION=1
FILE='feature-world-current-ime.json'
FIELDS={'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken','documentNonce','focusNonce','control','text'}
HEAD={'picoWorldCurrentImeVersion','commandId','runId','ownerToken','documentNonce','focusNonce','instance','sequence','processId',
    'requestedEpochMs','requestedMonotonicMs','capturedEpochMs','capturedMonotonicMs','status','source'}


def command(value):
    document.strict(value);exact(value,FIELDS)
    need(type(value['operation']) is str and value['operation']=='commit-current-text'
        and type(value['control']) is str and value['control'] in ('text','foreign') and type(value['text']) is str)
    for name in ('documentNonce','focusNonce'):
        need(type(value[name]) is str and re.fullmatch(document.HEX,value[name]))
    need(len({value['commandId'],value['documentNonce'],value['focusNonce']})==3)
    text=value['text'];need(sum(2 if ord(c)>65535 else 1 for c in text)<=512
        and not any(ord(c)<32 or ord(c)==127 or 0xE000<=ord(c)<=0xE05E or 0xD800<=ord(c)<=0xDFFF for c in text))
    base={key:value[key] for key in ('schemaVersion','commandId','action','runId','fixtureUrl','ownerToken')}
    base['operation']='observe-current-document';document.command(base);return value


def validate(packet,call,pid,epoch,original):
    command(call);document.strict(packet);exact(packet,HEAD)
    need(type(packet['picoWorldCurrentImeVersion']) is int and packet['picoWorldCurrentImeVersion']==1
        and integer(pid,1) and type(packet['processId']) is int and packet['processId']==pid
        and all(type(packet[key]) is str and packet[key]==call[key] for key in ('commandId','runId','ownerToken','documentNonce','focusNonce'))
        and type(packet['instance']) is str and re.fullmatch(document.HEX,packet['instance']) and integer(packet['sequence'],1)
        and type(packet['status']) is str and packet['status'] in ('pending','ready','unavailable'))
    for key in ('requestedEpochMs','capturedEpochMs'):need(integer(packet[key],1))
    for key in ('requestedMonotonicMs','capturedMonotonicMs'):need(integer(packet[key]))
    need(0<=packet['capturedMonotonicMs']-packet['requestedMonotonicMs']<=1500)
    fresh(packet['capturedEpochMs'],epoch);fresh(packet['requestedEpochMs'],epoch)
    if packet['status']=='pending':exact(packet['source'],set());return packet
    source=packet['source'];exact(source,{'reason','dispatch','nativeBefore','nativeAfter','focusReference','documentReference','originalFinish'})
    need(type(source['reason']) is str and (not source['reason'] if packet['status']=='ready' else bool(source['reason'])))
    actual_focus=decode(original['raw']);doc=original_document(original['documentOriginal'],pid)
    validate_focus(actual_focus,original['request'],pid,actual_focus['capturedEpochMs'],original['documentOriginal'])
    need(same(source['focusReference'],{k:actual_focus[k] for k in ('commandId','instance','sequence')})
        and same(source['documentReference'],{k:doc[k] for k in ('commandId','instance','sequence')})
        and same(source['originalFinish'],doc['source']['originalFinish']))
    from adapters.pico4.world_current_consumption import native as native_original
    for side in ('nativeBefore','nativeAfter'):
        snapshot=source[side];exact(snapshot,{'native','finish'})
        need(same(snapshot['finish'],doc['source']['originalFinish']))
        native_original(snapshot['native'],actual_focus,packet)
    need(source['nativeBefore']['native']['capturedMonotonicMs']<=source['nativeAfter']['native']['capturedMonotonicMs'])
    dispatch=source['dispatch'];exact(dispatch,{'issued','acceptedQt','issuedEpochMs','issuedMonotonicMs'})
    need(type(dispatch['issued']) is bool and type(dispatch['acceptedQt']) is bool)
    if dispatch['issued']:
        need(integer(dispatch['issuedEpochMs'],1) and integer(dispatch['issuedMonotonicMs'])
            and packet['requestedMonotonicMs']<=dispatch['issuedMonotonicMs']<=packet['capturedMonotonicMs'])
    else:need(dispatch['issuedEpochMs'] is dispatch['issuedMonotonicMs'] is None and not dispatch['acceptedQt'])
    return packet


class PicoWorldCurrentIme:
    def __init__(self,focus,send,read,retain,capacity,resource_provider):
        from adapters.pico4.world_current_host_stage import WorldRootCurrentParticipant2
        need(type(focus) is PicoWorldCurrentInput and type(resource_provider) is WorldRootCurrentParticipant2
            and resource_provider.host_selection.operation=='ime' and all(callable(f) for f in (send,read,retain,capacity)))
        self.focus=focus;self.send=send;self.read_raw=read;self.retain=retain;self.capacity=capacity;self.resources=resource_provider
        self.lock=focus.lock;self.guard=focus.guard;self.clock_ms=focus.clock_ms;self.monotonic=focus.monotonic;self.sleep=focus.sleep;self.pid=focus.pid
        self.issued=self.failed=False;self.failure=None;self.original_focus=self.call=self.raw=self.last=self.entry_text=None
    def commit(self,text):
        return self.resources.ime_commit(self,text)

    def _commit_original(self,text):
        need(not self.issued and not self.failed and self.lock._owner is None)
        # Explicit typed Root books the actual text/intent/event/Raw/response/
        # trace copies BEFORE command,source copies,writer or dispatch.
        try:
            self.resources.ime_entry(self,text)
            self.original_focus=self.focus.original();self.focus.require_warm(self.original_focus)
            old=self.original_focus['request']
            self.call=command({**{k:old[k] for k in ('schemaVersion','action','runId','fixtureUrl','ownerToken')},
                'commandId':uuid.uuid4().hex,'operation':'commit-current-text','documentNonce':old['documentNonce'],
                'focusNonce':old['commandId'],'control':old['control'],'text':text})
            started=self.monotonic();requested=self.clock_ms()
            # SAME original serialization domain as Document/Consumption.
            # Started/requested above charge lock wait to the original1.5.
            with self.lock.held():
                self.retain(dict(kind='ime-request',request=deepcopy(self.call),focusOriginal=self.original_focus))
                self.capacity();self.focus.require_warm(self.original_focus)
                need(self.guard() is not False)
                current=self.clock_ms();now=self.monotonic();fresh(requested,current);need(number(now,started,started+1.5))
                # Fence before the actual low-level provider. A lost return stays
                # issued/unknown; no second send is available from this owner.
                self.issued=True;self.send(deepcopy(self.call));previous=now
                for poll in range(31):
                    self.capacity();need(self.guard() is not False)
                    current=self.clock_ms();now=self.monotonic();fresh(requested,current);need(number(now,previous,started+1.5))
                    raw=self.read_raw();self.raw=raw
                    self.retain(dict(kind='ime-raw',request=self.call,raw=raw))
                    need(type(raw) is str and len(raw.encode('utf-8'))<=65536)
                    packet=decode(raw) if raw else None
                    if type(packet) is dict and packet.get('commandId')==self.call['commandId']:
                        validate(packet,self.call,self.pid,self.clock_ms(),self.original_focus)
                        need(packet['status']!='unavailable')
                        if packet['status']=='ready':
                            need(packet['source']['dispatch']['issued'] is True)
                            saved=deepcopy(packet);break
                    previous=now;need(poll<30);self.sleep(min(.05,1.5-(now-started)))
                else:need(False)
            self.capacity();need(self.guard() is not False)
            epoch=self.clock_ms();finished=self.monotonic();fresh(requested,epoch);need(number(finished,started,started+1.5))
            self.last=saved
            self.resources.event_query_returned(self,packet)
            return packet  # Delivery only; no text or feature success verdict.
        except BaseException as error:
            self.failed=True
            if self.failure is None:self.failure=(error,error.__traceback__)
            self.resources.fail(error);raise
