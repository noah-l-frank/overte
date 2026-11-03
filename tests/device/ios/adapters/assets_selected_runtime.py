"""Explicit selected-pair Assets factories; ordinary runtime stays literal.

Selection is already durable before this runtime is usable. A reconstructed
runtime does not claim pure reconstruction: normal source construction retains
its existing InstalledBinding/SDK guards and possible owner WAL writes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.assets_end_graph import AssetsFinalArchive
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_selected_profile import SelectedAssetsFiles,SelectedAssetsScene
from ios.adapters.installed_process_runtime import admitted_source


class SelectedAssetsRuntime(IOSAssetsRuntime):
    FILES_OWNER=SelectedAssetsFiles
    SCENE_OWNER=SelectedAssetsScene
    def __init__(self,adapter,selected,*,phase=None,**kwargs):
        need(type(selected) is AssetsFinalArchive);selected.selected_guard();self.assets_selection=selected;self.assets_phase=phase
        super().__init__(adapter,**kwargs)
        if self.assets_episode is not None:
            from ios.adapters.assets_selected_profile import EpisodeAssetsFiles,EpisodeAssetsScene
            need(self.assets_episode.owner.selected is selected)
            self.FILES_OWNER,self.SCENE_OWNER=EpisodeAssetsFiles,EpisodeAssetsScene
            if self.assets_episode.index==2:
                from ios.adapters.assets_renamed_usage import RenamedAssetsUsage
                self.USAGE_OWNER=RenamedAssetsUsage
    def _assets_usage_values(self,selector,run,role,tree):
        episode=self.assets_episode
        if episode is None or episode.index!=2:return {}
        episode.guard();need(episode.descriptor['kind']=='upload' and episode.descriptor['resource']=='gltf-bundle/main.gltf'
            and run==episode.owner.run and role=='primary')
        return dict(tree=tree)
    def _assets_selected_values(self,selector,run,role,lock):
        selected=self.assets_selection;selected.selected_guard();need(selected.state==dict(phase='selected'))
        from feature_journeys.phase_fixture import PhaseFixtureReader
        phase=self.assets_phase;need(isinstance(phase,PhaseFixtureReader) and phase.run==selected.run and phase.area=='assets'
            and phase.fixture_url==selected.context['fixtureUrl'])
        current=phase.status();need(current['active'] and current['instance']==selected.context['inputPhaseOriginal']['instance'])
        subject='actor' if role=='actor' else 'primary'
        info=selected.context['roles'][subject]
        need(run==selected.run and selector==info['target'] and self.state_path(selector).parent==Path(info['stateRoot']))
        if self.assets_episode is None:
            need(lock.path==Path(info['stateRoot'])/'script-feature-sources.lock')
            lock.assert_held();return dict(selection=selected)
        self.assets_episode.runtime_guard(self,selector,lock)
        need(self.assets_episode.descriptor['runId']==run)
        return dict(selection=selected,episode=self.assets_episode)
    def _sources(self,selector):
        episode=self.assets_episode
        if episode is None:return super()._sources(selector)
        role=episode.role(selector);lock=episode.locks[role]
        self._assets_selected_values(selector,self.assets_selection.run,role,lock)
        parts=super()._sources(selector);original=parts['check']
        def checked():
            self._assets_selected_values(selector,self.assets_selection.run,role,lock)
            need(original() is not False);return True
        parts['check']=checked
        for transport in (parts['observer'],getattr(parts['clock_source'].send,'__self__',None)):
            need(transport is not None);before=transport.before_send
            def final(before=before):
                checked()
                if before is not None:need(before() is not False)
                checked()
            transport.before_send=final
        checked();return parts

    def _assets_sources(self,selector,lock):
        selected=self.assets_selection;selected.selected_guard()
        roles=[role for role,info in selected.context['roles'].items() if info['target']==selector];need(len(roles)==1)
        role=roles[0];info=selected.context['roles'][role];self._assets_selected_values(selector,selected.run,role,lock)
        parts=super()._assets_sources(selector,lock)
        need(same(parts['binding'],info['binding']) and same(admitted_source(self,selector,info['binding']),info['source']))
        original=parts['check']
        def checked():
            self._assets_selected_values(selector,selected.run,role,lock);need(original() is not False);return True
        parts['check']=checked
        for transport in (parts['observer'],getattr(parts['clock_source'].send,'__self__',None)):
            need(transport is not None);before=transport.before_send
            def final(before=before):
                checked()
                if before is not None:need(before() is not False)
                checked()
            transport.before_send=final
        parts['native'].assets_guard=checked;checked();return parts

    def _assets_end_native(self,owner):
        need(self.assets_episode is None)
        from ios.adapters.assets_end_process import AssetsProcessEnd
        need(type(owner) is AssetsProcessEnd and owner.runtime is self and owner.tx.archive is self.assets_selection
            and owner.state is not None and owner.state['phase']=='prepared')
        selected=self.assets_selection;selected.selected_guard();need(selected.state['phase']=='validated')
        info=selected.context['roles'][owner.role];need(owner.target==info['target'] and same(owner.binding,info['binding']))
        # Exactly the existing source constructor, gated for this read-only
        # native fence. No normal Input/Files/Scene owner escapes this method.
        parts=IOSAssetsRuntime._assets_sources(self,owner.target,owner.lock)
        need(same(parts['binding'],info['binding']) and same(admitted_source(self,owner.target,info['binding']),info['source']))
        def guard():
            owner.bound();need(owner.state['phase']=='prepared' and selected.state['phase']=='validated')
            need(parts['check']() is not False);return True
        for transport in (parts['observer'],getattr(parts['clock_source'].send,'__self__',None)):
            need(transport is not None);before=transport.before_send
            def final(before=before):
                guard()
                if before is not None:need(before() is not False)
                guard()
            transport.before_send=final
        guard();return parts['observer'].bound_native_observer(parts['clock_source'])
