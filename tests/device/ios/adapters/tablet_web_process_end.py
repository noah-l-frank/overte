"""One normal Tablet Stop and two genuinely role-owned OS quiet histories.

The Actor opens no session and never calls Stop. It issues its own old-PID OS
queries in its existing worker process. Native held objects remain in the live
seal: OS absence is a separate source, not a post-death zero native snapshot.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal as protocol
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.installed_code import source as process_source
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_process_inventory import TabletWebProcessInventory

VERSION=1


def issuer_host():return os.getpid()


def mutable_paths(feature,lock):
    """Exact local metadata scope, never a native/cleanup permission."""
    f=feature;lock.assert_held()
    result=[f.root/('tabletweb-process-end-'+f.run+'.json'),f.runtime.state_path(f.selector),f.runtime.adapter._binding_store(f.selector).path,
        f.root/('tabletweb-session-end-'+f.run+'.json'),f.root/('tabletweb-final-archive-'+f.run+'.json'),
        f.root/('tabletweb-worker-retired-'+f.run+'.json')]
    for role in protocol.ROLES:
        path=f.root/filename('tabletweb',role,0);result.append(path)
        result.extend(path.with_name(path.stem+'-'+str(index)+'.json') for index in range(1,257))
    def guard():lock.assert_held();f.clock();return True
    inventory=TabletWebProcessInventory(f.root,f.binding,f.run,lock,guard,monotonic=f.monotonic,historical=True)
    result.extend(inventory.paths());return result


class TabletWebProcessEnd:
    def __init__(self,terminal):
        from ios.adapters.tablet_web_terminal import TabletWebTerminal
        need(type(terminal) is TabletWebTerminal);self.terminal,self.feature,self.lock=terminal,terminal.feature,terminal.lock
        self.binding,self.run=deepcopy(self.feature.binding),self.feature.run;self.lock.assert_held()
        self.store=PrivateFeatureState(self.feature.root/('tabletweb-process-end-'+self.run+'.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(tabletWebProcessEndVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))
    def os_store(self,role):return PrivateFeatureState(self.feature.root/filename('tabletweb',role,0))
    def inventory_guard(self):self.lock.assert_held();self.feature.clock();return True
    def inventory_owner(self,*,historical=True):
        return TabletWebProcessInventory(self.feature.root,self.binding,self.run,self.lock,self.inventory_guard,
            monotonic=self.feature.monotonic,historical=historical)
    def mutable(self):
        return mutable_paths(self.feature,self.lock)
    def roots(self):
        roots={self.feature.root}
        if self.feature.screen is not None:roots.add(Path(self.feature.screen['artifactRoot']))
        return roots
    def inventories(self):
        value={str(root):{key:list(signature) for key,signature in EmoteOriginalLease(root,self.mutable()).rows.items()} for root in self.roots()}
        reference=self.inventory_owner(historical=False).write(value)
        self.inventory_unchanged(value);return reference
    def inventory_unchanged(self,inventories):
        need(set(inventories)=={str(root) for root in self.roots()})
        for root,rows in inventories.items():
            need(type(rows) is dict and 1<=len(rows)<50000)
            lease=object.__new__(EmoteOriginalLease);lease.root=Path(root);lease.mutable=set(self.mutable())
            lease.rows={key:tuple(signature) for key,signature in rows.items()};lease.guard()
    def originals_unchanged(self,state=None):
        state=self.state if state is None else state
        self.inventory_unchanged(self.inventory_owner().read(state['inventories']))
    def decode(self,value):
        exact(value,{'tabletWebProcessEndVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['tabletWebProcessEndVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','source','bundleId','terminalSha256','retirement','started','stopReturned','roles','inventories'})
        need(state['phase'] in ('prepared','stop-issued','complete') and type(state['stopReturned']) is bool
            and (not state['stopReturned'] or state['phase']!='prepared') and type(state['bundleId']) is str and state['bundleId'])
        process_source(state['source']);need(self.terminal.previous is not None and digest(self.terminal.previous)==state['terminalSha256'])
        exact(state['started'],{'epochMs','monotonic'});need(number(state['started']['epochMs'],1,1e15) and number(state['started']['monotonic'],0,1e15))
        self.authority(state['retirement']);exact(state['roles'],protocol.ROLES);hosts={role:set() for role in protocol.ROLES}
        self.originals_unchanged(state)
        saved=getattr(self,'state',None);self.state=state
        try:
            all_originals=[]
            for role,item in state['roles'].items():
                if item is None:need(state['phase']!='complete');continue
                exact(item,{'original','issuers','pending'});need(type(item['issuers']) is list and len(item['issuers'])<=256)
                pending=item['pending']
                if pending is not None:
                    exact(pending,{'hostProcessId'});need(type(pending['hostProcessId']) is int and pending['hostProcessId']>0)
                    hosts[role].add(pending['hostProcessId'])
                archive=None if item['original'] is None else self.os_archive(role,item['original'])
                need(archive is not None or pending is not None)
                need(len(item['issuers'])==(0 if archive is None else len(archive['records'])))
                for ordinal,issuer in enumerate(item['issuers'],1):
                    exact(issuer,{'ordinal','hostProcessId'});need(type(issuer['ordinal']) is int and issuer['ordinal']==ordinal
                        and type(issuer['hostProcessId']) is int and issuer['hostProcessId']>0);hosts[role].add(issuer['hostProcessId'])
                actual=self.os_store(role).read()
                if pending is None:need(same(actual,item['original']))
                elif actual is not None:self.os_prefix(role,item['original'],actual)
                if archive is not None:all_originals.extend(row['original'] for row in self.os_rows(role,archive) if row['mode']=='observed')
                if state['phase']=='complete':need(pending is None and archive is not None and archive['pending'] is None and archive['windows'] and archive['windows'][-1]['complete'])
            need(not hosts['primary'].intersection(hosts['actor']) and len({row['commandId'] for row in all_originals})==len(all_originals)
                and len({row['sequence'] for row in all_originals})==len(all_originals))
            if state['phase']=='prepared':need(all(item is None for item in state['roles'].values()))
        finally:self.state=saved
        return deepcopy(state)
    def authority(self,value):
        exact(value,{'tabletWebRunRetirementVersion','phase','acquisition'});need(type(value['tabletWebRunRetirementVersion']) is int and value['tabletWebRunRetirementVersion']==1)
        clock=value['acquisition'];exact(clock,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        a,b,c,d=(clock[k] for k in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'))
        need(number(a,1,1e15) and number(b,a,a+1500) and b-a<1500 and number(c,0,1e15) and number(d,c,c+1.5) and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)
        phase=value['phase'];phase_packet(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=b)
        original=self.terminal.state['description'];need(not phase['active'] and a<=phase['capturedEpochMs']<=b
            and phase['activations'] and phase['activations'][-1]['ticket']==original['ticket']
            and phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        # Bind the actual authority instance and immutable activation prefix to
        # both independently admitted source histories, not just a caller URL.
        for latest in self.terminal.phase_floors().values():
            phase_packet(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=b,previous=latest)
        return value
    def bound(self):
        f=self.feature;self.lock.assert_held();f.clock();base=f.runtime.adapter;base._candidate_guard(complete=True)
        need(same(self.store.read(),self.previous) and same(self.terminal.store.read(),self.terminal.previous))
        state=base.read_session(f.selector);target=base._target(f.selector)
        need(type(state) is dict and state.get('sessionId')==self.binding['sessionId']
            and same(base._scope(f.selector,self.binding['sessionId'],state,target),{k:v for k,v in self.binding.items() if k!='processIdentity'}))
        if self.state is not None:self.originals_unchanged()
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def prepare(self):
        self.bound();need(self.feature.role=='primary' and self.state is None);self.terminal.replay();f=self.feature
        inventory=self.inventories()
        actual=IOSGraphicsRuntime._graphics_final_source(f.runtime,f.selector,self.binding)
        reader=PhaseFixtureReader(f.client,self.run,'tablet-web',epoch_ms=f.epoch_ms,monotonic=f.monotonic)
        a,c=f.epoch_ms(),f.monotonic();phase=reader.status()
        retirement=dict(tabletWebRunRetirementVersion=1,phase=phase,acquisition=dict(hostBeforeEpochMs=a,hostAfterEpochMs=f.epoch_ms(),
            hostBeforeMonotonic=c,hostAfterMonotonic=f.monotonic()));self.authority(retirement)
        self.state=dict(phase='prepared',source=actual,bundleId=f.runtime.adapter._target(f.selector)['appId'],
            terminalSha256=digest(self.terminal.previous),retirement=retirement,started=dict(epochMs=f.epoch_ms(),monotonic=f.monotonic()),
            stopReturned=False,roles={role:None for role in protocol.ROLES},inventories=inventory);self.save()
    def send_clock(self):
        """Pure final transport guard: no recursive SDK or file read."""
        f=self.feature;f.clock();clock=self.state['retirement']['acquisition'];epoch,mono=f.epoch_ms(),f.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and mono-clock['hostBeforeMonotonic']<1.5
            and abs(epoch-clock['hostBeforeEpochMs']-(mono-clock['hostBeforeMonotonic'])*1000)<=250)
    def stop(self):
        self.bound();need(self.feature.role=='primary' and self.state is not None and self.state['phase']=='prepared');self.terminal.replay();f=self.feature;base=f.runtime.adapter
        self.send_clock();self.state['phase']='stop-issued';self.save();self.send_clock()
        outer=base._operation;need(outer in (None,'feature.tablet-web.terminal'));previous=base._session_recreation_forbidden
        base._session_recreation_forbidden=True;base._operation=None
        try:
            with transport_scope(self.send_clock):base.invoke(f.selector,'app.stop',{})
        finally:base._session_recreation_forbidden=previous;base._operation=outer
        self.state['stopReturned']=True;self.save()
    def os_archive(self,role,value):
        store=self.os_store(role);need(value is not None)
        return IOSProcessRetirement.archive(value,path=store.path,binding=self.binding,source=self.state['source'],bundle=self.state['bundleId'],
            run=self.run,role=role,stage=0,profile='tabletweb')
    def os_prefix(self,role,old,current):
        """Actual child may advance under an issued parent intent, never reset."""
        after=self.os_archive(role,current)
        if old is None:return after
        before=self.os_archive(role,old);need(after['records'][:len(before['records'])]==before['records']
            and len(after['windows'])>=len(before['windows']))
        for index,window in enumerate(before['windows']):
            actual=after['windows'][index]
            if index<len(before['windows'])-1:need(same(actual,window))
            else:need(actual['samples'][:len(window['samples'])]==window['samples'])
        return after
    def os_rows(self,role,state):
        reader=object.__new__(IOSProcessRetirement);reader.store=self.os_store(role);reader.binding=self.binding
        reader.source=self.state['source'];reader.bundle=self.state['bundleId'];reader.run=self.run;reader.role=role;reader.stage=0;reader.pid=int(self.binding['processIdentity'])
        return [reader.load(ref) for ref in state['records']]
    def advance(self,role):
        self.bound();need(role==self.feature.role and role in protocol.ROLES and self.state is not None and self.state['phase'] in ('stop-issued','complete'))
        need(self.state['phase']!='complete');own=self.state['roles'][role]
        if own is None:
            own=dict(original=None,issuers=[],pending=dict(hostProcessId=issuer_host()));self.state['roles'][role]=own;self.save()
        reader=IOSGraphicsRuntime._retired_process_observer(self.feature.runtime,self.feature.selector,self.binding,self.state['source'])
        # The genuine OS reader uses its own host clock, independently of the
        # native source that is no longer callable after process death.
        reader.epoch_ms,reader.monotonic=self.feature.epoch_ms,self.feature.monotonic
        owner=IOSProcessRetirement(self.os_store(role),reader,self.binding,self.run,role,0,self.lock,profile='tabletweb')
        def adopt():
            need(own['pending'] is not None);current=self.os_store(role).read();self.os_prefix(role,own['original'],current)
            history=self.os_archive(role,current);start=len(own['issuers'])
            own['issuers']+= [dict(ordinal=index,hostProcessId=own['pending']['hostProcessId']) for index in range(start+1,len(history['records'])+1)]
            own.update(original=deepcopy(current),pending=None);self.save()
        if own['pending'] is not None:
            # Recover only actual child originals/local abandoned-query WAL;
            # no OS read or other input is replayed by this recovery step.
            owner.recover();adopt()
        own['pending']=dict(hostProcessId=issuer_host());self.save()
        done=owner.advance();actual=owner.current();need(actual['acquisition']['hostBeforeEpochMs']>=self.state['retirement']['acquisition']['hostAfterEpochMs']);adopt()
        complete=all(item is not None and item['pending'] is None and item['original'] is not None
            and self.os_archive(name,item['original'])['windows'] and self.os_archive(name,item['original'])['windows'][-1]['complete']
            for name,item in self.state['roles'].items())
        if complete:
            need(all(absent(row['original']) for name,item in self.state['roles'].items() for row in self.os_rows(name,self.os_archive(name,item['original']))
                if row['mode']=='observed' and row['window']==len(self.os_archive(name,item['original'])['windows'])-1))
            if role=='primary':
                IOSGraphicsRuntime._graphics_final_stopped(self.feature.runtime,self.feature.selector,self.binding,self.state['source'])
                self.state['phase']='complete';self.save()
        return done
    def verify(self):
        self.lock.assert_held();need(self.previous is not None and same(self.store.read(),self.previous))
        self.state=self.decode(self.previous);need(self.state['phase']=='complete');self.terminal.replay();return deepcopy(self.previous)
    def role_os(self,role):
        self.verify();need(role in protocol.ROLES);state=self.os_archive(role,self.state['roles'][role]['original'])
        window=state['windows'][-1];rows=self.os_rows(role,state);quiet=[rows[index-1] for index in window['samples'][window['start']:]]
        need(len(quiet)>=3 and all(row['mode']=='observed' and absent(row['original']) for row in quiet));first,last=quiet[0],quiet[-1]
        value=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=self.state['source']['instance'],
            processId=int(self.binding['processIdentity']),samples=len(quiet),originalSha256=digest(dict(owner=self.os_store(role).read(),records=quiet)),
            hostAfterFirstEpochMs=first['acquisition']['hostAfterEpochMs'],hostBeforeLastEpochMs=last['acquisition']['hostBeforeEpochMs'],
            hostAfterFirstMonotonic=first['acquisition']['hostAfterMonotonic'],hostBeforeLastMonotonic=last['acquisition']['hostBeforeMonotonic'],
            osAfterFirstEpochMs=first['original']['clockAfter']['epochMs'],osBeforeLastEpochMs=last['original']['clockBefore']['epochMs'],
            osAfterFirstMonotonicMs=first['original']['clockAfter']['monotonicMs'],osBeforeLastMonotonicMs=last['original']['clockBefore']['monotonicMs'])
        protocol.os_quiet(value,self.binding['processIdentity']);return value
