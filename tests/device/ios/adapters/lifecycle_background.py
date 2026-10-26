"""One-send Chat background/resume with original OS and editor evidence.

No native/UI reads are made while backgrounded. This component does not retire
the Lifecycle run, restore the world or establish Actor/image acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.installed_code import InstalledCodeBinding,source as process_source
from ios.adapters.snapshot_photos_context import PhotosClientContext
from ios.adapters.tablet_web_admission import installed_forward
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.adapters import lifecycle_originals as originals


def os_original(value,binding,bundle):
    exact(value,{'iosLifecycleOSVersion','binding','process','source','installed','appState','hostBefore','hostAfter'})
    need(type(value['iosLifecycleOSVersion']) is int and value['iosLifecycleOSVersion']==1 and same(context(value['binding']),binding))
    for stamp in (value['hostBefore'],value['hostAfter']):
        exact(stamp,{'epochMs','monotonic'});need(number(stamp['epochMs'],1,1e15) and number(stamp['monotonic'],0,1e15))
    a,b=value['hostBefore'],value['hostAfter'];utc=b['epochMs']-a['epochMs'];mono=(b['monotonic']-a['monotonic'])*1000
    need(0<=utc<5000 and 0<=mono<5000 and abs(utc-mono)<=250)
    actual=value['process'];exact(actual,{'bundleId','pid','foreground'})
    need(actual['bundleId']==bundle['bundleId'] and type(actual['pid']) is int and str(actual['pid'])==binding['processIdentity']
         and type(actual['foreground']) is bool and type(value['appState']) is int and value['appState'] in (2,3,4)
         and actual['foreground']==(value['appState']==4));process_source(value['source'])
    class Frozen(PrivateFeatureState):
        def read(self):return deepcopy(value['installed'])
        def write(self,*_args,**_kwargs):need(False)
    forbidden=lambda *_args,**_kwargs:need(False)
    scope={key:binding[key] for key in binding if key!='processIdentity'}
    record=InstalledCodeBinding(Frozen('/unused-lifecycle-os-original'),scope,bundle,forbidden,forbidden,forbidden).record()
    need(record is not None and record['phase']=='bound' and record['process']['pid']==actual['pid']
         and same(record['source'],value['source']));return value


class LifecycleOSContext(PhotosClientContext):
    """Reuse the existing strict background-safe SDK/process/source context."""
    def status(self,epoch_ms,monotonic):
        before=dict(epochMs=epoch_ms(),monotonic=monotonic());first=self.probe()
        state=self.runtime.adapter.query_app_state(self.client,self.session,self.target);last=self.probe()
        need(same(first['process'],last['process']) and same(first['source'],last['source']))
        value=dict(iosLifecycleOSVersion=1,binding=deepcopy(self.binding),process=last['process'],source=last['source'],
            installed=last['installed'],appState=state,hostBefore=before,hostAfter=dict(epochMs=epoch_ms(),monotonic=monotonic()))
        os_original(value,self.binding,self.gate.bundle);return value

    def background(self):
        self.probe(True);return self.client.execute(self.session,'mobile: backgroundApp',dict(seconds=-1))


class LifecycleBackground:
    def __init__(self,store,history_store,os_context,run,lock,source_factory,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(history_store,PrivateFeatureState)
             and isinstance(os_context,LifecycleOSContext) and isinstance(lock,ScriptSourceLock)
             and all(callable(f) for f in (source_factory,epoch_ms,monotonic,sleep)))
        need(store.path==history_store.path.with_name('ios-lifecycle-background.json')
             and history_store.path.name=='lifecycle-editor-owner.json' and lock.path==store.path.parent/'script-feature-sources.lock')
        self.store,self.history_store,self.os,self.lock=store,history_store,os_context,lock
        self.binding,self.run=deepcopy(context(os_context.binding)),identifier(run)
        self.source_factory,self.epoch_ms,self.monotonic,self.sleep=source_factory,epoch_ms,monotonic,sleep
        self.started=self.last_clock=None;self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state=None):
        return dict(iosLifecycleBackgroundVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state if state is None else state))

    def history_forward(self,current):
        if self.state is None:return
        before=self.state['history'];exact(current,set(before));need(all(same(current[key],before[key]) for key in before if key!='state'))
        a,b=before['state'],current['state'];exact(b,set(a));need(same(a['baseline'],b['baseline']))
        if self.state['phase']=='observed':
            count=len(a['frames']);need(len(b['frames'])>=count+1 and same(a['frames'],b['frames'][:count])
                and same(a['aliases'],b['aliases'][:len(a['aliases'])]) and same(b['frames'][count],self.state['afterReference']));return
        need(same(a['aliases'],b['aliases']))
        if self.state['phase'] in ('background-issued','background-observed'):need(same(before,current));return
        count=len(a['frames']);need(count<=len(b['frames'])<=count+1 and same(a['frames'],b['frames'][:count]))
        if len(b['frames'])==count+1:need(b['original'] is None)
        elif b['original'] is not None:need(b['original']['index']==count+1)

    def file_guard(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        self.os.runtime.adapter._candidate_guard()
        need(same(self.os.runtime.adapter.read_session(self.os.selector),self.os.session_state))
        self.history_forward(self.history_store.read());return True

    def bound(self):
        self.file_guard();now=self.monotonic();need(number(now,0,1e15)
            and (self.last_clock is None or now>=self.last_clock) and (self.started is None or 0<=now-self.started<30))
        self.last_clock=now

    def history(self):
        return LifecycleEditorHistory(self.history_store,self.binding,self.run,self.lock,self.file_guard)

    def decode(self,value):
        exact(value,{'iosLifecycleBackgroundVersion','binding','runId','state'});state=value['state']
        need(type(value['iosLifecycleBackgroundVersion']) is int and value['iosLifecycleBackgroundVersion']==1 and same(value,self.envelope(state)))
        exact(state,{'phase','before','after','afterReference','history','osBefore','background','foreground'})
        need(state['phase'] in ('background-issued','background-observed','foreground-issued','observed')
             and integer(state['before'],1) and state['before']==len(state['history']['state']['frames']))
        os_original(state['osBefore'],self.binding,self.os.gate.bundle);need(state['osBefore']['process']['foreground'])
        for key,foreground in (('background',False),('foreground',True)):
            if state[key] is not None:
                os_original(state[key],self.binding,self.os.gate.bundle);need(state[key]['process']['foreground']==foreground)
                installed_forward(state['osBefore']['installed'],state[key]['installed'])
                need(same(state['osBefore']['source'],state[key]['source']) and state[key]['hostBefore']['monotonic']>=state['osBefore']['hostAfter']['monotonic']
                     and state[key]['hostBefore']['epochMs']>=state['osBefore']['hostAfter']['epochMs'])
        if state['phase']!='background-issued':need(state['background'] is not None)
        if state['foreground'] is not None:need(state['background'] is not None and state['foreground']['hostBefore']['monotonic']>=state['background']['hostAfter']['monotonic']
            and state['foreground']['hostBefore']['epochMs']>=state['background']['hostAfter']['epochMs'])
        if state['after'] is not None:need(type(state['after']) is int and state['after']==state['before']+1
            and state['foreground'] is not None and type(state['afterReference']) is dict)
        else:need(state['afterReference'] is None)
        if state['phase']=='observed':need(state['after'] is not None)
        previous=self.state;self.state=state
        try:
            history=self.history();before=history.read(state['before']);self.before(before,history)
            if state['after'] is not None:
                need(same(state['afterReference'],history.state['frames'][state['after']-1]))
                self.completed(before,history.read(state['after']),history)
        finally:self.state=previous
        return deepcopy(state)

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)

    def before(self,value,history):
        index=self.state['before'] if self.state is not None else len(history.state['frames'])
        projected=history.historical_editor(index)
        actual=originals.validate(value,self.binding,self.run)['field']
        aliases=[row for row in history.state['aliases'] if row['after']<=index]
        need(len(aliases)==2 and projected==dict(editor='chat',text='reply-'+self.run,focused=True,generation=2,keyboard=True)
             and actual is not None and actual['textOwned'])

    def completed(self,before,after,history):
        history.follows(before,after);a=originals.validate(before,self.binding,self.run);b=originals.validate(after,self.binding,self.run)
        need(a['field'] is not None and b['field'] is not None and same(a['field']['identity'],b['field']['identity'])
             and b['field']['text']==a['field']['text']=='reply-'+self.run and b['field']['textOwned']
             and not b['field']['focused'] and not b['keyboard']['keyboard'])
        first,last=before['clockJoin']['nativeAfter']['lifecycle'],after['clockJoin']['nativeBefore']['lifecycle']
        need(last['backgrounds']>=first['backgrounds']+1 and last['activations']>=first['activations']+1 and last['launches']==first['launches']
             and before['originals']['ui']['lastSequence']==after['originals']['ui']['lastSequence'])
        need(history.historical_editor(self.state['after'])['generation']==2)

    def status(self):
        self.bound();value=self.os.status(self.epoch_ms,self.monotonic);self.bound();return value

    def wait(self,foreground):
        started=self.monotonic()
        for index in range(51):
            value=self.status()
            if value['process']['foreground']==foreground:return value
            if self.monotonic()-started>=5 or index==50:break
            self.sleep(.1)
        need(False)

    def act(self):
        self.started=self.monotonic();self.bound()
        if self.state is None:
            need(self.status()['process']['foreground']);history=self.history();need(history.state['original'] is None)
            self.before(history.read(len(history.state['frames'])),history)
            source=self.source_factory();need(same(source.binding,self.binding) and source.run==self.run)
            index=history.append(source.sample(self.epoch_ms()));self.before(history.read(index),history)
            status=self.status();need(status['process']['foreground'])
            self.state=dict(phase='background-issued',before=index,after=None,afterReference=None,history=deepcopy(history.store.read()),osBefore=status,background=None,foreground=None)
            self.save();self.os.background();self.bound()
        if self.state['phase']=='background-issued':
            self.state.update(phase='background-observed',background=self.wait(False));self.save()
        if self.state['phase']=='background-observed':
            need(not self.status()['process']['foreground']);self.state['phase']='foreground-issued';self.save()
            self.os.activate();self.bound()
        if self.state['phase'] in ('foreground-issued','observed'):
            foreground=self.wait(True)
            if self.state['foreground'] is None:self.state['foreground']=foreground;self.save()
            history=self.history()
            if self.state['after'] is None:
                if len(history.state['frames'])==self.state['before']:
                    if history.state['original'] is not None:index=history.recover_original()
                    else:
                        source=self.source_factory();need(same(source.binding,self.binding) and source.run==self.run)
                        index=history.append(source.sample(self.epoch_ms()))
                else:index=len(history.state['frames'])
                need(index==self.state['before']+1);self.state['after']=index
                self.state['afterReference']=deepcopy(history.state['frames'][index-1])
                try:self.completed(history.read(self.state['before']),history.read(index),history)
                except BaseException:self.state['after']=None;self.state['afterReference']=None;raise
                self.state['phase']='observed';self.save()
            self.completed(history.read(self.state['before']),history.read(self.state['after']),history)
        self.bound();return dict(originalBefore=self.state['before'],originalAfter=self.state['after'],historical=True,
            independentActorRequired=True,imageRequired=True,wholeFeatureRequired=True)
