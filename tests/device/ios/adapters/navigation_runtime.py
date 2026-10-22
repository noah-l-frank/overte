"""Worlds observation factories on the existing candidate-qualified iOS session.

No session creation, normal input, feature dispatch or capability advertisement
is provided here. The whole navigation coordinator must own admission/cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_scene_inputs import NavigationSceneInputs
from ios.adapters.navigation_sample import NavigationSampleOwner
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSNavigationRuntime(IOSScriptRuntime):
    def _navigation_scene_inputs(self,selector,admission):
        need(isinstance(admission,NavigationAdmissionOwner));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        ui=NativeUI(source['client'],source['session'],source['check'])
        return NavigationSceneInputs(PrivateFeatureState(admission.store.path.with_name('ios-navigation-scene-inputs.json')),
            admission,ui,source['native'])

    def _navigation_admission_owner(self,selector,client,run,lock):
        identifier(run);need(isinstance(lock,ScriptSourceLock));lock.assert_held()
        source=self._sources(selector);fixture=NavigationFixtureReader(client,run);fixture.attach()
        directory=self.state_path(selector).parent
        need(lock.path==directory/'script-feature-sources.lock')
        observer,clock=source['observer'],source['clock_source']
        readers=dict(inventory=observer.scene_inventory(clock),navigation=observer.navigation_state(clock),
            bookmarks=observer.location_bookmarks(clock),model=observer.places_model(clock),http=observer.places_http(clock),
            dialogs=observer.navigation_dialogs(clock),replies=observer.navigation_replies(),ui=source['native'])
        source['check']()
        return NavigationAdmissionOwner(PrivateFeatureState(directory/'ios-navigation-scene-admission.json'),
            source['binding'],run,lock,source['check'],native=observer.bound_native_observer(clock),sources=readers,fixture=fixture)

    def _navigation_observation_owner(self,selector,client,run,role,stage,request,root,lock,*,previous=None):
        identifier(run);identifier(request)
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1) and isinstance(lock,ScriptSourceLock))
        lock.assert_held();source=self._sources(selector)
        fixture=NavigationFixtureReader(client,run);fixture.attach()
        need(fixture.inputs['sourceRevision']==source['binding']['sourceRevision'])
        directory=self.state_path(selector).parent
        need(lock.path==directory/'script-feature-sources.lock')
        observer=source['observer'];clock=source['clock_source']
        native=observer.bound_native_observer(clock);navigation=observer.navigation_state(clock)
        readers=dict(bookmarks=observer.location_bookmarks(clock),model=observer.places_model(clock),
            http=observer.places_http(clock),dialogs=observer.navigation_dialogs(clock),replies=observer.navigation_replies(),
            ui=source['native'])
        def child(request_id):
            source['check']()
            return NavigationSampleOwner(PrivateFeatureState(directory/('ios-navigation-'+role+'-'+str(stage)+'-'+request_id[4:]+'-sample.json')),
                root,source['binding'],run,role,stage,request_id,lock,source['check'],native=native,navigation=navigation,
                fixture=fixture,frame_factory=lambda intent,receipt:observer.vulkan_world_frame(intent,receipt))
        images=NavigationSamples(PrivateFeatureState(directory/('ios-navigation-'+role+'-'+str(stage)+'-samples.json')),
            root,source['binding'],run,role,stage,lock,source['check'],factory=child)
        source['check']();owner=NavigationObservationOwner(
            PrivateFeatureState(directory/('ios-navigation-'+role+'-'+str(stage)+'-'+request+'-observation.json')),
            images,source['binding'],run,role,stage,request,lock,source['check'],native=native,navigation=navigation,
            sources=readers,fixture=fixture,previous=previous)
        need(same(owner.binding,source['binding']));source['check']();return owner
