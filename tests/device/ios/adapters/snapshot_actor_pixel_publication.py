"""Typed original Actor scenes through the existing canonical publication WAL.

No default Snapshot UI state, Primary packet, wanted state or ACK becomes an
Actor fact. Scene1 retains complete originals; this family commits their exact
content while keeping the shared publisher's bounded PFS and wire contracts.
"""
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number,NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same,unpack
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.snapshot_actor_pixel_samples import PROFILE,facts as scene_facts
from feature_journeys.witness import Client
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.snapshot_actor_pixel_set import SnapshotActorPixelSet


class SnapshotActorPixelSamplePublisher(PhaseWitnessPublisher):
    """The literal shared intent/issued/POST/lookup/CAS algorithm is inherited."""
    def original(self,value):
        need(self.area=='snapshots'and type(value)is dict)
        derived=deepcopy(self.validate_original(deepcopy(value)))
        exact(derived,{'ticket','public','acquisition'});identifier(derived['ticket'])
        public=derived['public'];exact(public,{'snapshotActorPixelPublicVersion','runId','sequence','capturedEpochMs','facts'})
        need(type(public['snapshotActorPixelPublicVersion'])is int and public['snapshotActorPixelPublicVersion']==1
            and public['runId']==self.run and integer(public['sequence'],1,8))
        clock=self.acquisition(derived['acquisition']);need(number(public['capturedEpochMs'],clock['hostBeforeEpochMs'],clock['hostAfterEpochMs']))
        scene_facts(public['facts'],captured=public['capturedEpochMs']);need(public['sequence']==public['facts']['witnessIndex'])
        return derived,dict(ticket=derived['ticket'],actor='owned-observer',actorSequence=public['sequence'],
            capturedEpochMs=public['capturedEpochMs'],facts=deepcopy(public['facts']))

    def journal(self,value):
        exact(value,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(value['schemaVersion'])is int and value['schemaVersion']==1 and value['runId']==self.run and value['area']=='snapshots'
            and number(value['sampleEpochMs'],1,1e15)and type(value['entries'])is list and len(value['entries'])<=8)
        identifier(value['ticket']);sequence=actor=0
        for row in value['entries']:
            exact(row,{'ticket','actor','actorSequence','capturedEpochMs','facts','sequence','receivedEpochMs'})
            identifier(row['ticket']);need(integer(row['sequence'],sequence+1)and integer(row['actorSequence'],actor+1,8)
                and row['actor']=='owned-observer'and number(row['capturedEpochMs'],1,value['sampleEpochMs']+250)
                and number(row['receivedEpochMs'],1,value['sampleEpochMs'])and -250<=row['receivedEpochMs']-row['capturedEpochMs']<=1500)
            scene_facts(row['facts'],captured=row['capturedEpochMs']);need(row['facts']['witnessIndex']==row['actorSequence'])
            need(same(row['facts']['binding'],self.binding));sequence,actor=row['sequence'],row['actorSequence']
        return value


