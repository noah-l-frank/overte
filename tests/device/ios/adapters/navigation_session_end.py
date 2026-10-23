"""One SDK DELETE after actual Navigation process end, with original 404 proof.

No ordinary cleanup fallback can terminate again. Uncertain DELETE delivery is
resolved only by separately journaled GETs; all original evidence is retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import appium_adapter as backend
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.installed_code import InstalledCodeBinding,cleanup_record
from ios.adapters.navigation_process_end import NavigationProcessEnd
from ios.adapters.process_retirement import acquisition
from ios.adapters.retired_process import validate as os_packet,absent

VERSION=1


class NavigationSessionEnd:
    def __init__(self,process):
        need(type(process) is NavigationProcessEnd)
        self.process,self.flow,self.lock=process,process.flow,process.lock;self.base=self.flow.runtime.adapter
        self.binding,self.run=deepcopy(process.binding),process.run
        self.lock.assert_held();process.verify()
        self.store=PrivateFeatureState(process.store.path.with_name('ios-navigation-session-end.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state):
        return dict(iosNavigationSessionEndVersion=VERSION,runId=self.run,binding=self.binding,
            processOriginalSha256=digest(self.process.previous),payload=pack([state]))

    @staticmethod
    def query_clock(value):
        exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        a,b,c,d=(value[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'))
        need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15)
            and number(d,c,c+1.5) and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)

    def decode(self,value):
        exact(value,{'iosNavigationSessionEndVersion','runId','binding','processOriginalSha256','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosNavigationSessionEndVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','sdkOriginal','installedOriginal','osOriginal','osAcquisition','queries','pending','deleteReturned'})
        need(state['phase'] in ('prepared','delete-issued','sdk-absent','complete') and type(state['deleteReturned']) is bool
            and (not state['deleteReturned'] or state['phase']!='prepared'))
        installed=state['installedOriginal'];sdk=state['sdkOriginal'];scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        class Frozen:
            def read(_self):return deepcopy(installed)
        def forbidden(*_args,**_kwargs):need(False)
        record=InstalledCodeBinding(Frozen(),scope,installed['observation']['bundle'],forbidden,forbidden,forbidden).record()
        need(record is not None and record['phase']=='retired' and str(record['process']['pid'])==self.binding['processIdentity']
            and same(record['source'],self.process.state['source']) and record['observation']['bundle']['bundleId']==self.process.state['bundleId']
            and sdk.get('sessionId')==self.binding['sessionId'] and sdk.get('generation')==self.binding['generation']
            and sdk.get('targetFingerprint')==self.binding['targetFingerprint'])
        original=state['osOriginal'];os_packet(original,dict(commandId=original['commandId'],bundleId=self.process.state['bundleId']),
            int(self.binding['processIdentity']),self.process.state['source']);acquisition(state['osAcquisition'],original);need(absent(original))
        need(type(state['queries']) is list and len(state['queries'])<=64)
        for index,row in enumerate(state['queries'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index
                and row['status'] in ('present','absent','abandoned'))
            if row['status']=='abandoned':need(row['acquisition'] is None)
            else:self.query_clock(row['acquisition'])
        pending=state['pending'];need(pending is None or type(pending) is int and pending==len(state['queries'])+1)
        if state['phase'] in ('sdk-absent','complete'):
            need(pending is None and state['queries'] and state['queries'][-1]['status']=='absent')
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();self.flow.clock();self.base._candidate_guard(complete=True)
        need(same(self.store.read(),self.previous) and same(self.process.store.read(),self.process.previous)
            and same(self.flow.store.read(),self.flow.previous))
        self.process.originals_unchanged()
        if self.state is not None:
            current=self.base.read_session(self.flow.selector)
            need(same(current,self.state['sdkOriginal']) or current is None and self.state['phase'] in ('sdk-absent','complete'))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def os_current(self):
        reader=IOSGraphicsRuntime._retired_process_observer(self.flow.runtime,self.flow.selector,self.binding,self.process.state['source'])
        original=reader.read();need(absent(original));return original,deepcopy(reader.acquisition)

    def prepare(self):
        self.bound();need(self.state is None);self.process.verify()
        runtime=self.flow.runtime;_client,session,sdk,target,scope=runtime._existing(self.flow.selector)
        need(session==self.binding['sessionId'] and same(scope,{key:item for key,item in self.binding.items() if key!='processIdentity'}))
        installed=self.base._binding_store(self.flow.selector).read();need(installed is not None)
        original,receipt=self.os_current()
        self.state=dict(phase='prepared',sdkOriginal=deepcopy(sdk),installedOriginal=deepcopy(installed),
            osOriginal=original,osAcquisition=receipt,queries=[],pending=None,deleteReturned=False);self.save()

    def query(self):
        self.bound();need(self.state['phase'] in ('prepared','delete-issued'))
        if self.state['pending'] is not None:
            self.state['queries'].append(dict(index=self.state['pending'],status='abandoned',acquisition=None))
            self.state['pending']=None;self.save()
        need(len(self.state['queries'])<64);self.state['pending']=len(self.state['queries'])+1;self.save()
        target=self.base._retired_candidate_scope(self.flow.selector,{key:item for key,item in self.binding.items() if key!='processIdentity'})
        client=backend.WebDriver(target['serverUrl']);epoch,mono=self.flow.epoch_ms(),self.flow.monotonic();status='present'
        with transport_scope(self.bound):
            self.bound()
            try:client.call('GET','/session/'+self.binding['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404);status='absent'
        clock=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=self.flow.epoch_ms(),hostBeforeMonotonic=mono,hostAfterMonotonic=self.flow.monotonic())
        self.query_clock(clock);self.state['queries'].append(dict(index=self.state['pending'],status=status,acquisition=clock));self.state['pending']=None
        if status=='absent':self.state['phase']='sdk-absent'
        self.save();return status=='absent'

    def fresh(self):
        self.bound();clock=self.state['osAcquisition'];epoch,mono=self.flow.epoch_ms(),self.flow.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and mono-clock['hostBeforeMonotonic']<1.5
            and abs(epoch-clock['hostBeforeEpochMs']-(mono-clock['hostBeforeMonotonic'])*1000)<=250)

    def finish(self):
        self.bound()
        if self.state is None:self.prepare()
        self.process.verify()
        if self.state['phase']=='complete':return self.historical()
        if self.state['phase'] in ('prepared','delete-issued') and not self.query():
            need(self.state['phase']=='prepared')
            original,clock=self.os_current();self.state.update(phase='delete-issued',osOriginal=original,osAcquisition=clock);self.save()
            target=self.base._retired_candidate_scope(self.flow.selector,{key:item for key,item in self.binding.items() if key!='processIdentity'})
            client=backend.WebDriver(target['serverUrl'])
            with transport_scope(self.fresh):
                self.fresh()
                try:client.call('DELETE','/session/'+self.binding['sessionId'])
                except backend.WebDriverRequestError as error:need(error.status==404)
            self.state['deleteReturned']=True;self.save();need(self.query())
        need(self.state['phase']=='sdk-absent');sdk=self.state['sdkOriginal'];current=self.base.read_session(self.flow.selector)
        if current is not None:
            need(same(current,sdk));PrivateFeatureState(self.flow.runtime.state_path(self.flow.selector)).discard(sdk)
        store=self.base._binding_store(self.flow.selector);installed=store.read()
        if installed is not None:
            need(same(cleanup_record(self.state['installedOriginal'],installed),installed));store.discard(installed)
        self.state['phase']='complete';self.save();return self.historical()

    def historical(self):
        self.bound();self.decode(self.previous);self.process.verify();need(self.state['phase']=='complete'
            and self.base.read_session(self.flow.selector) is None and self.base._binding_store(self.flow.selector).read() is None)
        return deepcopy(self.previous)
