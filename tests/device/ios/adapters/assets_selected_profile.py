"""Explicit early selected pair; never infer a target from an old Asset WAL.

The immutable selection is an OriginalFrame owned by the same final archive.
It is host configuration provenance, not native/OS/server absence evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_scene_sources import AssetsSceneSources


def link(value):
    exact(value,{'archivePath','contextSha256','reference'})
    p=Path(value['archivePath']);need(type(value['archivePath']) is str and p.is_absolute() and p.resolve()==p)
    # The actual OriginalFrame codec validates the complete reference. No path,
    # digest or target-looking string independently grants selection authority.
    need(type(value['reference']) is dict and type(value['contextSha256']) is str)
    return deepcopy(value)


class SelectedAssetsFiles(OwnedAssetsFiles):
    OWNER_VERSION=3
    EXTRA_FIELDS=frozenset({'selectedPair'})
    def __init__(self,*args,selection,**kwargs):
        self.selection=selection;self.selection_read_only=False;self.selection_role=kwargs.get('role','primary')
        selection.selected_guard();super().__init__(*args,**kwargs)
        need(self.role=='primary' and same(self.binding,selection.context['roles'][self.role]['binding'])
            and self.run==selection.run and self.url==selection.context['fixtureUrl']
            and self.store.path.parent==self.selected_directory(self.role))
        selection.selected_guard()
    def selected_directory(self,role):return Path(self.selection.context['roles'][role]['stateRoot'])
    def extra_envelope(self):return dict(selectedPair=self.selection.link())
    def envelope_guard(self):
        self.selection.selected_guard();need(getattr(self,'selection_read_only',False) is True or self.selection.state==dict(phase='selected'));return True
    def decode(self,value):
        need(type(value) is dict and type(value.get('iosAssetsFileOwnerVersion')) is int and value['iosAssetsFileOwnerVersion']==self.OWNER_VERSION)
        return super().decode(value)


class SelectedAssetsScene(AssetsSceneSources):
    OWNER_VERSION=2
    EXTRA_FIELDS=frozenset({'selectedPair'})
    def __init__(self,*args,selection,**kwargs):
        self.selection=selection;self.selection_read_only=False;selection.selected_guard();super().__init__(*args,**kwargs)
        selected_role='actor' if self.role=='actor' else 'primary'
        need(same(self.binding,selection.context['roles'][selected_role]['binding']) and self.run==selection.run
            and self.store.path.parent==self.selected_directory(selected_role))
        selection.selected_guard()
    def selected_directory(self,role):return Path(self.selection.context['roles'][role]['stateRoot'])
    def extra_envelope(self):return dict(selectedPair=self.selection.link())
    def envelope_guard(self):
        self.selection.selected_guard();need(getattr(self,'selection_read_only',False) is True or self.selection.state==dict(phase='selected'));return True


class EpisodeAssetsFiles(SelectedAssetsFiles):
    OWNER_VERSION=4
    EXTRA_FIELDS=frozenset({'selectedPair','episode'})
    def __init__(self,*args,episode,selection,**kwargs):
        from ios.adapters.assets_episodes import AssetsEpisodeScope
        need(type(episode) is AssetsEpisodeScope and episode.owner.selected is selection)
        self.episode=episode;episode.guard();super().__init__(*args,selection=selection,**kwargs)
    def reserve(self,ticket,resource='gltf-bundle/main.gltf'):
        descriptor=self.episode.descriptor
        need(ticket==descriptor['ticket'] and resource==descriptor['resource'])
        return super().reserve(ticket,resource)
    def selected_directory(self,role):
        self.episode.guard();return Path(self.episode.descriptor['directories'][role]['stateRoot']['path'])
    def extra_envelope(self):return dict(super().extra_envelope(),episode=self.episode.link())
    def envelope_guard(self):
        self.episode.guard();return super().envelope_guard()


class EpisodeAssetsScene(SelectedAssetsScene):
    OWNER_VERSION=3
    EXTRA_FIELDS=frozenset({'selectedPair','episode'})
    def __init__(self,*args,episode,selection,**kwargs):
        from ios.adapters.assets_episodes import AssetsEpisodeScope
        need(type(episode) is AssetsEpisodeScope and episode.owner.selected is selection)
        self.episode=episode;episode.guard();super().__init__(*args,selection=selection,**kwargs)
    def selected_directory(self,role):
        self.episode.guard();return Path(self.episode.descriptor['directories'][role]['stateRoot']['path'])
    def extra_envelope(self):return dict(super().extra_envelope(),episode=self.episode.link())
    def envelope_guard(self):
        self.episode.guard();return super().envelope_guard()
