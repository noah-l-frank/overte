"""Version-two failed preparation with actual retained GPU/file prefixes.

Literal version one remains the pre-capture reader. This later reader admits
only typed interrupted preparation originals, never a successful feature.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from ios.adapters.navigation_preparation_abort import NavigationPreparationAbort,INPUT_PREFIXES,OTHER_OWNERS
from ios.adapters.navigation_preparation_reads import inspect
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation

VERSION=2


class NavigationPartialPreparationAbort(NavigationPreparationAbort):
    def parents(self):
        f=self.flow;f.lock.assert_held();need(f.role=='primary' and f.store.read() is None)
        whole=NavigationWholeFeature(f);whole.load();preparation=NavigationWholePreparation(f);preparation.load()
        need(whole.state is not None and whole.state['phase']=='preparing' and whole.state['cleanup'] is None
            and preparation.state is not None and preparation.state['phase']=='preparing')
        for path in f.store.path.parent.iterdir():need(not path.name.startswith(INPUT_PREFIXES))
        for name in OTHER_OWNERS:need(PrivateFeatureState(f.store.path.with_name(name)).read() is None)
        # This is the real historical prefix decoder, including native command
        # and storage WAL, original components and exact private PNG inode.
        # Captured pixels use the complete original decoder; partial files
        # remain partial evidence. No capture/release query is retried here.
        reads=inspect(preparation)
        return dict(whole=whole.previous,preparation=preparation.previous,reads=reads),context(preparation.state['binding'])

    def envelope(self,state):
        value=super().envelope(state);value['iosNavigationPreparationAbortVersion']=VERSION;return value

    def result(self):
        value=super().result();value['iosNavigationPreparationAbortResultVersion']=VERSION;return value


def owner(flow):
    """Dispatch literal persisted versions; a new partial owner writes two."""
    value=PrivateFeatureState(flow.store.path.with_name('ios-navigation-preparation-abort.json')).read()
    if value is None:return NavigationPartialPreparationAbort(flow)
    need(type(value) is dict)
    version=value.get('iosNavigationPreparationAbortVersion')
    need(type(version) is int and version in (1,2))
    return (NavigationPreparationAbort if version==1 else NavigationPartialPreparationAbort)(flow)
