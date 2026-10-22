"""Current Worlds source floors after proven restart, distinct from admission.

The first static admission stays the restoration baseline. Ordinary owners
may use these actual new-process sources without assigning new clocks to it.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_process_context import source_basis
from ios.adapters.navigation_process_owner import NavigationProcessOwner

NAMES=frozenset(('ios-navigation-surface-actions.json','ios-navigation-places-actions.json',
    'ios-navigation-composite-actions.json','ios-navigation-missing-actions.json'))


class NavigationProcessScope:
    def __init__(self,owner):
        need(isinstance(owner,NavigationProcessOwner) and not owner.historical)
        owner.bound();need(owner.state is not None and owner.state['phase']=='transferred')
        self.owner=owner;self.store,self.lock=owner.store,owner.lock
        self.binding,self.run=deepcopy(owner.binding),owner.run
        self.native,self.sources,self.fixture=owner.native,owner.sources,owner.fixture
        self.historical=False;self.bound()

    def bound(self):
        self.owner.bound();need(not self.owner.historical and self.owner.state is not None
            and self.owner.state['phase']=='transferred' and same(self.owner.binding,self.binding)
            and self.owner.run==self.run and self.owner.native is self.native and self.owner.sources is self.sources
            and self.owner.fixture is self.fixture)

    def archive(self):
        """An explicitly typed current source basis, never a static admission."""
        self.bound();return source_basis(self.owner.archive(),self.owner.owner_files)

    def original_admission(self):
        self.bound();return deepcopy(self.owner.archive()['initialAdmission'])

    def ui_original(self,value):
        from ios.adapters.normal_input import observation
        observation(value,int(self.binding['processIdentity']),value.get('sampleEpochMs'))
        floor=self.archive()['originals']['ui']
        need(value['instance']==floor['instance'] and value['lastSequence']>=floor['lastSequence']
            and value['elapsedMs']>=floor['elapsedMs'] and value['sampleEpochMs']>=floor['sampleEpochMs'])
        for key in ('placesSourceSequence','navigationDialogSourceSequence'):
            if key in floor:need(key in value and value[key]>=floor[key])
        return value


def owner_path(scope,name):
    need(name in NAMES and isinstance(scope,(NavigationAdmissionOwner,NavigationProcessScope)))
    if isinstance(scope,NavigationProcessScope):
        scope.bound();name=name[:-5]+'-'+scope.binding['processIdentity']+'.json'
    return scope.store.path.with_name(name)
