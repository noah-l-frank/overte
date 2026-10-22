"""Create components on the existing fully candidate-bound iOS runtime.

These factories create no session, install nothing and advertise no feature.
A complete CreateFeature still owns independent publication and paired cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.native_script_roots import NativeScriptRoots,FILE as ROOTS_FILE,LIMIT as ROOTS_LIMIT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.token_script_ui import TokenScriptUI
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.create_api_clock import check as api_check,guarded
from ios.adapters.create_api_transport import CreateNativeInput,CreateNativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.create_action_owner import CreateActionOwner,CreateBoundIO
from ios.adapters.create_actor_facts import CreateActorFacts
from ios.adapters.create_actions import CreateActions
from ios.adapters.create_files import OwnedCreateFiles
from ios.adapters.create_export_artifact import CreateExportArtifact
from ios.adapters.create_inputs import IOSCreateUI
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.create_rez_client import CreateRezClient
from ios.adapters.create_sample import CreateSampleOwner
from ios.adapters.create_primary import CreatePrimary
from ios.adapters.create_sources import CreateSources
from ios.adapters.create_world_input import CreateWorldInput
from ios.adapters.graphics_runtime import IOSGraphicsRuntime


class IOSCreateRuntime(IOSGraphicsRuntime):
    def _sources(self,selector):
        api_check();sources=super()._sources(selector);api_check()
        sources['check']=guarded(sources['check']);sources['process']=guarded(sources['process'])
        for key in ('observer','clock_source'):
            original=sources[key];original.observe_process=guarded(original.observe_process)
            original.before_send=api_check
        sources['native']=CreateNativeInput.from_original(sources['native'])
        sources['native'].observe_process=guarded(sources['native'].observe_process)
        return sources
    def normal_feature_runtime(self,selector,*,read_only=False):
        need(type(read_only) is bool);sources=self._sources(selector)
        ui=TokenScriptUI(IOSScriptIO(CreateNativeUI(sources['client'],sources['session'],sources['check']),sources['native']))
        return ui,sources['observe'],sources['binding'],sources['check'],sources['installed']
    def _create_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.create_feature import IOSCreateFeature
        return IOSCreateFeature(self,selector,client,run,role,settings)
    def _create_store(self,selector,name):
        need(type(name) is str and name.startswith('ios-create-') and name.endswith('.json') and '/' not in name)
        return PrivateFeatureState(self.state_path(selector).with_name(name))
    def _create_sources(self,selector,lock):
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        lock.assert_held();s=self._sources(selector);observer,clock=s['observer'],s['clock_source']
        root_reader=NativeScriptRoots(observer.send,lambda:observer.original(remote=observer.remote.rsplit('/',1)[0]+'/'+ROOTS_FILE,limit=ROOTS_LIMIT),
            s['native_clock'],s['check'],int(s['binding']['processIdentity']),ios=True)
        return dict(s,create=observer.create_state(clock),work=observer.create_work(clock),script_work=observer.script_work(clock),
            domain=observer.emote_world(clock),roots=root_reader,geometry=observer.geometry(),native_bound=observer.bound_native_observer(clock),
            ui=CreateNativeUI(s['client'],s['session'],s['check']))
    def _create_marker(self,selector,root,run,role,fixture_url,ticket,lock):
        return CreateMarkerScope(self,selector,root,run,role,fixture_url,ticket,lock)
    def _create_source_owner(self,selector,run,role,phase,scripts_root,lock):
        sources=self._create_sources(selector,lock)
        return CreateSources(self._create_store(selector,'ios-create-'+role+'-sources.json'),lock,sources['binding'],run,role,scripts_root,sources['check'],
            phase=phase,readers=dict(create=sources['create'],domain=sources['domain'],work=sources['work'],worker=sources['script_work'],native=sources['native_bound']))
    def _create_sample(self,selector,run,role,request_id,root,lock):
        s=self._create_sources(selector,lock)
        frame=self._vulkan_world_frame_owner(selector,run,role,0,request_id,root,source_lock=lock)
        return CreateSampleOwner(self._create_store(selector,'ios-create-'+role+'-'+request_id[4:]+'-sample.json'),lock,
            s['binding'],run,role,request_id,s['check'],native=s['native_bound'],source=s['create'],frame_owner=frame)
    def _create_actor_facts(self,selector,run,primary_sources,peer_sources,lock,*,marker=None):
        lock.assert_held();primary_sources.lock.assert_held()
        return CreateActorFacts(self._create_store(selector,'ios-create-actor-facts.json'),lock,run,primary_sources,peer_sources,peer_sources.guard,marker=marker)
    def _create_export_artifact(self,selector,run,root,request_id,lock):
        sources=self._create_sources(selector,lock)
        need(request_id.startswith('ios-'));from feature_journeys.contract import identifier
        identifier(request_id[4:])
        return CreateExportArtifact(self._create_store(selector,'ios-create-export-'+request_id[4:]+'-artifact.json'),lock,root,sources['binding'],run,sources['check'])
    def _create_primary(self,selector,run,root,source,lock,*,actions=None,marker=None):
        need(isinstance(source,CreateSources) and source.role=='primary' and source.lock is lock)
        s=self._create_sources(selector,lock);need(s['binding']==source.binding)
        def sample(request):return self._create_sample(selector,run,'primary',request,root,lock)
        def export(name):
            need(name.startswith('ios-create-export-') and name.endswith('-artifact.json'))
            return self._create_export_artifact(selector,run,root,'ios-'+name[len('ios-create-export-'):-len('-artifact.json')],lock)
        return CreatePrimary(self._create_store(selector,'ios-create-primary.json'),lock,s['binding'],run,source,s['check'],
            actions=actions,marker=marker,sample_resolver=sample,export_resolver=export)
    def _create_actions(self,selector,run,client,rez_config,lock,marker_scope,*,prepared=None):
        from ios.adapters.create_marker_identity import PreparedCreateMarker
        need(isinstance(marker_scope,CreateMarkerScope))
        if prepared is None:prepared=marker_scope.prepared()
        need(isinstance(prepared,PreparedCreateMarker) and prepared.run==run and prepared.binding==marker_scope.binding)
        if marker_scope.state['phase']!='ready':need(self._create_store(selector,'ios-create-actions.json').read() is not None)
        s=self._create_sources(selector,lock);need(s['binding']==marker_scope.binding)
        phase=PhaseFixtureReader(client,run,'create');fixture_url=phase.fixture_url
        def store(name):return self._create_store(selector,name)
        inputs=CreateActionOwner(store('ios-create-inputs.json'),lock,s['binding'],run,fixture_url,s['check'])
        cleanup_inputs=CreateActionOwner(store('ios-create-cleanup-inputs.json'),lock,s['binding'],run,fixture_url,s['check'])
        files=OwnedCreateFiles(s['observer'].create_files(s['clock_source']),store('ios-create-files.json'),s['binding'],run,fixture_url,lock=lock)
        rez=CreateRezClient(store('ios-create-rez-client.json'),lock,s['binding'],run,rez_config,s['check'])
        native=CreateNativeInput.from_original(s['native'])
        ui=IOSCreateUI(CreateBoundIO(native,inputs),lambda _summary:None)
        def world(ticket):
            return CreateWorldInput(store('ios-create-world-input-'+ticket+'.json'),s['binding'],run,ticket,lock,
                s['native_bound'],s['create'],s['geometry'],native,CreateNativeUI.from_original(s['ui']),s['check'])
        return CreateActions(store('ios-create-actions.json'),lock,s['binding'],run,fixture_url,s['check'],source=s['create'],work=s['work'],
            scripts_root=s['roots'].read(0)['source']['defaultScriptsUrl'],
            ui=ui,normal=CreateNativeUI.from_original(s['ui']),inputs=inputs,cleanup_inputs=cleanup_inputs,files=files,rez=rez,phase=phase,geometry=s['geometry'],world_factory=world,
            marker_scope=prepared)
