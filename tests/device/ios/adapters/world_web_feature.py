"""World Web on existing candidate-bound SDKs and separate original owners.

Capability activation and final SDK teardown are deliberately separate. The
actor queries the real primary SDK through its own readers and retains its own
native inventories; normalized primary publications never become actor facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
from pathlib import Path
import time
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE
from feature_journeys.witness import Client
from ios.adapters.peer_admission import admit_existing_peer,validate as peer_admission
from ios.adapters.world_web_api_clock import operation,check
from ios.adapters.world_web_construction import construct as construct_source
from ios.adapters.world_web_evidence import required as required_evidence
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.adapters.world_web_actor_retirement import WorldWebActorRetirement
from ios.adapters import world_web_factories as factories


class IOSWorldWebFeature:
    def __init__(self,runtime,selector,client,run,role,configuration,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        from ios.adapters.world_web_runtime import IOSWorldWebRuntime
        from ios.adapters.world_web_configuration import settings
        need(isinstance(runtime,IOSWorldWebRuntime) and isinstance(client,Client) and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.settings=settings(configuration,role=role,target=selector);self.root=Path(self.settings['artifactRoot']);self.policy=deepcopy(self.settings['imagePolicy']);self.origins=deepcopy(self.settings['origins'])
        self.primary_selector=selector if role=='primary' else self.settings['primaryTarget']
        self.lock=ScriptSourceLock(runtime.state_path(selector).with_name('script-feature-sources.lock'))
        self.primary_lock=self.lock if role=='primary' else ScriptSourceLock(runtime.state_path(self.primary_selector).with_name('script-feature-sources.lock'))
        self.store=runtime._world_web_store(selector,'ios-world-web-'+role+'-feature.json');self.phase=PhaseFixtureReader(client,run,'world-web',epoch_ms=epoch_ms,monotonic=monotonic)
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.previous=self.state=None
    @contextmanager
    def held(self):
        locks=[self.lock] if self.role=='primary' else sorted([self.lock,self.primary_lock],key=lambda lock:str(lock.path))
        failure=None
        with ExitStack() as stack:
            for lock in locks:stack.enter_context(lock.held())
            try:yield
            except BaseException as original:failure=original
        if failure is not None:raise failure
    def envelope(self,state):
        return dict(iosWorldWebFeatureVersion=2,runId=self.run,role=self.role,peerTarget=self.settings['actorTarget' if self.role=='primary' else 'primaryTarget'],artifactRoot=str(self.root),imagePolicy=self.policy,origins=self.origins,
            fixtureUrl=self.phase.fixture_url,payload=pack([state]))
    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is None:return
        exact(self.previous,{'iosWorldWebFeatureVersion','runId','role','peerTarget','artifactRoot','imagePolicy','origins','fixtureUrl','payload'});rows=unpack(self.previous['payload'])
        need(len(rows)==1 and same(self.previous,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','binding','primaryBinding','phaseInstance','initialTicket','actorAdmission','baseline','lease','beforeImage','images','retirement'})
        need(state['phase'] in ('baseline','ready','cleaning','cleaned','paired','retired') and type(state['images']) is list and len(state['images'])<=64
            and len(set(state['images']))==len(state['images']));context(state['binding']);context(state['primaryBinding']);identifier(state['phaseInstance']);identifier(state['initialTicket'])
        for request in state['images']+([] if state['beforeImage'] is None else [state['beforeImage']]):need(request.startswith('ios-'));identifier(request[4:])
        if self.role=='primary':peer_admission(state['actorAdmission'],state['binding'])
        else:need(state['actorAdmission'] is state['beforeImage'] is None and state['images']==[])
        self.state=deepcopy(state)
    def save(self):
        check();self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def parts(self):
        # Constructor reads belong to one synchronous, read-only assembly.
        # Each Source enters by decoding its complete actual byte graph and
        # keeps the existing identity/header/state guards through every child
        # constructor and final exit. No round escapes in the returned owners.
        with ExitStack() as construction:return self._parts(construction)
    def _parts(self,construction):
        own=self.runtime._sources(self.selector);peer=None
        source=construction.enter_context(construct_source(
            lambda:self.runtime._world_web_source_owner(self.selector,self.run,self.role,self.phase,self.lock)))
        need(own['binding']==source.binding==self.state['binding'])
        if self.role=='actor':
            peer=source;source=construction.enter_context(construct_source(
                lambda:self.runtime._world_web_source_owner(self.primary_selector,self.run,'actor-primary',self.phase,self.primary_lock)))
            need(source.binding==self.state['primaryBinding'])
        scope=self.runtime._world_web_marker(self.primary_selector,self.root,self.run,'primary',self.phase.fixture_url,self.state['initialTicket'],self.primary_lock)
        references=self.state['lease'];lease=None if references is None else WorldWebLease(scope,source,references['before'],references['after'])
        if lease is not None:construction.enter_context(lease.validation_round())
        images={}
        def sample(request):
            need(self.role=='primary')
            if request not in images:images[request]=factories.sample(self.runtime,self.selector,source,request,self.root)
            return images[request]
        history=factories.observer(self.runtime,self.selector,source,self.origins,self.role,peer=peer,lease=lease,
            sample_resolver=sample if self.role=='primary' else None,setup_scope=scope)
        actions=before=retirement=None
        if self.role=='primary':
            entity=None if lease is None else lease.packet()['returned']['returned']['entityId'];actions=factories.actions(self.runtime,self.selector,source,scope,self.origins,entity)
            before=None if self.state['beforeImage'] is None else sample(self.state['beforeImage'])
            if before is not None:
                files=factories.file_receipts(self.runtime,self.selector,source,self.root)
                if lease is not None:
                    retirement=WorldWebRetirement(self.runtime._world_web_store(self.selector,'ios-world-web-primary-retirement.json'),lease,before,files,sample,actions.inputs,self.origins,
                        sample_requests=self.state['images'],sleep=self.sleep)
                else:
                    from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
                    retirement=WorldWebSetupRetirement(self.runtime._world_web_store(self.selector,'ios-world-web-primary-setup-retirement.json'),scope,history,self.state['baseline'],
                        baseline_image=before,files=files,sample_factory=sample,sample_requests=self.state['images'],sleep=self.sleep)
        elif lease is not None:
            retirement=WorldWebActorRetirement(self.runtime._world_web_store(self.selector,'ios-world-web-actor-retirement.json'),history,sleep=self.sleep)
        elif self.state['baseline'] is not None:
            from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
            retirement=WorldWebSetupRetirement(self.runtime._world_web_store(self.selector,'ios-world-web-actor-setup-retirement.json'),scope,history,self.state['baseline'],sleep=self.sleep)
        return dict(own=own,source=source,peer=peer,scope=scope,lease=lease,history=history,actions=actions,before=before,sample=sample,retirement=retirement)
    def ensure(self):
        self.load();status=self.phase.read();need(status['status']['active'])
        if self.state is None:
            need(status['verb']=='baseline');own=self.runtime._sources(self.selector);primary=own if self.role=='primary' else self.runtime._sources(self.primary_selector)
            admission=None if self.role=='actor' else admit_existing_peer(self.runtime,self.settings['actorTarget'],own['binding'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            self.state=dict(phase='baseline',binding=deepcopy(own['binding']),primaryBinding=deepcopy(primary['binding']),phaseInstance=status['status']['instance'],initialTicket=status['ticket'],
                actorAdmission=admission,baseline=None,lease=None,beforeImage=None,images=[],retirement=None);self.save()
        need(status['status']['instance']==self.state['phaseInstance']);parts=self.parts()
        need(parts['source'].version==5 and (parts['peer'] is None or parts['peer'].version==5))
        if self.state['baseline'] is None:
            need(status['verb']=='baseline');original,_observed=parts['history'].capture();entry=parts['history'].entries()[original['reference']['index']-1]
            self.state['baseline']=deepcopy(entry['source']);self.save()
        # Legacy inventories remain historically readable. A new full run
        # must positively own real retained Script manager/picker roots before
        # any ordinary setup input can create one.
        for source in (parts['source'],parts['peer']):
            if source is None:continue
            need(source.state['records'])
            inventory=source.frame(source.state['records'][-1])['originals']['widgets'].get('scriptInventory')
            need(inventory is not None and inventory['inventoryVersion']==2)
            from adapters.script_ui_root_ownership import membership
            roots=membership(inventory,pid=source.pid);need(roots['available'] and roots['complete'] and roots['wholeTreeReady'])
        if self.role=='primary':
            if self.state['beforeImage'] is None:
                need(status['verb']=='baseline' and parts['scope'].state['phase']=='new');self.state['beforeImage']='ios-'+uuid.uuid4().hex;self.save();parts=self.parts()
            if parts['before'].state is None:parts['before'].capture(status['ticket'])
        elif self.state['lease'] is None and parts['scope'].state['phase']=='ready' and parts['scope'].state['admission'] is not None:
            after=parts['source'].capture('independent-primary-admission');WorldWebLease(parts['scope'],parts['source'],self.state['baseline'],after)
            self.state['lease']=dict(before=deepcopy(self.state['baseline']),after=after);self.state['phase']='ready';self.save();parts=self.parts()
        return parts,status
    @operation
    def act(self,call):
        call=arguments('feature.world-web.act',call);need(self.role=='primary' and call['runId']==self.run)
        with self.held():
            parts,status=self.ensure();need(status['ticket']==call['ticket'])
            from ios.adapters.world_web_restoration import original
            original(parts['before'])
            need(call['verb']=='open' or parts['lease'] is not None)
            with self.runtime.existing_input_session(self.selector):response=parts['actions'].act(call)
            if self.state['lease'] is None:
                entry=parts['actions'].state['calls'][-1];WorldWebLease(parts['scope'],parts['source'],entry['before'],entry['after'])
                self.state['lease']=dict(before=deepcopy(entry['before']),after=deepcopy(entry['after']));self.state['phase']='ready';self.save()
            return response
    def publisher(self,parts):
        need(self.role=='actor')
        return PhaseWitnessPublisher(PrivateFeatureState(self.store.path.with_name('phase-publication-world-web-'+self.run+'-actor.json')),self.state['binding'],self.phase,self.lock,parts['own']['check'],
            parts['history'].validate_original,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    @operation
    def observe(self,call):
        call=arguments('feature.world-web.observe',call);need(call['runId']==self.run)
        with self.held():
            parts,status=self.ensure()
            if status['verb']=='cleanup':
                need(parts['retirement'] is not None)
                if self.role=='actor':
                    self.actor_cleanup(parts,status)
                    publisher=self.publisher(parts);need(publisher.resolve())
                    observed,measured=parts['history'].capture();publisher.publish(observed)
                    value=measured['public'];need(value['sequence']>call['afterSequence']);return value
                with self.cleanup_originals(parts) as retirement_publisher:
                    original=self.clean_local(parts,status)
                    parts['retirement'].validate_original(original)
                    value=parts['retirement'].qualification(parts['retirement'].state)['public']
                    from ios.adapters.world_web_terminal_live import WorldWebTerminalLive
                    need(same(WorldWebTerminalLive(parts['retirement']).append(original),value))
                    need(value['sequence']>call['afterSequence']);return value
            sample=previous=None;changed=False
            if self.role=='primary' and status['verb']!='baseline':
                need(parts['lease'] is not None)
                required=required_evidence(self.run,status['verb'],status['inputs']);changed='changed' in required
                if required&{'image','changed'}:
                    previous=next((parts['sample'](request) for request in reversed(self.state['images']) if parts['sample'](request).state is not None and parts['sample'](request).state['phase']=='qualified'),None)
                    request='ios-'+uuid.uuid4().hex;self.state['images'].append(request);self.save();sample=parts['sample'](request)
            original,measured=parts['history'].capture(sample=sample,policy=self.policy,previous=previous,changed=changed)
            if self.role=='actor':
                publisher=self.publisher(parts);need(publisher.resolve());publisher.publish(original)
            value=measured['public'];need(value['sequence']>call['afterSequence']);return value
    def clean_local(self,parts,status):
        need(status['verb']=='cleanup' and parts['retirement'] is not None);self.state['phase']='cleaning';self.save()
        with self.runtime.existing_input_session(self.selector):original=parts['retirement'].cleanup(status['ticket'])
        self.state['phase']='cleaned'
        if self.role=='primary' and self.state['retirement'] is not None:
            retained=self.state['retirement'];exact(retained,{'localSha256','peerReceipt','readerOriginal'})
            measured=parts['retirement'].validate_original(original)
            need(measured['acquisition']['hostBeforeMonotonic']>=retained['peerReceipt']['acquisition']['hostAfterMonotonic']
                and measured['ticket']==retained['peerReceipt']['entry']['ticket'])
            retained['localSha256']=digest(original);self.state['phase']='paired'
        self.save();return original

    def actor_cleanup(self,parts,status):
        need(self.role=='actor')
        if self.state['retirement'] is None:
            # This is ordering metadata, never a primary native effect. The
            # actor's following acquisition independently checks actual SDK
            # originals. Publishing before primary local quiet would make the
            # immutable 1.5s receipt stale while primary is still restoring.
            primary=IOSWorldWebFeature(self.runtime,self.primary_selector,self.client,self.run,'primary',
                {key:self.settings[key] for key in ('artifactRoot','imagePolicy','origins')}|dict(actorTarget=self.selector),
                epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
            primary.lock=primary.primary_lock=self.primary_lock;primary.load()
            if primary.state is None:return False
            need(primary.state['binding']==self.state['primaryBinding']
                and peer_admission(primary.state['actorAdmission'],primary.state['binding'])==self.state['binding']
                and primary.state['phaseInstance']==self.state['phaseInstance'])
            if primary.state['phase']!='cleaned':return False
            with self.cleanup_originals(parts) as publisher:
                original=self.clean_local(parts,status);self.publish_retirement(parts,original,publisher)
        else:
            # Scene3 is once per actual cleanup ticket. Repeated ordinary
            # cleanup/observation must resolve the retained receipt instead of
            # attempting a second POST with a newly measured original.
            from ios.adapters.world_web_fence import original
            need(self.state['phase']=='cleaned');retained=original(parts['retirement'])
            measured=parts['retirement'].validate_original(retained)
            receipt=self.state['retirement']['publication']
            publisher=self.retirement_publisher(parts);publisher.bound()
            need(publisher.state['pending'] is None and publisher.state['records']
                and same(publisher.previous,self.state['retirement']['publisherOriginal'])
                and same(publisher.load(publisher.state['records'][-1]),receipt))
            need(measured['ticket']==status['ticket']==receipt['intent']['body']['ticket']
                and receipt['mode']=='published' and digest(retained)==self.state['retirement']['localSha256'])
        return True

    def terminal(self,call):
        from ios.adapters.world_web_terminal import WorldWebTerminal
        return WorldWebTerminal(self).invoke(call)
    def retirement_publisher(self,parts):
        need(self.role=='actor')
        return PhaseRetirementPublisher(PrivateFeatureState(self.store.path.with_name('phase-retirement-world-web-'+self.run+'-actor.json')),self.state['binding'],self.phase,self.lock,
            parts['own']['check'],parts['retirement'].validate_original,stage=WEB_SCENE_STAGE,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
    @contextmanager
    def cleanup_originals(self,parts):
        if self.role!='actor':yield None;return
        # Prepare all ordinary publisher metadata before fresh acquisition.
        publisher=self.retirement_publisher(parts);need(publisher.resolve())
        with parts['retirement'].original_round():yield publisher
    def publish_retirement(self,parts,original,publisher=None):
        need(self.role=='actor')
        if publisher is None:publisher=self.retirement_publisher(parts);need(publisher.resolve())
        with parts['retirement'].publication_round(publisher):publisher.publish(original)
        need(publisher.state['records'] and publisher.state['pending'] is None)
        receipt=publisher.load(publisher.state['records'][-1]);need(receipt['mode']=='published' and receipt['intent']['body']['originalSha256']==digest(original))
        self.state['retirement']=dict(localSha256=digest(original),publication=receipt,publisherOriginal=deepcopy(publisher.previous));self.save()
    @operation
    def cleanup(self,call):
        call=arguments('feature.world-web.cleanup',call);need(call['runId']==self.run)
        with self.held():
            parts,status=self.ensure()
            if self.role=='actor':return {'performed':self.actor_cleanup(parts,status)}
            with self.cleanup_originals(parts) as publisher:
                original=self.clean_local(parts,status)
            binding=deepcopy(self.state['binding']);admission=deepcopy(self.state['actorAdmission']);instance=self.state['phaseInstance'];guard=parts['own']['check']
            if self.state['phase']=='paired':
                # Repeated local cleanup still acquires and validates a fresh
                # original above. Actor Scene3 is once-only: its immutable
                # receipt must be decoded from the retained reader, rather
                # than reacquired as a newly fresh publication.
                def admitted(value):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(value,binding))
                reader=PhaseRetirementReader(self.runtime._world_web_store(self.selector,'ios-world-web-primary-peer-retirement.json'),binding,self.phase,guard,admission,admitted,
                    stage=WEB_SCENE_STAGE,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                retained=self.state['retirement']
                need(reader.previous is not None and reader.state['records']
                    and same(reader.previous,retained['readerOriginal']) and same(reader.state['records'][-1],retained['peerReceipt'])
                    and retained['localSha256']==digest(original))
                return {'performed':True}
        # The independent actor needs the primary's lock for its direct SDK
        # originals. Wait for its original receipt outside both role locks.
        def admitted(value):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(value,binding))
        reader=PhaseRetirementReader(self.runtime._world_web_store(self.selector,'ios-world-web-primary-peer-retirement.json'),binding,self.phase,guard,admission,admitted,
            stage=WEB_SCENE_STAGE,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        started=previous=self.monotonic()
        while True:
            now=self.monotonic();need(number(now,previous,started+15));previous=now
            try:receipt=reader.read();break
            except NativeUIError:
                if now-started>=14.5:raise
                self.sleep(.15)
        with self.held():
            self.load();need(self.state['phase']=='cleaned');parts=self.parts();current=self.phase.read()
            need(current['verb']=='cleanup' and current['ticket']==receipt['entry']['ticket'] and current['status']['instance']==instance)
            confirmation=parts['retirement'].cleanup(current['ticket']);measured=parts['retirement'].validate_original(confirmation)
            need(measured['acquisition']['hostBeforeMonotonic']>=receipt['acquisition']['hostAfterMonotonic'])
            self.state['retirement']=dict(localSha256=digest(confirmation),peerReceipt=deepcopy(receipt),readerOriginal=deepcopy(reader.previous));self.state['phase']='paired';self.save();return {'performed':True}
    @operation
    def publish(self):
        need(self.role=='actor');return self.observe(dict(contractVersion=16,runId=self.run,afterSequence=0))

    @operation
    def finalize(self,phase_original,*,stop_census=None):
        """Scene originals, own normal Stop, OS quiet and immutable archives."""
        from ios.adapters.world_web_final_archive import WorldWebFinalArchive
        from ios.adapters.world_web_process_end import WorldWebProcessEnd
        from ios.adapters.world_web_archived import rebuild
        from ios.adapters.world_web_fence import phase as retired_phase,original as scene_original
        self.lock.assert_held();self.primary_lock.assert_held();self.load();need(self.state is not None)
        retired_phase(phase_original,self)
        need(self.state['phase'] in (('paired','retired') if self.role=='primary' else ('cleaned','retired')))
        process=WorldWebProcessEnd(self)
        archive=WorldWebFinalArchive(self.runtime._world_web_store(self.selector,'ios-world-web-'+self.role+'-'+self.run+'-final.json'),
            self.root,self.state['binding'],self.run,self.role,self.lock)
        header={key:value for key,value in self.previous.items() if key!='payload'}
        def historical():
            owner=rebuild(self)
            return owner,dict(source=owner.source,peer=None if self.role=='primary' else owner.peer,retirement=owner,
                lease=owner.lease if self.role=='primary' else owner.observer.lease)
        if self.state['phase']=='retired':
            owner,parts=historical();process.verify(parts);frame=archive.verify()
            need(same(frame['feature'],dict(self.state,phase=frame['feature']['phase'])) and same(frame['coordinatorHeader'],header)
                and same(owner.validate_original(frame['original']),frame['measured']))
            return {'performed':True}
        if process.state is None or process.state['phase']=='fencing':
            from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory
            need(type(stop_census) is WorldWebRootedInventory
                and self is (stop_census.terminal.flow if self.role=='primary' else stop_census.terminal.actor))
            stop_census.current_roots()
        if process.state is None:
            peer=None if self.role=='actor' else process.actor_ready(actor=stop_census.terminal.actor)
            if self.role=='primary' and peer is None:return {'performed':False}
            parts=self.parts();need(parts['retirement'] is not None and self.state['retirement'] is not None)
            original=scene_original(parts['retirement']);parts['retirement'].validate_original(original)
            need(digest(original)==self.state['retirement']['localSha256'])
            process.prepare(self.runtime._graphics_final_source(self.selector,self.state['binding']),digest(original),peer)
        if process.state['phase']=='fencing':process.stop(self.parts(),census=stop_census)
        started=self.monotonic()
        while process.state['phase']!='complete':
            if process.advance():break
            need(self.monotonic()-started<15);self.sleep(.15)
        # Only the existing SDK's OS endpoint is used after Stop. The typed
        # reconstruction below cannot send a native/DOM/UI/file/GPU query.
        owner,parts=historical();process.verify(parts);original=scene_original(owner)
        current=retired_phase(self.phase.status(),self)
        archive.seal(phase_original=current,feature=deepcopy(self.state),original=original,validate=owner.validate_original,
            paired=deepcopy(self.state['retirement']),directories=[],extra=[],excluded=[self.store.path,archive.store.path],coordinator_header=header)
        self.state['phase']='retired';self.save();return {'performed':True}
