"""Once-only ordered Actor-before / ordinary Capture / Actor-after originals.

A known complete old-frame reply can lead to a distinct new original read;
an unknown reply cannot. No state is published to canonical /samples here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_scene_witness import SnapshotSceneWitnessOwner,SnapshotScenePending
from ios.adapters.snapshot_scene import measured_entities,validate as scene_follow
NAME='ios-snapshot-scene-capture-order.json'
PHASES=('new','page-issued','page-saved','before-issued','before-saved','primary-before-issued','primary-before-saved','capture-issued','capture-saved','provenance-issued','provenance-saved','after-issued','complete')


class SnapshotSceneActorSet:
    """One actual held Actor lock/binding; fresh sources are optional history only."""
    def __init__(self,root,lock,binding,run,fixture_url,*,sources=None,client=None,epoch_ms=None,monotonic=None):
        self.root,self.lock,self.binding,self.run,self.fixture_url=root,lock,deepcopy(context(binding)),identifier(run),fixture_url
        need(type(lock) is ScriptSourceLock and root.is_absolute() and root.resolve(strict=True)==root
            and lock.path==root/'script-feature-sources.lock' and fixture_url.endswith('/runs/'+run+'/'))
        self.sources,self.client,self.epoch_ms,self.monotonic=sources,client,epoch_ms,monotonic
        lock.assert_held()
        if sources is not None:
            need(same(sources['binding'],binding) and callable(sources['check']) and sources['check']() is not False
                and all(callable(fn) for fn in (epoch_ms,monotonic)))

    def store(self,index):
        need(integer(index,1,8));return PrivateFeatureState(self.root/('ios-snapshot-actor-scene-witness-'+format(index,'04d')+'.json'))

    def owner(self,index,*,historical):
        self.lock.assert_held();store=self.store(index)
        if historical:return SnapshotSceneWitnessOwner(store,self.lock,self.binding,self.run,index,self.fixture_url,historical=True)
        need(self.sources is not None and self.sources['check']() is not False)
        phase=PhaseFixtureReader(self.client,self.run,'snapshots',epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        return SnapshotSceneWitnessOwner(store,self.lock,self.binding,self.run,index,self.fixture_url,phase=phase,
            feature=self.sources['observer'],native=self.sources['clock_source'],guard=self.sources['check'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def native_floor(self,indices):
        need(self.sources is not None);last=None
        for index in indices:
            if self.store(index).read() is None:continue
            witness=self.owner(index,historical=True)
            if witness.packet_store().read() is None:continue
            child=witness.child(historical=True);state=child.state
            if state['phase']=='retained':last=child.historical()['acquisition']['nativeAfter']
            elif state['phase']=='issued':last=state['started']['nativeBefore']
        if last is not None:
            native=self.sources['clock_source']
            if native.instance is None:restore(native,last)
            else:need(native.instance==last['instance'] and native.sequence>=last['sequence'] and native.lifecycle==last['lifecycle'])


class SnapshotSceneCaptureOrder:
    def __init__(self,page,actors,*,epoch_ms,monotonic,historical=False):
        need(type(page) is IOSSnapshotPageOwner and page.combined_profile() and type(actors) is SnapshotSceneActorSet
            and type(historical) is bool and all(callable(fn) for fn in (epoch_ms,monotonic)))
        self.page,self.actors,self.lock,self.binding,self.run=page,actors,page.lock,deepcopy(page.binding),page.run
        self.epoch_ms,self.monotonic,self.historical=epoch_ms,monotonic,historical
        need(page.historical is historical and page.store.path.parent!=actors.root and page.lock.path!=actors.lock.path
            and page.binding['targetFingerprint']!=actors.binding['targetFingerprint'] and page.run==actors.run
            and page.fixture_url==actors.fixture_url and all(page.binding[k]==actors.binding[k] for k in ('sourceRevision','artifactSha256')))
        self.store=PrivateFeatureState(page.store.path.with_name(NAME));self.lock.assert_held();actors.lock.assert_held()
        self.previous=self.store.read();self.state=dict(phase='new',ticket=None,started=None,before=None,primaryBeforeCount=None,primaryBefore=None,capture=None,
            callBefore=None,callAfter=None,provenance=None,attempts=[],finished=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        elif historical:need(False)
        else:
            # Old capture completion can never receive retrospective bracketing.
            existing=self.capture_optional()
            need(existing is None or existing.state['phase'] in ('new','preparing','prepared')
                and not any(row['label']=='capture' for row in existing.state['inputSlots']))
            for index in range(1,9):
                need(actors.store(index).read() is None
                    and PrivateFeatureState(actors.root/('ios-snapshot-actor-native-scene-'+format(index,'04d')+'.json')).read() is None)

    @classmethod
    def archive(cls,store,lock,binding,run,fixture_url,actor_root,actor_lock,actor_binding,*,epoch_ms,monotonic):
        need(cls is SnapshotSceneCaptureOrder and type(store) is PrivateFeatureState and store.path.name==NAME)
        page=IOSSnapshotPageOwner.archive(PrivateFeatureState(store.path.with_name('ios-snapshot-page-owner.json')),
            lock,binding,run,fixture_url,combined=True)
        actors=SnapshotSceneActorSet(actor_root,actor_lock,actor_binding,run,fixture_url)
        owner=cls(page,actors,epoch_ms=epoch_ms,monotonic=monotonic,historical=True)
        need(owner.store.path==store.path and owner.state['phase']=='complete');return owner

    def envelope(self,state):
        return dict(iosSnapshotSceneCaptureOrderVersion=1,binding=self.binding,actorBinding=self.actors.binding,
            runId=self.run,fixtureUrl=self.page.fixture_url,actorRoot=str(self.actors.root),payload=pack([state]))

    def bound(self):
        self.lock.assert_held();self.actors.lock.assert_held();self.page.bound()
        need(same(self.store.read(),self.previous) and (self.previous is None or same(self.envelope(self.state),self.previous)))
        if not self.historical:need(self.actors.sources['check']() is not False)

    def capture_optional(self):
        store=PrivateFeatureState(self.store.path.with_name('ios-snapshot-primary-capture-owner.json'))
        if store.read() is None:return None
        return IOSSnapshotCaptureOwner.archive(store,self.lock,self.binding,self.run,self.page.fixture_url,combined=True)

    def capture(self):
        owner=self.capture_optional();need(owner is not None and owner.state['phase'] in ('copied','file-cleaned'))
        result=owner.result();need(same(result,owner.state['result']));return owner,result

    @staticmethod
    def stamp(value):
        exact(value,{'epochMs','monotonic'});need(number(value['epochMs'],1,1e15) and number(value['monotonic'],0,1e15));return value

    @staticmethod
    def span(a,b):
        SnapshotSceneCaptureOrder.stamp(a);SnapshotSceneCaptureOrder.stamp(b)
        need(0<=b['epochMs']-a['epochMs']<25000 and 0<=b['monotonic']-a['monotonic']<25
            and abs(b['epochMs']-a['epochMs']-(b['monotonic']-a['monotonic'])*1000)<=250)

    def now(self):return self.stamp(dict(epochMs=self.epoch_ms(),monotonic=self.monotonic()))
    def deadline(self):
        need(not self.historical and self.state['started'] is not None);self.span(self.state['started'],self.now())

    def original_actor(self,index,reference):
        owner=self.actors.owner(index,historical=True);original=owner.original();measured=owner.validate_original(original)
        need(reference==dict(index=index,ownerSha256=original['ownerSha256'],packetOwnerSha256=measured['packetOwnerSha256'])
            and measured['ticket']==self.state['ticket']);return measured

    def decode(self,value):
        exact(value,{'iosSnapshotSceneCaptureOrderVersion','binding','actorBinding','runId','fixtureUrl','actorRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosSnapshotSceneCaptureOrderVersion']) is int
            and value['iosSnapshotSceneCaptureOrderVersion']==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,set(self.state));need(state['phase'] in PHASES);pos=PHASES.index(state['phase'])
        if pos==0:
            need(state==dict(phase='new',ticket=None,started=None,before=None,primaryBeforeCount=None,primaryBefore=None,capture=None,callBefore=None,callAfter=None,
                provenance=None,attempts=[],finished=None));return deepcopy(state)
        identifier(state['ticket']);self.stamp(state['started'])
        need((state['before'] is not None)==(pos>=PHASES.index('before-saved'))
            and (state['primaryBeforeCount'] is not None)==(pos>=PHASES.index('primary-before-issued'))
            and (state['primaryBefore'] is not None)==(pos>=PHASES.index('primary-before-saved'))
            and (state['callBefore'] is not None)==(pos>=PHASES.index('capture-issued'))
            and (state['callAfter'] is not None)==(pos>=PHASES.index('capture-saved'))
            and (state['capture'] is not None)==(pos>=PHASES.index('capture-saved'))
            and (state['provenance'] is not None)==(pos>=PHASES.index('provenance-saved'))
            and (state['finished'] is not None)==(state['phase']=='complete')
            and type(state['attempts']) is list and len(state['attempts'])<=7
            and (not state['attempts']or pos>=PHASES.index('after-issued')))
        if state['primaryBeforeCount'] is not None:need(integer(state['primaryBeforeCount'],1,383))
        if state['primaryBefore'] is not None:need(state['primaryBefore']['index']==state['primaryBeforeCount']+1)
        for key in ('callBefore','callAfter','finished'):
            if state[key] is not None:self.span(state['started'],state[key])
        if state['callAfter'] is not None:self.span(state['callBefore'],state['callAfter'])
        for i,row in enumerate(state['attempts']):
            exact(row,{'index','mode','original'});need(row['index']==i+2 and row['mode'] in ('issued','known-old','accepted'))
            need((row['original'] is None)==(row['mode']=='issued'))
            if row['mode']!='known-old':need(i==len(state['attempts'])-1)
        if state['phase']=='complete':need(state['attempts'] and state['attempts'][-1]['mode']=='accepted')
        return deepcopy(state)

    def save(self):
        need(not self.historical);self.lock.assert_held();self.actors.lock.assert_held()
        need(self.page.guard() is not False and self.actors.sources['check']() is not False and same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def actor(self,index,*,born_here):
        self.deadline()
        if self.actors.store(index).read() is None and not born_here:
            raise SnapshotScenePending('Actor owner birth is uncertain; no replacement query is allowed')
        self.actors.native_floor([1]+[row['index']for row in self.state['attempts']])
        owner=self.actors.owner(index,historical=False);original=owner.acquire(self.state['ticket']);value=owner.validate_original(original)
        reference=dict(index=index,ownerSha256=original['ownerSha256'],packetOwnerSha256=value['packetOwnerSha256'])
        return reference,value

    @operation
    def acquire(self,ticket):
        need(not self.historical);identifier(ticket);self.bound()
        if self.state['phase']=='complete':need(self.state['ticket']==ticket);return self.proof()
        born_before=False
        if self.state['phase']=='new':
            self.state.update(phase='page-issued',ticket=ticket,started=self.now());self.save()
        need(self.state['ticket']==ticket);self.deadline()
        if self.state['phase']=='page-issued':
            self.page.open(ticket);self.deadline();self.state['phase']='page-saved';self.save()
        if self.state['phase']=='page-saved':self.state['phase']='before-issued';self.save();born_before=True
        if self.state['phase']=='before-issued':
            ref,_measured=self.actor(1,born_here=born_before);self.state.update(phase='before-saved',before=ref);self.save()
        if self.state['phase']=='before-saved':
            self.state.update(phase='primary-before-issued',primaryBeforeCount=len(self.page.state['records']));self.save()
        if self.state['phase']=='primary-before-issued':
            self.deadline();count=self.state['primaryBeforeCount'];self.page.recover_observation()
            if len(self.page.state['records'])==count:self.page.observe()
            need(len(self.page.state['records'])==count+1)
            ref=self.page.state['records'][-1];frame=self.page.original(ref)
            need(self.page.route(frame)['kind']=='snapshot')
            before=self.original_actor(1,self.state['before']);clock=frame['clockJoin']
            need(clock['hostBeforeEpochMs']>=before['clockJoin']['hostAfterEpochMs']
                and clock['hostBeforeMonotonic']>=before['clockJoin']['hostAfterMonotonic'])
            self.state.update(phase='primary-before-saved',primaryBefore=deepcopy(ref));self.save()
        if self.state['phase']=='primary-before-saved':
            self.state.update(phase='capture-issued',callBefore=self.now());self.save()
        if self.state['phase']=='capture-issued':
            self.deadline()
            # This is the actual unchanged normal Page/Capture/Input WAL. Its
            # own issued-input recovery never resends an unknown normal input.
            result=self.page.capture(ticket);self.deadline();owner,captured=self.capture()
            need(same(result['capture'],captured))
            self.state.update(phase='capture-saved',callAfter=self.now(),capture=dict(resultSha256=digest(captured),
                inputIndex=owner.state['captureInput'],phaseSha256=digest(owner.state['phaseOriginal'])));self.save()
        if self.state['phase']=='capture-saved':self.state['phase']='provenance-issued';self.save()
        if self.state['phase']=='provenance-issued':
            self.deadline();live=self.page.runtime.capture_child(self.page);live.provenance();self.deadline()
            rows=[row for row in live.state['slots']if row['kind']=='provenance'and row['label']=='ordinary-frame-provenance'];need(len(rows)==1)
            child=live.history('provenance',rows[0]['index'])
            self.state.update(phase='provenance-saved',provenance=dict(index=child.index,ownerSha256=digest(child.previous)));self.save()
        born_after=False
        if self.state['phase']=='provenance-saved':
            self.state['phase']='after-issued';self.state['attempts'].append(dict(index=2,mode='issued',original=None));self.save();born_after=True
        if self.state['phase']=='after-issued':
            row=self.state['attempts'][-1]
            if row['mode']=='known-old':
                self.deadline();need(len(self.state['attempts'])<7)
                row=dict(index=row['index']+1,mode='issued',original=None);self.state['attempts'].append(row);self.save();born_after=True
            need(row['mode']=='issued');ref,after=self.actor(row['index'],born_here=born_after)
            frame=after['nativeOriginal']['packet']['source']['frame'];floor=after['nativeOriginal']['acquisition']['nativeBefore']['capturedEpochMs']
            if frame['consumedEpochMs']<floor:
                row.update(mode='known-old',original=ref);self.save()
                raise SnapshotScenePending('Complete Actor original has an older rendered frame; a separately journaled new read is required')
            row.update(mode='accepted',original=ref);self.state.update(phase='complete',finished=self.now());self.save()
        return self.proof()

    @operation
    def proof(self):
        self.bound();need(self.state['phase']=='complete');self.decode(self.previous)
        before=self.original_actor(1,self.state['before']);after=None
        for row in self.state['attempts']:
            current=self.original_actor(row['index'],row['original']);frame=current['nativeOriginal']['packet']['source']['frame']
            floor=current['nativeOriginal']['acquisition']['nativeBefore']['capturedEpochMs']
            need((frame['consumedEpochMs']>=floor)==(row['mode']=='accepted'))
            if after is not None:
                follow_native(after['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore'])
                scene_follow(current['nativeOriginal']['packet'],current['nativeOriginal']['query'],int(self.actors.binding['processIdentity']),previous=after['nativeOriginal']['packet'])
            after=current
        need(after is not None)
        follow_native(before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
        scene_follow(after['nativeOriginal']['packet'],after['nativeOriginal']['query'],int(self.actors.binding['processIdentity']),previous=before['nativeOriginal']['packet'])
        owner,captured=self.capture();saved=self.state['capture']
        need(saved==dict(resultSha256=digest(captured),inputIndex=owner.state['captureInput'],phaseSha256=digest(owner.state['phaseOriginal'])))
        prov=self.state['provenance'];packet=owner.history('provenance',prov['index']);need(digest(packet.previous)==prov['ownerSha256'])
        frame=packet.join_capture(owner)['provenance']['frame'];need(frame['snapshotFrameProvenanceVersion']==2)
        # This independently retained real Primary observation is AFTER the
        # Actor-before original, and its OWN native cutoff precedes the actual
        # ordinary captured frame. Wrapper call stamps alone grant no order.
        native_before=self.page.original(self.state['primaryBefore'])
        need(self.page.route(native_before)['kind']=='snapshot'
            and same(native_before['phaseBefore']['activations'],owner.state['phaseOriginal']['activations'])
            and native_before['phaseBefore']['instance']==owner.state['phaseOriginal']['instance'])
        anchor=native_before['clockJoin'];cutoff=anchor['nativeAfter']['capturedEpochMs']
        need(frame['recordedEpochMs']>cutoff
            and before['clockJoin']['hostAfterEpochMs']<=anchor['hostBeforeEpochMs']
            and before['clockJoin']['hostAfterMonotonic']<=anchor['hostBeforeMonotonic']
            and anchor['hostAfterEpochMs']<=self.state['callBefore']['epochMs']
            and anchor['hostAfterMonotonic']<=self.state['callBefore']['monotonic'])
        follow_native(anchor['nativeAfter'],packet.historical()['acquisition']['nativeBefore'])
        baseline=measured_entities(frame['scene'])
        for actor in (before,after):
            raw=actor['nativeOriginal']['packet']['source']['frame']
            need(same(measured_entities(raw['scene']),baseline) and same(raw['camera'],frame['camera'])
                and same(raw['worldFromCamera'],frame['worldFromCamera']) and same(raw['viewport'],frame['viewport'])
                and actor['phaseBefore']['instance']==owner.state['phaseOriginal']['instance']
                and same(actor['phaseBefore']['activations'],owner.state['phaseOriginal']['activations'])
                and same(actor['phaseAfter']['activations'],actor['phaseBefore']['activations']))
        b=before['clockJoin'];a=after['clockJoin'];cb=self.state['callBefore'];ca=self.state['callAfter']
        need(b['hostAfterEpochMs']<=cb['epochMs']<=ca['epochMs']<=a['hostBeforeEpochMs']
            and b['hostAfterMonotonic']<=cb['monotonic']<=ca['monotonic']<=a['hostBeforeMonotonic'])
        self.span(self.state['started'],self.state['finished'])
        return dict(iosSnapshotSceneCaptureOrderResultVersion=1,runId=self.run,ticket=self.state['ticket'],binding=deepcopy(self.binding),
            actorBinding=deepcopy(self.actors.binding),normalCaptureResultSha256=digest(captured),
            ordinaryProvenanceOwnerSha256=digest(packet.previous),actorBeforeOwnerSha256=before['ownerSha256'],actorAfterOwnerSha256=after['ownerSha256'],
            captureCallBefore=deepcopy(cb),captureCallAfter=deepcopy(ca),primaryBeforeOriginalSha256=digest(native_before),
            primaryNativeBeforeCapturedFrameEstablished=True,actorBeforeCaptureAfterOriginalOrderEstablished=True,
            actualIndependentActorSceneInputsAgree=True,unknownInputResendAllowed=False,canonicalActorPublicationRequired=True,
            actorRenderedPixelsRequired=True,fullSceneAppearanceFidelityRequired=True,destinationCompositionRequired=True,
            pairedCleanupRequired=True,wholeFeatureRequired=True,nativeQualified=False,deviceQualified=False,wholeQualified=False)
