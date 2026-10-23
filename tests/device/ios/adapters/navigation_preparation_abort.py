"""Failed pre-capture Worlds ownership ends through one Stop and original OS proof.

This owner preserves the failed preparation and every partial original. It
cannot produce a Scene, restored image, successful terminal seal or Complete.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import appium_adapter as backend
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.installed_code import InstalledCodeBinding,cleanup_record,source as process_source
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.adapters.navigation_session_end import NavigationSessionEnd
from ios.adapters.process_retirement import IOSProcessRetirement,filename,acquisition
from ios.adapters.retired_process import absent,validate as os_packet

VERSION=1
ROLES=('primary','actor')
PHASES=('prepared','stop-issued','os-quiet','delete-issued','sdk-absent','failed-ended')
INPUT_PREFIXES=('ios-navigation-address-','ios-navigation-scene-inputs','ios-navigation-surface-actions',
    'ios-navigation-places-actions','ios-navigation-places-cleanup','ios-navigation-missing-actions',
    'ios-navigation-restart','ios-navigation-process-context','ios-navigation-process-return',
    'ios-navigation-restoration-','ios-navigation-terminal','ios-navigation-final-archive')
OTHER_OWNERS=('script-feature-owner.json','script-feature-retirement.json','ios-authentication-feature.json',
    'ios-authentication-retirement.json','ios-graphics-feature.json','ios-emote-primary-feature.json',
    'ios-emote-actor-feature.json','ios-create-primary-feature.json','ios-create-actor-feature.json')


class NavigationPreparationAbort:
    def parents(self):
        f=self.flow;f.lock.assert_held();need(f.role=='primary' and f.store.read() is None)
        whole=NavigationWholeFeature(f);whole.load();preparation=NavigationWholePreparation(f);preparation.load()
        need(whole.state is not None and whole.state['phase']=='preparing' and whole.state['cleanup'] is None
            and preparation.state is not None and preparation.state['phase']=='preparing')
        # A capture intent also owns a separate GPU-command/host-PNG graph.
        # That partial original graph must be independently decoded before
        # extending this earliest failure reader; no successful image is made.
        need(preparation.state['admission']['phase']=='planned'
            and all(row['phase']=='planned' for row in preparation.state['baselines'].values()))
        for role,row in preparation.state['baselines'].items():
            nonce=row['requestId'][4:]
            for name in ('ios-navigation-baseline-'+role+'-'+nonce+'.json','navigation-baseline-world-frame-'+role+'-'+nonce+'.json'):
                need(PrivateFeatureState(f.store.path.with_name(name)).read() is None)
            prefix='navigation-baseline-'+f.run+'-'+role+'-'+nonce+'-'
            need(all(not path.name.startswith(prefix) for path in f.root.iterdir()))
        for path in f.store.path.parent.iterdir():need(not path.name.startswith(INPUT_PREFIXES))
        for name in OTHER_OWNERS:need(PrivateFeatureState(f.store.path.with_name(name)).read() is None)
        return dict(whole=whole.previous,preparation=preparation.previous),context(preparation.state['binding'])

    def __init__(self,flow):
        need(type(flow) is IOSNavigationFeature);self.flow=flow;self.lock=flow.lock;self.base=flow.runtime.adapter
        self.failure,self.binding=self.parents();self.run=flow.run
        self.store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-preparation-abort.json'))
        self.previous=self.store.read();self.state=None
        if self.previous is None:
            need(all(self.os_store(role).read() is None for role in ROLES))
            self.source=deepcopy(process_source(IOSGraphicsRuntime._graphics_final_source(flow.runtime,flow.selector,self.binding)))
            self.bundle=self.base._target(flow.selector)['appId']
            self.state=dict(phase='prepared',started=dict(epochMs=flow.epoch_ms(),monotonic=flow.monotonic()),stopReturned=False,
                os={role:None for role in ROLES},inventories=self.inventories(),sdkOriginal=None,installedOriginal=None,
                beforeDelete=None,queries=[],pending=None,deleteReturned=False)
            self.save()
        else:
            self.source=deepcopy(process_source(self.previous['source']));self.bundle=self.previous['bundleId'];self.state=self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationPreparationAbortVersion=VERSION,runId=self.run,artifactRoot=str(self.flow.root),binding=self.binding,
            fixtureUrl=self.flow.client.url,source=self.source,bundleId=self.bundle,failure=deepcopy(self.failure),
            failureSha256=digest(self.failure),payload=pack([state]))

    def os_store(self,role):return PrivateFeatureState(self.flow.store.path.with_name(filename('navigation',role,0)))

    def mutable(self):
        f=self.flow;paths=[self.store.path,f.runtime.state_path(f.selector),self.base._binding_store(f.selector).path]
        for role in ROLES:
            path=self.os_store(role).path;paths.append(path)
            paths.extend(path.with_name(path.stem+'-'+str(n)+'.json') for n in range(1,257))
        return paths

    def inventories(self):
        return {str(root):{name:list(row) for name,row in EmoteOriginalLease(root,self.mutable()).rows.items()}
            for root in {self.flow.root,self.store.path.parent}}

    def originals(self,state):
        need(type(state['inventories']) is dict and set(state['inventories'])=={str(self.flow.root),str(self.store.path.parent)})
        for root,rows in state['inventories'].items():
            need(type(rows) is dict and 1<=len(rows)<50000)
            lease=object.__new__(EmoteOriginalLease);lease.root=Path(root);lease.mutable=set(self.mutable())
            lease.rows={name:tuple(row) for name,row in rows.items()};lease.guard()

    def os_archive(self,role,sha):
        store=self.os_store(role);value=store.read();need(value is not None and digest(value)==sha)
        state=IOSProcessRetirement.archive(value,path=store.path,binding=self.binding,source=self.source,bundle=self.bundle,
            run=self.run,role=role,stage=0,profile='navigation')
        reader=object.__new__(IOSProcessRetirement);reader.store=store;reader.binding=self.binding;reader.source=self.source
        reader.bundle=self.bundle;reader.run=self.run;reader.role=role;reader.stage=0;reader.pid=int(self.binding['processIdentity'])
        rows=[reader.load(ref) for ref in state['records']]
        return state,[row['original'] for row in rows if row['mode']=='observed']

    def installed(self,value):
        need(type(value) is dict)
        class Frozen:
            def read(_self):return deepcopy(value)
        def forbidden(*_args,**_kwargs):need(False)
        scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        record=InstalledCodeBinding(Frozen(),scope,value['observation']['bundle'],forbidden,forbidden,forbidden).record()
        need(record is not None and record['phase']=='retired' and record['process']['pid']==int(self.binding['processIdentity'])
            and same(record['source'],self.source) and record['observation']['bundle']['bundleId']==self.bundle)

    def decode(self,value):
        exact(value,set(self.envelope({})));rows=unpack(value['payload'])
        need(type(value['iosNavigationPreparationAbortVersion']) is int and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','started','stopReturned','os','inventories','sdkOriginal','installedOriginal','beforeDelete','queries','pending','deleteReturned'})
        need(state['phase'] in PHASES and type(state['stopReturned']) is bool and type(state['deleteReturned']) is bool)
        exact(state['started'],{'epochMs','monotonic'});need(number(state['started']['epochMs'],1,1e15) and number(state['started']['monotonic'],0,1e15))
        exact(state['os'],ROLES);originals=[]
        for role,sha in state['os'].items():
            if sha is None:need(state['phase'] in ('prepared','stop-issued'))
            else:
                os_state,packets=self.os_archive(role,sha);originals.extend(packets)
                if state['phase']!='stop-issued':need(os_state['pending'] is None and os_state['windows'] and os_state['windows'][-1]['complete'])
        need(len({p['commandId'] for p in originals})==len(originals) and len({p['sequence'] for p in originals})==len(originals))
        if state['phase']=='prepared':need(not state['stopReturned'] and all(sha is None for sha in state['os'].values()))
        if state['phase'] in ('prepared','stop-issued','os-quiet'):
            need(state['sdkOriginal'] is state['installedOriginal'] is state['beforeDelete'] is None and not state['deleteReturned']
                and state['queries']==[] and state['pending'] is None)
        else:
            sdk=state['sdkOriginal'];need(type(sdk) is dict and all(sdk.get(k)==v for k,v in self.binding.items() if k!='processIdentity'))
            self.installed(state['installedOriginal']);before=state['beforeDelete'];exact(before,{'original','acquisition'})
            packet=before['original'];os_packet(packet,dict(commandId=packet['commandId'],bundleId=self.bundle),int(self.binding['processIdentity']),self.source)
            acquisition(before['acquisition'],packet);need(absent(packet))
        need(type(state['queries']) is list and len(state['queries'])<=64)
        for index,row in enumerate(state['queries'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index and row['status'] in ('present','absent','abandoned'))
            if row['status']=='abandoned':need(row['acquisition'] is None)
            else:NavigationSessionEnd.query_clock(row['acquisition'])
        need(state['pending'] is None or type(state['pending']) is int and state['pending']==len(state['queries'])+1)
        if state['phase'] in ('sdk-absent','failed-ended'):need(state['pending'] is None and state['queries'] and state['queries'][-1]['status']=='absent')
        self.originals(state);return deepcopy(state)

    def bound(self):
        self.lock.assert_held();failure,binding=self.parents();need(same(failure,self.failure) and same(binding,self.binding) and same(self.store.read(),self.previous))
        self.base._candidate_guard(complete=True);scope={k:v for k,v in self.binding.items() if k!='processIdentity'}
        target=self.base._retired_candidate_scope(self.flow.selector,scope);need(target['appId']==self.bundle)
        sdk=self.base.read_session(self.flow.selector)
        if sdk is None:need(self.state is not None and self.state['phase'] in ('sdk-absent','failed-ended'))
        else:
            need(sdk.get('sessionId')==self.binding['sessionId'] and same(self.base._scope(self.flow.selector,self.binding['sessionId'],sdk,target),scope))
            if self.state is not None and self.state['sdkOriginal'] is not None:need(same(sdk,self.state['sdkOriginal']))
        if self.state is not None:self.originals(self.state)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def input_guard(self):
        self.bound();start=self.state['started'];epoch,mono=self.flow.epoch_ms(),self.flow.monotonic()
        need(number(epoch,start['epochMs'],start['epochMs']+30000) and epoch-start['epochMs']<30000
            and number(mono,start['monotonic'],start['monotonic']+30) and mono-start['monotonic']<30
            and abs(epoch-start['epochMs']-(mono-start['monotonic'])*1000)<=250)

    def stop(self):
        self.input_guard();need(self.state['phase']=='prepared');base=self.base;outer=base._operation
        need(outer in (None,'feature.world-navigation.cleanup') and same(IOSGraphicsRuntime._graphics_final_source(self.flow.runtime,self.flow.selector,self.binding),self.source))
        self.state['phase']='stop-issued';self.save();previous=base._session_recreation_forbidden
        base._operation=None;base._session_recreation_forbidden=True
        try:
            with transport_scope(self.input_guard):self.input_guard();base.invoke(self.flow.selector,'app.stop',{})
        finally:base._operation=outer;base._session_recreation_forbidden=previous
        self.state['stopReturned']=True;self.save()

    def process_round(self):
        self.bound();need(self.state['phase']=='stop-issued');done=True
        for role in ROLES:
            reader=IOSGraphicsRuntime._retired_process_observer(self.flow.runtime,self.flow.selector,self.binding,self.source)
            owner=IOSProcessRetirement(self.os_store(role),reader,self.binding,self.run,role,0,self.lock,profile='navigation')
            complete=owner.advance();done=complete and done;owner.current();self.state['os'][role]=digest(owner.previous);self.save()
        if done:
            IOSGraphicsRuntime._graphics_final_stopped(self.flow.runtime,self.flow.selector,self.binding,self.source)
            self.state['phase']='os-quiet';self.save()
        return done

    def query(self):
        self.bound();need(self.state['phase']=='delete-issued')
        if self.state['pending'] is not None:
            self.state['queries'].append(dict(index=self.state['pending'],status='abandoned',acquisition=None));self.state['pending']=None;self.save()
        need(len(self.state['queries'])<64);self.state['pending']=len(self.state['queries'])+1;self.save()
        target=self.base._retired_candidate_scope(self.flow.selector,{k:v for k,v in self.binding.items() if k!='processIdentity'})
        epoch,mono=self.flow.epoch_ms(),self.flow.monotonic();status='present'
        with transport_scope(self.bound):
            try:backend.WebDriver(target['serverUrl']).call('GET','/session/'+self.binding['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404);status='absent'
        clock=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=self.flow.epoch_ms(),hostBeforeMonotonic=mono,hostAfterMonotonic=self.flow.monotonic())
        NavigationSessionEnd.query_clock(clock);self.state['queries'].append(dict(index=self.state['pending'],status=status,acquisition=clock));self.state['pending']=None
        if status=='absent':self.state['phase']='sdk-absent'
        self.save();return status=='absent'

    def delete(self):
        self.bound();need(self.state['phase'] in ('os-quiet','delete-issued'))
        if self.state['phase']=='os-quiet':
            reader=IOSGraphicsRuntime._retired_process_observer(self.flow.runtime,self.flow.selector,self.binding,self.source)
            packet=reader.read();need(absent(packet));self.input_guard()
            self.state.update(phase='delete-issued',sdkOriginal=deepcopy(self.base.read_session(self.flow.selector)),
                installedOriginal=deepcopy(self.base._binding_store(self.flow.selector).read()),beforeDelete=dict(original=packet,acquisition=deepcopy(reader.acquisition)))
            self.save();target=self.base._retired_candidate_scope(self.flow.selector,{k:v for k,v in self.binding.items() if k!='processIdentity'})
            def fresh():
                self.input_guard();clock=self.state['beforeDelete']['acquisition'];epoch,mono=self.flow.epoch_ms(),self.flow.monotonic()
                need(number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
                    and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and mono-clock['hostBeforeMonotonic']<1.5)
            with transport_scope(fresh):
                fresh()
                try:backend.WebDriver(target['serverUrl']).call('DELETE','/session/'+self.binding['sessionId'])
                except backend.WebDriverRequestError as error:need(error.status==404)
            self.state['deleteReturned']=True;self.save()
        return self.query()

    def finish(self):
        self.bound()
        if self.state['phase']=='prepared':self.stop()
        while self.state['phase']=='stop-issued':
            if self.process_round():break
            self.flow.clock();self.flow.sleep(1.6)
        if self.state['phase'] in ('os-quiet','delete-issued'):need(self.delete())
        need(self.state['phase'] in ('sdk-absent','failed-ended'))
        sdk=self.base.read_session(self.flow.selector)
        if sdk is not None:need(same(sdk,self.state['sdkOriginal']));PrivateFeatureState(self.flow.runtime.state_path(self.flow.selector)).discard(sdk)
        store=self.base._binding_store(self.flow.selector);installed=store.read()
        if installed is not None:need(same(cleanup_record(self.state['installedOriginal'],installed),installed));store.discard(installed)
        self.state['phase']='failed-ended';self.save();return self.result()

    def result(self):
        self.bound();self.decode(self.previous);need(self.state['phase']=='failed-ended'
            and self.base.read_session(self.flow.selector) is None and self.base._binding_store(self.flow.selector).read() is None)
        return dict(iosNavigationPreparationAbortResultVersion=1,runId=self.run,status='failed',processEnded=True,sdkAbsent=True,
            originalsRetained=True,originalSha256=digest(self.previous))
