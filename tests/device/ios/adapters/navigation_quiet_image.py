"""Static originals with actual global key/pointer and UIKit observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.navigation_restored_image import NavigationRestoredImage
from ios.adapters.navigation_input_cut import NavigationInputCut
from ios.adapters import world_web_keys as keys,pointer_state as pointer

VERSION=1


class NavigationQuietImage(NavigationRestoredImage):
    PREFIX='quiet'
    ENVELOPE='iosNavigationQuietImageVersion'
    ORIGINAL='iosNavigationQuietOriginalVersion'
    KEYS=NavigationRestoredImage.KEYS+('inputOwner',)

    def __init__(self,*args,input_readers=None,**kwargs):
        self.input_readers=input_readers;super().__init__(*args,**kwargs)
        need((input_readers is None) if self.historical else input_readers is not None)

    def input_owner(self):
        return NavigationInputCut(PrivateFeatureState(self.store.path.with_name('ios-navigation-input-'+self.role+'-'+self.request[4:]+'.json')),
            self.root,self.binding,self.run,self.role,self.request,self.lock,self.guard,
            readers=None if self.historical else self.input_readers,historical=self.historical,monotonic=self.monotonic)

    def extra_originals(self):
        super().extra_originals()
        def actual():
            owner=self.input_owner();owner.acquire();return owner.store.read()
        self.take('inputOwner',actual)

    def static_state(self,original,clock,parts):
        from adapters.script_feature.history import same
        proof=super().static_state(original,clock,parts);owner=self.input_owner()
        need(same(owner.store.read(),parts['inputOwner']));inputs=owner.archive()
        before,after=clock['nativeBefore']['capturedEpochMs'],clock['nativeAfter']['capturedEpochMs']
        for kind in ('keys','pointer'):
            packet=inputs[kind];need(before<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=after)
        geometry=inputs['geometry']['observation'];need(before<=geometry['sampleEpochMs']<=after)
        keys.privacy_qualified(inputs['keys']);keys.drained(inputs['keys'])
        p=inputs['pointer']['source'];need(p['complete'] and p['startup']['observed'] and p['pendingDispatches']==0
            and p['contacts']==[] and p['qtMouseButtons']==0 and p['worldTapActive'] is False)
        ui=geometry['nativeUi'];need(ui.get('keyboardVisible') is False and number(ui.get('imeInsetBottom'),0,0))
        # Hidden editors retain responsibility. Only final OS-process absence
        # can end those roots, irrespective of the last delivered IME event.
        need(all(root['field']['focused'] is False for root in original['ui']['navigationInventory']['roots']))
        return proof
