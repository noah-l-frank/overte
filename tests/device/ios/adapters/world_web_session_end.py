"""SDK-only deletion after World scene/OS originals; never a second app Stop.

A lost DELETE is resolved by GET only. Ordinary cleanup fallback termination is
not used. Private immutable originals retain the actual SDK/installed/OS scope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import same
from ios.adapters import appium_adapter as backend
from ios.adapters.installed_code import InstalledCodeBinding,cleanup_record
from ios.adapters.process_retirement import acquisition
from ios.adapters.retired_process import validate as process_packet,absent
from ios.adapters.world_web_api_clock import check,operation

KEYS={'sdk-state','installed-binding','os-original','os-acquisition'}


class WorldWebSessionEnd:
    @classmethod
    def archive(cls,value,*,root,binding,run,role):
        from pathlib import Path
        from types import SimpleNamespace
        from adapters.normal_feature_state import context
        from feature_journeys.contract import identifier
        need(role in ('primary','actor'));owner=object.__new__(cls)
        owner.flow=SimpleNamespace(root=Path(root));owner.binding=deepcopy(context(binding));owner.run=identifier(run);owner.role=role
        return owner.decode(value)

    def __init__(self,flow):
        from ios.adapters.world_web_feature import IOSWorldWebFeature
        need(isinstance(flow,IOSWorldWebFeature));self.flow,self.base,self.lock=flow,flow.runtime.adapter,flow.lock;self.monotonic=flow.monotonic
        self.lock.assert_held();need(flow.state is not None and flow.state['phase']=='retired')
        self.binding,self.run,self.role=deepcopy(flow.state['binding']),flow.run,flow.role
        self.store=flow.runtime._world_web_store(flow.selector,'ios-world-web-'+self.role+'-'+self.run+'-sdk-final.json')
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def ref(self,key,value=None):
        need(key in KEYS);sha=digest(value);reference=dict(key=key,sha256=sha)
        path=self.flow.root/('world-web-sdk-'+self.run+'-'+self.role+'-'+key+'-'+sha+'.json');store=PrivateFeatureState(path)
        old=store.read()
        plans=self.state['plans'];matches=[row for row in plans if row['reference']==reference]
        if not matches:
            need(len(plans)<64);plans.append(dict(reference=reference,phase='planned'));self.save()
        else:need(len(matches)==1 and matches[0]['phase'] in ('planned','saved'))
        if old is None:store.write(value,None)
        else:need(same(old,value))
        need(same(store.read(),value));next(row for row in plans if row['reference']==reference)['phase']='saved';self.save();return reference
    def load(self,reference):
        exact(reference,{'key','sha256'});need(reference['key'] in KEYS and type(reference['sha256']) is str and len(reference['sha256'])==64)
        path=self.flow.root/('world-web-sdk-'+self.run+'-'+self.role+'-'+reference['key']+'-'+reference['sha256']+'.json')
        value=PrivateFeatureState(path).read();need(value is not None and digest(value)==reference['sha256']);return value
    def envelope(self,state):return dict(iosWorldWebSDKFinalVersion=1,runId=self.run,role=self.role,binding=self.binding,state=state)
    def decode(self,value):
        exact(value,{'iosWorldWebSDKFinalVersion','runId','role','binding','state'})
        need(type(value['iosWorldWebSDKFinalVersion']) is int and same(value,self.envelope(value['state'])))
        state=value['state'];exact(state,{'phase','processSha256','sceneSha256','sdkState','installedBinding','original','acquisition','observed404','plans'})
        need(state['phase'] in ('preparing','prepared','delete-issued','complete') and type(state['observed404']) is bool)
        need(type(state['plans']) is list and len(state['plans'])<=64)
        for row in state['plans']:
            exact(row,{'reference','phase'});need(row['phase'] in ('planned','saved','absent'))
            ref=row['reference'];exact(ref,{'key','sha256'});need(ref['key'] in KEYS)
            path=self.flow.root/('world-web-sdk-'+self.run+'-'+self.role+'-'+ref['key']+'-'+ref['sha256']+'.json')
            actual=PrivateFeatureState(path).read()
            if row['phase']=='saved':need(actual is not None and digest(actual)==ref['sha256'])
            elif row['phase']=='absent':need(actual is None)
            else:need(actual is None or digest(actual)==ref['sha256'])
        if state['phase']=='preparing':return deepcopy(state)
        original=self.load(state['original']);receipt=self.load(state['acquisition']);installed=self.load(state['installedBinding']);sdk=self.load(state['sdkState'])
        scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        class Frozen:
            def read(_self):return deepcopy(installed)
        def forbidden(*_args,**_kwargs):need(False)
        record=InstalledCodeBinding(Frozen(),scope,installed['observation']['bundle'],forbidden,forbidden,forbidden).record()
        need(record is not None and record['phase']=='retired' and str(record['process']['pid'])==self.binding['processIdentity']
            and sdk.get('sessionId')==self.binding['sessionId'] and sdk.get('generation')==self.binding['generation']
            and sdk.get('targetFingerprint')==self.binding['targetFingerprint'])
        process_packet(original,dict(commandId=original['commandId'],bundleId=installed['observation']['bundle']['bundleId']),int(self.binding['processIdentity']),installed['source'])
        acquisition(receipt,original);need(absent(original))
        need(state['observed404']==(state['phase']=='complete'))
        return deepcopy(state)
    def bound(self,*,writing=False):
        if not writing:need(self.previous is None and self.state is None or self.previous is not None and same(self.state,self.decode(self.previous)))
        check();self.lock.assert_held();need(same(self.store.read(),self.previous) and same(self.flow.state['binding'],self.binding))
    def save(self):
        self.bound(writing=True);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def final_originals(self):
        from ios.adapters.world_web_process_end import WorldWebProcessEnd
        from ios.adapters.world_web_final_archive import WorldWebFinalArchive
        process=WorldWebProcessEnd(self.flow);need(process.state is not None and process.state['phase']=='complete')
        archive=WorldWebFinalArchive(self.flow.runtime._world_web_store(self.flow.selector,'ios-world-web-'+self.role+'-'+self.run+'-final.json'),
            self.flow.root,self.binding,self.run,self.role,self.lock);archive.verify()
        if self.state is not None:need(digest(process.previous)==self.state['processSha256'] and digest(archive.previous)==self.state['sceneSha256'])
        return process,archive
    def prepare(self):
        self.bound();need(self.state is None or self.state['phase']=='preparing');process,archive=self.final_originals()
        # The whole pure finalizer is rerun before obtaining this new original
        # OS observation. No old process sample is made current by metadata.
        need(self.flow.finalize(archive.verify()['phaseOriginal'])==dict(performed=True))
        runtime=self.flow.runtime;client,session,sdk,target,scope=runtime._existing(self.flow.selector)
        need(session==self.binding['sessionId'] and scope=={key:item for key,item in self.binding.items() if key!='processIdentity'})
        installed=self.base._binding_store(self.flow.selector).read();need(installed is not None and installed['phase']=='retired')
        if self.state is None:
            self.state=dict(phase='preparing',processSha256=digest(process.previous),sceneSha256=digest(archive.previous),
                sdkState=None,installedBinding=None,original=None,acquisition=None,observed404=False,plans=[]);self.save()
        actual=self.os_current(process);original=actual['original']
        self.state.update(sdkState=self.ref('sdk-state',sdk),installedBinding=self.ref('installed-binding',installed),
            original=self.ref('os-original',original),acquisition=self.ref('os-acquisition',actual['acquisition']),phase='prepared');self.save()
    def os_current(self,process):
        from ios.adapters.process_retirement import IOSProcessRetirement,filename
        reader=self.flow.runtime._retired_process_observer(self.flow.selector,self.binding,process.state['source'])
        owner=IOSProcessRetirement(PrivateFeatureState(self.store.path.with_name(filename('worldweb',self.role,1))),reader,
            self.binding,self.run,self.role,1,self.lock,profile='worldweb')
        owner.advance();actual=owner.current();need(absent(actual['original']));return actual

    def fresh(self):
        receipt=self.load(self.state['acquisition']);epoch,mono=self.flow.epoch_ms(),self.flow.monotonic()
        need(number(epoch,receipt['hostAfterEpochMs'],receipt['hostBeforeEpochMs']+1500) and epoch-receipt['hostBeforeEpochMs']<1500
            and number(mono,receipt['hostAfterMonotonic'],receipt['hostBeforeMonotonic']+1.5) and mono-receipt['hostBeforeMonotonic']<1.5
            and abs(epoch-receipt['hostBeforeEpochMs']-(mono-receipt['hostBeforeMonotonic'])*1000)<=250)
    @operation
    def finish(self):
        self.bound()
        if self.state is None or self.state['phase']=='preparing':self.prepare()
        self.final_originals();scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        target=self.base._retired_candidate_scope(self.flow.selector,scope);client=backend.WebDriver(target['serverUrl']);path='/session/'+self.binding['sessionId']
        if self.state['phase']=='complete':return self.historical()
        current=self.base.read_session(self.flow.selector);sdk=self.load(self.state['sdkState'])
        need(current is None or same(current,sdk))
        try:client.call('GET',path)
        except backend.WebDriverRequestError as error:need(error.status==404)
        else:
            # An uncertain DELETE is never repeated, even if ignored.
            need(self.state['phase']=='prepared')
            process,_archive=self.final_originals();actual=self.os_current(process);original=actual['original']
            self.state.update(original=self.ref('os-original',original),acquisition=self.ref('os-acquisition',actual['acquisition']),phase='delete-issued');self.save()
            def final_guard():self.bound();self.fresh();need(same(self.base.read_session(self.flow.selector),sdk))
            with transport_scope(final_guard):
                final_guard()
                try:client.call('DELETE',path)
                except backend.WebDriverRequestError as error:need(error.status==404)
            try:client.call('GET',path)
            except backend.WebDriverRequestError as error:need(error.status==404)
            else:need(False)
        need(self.base.read_session(self.flow.selector) is None or same(self.base.read_session(self.flow.selector),sdk))
        if current is not None:PrivateFeatureState(self.flow.runtime.state_path(self.flow.selector)).discard(sdk)
        store=self.base._binding_store(self.flow.selector);installed=store.read()
        if installed is not None:
            need(same(cleanup_record(self.load(self.state['installedBinding']),installed),installed));store.discard(installed)
        for row in self.state['plans']:
            if row['phase']=='planned':
                ref=row['reference'];path=self.flow.root/('world-web-sdk-'+self.run+'-'+self.role+'-'+ref['key']+'-'+ref['sha256']+'.json')
                value=PrivateFeatureState(path).read();need(value is None or digest(value)==ref['sha256'])
                row['phase']='absent' if value is None else 'saved'
        self.state.update(phase='complete',observed404=True);self.save();return self.historical()
    def historical(self):
        self.bound();self.decode(self.previous);need(self.state['phase']=='complete')
        self.final_originals();need(self.base.read_session(self.flow.selector) is None and self.base._binding_store(self.flow.selector).read() is None)
        self.base._candidate_guard(complete=True);return dict(cleaned=True)
