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


def selected_motion_original(candidate,frame,binding,run,owner_instance):
    """Historical typed byte join; ONLY local live receipt supplies ownership."""
    import hashlib,re
    from adapters.native_feature_observation import decode
    from ios.adapters.bundle_observation import validate as validate_bundle
    from ios.adapters.bundle_identity import compare
    from ios.adapters import lifecycle_world as world,native_geometry
    exact(candidate,{'originalKeeperSelectedMotionCandidateVersion','selectionQueryId','bundleRead','selectedArtifactBundle','reads'})
    need(type(candidate['originalKeeperSelectedMotionCandidateVersion']) is int and candidate['originalKeeperSelectedMotionCandidateVersion']==1
        and type(candidate['selectionQueryId']) is str and re.fullmatch('ios-[0-9a-f]{32}',candidate['selectionQueryId']) is not None)
    native_geometry.validate(frame['originals']['geometry'],frame['originals']['geometry']['commandId'],native_epoch_ms=frame['clockJoin']['nativeAfter']['capturedEpochMs'])
    reads=frame['reads'];need(type(reads) is list and len(reads)==5 and reads==candidate['reads'] and reads[2]==candidate['bundleRead'])
    actions=['feature-native-observe','native-geometry-snapshot','ios-bundle-observe',world.ACTION,'feature-native-observe']
    packets=[frame['clockJoin']['nativeBefore'],frame['originals']['geometry'],None,frame['originals']['world'],frame['clockJoin']['nativeAfter']]
    flags={'queryIssuanceOwned','freshNativeAcquisitionEstablished','installedCandidateBound','physicalFileIdentityEstablished',
        'nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
    indices=[];ids=[];bundle=None;owner=None
    for index,(row,action,packet) in enumerate(zip(reads,actions,packets)):
        exact(row,{'query','queryIndex','original'});need(integer(row['queryIndex'],1,32));indices.append(row['queryIndex'])
        query=row['query'];fields={'schemaVersion','commandId','action'}|({'runId'} if action==world.ACTION else set());exact(query,fields)
        need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']==action
            and type(query['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',query['commandId']) is not None
            and (action!=world.ACTION or query['runId']==run));ids.append(query['commandId'])
        value=row['original'];exact(value,{'originalKeeperNativeFileVersion','ownerInstance','source','action','requestId','rawJson','bytes','sha256'}|flags)
        need(type(value['originalKeeperNativeFileVersion']) is int and value['originalKeeperNativeFileVersion']==(2 if index==2 else 1)
            and value['source']=='original-rsd-house-arrest' and value['action']==action and value['requestId']==query['commandId']
            and type(value['rawJson']) is str and type(value['bytes']) is int and value['bytes']==len(value['rawJson'].encode('utf-8'))
            and value['sha256']==hashlib.sha256(value['rawJson'].encode('utf-8')).hexdigest() and all(value[key] is False for key in flags))
        identifier(value['ownerInstance']);owner=value['ownerInstance'] if owner is None else owner;need(value['ownerInstance']==owner==owner_instance)
        actual=decode(value['rawJson'],limit=262144)
        if index==2:
            validate_bundle(actual,query,int(binding['processIdentity']));need(actual['status']=='ready')
            compare(actual['bundle'],candidate['selectedArtifactBundle']);bundle=actual
        else:need(actual==packet and query['commandId']==packet.get('requestId',packet.get('commandId')))
    need(indices==list(range(indices[0],indices[0]+5)) and len(set(ids))==5)
    first,last=frame['clockJoin']['nativeBefore'],frame['clockJoin']['nativeAfter']
    need(first['capturedEpochMs']<=bundle['capturedEpochMs']<=last['capturedEpochMs'])
    return bundle


def motion_original(value,binding,run):
    """Typed original preparation only; no current SDK/native authority."""
    from ios.adapters.lifecycle_world_attempt import source_frame_original
    from ios.adapters.lifecycle_world_hold import coordinates
    from ios.adapters import lifecycle_world as world
    exact(value,{'iosLifecycleTouchResourceOwnerVersion','binding','runId','state'})
    need(type(value['iosLifecycleTouchResourceOwnerVersion']) is int and value['iosLifecycleTouchResourceOwnerVersion'] in (2,3,4)
        and same(context(value['binding']),binding) and value['runId']==run)
    state=deepcopy(value['state']);keys={'phase','ownerInstance','hostProcessId','frame','path','seconds','sourceContext'}
    if value['iosLifecycleTouchResourceOwnerVersion'] in (3,4):keys.add('acquisitionReference')
    if value['iosLifecycleTouchResourceOwnerVersion']==4:keys.add('selectedQueryId')
    exact(state,keys)
    if value['iosLifecycleTouchResourceOwnerVersion'] in (3,4):
        from ios.adapters.keyboard_source import sha
        ref=state['acquisitionReference'];exact(ref,{'index','sha256','bytes','device','inode'});sha(ref['sha256'])
        need(integer(ref['index'],1,1024) and integer(ref['bytes'],2,1024*1024)
            and integer(ref['device'],0,2**64-1) and integer(ref['inode'],1,2**64-1))
    need(state['phase']=='motion-prepared' and integer(state['hostProcessId'],1) and number(state['seconds'],0,12) and state['seconds']>0)
    identifier(state['ownerInstance']);frame=state['frame'];exact(frame,{'originals','clockJoin'}|({'selectedCandidate'} if value['iosLifecycleTouchResourceOwnerVersion']==4 else set()))
    exact(frame['originals'],{'world','worldClock','geometry','window'})
    packet=source_frame_original(frame,binding,run)
    if value['iosLifecycleTouchResourceOwnerVersion']==4:
        selected_motion_original(frame['selectedCandidate'],dict(frame,reads=frame['selectedCandidate']['reads']),binding,run,state['ownerInstance'])
        need(state['selectedQueryId']==frame['selectedCandidate']['selectionQueryId'])
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


class _NativeMotionReference:
    """Local source-born receipt; JSON/reference content is never authority.

    Weak SDK/source/task pairing plus live journal membership is mandatory on
    EACH real original reread. No native verdict or product owner is retained.
    """
    def __init__(self,owner,journal,reference,window_task,window_function,started,*,selected=None,selected_id=None):
        source=owner.source;loop=asyncio.get_running_loop();creator=source._creator_task()
        need(type(source._native_motion_key) is object and isinstance(creator,asyncio.Task)
            and creator.get_loop() is loop and not creator.done() and source._loop is loop
            and isinstance(owner.wda,asyncio.Task) and owner.wda.get_loop() is loop and not owner.wda.done()
            and isinstance(window_task,asyncio.Task) and window_task.get_loop() is loop and window_task.done()
            and not window_task.cancelled() and window_task.exception() is None)
        self._owner,self._source,self._rsd,self._loop=weakref.ref(owner),weakref.ref(source),weakref.ref(journal['rsd']),weakref.ref(loop)
        self._creator,self._wda=weakref.ref(creator),weakref.ref(owner.wda)
        self._source_function=source.current.__func__;self._current_function=owner._native_acquisition_current.__func__
        self._files_function=owner._native_acquisition_files.__func__;self._key=source._native_motion_key
        self._window_getter=owner._native_motion_window_function.__func__
        self._run=journal['run'];self._journal_key=journal.setdefault('motionBirth',object())
        self._reference,self._window_task=deepcopy(reference),window_task
        self._window_function,self._window_session=window_function,owner.wda_session
        self._capture=weakref.ref(asyncio.current_task());self._started=started;self._deadline=started+1.5
        self._target=None;self._failed=False;self._selected=selected;self._selected_id=selected_id
        self._selected_birth=None
        if selected is not None:
            query_owner=owner.native_query_journals.get(self._run)
            need(query_owner is not None and query_owner.get('selectedOriginals',{}).get(selected_id) is selected)
            selected[1]();capture=selected[3]['capture']()
            need(isinstance(capture,asyncio.Task) and capture.done() and not capture.cancelled() and capture.exception() is None)
            self._selected_birth=query_owner.setdefault('selectedMotionBirth',object())
    @property
    def reference(self):return deepcopy(self._reference)
    def _original_journal(self):
        owner=self._owner();need(owner is not None)
        journal=owner.native_acquisition_journals.get(self._run)
        need(journal is not None and journal.get('motionBirth') is self._journal_key)
        return journal
    def _check(self):
        try:
            if self._selected is not None:
                owner=self._owner();need(owner is not None)
                query_owner=owner.native_query_journals.get(self._run)
                need(query_owner is not None and query_owner.get('selectedMotionBirth') is self._selected_birth
                    and query_owner.get('selectedOriginals',{}).get(self._selected_id) is self._selected)
                self._selected[1]()
            source,owner,rsd,loop=self._source(),self._owner(),self._rsd(),self._loop()
            creator,wda,capture=self._creator(),self._wda(),self._capture()
            need(not self._failed and source is not None and owner is not None and rsd is not None
                and loop is asyncio.get_running_loop() and source._loop is loop and source._native_motion_key is self._key
                and source.current.__func__ is self._source_function and owner.source is source
                and owner._native_acquisition_current.__func__ is self._current_function
                and owner._native_acquisition_files.__func__ is self._files_function
                and owner._native_motion_window_function.__func__ is self._window_getter
                and owner._native_motion_window_function() is self._window_function
                and creator is not None and not creator.done() and creator.get_loop() is loop
                and wda is not None and owner.wda is wda and not wda.done() and wda.get_loop() is loop
                and owner.wda_session==self._window_session and owner.wda_binding_claimed
                and capture is not None and capture.done() and not capture.cancelled() and capture.exception() is None
                and self._window_task.done() and not self._window_task.cancelled() and self._window_task.exception() is None
                and not source._leases and not source._born and owner.touch is None
                and loop.time()<self._deadline and owner.instance==self._original_journal()['previous']['ownerInstance'])
            target=None if self._target is None else self._target()
            need((self._target is None and owner.touch_resources is None)
                or (target is not None and owner.touch_resources is target))
            owner._native_acquisition_current(self._original_journal(),self._original_journal()['binding']['sessionId'])
            need(self._original_journal()['rsd'] is rsd and self._original_journal().get('motionOriginals',{}).get(self._reference['sha256']) is self
                and self._reference in self._original_journal()['previous']['frames'] and self._original_journal()['previous']['pending'] is None)
        except BaseException:
            self.revoke() # Observed unknown scope never revives by ABA.
            raise
    def revoke(self):
        self._failed=True
        if self._selected is not None:self._selected[3]['revoked']=True
    def bind(self,source,resource,owner_instance):
        owner=self._owner();need(source is self._source() and owner is not None and owner.instance==owner_instance
            and self._target is None and owner.touch_resources is resource and resource.lock is self._original_journal()['lock']
            and resource.binding==self._original_journal()['binding'] and resource.run==self._original_journal()['run']
            and resource.version==1 and resource.previous is None and resource._factory is None)
        # The actual existing Source.prepare_motion calls this only after its
        # exact Source/Resource type checks; no RPC field can supply this object.
        if self._selected is not None:
            need(self._selected[3]['motionTarget'] is None)
            self._selected[3]['motionTarget']=weakref.ref(resource)
        self._target=weakref.ref(resource);self._check()
    def original(self,source,resource,owner_instance):
        from adapters.native_clock_join import validate_join
        from ios.adapters.lifecycle_world_attempt import source_frame_original
        self._check();owner=self._owner();need(source is self._source() and owner.instance==owner_instance
            and (resource is None or self._target is not None and self._target() is resource))
        files=owner._native_acquisition_files(self._original_journal(),self._check)
        frame=files.read(files.expand(self._reference));self._check()
        exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads','sdkWindow'}|({'selectedCandidate'} if self._selected is not None else set()))
        need(type(frame['originalKeeperNativeAcquisitionFrameVersion']) is int and frame['originalKeeperNativeAcquisitionFrameVersion']==(3 if self._selected is not None else 2)
            and frame['clockJoin']['hostBeforeMonotonic']==self._started)
        exact(frame['originals'],{'world','worldClock','geometry','window'})
        sdk=frame['sdkWindow'];exact(sdk,{'method','path','reply','hostBeforeMonotonic','hostAfterMonotonic'})
        from urllib.parse import quote
        need(sdk['method']=='GET' and sdk['path']=='/session/'+quote(self._window_session,safe='')+'/window/rect'
            and sdk['reply']==self._window_task.result() and type(sdk['reply']) is dict
            and sdk['reply'].get('value')==frame['originals']['window']
            and self._started<=sdk['hostBeforeMonotonic']<=sdk['hostAfterMonotonic']
            <=frame['clockJoin']['hostAfterMonotonic']<self._deadline)
        validate_join(frame['clockJoin'],frame['originals']);source_frame_original(frame,self._original_journal()['binding'],self._original_journal()['run'])
        result=dict(originals=deepcopy(frame['originals']),clockJoin=deepcopy(frame['clockJoin']))
        if self._selected is not None:
            selected_motion_original(frame['selectedCandidate'],frame,self._original_journal()['binding'],self._run,owner_instance)
            need(frame['selectedCandidate']['selectionQueryId']==self._selected_id
                and frame['selectedCandidate']['selectedArtifactBundle']==self._selected[2])
            result['selectedCandidate']=deepcopy(frame['selectedCandidate'])
        self._check();return result


class LifecycleTouchResourceOwner:
    def __init__(self,store,binding,run,lock,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard))
        self.store,self.binding,self.run,self.lock,self.check=store,deepcopy(context(binding)),identifier(run),lock,guard
        need(store.path.name=='ios-lifecycle-touch-resources-'+run+'.json' and lock.path==store.path.parent/'script-feature-sources.lock')
        self.previous=store.read();self.state=None;self._source=None;self._lease=None;self._retained=None;self._factory=None;self._loop=None
        self.version=1 if self.previous is None else self.previous.get('iosLifecycleTouchResourceOwnerVersion')
        need(type(self.version) is int and self.version in (1,2,3,4))
        self._motion_source=self._motion_rsd=self._motion_loop=self._motion_current_function=self._motion_address=None
        self._motion_failed=False;self._motion_original=None
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
        if self.version in (2,3,4):return motion_original(value,self.binding,self.run)
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
    def prepare_motion(self,source,owner_instance,original,*,seconds):
        """Record immutable intent before Down; does not acquire a worker.

        Called only by the actual original keeper Source. Weak actual object/
        loop/RSD pairing stays inside this process and supplies NO native guard.
        """
        from ios.adapters.lifecycle_world_hold import coordinates
        from ios.adapters import lifecycle_world as world
        self.current();need(self.version==1 and self.previous is None and self._factory is None
            and type(original) is _NativeMotionReference)
        frame=original.original(source,self,owner_instance)
        loop=asyncio.get_running_loop();need(source._loop is loop)
        original_rsd,address=source.current();current_function=source.current.__func__
        state=dict(phase='motion-prepared',ownerInstance=identifier(owner_instance),hostProcessId=os.getpid(),
            frame=deepcopy(frame),path=coordinates(frame),seconds=seconds,sourceContext=world.context(frame['originals']['world']),
            acquisitionReference=original.reference)
        version=4 if original._selected is not None else 3
        if version==4:state['selectedQueryId']=original._selected_id
        envelope=dict(iosLifecycleTouchResourceOwnerVersion=version,binding=deepcopy(self.binding),runId=self.run,state=state)
        motion_original(envelope,self.binding,self.run)
        # These motion-pair fields add only weak SDK/Source/product edges.
        # The existing owner guard/factory retains its original responsibility;
        # a restored DTO cannot recreate that source/loop or authorize input.
        self._motion_source=weakref.ref(source);self._motion_rsd=weakref.ref(original_rsd);self._motion_loop=weakref.ref(loop)
        self._motion_current_function=current_function;self._motion_address=address
        self.version=version;self.state=state;self._motion_original=original;self.save();self.motion_current();return deepcopy(self.previous)
    def motion_current(self):
        try:
            self.current();need(self.version in (2,3,4) and not self._motion_failed and self._motion_source is not None
                and self.state['hostProcessId']==os.getpid() and same(self.envelope(),self.previous))
            source=self._motion_source();loop=self._motion_loop();rsd=self._motion_rsd()
            need(source is not None and loop is asyncio.get_running_loop() and source._loop is loop and rsd is not None
                and source.current.__func__ is self._motion_current_function)
            current,address=source.current();need(current is rsd and address==self._motion_address)
            motion_original(self.previous,self.binding,self.run)
            if self.version in (3,4):
                need(type(self._motion_original) is _NativeMotionReference
                    and self._motion_original.reference==self.state['acquisitionReference']
                    and self._motion_original.original(source,self,self.state['ownerInstance'])==self.state['frame'])
            return True
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
        if self.version==3:
            raise TouchTransportUnavailable('Independent child installed-candidate bytes and native current movement admission are unavailable')
        if self.version==4:
            raise TouchTransportUnavailable('Original selected-IPA preparation exists; fresh current Down/movement guard is not connected')
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
