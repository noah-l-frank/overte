"""Independent Worlds acquisition ledger and one-send actor publication.

Original per-request owners supply all facts. This component never sends a
product input, admits a scene/restart, derives cleanup absence or enables a
whole feature capability. A sample intent is checked against actual sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier,result as public_result
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.navigation_observation_owner import NavigationObservationOwner,validation_round
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.navigation_sample import NavigationMarkerPending
from navigation_observation import same_viewpoint,viewpoint_urls

VERSION=1


class NavigationObserver:
    def __init__(self,store,images,*,factory=None,historical=False,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(images,NavigationSamples) and type(historical) is bool
            and callable(epoch_ms) and callable(monotonic) and (factory is None if historical else callable(factory)))
        self.store,self.images,self.lock=store,images,images.lock
        self.binding,self.run,self.role,self.stage=deepcopy(images.binding),images.run,images.role,images.stage
        need(store.path==images.store.path.with_name('ios-navigation-'+self.role+'-'+str(self.stage)+'-observer.json'))
        self.factory,self.historical,self.epoch_ms,self.monotonic=factory,historical,epoch_ms,monotonic
        self.lock.assert_held();self.previous=store.read()
        self.state=dict(rows=[],sequence=0)
        if self.previous is not None:self.state=self.decode(self.previous)
        elif historical:need(False)
        else:self.save()

    def envelope(self,state):
        return dict(iosNavigationObserverVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            binding=self.binding,artifactRoot=str(self.images.root),payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        if not self.historical:self.images.bound()

    def path(self,request):
        identifier(request)
        return self.store.path.with_name('ios-navigation-'+self.role+'-'+str(self.stage)+'-'+request+'-observation.json')

    def owners(self,rows=None):
        with validation_round():return self._owners(rows)

    def _owners(self,rows=None):
        """Reopen actual immutable carriers/PNGs, without any live factory."""
        rows=self.state['rows'] if rows is None else rows
        images=NavigationSamples(self.images.store,self.images.root,self.binding,self.run,self.role,self.stage,
            self.lock,lambda:True,historical=True)
        result=[];previous=None
        for row in rows:
            if row['status']=='reserved':break
            store=PrivateFeatureState(self.path(row['requestId']));value=store.read()
            need(value is not None and digest(value)==row['ownerSha256'])
            owner=NavigationObservationOwner(store,images,self.binding,self.run,self.role,self.stage,row['requestId'],
                self.lock,lambda:True,previous=previous,historical=True)
            owner.archive();need(owner.state['phase']==row['status'] and owner.state['ticket']==row['ticket'])
            result.append(owner);previous=owner
        return result

    def decode(self,value):
        exact(value,{'iosNavigationObserverVersion','runId','role','stage','binding','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationObserverVersion']) is int
            and value['iosNavigationObserverVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'rows','sequence'})
        need(type(state['rows']) is list and len(state['rows'])<=512 and integer(state['sequence'],0,512))
        seen=set();sequence=0
        for index,row in enumerate(state['rows']):
            exact(row,{'requestId','ticket','status','childStarted','ownerSha256','sequence'})
            identifier(row['requestId']);identifier(row['ticket']);need(row['requestId'] not in seen);seen.add(row['requestId'])
            need(row['status'] in ('reserved','observed','marker-pending','failed') and type(row['childStarted']) is bool)
            if row['status']=='reserved':
                need(index==len(state['rows'])-1 and row['ownerSha256'] is row['sequence'] is None)
            else:
                need(row['childStarted'] and type(row['ownerSha256']) is str and len(row['ownerSha256'])==64)
                if row['status']=='observed':sequence+=1;need(type(row['sequence']) is int and row['sequence']==sequence)
                else:need(row['sequence'] is None)
        need(sequence==state['sequence']);owners=self.owners(state['rows'])
        return deepcopy(state)

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def measurement(self,owner,row):
        actual=owner.archive();need(row['status']=='observed' and actual is not None and row['sequence'] is not None)
        name=unpack(owner.state['imageArchive']['payload'])[0]
        name=unpack(name['payload'])[0]['frameOwner']['name']
        return dict(iosNavigationObservedVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            binding=deepcopy(self.binding),requestId=owner.request,ticket=row['ticket'],sequence=row['sequence'],
            capturedEpochMs=actual['acquiredHostEpochMs'],state=deepcopy(actual['state']),imageName=name,
            imageSha256=actual['image']['image']['sha256'],nativeAfter=deepcopy(owner.state['clockJoin']['nativeAfter']),
            ownerSha256=digest(owner.previous))

    def latest(self):
        """Historical original result; this method supplies no fresh return."""
        self.bound();need(same(self.envelope(self.state),self.previous))
        owners=self.owners();need(owners and owners[-1].state['phase']=='observed')
        value=self.measurement(owners[-1],self.state['rows'][-1]);self.bound();return value

    def live(self,row):
        need(not self.historical);previous=self.owners();previous=previous[-1] if previous else None
        owner=self.factory(row['requestId'],previous)
        need(isinstance(owner,NavigationObservationOwner) and not owner.historical and owner.store.path==self.path(row['requestId'])
            and same(owner.binding,self.binding) and (owner.run,owner.role,owner.stage)==(self.run,self.role,self.stage)
            and owner.lock.path==self.lock.path and owner.images.root==self.images.root
            and owner.images.store.path==self.images.store.path)
        return owner

    def adopt(self,row,owner):
        need(row is self.state['rows'][-1] and row['status']=='reserved' and row['childStarted'])
        owner.archive();status=owner.state['phase'];need(status in ('observed','marker-pending','failed'))
        row.update(status=status,ownerSha256=digest(owner.previous))
        if status=='observed':self.state['sequence']+=1;row['sequence']=self.state['sequence']
        # The child may have advanced the shared image index. Adopt its exact
        # carrier, never reconstruct an old index as a new source floor.
        self.images=owner.images;self.save()
        return None if status!='observed' else self.measurement(owner,row)

    def read(self,ticket,url,label,host_barrier,*,publication_owner=None,**options):
        need(not self.historical);self.bound();identifier(ticket)
        need(same(self.envelope(self.state),self.previous))
        need(not self.state['rows'] or self.state['rows'][-1]['status']!='reserved')
        if publication_owner is None:publication=self.publication_state()
        else:
            from ios.adapters.navigation_publications import NavigationPublications
            need(isinstance(publication_owner,NavigationPublications));publication=publication_owner.for_observer(self)
        need(publication is None or publication['pending'] is None)
        need(len(self.state['rows'])<512 and type(label) is str and label in ('A','B')
            and same_viewpoint(url,viewpoint_urls(options['provider_inputs']['sceneUrl'])[label]))
        row=dict(requestId=uuid.uuid4().hex,ticket=ticket,status='reserved',childStarted=False,ownerSha256=None,sequence=None)
        self.state['rows'].append(row);self.save();owner=self.live(row)
        need(owner.store.read() is None);row['childStarted']=True;self.save()
        pending=False
        try:owner.acquire(ticket,url,label,host_barrier,**options)
        except NavigationMarkerPending:pending=True
        measured=self.adopt(row,owner)
        if pending:raise NavigationMarkerPending('Independent Worlds original marker remains pending')
        need(measured is not None);clock=owner.state['clockJoin'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
            and epoch-clock['hostBeforeEpochMs']<1500 and number(mono,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5)
            and mono-clock['hostBeforeMonotonic']<1.5
            and abs(epoch-clock['hostBeforeEpochMs']-(mono-clock['hostBeforeMonotonic'])*1000)<=250)
        self.bound();return deepcopy(measured)

    def recover(self,*,abandon_sources=False,directory=None):
        """Explicit old-return recovery, never another capture/source request."""
        need(not self.historical and type(abandon_sources) is bool and (not abandon_sources or directory is None));self.bound()
        need(same(self.envelope(self.state),self.previous))
        need(self.state['rows'] and self.state['rows'][-1]['status']=='reserved')
        row=self.state['rows'][-1];need(row['childStarted']);owner=self.live(row);need(owner.state is not None)
        if owner.state['phase']=='reading':
            if abandon_sources:owner.abandon_sources()
            else:owner.recover(directory=directory)
        return self.adopt(row,owner)

    def publication_store(self):
        return PrivateFeatureState(self.store.path.with_name('phase-publication-world-navigation-'+self.run+'-actor.json'))

    def validate_original(self,reference):
        """Canonical publisher callback: actual original files, no live SDK."""
        self.lock.assert_held();exact(reference,{'requestId','ownerSha256'})
        need(same(self.store.read(),self.previous) and same(self.envelope(self.state),self.previous))
        rows=[row for row in self.state['rows'] if row['requestId']==reference['requestId']]
        need(len(rows)==1 and rows[0]['ownerSha256']==reference['ownerSha256'])
        owners=[owner for owner in self.owners() if owner.request==reference['requestId']];need(len(owners)==1)
        owner=owners[0];measured=self.measurement(owner,rows[0]);clock=owner.state['clockJoin']
        resources=['entity:ios-navigation-scene']
        if measured['state']['panel']:resources.append('panel:ios-navigation-places')
        if owner.state['originals']['ui']['navigationInventory']['roots']:resources.append('panel:ios-navigation-address')
        if measured['state']['error']!='none':resources.append('panel:ios-navigation-error')
        public=public_result('feature.world-navigation.observe',dict(schemaVersion=1,contractVersion=16,runId=self.run,
            sequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],state=measured['state'],resources=resources,
            lifecycle=measured['nativeAfter']['lifecycle'],artifacts=[dict(kind='image',source='world-render-target',
                name=measured['imageName'],sequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],ticket=measured['ticket'])]))
        return dict(ticket=measured['ticket'],public=public,
            acquisition={key:clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})

    def publication_state(self):
        value=self.publication_store().read()
        if value is None:return None
        need(self.role=='actor');owners=self.owners();need(owners)
        phase=owners[0].state['phaseBefore']['originals']['phaseBefore']
        return PhaseWitnessPublisher.archive(value,store=self.publication_store(),binding=self.binding,run=self.run,
            area='world-navigation',fixture_url=owners[0].state['options']['fixture_url'].split('/runs/')[0],
            phase_instance=phase['instance'],validate_original=self.validate_original)

    def publisher(self,client):
        need(not self.historical and self.role=='actor' and self.stage==0 and isinstance(client,Client));self.bound()
        owners=self.owners();need(owners and client.url+'/runs/'+self.run+'/'==owners[0].state['options']['fixture_url'])
        phase=PhaseFixtureReader(client,self.run,'world-navigation',epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        phase.status()
        return PhaseWitnessPublisher(self.publication_store(),self.binding,phase,self.lock,self.bound,self.validate_original,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def confirm_publication(self,client):
        """Resolve the canonical publisher's actual receipt without a resend."""
        publisher=self.publisher(client);need(publisher.resolve() and publisher.state['records'])
        receipt=publisher.load(publisher.state['records'][-1]);need(receipt['mode']=='published')
        return deepcopy(receipt['entry'])

    def publish(self,client):
        measured=self.latest();publisher=self.publisher(client)
        publisher.publish(dict(requestId=measured['requestId'],ownerSha256=measured['ownerSha256']))
        receipt=publisher.load(publisher.state['records'][-1]);need(receipt['mode']=='published')
        return deepcopy(receipt['entry'])