class SnapshotActorPixelCanonicalPublication:
    def __init__(self,actors,actor_client=None,*,historical=False):
        need(type(actors)is SnapshotActorPixelSet and type(historical)is bool)
        self.actors,self.lock,self.binding,self.run,self.historical=actors,actors.lock,deepcopy(actors.binding),actors.run,historical
        self.store=PrivateFeatureState(actors.root/('phase-publication-snapshots-'+self.run+'-actor.json'))
        self.client,self.phase,self.publisher=actor_client,None,None
        if historical:need(actor_client is None)
        else:
            need(isinstance(actor_client,Client)and actors.sources is not None and actors.fixture_url==actor_client.url+'/runs/'+actors.run+'/')
            self.sources=actors.sources;self.feature=self.sources['observer'];self.native=self.sources['clock_source'];self.source_guard=self.sources['check']
            need(type(self.feature)is FeatureObservation and type(self.native)is NativeFeatureObservation)
            self.phase=PhaseFixtureReader(actor_client,self.run,'snapshots',epoch_ms=actors.epoch_ms,monotonic=actors.monotonic)
        self.guard()

    def guard(self):
        self.lock.assert_held();need(same(self.actors.binding,self.binding)and self.actors.run==self.run)
        if not self.historical:
            need(self.actors.sources is self.sources and same(self.sources['binding'],self.binding)
                and self.sources['observer']is self.feature and self.sources['clock_source']is self.native and self.sources['check']is self.source_guard
                and self.source_guard()is not False)
            self.feature.guard();need(self.native.pid==int(self.binding['processIdentity'])==self.feature.process['pid'])
        return True

    def prepare(self):
        need(not self.historical);self.guard()
        if self.publisher is None:
            self.phase.status()
            self.publisher=SnapshotActorPixelSamplePublisher(self.store,self.binding,self.phase,self.lock,self.guard,self.validate_original,
                epoch_ms=self.actors.epoch_ms,monotonic=self.actors.monotonic)
        return self.publisher

    def reference(self,index):
        owner=self.actors.owner(index,historical=True);original=owner.original();measured=owner.validate_original(original)
        return dict(snapshotActorPixelPublicationOriginalVersion=1,index=index,ownerSha256=original['ownerSha256'],packetOwnerSha256=measured['packetOwnerSha256'])

    def validate_original(self,value):
        # Historical source validation only: never call a live guard/getter.
        self.lock.assert_held();exact(value,{'snapshotActorPixelPublicationOriginalVersion','index','ownerSha256','packetOwnerSha256'})
        need(type(value['snapshotActorPixelPublicationOriginalVersion'])is int and value['snapshotActorPixelPublicationOriginalVersion']==1 and integer(value['index'],1,8))
        index=value['index'];owner=self.actors.owner(index,historical=True);original=owner.original();measured=owner.validate_original(original)
        need(same(value,dict(snapshotActorPixelPublicationOriginalVersion=1,index=index,ownerSha256=original['ownerSha256'],packetOwnerSha256=measured['packetOwnerSha256']))
            and same(measured['binding'],self.binding)and measured['runId']==self.run and measured['role']=='actor')
        saved=self.store.read();instance=(saved['phaseInstance']if saved is not None else self.phase.previous['instance'])
        need(measured['phaseBefore']['instance']==measured['phaseAfter']['instance']==instance)
        frame=measured['nativeOriginal']['packet']['source']['frame'];clock={key:measured['clockJoin'][key]for key in('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')}
        facts=dict(snapshotActorPixelSampleVersion=1,profile=PROFILE,binding=deepcopy(self.binding),role='actor',witnessIndex=index,
            witnessOwnerSha256=value['ownerSha256'],packetOwnerSha256=value['packetOwnerSha256'],nativeOriginalSha256=digest(measured['nativeOriginal']),
            phaseBeforeSha256=digest(measured['phaseBefore']),phaseAfterSha256=digest(measured['phaseAfter']),
            frame={key:deepcopy(frame[key])for key in('frameInstance','frameIndex','processId','recordedEpochMs','consumedEpochMs','viewport')})
        facts['frame'].update(sceneSha256=digest(frame['scene']),cameraSha256=digest(frame['camera']),worldFromCameraSha256=digest(frame['worldFromCamera']))
        png=measured['nativeOriginal']['packet']['source']['png'];read=frame['readback']
        facts['png']=dict(bytes=png['bytes'],sha256=png['sha256'],**{key:deepcopy(read[key])for key in('pixelSha256','imageExtent','sourceExtent','rectBottomLeft','readEpochMs')},callbackEpochMs=frame['callbackEpochMs'])
        resource=measured['nativeOriginal']['packet']['source']['resource']
        facts['resource']={key:resource[key]for key in('callbackScopeRetired','retainedQImage','nativeSlotProcessLifetime')}
        scene_facts(facts,captured=clock['hostAfterEpochMs'])
        return dict(ticket=measured['ticket'],public=dict(snapshotActorPixelPublicVersion=1,runId=self.run,sequence=index,capturedEpochMs=clock['hostAfterEpochMs'],facts=facts),acquisition=clock)

    def publish(self,index):
        publisher=self.prepare();reference=self.reference(index);return publisher.publish(reference)

    def history(self):
        self.guard();value=self.store.read();need(value is not None)
        state=SnapshotActorPixelSamplePublisher.archive(value,store=self.store,binding=self.binding,run=self.run,area='snapshots',
            fixture_url=self.actors.fixture_url.rsplit('/runs/',1)[0],phase_instance=value['phaseInstance'],validate_original=self.validate_original)
        need(state['pending']is None);rows=[]
        for reference in state['records']:
            path=self.store.path.with_name('phase-publication-snapshots-'+self.run+'-actor-'+str(reference['ordinal'])+'.json')
            record=PrivateFeatureState(path).read();need(record is not None and digest(record)==reference['sha256'])
            payload=unpack(record['payload']);need(len(payload)==1);rows.append(deepcopy(payload[0]))
        return rows
