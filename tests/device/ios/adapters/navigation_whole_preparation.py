"""Own both untouched images before the existing ordinary Worlds scene entry.

Original queries are admitted once. This whole-run preparation does not enable
the incomplete public cleanup/terminal capability by itself.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_static_comparison import untouched

VERSION=1
ROLES=('primary','actor')


class NavigationWholePreparation:
    def __init__(self,flow):
        need(type(flow) is IOSNavigationFeature)
        self.flow=flow;self.lock,self.root,self.run=flow.lock,flow.root,flow.run
        self.store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-whole-preparation.json'))
        self.previous=self.state=None

    def envelope(self,state):
        return dict(iosNavigationWholePreparationVersion=VERSION,runId=self.run,artifactRoot=str(self.root),payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        self.state=None if self.previous is None else self.decode(self.previous)

    def decode(self,value):
        exact(value,{'iosNavigationWholePreparationVersion','runId','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationWholePreparationVersion']) is int
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'binding','baselines','admission','phase'})
        context(state['binding']);exact(state['baselines'],ROLES)
        need(state['phase'] in ('preparing','entered'))
        for role,row in state['baselines'].items():
            exact(row,{'requestId','phase','ownerSha256'})
            need(type(row['requestId']) is str and row['requestId'].startswith('ios-'))
            from feature_journeys.contract import identifier
            identifier(row['requestId'][4:]);need(row['phase'] in ('planned','issued','observed'))
            need((row['ownerSha256'] is None) if row['phase']!='observed' else
                type(row['ownerSha256']) is str and len(row['ownerSha256'])==64)
        need(state['baselines']['primary']['requestId']!=state['baselines']['actor']['requestId'])
        exact(state['admission'],{'phase','ownerSha256'})
        row=state['admission'];need(row['phase'] in ('planned','issued','observed'))
        need((row['ownerSha256'] is None) if row['phase']!='observed' else
            type(row['ownerSha256']) is str and len(row['ownerSha256'])==64)
        if row['phase']!='planned':need(all(v['phase']=='observed' for v in state['baselines'].values()))
        if state['phase']=='entered':need(row['phase']=='observed')
        return deepcopy(state)

    def save(self):
        self.lock.assert_held();self.flow.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.flow.clock()

    def current(self):
        source=self.flow.current();need(same(source['binding'],self.state['binding']))
        return source

    def baseline(self,role,*,historical):
        need(role in ROLES and type(historical) is bool);row=self.state['baselines'][role]
        if historical:
            owner=NavigationBaselineImage(PrivateFeatureState(self.store.path.with_name(
                'ios-navigation-baseline-'+role+'-'+row['requestId'][4:]+'.json')),
                self.root,self.state['binding'],self.run,role,row['requestId'],self.lock,lambda:True,historical=True,
                epoch_ms=self.flow.epoch_ms,monotonic=self.flow.monotonic)
        else:
            self.current();f=self.flow
            owner=f.runtime._navigation_baseline_image(f.selector,f.client,self.run,role,row['requestId'],self.root,self.lock)
        need(type(owner) is NavigationBaselineImage and owner.lock is self.lock and owner.root==self.root
            and owner.run==self.run and owner.role==role and same(owner.binding,self.state['binding'])
            and owner.request==row['requestId'] and owner.store.path==self.store.path.with_name(
                'ios-navigation-baseline-'+role+'-'+row['requestId'][4:]+'.json'))
        return owner

    def take_baseline(self,role):
        row=self.state['baselines'][role]
        if row['phase']=='observed':
            owner=self.baseline(role,historical=True);owner.archive();need(digest(owner.previous)==row['ownerSha256']);return
        owner=self.baseline(role,historical=False)
        if row['phase']=='planned':
            need(owner.state is None);row['phase']='issued';self.save()
            owner.acquire(self.flow.epoch_ms())
        else:
            # Only the same completely retained child can resolve a lost
            # parent return. An unknown/partial query is never issued again.
            if owner.state is None:raise NavigationFeaturePending('Untouched Worlds image delivery remains unresolved')
            if owner.state['phase']=='reading':owner.recover()
        owner.archive();row.update(phase='observed',ownerSha256=digest(owner.store.read()));self.save()

    def admission(self,*,historical):
        f=self.flow
        if historical:
            return NavigationAdmissionOwner(PrivateFeatureState(self.store.path.with_name('ios-navigation-scene-admission.json')),
                self.state['binding'],self.run,self.lock,lambda:True,historical=True)
        self.current();return f.runtime._navigation_admission_owner(f.selector,f.client,self.run,self.lock)

    def originals(self):
        """Historical graph validation grants no new native freshness."""
        need(self.state is not None and self.state['admission']['phase']=='observed')
        images={role:self.baseline(role,historical=True) for role in ROLES}
        proofs={role:owner.archive()[1] for role,owner in images.items()}
        for role,owner in images.items():need(digest(owner.previous)==self.state['baselines'][role]['ownerSha256'])
        admission=self.admission(historical=True);actual=admission.archive()
        need(digest(admission.previous)==self.state['admission']['ownerSha256'])
        untouched(proofs['primary'],proofs['actor'])
        for proof in proofs.values():untouched(actual,proof)
        a,b=(images[role].originals()['capture'] for role in ROLES)
        need(a['requestId']!=b['requestId'] and a['source']['renderTrace']['frameId']!=b['source']['renderTrace']['frameId'])
        need(proofs['primary']['clockJoin']['nativeAfter']['sequence']<proofs['actor']['clockJoin']['nativeBefore']['sequence']
            and proofs['actor']['clockJoin']['nativeAfter']['sequence']<actual['clockJoin']['nativeBefore']['sequence'])
        return images,admission

    def prepare(self):
        f=self.flow;need(f.role=='primary')
        with f.held():
            self.load();f.load()
            if self.state is None:
                need(f.state is None);source=f.current();f.fixture.attach()
                self.state=dict(binding=deepcopy(source['binding']),baselines={role:dict(requestId='ios-'+uuid.uuid4().hex,
                    phase='planned',ownerSha256=None) for role in ROLES},admission=dict(phase='planned',ownerSha256=None),phase='preparing')
                self.save()
            if self.state['phase']=='entered':
                self.originals();f.prepare();need(same(f.state['initialBinding'],self.state['binding']));return
            self.current()
            for role in ROLES:self.take_baseline(role)
            row=self.state['admission'];owner=self.admission(historical=False)
            if row['phase']=='planned':
                need(owner.state is None);row['phase']='issued';self.save();owner.acquire(f.epoch_ms())
            elif row['phase']=='issued':
                if owner.state is None or owner.state['phase']!='admitted':
                    raise NavigationFeaturePending('Original Worlds admission delivery remains unresolved')
            if row['phase']!='observed':
                owner.archive();row.update(phase='observed',ownerSha256=digest(owner.store.read()));self.save()
            self.originals();f.prepare()
            need(f.state['phase']=='ready' and same(f.state['initialBinding'],self.state['binding'])
                and f.state['admissionSha256']==row['ownerSha256'])
            self.state['phase']='entered';self.save()
