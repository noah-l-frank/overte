"""Phone Script journey owner: ordinary inputs and independently acquired facts.

The primary and separately credentialed actor use separate durable observations.
Neither requested verbs nor stored acknowledgments are measurements.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments, identifier, result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.script_fixture import validate_status, missing_receipt
from feature_journeys.witness import Client, projection
from overte_phone_script_causality import check as causal, wait as ready
from overte_phone_script_history import pack, unpack, same, canonical, PhoneScriptHistory
from overte_phone_script_history import restore
from overte_phone_script_file_scope import join, file_cursor
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_measurements import fixture_scope, owned_tree
from overte_phone_script_measurements import compose

VERSION=1


class ScriptPhasePending(NativeUIError):
    """An actor must wait for an input transaction, never publish old facts."""


class ScriptRunRetired(ScriptPhasePending):
    def __init__(self,status):
        super().__init__('Owned Script fixture run has retired')
        self.status=deepcopy(status)


class ScriptFixtureReader:
    """Attach to the runner's existing run without registering or activating it."""
    def __init__(self, client, run, *, epoch_ms=lambda:time.time()*1000):
        need(isinstance(client,Client) and callable(epoch_ms))
        identifier(run)
        self.client,self.run,self.epoch_ms=client,run,epoch_ms
        self.fixture_url=client.url+'/runs/'+run+'/'
        fixture_scope(run,self.fixture_url)

    def read(self, previous=None):
        import secrets
        nonce=secrets.token_hex(16)
        value=self.client.request('/runs/'+self.run+'/scripts',script_nonce=nonce)
        instance=value.get('instance') if previous is None else previous['instance']
        validate_status(value,instance=instance,run=self.run,previous=previous,request_id=nonce)
        need(-250<=self.epoch_ms()-value['capturedEpochMs']<=1500)
        if not value['active']:raise ScriptRunRetired(value)
        active=self.client.request('/runs/'+self.run+'/active')
        exact(active,{'schemaVersion','runId','area','ticket','stimulus'})
        need(type(active['schemaVersion']) is int and active['schemaVersion']==1
             and active['runId']==self.run and active['area']=='scripts' and active['ticket']==value['ticket'])
        exact(active['stimulus'],{'verb','inputs'})
        ticket=identifier(active['ticket']);need(bool(value['activations']))
        stimulus=active['stimulus'];verb=stimulus['verb']
        if verb in ('baseline','cleanup'):need(stimulus['inputs']=={})
        else:arguments('feature.scripts.act',dict(contractVersion=CONTRACT_VERSION,runId=self.run,
            fixtureUrl=self.fixture_url,ticket=ticket,**stimulus))
        return deepcopy(dict(ticket=ticket,verb=verb,inputs=stimulus['inputs'],
            afterEpochMs=value['activations'][-1]['activatedEpochMs'],status=value))


