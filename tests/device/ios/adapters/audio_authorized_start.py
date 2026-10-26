"""One ordinary recording Start gated by retained current OS authorization.

Permission denial before input can acquire a genuinely new decision later.
An existing Record intent is never resent, including after a lost SDK return.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.assets_file_sources import private_original
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_authorization_sources import AudioAuthorizationSources
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner


class DeliveryIO:
    def __init__(self,owner,original):self.owner,self.base,self.original=owner,original,original.original
    def capture(self):return self.base.capture()
    def scroll(self,*args,**kwargs):return self.base.scroll(*args,**kwargs)
    def activate(self,identifier,*,token):
        if identifier!='audio.record':return self.base.activate(identifier,token=token)
        with scope(self.owner.delivery_guard):return self.base.activate(identifier,token=token)


class AudioAuthorizedStarts:
    def __init__(self,store,parent,sources):
        need(isinstance(store,PrivateFeatureState) and isinstance(parent,IOSAudioRecordedOwner)
            and isinstance(sources,AudioAuthorizationSources) and not parent.historical and sources.parent is parent
            and not sources.historical
            and store.path==parent.store.path.with_name('ios-audio-authorized-starts.json'))
        self.store,self.parent,self.sources=store,parent,sources
        self.binding,self.run=deepcopy(parent.binding),parent.run
        self.monotonic,self.epoch_ms=parent.monotonic,parent.epoch_ms
        self.historical=False;self.active=False;self.previous=store.read();self.state=dict(entries=[])
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def archive(cls,store,parent,sources):
        need(isinstance(parent,IOSAudioRecordedOwner) and parent.historical and isinstance(sources,AudioAuthorizationSources)
            and sources.historical and sources.parent is parent and store.path==parent.store.path.with_name('ios-audio-authorized-starts.json'))
        owner=object.__new__(cls);owner.store,owner.parent,owner.sources=store,parent,sources
        owner.binding,owner.run=deepcopy(parent.binding),parent.run;owner.monotonic=parent.monotonic
        owner.historical=True;owner.active=False;owner.previous=store.read();need(owner.previous is not None)
        owner.state=owner.decode(owner.previous);return owner

    def bound(self):
        self.parent.bound();self.sources.bound();need(same(self.store.read(),self.previous))
        if self.active:need(self.parent.ui is self._ui and self._ui.io is self._proxy and self._ui.intent is self._handler)
        return True

    def envelope(self):return dict(iosAudioAuthorizedStartsVersion=1,binding=self.binding,runId=self.run,payload=pack([self.state]))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def parent_operation(self,ticket):
        rows=self.parent.state['operations']+([] if self.parent.state['pending'] is None else [self.parent.state['pending']])
        found=[row for row in rows if row['ticket']==ticket];need(len(found)<=1)
        if found:need(found[0]['verb']=='record-start')
        return found[0] if found else None

    @staticmethod
    def permission(frame):
        source=frame['originals']['session']['source']
        return ('granted' if source['osPermission']==1 else 'denied') if source['available'] and source['osPermission'] in (1,2) else 'unknown'

    @staticmethod
    def eligible(frame,checked):
        exact(checked,{'epochMs','monotonic'});need(number(checked['epochMs'],1,1e15) and number(checked['monotonic'],0,1e15))
        join=frame['clockJoin'];need(checked['epochMs']>=join['hostAfterEpochMs'] and checked['monotonic']>=join['hostAfterMonotonic'])
        utc=checked['epochMs']-join['hostBeforeEpochMs'];mono=(checked['monotonic']-join['hostBeforeMonotonic'])*1000
        return 0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250

    def decode(self,value):
        exact(value,{'iosAudioAuthorizedStartsVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(type(value['iosAudioAuthorizedStartsVersion']) is int and value['iosAudioAuthorizedStartsVersion']==1 and len(rows)==1
            and same(value['binding'],self.binding) and value['runId']==self.run)
        state=rows[0];exact(state,{'entries'});need(type(state['entries']) is list and len(state['entries'])<=8);seen=set()
        for entry in state['entries']:
            exact(entry,{'ticket','phase','attempts','input','startedBy','after'})
            identifier(entry['ticket']);need(entry['ticket'] not in seen);seen.add(entry['ticket'])
            need(entry['phase'] in ('reserved','checking','denied','grant-recorded','record-intent','parent-complete','blocked-after','complete')
                and type(entry['attempts']) is list and len(entry['attempts'])<=8)
            operation=self.parent_operation(entry['ticket'])
            for attempt in entry['attempts']:
                exact(attempt,{'before','permission','decision','checked'});need(attempt['before'] in self.sources.state['frames'])
                frame=self.sources.frame(attempt['before']);permission=self.permission(frame)
                need(frame['ticket']==entry['ticket'] and frame['stage']=='before-start' and attempt['permission']==permission)
                eligible=self.eligible(frame,attempt['checked'])
                decision=permission if permission!='granted' else 'granted' if eligible else 'expired'
                need(attempt['decision']==decision)
            if entry['phase'] in ('grant-recorded','record-intent','parent-complete','complete'):
                need(entry['attempts'] and entry['attempts'][-1]['decision']=='granted')
            if entry['phase']=='denied':need(entry['attempts'] and entry['attempts'][-1]['decision']!='granted')
            if entry['input'] is not None:
                item=entry['input'];exact(item,{'index','row'})
                need(operation is not None and type(item['index']) is int and 0<=item['index']<len(operation['inputs'])
                    and same(item['row'],operation['inputs'][item['index']]) and item['row']['verb']=='record-start'
                    and entry['attempts'] and entry['attempts'][-1]['decision']=='granted')
            if entry['phase'] in ('record-intent','parent-complete','blocked-after','complete'):need(entry['input'] is not None)
            if entry['startedBy'] is not None:
                need(operation is not None and same(entry['startedBy'],operation['after']) and entry['input'] is not None)
                self.effect(entry)
            if entry['after'] is not None:
                need(entry['after'] in self.sources.state['frames'] and entry['startedBy'] is not None)
                after=self.sources.frame(entry['after']);need(after['ticket']==entry['ticket'] and after['stage']=='after-start' and after['parent']==entry['startedBy'])
                if entry['phase']=='complete':need(self.permission(after)=='granted')
                if entry['phase']=='blocked-after':need(self.permission(after)!='granted')
            if entry['phase'] in ('complete','blocked-after'):need(entry['after'] is not None and entry['startedBy'] is not None)
        return deepcopy(state)

    def effect(self,entry):
        operation=self.parent_operation(entry['ticket']);need(operation is not None and entry['startedBy'] is not None)
        observed=self.parent.original(entry['startedBy']);actual=self.parent.effect(operation,observed)
        grant=self.sources.frame(entry['attempts'][-1]['before']);event=observed['originals']['native']['audio']['recordedVoice']['events'][0]
        delta=event['publishedEpochMs']-grant['originals']['session']['clockBefore']['epochMs'];need(0<=delta<1500)
        return actual

    def sample(self,entry,stage,reference):
        if self.sources.state['pending'] is not None:
            pending=self.sources.state['pending'];need(pending['ticket']==entry['ticket'] and pending['stage']==stage and pending['parent']==reference)
            return self.sources.recover_capture()
        used=[attempt['before']['index'] for attempt in entry['attempts']]+([] if entry['after'] is None else [entry['after']['index']])
        if self.sources.state['frames']:
            candidate=self.sources.state['frames'][-1];frame=self.sources.frame(candidate)
            if candidate['index']>max(used,default=0) and frame['ticket']==entry['ticket'] and frame['stage']==stage and frame['parent']==reference:return candidate
        return self.sources.capture(entry['ticket'],stage,reference)

    def before_intent(self,verb,value,control):
        if verb!='record-start':return self._original_intent(verb,value,control)
        self.bound();entry=self._entry;operation=self.parent_operation(entry['ticket'])
        need(operation is self.parent.state['pending'] and not any(row['verb']=='record-start' for row in operation['inputs']) and len(entry['attempts'])<8)
        entry['phase']='checking';self.save();reference=self.sample(entry,'before-start',operation['before']);frame=self.sources.frame(reference)
        checked=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic());permission=self.permission(frame)
        decision=permission if permission!='granted' else 'granted' if self.eligible(frame,checked) else 'expired'
        entry['attempts'].append(dict(before=reference,permission=permission,decision=decision,checked=checked))
        entry['phase']='grant-recorded' if decision=='granted' else 'denied';self.save()
        if decision!='granted':raise NativeUIError('A fresh definite OS microphone grant is required before Record input')
        self._original_intent(verb,value,control);entry['input']=dict(index=len(operation['inputs'])-1,row=deepcopy(operation['inputs'][-1]))
        entry['phase']='record-intent';self.save();self._grant_frame=frame
        self._grant_sources=deepcopy(self.sources.previous);self._grant_owner=deepcopy(self.previous)
        self._pins=[(self.sources.frames.path(self.sources.frames.expand(reference)),reference)]
        self._pins.extend((self.sources.raws.store.path(self.sources.raws.store.expand(ref)),ref) for ref in frame['rawRefs'])

    def delivery_guard(self):
        # This guard runs inside the existing SDK final-transport scope. It
        # must perform only host/immutable-file checks, never SDK/native reads.
        need(self.active and self.parent.ui is self._ui and self._ui.io is self._proxy and self._ui.intent is self._handler
            and same(self.store.read(),self._grant_owner) and same(self.previous,self._grant_owner)
            and same(self.sources.store.read(),self._grant_sources) and same(self.sources.previous,self._grant_sources))
        entry=self._entry;operation=self.parent_operation(entry['ticket']);item=entry['input']
        need(operation is self.parent.state['pending'] and item is not None and same(operation['inputs'][item['index']],item['row'])
            and same(self.parent.store.read(),self.parent.previous))
        need(self.eligible(self._grant_frame,dict(epochMs=self.epoch_ms(),monotonic=self.monotonic())))
        for path,reference in self._pins:
            raw,identity=private_original(path,reference['bytes'])
            need(identity['device']==reference['device'] and identity['inode']==reference['inode'] and len(raw)==reference['bytes']
                and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        return True

    @operation
    def act(self,ticket):
        need(not self.historical and not self.active);self.bound();identifier(ticket)
        entry=next((row for row in self.state['entries'] if row['ticket']==ticket),None)
        if entry is None:
            need(len(self.state['entries'])<8 and self.parent_operation(ticket) is None)
            entry=dict(ticket=ticket,phase='reserved',attempts=[],input=None,startedBy=None,after=None);self.state['entries'].append(entry);self.save()
        if entry['phase']=='blocked-after':raise NativeUIError('The original post-Start authorization remains unqualified')
        if entry['phase']=='complete':return self.result(entry)
        self._entry=entry;self._ui=self.parent.ui;self._original_io=self._ui.io;self._original_intent=self._ui.intent
        need(getattr(self._original_intent,'__self__',None) is self.parent
            and getattr(self._original_intent,'__func__',None) is IOSAudioRecordedOwner.input_intent)
        self._proxy=DeliveryIO(self,self._original_io)
        def handler(verb,value,control):return self.before_intent(verb,value,control)
        self._handler=handler;self._ui.io,self._ui.intent=self._proxy,handler;self.active=True
        try:
            parent=self.parent_operation(ticket)
            if parent is not None and parent['after'] is None and not any(row['verb']=='record-start' for row in parent['inputs']):
                self.parent.ui.start();self.parent.resolve()
            elif parent is None:self.parent.act(ticket,'record-start')
            elif parent['after'] is None:
                inputs=[(index,row) for index,row in enumerate(parent['inputs']) if row['verb']=='record-start'];need(len(inputs)==1)
                if entry['input'] is None:entry['input']=dict(index=inputs[0][0],row=deepcopy(inputs[0][1]));entry['phase']='record-intent';self.save()
                self.parent.resolve()
            parent=self.parent_operation(ticket);need(parent is not None and parent['after'] is not None)
            entry['startedBy']=deepcopy(parent['after']);entry['phase']='parent-complete';self.effect(entry);self.save()
            entry['after']=self.sample(entry,'after-start',entry['startedBy']);after=self.sources.frame(entry['after'])
            entry['phase']='complete' if self.permission(after)=='granted' else 'blocked-after';self.save()
            if entry['phase']!='complete':raise NativeUIError('Actual OS microphone permission changed after the owned Start')
            return self.result(entry)
        finally:
            self._ui.io,self._ui.intent=self._original_io,self._original_intent;self.active=False

    def result(self,entry):
        self.bound();need(entry['phase']=='complete');return dict(performed=True,historical=True,original=deepcopy(entry['startedBy']),
            authorizationBefore=deepcopy(entry['attempts'][-1]['before']),authorizationAfter=deepcopy(entry['after']),state=self.effect(entry))
