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
        self._target=None;self._failed=False;self._selected=selected;self._selected_id=selected_id;self._worker_guard=None;self._worker_phase=None
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
    def _identity(self):
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
                and owner.instance==self._original_journal()['previous']['ownerInstance'])
            if self._worker_guard is None:need(not source._leases and not source._born and owner.touch is None)
            else:
                need(type(self._worker_guard) is _NativeMotionWorkerGuard and self._worker_guard._original() is not None
                    and self._worker_guard._original()._selected is self._selected)
                self._worker_guard._scope_without_ref()
            target=None if self._target is None else self._target()
            need((self._target is None and owner.touch_resources is None)
                or (target is not None and owner.touch_resources is target))
            owner._native_acquisition_current(self._original_journal(),self._original_journal()['binding']['sessionId'])
            need(self._original_journal()['rsd'] is rsd and self._original_journal().get('motionOriginals',{}).get(self._reference['sha256']) is self
                and self._reference in self._original_journal()['previous']['frames'])
            pending=self._original_journal()['previous']['pending']
            if pending is not None:
                step=self._worker_guard
                need(type(step) is _NativeMotionWorkerGuard and type(step._pending_write) is _NativeMotionPendingWrite)
                step._pending_write.identity(self._original_journal(),pending)
        except BaseException:
            self.revoke() # Observed unknown scope never revives by ABA.
            raise
    def _check(self):
        try:
            self._identity();need(asyncio.get_running_loop().time()<self._deadline)
        except BaseException:
            self.revoke();raise
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
        return self._read(source,resource,owner_instance,self._check)
    def anchor(self,source,resource,owner_instance):
        # Only already-bound immutable intent, never a fresh/native verdict.
        need(type(resource) is LifecycleTouchResourceOwner and resource.version==4
            and resource._motion_original is self and self._target is not None and self._target() is resource)
        return self._read(source,resource,owner_instance,self._identity)
    def _read(self,source,resource,owner_instance,guard):
        # Consumer reads never borrow a writer's pending/adoption permission.
        if self._original_journal()['previous']['pending'] is not None:
            self.revoke();need(False)
        from adapters.native_clock_join import validate_join
        from ios.adapters.lifecycle_world_attempt import source_frame_original
        guard();owner=self._owner();need(source is self._source() and owner.instance==owner_instance
            and (resource is None or self._target is not None and self._target() is resource))
        files=owner._native_acquisition_files(self._original_journal(),guard)
        frame=files.read(files.expand(self._reference));guard()
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
        guard();return result


class _NativeMotionPendingWrite:
    """Ephemeral actual writer responsibility; never pending-file adoption."""
    def __init__(self,step,task,cut,token,journal,files,index,frame):
        import hashlib
        from adapters.script_feature.history import canonical
        from adapters.original_frame_store import VERSION as frame_version
        need(type(step) is _NativeMotionWorkerGuard and type(files) is OriginalFrameStore
            and step._pending_write is None and asyncio.current_task() is task
            and files.guard is token[1] and files.root==step._resource().store.path.parent
            and files.namespace=='lifecycle-native-acquisition' and files.schema_prefix=='iosLifecycleNativeAcquisition'
            and files.kind=='sources' and files.role=='primary' and files.binding==journal['binding'] and files.run==journal['run']
            and index==len(journal['previous']['frames'])+1 and 1<=index<=8 and journal['previous']['pending'] is None)
        body=dict({files.key('FrameVersion'):frame_version},kind=files.kind,binding=files.binding,runId=files.run,
            role=files.role,index=index,frame=frame)
        raw=canonical(body)
        self._step,self._task,self._files=weakref.ref(step),weakref.ref(task),weakref.ref(files)
        self._cut,self._token,self._journal=cut,token,journal
        self._expected=dict(index=index,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));self._pending=None
    def _scope(self):
        step,task,files=self._step(),self._task(),self._files()
        need(type(step) is _NativeMotionWorkerGuard and isinstance(task,asyncio.Task) and type(files) is OriginalFrameStore
            and task is asyncio.current_task() and not task.done() and task.get_loop() is asyncio.get_running_loop()
            and step._pending_write is self)
        step._scope_without_ref();owner=step._owner();resource=step._resource()
        need(owner is not None and owner.native_current_cuts.get(task) is self._cut and len(self._cut)==6
            and self._cut[0] is resource and self._cut[4] is step and self._cut[5] in ('before-down','after-down')
            and owner.native_acquisition is self._token and self._token[0] is task and self._token[1] is files.guard
            and task.get_loop().time()<self._cut[3] and resource.lock is self._journal['lock']
            and resource._motion_original._original_journal() is self._journal)
        return files
    def record(self,reference):
        files=self._scope();files.original(reference)
        need({key:reference[key] for key in self._expected}==self._expected)
        previous=self._pending
        if previous is None:need(reference['phase']=='planned' and reference['file'] is None)
        else:
            need(reference['phase']=={'planned':'opened','opened':'saved'}.get(previous['phase'])
                and all(same(previous[k],reference[k]) for k in previous if k not in ('phase','file'))
                and (previous['phase']=='planned' or same(previous['file'],reference['file'])))
        self._pending=deepcopy(reference)
    def identity(self,journal,pending):
        files=self._scope();files.original(pending)
        need(journal is self._journal and self._pending is not None and same(pending,self._pending)
            and {key:pending[key] for key in self._expected}==self._expected
            and pending['index']==len(journal['previous']['frames'])+1)


