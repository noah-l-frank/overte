"""One ordinary bounded contact while the original Create editor owns input.

This owner implements the intercepted first world attempt only. It does not
pretend a synchronous complete W3C sequence leaves a contact held afterwards.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid
import re
from urllib.parse import quote
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.adapters.lifecycle_originals import IOSLifecycleSources,validate as editor_original
from ios.adapters.native_geometry import OriginalGeometry,validate as geometry_original
from ios.adapters import lifecycle_world as world


def gesture(packet,geometry,window,pointer):
    """Actual safe-content pad coordinates projected through UIKit originals."""
    world.original(packet);need(packet['iosLifecycleWorldVersion']>=2)
    pad=world.touch.pad(packet['source']['pad']);need(pad is not None and pad['fixed'] and not pad['moveValid'])
    # The editor may hide/disable the pad. Geometry still locates the same
    # ordinary forward attempt; UI routing and physics decide its actual effect.
    document,viewport=geometry_original(geometry,geometry['commandId'],native_epoch_ms=packet['clockAfter']['epochMs'])
    need(all(abs(document['window'][key]-value)<=1 for key,value in zip(('width','height'),pad['viewport'])))
    exact(window,{'x','y','width','height'})
    need(all(number(window[key],-10000,10000) for key in ('x','y'))
        and all(number(window[key],1,10000) for key in ('width','height'))
        and abs(window['width']-document['nativeUi']['surfaceWidth'])<=1
        and abs(window['height']-document['nativeUi']['surfaceHeight'])<=1)
    center=pad['center'];end=[center[0],center[1]-pad['radius']*.25]
    def screen(point):
        need(all(0<=n<limit for n,limit in zip(point,pad['viewport'])))
        return [round(window['x']+viewport['x']+point[0]*viewport['width']/pad['viewport'][0]),
                round(window['y']+viewport['y']+point[1]*viewport['height']/pad['viewport'][1])]
    start,finish=screen(center),screen(end)
    return dict(actions=[dict(type='pointer',id=pointer,parameters=dict(pointerType='touch'),actions=[
        dict(type='pointerMove',duration=0,origin='viewport',x=start[0],y=start[1]),dict(type='pointerDown',button=0),
        dict(type='pointerMove',duration=150,origin='viewport',x=finish[0],y=finish[1]),
        dict(type='pause',duration=300),dict(type='pointerUp',button=0)])])


def source_frame_original(frame,binding,run):
    need(type(frame) is dict and 'originals' in frame and 'clockJoin' in frame)
    raw=frame['originals'];joined=validate_join(frame['clockJoin'],raw);packet=raw['world'];world.original(packet)
    need(same(raw['worldClock'],dict(capturedEpochMs=packet['clockAfter']['epochMs'])))
    need(packet['runId']==run and str(packet['processId'])==binding['processIdentity']
         and joined['nativeBefore']['processId']==packet['processId']
         and joined['nativeBefore']['capturedEpochMs']<=packet['clockBefore']['epochMs']
         <=packet['clockAfter']['epochMs']<=joined['nativeAfter']['capturedEpochMs'])
    return packet



class LifecycleWorldAttempt:
    def __init__(self,store,history,sources,reader,geometry,ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(history,LifecycleEditorHistory)
             and isinstance(sources,IOSLifecycleSources) and isinstance(reader,world.IOSLifecycleWorld)
             and isinstance(geometry,OriginalGeometry) and isinstance(ui,NativeUI)
             and all(callable(fn) for fn in (epoch_ms,monotonic)))
        self.store,self.history,self.sources,self.reader,self.geometry,self.ui=store,history,sources,reader,geometry,ui
        self.binding,self.run=history.binding,history.run;self.epoch_ms,self.monotonic=epoch_ms,monotonic
        need(store.path==history.store.path.with_name('ios-lifecycle-world-attempt.json')
             and same(self.binding,sources.binding) and sources.run==self.run and str(reader.pid)==self.binding['processIdentity']
             and ui.base=='/session/'+quote(self.binding['sessionId'],safe=''))
        self.previous=store.read();self.state=dict(phase='new',before=None,after=None,preHistory=None,postStart=None,
            pointer='overte-lifecycle-'+uuid.uuid4().hex,body=None,ack=False,release='none',storage={})
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):self.history.check();need(same(self.store.read(),self.previous));return True

    def files(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound if live else lambda:True,
            self.storage if live else lambda *_:need(False),namespace='ios-lifecycle-world-proof',schema_prefix='iosLifecycleWorldProof')

    def frame(self,ref):return self.files().read(self.files().expand(ref))

    def envelope(self):return dict(iosLifecycleWorldAttemptVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state))

    def decode(self,value):
        exact(value,{'iosLifecycleWorldAttemptVersion','binding','runId','state'})
        need(type(value['iosLifecycleWorldAttemptVersion']) is int and value['iosLifecycleWorldAttemptVersion']==1
             and same(value['binding'],self.binding) and value['runId']==self.run)
        state=value['state'];exact(state,{'phase','before','after','preHistory','postStart','pointer','body','ack','release','storage'})
        need(state['phase'] in ('new','ready','issued','observed') and type(state['pointer']) is str
             and re.fullmatch('overte-lifecycle-[a-f0-9]{32}',state['pointer']) is not None and type(state['ack']) is bool
             and state['release'] in ('none','issued','returned') and type(state['storage']) is dict)
        previous=self.state;self.state=state
        try:
            for key,ref in state['storage'].items():need(key in ('1','2'));self.files().original(ref);need(ref['index']==int(key))
            if state['before'] is not None:
                need(state['before']['index']==1);self.prepared()
            else:need(state['phase']=='new' and state['body'] is None)
            if state['phase'] in ('ready','issued','observed'):need(state['before'] is not None and state['body'] is not None)
            if state['ack'] or state['release']!='none':need(state['phase'] in ('issued','observed'))
            if state['after'] is not None:need(state['after']['index']==2);self.effect()
            need((state['phase']=='observed')==(state['after'] is not None))
            if state['postStart'] is not None:need(state['phase'] in ('issued','observed') and integer(state['postStart'],1,len(self.history.state['frames'])))
        finally:self.state=previous
        return deepcopy(state)

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)

    def storage(self,kind,value):
        self.bound();need(kind=='original');self.files().original(value);key=str(value['index']);need(key in ('1','2'))
        old=self.state['storage'].get(key)
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(old[k],value[k]) for k in old if k not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        self.state['storage'][key]=deepcopy(value);self.save()

    def recover_frame(self,index):
        ref=self.state['storage'].get(str(index))
        if ref is None:return None
        need(ref['phase'] in ('opened','saved'));self.files().read(ref)
        if ref['phase']=='opened':ref=dict(ref,phase='saved');self.storage('original',ref)
        return self.files().compact(ref)

    def acquire(self,before):
        clock=NativeClockAcquisition(self.sources.source['clock_source'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(self.epoch_ms())
        if before:
            geometry=self.geometry.capture();packet=self.reader.read(self.run)
            raw=dict(world=packet,worldClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']),geometry=geometry,window=self.ui._request('GET','/window/rect'))
        else:
            packet=self.reader.read(self.run);raw=dict(world=packet,worldClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']))
        # The common join reads direct native fields. This is a verbatim alias
        # of the retained original clock, checked against that original below.
        join=clock.finish(raw,[('worldClock','capturedEpochMs')])
        return dict(originals=raw,clockJoin=join)

    def source_frame(self,frame):return source_frame_original(frame,self.binding,self.run)

    def prepared(self):
        frame=self.frame(self.state['before']);exact(frame,{'originals','clockJoin'})
        exact(frame['originals'],{'world','worldClock','geometry','window'});packet=self.source_frame(frame)
        need(self.state['preHistory'] is not None);index=self.state['preHistory']['index']
        need(integer(index,1,len(self.history.state['frames'])) and same(self.state['preHistory'],self.history.state['frames'][index-1]))
        value=self.history.read(index);facts=editor_original(value,self.binding,self.run)
        projected=self.history.historical_editor(index)
        need(projected['editor']=='create' and projected['generation']==1 and projected['focused'] and projected['keyboard']
             and facts['field']['textOwned'] and facts['field']['text']==projected['text'] and projected['text'].endswith(self.run)
             and any(ord(char)>127 for char in projected['text'])
             and facts['holder']['commit']=={} and packet['source']['touch']['active']==[])
        need(value['clockJoin']['nativeAfter']['capturedEpochMs']<=packet['clockBefore']['epochMs'])
        need(frame['clockJoin']['nativeBefore']['capturedEpochMs']<=frame['originals']['geometry']['observation']['sampleEpochMs']
             <=packet['clockBefore']['epochMs'])
        need(same(gesture(packet,frame['originals']['geometry'],frame['originals']['window'],self.state['pointer']),self.state['body']))
        world.measure(packet,packet);return frame

    def effect(self):
        frame=self.frame(self.state['after']);exact(frame,{'originals','clockJoin','history'})
        exact(frame['originals'],{'world','worldClock'});after=self.source_frame(frame);before=self.source_frame(self.prepared())
        contact=world.contact_attempt(before,after);facts=world.measure(before,after)
        need(contact['ended'] is not None and contact['terminal']=='released' and after['source']['touch']['active']==[] and facts['heldInputs']==[]
             and facts['worldDisplacement']<=.025 and all(n==0 for n in after['source']['drive']['raw']))
        events=after['source']['touch']['events'][len(before['source']['touch']['events']):]
        need(all(row['route'] in ('ui','captured') for row in events))
        origin=before['source']['pad']['center'];end=[origin[0],origin[1]-before['source']['pad']['radius']*.25]
        points=[point for event in events for point in event['points'] if point['id']==contact['contactId']]
        need(all(abs(a-b)<=1 for a,b in zip(points[0]['position'],origin))
             and all(abs(a-b)<=1 for a,b in zip(points[-1]['position'],end)))
        index=frame['history']['index'];need(integer(self.state['postStart'],1,len(self.history.state['frames']))
            and index==self.state['postStart']+1 and integer(index,1,len(self.history.state['frames']))
            and same(frame['history'],self.history.state['frames'][index-1]))
        old=self.history.read(self.state['preHistory']['index']);new=self.history.read(index);self.history.follows(old,new)
        a,b=editor_original(old,self.binding,self.run),editor_original(new,self.binding,self.run)
        need(same(a['field'],b['field']) and same(a['holder']['current'],b['holder']['current'])
             and a['keyboard']==b['keyboard'] and self.history.historical_editor(index)==self.history.historical_editor(self.state['preHistory']['index']))
        need(after['clockAfter']['epochMs']<=new['clockJoin']['nativeBefore']['capturedEpochMs'])
        return dict(contact=contact,facts=facts,editor=self.history.historical_editor(index))

    def release_save(self,phase):
        # Cleanup of the exact already-issued session must remain possible if
        # foreground/candidate continuity failed during POST. This CAS changes
        # only release responsibility, derives no native fact and admits no
        # new input. Original immutable state is the previously validated WAL.
        self.history.lock.assert_held();need(self.previous is not None and same(self.store.read(),self.previous))
        value=deepcopy(self.previous);state=value['state']
        need(state['phase'] in ('issued','observed') and same(value['binding'],self.binding) and value['runId']==self.run
             and (state['release'],phase) in (('none','issued'),('issued','returned')))
        state['release']=phase;self.store.write(value,self.previous);need(same(value,self.store.read()))
        self.previous=deepcopy(value);self.state=deepcopy(state)

    def release(self):
        self.history.lock.assert_held();need(self.previous is not None and same(self.store.read(),self.previous))
        need(self.previous['state']['phase'] in ('issued','observed'))
        if self.previous['state']['release']=='none':
            self.release_save('issued');self.ui.release_actions();self.release_save('returned')

    def act(self):
        self.bound()
        if self.state['phase']=='new':
            if self.state['preHistory'] is None:
                self.history.append(self.sources.sample(self.sources.epoch_ms()));self.state['preHistory']=deepcopy(self.history.state['frames'][-1]);self.save()
            ref=self.recover_frame(1)
            if ref is None:ref=self.files(True).write(1,self.acquire(True))
            self.state['before']=ref;frame=self.frame(ref)
            self.state['body']=gesture(frame['originals']['world'],frame['originals']['geometry'],frame['originals']['window'],self.state['pointer'])
            self.state['phase']='ready';self.save()
        if self.state['phase']=='ready':
            frame=self.prepared();join=frame['clockJoin'];self.ui._check()
            need(0<=self.epoch_ms()-join['hostBeforeEpochMs']<1500 and 0<=self.monotonic()-join['hostBeforeMonotonic']<1.5)
            fresh(frame['originals']['world']['clockAfter']['epochMs'],self.reader.clock_ms())
            self.state['phase']='issued';self.save()
            try:
                self.ui._check()
                need(0<=self.epoch_ms()-join['hostBeforeEpochMs']<1500 and 0<=self.monotonic()-join['hostBeforeMonotonic']<1.5)
                self.ui._request('POST','/actions',self.state['body']);self.state['ack']=True;self.save()
            finally:self.release()
        return self.observe()

    def observe(self):
        self.bound();need(self.state['phase'] in ('issued','observed'))
        if self.state['phase']=='observed':return self.effect() # Historical, without another input or sample.
        self.release()
        need(self.state['release']=='returned')
        if self.state['postStart'] is None:self.state['postStart']=len(self.history.state['frames']);self.save()
        ref=self.recover_frame(2)
        if ref is None:
            need(len(self.history.state['frames'])==self.state['postStart'])
            frame=self.acquire(False)
            self.history.append(self.sources.sample(self.sources.epoch_ms()));frame['history']=deepcopy(self.history.state['frames'][-1])
            ref=self.files(True).write(2,frame)
        self.state['after']=ref;self.state['phase']='observed';self.save();return self.effect()
