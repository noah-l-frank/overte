"""Owned ordinary Emote cancellation and chooser retirement, never a setter.

This closes only the current run's normal input surface. Scene, GPU, Script
and independently acquired peer retirement belong to the whole feature owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator
from adapters.script_feature.history import pack,unpack,same
from adapters.token_emote_ui import TokenEmoteUI,snapshot,same_reference
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.emote_ui_inventory import absent as absent_chooser

VERSION=1


class IOSEmoteCleanup:
    def __init__(self,store,sources,normal,*,validate_owned,validate_restored):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSEmoteSources)
            and sources.role=='primary' and not sources.historical and isinstance(normal,NativeUI)
            and all(callable(fn) for fn in (validate_owned,validate_restored)))
        self.store,self.sources,self.normal=store,sources,normal
        self.validate_owned,self.validate_restored=validate_owned,validate_restored
        self.recovery=IOSEmoteSourceRecovery(sources);sources.lock.assert_held()
        self.previous=store.read();self.state=dict(phase='closing',intents=[],last=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosEmoteCleanupInputsVersion=VERSION,runId=self.sources.run,binding=self.sources.binding,payload=pack([state]))

    def original(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(self.sources.frames)))
        from ios.adapters.emote_observation import IOSEmoteObservationDecoder
        return IOSEmoteObservationDecoder.retained(self.sources,reference)

    def reference(self):return dict(index=len(self.sources.frames),sha256=digest(self.sources.frames[-1]))

    def decode(self,value):
        exact(value,{'iosEmoteCleanupInputsVersion','runId','binding','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','intents','last'});need(state['phase'] in ('closing','closed') and type(state['intents']) is list and len(state['intents'])<=64)
        for index,row in enumerate(state['intents']):
            exact(row,{'kind','input','before','after'});need(row['kind'] in ('qt','sdk','release'))
            original=self.original(row['before'])
            if row['kind']=='qt':
                data=row['input'];exact(data,{'controlId','action','sequence','instance','generation','direction','original'})
                observed=snapshot(data['original']);same_reference(observed,original['ui'],data['controlId'])
                need(data['sequence']==observed['scope']['sequence']+1 and data['instance']==observed['scope']['instance']
                    and data['generation']==observed['scope']['generation'])
            elif row['kind']=='sdk':need(type(row['input']) is bool)
            else:need(row['input'] is None)
            if row['after'] is None:need(index==len(state['intents'])-1 and state['phase']=='closing')
            else:
                current=self.original(row['after']);need(row['after']['index']>row['before']['index'])
                if row['kind']!='release':self.consumed(row,current)
        if state['last'] is not None:self.original(state['last'])
        if state['phase']=='closed':need(state['last'] is not None and state['intents'] and state['intents'][-1]['kind']=='release')
        return deepcopy(state)

    def bound(self):self.sources.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def capture(self):
        self.recovery.recover();frame=self.sources.read();self.recovery.follow(frame)
        reference=self.reference();self.state['last']=reference;self.save();return frame,reference

    @staticmethod
    def consumed(row,current):
        if row['kind']=='sdk':need(current['ui']['open']==row['input']);return
        need(row['kind']=='qt');original=snapshot(row['input']['original']);after=snapshot(current['ui'])
        a,b=original['scope'],after['scope'];need(all(a[key]==b[key] for key in ('instance','generation','processId'))
            and b['sourceSequence']>a['sourceSequence'] and b['sequence']==row['input']['sequence']
            and b['elapsedMs']>=a['elapsedMs'] and b['capturedEpochMs']>=a['capturedEpochMs'])

    def resolve(self):
        self.bound()
        if not self.state['intents'] or self.state['intents'][-1]['after'] is not None:return True
        row=self.state['intents'][-1]
        # There is no original source for an uncertain WebDriver pointer
        # release; do not silently replay it or declare that lease retired.
        need(row['kind']!='release')
        current,reference=self.capture();self.consumed(row,current);row['after']=reference;self.save();return True

    def intent(self,value):
        self.bound();need(not self.state['intents'] or self.state['intents'][-1]['after'] is not None)
        frame,reference=self.capture();same_reference(value['original'],frame['ui'],value['controlId'])
        # Source-owned token equality includes the native sequence. A later
        # unknown command can neither replace this intent nor settle it.
        self.state['intents'].append(dict(kind='qt',input=deepcopy(value),before=reference,after=None));self.save()

    def receipt(self,value):
        self.bound();row=self.state['intents'][-1];need(row['kind']=='qt' and row['after'] is None and same(row['input'],value['intent']))
        frame,reference=self.capture();self.consumed(row,frame)
        # The receipt is delivery evidence only; functional restoration is
        # evaluated independently from the actual original Rig source below.
        row['after']=reference;self.save()

    def tablet(self,opened):
        frame,reference=self.capture()
        if frame['ui']['open']==opened:return
        need(len(self.state['intents'])<64)
        row=dict(kind='sdk',input=opened,before=reference,after=None);self.state['intents'].append(row);self.save()
        self.normal.click(Locator('accessibility id','OverteTabletOpen' if opened else 'OverteTabletClose'))
        current,reference=self.capture();self.consumed(row,current);row['after']=reference;self.save()

    def close(self):
        self.bound()
        if self.state['phase']=='closed':return {'performed':True}
        self.resolve();frame,_ref=self.capture()
        need(frame['phaseAfter']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        need(self.validate_owned(frame) is not False)
        ui=TokenEmoteUI(self.sources.readers['ui'],self.intent,receipt=self.receipt,
            monotonic=self.sources.monotonic,sleep=self.normal.sleep)
        if frame['group']['native']['animation']['overrideActive']:
            self.tablet(True);ui.open();ui.cancel()
        frame,_ref=self.capture();need(self.validate_restored(frame) is not False
            and frame['group']['native']['animation']['overrideActive'] is False)
        # A hidden chooser can still retain its real QML instance. Reopen the
        # owned tablet, use its ordinary Home navigation and observe absence.
        if not absent_chooser(frame['widgets']):self.tablet(True);ui.close()
        self.tablet(False);frame,_ref=self.capture()
        need(not frame['widgets']['tabletShown'] and absent_chooser(frame['widgets']) and self.validate_restored(frame) is not False)
        need(len(self.state['intents'])<64)
        row=dict(kind='release',input=None,before=self.reference(),after=None);self.state['intents'].append(row);self.save()
        self.normal.release_actions();current,reference=self.capture()
        need(not current['widgets']['tabletShown'] and absent_chooser(current['widgets']) and self.validate_restored(current) is not False)
        row['after']=reference;self.state.update(phase='closed',last=reference);self.save();return {'performed':True}
