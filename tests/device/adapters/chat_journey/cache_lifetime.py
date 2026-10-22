"""Original Chat cache mutation ownership; uncertain mutations are never resent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_chat_observation import OwnedChatCapture,command,validate
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
MAX_FRAMES=24
PHASES=('ready','activation-issued','active','retirement-issued','retired')


class ChatCacheLifetime:
    def __init__(self,capture,store,source_lock,*,monotonic=time.monotonic):
        need(isinstance(capture,OwnedChatCapture) and isinstance(source_lock,ScriptSourceLock) and callable(monotonic)
            and capture.owner.store.path.parent==store.path.parent==source_lock.path.parent
            and capture.owner.store.path!=store.path and not getattr(capture.reader,'_chat_cache_lifetime_owned',False))
        self.capture,self.reader,self.store,self.lock=capture,capture.reader,store,source_lock
        self.monotonic=monotonic;self.last_clock=None;self.started=None;self.wanted=None;self.request=None
        owned=capture.owner.owned();need(owned is not None and owned['runId']==capture.run and owned['admitted'])
        self.scope=dict(chatCacheLifetimeVersion=VERSION,runId=capture.run,binding=deepcopy(capture.owner.binding),
            captureOwner=capture.owner.store.path.name,sourceInstance=owned['sourceInstance'],selfSha256=owned['selfSha256'])
        self.previous=store.read();self.base={**self.scope,'phase':'ready','activation':None,'retirement':None,'frames':[]}
        if self.previous is not None:
            exact(self.previous,set(self.base));need(all(same(self.previous[key],value) for key,value in self.scope.items()))
            self.base={**deepcopy(self.previous),'frames':unpack(self.previous['frames'])};self.validate()
            if self.base['frames']:
                value=self.base['frames'][-1]['packet']
                need(self.reader.instance is None and self.reader.run is None and self.reader.sequence==0 and self.reader.source is None)
                self.reader.instance,self.reader.run,self.reader.sequence,self.reader.captured=value['instance'],capture.run,value['sequence'],value['capturedEpochMs']
                self.reader.source=deepcopy(value['source'])
        need(not owned['active'] or self.base['phase']!='ready')
        capture.owner.bind_lifetime(store)
        owned=capture.owner.owned();need(owned['retirement'] is None or self.base['phase']=='retired')
        self.original_send=self.reader.send;self.reader.send=self.send;self.reader._chat_cache_lifetime_owned=True

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        if self.started is not None:need(value-self.started<=1.5)
        self.last_clock=value;return value

    def owner(self):
        owned=self.capture.owner.owned();need(owned is not None and owned['admitted'] and owned['runId']==self.scope['runId']
            and owned['sourceInstance']==self.scope['sourceInstance'] and owned['selfSha256']==self.scope['selfSha256'])
        return owned

    def validate(self):
        need(self.base['phase'] in PHASES and type(self.base['frames']) is list and len(self.base['frames'])<=MAX_FRAMES)
        for key,operation in (('activation','observe'),('retirement','retire')):
            intent=self.base[key]
            if intent is not None:
                exact(intent,{'request','requestedEpochMs','beforeIndex'});command(intent['request'])
                need(intent['request']['operation']==operation and intent['request']['runId']==self.capture.run and integer(intent['requestedEpochMs'],1)
                    and integer(intent['beforeIndex'],0,len(self.base['frames'])-1))
                before=self.base['frames'][intent['beforeIndex']]
                need(before['request']['operation']=='inspect' and before['packet']['capturedEpochMs']<=intent['requestedEpochMs'])
                fresh(before['packet']['capturedEpochMs'],intent['requestedEpochMs'])
                original=before['packet']['source']
                if operation=='observe':need(not original['scopePresent'] and not original['retired'] and not original['openedCommandId'] and not original['retiredCommandId'])
                else:need(original['scopePresent'] and not original['retired'] and self.base['activation'] is not None
                    and original['openedCommandId']==self.base['activation']['request']['commandId'])
        phase=self.base['phase']
        need((self.base['activation'] is None)==(phase=='ready')
            and (self.base['retirement'] is None)==(phase in ('ready','activation-issued','active')))
        previous=None;nonces=set()
        for index,row in enumerate(self.base['frames']):
            exact(row,{'request','requestedEpochMs','packet'});request=row['request'];value=row['packet']
            command(request);validate(value,request,self.reader.pid,value['capturedEpochMs'])
            need(value['chatVersion']==3 and request['commandId'] not in nonces and integer(row['requestedEpochMs'],1)
                and value['capturedEpochMs']>=row['requestedEpochMs'] and value['runId']==self.capture.run
                and value['instance']==self.scope['sourceInstance'] and value['source']['selfSha256']==self.scope['selfSha256']
                and value['source']['droppedEvents']==0)
            nonces.add(request['commandId']);source=value['source']
            if request['operation']!='inspect':
                intent=self.base['activation' if request['operation']=='observe' else 'retirement'];need(intent is not None
                    and intent['request']==request and intent['requestedEpochMs']==row['requestedEpochMs'] and intent['beforeIndex']<index)
            if source['openedCommandId']:
                need(self.base['activation'] is not None and source['openedCommandId']==self.base['activation']['request']['commandId']
                    and (not source['scopePresent'] or source['openedEpochMs']>=self.base['activation']['requestedEpochMs']))
            if source['retired']:
                need(self.base['retirement'] is not None and source['retiredCommandId']==self.base['retirement']['request']['commandId']
                    and value['capturedEpochMs']>=self.base['retirement']['requestedEpochMs'])
            if previous is not None:
                old=previous['source'];need(value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'])
                if old['openedCommandId']:need(source['openedCommandId']==old['openedCommandId'])
                if old['retiredCommandId']:need(source['retiredCommandId']==old['retiredCommandId'])
                if old['scopePresent'] and source['scopePresent']:
                    need(source['openedEpochMs']==old['openedEpochMs'] and source['events'][:len(old['events'])]==old['events'])
            previous=value
        if phase=='active':need(previous is not None and previous['source']['scopePresent'] and not previous['source']['retired'])
        if phase=='retired':
            need(len(self.base['frames'])>=2 and all(row['request']['operation']=='inspect' and row['packet']['source']['retired']
                and not row['packet']['source']['scopePresent'] for row in self.base['frames'][-2:]))

    def save(self,**changes):
        self.lock.assert_held();need(same(self.store.read(),self.previous));self.base={**self.base,**deepcopy(changes)};self.validate()
        value={**self.base,'frames':pack(self.base['frames'])};self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def send(self,request):
        self.lock.assert_held();command(request);need(request['operation']==self.wanted and self.request is None)
        fence=getattr(self,'phase_fence',None)
        if fence is not None and self.wanted!='inspect':fence.mark()
        epoch=self.reader.clock_ms();need(integer(epoch,1));self.request=dict(request=deepcopy(request),requestedEpochMs=epoch)
        if self.wanted!='inspect':
            key='activation' if self.wanted=='observe' else 'retirement'
            need(self.base[key] is None and self.base['phase']==('ready' if key=='activation' else 'active'))
            need(self.base['frames'] and self.base['frames'][-1]['request']['operation']=='inspect')
            fresh(self.base['frames'][-1]['packet']['capturedEpochMs'],epoch)
            self.save(**{key:{**self.request,'beforeIndex':len(self.base['frames'])-1},'phase':'activation-issued' if key=='activation' else 'retirement-issued'})
        # A slow or lost durable write cannot turn into a later input dispatch.
        self.owner();self.now();current=self.reader.clock_ms();fresh(epoch,current)
        if self.wanted!='inspect':fresh(self.base['frames'][-1]['packet']['capturedEpochMs'],current)
        if fence is not None and self.wanted!='inspect':fence.check()
        self.original_send(request)

    def query(self,operation):
        self.lock.assert_held();need(self.wanted is None and len(self.base['frames'])<MAX_FRAMES)
        self.wanted=operation;self.request=None
        try:
            value=self.reader.perform(self.capture.run,operation);need(self.request is not None)
            row={**deepcopy(self.request),'packet':deepcopy(value)}
            self.save(frames=self.base['frames']+[row]);self.now();return value
        finally:self.wanted=None;self.request=None

    def active(self,value):
        source=value['source'];need(self.base['activation'] is not None and source['scopePresent'] and not source['retired']
            and source['openedCommandId']==self.base['activation']['request']['commandId'])
        self.owner();self.capture.owner.activated(value);self.save(phase='active')

    def finished(self,value):
        result=deepcopy(value);self.owner();need(self.reader.guard() is not False)
        measured=self.now();epoch=self.reader.clock_ms();fresh(value['capturedEpochMs'],epoch)
        ended=self.now();need(epoch-value['capturedEpochMs']+math.ceil((ended-measured)*1000)<=1500)
        return result

    def activate(self):
        with self.lock.held():
            self.started=None;self.started=self.now();self.owner()
            need(self.base['phase'] in ('ready','activation-issued','active'))
            if self.base['phase']=='ready':
                before=self.query('inspect');source=before['source']
                need(not source['scopePresent'] and not source['retired'] and not source['openedCommandId'] and not source['retiredCommandId'])
                value=self.query('observe') # At most once in this durable lifetime.
            else:value=self.query('inspect') # Unknown mutation is never resent.
            self.active(value);return self.finished(value)

    def retire(self):
        with self.lock.held():
            self.started=None;self.started=self.now();self.owner()
            need(self.base['phase'] in ('active','retirement-issued','retired'))
            if self.base['phase']=='active':
                before=self.query('inspect');self.active(before)
                value=self.query('retire') # Original callback records before dispatch.
            for _ in range(2):
                value=self.query('inspect');source=value['source']
                need(source['retired'] and not source['scopePresent'] and source['openedCommandId']==self.base['activation']['request']['commandId']
                    and source['retiredCommandId']==self.base['retirement']['request']['commandId'])
            self.save(phase='retired');self.capture.owner.finish_lifetime(self,value);return self.finished(value)
