"""Original-process restored PNG, actual input quiet and retained UI roots."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_baseline_image import NavigationBaselineImage,KEYS
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_input_cut import NavigationInputCut
from ios.adapters.navigation_initial_restored_state import compose
from ios.adapters import world_web_keys as keys

VERSION=1


class NavigationInitialRestoredImage(NavigationBaselineImage):
    PREFIX='initial-restored'
    ENVELOPE='iosNavigationInitialRestoredImageVersion'
    ORIGINAL='iosNavigationInitialRestoredOriginalVersion'
    STAGE=0
    KEYS=KEYS+('addressOwner','surfaceOwner','inputOwner')

    def __init__(self,*args,admission,directory,previous,fixture_url,input_readers=None,**kwargs):
        need(type(admission) is NavigationAdmissionOwner and type(previous) is NavigationObservationOwner)
        self.admission,self.previous_observation=admission,previous
        self.initial=deepcopy(admission.archive());previous.archive()
        self.admission_carrier=deepcopy(admission.store.read());self.prior_carrier=deepcopy(previous.store.read())
        self.prior=dict(originals=deepcopy(previous.state['originals']),nativeAfter=deepcopy(previous.state['clockJoin']['nativeAfter']))
        self.directory,self.fixture_url,self.input_readers=deepcopy(directory),fixture_url,input_readers
        super().__init__(*args,**kwargs)
        need(self.lock is admission.lock is previous.lock and same(self.binding,admission.binding)
            and same(self.binding,previous.binding) and self.run==admission.run==previous.run
            and self.role==previous.role and previous.stage==0)
        need((input_readers is None) if self.historical else input_readers is not None)

    def envelope(self,state):
        return super().envelope(state)|dict(initialAdmissionSha256=digest(self.admission_carrier),
            directoryProofSha256=digest(self.directory),previousOwnerSha256=digest(self.prior_carrier),fixtureUrl=self.fixture_url)

    def bound(self):
        super().bound();previous=self.previous_observation
        need(same(self.admission.store.read(),self.admission_carrier)
            and same(previous.store.read(),self.prior_carrier) and same(previous.envelope(previous.state),self.prior_carrier)
            and same(self.prior,dict(originals=previous.state['originals'],nativeAfter=previous.state['clockJoin']['nativeAfter'])))

    def qualify(self):
        need(same(self.admission.archive(),self.initial));self.previous_observation.archive();return super().qualify()

    def input_owner(self):
        return NavigationInputCut(PrivateFeatureState(self.store.path.with_name('ios-navigation-input-'+self.role+'-'+self.request[4:]+'.json')),
            self.root,self.binding,self.run,self.role,self.request,self.lock,self.guard,
            readers=None if self.historical else self.input_readers,historical=self.historical,monotonic=self.monotonic)

    def extra_originals(self):
        for key,name in (('addressOwner','ios-navigation-address-'+self.binding['processIdentity']+'-inputs.json'),
                         ('surfaceOwner','ios-navigation-surface-actions.json')):
            store=PrivateFeatureState(self.store.path.with_name(name))
            self.take(key,store.read)
        def actual():
            owner=self.input_owner();owner.acquire();return owner.store.read()
        self.take('inputOwner',actual)

    def static_state(self,original,clock,parts):
        proof=compose(self.initial,original,clock,parts['base'],address_owner=parts['addressOwner'],
            surface_owner=parts['surfaceOwner'],directory=self.directory,prior=self.prior,fixture_url=self.fixture_url)
        owner=self.input_owner();need(same(owner.store.read(),parts['inputOwner']));inputs=owner.archive()
        before,after=clock['nativeBefore']['capturedEpochMs'],clock['nativeAfter']['capturedEpochMs']
        for kind in ('keys','pointer'):
            packet=inputs[kind];need(before<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=after)
        geometry=inputs['geometry']['observation'];need(before<=geometry['sampleEpochMs']<=after)
        keys.privacy_qualified(inputs['keys']);keys.drained(inputs['keys'])
        pointer=inputs['pointer']['source'];need(pointer['complete'] and pointer['startup']['observed'] and pointer['pendingDispatches']==0
            and pointer['contacts']==[] and pointer['qtMouseButtons']==0 and pointer['worldTapActive'] is False)
        ui=geometry['nativeUi'];need(ui.get('keyboardVisible') is False and number(ui.get('imeInsetBottom'),0,0))
        need(all(root['field']['focused'] is False for root in original['ui']['navigationInventory']['roots']))
        return proof