class PhoneScriptFeature:
    def __init__(self,adapter,selector,source,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,ScriptFixtureReader) and role in ('primary','actor')
             and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-script-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-script-'+role+'-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-script-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))

    def _read(self,store,kind):
        value=store.read()
        if value is None:return None
        exact(value,{'scriptFeatureVersion','kind','runId','fixtureUrl','payload'})
        need(type(value['scriptFeatureVersion']) is int and value['scriptFeatureVersion']==VERSION
             and value['kind']==kind and value['runId']==self.run and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1)
        return rows[0]

    def _save(self,store,kind,state):
        self.lock.assert_held()
        old=store.read()
        # Validate existing scope before any CAS, including a fresh object.
        self._read(store,kind)
        value=dict(scriptFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,payload=pack([state]))
        store.write(value,old);need(same(store.read(),value))

    def control(self):
        value=self._read(self.store,'owner')
        if value is not None:
            exact(value,{'phase','stage','directory','fileOwner','ticket','readiness','backend','cleanupProof'})
            need(value['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned')
                 and type(value['stage']) is int and value['stage'] in (0,1)
                 and type(value['readiness']) is list and len(value['readiness'])<=64)
            need(type(value['cleanupProof']) is list and len(value['cleanupProof'])<=64)
            if value['ticket'] is not None:identifier(value['ticket'])
        return value

    def role_state(self,role=None):
        role=self.role if role is None else role;need(role in ('primary','actor'))
        store=PrivateFeatureState(self.store.path.with_name('phone-script-'+role+'-feature.json'))
        state=self._read(store,role)
        if state is None:
            return dict(phase='ready',sequence=0,stage=0,backend=None,capturedEpochMs=0,restart=None)
        exact(state,{'phase','sequence','stage','backend','capturedEpochMs','restart'})
        need(state['phase'] in ('ready','retired') and integer(state['sequence'],0,1000000000)
             and type(state['stage']) is int and state['stage'] in (0,1)
             and integer(state['capturedEpochMs']))
        if state['backend'] is not None:
            validate_status(state['backend'],instance=state['backend']['instance'],run=self.run)
        if state['stage']==0:need(state['restart'] is None)
        else:
            proof=state['restart'];exact(proof,{'oldBinding','oldFrame','exit','newBinding'})
            context(proof['oldBinding']);context(proof['newBinding'])
            from adapters.native_process_presence import validate as validate_exit
            exit=proof['exit']
            request=dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=exit['queryProcessId'])
            validate_exit(exit,request,int(proof['newBinding']['processIdentity'].split(':')[0]),exit['capturedEpochMs'])
            need(exit['presence']=='absent' and str(exit['queryProcessId'])==proof['oldBinding']['processIdentity'].split(':')[0])
        return state

    def _actions(self):
        flow=self.adapter._script_actions(self.selector,self.run,self.fixture_url)
        flow.lock=self.lock
        return flow

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            state=self.control()
            if state is None:
                # No abandoned role history may be adopted as a new run.
                need(all(self.adapter.script_history_store(self.selector,role,stage=stage).read() is None
                    and self.adapter.script_observation_store(self.selector,role,stage=stage).read() is None
                    for role in ('primary','actor') for stage in (0,1)))
                need(self.role_store.read() is None)
                state=dict(phase='preparing',stage=0,directory=None,fileOwner=None,ticket=None,readiness=[],backend=None,cleanupProof=[])
                self._save(self.store,'owner',state)
            if state['phase']=='preparing':
                actual=self._actions().prepare()
                need(actual['phase']=='ready' and not actual['staged'] and actual['lastRestart'] is None)
                state.update(phase='baseline',directory=actual['directory'],fileOwner=actual['fileOwner'])
                self._save(self.store,'owner',state)
            return deepcopy(state)

    def act(self,call):
        need(self.role=='primary')
        call=deepcopy(arguments('feature.scripts.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.lock.held():
            state=self.control();need(state['phase'] in ('baseline','active','acting'))
            active=self.source.read(state['backend'])
            need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if state['phase']=='acting':need(state['ticket']==call['ticket'])
            else:
                if state['ticket']==call['ticket']:
                    # A repeated completed call is still admitted by the input
                    # owner, but cannot rewrite or replay its original barrier.
                    return self._actions().act(call)
                state.update(phase='acting',ticket=call['ticket'],readiness=[],backend=active['status'])
                self._save(self.store,'owner',state)
            actions=self._actions();receipt=actions.act(call);actual=actions.load()
            need(actual['phase']=='acknowledged' and same(actual['current']['arguments'],call))
            stage=1 if actual['lastRestart'] is not None else 0
            need(stage>=state['stage'] and not (call['verb']=='restart-app' and state['stage']==1))
            state.update(stage=stage,fileOwner=actual['fileOwner'])
            if call['verb']!='restart-app':
                reader=self.adapter._script_execution_observer(self.selector,read_only=True)
                frames=[actual['current']['barrier']]+state['readiness']
                reader.restore_history(frames)
                def record(packet):
                    state['readiness'].append(packet)
                    self._save(self.store,'owner',state)
                ready(call,actual['current']['barrier'],actual['directory'],reader,
                    monotonic=self.monotonic,sleep=self.sleep,record=record)
            else:
                need(actual['current']['receipt']['handoff']['exit']['errorSymbol']=='ESRCH')
            state['phase']='active';self._save(self.store,'owner',state)
            return receipt

    def _restart(self,state,control,actions):
        """Each role independently observes the exit and new original sources."""
        need(state['stage']==0 and control['stage']==1 and actions['lastRestart'] is not None)
        restart=actions['lastRestart'];old=self.adapter.script_history_store(self.selector,self.role,stage=0).read()
        need(type(old) is dict and old['phase']=='ready' and old['runId']==self.run
             and same(old['binding'],restart['oldBinding']))
        frames=unpack(old['transcript']);need(bool(frames))
        last=frames[-1]
        # A role which never saw the actual pre-restart bundle cannot borrow
        # another role's running engine/effect, even from the primary handoff.
        need(last['execution']['instance']==restart['oldNative']['instance'])
        before=last['execution']['source'];directory=control['directory']
        need(any(row['url']==directory+'/script-bundle/main.js' and row['running']
                 for row in before['engines']))
        measured=compose(self.run,last['ticket'],directory,self.fixture_url,last['execution']['processId'],
            last['execution'],last['ui'],last['service'],last['lifecycle'],last['epochMs'],last['afterEpochMs'])
        original=restart['scriptHandoff']['oldNative']
        need(measured['engineInstance']==original['engineInstance'] and measured['effect'] is not None
             and measured['effect']['id']==original['effectId'] and measured['state']['companions']==['companion.js'])
        presence=self.adapter._process_presence(self.selector,read_only=True)
        exit=presence.require_absent(restart['oldNative']['pid'])
        need(exit['instance']==restart['newNative']['instance'])
        return dict(oldBinding=deepcopy(old['binding']),oldFrame=deepcopy(last),exit=exit,
                    newBinding=deepcopy(restart['newBinding']))

    def observe(self,call):
        call=arguments('feature.scripts.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        with self.lock.held():
            try:return self._observe_locked(call)
            except ScriptPhasePending as error:pending=error
        # The source lock sanitizes failures from its body. Expected phase
        # waiting is emitted only after a successful lock release.
        raise pending

    def _observe_locked(self,call):
        self.lock.assert_held()
        control=self.control()
        if control is None or control['phase'] in ('preparing','acting','cleaning'):
            raise ScriptPhasePending('Script input or cleanup transaction is incomplete')
        state=self.role_state();need(call['afterSequence']<=state['sequence'])
        if state['phase']=='retired':raise ScriptRunRetired(state['backend'])
        state['phase']='reading';self._save(self.role_store,self.role,state)
        try:active=self.source.read(state['backend'])
        except ScriptRunRetired as error:
            need(self.role=='actor' and control['phase']=='cleaned' and state['sequence']>0
                 and state['backend'] is not None and state['backend']['ticket']==control['backend']['ticket'])
            state.update(phase='retired',backend=error.status)
            self._save(self.role_store,self.role,state)
            raise
        if control['backend'] is not None:
            previous=control['backend']
            validate_status(previous,instance=previous['instance'],run=self.run)
            validate_status(active['status'],instance=previous['instance'],run=self.run,previous=previous)
        elif self.role=='primary':
            control['backend']=active['status'];self._save(self.store,'owner',control)
        actions=self._actions().load();need(actions is not None)
        if state['stage']==1:
            proof=state['restart'];restart=actions['lastRestart'];need(restart is not None)
            need(same(proof['oldBinding'],restart['oldBinding']) and same(proof['newBinding'],restart['newBinding'])
                 and proof['exit']['instance']==restart['newNative']['instance'])
        waiting=(active['verb']=='cleanup' and control['phase']!='cleaned'
            or active['verb'] not in ('baseline','cleanup') and control['ticket']!=active['ticket'])
        if waiting and self.role=='actor':
            # No native acquisition has started. Preserve the actual HTTP
            # prefix while waiting for the primary's new input transaction.
            state.update(phase='ready',backend=active['status'])
            self._save(self.role_store,self.role,state)
            raise ScriptPhasePending('Script challenge is awaiting normal input or cleanup')
        if active['verb']=='baseline':need(control['phase']=='baseline')
        elif active['verb']=='cleanup':need(control['phase']=='cleaned')
        else:
            need(control['phase']=='active' and control['ticket']==active['ticket']
                 and actions['phase']=='acknowledged')
            current=actions['current']['arguments']
            need(current['ticket']==active['ticket'] and current['verb']==active['verb']
                 and same(current['inputs'],active['inputs']))
        if state['stage']!=control['stage']:
            state['restart']=self._restart(state,control,actions)
            state['stage']=control['stage']
        fixture_state='present' if actions['staged'] and control['phase']!='cleaned' else 'absent'
        source=self.adapter._script_observation(self.selector,self.run,self.fixture_url,role=self.role,
            fixture_state=fixture_state,retired_owner=control['fileOwner'] if control['phase']=='cleaned' else None,
            stage=state['stage'],source_lock=self.lock)
        actual=source.read(active['ticket'],active['afterEpochMs'])
        measured=actual['measurement'];native=actual['sources']['execution']
        if active['verb'] not in ('baseline','cleanup','restart-app'):
            causal(actions['current']['arguments'],actions['current']['barrier'],native,
                   control['directory'],actual['sources']['epochMs'])
        if active['verb']=='restart-app':
            need(state['restart'] is not None and not measured['state']['running']
                 and measured['effect'] is None and not measured['state']['open'] and not measured['state']['picker']
                 and not any(owned_tree(event['url'],control['directory']) for event in native['source']['loads']['events']))
            restart=actions['lastRestart']
            need(native['instance']==restart['newNative']['instance']
                 and all(measured['lifecycle'][key]>=count for key,count in restart['newNative']['lifecycle'].items()))
        if measured['state']['error']=='not-found':
            need(active['verb']=='load-url')
            missing_receipt(active['status'],run=self.run,ticket=active['ticket'],fixture_url=self.fixture_url,
                after_epoch=actions['current']['barrier']['capturedEpochMs'])
        need(measured['capturedEpochMs']>=state['capturedEpochMs'])
        # Re-read the active ticket after acquisition. Old measurements are
        # never relabelled when the runner moves to another challenge.
        confirmed=self.source.read(active['status'])
        if confirmed['ticket']!=active['ticket'] and self.role=='actor':
            state.update(phase='ready',sequence=state['sequence']+1,backend=confirmed['status'],
                         capturedEpochMs=measured['capturedEpochMs'])
            self._save(self.role_store,self.role,state)
            raise ScriptPhasePending('Retired Script sample was dropped without publication')
        need(confirmed['ticket']==active['ticket'] and same(confirmed['inputs'],active['inputs'])
             and confirmed['verb']==active['verb'])
        state.update(phase='ready',sequence=state['sequence']+1,backend=confirmed['status'],
                     capturedEpochMs=measured['capturedEpochMs'])
        value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=state['sequence'],
            capturedEpochMs=measured['capturedEpochMs'],state=measured['state'],artifacts=[],
            resources=actual['resources'],lifecycle=measured['lifecycle'])
        result('feature.scripts.observe',value)
        self._save(self.role_store,self.role,state)
        return deepcopy(value)

    def _cleanup_read(self,control,active,*,absent,persist=True):
        """A failed main sample cannot prevent separately journalled cleanup.

        Retain the main failure; acquire new originals under the persisted
        cleaning intent and restore the last accepted native source prefixes.
        """
        reader=self.adapter._script_measurements(self.selector,self.run,self.fixture_url,read_only=True,
            fixture_state='absent' if absent else 'present',
            retired_owner=control['fileOwner'] if self.adapter.script_files_store(self.selector).read() is None else None)
        old=self.adapter.script_history_store(self.selector,'primary',stage=control['stage']).read()
        frames=[] if old is None else unpack(old['transcript'])
        clean=control['cleanupProof']
        frames+= [{key:value for key,value in frame.items() if key!='files'} for frame in clean]
        # Fresh main/actor verification may occur between idempotent cleanup
        # calls. Restore all originals in their acquisition order, rather than
        # appending older cleanup frames after newer main observations.
        need(all(integer(frame['execution']['sequence'],1) for frame in frames))
        frames.sort(key=lambda frame:frame['execution']['sequence'])
        restore(reader,frames)
        previous=None
        if clean:
            last=clean[-1]
            previous=file_cursor(self.run,control['directory'],reader.execution.pid,last['files'],
                last['epochMs'],last['afterEpochMs'])
        observed=self.adapter.script_observation_store(self.selector,'primary',stage=control['stage']).read()
        if observed is not None:
            cursor=observed['fileCursor']
            if previous is None or cursor['sequence']>previous['sequence']:previous=cursor
        admission=file_cursor(self.run,control['directory'],reader.execution.pid,reader.file_observation(),
            reader.lifecycle.clock_ms(),active['afterEpochMs'],previous=previous)
        reader.read(active['ticket'],active['afterEpochMs'])
        if clean:
            prefix=clean[0]['execution']['source']['loads']
            current=reader.last_sources['execution']['source']['loads']
            need(current['instance']==prefix['instance'] and current['events'][:prefix['sequence']]==prefix['events']
                 and not any(owned_tree(event['url'],control['directory']) or event['url'].startswith(self.fixture_url+'tickets/')
                     for event in current['events'][prefix['sequence']:]))
        actual=join(self.run,active['ticket'],control['directory'],self.fixture_url,reader.execution.pid,
            reader.last_sources,reader.file_observation(),reader.lifecycle.clock_ms(),active['afterEpochMs'],previous=admission)
        measured=actual['measurement']
        need(not measured['state']['running'] and measured['effect'] is None and not measured['state']['open']
             and not measured['state']['picker'] and measured['state']['error']=='none'
             and actual['resources']==([] if absent else ['file:script-fixtures']))
        frame=dict(ticket=active['ticket'],afterEpochMs=active['afterEpochMs'],
                   **deepcopy(reader.last_sources),files=reader.file_observation())
        need(len(clean)<64);control['cleanupProof'].append(frame)
        if persist:self._save(self.store,'owner',control)
        return measured

    def cleanup(self,call):
        need(self.role=='primary')
        call=arguments('feature.scripts.cleanup',call);need(call['runId']==self.run)
        self.prepare()
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            started=previous=self.monotonic();need(number(started,0,1e15))
            def bound():
                nonlocal previous
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<30);previous=now
            control=self.control();active=self.source.read(control['backend'])
            need(active['verb']=='cleanup');bound()
            if control['phase']!='cleaned':
                control.update(phase='cleaning',backend=active['status'])
                self._save(self.store,'owner',control);bound()
                owned=self.adapter.script_store(self.selector).read()
                if owned is not None:
                    if owned.get('sourceKind')=='feature-script-missing':
                        manager=self.adapter._script_missing_manager(self.selector)
                        if manager.state['loadAttempted']:
                            manager.settle_missing(self.adapter._script_execution_observer(self.selector,read_only=True))
                    else:
                        manager=self.adapter._script_file_manager(self.selector,run=self.run)
                        manager.close_dialog()
                        if manager.state['loadAttempted']:manager.stop_source(manager.state['source'])
                    manager.close();bound()
                files=self.adapter._script_files(self.selector,read_only=True)
                owner=files.owned();need(same(owner,control['fileOwner']))
                location=files.locate();need(location['directory']==control['directory'])
                exists=location['exists']
                # Both wall-clock domains must span the quiet window. A fast
                # loop or retimed cached native samples cannot establish it.
                first=self.monotonic();first_epoch=None;samples=0
                while True:
                    bound();measured=self._cleanup_read(control,active,absent=not exists);samples+=1
                    epoch=measured['capturedEpochMs'];first_epoch=epoch if first_epoch is None else first_epoch
                    if self.monotonic()-first>=3 and epoch-first_epoch>=3000 and samples>=3:break
                    self.sleep(.25)
                if exists:
                    files=self.adapter._script_files(self.selector)
                    need(same(files.owned(),owner));files.release();bound()
                else:
                    # Original locate proved absence after an uncertain or
                    # never-attempted release; no second release is sent.
                    files.store.discard(owner)
                self._cleanup_read(control,active,absent=True);bound()
                control.update(phase='cleaned',backend=active['status'])
                self._save(self.store,'owner',control)
            else:self._cleanup_read(control,active,absent=True)
            bound();return {'performed':True}

    def _retirement_paths(self):
        values=[self.adapter.script_actions_store(self.selector)]
        for role in ('primary','actor'):
            values.append(PrivateFeatureState(self.store.path.with_name('phone-script-'+role+'-feature.json')))
            for stage in (0,1):
                values.extend([self.adapter.script_history_store(self.selector,role,stage=stage),
                               self.adapter.script_observation_store(self.selector,role,stage=stage)])
        return values+[self.store] # The original owner is retired last.

    def finalize(self):
        """Retire journals only after both independent cleanup observations.

        Hashes authorize interrupted host-file retirement, never feature facts.
        Every attempt still performs a new five-source native absence check.
        """
        import hashlib
        need(self.role=='primary')
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            plan=self._read(self.retirement_store,'retirement')
            paths=self._retirement_paths()
            if plan is None:
                control=self.control();need(control is not None and control['phase']=='cleaned')
                actions=self._actions().load();need(actions is not None)
                for role in ('primary','actor'):
                    store=PrivateFeatureState(self.store.path.with_name('phone-script-'+role+'-feature.json'))
                    state=self.role_state(role)
                    need(state is not None and state['phase'] in ('ready','retired') and state['sequence']>0
                         and state['stage']==control['stage'] and state['backend']['activations'][-1]['ticket']==control['backend']['ticket'])
                    for stage in range(control['stage']+1):
                        history=self.adapter.script_history_store(self.selector,role,stage=stage)
                        binding=actions['binding'] if stage==control['stage'] else actions['lastRestart']['oldBinding']
                        archive=PhoneScriptHistory(history,binding,self.run,role,control['directory'],self.fixture_url)
                        need(bool(archive.frames))
                    observation=self.adapter.script_observation_store(self.selector,role,stage=control['stage']).read()
                    frame=archive.frames[-1]
                    actual=join(self.run,frame['ticket'],control['directory'],self.fixture_url,frame['execution']['processId'],
                        {key:value for key,value in frame.items() if key not in ('ticket','afterEpochMs')},
                        observation['fileObservation'],frame['epochMs'],frame['afterEpochMs'])
                    need(frame['ticket']==control['backend']['ticket'] and actual['resources']==[]
                         and not actual['measurement']['state']['running'] and actual['measurement']['state']['error']=='none')
                need(self.adapter.script_files_store(self.selector).read() is None
                     and self.adapter.script_store(self.selector).read() is None
                     and self.adapter.script_restart_store(self.selector).read() is None)
                restart=self.adapter._script_restart_inputs(self.selector)
                if restart.store.read() is not None:
                    binding,native=self.adapter._script_restart_source(self.selector)
                    restart.retire(binding,native)
                control=deepcopy(control)
                active=dict(ticket=control['backend']['ticket'],afterEpochMs=control['backend']['activations'][-1]['activatedEpochMs'])
                self._cleanup_read(control,active,absent=True)
                items=[]
                for store in paths:
                    value=store.read()
                    if value is not None:items.append(dict(name=store.path.name,sha256=hashlib.sha256(canonical(value)).hexdigest()))
                plan=dict(control=control,items=items,phase='verifying',verification=None)
                self._save(self.retirement_store,'retirement',plan)
            exact(plan,{'control','items','phase','verification'})
            need(plan['phase'] in ('verifying','retiring') and type(plan['items']) is list
                 and len(plan['items'])<=len(paths))
            known={store.path.name:store for store in paths};names=set()
            for item in plan['items']:
                exact(item,{'name','sha256'})
                need(item['name'] in known and item['name'] not in names)
                names.add(item['name'])
                value=known[item['name']].read()
                need(value is None or hashlib.sha256(canonical(value)).hexdigest()==item['sha256'])
            control=deepcopy(plan['control']);need(control['phase']=='cleaned')
            active=dict(ticket=control['backend']['ticket'],afterEpochMs=control['backend']['activations'][-1]['activatedEpochMs'])
            plan['phase']='verifying';self._save(self.retirement_store,'retirement',plan)
            if plan['verification'] is not None:control['cleanupProof'].append(plan['verification'])
            self._cleanup_read(control,active,absent=True,persist=False)
            plan.update(phase='retiring',verification=control['cleanupProof'][-1])
            self._save(self.retirement_store,'retirement',plan)
            for item in plan['items']:
                store=known[item['name']];value=store.read()
                need(value is None or hashlib.sha256(canonical(value)).hexdigest()==item['sha256'])
                if value is not None:store.discard(value)
            need(all(store.read() is None for store in paths))
            self.retirement_store.discard(self.retirement_store.read())
            return {'performed':True}

    def publish(self):
        """Called only in the actor process with its own publisher credential."""
        need(self.role=='actor')
        value=self.observe(dict(contractVersion=CONTRACT_VERSION,runId=self.run,afterSequence=0))
        state=self.role_state();ticket=state['backend']['ticket']
        payload=dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],
            capturedEpochMs=value['capturedEpochMs'],facts=projection('scripts',value['state']))
        try:self.source.client.request('/runs/'+self.run+'/samples',payload)
        except ValueError:
            current=self.source.read(state['backend'])
            if current['ticket']!=ticket:return None # Retired sample is dropped, never retimed/relabelled.
            raise
        return value['sequence']
