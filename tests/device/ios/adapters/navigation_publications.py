"""Original Worlds publication continuity across the proven process transfer.

The canonical witness journal keeps the initial candidate binding. Each new
reference explicitly names its process stage; facts and global cursor are
reconstructed from actual role-owned sources and the typed transfer archive.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same
from feature_journeys.contract import result as public_result
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_observer import NavigationObserver
from ios.adapters.navigation_process_owner import NavigationProcessOwner
from ios.adapters.navigation_process_context import source_basis
from ios.adapters.graphics_history import follow_native
from ios.adapters import navigation_source_prefix as prefix

VERSION=1


class NavigationPublications:
    def __init__(self,initial,observers,*,transfer=None,restoration=None,guard=lambda:True,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(initial,NavigationAdmissionOwner) and type(observers) is dict
            and set(observers)==({0} if transfer is None else {0,1})
            and all(type(key) is int and isinstance(value,NavigationObserver) for key,value in observers.items())
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        initial.bound();self.initial,self.observers,self.transfer=initial,observers,transfer
        self.lock,self.run,self.binding=initial.lock,initial.run,deepcopy(initial.binding)
        self.guard,self.epoch_ms,self.monotonic=guard,epoch_ms,monotonic
        self.role=observers[0].role;self.stage=max(observers)
        self.restoration=restoration
        if restoration is not None:
            from ios.adapters.navigation_restoration import NavigationRestoration
            need(type(restoration) is NavigationRestoration and transfer is restoration.transfer
                and restoration.lock is self.lock and restoration.flow.role==self.role
                and restoration.flow.run==self.run and same(restoration.binding,observers[self.stage].binding))
        self.store=PrivateFeatureState(initial.store.path.with_name('phase-publication-world-navigation-'+self.run+'-actor.json'))
        self.bound();self.validate_sources()

    def bound(self):
        self.lock.assert_held();self.initial.bound();need(self.guard() is not False)
        for stage,observer in self.observers.items():
            need(observer.stage==stage and observer.run==self.run and observer.role==self.role
                and observer.lock.path==self.lock.path and observer.store.path.parent==self.store.path.parent)
            observer.bound();need(same(observer.envelope(observer.state),observer.store.read()))
        if self.transfer is not None:
            need(isinstance(self.transfer,NavigationProcessOwner) and self.transfer.lock.path==self.lock.path
                and self.transfer.run==self.run and self.transfer.store.path.parent==self.store.path.parent)
            self.transfer.bound()

    def validate_sources(self):
        self.bound();initial=self.initial.archive();bases={0:initial}
        need(same(self.observers[0].binding,self.binding))
        old=self.observers[0].owners()
        if self.transfer is not None:
            context=self.transfer.archive();need(same(context['initialAdmission'],initial))
            bases[1]=source_basis(context,self.transfer.owner_files)
            need(same(self.observers[1].binding,bases[1]['binding']) and old
                and self.observers[0].state['rows'][-1]['status']=='observed')
            before=context['before'];follow_native(old[-1].state['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
            raw=deepcopy(before['originals']);raw['navigationBefore']=raw.pop('navigation')
            prefix.follow(old[-1].state['originals'],raw,self.run,int(self.binding['processIdentity']))
        for stage,observer in self.observers.items():
            owners=old if stage==0 else observer.owners()
            if not owners:continue
            base=bases[stage];first=owners[0]
            follow_native(base['clockJoin']['nativeAfter'],first.state['nativeStart']['nativeBefore'])
            raw=deepcopy(base['originals']);raw['currentNavigation']=raw.pop('navigation')
            prefix.follow(raw,first.state['originals'],self.run,int(observer.binding['processIdentity']))
        self.bound()

    def reference(self,observer):
        need(observer is self.observers[self.stage]);value=observer.latest()
        return dict(iosNavigationPublicationReferenceVersion=VERSION,stage=self.stage,
            requestId=value['requestId'],ownerSha256=value['ownerSha256'])

    def validate_original(self,reference):
        self.validate_sources()
        if type(reference) is dict and 'iosNavigationRestorationReferenceVersion' in reference:
            need(self.restoration is not None)
            return self.restoration.validate_original(reference)
        if type(reference) is dict and set(reference)=={'requestId','ownerSha256'}:
            # A literal existing writer-1 stage-zero reference keeps its old
            # interpretation and bytes when the whole owner adopts the ledger.
            stage=0;local=reference
        else:
            exact(reference,{'iosNavigationPublicationReferenceVersion','stage','requestId','ownerSha256'})
            need(type(reference['iosNavigationPublicationReferenceVersion']) is int
                and reference['iosNavigationPublicationReferenceVersion']==VERSION
                and type(reference['stage']) is int and reference['stage'] in self.observers)
            stage=reference['stage'];local={key:reference[key] for key in ('requestId','ownerSha256')}
        value=self.observers[stage].validate_original(local)
        offset=0 if stage==0 else self.observers[0].state['sequence']
        public=deepcopy(value['public']);public['sequence']+=offset
        for artifact in public['artifacts']:artifact['sequence']+=offset
        value['public']=public_result('feature.world-navigation.observe',public)
        self.bound();return value

    def phase_instance(self):
        owners=self.observers[0].owners();need(owners)
        return owners[0].state['phaseBefore']['originals']['phaseBefore']['instance']

    def state(self):
        self.bound();value=self.store.read()
        if value is None:return None
        need(self.role=='actor')
        owners=self.observers[0].owners();need(owners)
        url=owners[0].state['options']['fixture_url'].split('/runs/')[0]
        return PhaseWitnessPublisher.archive(value,store=self.store,binding=self.binding,run=self.run,
            area='world-navigation',fixture_url=url,phase_instance=self.phase_instance(),validate_original=self.validate_original)

    def for_observer(self,observer):
        need(observer is self.observers[self.stage]);return None if self.role=='primary' else self.state()

    def latest(self):return deepcopy(self.validate_original(self.reference(self.observers[self.stage]))['public'])

    def publisher(self,client):
        need(self.role=='actor' and isinstance(client,Client));self.bound()
        owners=self.observers[0].owners();need(owners
            and client.url+'/runs/'+self.run+'/'==owners[0].state['options']['fixture_url'])
        phase=PhaseFixtureReader(client,self.run,'world-navigation',epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        phase.status();need(phase.previous['instance']==self.phase_instance())
        return PhaseWitnessPublisher(self.store,self.binding,phase,self.lock,self.bound,self.validate_original,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def publish(self,client,*,restored=False):
        need(type(restored) is bool and (not restored or self.restoration is not None))
        reference=self.restoration.reference() if restored else self.reference(self.observers[self.stage])
        publisher=self.publisher(client);publisher.publish(reference)
        receipt=publisher.load(publisher.state['records'][-1]);need(receipt['mode']=='published');return deepcopy(receipt['entry'])

    def resolve(self,client):
        publisher=self.publisher(client)
        need(publisher.resolve() and publisher.state['records']);receipt=publisher.load(publisher.state['records'][-1])
        need(receipt['mode']=='published');return deepcopy(receipt['entry'])
