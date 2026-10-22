"""Actual native receive history; a local echo is never remote delivery proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context

VERSION=3
FILE='feature-chat-observation.json'
HEX='[0-9a-f]{32}'
SHA='[0-9a-f]{64}'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','operation','runId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-chat-observe' and value['operation'] in ('observe','retire','inspect')
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '')+HEX,value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX,value['runId']))
    return value


def validate(value,request,pid,epoch):
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'chatVersion','commandId','runId','operation','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['chatVersion']) is int and value['chatVersion'] in (1,2,VERSION)
         and all(value[k]==request[k] for k in ('commandId','runId','operation'))
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['sequence'],1) and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    exact(source,{'scopePresent','retired','selfSha256','mixerPresent','mixerSha256','openedEpochMs','eventSequence','droppedEvents','events'}
        | ({'session'} if value['chatVersion']>=2 else set())
        | ({'openedCommandId','retiredCommandId'} if value['chatVersion']>=3 else set()))
    need(all(type(source[k]) is bool for k in ('scopePresent','retired','mixerPresent'))
         and not (source['scopePresent'] and source['retired'])
         and type(source['selfSha256']) is str and re.fullmatch(SHA,source['selfSha256'])
         and type(source['mixerSha256']) is str
         and (re.fullmatch(SHA,source['mixerSha256']) if source['mixerPresent'] else source['mixerSha256']=='')
         and integer(source['openedEpochMs']) and integer(source['eventSequence']) and integer(source['droppedEvents'])
         and type(source['events']) is list and len(source['events'])==min(128,source['eventSequence'])
         and source['droppedEvents']==source['eventSequence']-len(source['events']))
    if value['chatVersion']>=2:
        session=source['session']
        exact(session,{'domainSessionVersion','instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs','mixerActive'})
        need(type(session['domainSessionVersion']) is int and session['domainSessionVersion']==1
            and type(session['instance']) is str and re.fullmatch(HEX,session['instance']) and integer(session['revision'])
            and type(session['connected']) is bool and type(session['mixerActive']) is bool
            and type(session['domainSha256']) is str and (session['domainSha256']=='' or re.fullmatch(SHA,session['domainSha256']))
            and type(session['connectionBirth']) is str and integer(session['connectedEpochMs'])
            and (source['mixerPresent'] or not session['mixerActive']))
        if session['connected']:
            need(session['domainSha256']!='' and re.fullmatch(HEX,session['connectionBirth'])
                and 0<session['connectedEpochMs']<=value['capturedEpochMs'] and session['revision']>=1)
        else:need(session['connectionBirth']=='' and session['connectedEpochMs']==0)
    if value['chatVersion']>=3:
        opened,retired=source['openedCommandId'],source['retiredCommandId']
        need(all(type(item) is str and (item=='' or re.fullmatch('(?:ios-)?'+HEX,item)) for item in (opened,retired)))
        if source['scopePresent']:need(opened!='' and retired=='')
        elif source['retired']:need(retired!='')
        else:need(opened==retired=='')
    if source['scopePresent']:need(0<source['openedEpochMs']<=value['capturedEpochMs'])
    else:need(source['openedEpochMs']==source['eventSequence']==source['droppedEvents']==len(source['events'])==0)
    if request['operation']=='observe':need(source['scopePresent'] and not source['retired'])
    if request['operation']=='retire':need(source['retired'] and not source['scopePresent'])
    allowed=context(request['runId']);texts={allowed[k] for k in ('unicode','reply','hidden','retry')}
    previous=source['openedEpochMs']
    for seq,event in enumerate(source['events'],source['droppedEvents']+1):
        exact(event,{'sequence','capturedEpochMs','senderSha256','localOnly','channel','text'})
        need(integer(event['sequence'],1) and event['sequence']==seq and integer(event['capturedEpochMs'],1)
             and previous<=event['capturedEpochMs']<=value['capturedEpochMs']
             and type(event['senderSha256']) is str and re.fullmatch(SHA,event['senderSha256'])
             and type(event['localOnly']) is bool and event['channel'] in ('local','domain') and event['text'] in texts)
        previous=event['capturedEpochMs']
    return value


def identity(run,source_uuid):
    need(type(run) is str and re.fullmatch(HEX,run) and type(source_uuid) is str)
    try:value=uuid.UUID(source_uuid)
    except ValueError:raise NativeUIError('Native Chat source identity is invalid') from None
    need(str(value)==source_uuid and value.int!=0)
    return hashlib.sha256(run.encode('ascii')+b':'+value.bytes).hexdigest()


def received_texts(value,*,sender_sha256,receiver_sha256,channel,remote=True):
    """Preserve actual received order/multiplicity, without claiming rendered UI.

    sender_sha256 must be derived from independently bound actual peer identity;
    passing an outgoing request identity is not peer qualification.
    """
    request={k:value[k] for k in ('commandId','runId','operation')}
    request.update(schemaVersion=1,action='feature-chat-observe')
    validate(value,request,value['processId'],value['capturedEpochMs'])
    source=value['source']
    need(source['scopePresent'] and not source['retired'] and source['droppedEvents']==0
         and type(sender_sha256) is str and re.fullmatch(SHA,sender_sha256)
         and channel in ('local','domain') and type(remote) is bool
         and receiver_sha256==source['selfSha256'] and (not remote or sender_sha256!=receiver_sha256))
    return [event['text'] for event in source['events'] if event['senderSha256']==sender_sha256
            and event['channel']==channel and (not remote or not event['localOnly'])]


class NativeChatObservation:
    def __init__(self,send,read,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.instance,self.sequence,self.captured,self.source=None,0,0,None
        self.run=None

    def perform(self,run,operation):
        try:
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                         action='feature-chat-observe',operation=operation,runId=run)
            command(request,ios=self.ios);need(self.run in (None,run) and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    # iOS host UTC is not the native source clock. Actual AFC/PID
                    # acquisition bounds freshness there; native clocks stay native.
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    validate(value,request,self.pid,epoch)
                    need(self.instance in (None,value['instance']) and value['sequence']>self.sequence
                         and value['capturedEpochMs']>=self.captured
                         and (self.ios or value['capturedEpochMs']>=requested))
                    current=value['source']
                    if self.source is not None:
                        need(current['selfSha256']==self.source['selfSha256'] and not (self.source['retired'] and not current['retired']))
                        if 'session' in self.source:
                            need('session' in current and current['session']['instance']==self.source['session']['instance']
                                and current['session']['revision']>=self.source['session']['revision'])
                            if current['session']['revision']==self.source['session']['revision']:
                                need(all(current['session'][key]==self.source['session'][key] for key in
                                    ('connected','domainSha256','connectionBirth','connectedEpochMs')))
                        if 'openedCommandId' in self.source:
                            need(all(key in current for key in ('openedCommandId','retiredCommandId')))
                            for key in ('openedCommandId','retiredCommandId'):
                                if self.source[key]:need(current[key]==self.source[key])
                        if self.source['scopePresent'] and current['scopePresent']:
                            need(current['openedEpochMs']==self.source['openedEpochMs']
                                 and current['eventSequence']>=self.source['eventSequence']
                                 and current['droppedEvents']>=self.source['droppedEvents'])
                            old={e['sequence']:e for e in self.source['events']}
                            need(all(e['sequence'] not in old or e==old[e['sequence']] for e in current['events']))
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                    self.run,self.instance,self.sequence,self.captured=run,value['instance'],value['sequence'],value['capturedEpochMs']
                    self.source=deepcopy(current);return value
                now=self.monotonic();need(number(now,0,1e15) and now>=previous);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Native Chat receive observation failed') from None
        raise NativeUIError('Native Chat receive observation is unavailable')


class ChatCaptureOwner:
    """Persist original process/session ownership before opening native cache."""
    def __init__(self,store,binding,guard,*,component_only=False):
        from adapters.normal_feature_state import context as binding_context
        need(callable(guard) and type(component_only) is bool)
        self.store,self.guard,self.component_only=store,guard,component_only
        self.binding=deepcopy(binding_context(binding,component_only=component_only))

    def owned(self):
        need(self.guard() is not False);value=self.store.read()
        if value is None:return None
        exact(value,{'ownershipVersion','binding','runId','sourceInstance','selfSha256','admitted','active'})
        from adapters.normal_feature_state import context as binding_context
        binding_context(value['binding'],component_only=self.component_only)
        need(type(value['ownershipVersion']) is int and value['ownershipVersion']==1 and value['binding']==self.binding
             and type(value['runId']) is str and re.fullmatch(HEX,value['runId'])
             and (value['sourceInstance'] is None or type(value['sourceInstance']) is str and re.fullmatch(HEX,value['sourceInstance']))
             and (value['selfSha256'] is None or type(value['selfSha256']) is str and re.fullmatch(SHA,value['selfSha256']))
             and all(type(value[k]) is bool for k in ('admitted','active'))
             and (not value['active'] or value['admitted'])
             and (not value['admitted'] or value['sourceInstance'] is not None and value['selfSha256'] is not None))
        return value

    def begin(self,run):
        need(type(run) is str and re.fullmatch(HEX,run));value=self.owned()
        if value is None:
            value=dict(ownershipVersion=1,binding=self.binding,runId=run,sourceInstance=None,selfSha256=None,admitted=False,active=False)
            self.store.write(value,None)
        need(value['runId']==run);return value

    def match(self,value):
        owned=self.owned();need(owned is not None and value['runId']==owned['runId']
             and owned['sourceInstance'] in (None,value['instance'])
             and owned['selfSha256'] in (None,value['source']['selfSha256']))
        return owned

    def admit(self,value):
        owned=self.match(value);source=value['source']
        if not owned['admitted']:
            need(not source['scopePresent'] and not source['retired'])
            updated={**owned,'sourceInstance':value['instance'],'selfSha256':source['selfSha256'],'admitted':True}
            self.store.write(updated,owned);return updated
        return owned

    def activated(self,value):
        owned=self.match(value);need(owned['admitted'] and value['source']['scopePresent'] and not value['source']['retired'])
        if not owned['active']:self.store.write({**owned,'active':True},owned)


class OwnedChatCapture:
    def __init__(self,reader,owner,run):
        need(isinstance(reader,NativeChatObservation) and isinstance(owner,ChatCaptureOwner)
             and type(run) is str and re.fullmatch(HEX,run))
        self.reader,self.owner,self.run=reader,owner,run

    def observe(self):
        owned=self.owner.begin(self.run)
        original=self.reader.perform(self.run,'inspect');self.owner.match(original)
        if owned['active']:need(original['source']['scopePresent'] and not original['source']['retired'])
        self.owner.admit(original) # Native absence and durable source pin before observe can create a cache.
        value=self.reader.perform(self.run,'observe');self.owner.activated(value)
        need(value['source']['droppedEvents']==0)
        return value

    def retire(self):
        owned=self.owner.owned()
        if owned is None:return
        need(owned['runId']==self.run)
        started=previous=self.reader.monotonic();need(number(started,0,1e15))
        def budget():
            nonlocal previous
            now=self.reader.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
        original=self.reader.perform(self.run,'inspect');budget();self.owner.match(original)
        if owned['admitted']:
            self.reader.perform(self.run,'retire');budget()
            for _ in range(2):
                value=self.reader.perform(self.run,'inspect');budget();self.owner.match(value)
                need(value['source']['retired'] and not value['source']['scopePresent']
                     and value['source']['events']==[] and value['source']['eventSequence']==0)
        else:
            # No native mutation was admitted. Never purge a pre-existing scope.
            need(not original['source']['scopePresent'] and not original['source']['retired'])
        need(self.owner.guard() is not False);self.owner.store.discard(owned)
