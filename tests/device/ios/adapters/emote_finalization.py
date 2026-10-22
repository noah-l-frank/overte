"""Whole role final archival on the existing SDK, after fixture retirement.

This module is not connected to advertised capabilities until complete role
coordination and whole journey tests pass.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import unpack,same
from ios.adapters.emote_final_archive import IOSEmoteFinalArchive
from ios.adapters.emote_final_proof import validate as current_absence
from ios.adapters.emote_final_recoveries import validate as recovery_originals
from ios.adapters.emote_final_inputs import validate as fixed_input_originals
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_observer import IOSEmoteObserver,EmoteObservationPending
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_retirement import IOSEmoteRetirement,Frozen
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement,world_pixels
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_keyed_retirement import IOSEmoteKeyedRetirement
from ios.adapters.emote_retirement_scope import refresh as refresh_quiet
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery
from ios.adapters.emote_samples import IOSEmoteSamples
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.peer_admission import admit_existing_peer,validate as peer_admission


class IOSEmoteFinalization:
    def __init__(self,flow):
        self.flow=flow;self.store=PrivateFeatureState(flow.runtime.state_path(flow.selector).with_name('ios-emote-'+flow.role+'-'+flow.run+'-finalization.json'))
    def path(self,name,*,primary=False):
        f=self.flow;return PrivateFeatureState(f.runtime.state_path(f.primary_selector if primary else f.selector).with_name(name))
    def paths(self,read=None):
        f=self.flow;role=f.role
        read=(lambda store:store.read()) if read is None else read
        names=['ios-emote-'+role+'-'+tail+'.json' for tail in ('marker','marker-files','marker-script','marker-recovery','samples','sample-recovery',
            'observer','native-files','marker-entities','retirement-originals','rendered-retirement-originals','keyed-retirement-originals','restoration-frames','pointers','keys')]
        if role=='primary':names+=['ios-emote-cleanup-inputs.json','ios-emote-inputs.json','ios-emote-background.json','ios-emote-primary-peer-retirement.json']
        else:names+=['ios-emote-actor-peer-sources.json','ios-emote-actor-peer-recovery.json',
            'phase-publication-emotes-'+f.run+'-actor.json','phase-retirement-emotes-'+f.run+'-actor.json']
        result=[self.path(name) for name in names]
        if role=='actor':
            # Publisher records originate in the SDK directory. Preserve their
            # actual closed values as well as the referring journal before any
            # runtime metadata retires; the final proof must stand alone.
            for prefix in ('phase-publication','phase-retirement'):
                path=self.path(prefix+'-emotes-'+f.run+'-actor.json');value=read(path)
                if value is not None:
                    state=unpack(value['payload'])[0];need(state['pending'] is None)
                    for ref in state['records']:
                        result.append(self.path(prefix+'-emotes-'+f.run+'-actor-'+str(ref['ordinal'])+'.json'))
        result +=[self.path('ios-emote-'+role+'-sources.json',primary=True),self.path('ios-emote-'+role+'-source-recovery.json',primary=True)]
        samples=read(self.path('ios-emote-'+role+'-samples.json'))
        if samples is not None:
            for row in unpack(samples['payload'])[0]['rows']:
                result.append(self.path('graphics-world-frame-'+role+'-0-'+row['requestId'][4:]+'.json'))
        restoration=read(self.path('ios-emote-'+role+'-restoration-frames.json'))
        if restoration is not None:
            for ref in unpack(restoration['payload'])[0]['records']:
                original=PrivateFeatureState(f.root/('emote-restoration-'+f.run+'-'+role+'-'+str(ref['index'])+'.json')).read()
                result.append(self.path('graphics-world-frame-'+role+'-0-'+original['requestId'][4:]+'.json'))
        return result+[f.store]
    def guard(self):
        f=self.flow;f.lock.assert_held();f.primary_lock.assert_held()
        phase=f.phase.status();need(not phase['active'] and phase['instance']==f.state['phaseInstance'])
        other=f.state['primaryBinding'] if f.role=='actor' else peer_admission(f.state['actorAdmission'],f.state['binding'])
        admitted=admit_existing_peer(f.runtime,f.selector,other,epoch_ms=f.epoch_ms,monotonic=f.monotonic)
        need(same(admitted['binding'],f.state['binding']));return True
    def local_components(self):
        """Retire local owners without reopening the other role's SDK.

        Ownership-only sources cannot acquire facts. Their real guard checks
        this SDK's current candidate/process; immutable foreign originals stay
        historical while local pending CAS ownership is retained and settled.
        """
        f=self.flow;self.guard();own=f.runtime._sources(f.selector)
        need(same(own['binding'],f.state['binding']))
        source_root=f.root if f.role=='primary' else f.root/'primary-sdk-originals'
        sources=IOSEmoteSources(self.path('ios-emote-'+f.role+'-sources.json',primary=True),source_root,f.state['primaryBinding'],
            f.run,f.role,f.primary_lock,own['check'],None,ownership_only=True,monotonic=f.monotonic,epoch_ms=f.epoch_ms)
        peers=None
        if f.role=='actor':
            peers=IOSEmotePeerSources(self.path('ios-emote-actor-peer-sources.json'),f.root,f.state['binding'],f.run,None,f.lock,
                own['check'],ownership_only=True,monotonic=f.monotonic,epoch_ms=f.epoch_ms)
        scope=IOSEmoteMarkerScope(f.runtime,f.selector,f.root,f.run,f.role,f.phase.fixture_url,f.state['initialTicket'],f.lock,
            monotonic=f.monotonic,epoch_ms=f.epoch_ms,sleep=f.sleep)
        samples=IOSEmoteSamples(f.runtime,f.selector,scope,f.root,f.policy,f.phase,f.lock,monotonic=f.monotonic,epoch_ms=f.epoch_ms,sleep=f.sleep)
        observer=IOSEmoteObserver(self.path('ios-emote-'+f.role+'-observer.json'),sources,f.state['binding'],f.role,f.root,f.policy,
            f.phase,f.lock,own['check'],peers=peers,samples=samples,monotonic=f.monotonic,epoch_ms=f.epoch_ms)
        restoration=IOSEmoteRestorationFrames(f.runtime,f.selector,scope,f.root,f.lock,
            monotonic=f.monotonic,epoch_ms=f.epoch_ms,sleep=f.sleep)
        return dict(own=own,sources=sources,peers=peers,scope=scope,samples=samples,observer=observer,restoration=restoration)

    def owner(self,value):
        f=self.flow;paths=value['paths']
        return IOSEmoteRetirement(Frozen(self.path('ios-emote-'+f.role+'-retirement-originals.json').path,value),f.root,f.state['binding'],f.state['primaryBinding'],
            f.run,f.role,f.phase.fixture_url,f.state['phaseInstance'],f.lock,f.primary_lock,f.policy,paths,lambda:True)
    def decode(self,copies):
        """All facts come from retained original files, with no SDK or HTTP."""
        f=self.flow;binding=f.state['binding'];role=f.role
        raw=lambda name,primary=False:copies[str(self.path(name,primary=primary).path)]
        expected=self.paths(lambda store:copies[str(store.path)])
        need(list(copies)==[str(store.path) for store in expected])
        actual=copies[str(f.store.path)];need(actual is not None)
        original_state=unpack(actual['payload'])[0];need(same(actual,f.envelope(original_state))
            and original_state['phase']=='cleaned' and original_state['retirement'] is not None and original_state['cleanup'])
        owner=self.owner(raw('ios-emote-'+role+'-retirement-originals.json'));need(owner.state['pending'] is None)
        frame_path=self.path('ios-emote-'+role+'-restoration-frames.json')
        frames=IOSEmoteRestorationFrames.archive(raw(frame_path.path.name),store=frame_path,root=f.root,binding=binding,run=f.run,role=role,lock=f.lock)
        rendered_path=self.path('ios-emote-'+role+'-rendered-retirement-originals.json')
        rendered=IOSEmoteRenderedRetirement(Frozen(rendered_path.path,raw(rendered_path.path.name)),owner,frames)
        keys_path=self.path('ios-emote-'+role+'-keys.json')
        keys=IOSEmoteKeys.archive(raw(keys_path.path.name),store=Frozen(keys_path.path,raw(keys_path.path.name)),root=f.root,
            binding=binding,run=f.run,role=role,lock=f.lock)
        complete_path=self.path('ios-emote-'+role+'-keyed-retirement-originals.json')
        complete=IOSEmoteKeyedRetirement(Frozen(complete_path.path,raw(complete_path.path.name)),rendered,keys)
        reference=original_state['cleanup'][-1];need(same(original_state['retirement']['original'],reference))
        derived=complete.derive(reference);keyed_original=complete.original(reference);original=rendered.original(keyed_original['renderedReference'])
        fixed_input_originals(self,copies,owner.original(original['nativeReference']))
        source_path=self.path('ios-emote-'+role+'-sources.json',primary=True).path
        source_root=f.root if role=='primary' else f.root/'primary-sdk-originals'
        sources=IOSEmoteSources(Frozen(source_path,copies[str(source_path)]),source_root,f.state['primaryBinding'],f.run,role,f.primary_lock,lambda:True,None,historical=True)
        need(sources.state['phase']=='ready' and sources.frames)
        peers=None
        if role=='actor':
            path=self.path('ios-emote-actor-peer-sources.json').path
            peers=IOSEmotePeerSources(Frozen(path,copies[str(path)]),f.root,binding,f.run,None,f.lock,lambda:True,historical=True)
            need(peers.state['pending'] is None and peers.frames);prior_native=peers.frames[-1]['peer']['clockJoin']['nativeAfter']
        else:prior_native=sources.frames[-1]['clockJoin']['nativeAfter']
        decoder=IOSEmoteObservationDecoder(sources,binding,role,f.root,f.policy,f.lock,phase_instance=f.state['phaseInstance'],peers=peers)
        observer=object.__new__(IOSEmoteObserver);observer.sources,observer.binding,observer.role=sources,binding,role
        observer.root,observer.policy,observer.lock,observer.run=f.root,f.policy,f.lock,f.run
        samples=object.__new__(IOSEmoteSamples)
        samples.root,samples.binding,samples.run,samples.role,samples.policy,samples.lock=f.root,binding,f.run,role,f.policy,f.lock
        samples.store=Frozen(self.path('ios-emote-'+role+'-samples.json').path,raw('ios-emote-'+role+'-samples.json'))
        samples.state=samples.decode(samples.store.read())
        need(samples.state['phase']=='ready')
        observer.phase=SimpleNamespace(fixture_url=f.phase.fixture_url);observer.decoder,observer.peers,observer.samples=decoder,peers,samples
        observer.state=observer.decode(raw('ios-emote-'+role+'-observer.json'));need(observer.state['pending'] is None)
        scope=IOSEmoteMarkerScope.archive(raw('ios-emote-'+role+'-marker.json'),root=f.root,binding=binding,run=f.run,role=role,lock=f.lock)
        entities=IOSEmoteMarkerEntities.archive(raw('ios-emote-'+role+'-marker-entities.json'),store=self.path('ios-emote-'+role+'-marker-entities.json'),
            root=f.root,binding=binding,run=f.run,role=role,lock=f.lock)
        files=None
        if scope.state['fileOwnership'] is not None:
            files=IOSEmoteFileReceipts.archive(raw('ios-emote-'+role+'-native-files.json'),store=self.path('ios-emote-'+role+'-native-files.json'),
                root=f.root,binding=binding,run=f.run,role=role,lock=f.lock)
        pointers=IOSEmotePointers.archive(raw('ios-emote-'+role+'-pointers.json'),store=self.path('ios-emote-'+role+'-pointers.json'),
            root=f.root,binding=binding,run=f.run,role=role,lock=f.lock)
        final_native=current_absence(scope,entities,files,pointers,prior_native)
        key_end=keys.closed(scope)['last']['clockJoin']['nativeAfter'];follow(final_native,key_end)
        need(key_end['animation']['overrideActive'] is False and same(key_end['lifecycle'],final_native['lifecycle'])
            and key_end['animation']['history']['callSequence']==final_native['animation']['history']['callSequence'])
        final_native=key_end
        latest=frames.state['records'][-1];current,current_raw=frames.frame(latest)
        initial,initial_raw=frames.frame(original['initialReference']);world_pixels(initial,current,initial_raw,current_raw)
        barrier=entities.latest()['clockJoin']['nativeAfter']
        if files is not None:barrier=files.original(files.state['records'][-1])['clockJoin']['nativeAfter']
        follow(barrier,current['clockJoin']['nativeBefore']);follow(current['clockJoin']['nativeAfter'],final_native)
        owner.samples(raw('ios-emote-'+role+'-samples.json'),scope)
        recovery_originals(self,copies,sources,peers,scope,samples)
        if role=='actor':
            for cls,prefix,callback in ((PhaseWitnessPublisher,'phase-publication',observer.validate_original),
                                       (PhaseRetirementPublisher,'phase-retirement',complete.derive)):
                path=self.path(prefix+'-emotes-'+f.run+'-actor.json');value=copies[str(path.path)];need(value is not None)
                class RetainedPublisher(cls):
                    def record_store(_publisher,ordinal):
                        original_path=super().record_store(ordinal).path
                        need(str(original_path) in copies)
                        return Frozen(original_path,copies[str(original_path)])
                state=RetainedPublisher.archive(value,store=path,binding=binding,run=f.run,area='emotes',fixture_url=f.client.url,
                    phase_instance=f.state['phaseInstance'],validate_original=callback)
                need(state['pending'] is None and state['records'])
                publication=object.__new__(RetainedPublisher)
                publication.store,publication.binding,publication.run,publication.area=path,binding,f.run,'emotes'
                publication.url,publication.instance,publication.validate_original=f.client.url,f.state['phaseInstance'],callback
                publication.live=False
                if cls is PhaseRetirementPublisher:
                    retained=original_state['retirement']['publisher'];need(retained in state['records'])
                    entry=publication.load(retained)
                    need(entry['mode']=='published' and same(entry['intent']['original'],reference))
                else:
                    entry=publication.load(state['records'][-1]);last=observer.state['records'][-1]
                    expected=dict(iosEmoteObservationReferenceVersion=1,**last)
                    need(entry['mode']=='published' and same(entry['intent']['original'],expected)
                        and same(entry['intent']['derived']['public'],derived['public']))
            need(original_state['retirement']['kind']=='actor-published')
        else:
            need(original_state['retirement']['kind']=='primary-paired')
            receipt=original_state['retirement']['peerReceipt'];reader=object.__new__(PhaseRetirementReader)
            reader.store=self.path('ios-emote-primary-peer-retirement.json');reader.binding=binding
            reader.run,reader.area,reader.instance,reader.url=f.run,'emotes',f.state['phaseInstance'],f.client.url;reader.stage='complete'
            reader.admitted_original=original_state['actorAdmission']
            reader.validate_admission=lambda value:dict(runId=f.run,phaseInstance=f.state['phaseInstance'],binding=peer_admission(value,binding))
            reader.actor=reader.admission();state=reader.decode(raw('ios-emote-primary-peer-retirement.json'));need(receipt in state['records'])
        return derived
    def finish(self):
        f=self.flow;f.lock.assert_held();f.primary_lock.assert_held();saved=self.store.read()
        if saved is not None:
            paths=[PrivateFeatureState(path) for path in saved['paths']]
            transaction=IOSEmoteFinalArchive(self.store,f.root,saved['binding'],f.run,f.role,f.lock,f.primary_lock,paths,self.guard,self.decode)
            if f.state is None:
                need(transaction.state['phase'] in ('retiring','complete') and len(transaction.state['records'])==len(paths))
                feature=transaction.copy(transaction.state['records'][-1]);f.state=unpack(feature['payload'])[0]
            return transaction.retire()
        need(f.state is not None and f.state['phase']=='cleaned' and f.state['retirement'] is not None)
        parts=self.local_components();scope,samples,observer=parts['scope'],parts['samples'],parts['observer']
        need(scope.state['phase']=='released')
        observer.abandon_read();IOSEmoteSampleRecovery(samples).recover();samples.drain()
        if f.role=='actor':
            need(observer.publisher().resolve() and f.retirement_publisher(parts).resolve())
        pointers=f.pointers(parts);pointers.abandon();keys=f.keys(parts);keys.abandon()
        refresh_quiet(scope,clock=f.monotonic,sleep=f.sleep,pointers=pointers,keys=keys)
        entities=f.marker_entities(parts);entities.abandon();entities.capture();entities.closed(scope)
        if scope.state['fileOwnership'] is not None:
            files=f.file_receipts(parts);files.abandon();files.capture('absent',scope.state['fileOwnership'])
        restoration=parts['restoration'];restoration.abandon();restoration.capture('cleanup')
        pointers.capture();keys.capture()
        # The historical validator rereads each actual resource and pointer
        # original before any fixed runtime metadata can retire.
        transaction=IOSEmoteFinalArchive(self.store,f.root,f.state['binding'],f.run,f.role,f.lock,f.primary_lock,self.paths(),self.guard,self.decode)
        transaction.begin(f.phase.status());return transaction.retire()
