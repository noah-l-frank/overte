"""Canonical paired Graphics finalization followed by SDK-only session deletion.

The normal finalizer owns the only Stop. This transaction retains responsibility
across lost DELETE results; historical receipts never become current UI facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceBusy
from feature_journeys.contract import identifier
from ios.adapters import appium_adapter as backend
from ios.adapters.graphics_configuration import settings
from ios.adapters.graphics_finalization import IOSGraphicsFinalization
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.adapters.installed_code import cleanup_record,InstalledCodeBinding
from ios.adapters.process_retirement import acquisition
from ios.adapters.retired_process import validate as validate_process,absent

VERSION=1


class IOSGraphicsSessionRetirement:
    @classmethod
    def from_receipt(cls,runtime,selector,value):
        from feature_journeys.witness import Client
        run=identifier(value['runId']);suffix='/runs/'+run+'/'
        need(type(value['fixtureUrl']) is str and value['fixtureUrl'].endswith(suffix))
        class Historical(Client):
            def request(self,*_args,**_kwargs):need(False)
        client=Historical(value['fixtureUrl'][:-len(suffix)],'0'*32)
        return cls(runtime,selector,client,{key:value[key] for key in ('artifactRoot','imagePolicy')},value)

    def __init__(self,runtime,selector,client,selected,original,*,sleep=time.sleep):
        self.runtime,self.base,self.selector=runtime,runtime.adapter,selector
        self.sleep=sleep
        selected=settings(selected);identifier(original['runId'])
        need(original['artifactRoot']==selected['artifactRoot'] and same(original['imagePolicy'],selected['imagePolicy'])
            and original['fixtureUrl']==client.url+'/runs/'+original['runId']+'/')
        self.flow=runtime._graphics_feature(selector,original['runId'],role='primary',client=client,settings=selected)
        self.finalizer=IOSGraphicsFinalization(self.flow);self.lock=self.flow.lock
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-feature-session-retirement.json'))
        self.receipt=PrivateFeatureState(runtime.state_path(selector).with_name('ios-feature-session-retired.json'))
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,phase,scope,deletion):
        return dict(iosGraphicsSessionRetirementVersion=VERSION,runId=self.flow.run,fixtureUrl=self.flow.fixture_url,
            artifactRoot=str(self.flow.root),imagePolicy=self.flow.policy,phase=phase,scope=deepcopy(scope),deletion=deepcopy(deletion))

    def decode(self,value,*,complete=False):
        exact(value,{'iosGraphicsSessionRetirementVersion','runId','fixtureUrl','artifactRoot','imagePolicy','phase','scope','deletion'})
        need(type(value['iosGraphicsSessionRetirementVersion']) is int and value['iosGraphicsSessionRetirementVersion']==VERSION
             and value['phase'] in (('complete',) if complete else ('finalizing','prepared','delete-issued'))
             and same(value,self.envelope(value['phase'],value['scope'],value['deletion'])))
        scope=value['scope'];exact(scope,{'sourceRevision','artifactSha256','sessionId','generation','targetFingerprint'})
        from adapters.normal_feature_state import context
        context(dict(scope,processIdentity='1'))
        deletion=None if value['deletion'] is None else self.deletion(value['deletion'])
        if value['phase']=='finalizing':need(deletion is None)
        else:
            exact(deletion,{'sdkState','installedBinding','finalReceiptSha256','original','acquisition'})
            installed=deletion['installedBinding'];need(type(installed) is dict and installed['phase']=='retired' and same(installed['scope'],scope))
            class Original:
                def read(self):return deepcopy(installed)
            def unavailable():need(False)
            InstalledCodeBinding(Original(),scope,installed['observation']['bundle'],unavailable,unavailable,unavailable).record()
            state=deletion['sdkState'];need(type(state) is dict and state.get('sessionId')==scope['sessionId']
                and state.get('generation')==scope['generation'] and state.get('targetFingerprint')==scope['targetFingerprint'])
            raw=deletion['original'];validate_process(raw,dict(bundleId=installed['observation']['bundle']['bundleId'],commandId=raw['commandId']),
                installed['process']['pid'],installed['source']);acquisition(deletion['acquisition'],raw);need(absent(raw))
        return deepcopy(value)

    def deletion(self,value):
        exact(value,{'sdkState','installedBinding','finalReceiptSha256','original','acquisition'})
        return {key:(item if key=='finalReceiptSha256' else self.finalizer.load(item)) for key,item in value.items()}

    def save(self,value):
        self.lock.assert_held();self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.state=deepcopy(value)

    def local_scope(self,state):
        target=self.base._target(self.selector)
        return self.base._scope(self.selector,state['sessionId'],state,target)

    def validate_final(self):
        receipt=self.finalizer.receipt_store().read();need(receipt is not None)
        plan=self.finalizer.validate_receipt(receipt)
        need(same({k:v for k,v in plan['binding'].items() if k!='processIdentity'},self.state['scope']))
        if self.state['deletion'] is not None:
            deletion=self.deletion(self.state['deletion']);installed=deletion['installedBinding']
            need(digest(receipt)==deletion['finalReceiptSha256'] and same(plan['source'],installed['source'])
                 and plan['binding']['processIdentity']==str(installed['process']['pid']))
        return receipt,plan

    def prepare_delete(self):
        self.flow.clock()
        receipt,plan=self.validate_final()
        self.runtime._graphics_final_stopped(self.selector,plan['binding'],plan['source'])
        reader=self.runtime._retired_process_observer(self.selector,plan['binding'],plan['source']);raw=reader.read();need(absent(raw))
        state=self.base.read_session(self.selector);need(same(self.local_scope(state),self.state['scope']))
        installed=self.base._binding_store(self.selector).read();need(installed is not None and installed['phase']=='retired'
            and same(installed['scope'],self.state['scope']) and same(installed['source'],plan['source']))
        # Preserve original bounded documents separately. A large valid SDK or
        # recovered installed-code record must not overflow the parent journal.
        deletion={key:self.finalizer.retain('session-'+key.lower(),value) for key,value in
                  dict(sdkState=state,installedBinding=installed,original=raw,acquisition=reader.acquisition).items()}
        deletion['finalReceiptSha256']=digest(receipt)
        self.save(self.envelope('prepared',self.state['scope'],deletion))

    def delete(self):
        """One DELETE; actual SDK absence is required after ACK or uncertainty."""
        self.flow.clock();self.lock.assert_held();target=self.base._retired_candidate_scope(self.selector,self.state['scope'])
        _receipt,plan=self.validate_final()
        deletion=self.deletion(self.state['deletion']);current=self.base.read_session(self.selector)
        if current is not None:
            need(same(current,deletion['sdkState']) and same(self.local_scope(current),self.state['scope']))
            client=backend.WebDriver(target['serverUrl']);session=current['sessionId']
            try:client.call('GET','/session/'+session)
            except backend.WebDriverRequestError as error:
                need(error.status==404) # Actual old SDK absence after unknown DELETE.
            else:
                need(self.state['phase']=='prepared')
                # The existing SDK is still usable: obtain a new original OS
                # absence and exact process-source admission before deletion.
                self.runtime._graphics_final_stopped(self.selector,plan['binding'],plan['source'])
                reader=self.runtime._retired_process_observer(self.selector,plan['binding'],plan['source']);need(absent(reader.read()))
                need(same(self.base.read_session(self.selector),current))
                self.flow.clock()
                intent=deepcopy(self.state['deletion'])
                for key,value in dict(original=reader.last,acquisition=reader.acquisition).items():
                    intent[key]=self.finalizer.retain('session-'+key,value)
                self.save(self.envelope('delete-issued',self.state['scope'],intent))
                try:client.call('DELETE','/session/'+session)
                except backend.WebDriverRequestError as error:need(error.status==404)
                # An ACK cannot replace actual SDK absence. Once issued, an
                # ignored/lost DELETE is only observed; it is never resent.
                try:client.call('GET','/session/'+session)
                except backend.WebDriverRequestError as error:need(error.status==404)
                else:need(False)
            need(same(self.base.read_session(self.selector),current))
            self.flow.clock()
            PrivateFeatureState(self.runtime.state_path(self.selector)).discard(current)
        else:
            client=backend.WebDriver(target['serverUrl'])
            try:client.call('GET','/session/'+deletion['sdkState']['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404)
            else:need(False)
        need(self.base.read_session(self.selector) is None)
        installed_store=self.base._binding_store(self.selector);installed=installed_store.read()
        if installed is not None:
            need(same(cleanup_record(deletion['installedBinding'],installed),installed));installed_store.discard(installed)
        self.base._candidate_guard(complete=True)
        completed=self.envelope('complete',self.state['scope'],self.state['deletion']);self.decode(completed,complete=True)
        archive=PrivateFeatureState(self.flow.root/('graphics-session-retired-'+self.flow.run+'.json'))
        previous=archive.read()
        if previous is None:archive.write(completed,None)
        else:need(same(previous,completed))
        # This pointer is historical only. The immutable per-run original stays
        # in the artifact root if a later session replaces the local pointer.
        previous=self.receipt.read()
        if not same(previous,completed):self.receipt.write(completed,previous)
        self.store.discard(self.previous);self.previous=self.state=None
        return {'cleaned':True}

    def finalize(self):
        started=self.flow.clock();outer=self.flow.deadline;self.flow.deadline=started+60 if outer is None else min(outer,started+60)
        try:
            def start():
                if self.state is None:
                    state=self.base.read_session(self.selector);need(state is not None)
                    self.save(self.envelope('finalizing',self.local_scope(state),None))
            self.with_lock(start)
            while self.state['phase']=='finalizing':
                self.flow.clock();done=False
                try:done=self.finalizer.step()
                except (ScriptSourceBusy,GraphicsPhasePending):pass
                if done:
                    self.with_lock(self.prepare_delete)
                else:self.sleep(.25)
            return self.with_lock(self.delete)
        finally:self.flow.deadline=outer

    def with_lock(self,function):
        """Retry only actual entry contention under the existing whole budget."""
        for attempt in range(241):
            self.flow.clock();entered=False
            try:
                with self.lock.held():
                    entered=True;result=function();self.flow.clock();return result
            except ScriptSourceBusy:
                # A body may already own input responsibility. Never replay it
                # merely because an inner source reports unavailable/busy.
                if entered:raise
                self.flow.clock();need(attempt<240);self.sleep(.025)
        need(False)

    def historical(self,value):
        """Only an absent SDK/binding may reuse an original completed receipt."""
        with self.lock.held():
            self.base._candidate_guard(complete=True);self.state=self.decode(value,complete=True)
            self.base._retired_candidate_scope(self.selector,self.state['scope'])
            need(self.store.read() is None and self.base.read_session(self.selector) is None
                 and self.base._binding_store(self.selector).read() is None)
            self.validate_final()
            archive=PrivateFeatureState(self.flow.root/('graphics-session-retired-'+self.flow.run+'.json')).read()
            need(same(archive,value));return {'cleaned':True}