class _NativePassiveQueryCallback:
    """Exact original query's scheduled check, never a generic loop callback."""
    def __init__(self,scope,guard,bridges,journal,record):
        import threading,types
        owner,task=scope._owner(),scope._task()
        need(type(scope) is _NativeMotionPassiveRead and task is asyncio.current_task()
            and owner.native_passive_tasks.get(task) is scope and owner.native_query_task is task
            and scope._query_callback is None and owner.native_passive_callback is None)
        def nested(code,name):
            found=[v for v in code.co_consts if isinstance(v,types.CodeType) and v.co_name==name]
            need(len(found)==1);return found[0]
        root=scope._query_function.__code__
        need(guard.__code__ is nested(root,'current') and guard.__globals__ is scope._query_function.__globals__)
        self._worker_guard_code=nested(root,'worker_guard');self._worker_code=nested(root,'worker')
        self._check_code=nested(self._worker_guard_code,'check')
        self._thread=self._worker_function=self._finished=None
        self._scope,self._task=weakref.ref(scope),weakref.ref(task)
        self._guard,self._bridges,self._journal=guard,bridges,journal
        self._record=deepcopy(record);self._registered={};self._lock=threading.Lock();self._active=False
    def bind_thread(self,thread,worker,finished):
        import threading
        scope,task=self._scope(),self._task();owner=scope._owner()
        need(scope is not None and task is asyncio.current_task() and self._thread is None
            and owner.native_query_task is task and owner.native_passive_tasks.get(task) is scope
            and type(thread) is threading.Thread and thread.ident is None and not thread.is_alive()
            and worker.__code__ is self._worker_code and worker.__globals__ is scope._query_function.__globals__
            and any(row[0] is task and row[1] is thread and row[2] is finished and row[3] is task.get_loop()
                    for row in owner.source._native_queries))
        self._thread,self._worker_function,self._finished=thread,worker,finished
    def register(self,check,future):
        # Only the born HTTP thread's original worker_guard may register its
        # bridge. Copied same-code functions on another thread/Task are not
        # the source which owns this actual original send.
        import sys,threading
        scope=self._scope();need(scope is not None and self._thread is threading.current_thread()
            and self._thread.is_alive() and not self._finished.is_set()
            and sys._getframe(1).f_code is self._worker_guard_code
            and check.__code__ is self._check_code
            and check.__globals__ is scope._query_function.__globals__ and future in self._bridges and not future.done())
        with self._lock:
            need(check not in self._registered);self._registered[check]=future
    def task_for(self,scope):
        owner,task=scope._owner(),self._task()
        need(self._active and self._scope() is scope and scope._query_callback is self
            and asyncio.current_task() is None and isinstance(task,asyncio.Task) and not task.done()
            and asyncio.get_running_loop() is task.get_loop() and owner.source._loop is task.get_loop()
            and owner.native_passive_callback is self and owner.native_query_task is task
            and owner.native_passive_tasks.get(task) is scope)
        return task
    def execute(self,check,future):
        import sys
        scope=self._scope();need(scope is not None and sys._getframe(1).f_code is self._check_code
            and check.__code__ is self._check_code and asyncio.current_task() is None)
        owner,task=scope._owner(),self._task();need(owner is not None and owner.native_passive_callback is None)
        with self._lock:
            need(self._registered.pop(check,None) is future and not future.done())
        need(owner.native_query_journals.get(scope._resource().run) is self._journal
            and self._journal['loop'] is task.get_loop() and self._journal['pending'] is None)
        row=self._journal['previous']['records'][self._record['index']-1]
        need(row['index']==self._record['index'] and row['query']==self._record['query']
            and row['passiveLeaseId']==self._record['passiveLeaseId'] and row['passivePhase']==self._record['passivePhase']
            and row['phase'] in ('intent','http-returned'))
        self._active=True;owner.native_passive_callback=self
        try:
            self.task_for(scope);self._guard()
        finally:owner.native_passive_callback=None;self._active=False


