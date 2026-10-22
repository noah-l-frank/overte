"""New-process static image owner against actual retained restoration sources.

The unchanged acquisition protocol also owns raw current input journals. Its
closed restored-state decoder preserves historical events and explicit retained
roots; this is not a new untouched admission or a final cleanup verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.navigation_baseline_image import NavigationBaselineImage,KEYS
from ios.adapters.navigation_process_context import validate as process_original
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_restored_state import compose

VERSION=1


class NavigationRestoredImage(NavigationBaselineImage):
    PREFIX='restored'
    ENVELOPE='iosNavigationRestoredImageVersion'
    ORIGINAL='iosNavigationRestoredOriginalVersion'
    STAGE=1
    KEYS=KEYS+('addressOwner','surfaceOwner')

    def __init__(self,*args,process_context,owner_files,directory,previous,**kwargs):
        need(isinstance(previous,NavigationObservationOwner));previous.archive()
        self.previous_observation=previous;self.prior_carrier=deepcopy(previous.store.read())
        self.prior=dict(originals=deepcopy(previous.state['originals']),nativeAfter=deepcopy(previous.state['clockJoin']['nativeAfter']))
        self.process_context=process_original(process_context,owner_files);self.owner_files=list(owner_files)
        self.initial=deepcopy(self.process_context['initialAdmission']);self.directory=deepcopy(directory)
        super().__init__(*args,**kwargs)
        need(same(self.binding,self.process_context['restart']['input']['newBinding']) and self.run==self.initial['runId']
            and same(self.binding,previous.binding) and self.run==previous.run and self.role==previous.role and previous.stage==1)

    def envelope(self,state):
        return super().envelope(state)|dict(processContextSha256=digest(self.process_context),
            directoryProofSha256=digest(self.directory),previousOwnerSha256=digest(self.prior_carrier))

    def bound(self):
        super().bound();previous=self.previous_observation
        need(same(previous.store.read(),self.prior_carrier) and same(previous.envelope(previous.state),self.prior_carrier)
            and same(self.prior,dict(originals=previous.state['originals'],nativeAfter=previous.state['clockJoin']['nativeAfter'])))

    def qualify(self):
        self.previous_observation.archive();return super().qualify()

    def extra_originals(self):
        for key,name in (('addressOwner','ios-navigation-address-'),('surfaceOwner','ios-navigation-surface-actions-')):
            suffix='-inputs' if key=='addressOwner' else ''
            store=PrivateFeatureState(self.store.path.with_name(name+self.binding['processIdentity']+suffix+'.json'))
            self.take(key,store.read)

    def static_state(self,original,clock,parts):
        return compose(self.initial,self.process_context,self.owner_files,original,clock,parts['base'],
            address_owner=parts['addressOwner'],surface_owner=parts['surfaceOwner'],directory=self.directory,prior=self.prior)
