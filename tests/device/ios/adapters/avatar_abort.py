"""Failed preparation owns one Stop, original OS quiet and one SDK deletion.

This is an abort receipt, never a successful Avatar Scene/Complete witness.
The original failed feature and all subordinate ownership remain on disk.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import appium_adapter as backend,avatar_operation_clock as operation_clock
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.installed_code import source as process_source

VERSION=1
PHASES=('failed','stop-issued','os-quiet','delete-issued','aborted')


class IOSAvatarAbort:
    """A separate failed lifecycle; no input retry or fabricated scene proof."""
    @staticmethod
    def admission(feature,paired_failure):
        need(feature.state is not None)
        if paired_failure is None:need(feature.state['phase']=='preparing')
        else:
            from ios.adapters.avatar_paired_failure import validate
            validate(feature,paired_failure)

    @classmethod
    def history(cls,feature,value):
        """Read actual failed-process originals after SDK metadata retirement.

        This is only the OS/SDK part of failed preparation. Ancillary account,
        file and preference ownership remains with its separate original graph.
        No live candidate/session/native-source factory is invoked here.
        """
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(isinstance(feature,IOSAvatarFeature));feature.lock.assert_held();feature.load()
        paired=deepcopy(value.get('pairedPreparationFailure'));cls.admission(feature,paired)
        result=object.__new__(cls);result.feature,result.runtime,result.selector,result.lock=feature,feature.runtime,feature.selector,feature.lock
        result.run,result.role=feature.run,feature.role;result.failure=deepcopy(feature.previous)
        result.paired_failure=paired
        result.binding=context(feature.state['bindings'][feature.role])
        result.store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+feature.role+'-'+feature.run+'-abort.json'))
        result.previous=deepcopy(value)
        result.source=deepcopy(process_source(value['source']));result.bundle=value['bundleId']
        result.state=result.decode(value);return result

    @classmethod
    def archive(cls,feature,value):
        result=cls.history(feature,value)
        need(same(result.store.read(),value) and result.state['phase']=='aborted');return result

    def __init__(self,feature,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,paired_failure=None):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(isinstance(feature,IOSAvatarFeature) and all(callable(x) for x in (epoch_ms,monotonic)))
        self.feature,self.runtime,self.selector,self.lock=feature,feature.runtime,feature.selector,feature.lock
        self.run,self.role=feature.run,feature.role
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort.json'))
        self.lock.assert_held();feature.load();self.previous=self.store.read()
        retained=None if self.previous is None else self.previous.get('pairedPreparationFailure')
        if paired_failure is not None and self.previous is not None:need(same(paired_failure,retained))
        self.paired_failure=deepcopy(retained if paired_failure is None else paired_failure)
        self.admission(feature,self.paired_failure)
        self.failure=deepcopy(feature.previous);self.binding=context(feature.state['bindings'][self.role])
        if self.previous is None:
            started=operation_clock.begin(self.epoch_ms(),self.monotonic())
            source=IOSGraphicsRuntime._graphics_final_source(self.runtime,self.selector,self.binding)
            _client,_session,_state,target,_scope=self.runtime._existing(self.selector)
            self.source=deepcopy(process_source(source));self.bundle=target['appId']
            self.state=dict(phase='failed',operationClock=started,stopReturned=False,process=None,sdkQueries=[],sdkPending=None)
            self.save()
        else:
            self.source=deepcopy(process_source(self.previous['source']));self.bundle=self.previous['bundleId']
            self.state=self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        value=dict(iosAvatarAbortVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            source=self.source,bundleId=self.bundle,failure=dict(kind='preparation-incomplete' if self.paired_failure is None else 'peer-preparation-incomplete',
                original=self.failure,originalSha256=digest(self.failure)),payload=pack([state]))
        if self.paired_failure is not None:value['pairedPreparationFailure']=deepcopy(self.paired_failure)
        return value

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous)
            and same(self.feature.store.read(),self.failure))
        self.admission(self.feature,self.paired_failure)
        base=self.runtime.adapter;base._candidate_guard(complete=True)
        target=base._target(self.selector);session=base.read_session(self.selector)
        need(type(session) is dict and session.get('sessionId')==self.binding['sessionId']
            and target['appId']==self.bundle and same(base._scope(self.selector,self.binding['sessionId'],session,target),
                {key:item for key,item in self.binding.items() if key!='processIdentity'}))

    def decode(self,value):
        exact(value,{'iosAvatarAbortVersion','runId','role','binding','source','bundleId','failure','payload'}
            |({'pairedPreparationFailure'} if self.paired_failure is not None else set()))
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosAvatarAbortVersion']) is int
            and value['iosAvatarAbortVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','operationClock','stopReturned','process','sdkQueries','sdkPending'});operation_clock.validate(state['operationClock'])
        need(state['phase'] in PHASES and type(state['stopReturned']) is bool
            and (not state['stopReturned'] or state['phase']!='failed'))
        if state['process'] is not None:
            exact(state['process'],{'originalSha256'});self.process_archive(state['process'])
        need((state['process'] is not None)==(state['phase'] in ('os-quiet','delete-issued','aborted'))
            and type(state['sdkQueries']) is list and len(state['sdkQueries'])<=64)
        for index,row in enumerate(state['sdkQueries'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index
                and row['status'] in ('present','absent','abandoned'))
            acquisition=row['acquisition']
            if row['status']=='abandoned':need(acquisition is None)
            else:self.acquisition(acquisition)
        pending=state['sdkPending']
        need(pending is None or type(pending) is int and pending==len(state['sdkQueries'])+1)
        need(not state['sdkQueries'] or state['phase'] in ('delete-issued','aborted'))
        if state['phase']=='aborted':need(pending is None and state['sdkQueries'] and state['sdkQueries'][-1]['status']=='absent')
        return deepcopy(state)

    @staticmethod
    def acquisition(value):
        exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        a,b=value['hostBeforeEpochMs'],value['hostAfterEpochMs'];c,d=value['hostBeforeMonotonic'],value['hostAfterMonotonic']
        need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15)
            and number(d,c,c+1.5) and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def process_store(self):
        return PrivateFeatureState(self.store.path.with_name(filename('avatar',self.role,0)))

    def process_archive(self,reference):
        store=self.process_store();value=store.read();need(value is not None and digest(value)==reference['originalSha256'])
        state=IOSProcessRetirement.archive(value,path=store.path,binding=self.binding,source=self.source,bundle=self.bundle,
            run=self.run,role=self.role,stage=0,profile='avatar')
        need(state['pending'] is None and state['windows'] and state['windows'][-1]['complete']);return state

    def input_guard(self):
        self.bound();operation_clock.check(self.state['operationClock'],self.epoch_ms(),self.monotonic())

    def stop(self):
        self.bound();base=self.runtime.adapter;outer=base._operation
        need(self.state['phase']=='failed' and outer in (None,'feature.avatar-people.cleanup'))
        need(same(IOSGraphicsRuntime._graphics_final_source(self.runtime,self.selector,self.binding),self.source))
        self.input_guard();self.state['phase']='stop-issued';self.save()
        # The canonical lifecycle owns the genuine terminateApp and binding
        # retirement. Any lost return leaves this exact send owned forever.
        need(base._operation==outer);previous=base._session_recreation_forbidden
        base._session_recreation_forbidden=True;base._operation=None
        try:
            with transport_scope(self.input_guard):
                self.input_guard();base.invoke(self.selector,'app.stop',{})
        finally:base._operation=outer;base._session_recreation_forbidden=previous
        self.state['stopReturned']=True;self.save()

    def process_round(self):
        self.bound();need(self.state['phase']=='stop-issued')
        reader=IOSGraphicsRuntime._retired_process_observer(self.runtime,self.selector,self.binding,self.source)
        owner=IOSProcessRetirement(self.process_store(),reader,self.binding,self.run,self.role,0,self.lock,profile='avatar')
        if not owner.advance():return False
        owner.current()
        IOSGraphicsRuntime._graphics_final_stopped(self.runtime,self.selector,self.binding,self.source)
        self.state.update(phase='os-quiet',process=dict(originalSha256=digest(owner.previous)));self.save();return True

    def sdk_absence(self):
        self.bound();need(self.state['phase']=='delete-issued')
        if self.state['sdkPending'] is not None:
            self.state['sdkQueries'].append(dict(index=self.state['sdkPending'],status='abandoned',acquisition=None))
            self.state['sdkPending']=None;self.save()
        need(len(self.state['sdkQueries'])<64)
        self.state['sdkPending']=len(self.state['sdkQueries'])+1;self.save()
        target=self.runtime.adapter._target(self.selector);client=backend.WebDriver(target['serverUrl'])
        before,started=self.epoch_ms(),self.monotonic();status='present'
        self.bound()
        try:
            with transport_scope(self.bound):client.call('GET','/session/'+self.binding['sessionId'])
        except backend.WebDriverRequestError as error:need(error.status==404);status='absent'
        acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.epoch_ms(),
            hostBeforeMonotonic=started,hostAfterMonotonic=self.monotonic());self.acquisition(acquisition)
        self.bound();self.state['sdkQueries'].append(dict(index=self.state['sdkPending'],status=status,acquisition=acquisition))
        self.state['sdkPending']=None
        if status=='absent':self.state['phase']='aborted'
        self.save();return status=='absent'

    def delete(self):
        self.bound();need(self.state['phase'] in ('os-quiet','delete-issued'))
        if self.state['phase']=='os-quiet':
            reader=IOSGraphicsRuntime._retired_process_observer(self.runtime,self.selector,self.binding,self.source)
            from ios.adapters.retired_process import absent
            need(absent(reader.read()));self.process_archive(self.state['process'])
            self.input_guard();self.state['phase']='delete-issued';self.save()
            client=backend.WebDriver(self.runtime.adapter._target(self.selector)['serverUrl'])
            self.bound()
            try:
                with transport_scope(self.input_guard):
                    self.input_guard();client.call('DELETE','/session/'+self.binding['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404)
        return self.sdk_absence()

    def result(self):
        self.bound();self.decode(self.previous);need(self.state['phase']=='aborted')
        return self.original_result()

    def original_result(self):
        """SDK-free failed status; never discharge ancillary responsibility."""
        self.lock.assert_held();need(same(self.store.read(),self.previous));self.feature.load()
        need(same(self.feature.previous,self.failure));self.decode(self.previous);need(self.state['phase']=='aborted')
        # Keep every original failed intent and subordinate resource ledger.
        # The next archive step must still qualify that complete byte graph.
        return dict(iosAvatarAbortResultVersion=1,runId=self.run,role=self.role,status='failed',
            processEnded=True,sdkAbsent=True,ownershipRetained=True,originalSha256=digest(self.previous))
