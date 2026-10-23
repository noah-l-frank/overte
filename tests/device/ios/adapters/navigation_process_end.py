"""One normal final Stop, then separate original OS windows for both roles.

The terminal seal retains real Qt roots. These OS originals end that process
responsibility; no native packet or post-death rendered observation is invented.
SDK deletion and the complete final archive remain separate subsequent owners.
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
from feature_journeys import terminal as protocol
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.installed_code import source as process_source
from ios.adapters.navigation_run_retirement import NavigationRunRetirement,validate as retired_authority
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent

VERSION=1
STAGE=1


class NavigationProcessEnd:
    def __init__(self,terminal):
        from ios.adapters.navigation_feature import IOSNavigationFeature
        need(type(terminal) is NavigationTerminal)
        self.terminal,self.flow,self.lock=terminal,terminal.flow,terminal.lock
        need(type(self.flow) is IOSNavigationFeature)
        self.lock.assert_held();self.flow.load();need(self.flow.state is not None
            and type(self.flow.state['stage']) is int and self.flow.state['stage'] in (0,1))
        self.stage=self.flow.state['stage']
        self.binding=deepcopy(context(self.flow.state['binding']));self.run=self.flow.run
        self.store=PrivateFeatureState(self.flow.store.path.with_name('ios-navigation-process-end.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.checked_terminal=None

    def replay_terminal(self):
        if self.checked_terminal is None:return self.terminal.replay()
        from ios.adapters.navigation_terminal_replay import NavigationTerminalReplay
        need(type(self.checked_terminal) is NavigationTerminalReplay and self.checked_terminal.terminal is self.terminal)
        return self.checked_terminal.guard()

    def envelope(self,state):
        return dict(iosNavigationProcessEndVersion=VERSION,runId=self.run,binding=self.binding,payload=pack([state]))

    def os_store(self,role):
        return PrivateFeatureState(self.store.path.with_name(filename('navigation',role,self.stage)))

    def mutable(self):
        f=self.flow;base=f.runtime.adapter
        result=[self.store.path,f.runtime.state_path(f.selector),base._binding_store(f.selector).path,
            self.store.path.with_name('ios-navigation-session-end.json'),self.store.path.with_name('ios-navigation-final-archive.json')]
        for role in protocol.ROLES:
            store=self.os_store(role);result.append(store.path)
            # Exact bounded output namespace of IOSProcessRetirement, not a
            # wildcard exception for other source or ownership carriers.
            result.extend(store.path.with_name(store.path.stem+'-'+str(n)+'.json') for n in range(1,257))
        return result

    def inventories(self):
        return {str(root):{key:list(signature) for key,signature in EmoteOriginalLease(root,self.mutable()).rows.items()}
            for root in {self.flow.root,self.flow.store.path.parent}}

    def originals_unchanged(self,state=None):
        state=self.state if state is None else state
        expected={str(self.flow.root),str(self.flow.store.path.parent)};need(set(state['inventories'])==expected)
        for root,rows in state['inventories'].items():
            need(type(rows) is dict and 1<=len(rows)<50000)
            owner=object.__new__(EmoteOriginalLease);owner.root=Path(root);owner.mutable=set(self.mutable())
            owner.rows={key:tuple(signature) for key,signature in rows.items()};owner.guard()

    def os_archive(self,role,sha,*,complete=False):
        store=self.os_store(role);value=store.read();need(value is not None and digest(value)==sha)
        decoded=IOSProcessRetirement.archive(value,path=store.path,binding=self.binding,source=self.state['source'],
            bundle=self.state['bundleId'],run=self.run,role=role,stage=self.stage,profile='navigation')
        if complete:need(decoded['pending'] is None and decoded['windows'] and decoded['windows'][-1]['complete'])
        return decoded

    def os_rows(self,role,state):
        reader=object.__new__(IOSProcessRetirement);reader.store=self.os_store(role);reader.binding=self.binding
        reader.source=self.state['source'];reader.bundle=self.state['bundleId'];reader.run=self.run
        reader.role=role;reader.stage=self.stage;reader.pid=int(self.binding['processIdentity'])
        return [reader.load(reference) for reference in state['records']]

    def decode(self,value):
        exact(value,{'iosNavigationProcessEndVersion','runId','binding','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosNavigationProcessEndVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','source','bundleId','terminalSha256','retirement','started','stopReturned','os','inventories'})
        need(state['phase'] in ('prepared','stop-issued','stopped','complete') and type(state['stopReturned']) is bool
            and (not state['stopReturned'] or state['phase']!='prepared'))
        process_source(state['source']);exact(state['started'],{'epochMs','monotonic'})
        need(number(state['started']['epochMs'],1,1e15) and number(state['started']['monotonic'],0,1e15)
            and type(state['bundleId']) is str and state['bundleId']
            and self.terminal.previous is not None and digest(self.terminal.previous)==state['terminalSha256']
            and same(self.terminal.store.read(),self.terminal.previous) and self.terminal.state['seal'] is not None)
        description=self.terminal.state['description'];protocol.description(description,area='world-navigation',run=self.run)
        from ios.adapters.navigation_terminal_resources import binding
        need(all(same(row['binding'],binding(self.binding)) for row in description['roles'].values()))
        f=self.flow
        retired_authority(state['retirement'],run=self.run,instance=f.state['providerInstance'],inputs=f.state['providerInputs'],ticket=description['ticket'])
        exact(state['os'],protocol.ROLES)
        saved=getattr(self,'state',None);self.state=state
        try:
            originals=[]
            for role,sha in state['os'].items():
                if sha is None:need(state['phase'] in ('prepared','stop-issued'))
                else:
                    history=self.os_archive(role,sha,complete=state['phase']=='complete')
                    originals.extend(row['original'] for row in self.os_rows(role,history) if row['mode']=='observed')
            # A different role wrapper/hash cannot turn one SDK original into
            # two independently issued OS observations on this shared source.
            need(len({row['commandId'] for row in originals})==len(originals)
                and len({row['sequence'] for row in originals})==len(originals))
            if state['phase']=='prepared':need(all(sha is None for sha in state['os'].values()))
            need(type(state['inventories']) is dict);self.originals_unchanged(state)
        finally:self.state=saved
        return deepcopy(state)

    def bound(self):
        f=self.flow;self.lock.assert_held();f.clock()
        need(same(self.store.read(),self.previous) and same(f.store.read(),f.previous) and same(f.state['binding'],self.binding)
            and f.state['stage']==self.stage
            and same(self.terminal.store.read(),self.terminal.previous))
        base=f.runtime.adapter;base._candidate_guard(complete=True)
        session=base.read_session(f.selector);target=base._target(f.selector)
        need(type(session) is dict and session.get('sessionId')==self.binding['sessionId']
            and same(base._scope(f.selector,self.binding['sessionId'],session,target),
                {key:value for key,value in self.binding.items() if key!='processIdentity'}))
        if self.state is not None:self.originals_unchanged()

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def prepare(self):
        self.bound();need(self.state is None);self.replay_terminal()
        f=self.flow;runtime=f.runtime
        source=IOSGraphicsRuntime._graphics_final_source(runtime,f.selector,self.binding)
        # A newly constructed finish caller has no live fixture attachment.
        # Recover its authority metadata from the fully decoded original
        # admission; the following reader still fetches fresh retired status.
        original=f.initial_owner().archive()
        f.fixture.instance=original['providerInstance'];f.fixture.inputs=deepcopy(original['providerInputs'])
        retirement=NavigationRunRetirement(f.fixture,self.terminal.state['description']['ticket']).read()
        self.state=dict(phase='prepared',source=deepcopy(source),bundleId=runtime.adapter._target(f.selector)['appId'],
            terminalSha256=digest(self.terminal.previous),retirement=retirement,
            started=dict(epochMs=f.epoch_ms(),monotonic=f.monotonic()),stopReturned=False,
            os={role:None for role in protocol.ROLES},inventories=self.inventories())
        self.save()

    def input_guard(self):
        self.bound();f=self.flow;start=self.state['started'];clock=self.state['retirement']['acquisition']
        epoch,mono=f.epoch_ms(),f.monotonic()
        need(number(epoch,start['epochMs'],start['epochMs']+30000) and epoch-start['epochMs']<30000
            and number(mono,start['monotonic'],start['monotonic']+30) and mono-start['monotonic']<30
            and abs(epoch-start['epochMs']-(mono-start['monotonic'])*1000)<=250
            and number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
            and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and mono-clock['hostBeforeMonotonic']<1.5)

    def stop(self):
        self.bound();need(self.state is not None and self.state['phase']=='prepared');self.replay_terminal()
        f=self.flow;base=f.runtime.adapter
        need(same(IOSGraphicsRuntime._graphics_final_source(f.runtime,f.selector,self.binding),self.state['source']))
        outer=base._operation;need(outer in (None,'feature.world-navigation.terminal'))
        self.input_guard();self.state['phase']='stop-issued';self.save()
        # The canonical lifecycle owns actual terminateApp and installed-code
        # retirement. A lost return never authorizes another Stop here.
        previous=base._session_recreation_forbidden;base._session_recreation_forbidden=True;base._operation=None
        try:
            with transport_scope(self.input_guard):
                self.input_guard();base.invoke(f.selector,'app.stop',{})
        finally:base._session_recreation_forbidden=previous;base._operation=outer
        self.state['stopReturned']=True;self.save()

    def advance(self):
        self.bound();need(self.state is not None and self.state['phase'] in ('stop-issued','stopped','complete'))
        f=self.flow;done=True;all_absent=True
        for role in protocol.ROLES:
            reader=IOSGraphicsRuntime._retired_process_observer(f.runtime,f.selector,self.binding,self.state['source'])
            owner=IOSProcessRetirement(self.os_store(role),reader,self.binding,self.run,role,self.stage,self.lock,profile='navigation')
            complete=owner.advance();actual=owner.current()
            need(actual['acquisition']['hostBeforeEpochMs']>=self.state['retirement']['acquisition']['hostAfterEpochMs'])
            all_absent=all_absent and absent(actual['original']);done=done and complete
            self.state['os'][role]=digest(owner.previous);self.save()
        if all_absent:
            IOSGraphicsRuntime._graphics_final_stopped(f.runtime,f.selector,self.binding,self.state['source'])
            self.state['phase']='complete' if done else 'stopped';self.save()
        return done

    def verify(self):
        """Pure original graph/OS replay, including after the SDK is gone."""
        self.lock.assert_held();need(self.previous is not None and same(self.store.read(),self.previous))
        self.state=self.decode(self.previous);need(self.state['phase']=='complete');self.replay_terminal();return deepcopy(self.previous)

    def role_os(self,role):
        self.verify();need(role in protocol.ROLES)
        state=self.os_archive(role,self.state['os'][role],complete=True);store=self.os_store(role)
        reader=object.__new__(IOSProcessRetirement);reader.store=store;reader.binding=self.binding;reader.source=self.state['source']
        reader.bundle=self.state['bundleId'];reader.run=self.run;reader.role=role;reader.stage=self.stage;reader.pid=int(self.binding['processIdentity'])
        window=state['windows'][-1];rows=[reader.load(state['records'][n-1]) for n in window['samples'][window['start']:]]
        need(len(rows)>=3 and all(row['mode']=='observed' for row in rows));a,b=rows[0],rows[-1]
        value=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=self.state['source']['instance'],
            processId=int(self.binding['processIdentity']),samples=len(rows),originalSha256=digest(dict(owner=store.read(),records=rows)),
            hostAfterFirstEpochMs=a['acquisition']['hostAfterEpochMs'],hostBeforeLastEpochMs=b['acquisition']['hostBeforeEpochMs'],
            hostAfterFirstMonotonic=a['acquisition']['hostAfterMonotonic'],hostBeforeLastMonotonic=b['acquisition']['hostBeforeMonotonic'],
            osAfterFirstEpochMs=a['original']['clockAfter']['epochMs'],osBeforeLastEpochMs=b['original']['clockBefore']['epochMs'],
            osAfterFirstMonotonicMs=a['original']['clockAfter']['monotonicMs'],osBeforeLastMonotonicMs=b['original']['clockBefore']['monotonicMs'])
        protocol.os_quiet(value,self.binding['processIdentity']);return value