class _NativeMotionPassiveRead:
    """Actual same-source observation Task while held or after own Up/drain.

    This is read admission only. No source/native freshness, new input or
    resource-retirement claim follows from the old worker's returned context.
    """
    def __init__(self,owner,session,action,binding,run):
        from ios.adapters import lifecycle_world as world
        resource=owner.touch_resources;lease=owner.touch;task=asyncio.current_task()
        need(type(resource) is LifecycleTouchResourceOwner and resource.version==4
            and type(resource._native_step) is _NativeMotionWorkerGuard and type(lease) is TouchLease
            and resource._lease() is lease and getattr(lease,'_original_motion_resource',None) is resource
            and action in (world.ACTION,'feature-native-observe') and session==resource.binding['sessionId']
            and same(context(binding),resource.binding) and run==resource.run
            and isinstance(task,asyncio.Task) and task.get_loop() is owner.source._loop
            and owner.native_acquisition is None and owner.native_query_task is None and not owner.native_passive_tasks)
        # A known still-opening/moving/draining worker is not a readable
        # boundary. Refusal here does not revoke its immutable source; later
        # actual original return may establish a new readable phase.
        if lease.worker is None or (not lease.worker.done() and (lease.request_release.is_set() or lease.previous['phase']!='holding')):
            raise TouchTransportUnavailable('Original touch has not reached a stable held or returned context boundary')
        step=resource._native_step
        self._owner,self._resource,self._step,self._lease,self._task=weakref.ref(owner),weakref.ref(resource),weakref.ref(step),weakref.ref(lease),weakref.ref(task)
        self._action,self._session=action,session;self._query_callback=None
        self._phase='released' if lease.worker is not None and lease.worker.done() else 'holding'
        self._query_function=owner.native_query.__func__;self._file_function=owner.native_original_read.__func__
        owner.native_passive_tasks[task]=self
        try:self.current()
        except BaseException:
            owner.native_passive_tasks.pop(task,None);raise
    def lease_identity(self,source,owner,lease,worker):
        resource,step,task=self._resource(),self._step(),self._task()
        need(owner is self._owner() and resource is not None and step is resource._native_step
            and step._source() is source and step._owner() is owner and step._lease() is lease
            and lease is self._lease() and worker is step._worker() and worker is lease.worker
            and task is self.execution_task() and isinstance(task,asyncio.Task) and not task.done()
            and task.get_loop() is source._loop and owner.native_passive_tasks.get(task) is self
            and owner.native_query.__func__ is self._query_function and owner.native_original_read.__func__ is self._file_function
            and owner.touch is lease and source._leases==[lease] and len(source._born)==1
            and source._born[0]['lease'] is lease and source._born[0]['worker'] is worker
            and source._born[0]['loop'] is source._loop and source._born[0]['release'] is lease.request_release
            and source._born[0]['owner'] is not None and source._born[0].get('motionResource') is resource)
        status=source._born[0]['owner']._status()
        need(not lease.journal_failed and lease.down_issued)
        if self._phase=='holding':
            need(not worker.done() and not lease.request_release.is_set() and not lease.up_issued
                and lease.previous['phase']=='holding' and status['workerRunning'] and status['hostResponsibility']
                and not status['contextExitReturned'] and source._loop.time()<lease._deadline())
        else:
            need(worker.done() and not worker.cancelled() and worker.exception() is None and lease.request_release.is_set()
                and lease.closed and lease.up_issued and status['contextExitReturned']
                and not status['workerRunning'] and not status['hostResponsibility'])
        from ios.adapters.lifecycle_touch_transport import intent
        need(same(intent(lease.previous),intent(step._opening)))
    def execution_task(self):
        task=self._task();owner=self._owner();current=asyncio.current_task()
        if current is task and owner is not None and owner.native_passive_tasks.get(task) is self:return task
        callback=self._query_callback
        if current is None and type(callback) is _NativePassiveQueryCallback and owner is not None and owner.native_passive_callback is callback:
            return callback.task_for(self)
        raise TouchTransportUnavailable('Original passive request execution is unavailable')
    def bind_query(self,guard,bridges,journal,record):
        callback=_NativePassiveQueryCallback(self,guard,bridges,journal,record);self._query_callback=callback;return callback
    def current(self):
        self.execution_task()
        owner,resource,step=self._owner(),self._resource(),self._step()
        need(owner is not None and resource is not None and step is not None
            and owner.touch_resources is resource and resource._native_step is step)
        lease=self._lease();worker=step._worker()
        if lease is None or worker is None or lease.worker is not worker:
            step.fail();need(False)
        if self._phase=='holding' and (worker.done() or lease.request_release.is_set()):
            # A known ordinary release changes the observation phase; reject
            # THIS result without inventing source loss or preventing later
            # independently acquired released observations.
            raise TouchTransportUnavailable('Original touch observation crossed its held boundary')
        with resource.lock.held():step.scope()
        need(owner.scope(self._session) is resource._motion_rsd());return True
    @property
    def lease_id(self):
        self.current();return self._lease().previous['leaseId']
    def close(self):
        owner,task=self._owner(),self._task()
        need(owner is not None and task is asyncio.current_task() and owner.native_passive_tasks.get(task) is self)
        del owner.native_passive_tasks[task]


