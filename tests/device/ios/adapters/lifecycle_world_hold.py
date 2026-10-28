"""Original intercepted attempt, then one owned held-world contact.

An already authenticated touch context is required explicitly. No service,
selector repair or session creation exists here. Host release/context return
and independently observed native release/quiet are separate responsibilities.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import asyncio
import inspect
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters import lifecycle_world as world
from ios.adapters.lifecycle_originals import validate as editor_original
from ios.adapters.lifecycle_world_attempt import LifecycleWorldAttempt,gesture
from ios.adapters.touch import validate_actions
from ios.adapters.touch_lease import TouchLease

VERSION=1
STATE_KEYS={'phase','attempt','editor','path','seconds','frames','held','released','quiet','storage'}


def coordinates(frame):
    raw=frame['originals'];body=gesture(raw['world'],raw['geometry'],raw['window'],'owned-world-hold')
    actions=body['actions'][0]['actions'];start,end=actions[0],actions[2]
    return dict(window=dict(width=raw['window']['width'],height=raw['window']['height']),
                start=[start['x'],start['y']],end=[end['x'],end['y']])


class _MotionContext:
    """One retained actual context/HID, with the complete path already durable."""
    def __init__(self,factory,start,end,check,*,before_down=None):
        self.factory,self.start,self.end,self.check=factory,tuple(start),tuple(end),check
        need(before_down is None or callable(before_down));self.before_down=before_down
        self.actual=None;self.hid=None;self.sent=False;self._actual_exit=None
    async def __aenter__(self):
        start,end,check,before_down=self.start,self.end,self.check,self.before_down
        actual=self.factory();self.actual=actual;self._actual_exit=actual.__aexit__
        hid=await actual.__aenter__();self.hid=hid
        class Motion:
            async def send_touchscreen(_self,state,x,y):
                need((x,y)==start)
                if state==0xC2:
                    need(not self.sent);self.sent=True
                    if before_down is not None:
                        result=before_down();need(not inspect.isawaitable(result) and result is not False)
                    await hid.send_touchscreen(state,*start)
                    result=check()
                    if inspect.isawaitable(result):result=await result
                    need(result is not False)
                    await hid.send_touchscreen(state,*end)
                else:
                    need(state==0x02)
                    await hid.send_touchscreen(state,*start)
        return Motion()
    async def __aexit__(self,*arguments):
        exit_callback=self._actual_exit;need(exit_callback is not None)
        return await exit_callback(*arguments)


class LifecycleWorldHold:
    def __init__(self,store,attempt,session_factory):
        need(isinstance(store,PrivateFeatureState) and type(attempt) is LifecycleWorldAttempt and callable(session_factory))
        self.store,self.attempt,self.factory=store,attempt,session_factory
        self.history,self.sources,self.reader,self.geometry,self.ui=attempt.history,attempt.sources,attempt.reader,attempt.geometry,attempt.ui
        self.binding,self.run=self.history.binding,self.history.run
        need(store.path==self.history.store.path.with_name('ios-lifecycle-world-hold.json'))
        self.epoch_ms,self.monotonic=attempt.epoch_ms,attempt.monotonic
        self.previous=store.read();self.state=dict(phase='new',attempt=None,editor=None,path=None,seconds=None,frames=[],held=None,released=None,quiet=[],storage={})
        self.lease=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):
        self.history.check();need(self.sources.source['check']() is not False and same(self.store.read(),self.previous));return True
    def file_guard(self):
        self.history.lock.assert_held();need(same(self.store.read(),self.previous));return True
    def files(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound if live else self.file_guard,
            self.storage if live else lambda *_:need(False),namespace='ios-lifecycle-world-hold-proof',schema_prefix='iosLifecycleWorldHoldProof')
    def frame(self,index):
        need(integer(index,1,len(self.state['frames'])))
        return self.files().read(self.files().expand(self.state['frames'][index-1]))
    def source_frame(self,frame,*,before=False):
        exact(frame,{'originals','clockJoin'})
        exact(frame['originals'],{'world','worldClock'}|({'geometry','window'} if before else set()))
        packet=self.attempt.source_frame(frame)
        if before:
            need(frame['clockJoin']['nativeBefore']['capturedEpochMs']<=frame['originals']['geometry']['observation']['sampleEpochMs']
                 <=packet['clockBefore']['epochMs'])
        return packet
    def packet(self,index):return self.source_frame(self.frame(index),before=index==1)
    def envelope(self):return dict(iosLifecycleWorldHoldVersion=VERSION,binding=self.binding,runId=self.run,state=deepcopy(self.state))
    def decode(self,value):
        exact(value,{'iosLifecycleWorldHoldVersion','binding','runId','state'})
        need(type(value['iosLifecycleWorldHoldVersion']) is int and value['iosLifecycleWorldHoldVersion']==VERSION
             and same(value['binding'],self.binding) and value['runId']==self.run)
        state=value['state'];exact(state,STATE_KEYS);old=self.state;self.state=state
        try:
            need(state['phase'] in ('new','prepared','issued','held','released','quiet') and type(state['frames']) is list
                 and len(state['frames'])<=32 and type(state['storage']) is dict and type(state['quiet']) is list)
            for key,ref in state['storage'].items():
                need(type(key) is str and key.isdigit() and key==str(int(key)) and integer(int(key),1,32));self.files().original(ref);need(ref['index']==int(key))
            for index,ref in enumerate(state['frames'],1):
                need(ref['index']==index);self.files().expand(ref);self.packet(index)
            if state['phase']!='new':self.prepared()
            if state['phase']=='held':need(state['held'] is not None)
            if state['phase'] in ('released','quiet'):need(state['released'] is not None)
            if state['held'] is not None:
                need(integer(state['held'],2,len(state['frames'])));self.held_proof(state['held'])
            if state['released'] is not None:self.release_proof()
            if state['quiet']:
                need(state['released'] is not None and all(integer(i,state['released']+1,len(state['frames'])) for i in state['quiet'])
                     and state['quiet']==sorted(set(state['quiet'])))
                for index in state['quiet']:self.quiet_packet(index)
            if state['phase']=='quiet':self.proof()
        finally:self.state=old
        return deepcopy(state)
    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)
    def storage(self,kind,value):
        self.bound();need(kind=='original');self.files().original(value);key=str(value['index']);old=self.state['storage'].get(key)
        need(value['index']==len(self.state['frames'])+1)
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(old[k],value[k]) for k in old if k not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        self.state['storage'][key]=deepcopy(value);self.save()
    def capture(self,before=False):
        need(len(self.state['frames'])<32)
        index=len(self.state['frames'])+1;pending=self.state['storage'].get(str(index))
        if pending is not None:
            need(pending['phase'] in ('opened','saved'));self.files().read(pending)
            if pending['phase']=='opened':self.storage('original',dict(pending,phase='saved'))
            ref=self.files().compact(self.state['storage'][str(index)])
        else:ref=self.files(True).write(index,LifecycleWorldAttempt.acquire(self,before))
        self.state['frames'].append(ref);self.save();return index
    def prepared(self):
        need(self.state['attempt'] is not None and same(self.attempt.store.read(),self.attempt.previous)
             and digest(self.attempt.previous)==self.state['attempt'] and self.attempt.state['phase']=='observed')
        self.attempt.effect()
        index=self.state['editor'];need(integer(index,1,len(self.history.state['frames'])))
        facts=editor_original(self.history.read(index),self.binding,self.run)
        need(facts['field'] is None and not facts['keyboard']['keyboard'] and not facts['holder']['commit']
             and not facts['holder']['resources']['pendingRuns'])
        before=self.frame(1);packet=self.source_frame(before,before=True)
        need(packet['source']['touch']['active']==[] and not packet['source']['pad']['moveValid'])
        need(self.history.read(index)['clockJoin']['nativeAfter']['capturedEpochMs']<=packet['clockBefore']['epochMs'])
        need(same(coordinates(before),self.state['path']))
        world.measure(packet,packet)
        need(type(self.state['seconds']) in (int,float) and 0<self.state['seconds']<=12)
        return before
    def lease_owner(self):
        if self.lease is None:
            before=self.prepared();path=deepcopy(self.state['path']);window=path['window']
            actions=validate_actions(dict(actions=[dict(type='pointer',id='world-hold-codec',parameters=dict(pointerType='touch'),actions=[
                dict(type='pointerMove',duration=0,origin='viewport',x=path['start'][0],y=path['start'][1]),
                dict(type='pointerDown',button=0),
                dict(type='pointerMove',duration=0,origin='viewport',x=path['end'][0],y=path['end'][1]),
                dict(type='pointerUp',button=0)])]),window['width'],window['height'])
            start,end=actions[0][1],actions[2][1]
            opening=deepcopy(self.previous);factory=self.factory
            def check():
                self.bound();need(self.factory is factory and same(self.previous,opening) and same(self.envelope(),opening))
                join=before['clockJoin']
                need(0<=self.epoch_ms()-join['hostBeforeEpochMs']<1500 and 0<=self.monotonic()-join['hostBeforeMonotonic']<1.5)
                fresh(before['originals']['world']['clockAfter']['epochMs'],self.reader.clock_ms())
                return True
            def move_check():
                check();need(not lease.request_release.is_set() and asyncio.get_running_loop().time()<lease._deadline())
                return True
            lease=TouchLease(PrivateFeatureState(self.store.path.with_name('ios-lifecycle-world-hold-touch.json')),
                lambda:_MotionContext(factory,start,end,move_check),binding=self.binding,run=self.run,check=check)
            self.lease=lease
        return self.lease
    async def act(self,*,seconds=12):
        self.bound()
        if self.state['phase']=='new':
            need(type(seconds) in (int,float) and 0<seconds<=12 and self.attempt.state['phase']=='observed')
            self.attempt.effect();self.state['attempt']=digest(self.attempt.previous);self.state['seconds']=seconds
            if self.state['editor'] is None:
                self.history.append(self.sources.sample(self.epoch_ms()));self.state['editor']=len(self.history.state['frames']);self.save()
            if not self.state['frames']:self.capture(True)
            before=self.frame(1);self.state['path']=coordinates(before)
            self.state['phase']='prepared';self.save()
        need(self.state['phase']=='prepared')
        frame=self.prepared();join=frame['clockJoin']
        need(0<=self.epoch_ms()-join['hostBeforeEpochMs']<1500 and 0<=self.monotonic()-join['hostBeforeMonotonic']<1.5)
        fresh(frame['originals']['world']['clockAfter']['epochMs'],self.reader.clock_ms())
        self.state['phase']='issued';self.save();lease=self.lease_owner()
        window=self.state['path']['window'];start=self.state['path']['start']
        return await lease.begin(window['width'],window['height'],*start,seconds=self.state['seconds'])
    def held_proof(self,index):
        baseline,current=self.packet(1),self.packet(index);proof=world.active_forward(baseline,current)
        pad=baseline['source']['pad'];start=pad['center'];end=[start[0],start[1]-pad['radius']*.25]
        points=[point for event in current['source']['touch']['events'] for point in event['points']
                if point['id']==proof['contact']['contactId']]
        need(points and all(abs(a-b)<=1 for a,b in zip(points[0]['position'],start))
             and all(abs(a-b)<=1 for a,b in zip(points[-1]['position'],end)))
        return proof
    def observe(self):
        self.bound();need(self.state['phase'] in ('issued','held'))
        lease=self.lease_owner();status=lease.inspect()
        need(status['workerRunning'] and status['hostResponsibility'] and status['failure'] is None and not status['upIssued']
             and asyncio.get_running_loop().time()<lease._deadline())
        index=self.capture();need(asyncio.get_running_loop().time()<lease._deadline())
        proof=self.held_proof(index)
        self.state['held']=index;self.state['phase']='held';self.save();return proof
    def release_proof(self):
        need(self.state['released'] is not None)
        need(integer(self.state['released'],(self.state['held'] or 1)+1,len(self.state['frames'])))
        if self.state['held'] is not None:return world.contact_released(self.packet(self.state['held']),self.packet(self.state['released']))
        current=self.packet(self.state['released']);row=world.contact_attempt(self.packet(1),current)
        need(row['ended'] is not None and not current['source']['touch']['active']
             and all(n==0 for n in current['source']['drive']['raw']) and all(n==0 for n in current['source']['drive']['effective']))
        return row
    async def release(self):
        # Ordinary Up/context exit remains possible after a candidate/foreground
        # guard failure. Native proof requires fresh current admission afterward.
        if self.state['released'] is not None:self.bound();return self.release_proof()
        lease=self.lease_owner();status=await lease.release()
        need(not status['hostResponsibility'] and status['contextExitReturned'])
        self.bound()
        if self.state['released'] is None:
            self.state['released']=self.capture();self.state['phase']='released';self.save()
        return self.release_proof()
    def quiet_packet(self,index):
        value=self.packet(index);source=value['source'];released=self.packet(self.state['released'])
        need(source['touch']['active']==[] and not source['pad']['moveValid'] and all(n==0 for n in source['drive']['raw'])
             and same(source['touch']['events'],released['source']['touch']['events']))
        world.measure(released,value);return value
    def sample_quiet(self):
        self.bound();need(self.state['released'] is not None)
        index=self.capture();self.quiet_packet(index)
        self.state['quiet'].append(index);self.save()
        if len(self.state['quiet'])<4:return None
        proof=self.proof();self.state['phase']='quiet';self.save();return proof
    def proof(self):
        need(self.state['held'] is not None and self.state['released'] is not None)
        return dict(held=self.held_proof(self.state['held']),released=self.release_proof(),
                    quiet=world.stationary([self.quiet_packet(index) for index in self.state['quiet']]))
