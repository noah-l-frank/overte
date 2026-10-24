"""Own once-only Emote SDK deletion after independent process quiet originals.

The SDK endpoint is observed after DELETE even when the reply is lost. An
issued DELETE is never retried. No native getter or app Stop is available here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope as transport_scope
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import appium_adapter as backend
from ios.adapters.emote_operation import clock,operation
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.installed_code import InstalledCodeBinding,cleanup_record
from ios.adapters.installed_process_runtime import retired_process_observer
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent,validate as process_packet


class IOSEmoteRootedSessionEnd:
    def __init__(self,process,processes,*,peer=None):
        need(type(process) is IOSEmoteRootedProcessEnd and type(processes) is dict);exact(processes,{'primary','actor'})
        need(all(type(owner) is IOSEmoteRootedProcessEnd and owner.role==role for role,owner in processes.items())
            and processes[process.role] is process and processes['primary'].peer is processes['actor']
            and processes['primary'].archive is processes['actor'].archive)
        self.process,self.processes,self.peer=process,dict(processes),peer
        self.flow,self.runtime,self.lock=process.flow,process.runtime,process.lock
        self.base,self.binding,self.run,self.role,self.root=process.runtime.adapter,deepcopy(process.binding),process.run,process.role,process.root
        self.monotonic,self.deadline,self.last_clock=process.monotonic,None,None
        self.store=PrivateFeatureState(process.store.path.with_name('ios-emote-'+self.role+'-'+self.run+'-rooted-sdk-end.json'))
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.file_bound,self.intent,
            namespace='emote-rooted-sdk',schema_prefix='emoteRootedSDK',monotonic=self.monotonic)
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.peer_identity()

    def clock(self):return clock(self)
    def peer_identity(self):
        if self.role=='actor':need(self.peer is None);return
        need(type(self.peer) is IOSEmoteRootedSessionEnd and self.peer.process is self.process.peer
            and self.peer.runtime is self.runtime and self.peer.role=='actor')
    def envelope(self,state):
        return dict(iosEmoteRootedSDKEndVersion=1,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),
            processSha256=digest(self.process.previous),payload=pack([state]))
    def os_store(self):return PrivateFeatureState(self.store.path.with_name(filename('emote',self.role,1)))
    def os_state(self):
        value=self.os_store().read();need(value is not None)
        return IOSProcessRetirement.archive(value,path=self.os_store().path,binding=self.binding,source=self.process.state['source'],
            bundle=self.process.state['bundleId'],run=self.run,role=self.role,stage=1,profile='emote')
    def decode(self,value):
        exact(value,{'iosEmoteRootedSDKEndVersion','runId','role','binding','artifactRoot','processSha256','payload'})
        rows=unpack(value['payload']);need(type(value['iosEmoteRootedSDKEndVersion']) is int and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','records','pending','sdk','installed','osSha256','observed404'})
        need(state['phase'] in ('preparing','prepared','delete-issued','complete') and type(state['records']) is list
            and len(state['records'])<=2 and type(state['observed404']) is bool
            and state['observed404']==(state['phase']=='complete'))
        for index,ref in enumerate(state['records'],1):self.frames.expand(ref);need(ref['index']==index)
        if state['pending'] is not None:
            self.frames.original(state['pending']);need(state['phase']=='preparing' and state['pending']['index']==len(state['records'])+1)
        for key,index in (('sdk',1),('installed',2)):
            ref=state[key]
            if ref is not None:need(len(state['records'])>=index and same(ref,state['records'][index-1]))
        if state['phase']!='preparing':
            need(state['pending'] is None and state['sdk'] is not None and state['installed'] is not None)
            sdk,installed=(self.original(state[key],key) for key in ('sdk','installed'))
            scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
            class Frozen:
                def read(_self):return deepcopy(installed)
            def unavailable(*_args,**_kwargs):need(False)
            record=InstalledCodeBinding(Frozen(),scope,installed['observation']['bundle'],unavailable,unavailable,unavailable).record()
            need(record is not None and record['phase']=='retired' and same(record['source'],self.process.state['source'])
                and str(record['process']['pid'])==self.binding['processIdentity'] and same(record['scope'],scope)
                and all(same(sdk.get(key),self.binding[key]) for key in ('sessionId','generation','targetFingerprint')))
            os=self.os_state();need(digest(self.os_store().read())==state['osSha256'] and os['pending'] is None
                and os['windows'] and os['windows'][-1]['complete'])
            self.stage_link(os)
        else:need(state['osSha256'] is None)
        return deepcopy(state)
    def file_bound(self):
        self.clock();self.lock.assert_held();self.process.bound();self.peer_identity()
        need(same(self.store.read(),self.previous));return True
    def bound(self,*,writing=False):
        self.file_bound()
        if not writing:need(self.previous is None and self.state is None or self.previous is not None and same(self.state,self.decode(self.previous)))
        return True
    def save(self):
        self.bound(writing=True);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def intent(self,event,wire):
        need(event=='original' and self.state['phase']=='preparing' and wire['index']==len(self.state['records'])+1)
        self.frames.original(wire);pending=self.state['pending']
        if pending is None:need(wire['phase']=='planned')
        else:
            need(all(same(wire[key],pending[key]) for key in wire if key not in ('phase','file'))
                and (pending['phase'],wire['phase']) in (('planned','opened'),('opened','saved')))
            if pending['file'] is not None:need(same(pending['file'],wire['file']))
        self.state['pending']=deepcopy(wire);self.save()
    def original(self,ref,key):
        value=self.frames.read(self.frames.expand(ref));exact(value,{'key','value'});need(value['key']==key);return value['value']
    def retain(self,key,index,value):
        if len(self.state['records'])>=index:
            ref=self.state['records'][index-1];need(same(self.original(ref,key),value));return ref
        need(len(self.state['records'])==index-1)
        pending=self.state['pending']
        if pending is None:ref=self.frames.write(index,dict(key=key,value=deepcopy(value)))
        else:
            need(pending['phase'] in ('opened','saved') and same(self.frames.read(pending),dict(key=key,value=value)))
            ref=self.frames.compact(dict(pending,phase='saved'))
        self.state['records'].append(ref);self.state.update(pending=None);self.state[key]=ref;self.save();return ref
    def qualify(self):
        for process in self.processes.values():process.completed()
        if self.peer is not None:self.peer.completed()
    def record(self,stage,reference):
        prior=object.__new__(IOSProcessRetirement)
        prior.profile='emote';prior.store=self.process.os_store() if stage==0 else self.os_store()
        prior.binding=self.binding;prior.source=self.process.state['source'];prior.bundle=self.process.state['bundleId']
        prior.run=self.run;prior.role=self.role;prior.stage=stage;prior._archives=None;prior.pid=int(self.binding['processIdentity'])
        return prior.load(reference)
    def after_stage_zero(self,actual):
        stage0=self.process.os_state();need(stage0['windows'][-1]['complete'])
        last=self.record(0,stage0['records'][-1])
        process_packet(actual['original'],dict(bundleId=self.process.state['bundleId'],commandId=actual['original']['commandId']),
            int(self.binding['processIdentity']),self.process.state['source'],last['original'])
        need(actual['acquisition']['hostBeforeEpochMs']>=last['acquisition']['hostAfterEpochMs']
            and actual['acquisition']['hostBeforeMonotonic']>=last['acquisition']['hostAfterMonotonic'])
    def stage_link(self,state):
        rows=[self.record(1,ref) for ref in state['records']]
        observed=[row for row in rows if row['mode']=='observed'];need(observed)
        self.after_stage_zero(observed[0])
    def stage_one(self):
        reader=retired_process_observer(self.runtime,self.flow.selector,self.binding,self.process.state['source'])
        owner=IOSProcessRetirement(self.os_store(),reader,self.binding,self.run,self.role,1,self.lock,profile='emote')
        complete=owner.advance();actual=owner.current();need(absent(actual['original']))
        # Both stages retain separate actual OS originals. Their source and
        # host order cannot be replaced by the coordinator's current clock.
        self.after_stage_zero(actual)
        return bool(complete),actual,owner.previous
    def fresh(self,actual):
        receipt=actual['acquisition'];epoch,mono=self.flow.epoch_ms(),self.monotonic()
        need(number(epoch,receipt['hostAfterEpochMs'],receipt['hostBeforeEpochMs']+1500) and epoch-receipt['hostBeforeEpochMs']<1500
            and number(mono,receipt['hostAfterMonotonic'],receipt['hostBeforeMonotonic']+1.5) and mono-receipt['hostBeforeMonotonic']<1.5
            and abs(epoch-receipt['hostBeforeEpochMs']-(mono-receipt['hostBeforeMonotonic'])*1000)<=250)
    @operation(30)
    def finish(self):
        self.bound()
        if self.state is not None and self.state['phase']=='complete':self.completed();return True
        self.qualify();scope={key:item for key,item in self.binding.items() if key!='processIdentity'}
        target=self.base._retired_candidate_scope(self.flow.selector,scope)
        client=backend.WebDriver(target['serverUrl']);path='/session/'+self.binding['sessionId']
        if self.state is None:
            self.state=dict(phase='preparing',records=[],pending=None,sdk=None,installed=None,osSha256=None,observed404=False);self.save()
        if self.state['phase']=='preparing':
            sdk=self.base.read_session(self.flow.selector);installed=self.base._binding_store(self.flow.selector).read()
            need(sdk is not None and installed is not None)
            self.retain('sdk',1,sdk);self.retain('installed',2,installed)
            complete,actual,os=self.stage_one()
            if not complete:return False
            self.state.update(phase='prepared',osSha256=digest(os));self.save()
        sdk=self.original(self.state['sdk'],'sdk');installed=self.original(self.state['installed'],'installed')
        current=self.base.read_session(self.flow.selector);need(current is None or same(current,sdk))
        try:client.call('GET',path)
        except backend.WebDriverRequestError as error:need(error.status==404)
        else:
            # Issued uncertainty can observe absence only; never resend.
            need(self.state['phase']=='prepared' and same(current,sdk))
            self.qualify()
            from ios.adapters.emote_rooted_sdk_cut import IOSEmoteRootedSDKCut
            cut=IOSEmoteRootedSDKCut(self)
            # Stage-one originals may advance even if their caller loses the
            # reply. Durable preparation relinquishes the previous OS digest
            # before acquisition, without relinquishing SDK responsibility.
            self.state.update(phase='preparing',osSha256=None);self.save()
            from adapters.original_file_reads import scope as read_scope
            with read_scope(fresh=True) as reads:complete,actual,os=self.stage_one()
            if not complete:
                self.state.update(phase='preparing',osSha256=None);self.save();return False
            self.state.update(phase='delete-issued',osSha256=digest(os));self.save()
            cut.issued(reads)
            def guard():
                self.bound();cut.guard();self.fresh(actual)
                need(same(self.base.read_session(self.flow.selector),sdk)
                    and same(self.base._binding_store(self.flow.selector).read(),installed)
                    and same(self.base._retired_candidate_scope(self.flow.selector,scope),target))
                self.base._candidate_guard(complete=True)
            with transport_scope(guard):
                guard()
                try:client.call('DELETE',path)
                except backend.WebDriverRequestError as error:need(error.status==404)
            try:client.call('GET',path)
            except backend.WebDriverRequestError as error:need(error.status==404)
            else:need(False)
        actual_sdk=self.base.read_session(self.flow.selector);need(actual_sdk is None or same(actual_sdk,sdk))
        if actual_sdk is not None:PrivateFeatureState(self.runtime.state_path(self.flow.selector)).discard(actual_sdk)
        store=self.base._binding_store(self.flow.selector);actual_installed=store.read()
        if actual_installed is not None:
            need(same(cleanup_record(installed,actual_installed),actual_installed));store.discard(actual_installed)
        self.state.update(phase='complete',observed404=True);self.save();self.completed();return True
    def completed(self):
        self.bound();need(self.state is not None and self.state['phase']=='complete');self.qualify()
        need(self.base.read_session(self.flow.selector) is None and self.base._binding_store(self.flow.selector).read() is None)
        self.base._candidate_guard(complete=True);return deepcopy(self.previous)
