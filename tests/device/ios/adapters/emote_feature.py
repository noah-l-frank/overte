"""Whole Emote coordination on existing independently qualified SDK targets.

No capability is advertised here. Final runtime dispatch must be enabled only
after the complete ordinary action/observation/paired retirement path is tested.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.emote_cleanup import IOSEmoteCleanup
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.graphics_history import restore_native
from ios.adapters.emote_lifecycle import IOSEmoteBackground
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.adapters.emote_observer import IOSEmoteObserver,EmoteObservationPending
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_pointers import IOSEmotePointers,zero as pointer_zero
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_scene_operation import retry_scene,initial as initial_scene,retired as retired_scene
from ios.adapters.emote_keyed_retirement import IOSEmoteKeyedRetirement
from ios.adapters.world_web_keys import drained as keys_zero
from ios.adapters.emote_retirement_scope import refresh as refresh_quiet
from ios.adapters.emote_retirement_scope_end import extend as extend_quiet
from ios.adapters.emote_samples import IOSEmoteSamples,EmoteMarkerPending
from ios.adapters.emote_ui_inventory import absent as absent_chooser
from ios.adapters.peer_admission import admit_existing_peer,validate as peer_admission
from ios.adapters.emote_operation import operation,clock as operation_clock
from ios.adapters.emote_images import EmoteImagePending
from ios.adapters.emote_observation_operation import ObservationPending,retry_observation

VERSION=1


class IOSEmoteFeature:
    RETRY_OBSERVATION_READINESS=False
    FORMAT_VERSION=1
    PROFILE_FIELDS=frozenset()
    Marker=IOSEmoteMarkerScope
    Observer=IOSEmoteObserver
    Samples=IOSEmoteSamples
    NativeRetirement=IOSEmoteRetirement
    RenderedRetirement=IOSEmoteRenderedRetirement
    KeyedRetirement=IOSEmoteKeyedRetirement
    scene_proof_version=1
    retirement_stage=None
    paired_retirement_kind='primary-paired'
    quiet_refresh=staticmethod(refresh_quiet)
    quiet_extend=staticmethod(extend_quiet)

    def __init__(self,runtime,selector,client,run,role,root,policy,*,primary_selector=None,actor_selector=None,
                 monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000,sleep=time.sleep):
        need(isinstance(runtime,IOSEmoteRuntime) and isinstance(client,Client) and role in ('primary','actor')
            and all(callable(fn) for fn in (monotonic,epoch_ms,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.root,self.policy=Path(root),deepcopy(policy);need(self.root.is_absolute() and self.root.resolve()==self.root
            and self.root.is_dir() and policy.get('source')=='world-render-target')
        PrivateFeatureState(self.root/'emote-feature-root-check')._parent()
        self.primary_selector=selector if role=='primary' else primary_selector
        need(self.primary_selector is not None and (role=='primary' or self.primary_selector!=selector))
        self.actor_selector=actor_selector;need(role=='actor' or actor_selector is not None and actor_selector!=selector)
        self.lock=ScriptSourceLock(runtime.state_path(selector).with_name('script-feature-sources.lock'))
        self.primary_lock=self.lock if role=='primary' else ScriptSourceLock(runtime.state_path(primary_selector).with_name('script-feature-sources.lock'))
        need(role=='primary' or self.primary_lock.path!=self.lock.path)
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-emote-'+role+'-feature.json'))
        self.phase=PhaseFixtureReader(client,run,'emotes',epoch_ms=epoch_ms,monotonic=monotonic)
        self.monotonic,self.epoch_ms,self.sleep=monotonic,epoch_ms,sleep
        self.previous=None;self.state=None;self.deadline=None;self.last_clock=None

    def clock(self):
        return operation_clock(self)

    @contextmanager
    def held(self,seconds=25):
        old=self.deadline;self.deadline=self.clock()+seconds if old is None else min(old,self.clock()+seconds)
        try:
            # Actor takes its own SDK lock first. Primary never takes actor's
            # lock or waits for actor publication while holding this lock.
            with self.lock.held():
                if self.role=='actor':
                    with self.primary_lock.held():yield
                else:yield
            self.clock()
        finally:self.deadline=old

    def profile_envelope(self,state):return {}

    def envelope(self,state):
        return dict(iosEmoteFeatureVersion=self.FORMAT_VERSION,runId=self.run,role=self.role,artifactRoot=str(self.root),
            fixtureUrl=self.phase.fixture_url,imagePolicy=self.policy,payload=pack([state]),**self.profile_envelope(state))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:self.state=None;return
        exact(self.previous,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'}|self.PROFILE_FIELDS)
        rows=unpack(self.previous['payload']);need(len(rows)==1 and same(self.previous,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','binding','primaryBinding','actorAdmission','phaseInstance','initialTicket','lastCall','inputBarrier','cleanup','retirement'})
        need(state['phase'] in ('preparing','ready','cleaning','cleaned','retired'));context(state['binding']);context(state['primaryBinding'])
        identifier(state['phaseInstance']);identifier(state['initialTicket'])
        if self.role=='primary':peer_admission(state['actorAdmission'],state['binding'])
        else:need(state['actorAdmission'] is None)
        if state['lastCall'] is not None:
            call=arguments('feature.emotes.act',state['lastCall']);need(call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url)
        if state['inputBarrier'] is not None:
            exact(state['inputBarrier'],{'index','sha256'});need(integer(state['inputBarrier']['index'],1))
        need(type(state['cleanup']) is list and len(state['cleanup'])<=128 and (state['retirement'] is None or type(state['retirement']) is dict))
        self.state=deepcopy(state)

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def bindings(self):
        own=self.runtime._sources(self.selector);primary=own if self.role=='primary' else self.runtime._sources(self.primary_selector)
        a,b=own['binding'],primary['binding'];context(a);context(b)
        if self.role=='actor':need(a['targetFingerprint']!=b['targetFingerprint'] and a['sessionId']!=b['sessionId']
            and all(a[key]==b[key] for key in ('artifactSha256','sourceRevision')))
        if self.state is not None:need(same(a,self.state['binding']) and same(b,self.state['primaryBinding']))
        return own,primary

    def components(self):
        own,primary=self.bindings();need(self.state is not None and self.phase.previous is not None
            and self.phase.previous['instance']==self.state['phaseInstance'])
        source_root=self.root
        if self.role=='actor':
            source_root=self.root/'primary-sdk-originals'
            if not source_root.exists():source_root.mkdir(mode=0o700)
            PrivateFeatureState(source_root/'emote-primary-original-root-check')._parent()
        sources=self.runtime._emote_sources(self.primary_selector,self.client,self.run,self.role,source_root,self.primary_lock)
        scope=self.Marker(self.runtime,self.selector,self.root,self.run,self.role,self.phase.fixture_url,
            self.state['initialTicket'],self.lock,monotonic=self.monotonic,epoch_ms=self.epoch_ms,sleep=self.sleep)
        peers=None
        if self.role=='actor':
            peers=IOSEmotePeerSources(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-actor-peer-sources.json')),
                self.root,own['binding'],self.run,self.phase,self.lock,own['check'],runtime=self.runtime,selector=self.selector,
                monotonic=self.monotonic,epoch_ms=self.epoch_ms)
        samples=self.Samples(self.runtime,self.selector,scope,self.root,self.policy,self.phase,self.lock,
            monotonic=self.monotonic,epoch_ms=self.epoch_ms,sleep=self.sleep)
        observer=self.Observer(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-observer.json')),
            sources,own['binding'],self.role,self.root,self.policy,self.phase,self.lock,own['check'],peers=peers,samples=samples,
            monotonic=self.monotonic,epoch_ms=self.epoch_ms)
        restoration=IOSEmoteRestorationFrames(self.runtime,self.selector,scope,self.root,self.lock,
            monotonic=self.monotonic,epoch_ms=self.epoch_ms,sleep=self.sleep)
        return dict(own=own,primary=primary,sources=sources,scope=scope,peers=peers,samples=samples,observer=observer,restoration=restoration)

    def marker_entities(self,parts):
        own=parts['own'];observer=own['observer'];native=observer.bound_native_observer(own['clock_source'])
        return IOSEmoteMarkerEntities(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-marker-entities.json')),
            self.root,self.state['binding'],self.run,self.role,self.lock,own['check'],native=native,entities=observer.create_entities(own['clock_source']),
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def pointers(self,parts):
        own=parts['own'];observer=own['observer']
        return IOSEmotePointers(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-pointers.json')),
            self.root,self.state['binding'],self.run,self.role,self.lock,own['check'],native=observer.bound_native_observer(own['clock_source']),
            pointer=observer.pointer_state(own['clock_source']),epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def keys(self,parts):
        own=parts['own'];observer=own['observer']
        return IOSEmoteKeys(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-keys.json')),
            self.root,self.state['binding'],self.run,self.role,self.lock,own['check'],native=observer.bound_native_observer(own['clock_source']),
            keys=observer.world_web_keys(own['clock_source']),geometry=observer.geometry(),epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def file_receipts(self,parts):
        own=parts['own'];scope=parts['scope'];native=own['observer'].bound_native_observer(own['clock_source'])
        result=IOSEmoteFileReceipts(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-native-files.json')),
            self.root,self.state['binding'],self.run,self.role,self.lock,own['check'],native=native,files=scope.files.native,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        if not result.state['records'] and scope.frames:restore_native(native,scope.frames[-1]['clockJoin']['nativeAfter'])
        return result

    def recover_background(self):
        """Finish only the already owned ordinary resume before UI factories."""
        if self.role!='primary':return
        value=PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-background.json')).read()
        if value is None:return
        need(self.state is not None)
        background=IOSEmoteBackground(self.runtime,self.selector,self.run,self.phase.fixture_url,self.state['binding'],self.lock,
            monotonic=self.monotonic,sleep=self.sleep)
        if background.state['phase']!='observed':background.act(background.state['call'])

    def prepare(self):
        self.load();status=self.phase.read();self.recover_background();own,primary=self.bindings()
        if self.state is None:
            admission=(admit_existing_peer(self.runtime,self.actor_selector,own['binding'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                if self.role=='primary' else None)
            self.state=dict(phase='preparing',binding=own['binding'],primaryBinding=primary['binding'],phaseInstance=status['status']['instance'],
                actorAdmission=admission,initialTicket=status['ticket'],lastCall=None,inputBarrier=None,cleanup=[],retirement=None);self.save()
        need(self.state['phaseInstance']==status['status']['instance'] and self.state['phase'] in ('preparing','ready','cleaning','cleaned'))
        parts=self.components()
        if self.state['phase']=='preparing':
            keys=self.keys(parts);keys.abandon()
            if not keys.state['records']:
                record=keys.original(keys.capture());keys_zero(keys.packet(record));keys.keyboard_hidden(record)
        if self.state['phase']=='preparing' and status['verb']=='cleanup':
            # A failed preparation owns its inputs/files even though readiness
            # was never reached. Cleanup must not attempt setup again.
            pointers=self.pointers(parts);pointers.abandon()
            if not pointers.state['records']:pointer_zero(pointers.original(pointers.capture())['packet'])
            entities=self.marker_entities(parts);entities.abandon()
            if not entities.state['records']:entities.capture()
            return parts
        if self.state['phase']=='preparing':
            pointers=self.pointers(parts);pointers.abandon()
            if not pointers.state['records']:
                pointer_zero(pointers.original(pointers.capture())['packet'])
            entities=self.marker_entities(parts);entities.abandon()
            if not entities.state['records']:entities.capture()
            restoration=parts['restoration'];restoration.abandon()
            if not any(restoration.original(ref)['phase']=='captured' and restoration.original(ref)['kind']=='initial'
                       for ref in restoration.state['records']):
                # The untouched background is captured before the first normal
                # marker input. An old challenge frame cannot stand in for it.
                restoration.capture('initial')
            initial_scene(self,parts)
            with self.runtime.existing_input_session(self.selector):parts['scope'].prepare()
            if parts['scope'].state['webAdmission'] is None:parts['scope'].admit_rendered()
            files=self.file_receipts(parts);files.abandon()
            if not files.state['records']:files.capture('bytes',parts['scope'].state['fileOwnership'])
            self.state['phase']='ready';self.save()
        return parts

    @staticmethod
    def reference(actions):
        row=actions.state['current'];need(row is not None and row['before'] is not None)
        ref=row['before'];return dict(index=ref['revision'],sha256=ref['sha256'])

    @operation(25)
    @retry_scene
    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.emotes.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url)
        with self.held():
            parts=self.prepare();need(self.state['phase']=='ready');status=self.phase.read()
            need(status['ticket']==call['ticket'] and status['verb']==call['verb'] and same(status['inputs'],call['inputs']))
            initial=parts['observer'].state['baseline'] is None
            if initial:parts['observer'].observe(0)
            if self.state['lastCall'] is not None and self.state['lastCall']['ticket']==call['ticket']:need(same(self.state['lastCall'],call))
            if self.state['lastCall'] is None or self.state['lastCall']['ticket']!=call['ticket']:
                self.state['lastCall']=call;self.state['inputBarrier']=None;self.save()
            if initial:
                parts['sources'].read()
                parts['observer'].begin_initial_input(parts['observer'].source_reference())
            observer=parts['observer']
            if self.state['inputBarrier'] is None and observer.state['phaseTicket']==call['ticket'] and observer.state['phaseBarrier'] is not None:
                # Adopt the same durable admission if the Feature metadata
                # return was lost before any ordinary action was sent.
                self.state['inputBarrier']=observer.initial_barrier(observer.state['phaseBarrier']);self.save()
            if call['verb']=='background-resume':
                if self.state['inputBarrier'] is None:
                    before=parts['sources'].read();self.state['inputBarrier']=dict(index=len(parts['sources'].frames),sha256=digest(before));self.save()
                result=IOSEmoteBackground(self.runtime,self.selector,self.run,self.phase.fixture_url,self.state['binding'],self.lock,
                    monotonic=self.monotonic,sleep=self.sleep).act(call)
            else:
                with self.runtime.existing_input_session(self.selector):
                    actions=self.runtime._emote_actions(self.selector,parts['sources']);result=actions.act(call)
                if self.state['inputBarrier'] is None:self.state['inputBarrier']=self.reference(actions)
                self.save()
            return result

    @operation(30)
    @retry_scene
    @retry_observation
    def observe(self,call):
        call=arguments('feature.emotes.observe',call);need(call['runId']==self.run)
        with self.held(30):
            parts=self.prepare();observer=parts['observer'];observer.abandon_read();current=self.phase.read()
            if current['verb']=='cleanup':
                self.clean_local(parts);result=self.retirement_sample(parts,call['afterSequence'])
                if self.role=='actor':self.publish_retirement(parts)
                return result
            need(self.state['phase']=='ready')
            barrier=(self.state['inputBarrier'] if self.role=='primary' and self.state['lastCall'] is not None
                and self.state['lastCall']['ticket']==current['ticket'] else None)
            try:result=observer.observe(call['afterSequence'],input_barrier=barrier)
            except (EmoteObservationPending,EmoteImagePending):
                if not self.RETRY_OBSERVATION_READINESS:raise
                # The actual incomplete read and its GPU ownership remain in
                # their original WALs. The next call abandons only independently
                # returned/drained reads; no normal input is repeated.
                raise ObservationPending(current['ticket']) from None
            if self.role=='actor':observer.publish_latest()
            return result

    @operation(60)
    def publish(self):
        need(self.role=='actor')
        # Actor acquisition uses this SDK and a separately bound Primary SDK;
        # it does not call Primary's normalized observe operation.
        with self.held():
            self.load();self.phase.status()
            archived=PrivateFeatureState(self.runtime.state_path(self.selector).with_name(
                'ios-emote-'+self.role+'-'+self.run+'-finalization.json')).read()
            retired=not self.phase.previous['active'] and (self.state is not None or archived is not None)
        if retired:return self.finalize()
        return self.observe(dict(contractVersion=16,runId=self.run,afterSequence=0))

    def cleanup_inputs(self,parts):
        observer=parts['observer'];sources=parts['sources'];need(self.role=='primary')
        actions=self.runtime._emote_actions(self.selector,sources)
        rows=actions.state['history']+([actions.state['current']] if actions.state['current'] is not None else [])
        def original_state(frame):
            need(observer.state['baseline'] is not None)
            # A prior act may have returned before Primary acquired its own
            # public playback observation. Recover only from the actual owned
            # action's original pre-input source and native measured history.
            latest=next((row for row in reversed(rows) if row['before'] is not None
                and row['call']['verb'] in ('play','sit','override')),None)
            if latest is not None:
                barrier=dict(index=latest['before']['revision'],sha256=latest['before']['sha256'])
                before=observer.decoder.source(barrier)
                if frame['group']['native']['animation']['history']['overrideSequence']>before['group']['native']['animation']['history']['overrideSequence']:
                    observer.recover_owned_episode(barrier,frame)
            proof=observer.proof(frame,self.phase.previous['activations'][-1]['ticket'])
            return observer.decoder.state(frame,proof,self.phase.previous['activations'][-1]['ticket'])
        def owned(frame):original_state(frame);return True
        def restored(frame):need(original_state(frame)['override'] is False);return True
        normal=NativeUI(parts['own']['client'],parts['own']['session'],parts['own']['check'])
        return IOSEmoteCleanup(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-cleanup-inputs.json')),
            sources,normal,validate_owned=owned,validate_restored=restored)

    def native_retirement_owner(self,parts):
        return self.NativeRetirement(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-retirement-originals.json')),
            self.root,self.state['binding'],self.state['primaryBinding'],self.run,self.role,self.phase.fixture_url,self.state['phaseInstance'],
            self.lock,self.primary_lock,self.policy,dict(sources=parts['sources'].store.path,
                peers=None if parts['peers'] is None else parts['peers'].store.path,
                files=self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-native-files.json'),
                entities=self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-marker-entities.json'),
                pointers=self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-pointers.json')),parts['own']['check'])

    def current_retirement_component(self,owner,kind,suffix):
        need(type(owner) is kind and not owner.historical and owner.root==self.root
            and owner.run==self.run and owner.role==self.role and owner.lock is self.lock and owner.primary_lock is self.primary_lock
            and same(owner.binding,self.state['binding']) and same(owner.primary_binding,self.state['primaryBinding'])
            and owner.fixture_url==self.phase.fixture_url and owner.phase_instance==self.state['phaseInstance']
            and same(owner.policy,self.policy) and owner.store.path==self.runtime.state_path(self.selector).with_name(
                'ios-emote-'+self.role+'-'+suffix+'-originals.json'))
        owner.current();return owner

    def rendered_retirement_owner(self,parts,*,native=None):
        native=(self.native_retirement_owner(parts) if native is None else
            self.current_retirement_component(native,self.NativeRetirement,'retirement'))
        return self.RenderedRetirement(PrivateFeatureState(self.runtime.state_path(self.selector).with_name(
            'ios-emote-'+self.role+'-rendered-retirement-originals.json')),native,parts['restoration'])

    def retirement_owner(self,parts,*,rendered=None,keys=None):
        rendered=(self.rendered_retirement_owner(parts) if rendered is None else
            self.current_retirement_component(rendered,self.RenderedRetirement,'rendered-retirement'))
        if keys is None:keys=self.keys(parts)
        else:
            need(type(keys) is IOSEmoteKeys and keys.root==self.root and keys.run==self.run and keys.role==self.role
                and keys.lock is self.lock and same(keys.binding,self.state['binding'])
                and keys.store.path==self.runtime.state_path(self.selector).with_name('ios-emote-'+self.role+'-keys.json'))
            keys.bound()
        return self.KeyedRetirement(PrivateFeatureState(self.runtime.state_path(self.selector).with_name(
            'ios-emote-'+self.role+'-keyed-retirement-originals.json')),rendered,keys)

    def clean_local(self,parts):
        need(self.phase.previous['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}) and self.state['phase']!='retired')
        if self.state['phase']=='cleaned':return
        self.state['phase']='cleaning';self.save();parts['observer'].abandon_read()
        if self.role=='primary' and parts['observer'].state['baseline'] is not None:
            with self.runtime.existing_input_session(self.selector):
                started=self.monotonic()
                for attempt in range(41):
                    try:self.cleanup_inputs(parts).close();break
                    except NativeUIError:
                        if attempt==40 or self.monotonic()-started>=10:raise
                        self.sleep(.15)
        parts['samples'].drain()
        with self.runtime.existing_input_session(self.selector):parts['scope'].cleanup()
        need(parts['scope'].state['phase']=='released');self.state['phase']='cleaned';self.save()

    def retirement_sample_owners(self,parts,observation):return parts['samples'].store.read()

    def retirement_sample(self,parts,after_sequence=0,*,fresh_end=False):
        need(self.state['phase']=='cleaned');owner=self.native_retirement_owner(parts)
        if owner.state['pending'] is not None:
            try:owner.resolve()
            except NativeUIError:owner.abandon()
        parts['observer'].abandon_read();parts['samples'].drain()
        pointers=self.pointers(parts);pointers.abandon();keys=self.keys(parts);keys.abandon()
        waiting=('scene-retired',self.phase.previous['activations'][-1]['ticket']) in (getattr(self,'_scene_proofs',None) or {})
        if fresh_end or waiting:self.quiet_extend(parts['scope'],pointers,keys=keys)
        else:self.quiet_refresh(parts['scope'],clock=self.monotonic,sleep=self.sleep,pointers=pointers,keys=keys)
        entities=self.marker_entities(parts);entities.abandon();entities.capture();entities.closed(parts['scope'])
        files=None
        if parts['scope'].state['fileOwnership'] is not None:
            files=self.file_receipts(parts);files.abandon();files.capture('absent',parts['scope'].state['fileOwnership'])
        retired_scene(self,parts)
        if self.role=='actor':
            # Receive and render the independently acquired current Primary
            # pose before fencing the Actor's final world pixels. A later peer
            # observation cannot qualify an earlier stale remote payload.
            parts['sources'].read();parts['peers'].read()
        restoration=parts['restoration'];restoration.abandon();current=restoration.capture('cleanup')
        public=parts['observer'].observe(after_sequence,retired=True)
        observation=parts['observer'].original(parts['observer'].state['records'][-1]);pointers.capture();keys.capture()
        def raw(name):return PrivateFeatureState(self.runtime.state_path(self.selector).with_name(name)).read()
        inputs=dict(cleanup=None,actions=None,background=None)
        if self.role=='primary':inputs=dict(cleanup=raw('ios-emote-cleanup-inputs.json'),actions=raw('ios-emote-inputs.json'),background=raw('ios-emote-background.json'))
        original=dict(observation=observation,sources=parts['sources'].store.read(),
            peers=None if parts['peers'] is None else parts['peers'].store.read(),scope=parts['scope'].snapshot(),
            fileReceipts=None if files is None else files.store.read(),entities=entities.store.read(),sampleOwners=self.retirement_sample_owners(parts,observation),inputOwners=inputs,pointers=pointers.store.read())
        native_reference=owner.retain(original)
        rendered=self.rendered_retirement_owner(parts,native=owner)
        if rendered.state['pending'] is not None:
            try:rendered.resolve()
            except NativeUIError:rendered.abandon()
        initials=[ref for ref in restoration.state['records'] if restoration.original(ref)['phase']=='captured'
                  and restoration.original(ref)['kind']=='initial'];need(initials)
        rendered_reference=rendered.retain(dict(nativeReference=native_reference,frames=restoration.store.read(),
            initialReference=initials[0],currentReference=current))
        complete=self.retirement_owner(parts,rendered=rendered,keys=keys)
        if complete.state['pending'] is not None:
            try:complete.resolve()
            except NativeUIError:complete.abandon()
        reference=complete.retain(dict(renderedReference=rendered_reference,keys=keys.store.read()))
        self.state['cleanup'].append(reference);need(len(self.state['cleanup'])<=128);self.save()
        # The separate original decoder, rather than expected cleanup flags,
        # must accept the entire local native/input/GPU/Script/file closure.
        return self.retirement_public(complete,reference,public)

    def retirement_public(self,owner,reference,public):
        need(same(owner.derive(reference)['public'],public));return public

    def retirement_decoder(self,owner):return owner.derive

    def retirement_publisher(self,parts):
        need(self.role=='actor');owner=self.retirement_owner(parts)
        return PhaseRetirementPublisher(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('phase-retirement-emotes-'+self.run+'-actor.json')),
            self.state['binding'],self.phase,self.lock,parts['own']['check'],self.retirement_decoder(owner),epoch_ms=self.epoch_ms,monotonic=self.monotonic,stage=self.retirement_stage)

    def publish_retirement(self,parts):
        need(self.role=='actor' and self.state['cleanup'])
        # Resolve an earlier facts publication separately. Phase retirement
        # discharges only that POST's ownership, never native cleanup.
        if not parts['observer'].publisher().resolve():raise EmoteObservationPending('An earlier facts publication is still unresolved')
        publisher=self.retirement_publisher(parts)
        if not publisher.resolve():raise EmoteObservationPending('An earlier retirement publication is still unresolved')
        publisher.publish(self.state['cleanup'][-1]);parts['observer'].publish_latest()
        last=publisher.load(publisher.state['records'][-1]);need(last['mode']=='published')
        self.state['retirement']=dict(kind='actor-published',original=self.state['cleanup'][-1],publisher=deepcopy(publisher.state['records'][-1]));self.save()
        return {'performed':True}

    def peer_retirement_reader(self,binding,guard,admission,admitted):
        return PhaseRetirementReader(PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-emote-primary-peer-retirement.json')),
            binding,self.phase,guard,admission,admitted,epoch_ms=self.epoch_ms,monotonic=self.monotonic,
            stage='complete' if self.retirement_stage is None else self.retirement_stage)

    def qualify_peer_retirement(self,receipt):
        from feature_journeys.retirement_receipts import summary
        now=self.epoch_ms();mono=self.monotonic();received=receipt['acquisition'];original_summary=summary(receipt['entry'])
        need(number(now,received['hostAfterEpochMs'],1e15) and number(mono,received['hostAfterMonotonic'],1e15)
            and max(now-original_summary['capturedEpochMs'],
                received['hostAfterEpochMs']-original_summary['capturedEpochMs']+(mono-received['hostAfterMonotonic'])*1000)<=1500)

    @operation(60)
    @retry_scene
    def cleanup(self,call):
        call=arguments('feature.emotes.cleanup',call);need(call['runId']==self.run)
        with self.held(30):
            self.load();need(self.state is not None and self.state['phase']!='retired')
            status=self.phase.read();need(status['verb']=='cleanup' and status['status']['instance']==self.state['phaseInstance'])
            self.recover_background()
            parts=self.components();self.clean_local(parts)
            # Repeated cleanup still acquires actual quiet/input/VM/GPU/pixel
            # originals. A prior receipt is historical evidence, not a lease
            # on the present product state; ordinary inputs remain once-only.
            self.retirement_sample(parts)
            if self.role=='actor':return self.publish_retirement(parts)
            own_binding=deepcopy(self.state['binding']);admission=deepcopy(self.state['actorAdmission']);instance=self.state['phaseInstance']
            guard=parts['own']['check']
        # The Primary lock is deliberately released before reading the
        # independent Actor's committed receipt; the Actor needs that lock to
        # acquire its own original Primary SDK evidence.
        def admitted(original):return dict(runId=self.run,phaseInstance=instance,binding=peer_admission(original,own_binding))
        reader=self.peer_retirement_reader(own_binding,guard,admission,admitted)
        waiting=self.monotonic();last=waiting
        while True:
            now=self.monotonic();need(number(now,last,waiting+20));last=now
            try:receipt=reader.read();break
            except NativeUIError:
                # Missing, stale, foreign or uncommitted receipts never permit
                # success. Only a future independently valid journal can join.
                if now-waiting>=19.5:raise
                self.sleep(.15)
        with self.held():
            self.load();self.phase.read();need(self.state['phase']=='cleaned' and self.phase.previous['activations'][-1]['ticket']==receipt['entry']['ticket'])
            parts=self.components();self.retirement_sample(parts,fresh_end=True)
            # Preserve the Actor's original receipt timestamp. Waiting and
            # reacquiring our own current proof cannot make that receipt fresh.
            self.qualify_peer_retirement(receipt)
            reference=self.state['cleanup'][-1]
            self.state['retirement']=dict(kind=self.paired_retirement_kind,original=reference,peerReceipt=deepcopy(receipt));self.save()
            return {'performed':True}

    @operation(60)
    @retry_scene
    def finalize(self):
        """After fixture retirement, retain originals and retire only metadata."""
        from ios.adapters.emote_finalization import IOSEmoteFinalization
        with self.held(30):
            self.load();self.phase.status();need(not self.phase.previous['active'])
            return IOSEmoteFinalization(self).finish()