class _NativeMotionWorkerGuard:
    """Original local lease and born Task, never a DTO or restored capability.

    The two actual input boundaries each acquire their OWN <=1.5s cut. The
    unchanged <=12s wait issues no input and makes no current native claim.
    Failure requests the existing ordinary Up; cleanup never calls this guard.
    """
    def __init__(self,resource,source,owner):
        need(type(resource) is LifecycleTouchResourceOwner and resource.version==4
            and type(resource._motion_original) is _NativeMotionReference
            and 0<resource.state['seconds']<=12 and resource._factory is None and resource._lease is None
            and resource._native_step is None and owner.source is source and owner.touch_resources is resource)
        need(same(resource.envelope(),resource.previous))
        original=resource._motion_original;original.anchor(source,resource,owner.instance)
        need(original._owner() is owner and original._selected is not None and owner.touch is None
            and not source._leases and not source._born)
        self._resource,self._source,self._owner,self._loop=weakref.ref(resource),weakref.ref(source),weakref.ref(owner),weakref.ref(asyncio.get_running_loop())
        self._original=weakref.ref(original);self._lease=self._worker=None;self._opening=self._factory=None
        self._failed=False;self._current=None;self._phase=None;self._contact=None;self._pending_write=None
        from ios.adapters.touch import validate_actions
        path=resource.state['path'];window=path['window']
        actions=validate_actions(dict(actions=[dict(type='pointer',id='original-motion-worker',parameters=dict(pointerType='touch'),actions=[
            dict(type='pointerMove',duration=0,origin='viewport',x=path['start'][0],y=path['start'][1]),
            dict(type='pointerDown',button=0),dict(type='pointerMove',duration=0,origin='viewport',x=path['end'][0],y=path['end'][1]),
            dict(type='pointerUp',button=0)])]),window['width'],window['height'])
        self._hid_start,self._hid_end=actions[0][1],actions[2][1]
        self._step_function=owner.native_motion_step.__func__
        need(original._selected[3].get('motionGuard') is None)
        resource._native_step=self;original._worker_guard=self
        original._selected[3]['motionGuard']=weakref.ref(self)
    def _scope_without_ref(self):
        resource,source,owner,loop=self._resource(),self._source(),self._owner(),self._loop()
        need(not self._failed and resource is not None and source is not None and owner is not None
            and loop is asyncio.get_running_loop() and source._loop is loop and resource._native_step is self
            and owner.source is source and owner.touch_resources is resource and resource.version==4
            and resource._motion_original is self._original() and resource.state['hostProcessId']==os.getpid()
            and not source._closing and not owner.closed and not owner.draining
            and owner.native_motion_step.__self__ is owner and owner.native_motion_step.__func__ is self._step_function)
        resource.file_guard();need(same(resource.envelope(),resource.previous))
        if self._lease is None:
            need(owner.touch is None and not source._leases and not source._born);return
        lease=self._lease();need(type(lease) is TouchLease and lease._session_factory is self._factory
            and lease.store.path.parent==resource.store.path.parent and lease.binding==resource.binding and lease.run==resource.run
            and same(lease.store.read(),lease.previous) and resource._lease() is lease)
        if self._worker is None:
            need(lease.worker is None and lease.previous is None and not source._born
                and (source._leases==[] and owner.touch is None or source._leases==[lease] and owner.touch in (None,lease)));return
        worker=self._worker();passive=owner.native_passive_tasks.get(asyncio.current_task())
        callback=owner.native_passive_callback
        if passive is None and asyncio.current_task() is None and type(callback) is _NativePassiveQueryCallback:
            passive=callback._scope();callback.task_for(passive)
        if passive is not None:
            need(type(passive) is _NativeMotionPassiveRead and passive._step() is self)
            passive.lease_identity(source,owner,lease,worker);return
        need(isinstance(worker,asyncio.Task) and worker is lease.worker and worker.get_loop() is loop
            and not worker.done() and owner.touch is lease and source._leases==[lease] and len(source._born)==1
            and source._born[0]['lease'] is lease and source._born[0]['worker'] is worker
            and source._born[0]['owner'] is not None and not lease.request_release.is_set() and loop.time()<lease._deadline())
        source._born[0]['owner']._status()
        from ios.adapters.lifecycle_touch_transport import intent
        need(self._opening is not None and intent(lease.previous)==intent(self._opening))
    def scope(self):
        try:
            original=self._original();need(original is not None and original._worker_guard is self)
            original._identity()
        except BaseException:
            self.fail();raise
    def fail(self):
        self._failed=True
        original=self._original()
        if original is not None:original.revoke()
        resource=self._resource()
        if resource is not None:resource._motion_failed=True
        lease=None if self._lease is None else self._lease()
        if lease is not None:lease.request_release.set()
    def bind_lease(self,lease,factory):
        need(self._lease is None and type(lease) is TouchLease and lease.worker is None and lease.previous is None
            and lease._session_factory is factory and self._resource()._lease() is lease)
        self._lease,self._factory=weakref.ref(lease),factory
    def born(self,lease,worker):
        source,owner=self._source(),self._owner()
        if self._worker is not None:
            need(self._lease() is lease and self._worker() is worker);return
        need(self._lease is not None and self._lease() is lease and worker is lease.worker
            and isinstance(worker,asyncio.Task) and worker.get_loop() is self._loop() and owner.touch is lease
            and source._leases==[lease] and len(source._born)==1 and source._born[0]['lease'] is lease
            and source._born[0]['worker'] is worker and source._born[0]['owner'] is not None
            and lease.previous is not None and lease.previous['phase']=='opening' and lease.previous['failure'] is None)
        source._born[0]['owner']._status();self._worker=weakref.ref(worker);self._opening=deepcopy(lease.previous)
        path=self._resource().state['path'];need(tuple(lease.previous['position'])==tuple(self._hid_start)
            and lease.previous['deadlineMonotonic']==lease.previous['startedMonotonic']+self._resource().state['seconds'])
    def checkpoint(self,phase):
        resource=self._resource();lease=None if self._lease is None else self._lease()
        with resource.lock.held():
            self.scope();need(lease is not None and asyncio.current_task() is self._worker()
                and type(self._current) is _NativeMotionReference and self._phase==phase
                and self._current._worker_guard is self and self._current._worker_phase==phase
                and asyncio.get_running_loop().time()<self._current._deadline and not lease.request_release.is_set())
    async def continuity(self):
        resource,owner=self._resource(),self._owner();lease=self._lease()
        with resource.lock.held():
            self.scope();await owner.fresh_touch_scope(resource.binding);self.scope()
            if lease.previous['phase']=='down-issued' and not lease.down_issued:
                self._current=await owner.native_motion_step(resource,self,'before-down');self._phase='before-down'
                self.checkpoint('before-down')
    async def movement(self):
        resource,owner=self._resource(),self._owner()
        try:
            with resource.lock.held():
                self.scope();need(asyncio.current_task() is self._worker() and self._lease().down_issued)
                self._current=await owner.native_motion_step(resource,self,'after-down');self._phase='after-down'
                self.checkpoint('after-down')
        except BaseException:
            self.fail();raise


