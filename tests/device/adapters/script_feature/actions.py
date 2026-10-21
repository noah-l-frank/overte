"""One-send normal Script input with original native barriers and ownership."""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# Platform input and clocks are supplied by the owning runtime.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import hashlib
import re

from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_script_observation import validate as validate_execution
from adapters.native_script_files import originals
from adapters.token_script_file_ui import file_url
from adapters.restart_inputs import validate_native_restart
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments, identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.measurements import fixture_scope

VERSION = 1


class ScriptActions:
    """Input acknowledgments only; fresh five-source observations stay separate.

    Failed ordinary delivery stays issued. Only the existing explicit restart
    protocol may resume an issued input from original OS/native evidence.
    """
    def __init__(self, adapter, selector, run, fixture_url, *, monotonic=time.monotonic):
        identifier(run); fixture_scope(run,fixture_url)
        self.adapter,self.selector,self.run,self.fixture_url=adapter,selector,run,fixture_url
        self.monotonic=monotonic
        self.store=PrivateFeatureState(adapter.state_path(selector).with_name('script-feature-actions.json'))
        self.lock=ScriptSourceLock(adapter.state_path(selector).with_name('script-feature-sources.lock'))
        self.previous=None;self.state=None

    def load(self):
        value=self.store.read()
        if value is None:
            self.previous=self.state=None
            return None
        exact(value,{'scriptActionVersion','sourceKind','runId','payload'})
        need(type(value['scriptActionVersion']) is int and value['scriptActionVersion']==VERSION
             and value['sourceKind']=='script-feature-actions' and value['runId']==self.run)
        rows=unpack(value['payload']);need(len(rows)==1)
        state=rows[0]
        exact(state,{'binding','nativeInstance','fixtureUrl','directory','fileOwner','phase','staged',
                     'tickets','current','lastRestart'})
        context(state['binding'])
        need(state['fixtureUrl']==self.fixture_url and state['phase'] in ('preparing','ready','issued','acknowledged')
             and type(state['staged']) is bool and type(state['tickets']) is list and len(state['tickets'])<=256)
        need(len(set(identifier(ticket) for ticket in state['tickets']))==len(state['tickets']))
        if state['phase']=='preparing':
            need(state['nativeInstance'] is None and state['directory'] is None and state['fileOwner'] is None
                 and state['current'] is None and not state['staged'] and not state['tickets'])
        else:
            identifier(state['nativeInstance'])
            need(file_url(state['directory']).endswith('/feature-script-'+self.run))
            owner=state['fileOwner']
            exact(owner,{'contractVersion','runId','ownerToken','binding','hashes'})
            need(type(owner['contractVersion']) is int and owner['contractVersion']==1
                 and owner['runId']==self.run and type(owner['ownerToken']) is str
                 and re.fullmatch('[0-9a-f]{64}',owner['ownerToken']) is not None
                 and same(context(owner['binding']),state['binding'])
                 and owner['hashes']=={name:hashlib.sha256(raw).hexdigest() for name,raw in originals(self.run).items()})
        current=state['current']
        if current is not None:
            exact(current,{'arguments','binding','barrier','stageAttempted','confirmed','receipt'})
            call=arguments('feature.scripts.act',current['arguments'])
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url
                 and call['ticket']==state['tickets'][-1]
                 and type(current['stageAttempted']) is bool and type(current['confirmed']) is bool)
            context(current['binding'])
            before=current['barrier']
            validate_execution(before,before.get('requestId'),before.get('processId'),before.get('capturedEpochMs'))
            need(current['binding']['processIdentity'].split(':')[0]==str(before['processId'])
                 and before['source'].get('effectSourceVersion')==1
                 and before['source'].get('sourceIdentityVersion')==1
                 and before['source'].get('loadSourceVersion')==1
                 and before['source'].get('membershipSourceVersion')==1 and before['source']['membership']['complete'])
            need(current['confirmed']==(state['phase']=='acknowledged'))
            if not current['confirmed']:need(current['receipt'] is None)
        else:need(state['phase'] in ('preparing','ready'))
        restart=state['lastRestart']
        if restart is not None:
            exact(restart,{'restartInputVersion','componentOnly','oldBinding','oldNative','phase','newBinding','newNative','ownerFiles','scriptHandoff'})
            need(type(restart['restartInputVersion']) is int and restart['restartInputVersion']==1
                 and restart['componentOnly'] is False and restart['phase']=='observed'
                 and same(context(restart['newBinding']),state['binding'])
                 and state['nativeInstance']==restart['newNative']['instance'])
            context(restart['oldBinding']);validate_native_restart(restart['oldNative'],restart['newNative'])
        self.previous,self.state=deepcopy(value),deepcopy(state)
        return deepcopy(state)

    def save(self, state):
        self.lock.assert_held()
        need(same(self.store.read(),self.previous))
        value=dict(scriptActionVersion=VERSION,sourceKind='script-feature-actions',runId=self.run,payload=pack([state]))
        self.store.write(value,self.previous)
        need(same(self.store.read(),value))
        self.previous,self.state=deepcopy(value),deepcopy(state)

    def prepare(self):
        """Reserve cleanup scope; never stage files or send feature input."""
        try:
            started=self.monotonic();need(number(started,0,1e15))
            def bound():
                now=self.monotonic();need(number(now,0,1e15) and started<=now and now-started<30)
            with self.lock.held(),self.adapter.existing_input_session(self.selector):
                bound()
                self.load()
                _ui,_observe,binding,check,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                if self.state is None:
                    need(self.adapter.script_files_store(self.selector).read() is None
                         and self.adapter.script_store(self.selector).read() is None
                         and self.adapter.script_restart_store(self.selector).read() is None
                         and self.adapter.script_restart_inputs_store(self.selector).read() is None)
                    self.save(dict(binding=deepcopy(binding),nativeInstance=None,fixtureUrl=self.fixture_url,
                        directory=None,fileOwner=None,phase='preparing',staged=False,tickets=[],current=None,lastRestart=None))
                    bound()
                need(same(binding,self.state['binding']))
                if self.state['phase']=='preparing':
                    files=self.adapter._script_files(self.selector,read_only=True)
                    if files.store.read() is None:files.reserve(self.run)
                    bound()
                    owner=files.owned();need(owner['runId']==self.run)
                    location=files.locate();need(location['exists'] is False)
                    state=deepcopy(self.state)
                    state.update(nativeInstance=files.native.instance,directory=location['directory'],
                                 fileOwner=deepcopy(owner),phase='ready')
                    check();bound();self.save(state);bound()
                bound();return deepcopy(self.state)
        except Exception:
            raise NativeUIError('Script input preparation failed; original ownership is retained') from None

    def _barrier(self):
        _ui,_observe,binding,check,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.state['binding']))
        source=self.adapter._script_execution_observer(self.selector,read_only=True)
        packet=source.read(0,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
        need(packet['instance']==self.state['nativeInstance'])
        check()
        return binding,packet

    def _deliver(self, call):
        adapter,selector=self.adapter,self.selector
        verb=call['verb']
        if verb=='restart-app':
            return adapter._script_restart(selector)
        if verb=='load-url':
            manager=adapter._script_missing_from_files(selector,self.run)
            manager.load_missing(self.fixture_url+'tickets/'+call['ticket']+'/missing.js',
                                 adapter._script_execution_observer(selector,read_only=True))
            return None
        if verb=='close':
            owned=adapter.script_store(selector).read()
            need(type(owned) is dict)
            if owned.get('sourceKind')=='feature-script-missing':
                manager=adapter._script_missing_manager(selector)
                manager.settle_missing(adapter._script_execution_observer(selector,read_only=True))
            else:manager=adapter._script_file_manager(selector,run=self.run)
            manager.close()
            return None
        if verb=='open' and not self.state['staged']:
            state=deepcopy(self.state);state['current']['stageAttempted']=True;self.save(state)
            files=adapter._script_files(selector)
            need(same(files.owned(),self.state['fileOwner']))
            need(files.stage_reserved()==self.state['directory'])
            state=deepcopy(self.state);state['staged']=True;self.save(state)
        need(self.state['staged'])
        manager=adapter._script_file_manager(selector,run=self.run)
        if verb=='open':manager.open()
        elif verb=='picker-open':manager.file_picker_open()
        elif verb=='picker-cancel':manager.file_picker_cancel()
        elif verb=='picker-accept':manager.file_picker_choose(call['inputs']['resource'])
        elif verb=='stop-owned':
            need(manager.state['source'] is not None)
            manager.stop_source(manager.state['source'])
        else:need(False)
        return None

    def act(self, call):
        try:
            call=deepcopy(arguments('feature.scripts.act',call))
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
            started=previous=self.monotonic();need(number(started,0,1e15))
            def check():
                nonlocal previous
                self.lock.assert_held()
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<30)
                previous=now
            with self.lock.held():
                self.load();need(self.state is not None and self.state['phase']!='preparing')
                old=self.state['current']
                if call['ticket'] in self.state['tickets']:
                    need(old is not None and same(old['arguments'],call))
                    if self.state['phase']=='acknowledged':
                        with self.adapter.existing_input_session(self.selector):self._barrier()
                        check()
                        return {'performed':True}
                    # Only the existing persisted one-send restart protocol may
                    # resume; no ordinary SDK/UI input is automatically replayed.
                    need(self.state['phase']=='issued' and call['verb']=='restart-app')
                    restart=self.adapter._script_restart_inputs(self.selector).read()
                    need(same(restart['oldBinding'],old['binding'])
                         and restart['oldNative']['instance']==old['barrier']['instance'])
                else:
                    need(self.state['phase'] in ('ready','acknowledged') and len(self.state['tickets'])<256)
                    with self.adapter.existing_input_session(self.selector):
                        binding,before=self._barrier()
                    state=deepcopy(self.state)
                    state.update(phase='issued',tickets=state['tickets']+[call['ticket']],current=dict(
                        arguments=call,binding=deepcopy(binding),barrier=before,stageAttempted=False,
                        confirmed=False,receipt=None))
                    check();self.save(state)
                check()
                with self.adapter.existing_input_session(self.selector):receipt=self._deliver(call)
                check()
                state=deepcopy(self.state)
                if call['verb']=='restart-app':
                    restart=self.adapter._script_restart_inputs(self.selector).read()
                    need(restart['phase']=='observed' and same(restart['oldBinding'],state['current']['binding'])
                         and type(receipt) is dict and type(receipt.get('handoff')) is dict
                         and receipt['handoff']['exit']['errorSymbol']=='ESRCH')
                    state['lastRestart']=deepcopy(restart)
                    state['binding']=deepcopy(restart['newBinding'])
                    state['nativeInstance']=restart['newNative']['instance']
                    files=self.adapter._script_files(self.selector,read_only=True)
                    state['fileOwner']=deepcopy(files.owned())
                    need(files.verify()==state['directory'])
                state['current'].update(confirmed=True,receipt=deepcopy(receipt));state['phase']='acknowledged'
                self.save(state);check()
                return {'performed':True} # Delivery only, never function/state proof.
        except Exception:
            raise NativeUIError('Script input failed; issued intent and original ownership are retained') from None
