"""Current installed/PID-gated composition; authenticated HID stays explicit.

Default profile retains an explicitly owned HID factory. Optional child profile
routes its original worker through existing operations and typed source births.
Production admission stays closed; JSON cannot supply a HID/SDK owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need,exact
from copy import deepcopy
import hashlib
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from feature_journeys.contract import identifier,json_document
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.adapters.lifecycle_editors import LifecycleEditors
from ios.adapters.lifecycle_world_attempt import LifecycleWorldAttempt
from ios.adapters.lifecycle_world_hold import LifecycleWorldHold


def passive_world_original(frame,binding,run,owner):
    """Strict typed RAW+carrier join. Transport correlation is NOT live ownership."""
    from adapters.native_feature_observation import decode,validate as native,integer,number
    from adapters.native_clock_join import validate_join
    from ios.adapters import lifecycle_world as world
    from ios.adapters.lifecycle_world_attempt import source_frame_original
    exact(frame,{'originalKeeperPassiveWorldFrameVersion','ordinal','phase','originals','clockJoin','reads','previousReference'})
    need(type(frame['originalKeeperPassiveWorldFrameVersion']) is int and frame['originalKeeperPassiveWorldFrameVersion']==1
        and integer(frame['ordinal'],1,6) and frame['phase']==('held' if frame['ordinal']==1 else 'released' if frame['ordinal']==2 else 'quiet'))
    exact(frame['originals'],{'world','worldClock'});joined=validate_join(frame['clockJoin'],frame['originals'])
    packet=source_frame_original(frame,binding,run);reads=frame['reads'];need(type(reads) is list and len(reads)==3)
    phase='holding' if frame['phase']=='held' else 'released';lease=None;indices=[];ids=[]
    for row,action,original in zip(reads,('feature-native-observe',world.ACTION,'feature-native-observe'),(joined['nativeBefore'],packet,joined['nativeAfter'])):
        exact(row,{'originalKeeperPassiveRawVersion','queryIndex','query','nativeFile','hostBefore','hostAfter','passiveLeaseId','passivePhase'})
        need(type(row['originalKeeperPassiveRawVersion']) is int and row['originalKeeperPassiveRawVersion']==1 and integer(row['queryIndex'],1,32)
            and row['passivePhase']==phase);identifier(row['passiveLeaseId']);lease=row['passiveLeaseId'] if lease is None else lease;need(row['passiveLeaseId']==lease)
        query=row['query'];exact(query,{'schemaVersion','commandId','action'}|({'runId'} if action==world.ACTION else set()))
        need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']==action
            and query['commandId']==original.get('requestId') and (action!=world.ACTION or query['runId']==run))
        flags={'queryIssuanceOwned','freshNativeAcquisitionEstablished','installedCandidateBound','physicalFileIdentityEstablished',
            'nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        value=row['nativeFile'];exact(value,{'originalKeeperNativeFileVersion','ownerInstance','source','action','requestId','rawJson','bytes','sha256','passiveLeaseId','passivePhase'}|flags)
        need(type(value['originalKeeperNativeFileVersion']) is int and value['originalKeeperNativeFileVersion']==4
            and value['ownerInstance']==owner and value['source']=='original-rsd-house-arrest' and value['action']==action
            and value['requestId']==query['commandId'] and value['passiveLeaseId']==lease and value['passivePhase']==phase
            and type(value['rawJson']) is str and type(value['bytes']) is int and value['bytes']==len(value['rawJson'].encode())
            and value['sha256']==hashlib.sha256(value['rawJson'].encode()).hexdigest() and all(value[k] is False for k in flags)
            and decode(value['rawJson'],limit=world.LIMIT)==original)
        for point in (row['hostBefore'],row['hostAfter']):
            exact(point,{'epochMs','monotonic'});need(number(point['epochMs'],1,1e15) and number(point['monotonic'],0,1e15))
        a,b=row['hostBefore'],row['hostAfter'];need(0<=b['epochMs']-a['epochMs']<1500 and 0<=b['monotonic']-a['monotonic']<1.5
            and abs((b['epochMs']-a['epochMs'])-(b['monotonic']-a['monotonic'])*1000)<=250)
        if action==world.ACTION:world.validate(original,query,int(binding['processIdentity']))
        else:native(original,query['commandId'],int(binding['processIdentity']),original['capturedEpochMs'])
        indices.append(row['queryIndex']);ids.append(query['commandId'])
    need(indices==list(range(indices[0],indices[0]+3)) and len(set(ids))==3)
    begin=reads[0]['hostAfter'] if frame['phase']=='quiet' else reads[0]['hostBefore'];end=reads[2]['hostAfter']
    need(joined['hostBeforeEpochMs']==begin['epochMs'] and joined['hostBeforeMonotonic']==begin['monotonic']
        and joined['hostAfterEpochMs']==end['epochMs'] and joined['hostAfterMonotonic']==end['monotonic'])
    need((frame['ordinal']==1)==(frame['previousReference'] is None));return frame



def selected_motion_frame_original(frame,binding,run,owner,selected_query):
    import re
    from urllib.parse import quote,unquote
    from adapters.native_feature_observation import number
    from adapters.native_clock_join import validate_join
    from ios.adapters.lifecycle_world_attempt import source_frame_original,gesture
    from ios.adapters.lifecycle_touch_resource_owner import selected_motion_original
    from ios.adapters import native_geometry
    exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads','sdkWindow','selectedCandidate'})
    need(type(frame['originalKeeperNativeAcquisitionFrameVersion']) is int and frame['originalKeeperNativeAcquisitionFrameVersion']==3)
    originals=frame['originals'];exact(originals,{'world','worldClock','geometry','window'})
    joined=validate_join(frame['clockJoin'],originals);packet=source_frame_original(frame,binding,run)
    candidate=frame['selectedCandidate'];selected_motion_original(candidate,frame,binding,run,owner)
    need(candidate['selectionQueryId']==selected_query)
    geometry=originals['geometry'];native_geometry.validate(geometry,geometry['commandId'],native_epoch_ms=joined['nativeAfter']['capturedEpochMs'])
    need(joined['nativeBefore']['capturedEpochMs']<=geometry['observation']['sampleEpochMs']<=packet['clockBefore']['epochMs'])
    sdk=frame['sdkWindow'];exact(sdk,{'method','path','reply','hostBeforeMonotonic','hostAfterMonotonic'})
    need(sdk['method']=='GET' and type(sdk['path']) is str and len(sdk['path'])<=512
        and sdk['path'].startswith('/session/') and sdk['path'].endswith('/window/rect'))
    session=unquote(sdk['path'][9:-12]);need(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',session) is not None
        and sdk['path']=='/session/'+quote(session,safe='')+'/window/rect')
    need(type(sdk['reply']) is dict and sdk['reply'].get('value')==originals['window']
        and number(sdk['hostBeforeMonotonic'],joined['hostBeforeMonotonic'],joined['hostAfterMonotonic'])
        and number(sdk['hostAfterMonotonic'],sdk['hostBeforeMonotonic'],joined['hostAfterMonotonic']))
    # Actual same raw UIKit geometry/window derives the complete path;
    # no x/y or dimensions arrive as caller-chosen movement authority.
    gesture(packet,geometry,originals['window'],'selected-original-reader')
    return frame


def original_child_world_frame(value,binding,run,*,before):
    """Historical content/reference join only; actual child owns all authority."""
    from adapters.native_feature_observation import integer
    from adapters.script_feature.history import canonical
    from ios.adapters.keyboard_source import sha
    flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
    exact(value,{'originalKeeperNativeAcquisitionVersion','ownerInstance','reference','originalFrame'}|flags|({'binding','runId'} if before else set()))
    need(type(value['originalKeeperNativeAcquisitionVersion']) is int and value['originalKeeperNativeAcquisitionVersion']==(3 if before else 4)
        and all(value[k] is False for k in flags));identifier(value['ownerInstance'])
    if before:need(value['binding']==binding and value['runId']==run)
    frame=value['originalFrame'];ref=value['reference'];exact(ref,{'index','sha256','bytes','device','inode'});sha(ref['sha256'])
    need(integer(ref['index'],1,1024) and integer(ref['bytes'],2,1024*1024) and integer(ref['device'],0,2**64-1) and integer(ref['inode'],1,2**64-1))
    prefix='iosLifecycleNativeAcquisitionFrameVersion' if before else 'iosLifecyclePassiveWorldFrameVersion'
    body={prefix:1,'kind':'sources','binding':binding,'runId':run,'role':'primary','index':ref['index'],'frame':frame}
    raw=canonical(body);need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'])
    if before:selected_motion_frame_original(frame,binding,run,value['ownerInstance'],frame['selectedCandidate']['selectionQueryId'])
    else:passive_world_original(frame,binding,run,value['ownerInstance'])
    return frame


class _OriginalKeeperMotionLease:
    """Transport to the existing child worker; NEVER an authenticated factory.

    Actual source/RSD/loop/worker/native admission remain in the child. This
    object cannot open a HID session. Existing production admission stays closed.
    """
    def __init__(self,source,run,owner,reference,path,seconds):
        import asyncio
        from adapters.native_feature_observation import number
        identifier(run);identifier(owner);exact(path,{'window','start','end'})
        need(type(source) is dict and source['binding']['sessionId']==source['session']
            and source['check']() is not False and type(reference) is dict)
        self._source=source;self._client=source['client'];self._session=source['session'];self._owner=owner
        self._binding=deepcopy(source['binding']);self._run=run;self._reference=deepcopy(reference);self._path=deepcopy(path)
        from ios.adapters.appium_adapter import WebDriver
        need(type(self._client) is WebDriver
            and self._client.retain_original_keeper_cleanup.__func__ is WebDriver.retain_original_keeper_cleanup
            and self._client._read_reply.__func__ is WebDriver._read_reply)
        self._execute=self._client.execute;self._call_function=self._client.call.__func__;self._origin=self._client.server_url
        self._cleanup=self._client.retain_original_keeper_cleanup(self._session,original=dict(ownerInstance=self._owner,
            binding=deepcopy(self._binding),runId=self._run,referenceJson=canonical(self._reference).decode('ascii')))
        from ios.adapters.touch import validate_actions
        need(number(seconds,0,12) and seconds>0)
        actions=validate_actions(dict(actions=[dict(type='pointer',id='original-child-motion',parameters=dict(pointerType='touch'),actions=[
            dict(type='pointerMove',duration=0,origin='viewport',x=self._path['start'][0],y=self._path['start'][1]),
            dict(type='pointerDown',button=0),dict(type='pointerUp',button=0)])]),self._path['window']['width'],self._path['window']['height'])
        self._requests=[];self._issued=False;self._journal=None;self._loop=None
        self._opening=dict(position=list(actions[0][1]),seconds=seconds)
    async def _request(self,operation,args,*,forward):
        import asyncio,inspect
        from ios.adapters.touch_lease import TouchLeasePending
        loop=asyncio.get_running_loop()
        if self._loop is None:self._loop=loop
        need(loop is self._loop)
        if forward:need(self._source['client'] is self._client and self._source['session']==self._session
            and self._source['binding']==self._binding and self._client.server_url==self._origin
            and self._client.call.__func__ is self._call_function and self._source['check']() is not False)
        # Preserve the ORIGINAL bound sender even if current mutable driver /
        # foreground fields drift. The child retained route checks its actual
        # original owner; no selector/new client/session is constructed here.
        def send():
            if not forward:
                need(not args);return self._cleanup(operation)
            return self._execute(self._session,'mobile: overteOriginalKeeperOperation',dict(operation=operation,args=deepcopy(args)))
        task=asyncio.create_task(asyncio.to_thread(send),name='original-child-'+operation);self._requests.append(task)
        failure=None
        while not task.done():
            try:await asyncio.shield(task)
            except BaseException as error:failure=failure or error
        # Actual Thread/Future completes before accepted return or propagated
        # cancellation. Unknown send is not a permit to repeat original Down.
        if failure is not None:raise failure
        result=task.result()
        need(type(result) is dict and result.get('ownerInstance')==self._owner)
        if forward:need(self._source['check']() is not False)
        return result
    def _inspection(self,result,*,begin=False,allow_unborn=False):
        from adapters.native_feature_observation import integer,number
        from ios.adapters.touch_lease import PHASES,FAILURES
        keys={'iosOriginalKeeperTouchVersion','ownerInstance','inspection','nativeTouchSupport','resourceRetirementEstablished'}
        keys.add('nativeMotionGuardAvailable')
        if not begin:keys|={'originalKeeperRetainedTouchProfileVersion','resourceReferenceJson'}
        else:keys.add('resourceReferenceJson')
        exact(result,keys);need(type(result['iosOriginalKeeperTouchVersion']) is int and result['iosOriginalKeeperTouchVersion']==(4 if begin else 3)
            and result['ownerInstance']==self._owner and result['nativeTouchSupport'] is False and result['resourceRetirementEstablished'] is False
            and result['nativeMotionGuardAvailable'] is False)
        if begin:need(result['resourceReferenceJson']==canonical(self._reference).decode('ascii'))
        if not begin:need(type(result['originalKeeperRetainedTouchProfileVersion']) is int and result['originalKeeperRetainedTouchProfileVersion']==1
            and result['resourceReferenceJson']==canonical(self._reference).decode('ascii'))
        value=result['inspection']
        if value is None:
            need(allow_unborn and not begin and not self._issued and self._journal is None);return None
        exact(value,{'hostResponsibility','workerRunning','downIssued','upIssued','contextExitReturned','failure','journal'})
        need(all(type(value[k]) is bool for k in ('hostResponsibility','workerRunning','downIssued','upIssued','contextExitReturned'))
            and (value['failure'] is None or value['failure'] in FAILURES))
        journal=value['journal'];exact(journal,{'iosTouchLeaseVersion','binding','runId','leaseId','position','startedMonotonic','deadlineMonotonic','phase','failure'})
        need(type(journal['iosTouchLeaseVersion']) is int and journal['iosTouchLeaseVersion']==1 and journal['binding']==self._binding
            and journal['runId']==self._run and journal['phase'] in PHASES and journal['failure']==value['failure'])
        identifier(journal['leaseId']);need(type(journal['position']) is list and len(journal['position'])==2
            and all(integer(n,0,65535) for n in journal['position'])
            and number(journal['startedMonotonic'],0,1e15) and number(journal['deadlineMonotonic'],journal['startedMonotonic'],journal['startedMonotonic']+12)
            and 0<journal['deadlineMonotonic']-journal['startedMonotonic']<=12)
        need(self._opening is not None and journal['position']==self._opening['position']
            and abs((journal['deadlineMonotonic']-journal['startedMonotonic'])-self._opening['seconds'])<1e-7)
        # Immutable original Source deadline remains in its own clock domain.
        # It is NEVER relabelled as the host event-loop deadline.
        immutable={k:v for k,v in journal.items() if k not in ('phase','failure')}
        if self._journal is None:self._journal=deepcopy(immutable)
        else:need(self._journal==immutable)
        return deepcopy(value)
    async def begin(self,width,height,x,y,*,seconds):
        need(not self._issued and (width,height,x,y)==(self._path['window']['width'],self._path['window']['height'],*self._path['start']))
        need(type(seconds) in (int,float) and seconds==self._opening['seconds'])
        self._issued=True # before actual send; lost return cannot authorize replay.
        result=await self._request('touch-begin',dict(binding=deepcopy(self._binding),runId=self._run,width=width,height=height,x=x,y=y,
            seconds=seconds,nativeMotionProfileVersion=2,expectedOwnerInstance=self._owner,referenceJson=canonical(self._reference).decode('ascii')),forward=True)
        return self._inspection(result,begin=True)
    async def inspect(self):return self._inspection(await self._request('touch-inspect',{},forward=False),allow_unborn=True)
    async def release(self):return self._inspection(await self._request('touch-release',{},forward=False))
    async def settle(self):return self._inspection(await self._request('touch-settle',{},forward=False),allow_unborn=True)


class _OriginalKeeperWorldConnection:
    """Existing client/child operation path; no local HID context or new Source."""
    def __init__(self,runtime,selector,source,run):
        need(type(runtime) is IOSLifecycleWorldHoldRuntime and source['check']() is not False)
        self.runtime,self.selector,self.source,self.run=runtime,selector,source,identifier(run)
        self.binding=deepcopy(source['binding']);self.owner=None;self.lease=None;self.preparation=None;self._lease=None
        self._terminal_started=False;self._terminal_references=None
    def current(self):
        need(self.source['binding']==self.binding and self.source['check']() is not False
            and self.lease is self._lease);return True
    def retained_lease(self):
        # This exact private born transport survives mutable public aliases.
        # It is only a sender; the child still proves the original Resource.
        need(self._lease is None or type(self._lease) is _OriginalKeeperMotionLease)
        return self._lease
    async def prepare(self,seconds):
        import asyncio
        from adapters.native_feature_observation import number
        from ios.adapters.lifecycle_world_hold import coordinates
        need(self.preparation is None and self.lease is None and number(seconds,0,12) and seconds>0)
        self.current()
        query=await asyncio.to_thread(self.runtime.adapter._lifecycle_owned_native_query,self.selector,self.run,
            'ios-bundle-observe',original_child_artifact=True)
        self.current()
        flags={'nativeAcquisitionBound','originalChildCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        exact(query,{'originalKeeperInstalledQueryVersion','binding','queryOriginal','installedBefore','installedAfter','selectedArtifactBundle','childBundleOriginal'}|flags)
        need(type(query['originalKeeperInstalledQueryVersion']) is int and query['originalKeeperInstalledQueryVersion']==3
            and query['binding']==self.binding and all(query[k] is False for k in flags))
        original=query['queryOriginal'];need(type(original['originalKeeperNativeQueryVersion']) is int and original['originalKeeperNativeQueryVersion']==3)
        selection=original['query']['commandId']
        value=await asyncio.to_thread(self.runtime.native_original_acquisition,self.selector,self.run,selected_query=selection)
        self.current();need(value['binding']==self.binding and value['runId']==self.run and value['ownerInstance']==original['ownerInstance'])
        frame=value['originalFrame'];path=coordinates(frame)
        # Bind cleanup to the ORIGINAL transport before preparation can leave
        # unknown child responsibility. It grants no authenticated/input fact.
        self.owner=value['ownerInstance'];lease=_OriginalKeeperMotionLease(self.source,self.run,self.owner,value['reference'],path,seconds)
        self._lease=self.lease=lease # BEFORE the preparation may have an unknown return.
        prepared=await lease._request('touch-motion-prepare',dict(binding=deepcopy(self.binding),runId=self.run,
            referenceJson=canonical(value['reference']).decode('ascii'),seconds=seconds),forward=True)
        exact(prepared,{'originalKeeperMotionPreparationVersion','ownerInstance','preparationRecorded','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'})
        need(type(prepared['originalKeeperMotionPreparationVersion']) is int and prepared['originalKeeperMotionPreparationVersion']==3
            and prepared['ownerInstance']==self.owner and prepared['preparationRecorded'] is True
            and all(prepared[k] is False for k in ('nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished')))
        self.preparation=deepcopy(value)
        return dict(originals=deepcopy(frame['originals']),clockJoin=deepcopy(frame['clockJoin']),originalChild=deepcopy(value))
    def bind_preparation(self,frame,seconds):
        """Rebind TRANSPORT to an existing source; never restore a worker from JSON."""
        from ios.adapters.lifecycle_world_hold import coordinates
        need(self.lease is None and self.preparation is None)
        value=frame['originalChild'];need(value['binding']==self.binding and value['runId']==self.run)
        self.owner=value['ownerInstance'];self.preparation=deepcopy(value)
        self._lease=self.lease=_OriginalKeeperMotionLease(self.source,self.run,self.owner,value['reference'],coordinates(frame),seconds)
        # Any resumed read/release/begin still reaches the original child's
        # actual opaque lease/resource gates; this DTO mints none of them.
    async def _terminal(self,mode):
        self.current();need(self.preparation is not None and self._lease is not None and mode in ('collect','recover'))
        target=self.source['target']['testBuild']
        args=dict(binding=deepcopy(self.binding),runId=self.run,resultsDirectory=target['resultsDirectory'],origin=target['fixtureOrigin'],
            nativePassiveAcquisitionVersion=2,phase='released-quiet',terminalMode=mode,expectedOwnerInstance=self.owner,
            preparationReferenceJson=canonical(self.preparation['reference']).decode('ascii'))
        if mode=='collect':
            need(not self._terminal_started);self._terminal_started=True # BEFORE actual possibly-unknown send.
        else:need(self._terminal_started)
        result=await self._lease._request('touch-native-acquire',args,forward=True)
        self.current()
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==5
            and result['ownerInstance']==self.owner and result['encoding']=='canonical-json-ascii'
            and type(result['acquisitionJson']) is str and result['acquisitionJson'].isascii()
            and len(result['acquisitionJson'])<12000 and all(result[key] is False for key in flags))
        value=json_document(result['acquisitionJson'])
        exact(value,{'binding','runId','preparationReferenceJson','terminalState','references'})
        need(canonical(value).decode('ascii')==result['acquisitionJson'] and value['binding']==self.binding and value['runId']==self.run
            and value['preparationReferenceJson']==args['preparationReferenceJson'] and value['terminalState'] in ('saved','partial')
            and type(value['references']) is list and len(value['references'])<=5)
        codec=OriginalFrameStore(self.runtime.adapter.state_path(self.selector).parent,self.binding,self.run,'primary',
            self.current,lambda *_:need(False),namespace='lifecycle-passive-world',schema_prefix='iosLifecyclePassiveWorld')
        references=set()
        for ordinal,row in enumerate(value['references'],2):
            exact(row,{'reference','ordinal','phase'});codec.expand(row['reference'])
            need(type(row['ordinal']) is int and row['ordinal']==ordinal and type(row['phase']) is str
                and row['phase']==('released' if ordinal==2 else 'quiet')
                and row['reference']['sha256'] not in references)
            references.add(row['reference']['sha256'])
        # Partial saved observations retain responsibility but are NEVER a
        # successful four-quiet proof. Recovery performs NO replacement query.
        need(value['terminalState']=='saved' and len(value['references'])==5)
        self._terminal_references=deepcopy(value['references'])
    async def recover_terminal(self):
        """Explicit saved-only recovery after original uncertain terminal RPC."""
        await self._terminal('recover')
    async def capture(self,phase,*,ordinal=None):
        import asyncio
        self.current();need(self.lease is not None and self.preparation is not None)
        if phase=='held':
            need(ordinal==1)
            value=await asyncio.to_thread(self.runtime.native_passive_world,self.selector,self.run,phase)
        else:
            need(type(ordinal) is int and 2<=ordinal<=6 and phase==('released' if ordinal==2 else 'quiet'))
            if not self._terminal_started:await self._terminal('collect')
            # A lost HTTP return NEVER automatically retries the batch. Caller
            # must explicitly ask saved-only recover_terminal on the same owner.
            need(self._terminal_references is not None)
            row=deepcopy(self._terminal_references[ordinal-2])
            selector=dict(binding=deepcopy(self.binding),runId=self.run,**row)
            result=dict(ownerInstance=self.owner)
            task=asyncio.create_task(asyncio.to_thread(self.runtime._native_passive_world_reference,
                self.selector,None,self.run,phase,result,selector),name='original-child-passive-ref-read')
            self._lease._requests.append(task);failure=None
            while not task.done():
                try:await asyncio.shield(task)
                except BaseException as error:failure=failure or error
            if failure is not None:raise failure
            value=task.result()
        self.current();need(value['ownerInstance']==self.owner)
        frame=value['originalFrame']
        return dict(originals=deepcopy(frame['originals']),clockJoin=deepcopy(frame['clockJoin']),originalChild=deepcopy(value))
    async def inspect(self):
        lease=self.retained_lease();need(lease is not None);return await lease.inspect()
    async def release(self):
        lease=self.retained_lease();need(lease is not None);return await lease.release()
    async def settle(self):
        lease=self.retained_lease();need(lease is not None);return await lease.settle()



class IOSLifecycleWorldHoldRuntime:
    def __init__(self,adapter):self.adapter=adapter
    def native_original_acquisition(self,selector,run,*,selected_query=None):
        """Reread the original child's immutable bytes; no fresh/input verdict.

        Actual capture clocks stay in the original frame. Transporting it
        later never samples a replacement native clock or changes its age.
        """
        import base64,time,re
        from adapters.native_feature_observation import decode,integer,number
        from adapters.script_feature.history import same,canonical
        from adapters.native_clock_join import validate_join
        from ios.adapters.lifecycle_world_attempt import source_frame_original
        from ios.adapters import lifecycle_world as world,native_geometry
        identifier(run);source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        binding=source['binding'];client=source['client'];session=source['session'];target=source['target']
        if selected_query is not None:
            need(type(selected_query) is str and re.fullmatch('ios-[0-9a-f]{32}',selected_query) is not None)
        operation='touch-native-acquire' if selected_query is None else 'touch-native-motion-acquire'
        extra={} if selected_query is None else dict(selectedQueryId=selected_query)
        result=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation=operation,
            args=dict(binding=deepcopy(binding),runId=run,resultsDirectory=target['testBuild']['resultsDirectory'],
                origin=target['testBuild']['fixtureOrigin'],**extra)))
        source['check']()
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==(1 if selected_query is None else 3)
            and result['encoding']=='canonical-json-ascii' and type(result['acquisitionJson']) is str
            and len(result['acquisitionJson'])<=2048 and result['acquisitionJson'].isascii()
            and all(result[key] is False for key in flags));identifier(result['ownerInstance'])
        payload=json_document(result['acquisitionJson']);exact(payload,{'binding','runId','reference'})
        need(same(payload['binding'],binding) and payload['runId']==run and canonical(payload).decode('ascii')==result['acquisitionJson'])
        # Reuse only the existing exact reference/envelope codec. The HOST
        # never opens this remote path or treats its inode as local authority.
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,binding,run,'primary',source['check'],
            lambda *_:need(False),namespace='lifecycle-native-acquisition',schema_prefix='iosLifecycleNativeAcquisition')
        reference=payload['reference'];codec.expand(reference);reference_json=canonical(reference).decode('ascii')
        raw=[];started=time.monotonic()
        def transfer_current():
            source['check']();now=time.monotonic();need(number(now,started,started+5) and now-started<5)
        for offset in range(0,reference['bytes'],4096):
            transfer_current()
            chunk=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquisition-read',
                args=dict(binding=deepcopy(binding),runId=run,referenceJson=reference_json,offset=offset)))
            transfer_current();exact(chunk,{'originalKeeperNativeAcquisitionReadVersion','ownerInstance','encoding','originalJson'}|flags)
            need(type(chunk['originalKeeperNativeAcquisitionReadVersion']) is int and chunk['originalKeeperNativeAcquisitionReadVersion']==1
                and chunk['ownerInstance']==result['ownerInstance'] and chunk['encoding']=='canonical-json-ascii'
                and type(chunk['originalJson']) is str and chunk['originalJson'].isascii() and len(chunk['originalJson'])<12000
                and all(chunk[key] is False for key in flags))
            value=json_document(chunk['originalJson']);exact(value,{'reference','offset','contentBase64'})
            need(canonical(value).decode('ascii')==chunk['originalJson'] and same(value['reference'],reference)
                and type(value['offset']) is int and value['offset']==offset and type(value['contentBase64']) is str
                and len(value['contentBase64'])<=5464)
            data=base64.b64decode(value['contentBase64'],validate=True)
            need(len(data)==min(4096,reference['bytes']-offset));raw.append(data)
        raw=b''.join(raw);need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        body=decode(raw.decode('utf-8'),limit=1024*1024);need(canonical(body)==raw)
        exact(body,{'iosLifecycleNativeAcquisitionFrameVersion','kind','binding','runId','role','index','frame'})
        need(type(body['iosLifecycleNativeAcquisitionFrameVersion']) is int and body['iosLifecycleNativeAcquisitionFrameVersion']==1
            and body['kind']=='sources' and body['role']=='primary' and same(body['binding'],binding) and body['runId']==run
            and type(body['index']) is int and body['index']==reference['index'])
        frame=body['frame']
        if selected_query is not None:return self._selected_motion_original_result(source,run,selected_query,result,reference,frame,transfer_current)
        exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads'})
        need(type(frame['originalKeeperNativeAcquisitionFrameVersion']) is int and frame['originalKeeperNativeAcquisitionFrameVersion']==1)
        originals=frame['originals'];exact(originals,{'world','worldClock','geometry'})
        joined=validate_join(frame['clockJoin'],originals);source_frame_original(frame,binding,run)
        first,last=joined['nativeBefore'],joined['nativeAfter'];geometry=originals['geometry'];packet=originals['world']
        native_geometry.validate(geometry,geometry['commandId'],native_epoch_ms=last['capturedEpochMs'])
        need(first['capturedEpochMs']<=geometry['observation']['sampleEpochMs']<=packet['clockBefore']['epochMs'])
        reads=frame['reads'];need(type(reads) is list and len(reads)==4)
        actions=['feature-native-observe','native-geometry-snapshot',world.ACTION,'feature-native-observe']
        packets=[first,geometry,packet,last];indices=[]
        file_flags={'queryIssuanceOwned','freshNativeAcquisitionEstablished','installedCandidateBound','physicalFileIdentityEstablished',
            'nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        for row,action,original in zip(reads,actions,packets):
            exact(row,{'query','queryIndex','original'});need(integer(row['queryIndex'],1,32));indices.append(row['queryIndex'])
            query=row['query'];fields={'schemaVersion','commandId','action'}
            if action==world.ACTION:fields.add('runId')
            exact(query,fields);need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']==action
                and type(query['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',query['commandId']) is not None
                and query['commandId']==original.get('requestId',original.get('commandId')) and (action!=world.ACTION or query['runId']==run))
            read=row['original'];exact(read,{'originalKeeperNativeFileVersion','ownerInstance','source','action','requestId','rawJson','bytes','sha256'}|file_flags)
            need(type(read['originalKeeperNativeFileVersion']) is int and read['originalKeeperNativeFileVersion']==1
                and read['ownerInstance']==result['ownerInstance'] and read['source']=='original-rsd-house-arrest'
                and read['action']==action and read['requestId']==query['commandId'] and type(read['rawJson']) is str
                and type(read['bytes']) is int and read['bytes']==len(read['rawJson'].encode('utf-8'))
                and read['sha256']==hashlib.sha256(read['rawJson'].encode('utf-8')).hexdigest()
                and all(read[key] is False for key in file_flags)
                and same(decode(read['rawJson'],limit=262144),original))
        need(indices==list(range(indices[0],indices[0]+4)) and len({row['query']['commandId'] for row in reads})==4)
        transfer_current()
        return dict(originalKeeperNativeAcquisitionVersion=1,ownerInstance=result['ownerInstance'],binding=deepcopy(binding),
            runId=run,reference=deepcopy(reference),originalFrame=deepcopy(frame),nativeAcquisitionBound=False,
            installedCandidateBound=False,nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)

    def _selected_motion_original_result(self,source,run,selected_query,result,reference,frame,transfer_current):
        selected_motion_frame_original(frame,source['binding'],run,result['ownerInstance'],selected_query)
        transfer_current()
        return dict(originalKeeperNativeAcquisitionVersion=3,ownerInstance=result['ownerInstance'],binding=deepcopy(source['binding']),runId=run,
            reference=deepcopy(reference),originalFrame=deepcopy(frame),nativeAcquisitionBound=False,installedCandidateBound=False,
            nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)

    def resource_metadata(self,selector,run,*,recover=False):
        """Read the original child's passive resource DTO, never borrow auth.

        Actual loop/Task/RSD objects remain in that child. This consumer opens
        no lease/session, grants no input or native-end/production admission.
        """
        from ios.adapters.lifecycle_touch_resource_owner import owner_header,capture_original
        identifier(run);need(type(recover) is bool)
        source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        operation='touch-resource-recover' if recover else 'touch-resource-capture'
        value=source['client'].execute(source['session'],'mobile: overteOriginalKeeperOperation',
                                      dict(operation=operation,args=dict(binding=deepcopy(source['binding']),runId=run)))
        source['check']()
        exact(value,{'originalKeeperTouchResourceVersion','ownerInstance','encoding','resourceJson',
                     'nativeTouchSupport','resourceRetirementEstablished'})
        need(type(value['originalKeeperTouchResourceVersion']) is int and value['originalKeeperTouchResourceVersion']==2
             and value['encoding']=='canonical-json-ascii' and type(value['resourceJson']) is str
             and len(value['resourceJson'])<=12288 and value['resourceJson'].isascii()
             and value['nativeTouchSupport'] is False and value['resourceRetirementEstablished'] is False)
        identifier(value['ownerInstance'])
        payload=json_document(value['resourceJson']);exact(payload,{'capture','owner'})
        need(value['resourceJson']==canonical(payload).decode('ascii'))
        state=owner_header(payload['owner'],source['binding'],run)
        need(state['pending'] is None and state['frames'])
        # Reuse existing reference codec and canonical original-body hash.
        # This checks DTO content correlation, NOT remote inode authority or
        # a local substitute for the child's original file/worker ownership.
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,source['binding'],run,'primary',
            source['check'],lambda *_:need(False),namespace='lifecycle-touch-resource',schema_prefix='iosLifecycleTouchResource')
        references=[codec.expand(ref) for ref in state['frames']]
        need([ref['index'] for ref in references]==list(range(1,len(references)+1)))
        capture=capture_original(payload['capture'],state);reference=references[-1]
        body=dict(iosLifecycleTouchResourceFrameVersion=1,kind='sources',binding=source['binding'],
                  runId=run,role='primary',index=reference['index'],frame=capture)
        raw=canonical(body)
        need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        source['check']()
        return dict(originalKeeperTouchResourceVersion=2,ownerInstance=value['ownerInstance'],
                    capture=deepcopy(capture),owner=deepcopy(payload['owner']),
                    nativeTouchSupport=False,resourceRetirementEstablished=False)

    def native_passive_world(self,selector,run,phase):
        """Existing child/pipe+chunk path. Four quiet calls are distinct originals.

        These originals remain partial observations; no canonical child or
        current native/input/resource-retirement capability is opened here.
        """
        import base64,time
        from adapters.native_feature_observation import decode,number
        from adapters.script_feature.history import canonical
        from adapters.original_frame_store import OriginalFrameStore
        identifier(run);need(phase in ('held','released','quiet'))
        source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        binding,client,session,target=source['binding'],source['client'],source['session'],source['target']
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        result=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquire',args=dict(
            binding=deepcopy(binding),runId=run,resultsDirectory=target['testBuild']['resultsDirectory'],origin=target['testBuild']['fixtureOrigin'],
            nativePassiveAcquisitionVersion=1,phase=phase)))
        source['check']();exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==4
            and result['encoding']=='canonical-json-ascii' and type(result['acquisitionJson']) is str and result['acquisitionJson'].isascii()
            and len(result['acquisitionJson'])<=2048 and all(result[k] is False for k in flags));identifier(result['ownerInstance'])
        value=json_document(result['acquisitionJson']);exact(value,{'binding','runId','reference','ordinal','phase'})
        need(canonical(value).decode('ascii')==result['acquisitionJson'] and value['binding']==binding and value['runId']==run and value['phase']==phase)
        return self._native_passive_world_reference(selector,source,run,phase,result,value)

    def _native_passive_world_reference(self,selector,source,run,phase,result,value):
        # Every caller reopens actual Source membership/physical bytes through
        # the SAME existing chunk route. Saved batch refs are historical only.
        import base64,time
        from adapters.native_feature_observation import decode
        if source is None:
            # The caller keeps its ACTUAL main-thread source/lock gates before
            # and after this owned thread. Acquire the SAME canonical existing
            # channel admission HERE, as native_passive_world always did; never
            # borrow the caller's thread-bound ScriptSourceLock callback.
            source=IOSScriptRuntime(self.adapter)._sources(selector)
            source['check']()
        binding,client,session=source['binding'],source['client'],source['session']
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        need(value['binding']==binding and value['runId']==run and value['phase']==phase)
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,binding,run,'primary',source['check'],lambda *_:need(False),
            namespace='lifecycle-passive-world',schema_prefix='iosLifecyclePassiveWorld')
        ref=value['reference'];codec.expand(ref);raw=[];started=time.monotonic()
        for offset in range(0,ref['bytes'],4096):
            source['check']();need(0<=time.monotonic()-started<5)
            chunk=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquisition-read',args=dict(
                binding=deepcopy(binding),runId=run,referenceJson=canonical(ref).decode('ascii'),offset=offset,nativePassiveAcquisitionVersion=1)))
            source['check']();need(0<=time.monotonic()-started<5)
            exact(chunk,{'originalKeeperNativeAcquisitionReadVersion','ownerInstance','encoding','originalJson'}|flags)
            need(type(chunk['originalKeeperNativeAcquisitionReadVersion']) is int and chunk['originalKeeperNativeAcquisitionReadVersion']==2
                and chunk['ownerInstance']==result['ownerInstance'] and chunk['encoding']=='canonical-json-ascii'
                and type(chunk['originalJson']) is str and chunk['originalJson'].isascii() and len(chunk['originalJson'])<12000
                and all(chunk[k] is False for k in flags))
            body=json_document(chunk['originalJson']);exact(body,{'reference','offset','contentBase64'})
            need(canonical(body).decode('ascii')==chunk['originalJson'] and body['reference']==ref and type(body['offset']) is int and body['offset']==offset
                and type(body['contentBase64']) is str and len(body['contentBase64'])<=5464)
            data=base64.b64decode(body['contentBase64'],validate=True);need(len(data)==min(4096,ref['bytes']-offset));raw.append(data)
        raw=b''.join(raw);need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'])
        body=decode(raw.decode('utf-8'),limit=1024*1024);need(canonical(body)==raw)
        exact(body,{'iosLifecyclePassiveWorldFrameVersion','kind','binding','runId','role','index','frame'})
        need(type(body['iosLifecyclePassiveWorldFrameVersion']) is int and body['iosLifecyclePassiveWorldFrameVersion']==1
            and body['kind']=='sources' and body['binding']==binding and body['runId']==run and body['role']=='primary'
            and type(body['index']) is int and body['index']==ref['index'])
        frame=passive_world_original(body['frame'],binding,run,result['ownerInstance']);need(frame['ordinal']==value['ordinal'] and frame['phase']==phase)
        source['check']();return dict(originalKeeperNativeAcquisitionVersion=4,ownerInstance=result['ownerInstance'],reference=deepcopy(ref),
            originalFrame=deepcopy(frame),**{k:False for k in flags})

    def production_child(self,selector,editors,attempt,*,configuration=None):
        from ios.adapters.lifecycle_touch_transport import admit
        # Dependency admission precedes candidate/SDK work. No target value
        # or caller-supplied factory may turn missing transport into support.
        admit(configuration)

    def child(self,selector,editors,attempt,session_factory,*,original_child=False):
        need(type(original_child) is bool and type(editors) is LifecycleEditors and type(attempt) is LifecycleWorldAttempt
            and (original_child and session_factory is None or not original_child and callable(session_factory)))
        editors.history.check();attempt.bound();need(attempt.history is editors.history)
        source=IOSScriptRuntime(self.adapter)._sources(selector)
        need(same(source['binding'],editors.binding))
        root=self.adapter.state_path(selector).parent;need(root==editors.history.store.path.parent)
        original=source['check'];lock=editors.history.lock
        def check():lock.assert_held();need(original() is not False);return True
        source['check']=check
        sources=IOSLifecycleSources(source,editors.run,epoch_ms=editors.sources.epoch_ms,monotonic=editors.sources.monotonic)
        # Retain the unchanged actual first-attempt owner; only the second
        # attempt's passive readers use this freshly admitted canonical scope.
        connection=_OriginalKeeperWorldConnection(self,selector,source,editors.run) if original_child else None
        owner=LifecycleWorldHold(PrivateFeatureState(root/'ios-lifecycle-world-hold.json'),attempt,session_factory,original_child=connection)
        owner.sources=sources;owner.reader=source['observer'].lifecycle_world(source['clock_source'])
        owner.geometry=source['observer'].geometry();owner.ui=NativeUI(source['client'],source['session'],check)
        return owner