class LifecycleTouchResourceOwner:
    def __init__(self,store,binding,run,lock,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard))
        self.store,self.binding,self.run,self.lock,self.check=store,deepcopy(context(binding)),identifier(run),lock,guard
        need(store.path.name=='ios-lifecycle-touch-resources-'+run+'.json' and lock.path==store.path.parent/'script-feature-sources.lock')
        self.previous=store.read();self.state=None;self._source=None;self._lease=None;self._retained=None;self._factory=None;self._loop=None
        self.version=1 if self.previous is None else self.previous.get('iosLifecycleTouchResourceOwnerVersion')
        need(type(self.version) is int and self.version in (1,2,3,4))
        self._motion_source=self._motion_rsd=self._motion_loop=self._motion_current_function=self._motion_address=None
        self._motion_failed=False;self._motion_original=None;self._native_step=None
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

    async def native_before_down(self):
        """Actual fresh original cut; local receipt only, never Down admission."""
        self.file_guard();need(self.version==4 and not self._motion_failed and type(self._motion_original) is _NativeMotionReference)
        owner=self._motion_original._owner();need(owner is not None)
        return await owner.native_before_down(self)

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
            if type(self._native_step) is not _NativeMotionWorkerGuard:
                raise TouchTransportUnavailable('Original selected-IPA preparation exists; fresh current Down/movement guard is not connected')
            return self._make_native_motion_lease(store,rsd,local_address,check=check,options=options,
                admit_begin=admit_begin,on_worker_birth=on_worker_birth,worker_lock=worker_lock)
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
    def _make_native_motion_lease(self,store,rsd,local_address,*,check,options,admit_begin,on_worker_birth,worker_lock):
        # Private source-born seam only. The normal RPC cannot install the
        # actual weak owner/lease bridge; restored DTO/WAL cannot recreate it.
        from ios.adapters.lifecycle_world_hold import _MotionContext
        step=self._native_step;step.scope()
        need(isinstance(store,PrivateFeatureState) and store.path!=self.store.path and store.read() is None
            and store.path.parent==self.store.path.parent and store.path.name=='ios-lifecycle-touch-lease-'+self.run+'.json'
            and rsd is self._motion_rsd() and local_address==self._motion_address and self._factory is None
            and callable(check) and worker_lock is True and callable(admit_begin) and callable(on_worker_birth))
        options={} if options is None else dict(options)
        need(set(options)<={'display_factory','hid_factory','socket_factory'} and all(callable(value) for value in options.values()))
        @asynccontextmanager
        async def selected_factory():
            # The SAME original worker owns this lock, SDK context and HID.
            with self.lock.held():
                step.scope();lease=self._lease()
                need(lease is not None and lease.worker is asyncio.current_task() and lease._session_factory is self._factory)
                self._source=resources.TouchResourceObservation(rsd);self._retained=RetainedTouchWorker(lease)
                self._loop=asyncio.get_running_loop()
                actual=lambda:touch_session(rsd,local_address,observation=self._source,**options)
                async with _MotionContext(actual,step._hid_start,step._hid_end,step.movement,
                        before_down=lambda:step.checkpoint('before-down')) as hid:yield hid
        self._factory=selected_factory
        lease=TouchLease(store,selected_factory,binding=self.binding,run=self.run,check=check,
            admit_begin=admit_begin,on_worker_birth=on_worker_birth)
        self._lease=weakref.ref(lease);lease._original_motion_resource=self
        step.bind_lease(lease,selected_factory);return lease

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
