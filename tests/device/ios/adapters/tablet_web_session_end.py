"""Tablet-owned once SDK deletion after both actual old-PID quiet windows.

No Navigation authority is accepted and no ordinary cleanup fallback is called.
An uncertain DELETE is reconciled solely by original GET/404 observations;
local SDK/installed metadata is removed only by exact compare-and-swap.
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
from ios.adapters.process_retirement import acquisition
from ios.adapters.retired_process import validate as os_packet,absent
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd

VERSION=1


class TabletWebSessionEnd:
    def __init__(self,process):
        need(type(process) is TabletWebProcessEnd);self.process,self.feature,self.lock=process,process.feature,process.lock
        self.base=self.feature.runtime.adapter;self.binding,self.run=deepcopy(process.binding),process.run
        self.lock.assert_held();process.verify()
        self.store=PrivateFeatureState(self.feature.root/('tabletweb-session-end-'+self.run+'.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(tabletWebSessionEndVersion=VERSION,binding=self.binding,runId=self.run,processOriginalSha256=digest(self.process.previous),payload=pack([state]))
    @staticmethod
    def query_clock(value):
        exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        a,b,c,d=(value[k] for k in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'))
        need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15) and number(d,c,c+1.5) and d-c<1.5
            and abs(b-a-(d-c)*1000)<=250)
    def decode(self,value):
        exact(value,{'tabletWebSessionEndVersion','binding','runId','processOriginalSha256','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['tabletWebSessionEndVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','sdkOriginal','installedOriginal','osOriginal','osAcquisition','osHistory','queries','pending','deleteReturned'})
        need(state['phase'] in ('prepared','delete-issued','sdk-absent','complete') and type(state['deleteReturned']) is bool
            and (not state['deleteReturned'] or state['phase']!='prepared'))
        installed,sdk=state['installedOriginal'],state['sdkOriginal'];scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        class Frozen:
            def read(_self):return deepcopy(installed)
        def forbidden(*_args,**_kwargs):need(False)
        record=InstalledCodeBinding(Frozen(),scope,installed['observation']['bundle'],forbidden,forbidden,forbidden).record()
        need(record is not None and record['phase']=='retired' and str(record['process']['pid'])==self.binding['processIdentity']
            and same(record['source'],self.process.state['source']) and record['observation']['bundle']['bundleId']==self.process.state['bundleId']
            and sdk.get('sessionId')==self.binding['sessionId'] and sdk.get('generation')==self.binding['generation']
            and sdk.get('targetFingerprint')==self.binding['targetFingerprint'])
        need(type(state['osHistory']) is list and 1<=len(state['osHistory'])<=4);last=self.prior_os()
        for receipt in state['osHistory']:
            exact(receipt,{'original','acquisition'});raw=receipt['original']
            os_packet(raw,dict(commandId=raw['commandId'],bundleId=self.process.state['bundleId']),int(self.binding['processIdentity']),self.process.state['source'],last['original'])
            acquisition(receipt['acquisition'],raw);need(absent(raw)
                and receipt['acquisition']['hostBeforeEpochMs']>=last['acquisition']['hostAfterEpochMs']
                and receipt['acquisition']['hostBeforeMonotonic']>=last['acquisition']['hostAfterMonotonic']);last=receipt
        need(same(state['osOriginal'],last['original']) and same(state['osAcquisition'],last['acquisition']))
        need(type(state['queries']) is list and len(state['queries'])<=64)
        previous=None
        for index,row in enumerate(state['queries'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index and row['status'] in ('present','absent','abandoned'))
            if row['status']=='abandoned':need(row['acquisition'] is None)
            else:
                self.query_clock(row['acquisition']);clock=row['acquisition']
                if previous is not None:need(clock['hostBeforeEpochMs']>=previous['hostAfterEpochMs'] and clock['hostBeforeMonotonic']>=previous['hostAfterMonotonic'])
                previous=clock
        pending=state['pending'];need(pending is None or type(pending) is int and pending==len(state['queries'])+1)
        if state['phase'] in ('sdk-absent','complete'):need(pending is None and state['queries'] and state['queries'][-1]['status']=='absent')
        return deepcopy(state)
    def bound(self):
        self.lock.assert_held();self.feature.clock();self.base._candidate_guard(complete=True)
        need(same(self.store.read(),self.previous) and same(self.process.store.read(),self.process.previous))
        self.process.originals_unchanged()
        if self.state is not None:
            current=self.base.read_session(self.feature.selector)
            need(same(current,self.state['sdkOriginal']) or current is None and self.state['phase'] in ('sdk-absent','complete'))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def os_current(self):
        reader=IOSGraphicsRuntime._retired_process_observer(self.feature.runtime,self.feature.selector,self.binding,self.process.state['source'])
        reader.epoch_ms,reader.monotonic=self.feature.epoch_ms,self.feature.monotonic
        prior=self.prior_os() if self.state is None else self.state['osHistory'][-1]
        reader.last,reader.acquisition=deepcopy(prior['original']),deepcopy(prior['acquisition'])
        raw=reader.read();need(absent(raw));return raw,deepcopy(reader.acquisition)
    def prior_os(self):
        role=self.process.state['roles']['primary'];state=self.process.os_archive('primary',role['original'])
        rows=[row for row in self.process.os_rows('primary',state) if row['mode']=='observed'];need(rows)
        return dict(original=deepcopy(rows[-1]['original']),acquisition=deepcopy(rows[-1]['acquisition']))
    def prepare(self):
        self.bound();need(self.state is None);self.process.verify()
        _client,session,sdk,_target,scope=self.feature.runtime._existing(self.feature.selector)
        need(session==self.binding['sessionId'] and same(scope,{k:v for k,v in self.binding.items() if k!='processIdentity'}))
        installed=self.base._binding_store(self.feature.selector).read();need(installed is not None)
        raw,clock=self.os_current();self.state=dict(phase='prepared',sdkOriginal=deepcopy(sdk),installedOriginal=deepcopy(installed),
            osOriginal=raw,osAcquisition=clock,osHistory=[dict(original=deepcopy(raw),acquisition=deepcopy(clock))],queries=[],pending=None,deleteReturned=False);self.save()
    def transport(self):
        target=self.base._retired_candidate_scope(self.feature.selector,{k:v for k,v in self.binding.items() if k!='processIdentity'})
        return backend.WebDriver(target['serverUrl'])
    def query(self):
        self.bound();need(self.state['phase'] in ('prepared','delete-issued'))
        if self.state['pending'] is not None:
            self.state['queries'].append(dict(index=self.state['pending'],status='abandoned',acquisition=None));self.state['pending']=None;self.save()
        need(len(self.state['queries'])<64);self.state['pending']=len(self.state['queries'])+1;self.save();client=self.transport()
        epoch,mono=self.feature.epoch_ms(),self.feature.monotonic();status='present'
        with transport_scope(self.feature.clock):
            try:client.call('GET','/session/'+self.binding['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404);status='absent'
        clock=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=self.feature.epoch_ms(),hostBeforeMonotonic=mono,hostAfterMonotonic=self.feature.monotonic())
        self.query_clock(clock);self.state['queries'].append(dict(index=self.state['pending'],status=status,acquisition=clock));self.state['pending']=None
        if status=='absent':self.state['phase']='sdk-absent'
        self.save();return status=='absent'
    def fresh(self):
        """Pure original-clock deadline immediately before the actual send."""
        self.feature.clock();clock=self.state['osAcquisition'];epoch,mono=self.feature.epoch_ms(),self.feature.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and mono-clock['hostBeforeMonotonic']<1.5
            and abs(epoch-clock['hostBeforeEpochMs']-(mono-clock['hostBeforeMonotonic'])*1000)<=250)
    def advance(self):
        self.bound();need(self.feature.role=='primary')
        if self.state is None:self.prepare()
        self.process.verify()
        if self.state['phase']=='complete':return self.historical()
        if self.state['phase'] in ('prepared','delete-issued') and not self.query():
            # An issued request can only be observed. Even an HTTP failure or
            # lost return never authorizes replaying the DELETE.
            if self.state['phase']=='delete-issued':return None
            raw,clock=self.os_current();self.state['osHistory'].append(dict(original=deepcopy(raw),acquisition=deepcopy(clock)))
            self.state.update(phase='delete-issued',osOriginal=raw,osAcquisition=clock);self.save()
            self.bound();self.fresh();client=self.transport()
            with transport_scope(self.fresh):
                try:client.call('DELETE','/session/'+self.binding['sessionId'])
                except backend.WebDriverRequestError as error:need(error.status==404)
            self.state['deleteReturned']=True;self.save()
            if not self.query():return None
        need(self.state['phase']=='sdk-absent')
        sdk=self.base.read_session(self.feature.selector)
        if sdk is not None:
            need(same(sdk,self.state['sdkOriginal']));PrivateFeatureState(self.feature.runtime.state_path(self.feature.selector)).discard(sdk)
        store=self.base._binding_store(self.feature.selector);installed=store.read()
        if installed is not None:
            need(same(cleanup_record(self.state['installedOriginal'],installed),installed));store.discard(installed)
        self.state['phase']='complete';self.save();return self.historical()
    def historical(self):
        self.bound();self.decode(self.previous);self.process.verify()
        need(self.state['phase']=='complete' and self.base.read_session(self.feature.selector) is None
            and self.base._binding_store(self.feature.selector).read() is None)
        return deepcopy(self.previous)
