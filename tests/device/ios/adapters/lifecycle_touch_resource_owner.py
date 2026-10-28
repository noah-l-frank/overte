"""Once-only host resource responsibility, not authenticated broker admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import asynccontextmanager
import asyncio,os,weakref
from adapters.native_feature_observation import exact,integer,number,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import lifecycle_touch_resources as resources
from ios.adapters.hid_session import touch_session
from ios.adapters.touch_lease import TouchLease,TouchLeasePending
from ios.adapters.lifecycle_touch_transport import RetainedTouchWorker,TouchTransportUnavailable

VERSION=1


def owner_header(value,binding,run):
    exact(value,{'iosLifecycleTouchResourceOwnerVersion','binding','runId','state'})
    need(type(value['iosLifecycleTouchResourceOwnerVersion']) is int and value['iosLifecycleTouchResourceOwnerVersion']==1
        and same(value['binding'],binding) and value['runId']==run)
    state=deepcopy(value['state']);exact(state,{'phase','leaseFile','leaseOpening','sourceInstance','hostProcessId','frames','pending'})
    need(state['phase']=='factory-issued' and type(state['leaseFile']) is str
        and state['leaseFile']=='ios-lifecycle-touch-lease-'+run+'.json'
        and integer(state['hostProcessId'],1))
    identifier(state['sourceInstance']);opening=state['leaseOpening']
    exact(opening,{'iosTouchLeaseVersion','binding','runId','leaseId','position','startedMonotonic','deadlineMonotonic','phase','failure'})
    need(type(opening['iosTouchLeaseVersion']) is int and opening['iosTouchLeaseVersion']==1 and same(opening['binding'],binding)
        and opening['runId']==run and opening['phase']=='opening' and opening['failure'] is None)
    identifier(opening['leaseId']);need(type(opening['position']) is list and len(opening['position'])==2
        and all(integer(n,0,65535) for n in opening['position'])
        and number(opening['startedMonotonic'],0,1e15) and number(opening['deadlineMonotonic'],0,1e15)
        and 0<opening['deadlineMonotonic']-opening['startedMonotonic']<=12)
    need(type(state['frames']) is list and len(state['frames'])<=32)
    return state


def capture_original(value,state,previous=None):
    exact(value,{'iosLifecycleTouchResourceCaptureVersion','leaseId','source','worker'})
    need(type(value['iosLifecycleTouchResourceCaptureVersion']) is int and value['iosLifecycleTouchResourceCaptureVersion']==1
        and value['leaseId']==state['leaseOpening']['leaseId'])
    resources.validate(value['source'],None if previous is None else previous['source'])
    need(value['source']['instance']==state['sourceInstance'] and value['source']['hostProcessId']==state['hostProcessId'])
    worker=value['worker'];exact(worker,{'nativeTouchSupport','hostResponsibility','workerRunning','contextExitReturned','retirementEstablished'})
    need(worker['nativeTouchSupport'] is False and worker['retirementEstablished'] is False
        and all(type(worker[key]) is bool for key in ('hostResponsibility','workerRunning','contextExitReturned'))
        and value['source']['workerAlive'] and worker['workerRunning']==(not value['source']['workerDone']))
    return value


def motion_original(value,binding,run):
    """Typed original preparation only; no current SDK/native authority."""
    from ios.adapters.lifecycle_world_attempt import source_frame_original
    from ios.adapters.lifecycle_world_hold import coordinates
    from ios.adapters import lifecycle_world as world
    exact(value,{'iosLifecycleTouchResourceOwnerVersion','binding','runId','state'})
    need(type(value['iosLifecycleTouchResourceOwnerVersion']) is int and value['iosLifecycleTouchResourceOwnerVersion']==2
        and same(context(value['binding']),binding) and value['runId']==run)
    state=deepcopy(value['state']);exact(state,{'phase','ownerInstance','hostProcessId','frame','path','seconds','sourceContext'})
    need(state['phase']=='motion-prepared' and integer(state['hostProcessId'],1) and number(state['seconds'],0,12) and state['seconds']>0)
    identifier(state['ownerInstance']);frame=state['frame'];exact(frame,{'originals','clockJoin'})
    exact(frame['originals'],{'world','worldClock','geometry','window'})
    packet=source_frame_original(frame,binding,run)
    pad=world.touch.pad(packet['source']['pad'])
    need(frame['clockJoin']['nativeBefore']['capturedEpochMs']<=frame['originals']['geometry']['observation']['sampleEpochMs']
        <=packet['clockBefore']['epochMs'] and packet['source']['touch']['active']==[] and pad is not None and not pad['moveValid'])
    need(same(state['sourceContext'],world.context(packet)) and same(state['path'],coordinates(frame)))
    world.measure(packet,packet)
    # Both endpoints are independently derived from the SAME original native
    # pad/UIKit viewport and then checked by the unchanged touch codec.
    from ios.adapters.touch import validate_actions
    path=state['path'];body=dict(actions=[dict(type='pointer',id='owned-world-motion',parameters=dict(pointerType='touch'),actions=[
        dict(type='pointerMove',duration=0,origin='viewport',x=path['start'][0],y=path['start'][1]),dict(type='pointerDown',button=0),
        dict(type='pointerMove',duration=0,origin='viewport',x=path['end'][0],y=path['end'][1]),dict(type='pointerUp',button=0)])])
    validate_actions(body,path['window']['width'],path['window']['height']);return state


class LifecycleTouchResourceOwner:
    def __init__(self,store,binding,run,lock,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard))
        self.store,self.binding,self.run,self.lock,self.check=store,deepcopy(context(binding)),identifier(run),lock,guard
        need(store.path.name=='ios-lifecycle-touch-resources-'+run+'.json' and lock.path==store.path.parent/'script-feature-sources.lock')
        self.previous=store.read();self.state=None;self._source=None;self._lease=None;self._retained=None;self._factory=None;self._loop=None
        self.version=1 if self.previous is None else self.previous.get('iosLifecycleTouchResourceOwnerVersion')
        need(type(self.version) is int and self.version in (1,2))
        self._motion_source=self._motion_rsd=self._motion_loop=self._motion_current_function=self._motion_address=None
        self._motion_failed=False
        self.files=OriginalFrameStore(store.path.parent,self.binding,run,'primary',self.file_guard,self.intent,
            namespace='lifecycle-touch-resource',schema_prefix='iosLifecycleTouchResource')
        if self.previous is not None:self.state=self.decode(self.previous)
    def file_guard(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));return True
    def current(self):self.file_guard();need(self.check() is not False);return True
    def envelope(self):return dict(iosLifecycleTouchResourceOwnerVersion=self.version,binding=deepcopy(self.binding),runId=self.run,state=deepcopy(self.state))
    def save(self):
        self.file_guard();value=self.envelope();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def decode(self,value):
        if self.version==2:return motion_original(value,self.binding,self.run)
        state=owner_header(value,self.binding,self.run)
        previous=None
        for index,ref in enumerate(state['frames'],1):
            full=self.files.expand(ref);need(full['index']==index);frame=self.files.read(full);self.frame(frame,state,previous);previous=frame
        if state['pending'] is not None:
            full=self.files.original(state['pending']);need(len(state['frames'])<32 and full['index']==len(state['frames'])+1)
            if full['phase']=='saved':self.frame(self.files.read(full),state,previous)
        return state
    def frame(self,value,state=None,previous=None):
        return capture_original(value,self.state if state is None else state,previous)
    def prepare_motion(self,source,owner_instance,frame,*,seconds):
        """Record immutable intent before Down; does not acquire a worker.

        Called only by the actual original keeper Source. Weak actual object/
        loop/RSD pairing stays inside this process and supplies NO native guard.
        """
        from ios.adapters.lifecycle_world_hold import coordinates
        from ios.adapters import lifecycle_world as world
        self.current();need(self.version==1 and self.previous is None and self._factory is None)
        loop=asyncio.get_running_loop();need(source._loop is loop)
        original_rsd,address=source.current();current_function=source.current.__func__
        state=dict(phase='motion-prepared',ownerInstance=identifier(owner_instance),hostProcessId=os.getpid(),
            frame=deepcopy(frame),path=coordinates(frame),seconds=seconds,sourceContext=world.context(frame['originals']['world']))
        envelope=dict(iosLifecycleTouchResourceOwnerVersion=2,binding=deepcopy(self.binding),runId=self.run,state=state)
        motion_original(envelope,self.binding,self.run)
        # These motion-pair fields add only weak SDK/Source/product edges.
        # The existing owner guard/factory retains its original responsibility;
        # a restored DTO cannot recreate that source/loop or authorize input.
        self._motion_source=weakref.ref(source);self._motion_rsd=weakref.ref(original_rsd);self._motion_loop=weakref.ref(loop)
        self._motion_current_function=current_function;self._motion_address=address
        self.version=2;self.state=state;self.save();self.motion_current();return deepcopy(self.previous)
    def motion_current(self):
        try:
            self.current();need(self.version==2 and not self._motion_failed and self._motion_source is not None
                and self.state['hostProcessId']==os.getpid() and same(self.envelope(),self.previous))
            source=self._motion_source();loop=self._motion_loop();rsd=self._motion_rsd()
            need(source is not None and loop is asyncio.get_running_loop() and source._loop is loop and rsd is not None
                and source.current.__func__ is self._motion_current_function)
            current,address=source.current();need(current is rsd and address==self._motion_address)
            motion_original(self.previous,self.binding,self.run);return True
        except BaseException:
            self._motion_failed=True # Observed unknown scope cannot revive by ABA.
            raise

    def make_lease(self,store,rsd,local_address,*,check,options=None,admit_begin=None,on_worker_birth=None,worker_lock=False):
        """Explicit source/test seam, never canonical production admission.

        The existing real touch_session owns all operations. This wrapper only
        records the actual original lease and captures passive resource edges.
        """
        if self.version==2:
            raise TouchTransportUnavailable('Original child native world/geometry/current deadline guard is not connected for motion')
        # Refuse another owner namespace before constructing or touching a
        # TouchLease journal, including this resource-owner pathname itself.
        need(isinstance(store,PrivateFeatureState) and store.path!=self.store.path
            and store.path.parent==self.store.path.parent
            and store.path.name=='ios-lifecycle-touch-lease-'+self.run+'.json')
        self.current();need(self.previous is None and self._factory is None and callable(check)
            and type(worker_lock) is bool
            and all(callback is None or callable(callback) for callback in (admit_begin,on_worker_birth)))
        options={} if options is None else dict(options)
        need(set(options)<={'display_factory','hid_factory','socket_factory'} and all(callable(value) for value in options.values()))
        def factory():
            self.current();lease=self._lease()
            need(lease is not None and lease._session_factory is self._factory and lease.worker is asyncio.current_task()
                and lease.worker.get_loop() is asyncio.get_running_loop() and lease.previous is not None
                and lease.previous['phase']=='opening' and same(lease.store.read(),lease.previous)
                and same(lease.binding,self.binding) and lease.run==self.run and self.previous is None)
            source=resources.TouchResourceObservation(rsd)
            self.state=dict(phase='factory-issued',leaseFile=lease.store.path.name,leaseOpening=deepcopy(lease.previous),
                sourceInstance=source.instance,hostProcessId=os.getpid(),frames=[],pending=None)
            # This actual immutable opening precedes the original context
            # creation. A lost commit cannot reacquire/replay the factory.
            self.save();self._source=source;self._loop=asyncio.get_running_loop()
            self._retained=RetainedTouchWorker(lease);self.current()
            return touch_session(rsd,local_address,observation=source,**options)
        if worker_lock:
            @asynccontextmanager
            async def selected_factory():
                # This SAME actual worker owns the actual lock across original
                # context entry/Down/Up/drain. Callers never nest it across an
                # await that can finish the worker's outer lock context.
                with self.lock.held():
                    async with factory() as hid:yield hid
        else:selected_factory=factory
        self._factory=selected_factory
        lease=TouchLease(store,selected_factory,binding=self.binding,run=self.run,check=check,
                         admit_begin=admit_begin,on_worker_birth=on_worker_birth)
        self._lease=weakref.ref(lease);return lease
    def intent(self,kind,reference):
        self.file_guard();need(kind=='original' and self.state is not None and len(self.state['frames'])<32 and reference['index']==len(self.state['frames'])+1)
        self.files.original(reference);prior=self.state['pending']
        if prior is not None:
            need(all(same(prior[key],reference[key]) for key in prior if key not in ('phase','file')))
            need((prior['phase'],reference['phase']) in {('planned','opened'),('opened','saved')})
            if prior['file'] is not None:need(same(prior['file'],reference['file']))
        else:need(reference['phase']=='planned')
        self.state['pending']=deepcopy(reference);self.save();return True
    def capture(self):
        self.current();need(self.version==1 and self.state is not None and self.state['pending'] is None and len(self.state['frames'])<32)
        if self._source is None or self._retained is None:raise TouchLeasePending('Archived resource admission has no original retained source/worker')
        need(asyncio.get_running_loop() is self._loop)
        value=dict(iosLifecycleTouchResourceCaptureVersion=1,leaseId=self.state['leaseOpening']['leaseId'],source=self._source.snapshot(),worker=self._retained.inspect())
        previous=None if not self.state['frames'] else self.files.read(self.files.expand(self.state['frames'][-1]))
        self.frame(value,previous=previous);ref=self.files.write(len(self.state['frames'])+1,value)
        self.state['frames'].append(ref);self.state['pending']=None;self.save();self.current();return deepcopy(value)
    def recover_capture(self):
        # Exact saved adoption only. No source/SDK query, input or factory.
        self.file_guard();need(self.version==1 and self.state is not None and len(self.state['frames'])<32 and self.state['pending'] is not None and self.state['pending']['phase']=='saved')
        ref=self.state['pending'];value=self.files.read(ref);previous=None if not self.state['frames'] else self.files.read(self.files.expand(self.state['frames'][-1]))
        self.frame(value,previous=previous);self.state['frames'].append(self.files.compact(ref));self.state['pending']=None;self.save();return deepcopy(value)
    async def release_worker(self):
        # Release remains possible after current foreground continuity is lost;
        # this delegates once-only ordinary Up to the same original lease.
        self.lock.assert_held();retained=self._retained
        if retained is None:raise TouchLeasePending('Archived resource admission has no retained original worker')
        lease=self._lease() if type(self._lease) is weakref.ReferenceType else None
        need(type(retained) is RetainedTouchWorker and type(lease) is TouchLease and retained._lease is lease and lease._session_factory is self._factory
            and same(self.binding,retained._binding) and self.run==retained._run
            and retained._store is lease.store and lease.store.path.parent==self.store.path.parent
            and self.lock.path==lease.store.path.with_name('script-feature-sources.lock'))
        # A lost passive-capture CAS acknowledgement must not block original
        # Up. The retained owner independently checks the exact lease journal,
        # intent, task, loop, store, factory and check callback before release.
        # No resource-WAL acknowledgement, repair or new fact is created here.
        return await retained.release()
    def ensure_retired(self):
        self.file_guard()
        if self._retained is not None:self._retained.ensure_teardown()
        raise TouchTransportUnavailable('Independent HID/media/SDK/tunnel resource census and authenticated handoff are unavailable')
