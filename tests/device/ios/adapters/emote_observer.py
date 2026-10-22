"""Durable live Emote acquisitions and original-only actor publication.

The caller holds the observer SDK lock and, for the actor's independently read
primary SDK, that separate source lock. This owner never creates SDK sessions,
activates fixture phases, selects Emotes or rewrites native event history.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.emote_rig_measurements import playback
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_observation import IOSEmoteObservationDecoder,VERSION as ORIGINAL_VERSION
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_samples import IOSEmoteSamples
from ios.adapters.emote_sources import IOSEmoteSources,EmotePhaseChanged
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery

VERSION=1
OWNER_VERSION=2
OWNER_READS=(1,2)


class EmoteObservationPending(NativeUIError):pass


class IOSEmoteObserver:
    def __init__(self,store,sources,binding,role,root,policy,phase,lock,guard,*,peers=None,samples=None,
                 monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSEmoteSources) and not sources.historical
            and sources.role==role and isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and phase.run==sources.run
            and phase.previous is not None and (role=='primary' or isinstance(peers,IOSEmotePeerSources))
            and (samples is None or isinstance(samples,IOSEmoteSamples)) and all(callable(fn) for fn in (guard,monotonic,epoch_ms)))
        self.store,self.sources,self.binding,self.role=store,sources,deepcopy(binding),role
        self.root,self.policy,self.phase,self.lock=Path(root),deepcopy(policy),phase,lock
        self.run,self.guard,self.monotonic,self.epoch_ms=sources.run,guard,monotonic,epoch_ms
        self.peers,self.samples=peers,samples
        self.peer_recovery=None if peers is None else OriginalAvatarPeerRecovery(peers)
        self.recovery=IOSEmoteSourceRecovery(sources)
        self.sample_recovery=None if samples is None else IOSEmoteSampleRecovery(samples)
        need(store.path.name=='ios-emote-'+role+'-observer.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.decoder=IOSEmoteObservationDecoder(sources,binding,role,root,policy,lock,
            phase_instance=phase.previous['instance'],peers=peers)
        self.previous=store.read();self.failed=False
        self.state=dict(records=[],pending=None,baseline=None,phaseTicket=None,phaseBarrier=None,peerBarrier=None,imageBarrier=None,
            lastSource=None,lastPeer=None,lastImage=None,episode=None,abandoned=[])
        if self.previous is None:self.save()
        else:self.state=self.decode(self.previous)

    def envelope(self,state,version=OWNER_VERSION):
        return dict(iosEmoteObserverVersion=version,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.sources.binding,fixtureUrl=self.phase.fixture_url,phaseInstance=self.decoder.phase_instance,
            artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();self.sources.bound();need(not self.failed and self.guard() is not False
            and same(self.store.read(),self.previous) and self.phase.previous is not None
            and self.phase.previous['instance']==self.decoder.phase_instance)
        if self.peers is not None:self.peers.bound()

    def save(self):
        self.bound();value=self.envelope(self.state)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def record_store(self,index):
        need(integer(index,1,512));return PrivateFeatureState(self.root/('emote-observation-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def original(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,512))
        value=self.record_store(reference['index']).read();need(value is not None and digest(value)==reference['sha256'])
        exact(value,{'iosEmoteObserverRecordVersion','runId','role','binding','primaryBinding','fixtureUrl','phaseInstance','payload'})
        need(type(value['iosEmoteObserverRecordVersion']) is int and value['iosEmoteObserverRecordVersion']==VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding)
            and same(value['primaryBinding'],self.sources.binding) and value['fixtureUrl']==self.phase.fixture_url
            and value['phaseInstance']==self.decoder.phase_instance)
        rows=unpack(value['payload']);need(len(rows)==1 and rows[0]['sequence']==reference['index'])
        return rows[0]

    def validate_original(self,reference):
        """Historical callback: no bound(), SDK guard, live clock or HTTP read."""
        exact(reference,{'iosEmoteObservationReferenceVersion','index','sha256'})
        need(type(reference['iosEmoteObservationReferenceVersion']) is int and reference['iosEmoteObservationReferenceVersion']==VERSION)
        return self.decoder.derive(self.original({k:reference[k] for k in ('index','sha256')}))

    def decode(self,value):
        exact(value,{'iosEmoteObserverVersion','runId','role','binding','primaryBinding','fixtureUrl','phaseInstance','artifactRoot','imagePolicy','payload'})
        version=value['iosEmoteObserverVersion'];need(type(version) is int and version in OWNER_READS)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0],version)));state=rows[0]
        exact(state,{'records','pending','baseline','phaseTicket','phaseBarrier','peerBarrier','imageBarrier','lastSource','lastPeer','lastImage','episode','abandoned'})
        need(type(state['records']) is list and len(state['records'])<=512 and type(state['abandoned']) is list and len(state['abandoned'])<=512)
        last=None
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);original=self.original(reference);derived=self.decoder.derive(original)
            if last is not None:
                need(derived['public']['capturedEpochMs']>=last['public']['capturedEpochMs']
                    and derived['acquisition']['hostBeforeMonotonic']>=last['acquisition']['hostAfterMonotonic'])
            last=derived
        for name in ('baseline','phaseBarrier','lastSource'):
            if state[name] is not None:self.decoder.source(state[name])
        if state['episode'] is not None:
            exact(state['episode'],{'before','played'});before=self.decoder.source(state['episode']['before'])
            played=self.decoder.source(state['episode']['played']);playback(played['group'],before['group']['native'],pid=self.decoder.pid,
                epoch=played['clockJoin']['nativeAfter']['capturedEpochMs'])
        if state['phaseTicket'] is not None:identifier(state['phaseTicket'])
        for name in ('peerBarrier','lastPeer'):
            if state[name] is not None:
                need(self.peers is not None);self.decoder.retained(self.peers,state[name])
        for name in ('imageBarrier','lastImage'):
            if state[name] is not None:self.sample(state[name],legacy=version==1)
        pending=state['pending']
        if pending is not None:
            exact(pending,{'ticket','started','source','peer','sample','original','reference'})
            identifier(pending['ticket']);exact(pending['started'],{'hostBeforeEpochMs','hostBeforeMonotonic'})
            need(number(pending['started']['hostBeforeEpochMs'],1,1e15) and number(pending['started']['hostBeforeMonotonic'],0,1e15))
            if pending['source'] is not None:self.decoder.source(pending['source'])
            if pending['peer'] is not None:self.decoder.retained(self.peers,pending['peer'])
            if pending['sample'] is not None:self.sample(pending['sample'],legacy=version==1)
            if pending['original'] is not None:
                original=unpack(pending['original']);need(len(original)==1);self.decoder.derive(original[0])
            if pending['reference'] is not None:
                need(pending['original'] is not None and same(self.original(pending['reference']),unpack(pending['original'])[0]))
        else:
            need(len(state['records'])==512 or self.record_store(len(state['records'])+1).read() is None)
        for row in state['abandoned']:
            exact(row,{'pending','afterEpochMs','afterMonotonic','gpuRetirements'})
            need(type(row['pending']) is dict and row['pending']['original'] is row['pending']['reference'] is None
                and number(row['afterEpochMs'],row['pending']['started']['hostBeforeEpochMs'],1e15)
                and number(row['afterMonotonic'],row['pending']['started']['hostBeforeMonotonic'],1e15)
                and type(row['gpuRetirements']) is list)
        if version==1:
            for name in ('imageBarrier','lastImage'):
                if state[name] is not None:state[name]=self.sample_reference(state[name])
            if pending is not None and pending['sample'] is not None:pending['sample']=self.sample_reference(pending['sample'])
        return deepcopy(state)

    def sample_reference(self,value):
        need(self.samples is not None)
        rows=[row for row in self.samples.state['rows'] if row['requestId']==value['requestId']]
        need(len(rows)==1 and same(self.samples.record(rows[0]),value))
        return dict(iosEmoteSampleReferenceVersion=1,requestId=value['requestId'],sha256=digest(value))

    def sample(self,value,*,legacy=False):
        need(self.samples is not None)
        if legacy:
            self.sample_reference(value);return deepcopy(value)
        exact(value,{'iosEmoteSampleReferenceVersion','requestId','sha256'})
        need(type(value['iosEmoteSampleReferenceVersion']) is int and value['iosEmoteSampleReferenceVersion']==1)
        rows=[row for row in self.samples.state['rows'] if row['requestId']==value['requestId']]
        need(len(rows)==1);original=self.samples.record(rows[0]);need(digest(original)==value['sha256'])
        return original

    def source_reference(self):
        need(bool(self.sources.frames));return dict(index=len(self.sources.frames),sha256=digest(self.sources.frames[-1]))

    def retain(self,original):
        self.decoder.derive(original);index=original['sequence'];store=self.record_store(index)
        value=dict(iosEmoteObserverRecordVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.sources.binding,fixtureUrl=self.phase.fixture_url,phaseInstance=self.decoder.phase_instance,payload=pack([original]))
        previous=store.read()
        if previous is None:store.write(value,None)
        else:need(same(previous,value))
        need(same(store.read(),value));return dict(index=index,sha256=digest(value))

    def resolve(self):
        """Adopt an original record after a lost local metadata return."""
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if pending['original'] is None:return False
        original=unpack(pending['original'])[0];reference=self.retain(original)
        if pending['reference'] is not None:need(same(reference,pending['reference']))
        pending['reference']=reference;self.save()
        need(reference['index']==len(self.state['records'])+1);self.state['records'].append(reference)
        self.state['lastSource']=pending['source'];self.state['lastPeer']=pending['peer']
        if pending['sample'] is not None:self.state['lastImage']=deepcopy(pending['sample'])
        self.state['pending']=None;self.save();return True

    def abandon_read(self):
        """Retain a failed passive acquisition; never claim its missing facts.

        Only fully returned source reads and independently retired GPU owners
        can be abandoned here. A child's unresolved read remains blocking.
        """
        self.bound();pending=self.state['pending']
        if pending is None:return True
        if self.resolve():return True
        self.recovery.recover()
        if self.peer_recovery is not None:self.peer_recovery.recover()
        if self.sample_recovery is not None:self.sample_recovery.recover()
        need(self.sources.state['phase']=='ready' and (self.peers is None or self.peers.state['pending'] is None)
            and (self.samples is None or self.samples.state['phase']=='ready') and len(self.state['abandoned'])<512)
        gpu=[] if self.samples is None else self.samples.drain()
        self.state['abandoned'].append(dict(pending=deepcopy(pending),afterEpochMs=self.epoch_ms(),afterMonotonic=self.monotonic(),gpuRetirements=gpu))
        self.state['pending']=None;self.save();return True

    def proof(self,current,ticket,*,input_barrier=None,retired=False):
        state=self.state;baseline=state['baseline'];barrier=state['phaseBarrier'];episode=state['episode']
        if barrier is not None:
            before=self.decoder.source(barrier);floor=before['group']['native']['animation']['history']['callSequence']
            events=[row for row in current['group']['native']['animation']['history']['events'] if row['kind']=='override' and row['eventSequence']>floor]
            need(len(events)<=1)
            if events:
                if episode is None or self.decoder.source(episode['played'])['group']['native']['animation']['history']['overrideSequence']<events[0]['overrideSequence']:
                    played=playback(current['group'],before['group']['native'],pid=self.decoder.pid,
                        epoch=current['clockJoin']['nativeAfter']['capturedEpochMs'])
                    episode=dict(before=deepcopy(barrier),played=self.source_reference());state['episode']=episode;self.save()
                    if played['state']['override'] is False:
                        # Original advancing frames and restoration can both
                        # already be present. Keep that historical episode,
                        # then acquire a distinct current restoration sample.
                        # It cannot become a claimed active playback result.
                        raise EmoteObservationPending('A completed original episode requires a later restoration sample')
        if episode is None:proof=dict(kind='idle',baseline=baseline,before=None,played=None,inputBarrier=None)
        else:
            kind='playback' if current['group']['native']['animation']['overrideActive'] else 'retired' if retired else 'restoration'
            proof=dict(kind=kind,baseline=baseline,before=episode['before'],played=episode['played'],inputBarrier=input_barrier)
            if kind=='playback':proof['inputBarrier']=None
        self.decoder.state(current,proof,ticket);return proof

    def episode_comparison(self,proof):
        """Retain the episode's actual active image/peer through quiet reads.

        A later close/reopen or repeated idle observation must compare restored
        pixels to that same episode's original playback, rather than requiring
        an already restored body to move again. All current sources and fenced
        images are still independently acquired and validated.
        """
        if proof['kind']=='restoration':
            for reference in reversed(self.state['records']):
                original=self.original(reference)
                if original['proof']['kind']=='playback' and same(original['proof']['played'],proof['played']):
                    return original['peerAfter'],original['image']
        return self.state['peerBarrier'],self.state['imageBarrier']

    def observe(self,after_sequence,*,input_barrier=None,retired=False):
        self.bound();need(integer(after_sequence,0,len(self.state['records'])) and type(retired) is bool)
        if not self.resolve():raise EmoteObservationPending('A prior original acquisition still owns its unresolved reads')
        status=self.phase.read();ticket=status['ticket'];need(len(self.state['records'])<512)
        if ticket!=self.state['phaseTicket']:
            self.state.update(phaseTicket=ticket,phaseBarrier=deepcopy(input_barrier or self.state['lastSource']),
                peerBarrier=deepcopy(self.state['lastPeer']),imageBarrier=deepcopy(self.state['lastImage']));self.save()
        elif input_barrier is not None:need(same(input_barrier,self.state['phaseBarrier']))
        self.state['pending']=dict(ticket=ticket,started=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic()),
            source=None,peer=None,sample=None,original=None,reference=None);self.save()
        self.recovery.recover();current=self.sources.read();self.recovery.follow(current)
        pending=self.state['pending'];pending['source']=self.source_reference();self.save()
        need(current['phaseAfter']['activations'][-1]['ticket']==ticket)
        if self.state['baseline'] is None:
            need(current['group']['native']['animation']['overrideActive'] is False);self.state['baseline']=pending['source'];self.save()
        proof=self.proof(current,ticket,input_barrier=input_barrier if status['verb']=='cancel' else None,retired=retired)
        if self.peers is not None:
            self.peer_recovery.recover();peer=self.peers.read();self.peer_recovery.follow(peer)
            pending['peer']=self.peers.reference();self.save()
        marker=None
        if self.samples is not None and self.samples.scope.state['phase']=='ready' and not retired:
            self.sample_recovery.recover()
            avatar=None
            if self.peers is not None:
                from ios.adapters.emote_peer import session_sha
                primary=current['world']['source']['domain']['selfSha256']
                rows=[r for r in self.peers.frames[-1]['peer']['renderers']['source']['avatars'] if session_sha(r['sessionId'])==primary]
                need(len(rows)==1);avatar=rows[0]['sessionId']
            self.samples.capture(ticket,avatar_id=avatar)
            pending['sample']=self.sample_reference(self.samples.record(self.samples.state['rows'][-1]));self.save()
            scope=self.samples.scope;marker=dict(nonce=scope.state['fileOwnership']['nonce'],url=scope.state['admission']['marker']['sourceUrl'],scope=scope.snapshot())
        final=self.phase.read(status['status']);need(final['ticket']==ticket)
        peer_before,image_before=self.episode_comparison(proof)
        if image_before is not None and 'iosEmoteSampleReferenceVersion' in image_before:image_before=self.sample(image_before)
        acquisition=dict(pending['started'],hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        original=dict(iosEmoteObservationOriginalVersion=ORIGINAL_VERSION,runId=self.run,role=self.role,binding=self.binding,
            primaryBinding=self.sources.binding,sequence=len(self.state['records'])+1,ticket=ticket,source=pending['source'],
            sourceRecovery=self.recovery.store.read(),peerRecovery=None if self.peer_recovery is None else self.peer_recovery.store.read(),proof=proof,
            peerBefore=peer_before,peerAfter=pending['peer'],marker=marker,
            imageBefore=image_before if marker is not None else None,
            image=None if pending['sample'] is None else self.sample(pending['sample']),acquisition=acquisition)
        derived=self.decoder.derive(original);pending['original']=pack([original]);self.save();self.resolve()
        self.bound();now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,acquisition['hostAfterEpochMs'],acquisition['hostBeforeEpochMs']+1500)
            and number(mono,acquisition['hostAfterMonotonic'],acquisition['hostBeforeMonotonic']+1.5)
            and now-acquisition['hostBeforeEpochMs']<1500 and mono-acquisition['hostBeforeMonotonic']<1.5)
        return deepcopy(derived['public'])

    def publisher(self):
        need(self.role=='actor');return PhaseWitnessPublisher(
            PrivateFeatureState(self.store.path.with_name('phase-publication-emotes-'+self.run+'-actor.json')),
            self.binding,self.phase,self.lock,self.guard,self.validate_original,epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def publish_latest(self):
        self.bound();need(self.role=='actor' and self.state['pending'] is None and bool(self.state['records']))
        reference=dict(iosEmoteObservationReferenceVersion=VERSION,**self.state['records'][-1])
        return self.publisher().publish(reference)
