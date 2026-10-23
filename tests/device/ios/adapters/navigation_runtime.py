"""Worlds observation factories on the existing candidate-qualified iOS session.

Factories create no SDK session and advertise no capability. The whole
navigation coordinator owns admission, ordinary input and cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
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
from ios.adapters.navigation_places_inputs import IOSPlacesFlow
from ios.adapters.navigation_places_actions import NavigationPlacesActions
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.adapters.navigation_missing_actions import NavigationMissingActions
from ios.adapters.navigation_composite_actions import NavigationCompositeActions
from ios.adapters.navigation_process_owner import NavigationProcessOwner
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path
from ios.adapters.navigation_restart_proof import OWNERS as RESTART_OWNERS
from ios.adapters.places_controls import IOSPlacesIO
from ios.adapters.navigation_sample import NavigationSampleOwner
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSNavigationRuntime(IOSScriptRuntime):
    def _navigation_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.navigation_configuration import settings as validate_settings
        from ios.adapters.navigation_feature import IOSNavigationFeature
        from ios.adapters.navigation_whole_feature import NavigationWholeFeature
        need(role in ('primary','actor') and client is not None)
        selected=validate_settings(settings)
        return NavigationWholeFeature(IOSNavigationFeature(self,selector,client,run,selected['artifactRoot'],role=role))

    def _navigation_restored_image(self,selector,client,run,role,request,root,lock,*,process_context,owner_files,directory_proof,previous,quiet=False):
        """Current static pixels after an original typed process transfer."""
        from ios.adapters.navigation_restored_image import NavigationRestoredImage
        from ios.adapters.graphics_history import restore_native
        identifier(run);need(role in ('primary','actor') and isinstance(lock,ScriptSourceLock) and type(quiet) is bool);lock.assert_held()
        need(isinstance(previous,NavigationObservationOwner));previous.archive()
        source=self._sources(selector);directory=self.state_path(selector).parent
        need(lock.path==directory/'script-feature-sources.lock' and previous.lock is lock
            and same(source['binding'],previous.binding))
        fixture=NavigationFixtureReader(client,run);fixture.attach()
        need(fixture.inputs['sourceRevision']==source['binding']['sourceRevision'])
        observer,clock=source['observer'],source['clock_source']
        readers=dict(inventory=observer.scene_inventory(clock),navigation=observer.navigation_state(clock),
            bookmarks=observer.location_bookmarks(clock),model=observer.places_model(clock),http=observer.places_http(clock),
            dialogs=observer.navigation_dialogs(clock),replies=observer.navigation_replies(),ui=source['native'])
        native=observer.bound_native_observer(clock);restore_native(native,previous.state['clockJoin']['nativeAfter']);source['check']()
        image_type=NavigationRestoredImage;additional={}
        if quiet:
            from ios.adapters.navigation_quiet_image import NavigationQuietImage
            image_type=NavigationQuietImage
            additional['input_readers']=dict(keys=observer.world_web_keys(clock),pointer=observer.pointer_state(clock),geometry=observer.geometry())
        return image_type(PrivateFeatureState(directory/('ios-navigation-'+image_type.PREFIX+'-'+role+'-'+request[4:]+'.json')),
            root,source['binding'],run,role,request,lock,source['check'],native=native,sources=readers,fixture=fixture,
            frame_factory=lambda intent,receipt:observer.vulkan_world_frame(intent,receipt),process_context=process_context,
            owner_files=owner_files,directory=directory_proof,previous=previous,**additional)

    def _navigation_baseline_image(self,selector,client,run,role,request,root,lock):
        """Untouched static pixels on this existing installed candidate only."""
        from ios.adapters.navigation_baseline_image import NavigationBaselineImage
        identifier(run);need(role in ('primary','actor') and isinstance(lock,ScriptSourceLock));lock.assert_held()
        source=self._sources(selector);directory=self.state_path(selector).parent
        need(lock.path==directory/'script-feature-sources.lock')
        fixture=NavigationFixtureReader(client,run);fixture.attach()
        need(fixture.inputs['sourceRevision']==source['binding']['sourceRevision'])
        observer,clock=source['observer'],source['clock_source']
        readers=dict(inventory=observer.scene_inventory(clock),navigation=observer.navigation_state(clock),
            bookmarks=observer.location_bookmarks(clock),model=observer.places_model(clock),http=observer.places_http(clock),
            dialogs=observer.navigation_dialogs(clock),replies=observer.navigation_replies(),ui=source['native'])
        source['check']()
        return NavigationBaselineImage(PrivateFeatureState(directory/('ios-navigation-baseline-'+role+'-'+request[4:]+'.json')),
            root,source['binding'],run,role,request,lock,source['check'],native=observer.bound_native_observer(clock),
            sources=readers,fixture=fixture,frame_factory=lambda intent,receipt:observer.vulkan_world_frame(intent,receipt))

    def _navigation_observer(self,selector,client,run,role,stage,root,lock):
        """Role-owned original acquisition/publication on the existing session."""
        import uuid
        from ios.adapters.navigation_observer import NavigationObserver
        prototype=self._navigation_observation_owner(selector,client,run,role,stage,uuid.uuid4().hex,root,lock)
        def factory(request,previous):
            return NavigationObservationOwner(PrivateFeatureState(prototype.store.path.with_name(
                'ios-navigation-'+role+'-'+str(stage)+'-'+request+'-observation.json')),
                prototype.images,prototype.binding,run,role,stage,request,lock,prototype.guard,
                native=prototype.native,navigation=prototype.navigation,sources=prototype.sources,
                fixture=prototype.fixture,previous=previous)
        return NavigationObserver(PrivateFeatureState(prototype.store.path.with_name(
            'ios-navigation-'+role+'-'+str(stage)+'-observer.json')),prototype.images,factory=factory)

    def _navigation_restart(self,selector,initial,samples,lock,fixture):
        from ios.adapters.navigation_restart import NavigationRestart
        return NavigationRestart(self,selector,initial,samples,lock,fixture)

    def _navigation_restart_input(self,selector,operation,owner):
        from ios.adapters.navigation_restart import NavigationRestart
        need(isinstance(owner,NavigationRestart));owner.authorize_input(self,selector,operation)
        base=self.adapter;outer=base._operation;need(outer in (None,'feature.world-navigation.act'))
        base._operation=None
        try:return base.invoke(selector,operation,{})
        finally:base._operation=outer

    def _navigation_restart_stopped(self,selector,old_binding):
        from adapters.restart_inputs import RestartInputs
        directory=self.state_path(selector).parent
        inputs=RestartInputs(PrivateFeatureState(directory/'ios-navigation-restart-inputs.json'),
            [PrivateFeatureState(directory/name) for name in RESTART_OWNERS])
        need(same(inputs.read()['oldBinding'],old_binding) and inputs.read()['phase']=='stop-issued')
        base=self.adapter;base._candidate_guard(complete=True)
        client,state,target=base._script_restart_session(selector,inputs=inputs)
        gate=base._binding(selector,client,state['sessionId'],state,target);record=gate.record()
        if record is not None and record['phase']=='retiring':gate.finish_retirement()
        gate.retired_absence();base.reset_launch_state(selector,state)
        return dict(running=False,identity=None)

    def _navigation_recover_launch(self,selector,inputs):
        from adapters.restart_inputs import RestartInputs
        directory=self.state_path(selector).parent
        need(isinstance(inputs,RestartInputs) and not inputs.component_only
            and inputs.store.path==directory/'ios-navigation-restart-inputs.json'
            and inputs.owner_files==[str(directory/name) for name in RESTART_OWNERS])
        owned=self.adapter._binding_store(selector).read()
        if owned is not None and owned['phase']=='preparing':
            need(inputs.read()['phase']=='launch-issued')
            self.adapter._recover_script_restart_launch(selector,inputs=inputs)

    def _navigation_before_restart(self,selector,admission,*,missing=None):
        from ios.adapters.navigation_before_restart import NavigationBeforeRestart
        need(isinstance(admission,NavigationAdmissionOwner));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        return NavigationBeforeRestart(PrivateFeatureState(admission.store.path.with_name(
            'ios-navigation-before-restart.json')),admission,missing=missing)

    def _navigation_process_scope(self,owner):
        return NavigationProcessScope(owner)

    def _navigation_process_return(self,selector,scope):
        from ios.adapters.navigation_process_return import NavigationProcessReturn
        need(isinstance(scope,NavigationProcessScope));scope.bound()
        source=self._sources(selector);need(same(source['binding'],scope.binding)
            and scope.store.path.parent==self.state_path(selector).parent)
        ui=NativeUI(source['client'],source['session'],source['check'])
        return NavigationProcessReturn(PrivateFeatureState(scope.store.path.with_name(
            'ios-navigation-process-return-'+scope.binding['processIdentity']+'.json')),scope,ui,source['native'])

    def _navigation_process_owner(self,selector,client,initial,before,receipt,lock):
        """Acquire on the existing new candidate; never launch or infer a restart."""
        from ios.adapters.graphics_history import restore_native
        need(isinstance(lock,ScriptSourceLock));lock.assert_held()
        source=self._sources(selector);directory=self.state_path(selector).parent
        need(same(source['binding'],receipt['input']['newBinding']) and lock.path==directory/'script-feature-sources.lock')
        fixture=NavigationFixtureReader(client,initial['runId']);fixture.attach()
        observer,clock=source['observer'],source['clock_source']
        readers=dict(inventory=observer.scene_inventory(clock),navigation=observer.navigation_state(clock),
            bookmarks=observer.location_bookmarks(clock),model=observer.places_model(clock),http=observer.places_http(clock),
            dialogs=observer.navigation_dialogs(clock),replies=observer.navigation_replies(),ui=source['native'])
        native=observer.bound_native_observer(clock);restore_native(native,receipt['native']);source['check']()
        return NavigationProcessOwner(PrivateFeatureState(directory/'ios-navigation-process-context.json'),
            initial,before,receipt,[str(directory/name) for name in RESTART_OWNERS],lock,source['check'],
            native=native,sources=readers,fixture=fixture)

    def _navigation_composite_actions(self,selector,admission,*,floor=None):
        surfaces=self._navigation_surface_actions(selector,admission)
        places=self._navigation_places_actions(selector,admission,floor=floor)
        source=self._sources(selector)
        need(same(source['binding'],admission.binding))
        navigation=source['observer'].navigation_state(source['clock_source'])
        return NavigationCompositeActions(
            PrivateFeatureState(owner_path(admission,'ios-navigation-composite-actions.json')),
            surfaces,places,navigation)

    def _navigation_missing_actions(self,selector,admission):
        need(isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        ui=NativeUI(source['client'],source['session'],source['check'])
        return NavigationMissingActions(PrivateFeatureState(owner_path(admission,'ios-navigation-missing-actions.json')),
            admission,ui,source['native'])

    def _navigation_address_dismiss(self,selector,admission):
        from ios.adapters.navigation_address_inputs import NavigationAddressInputs
        from ios.adapters.navigation_address_dismiss import NavigationAddressDismiss
        need(isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        directory=admission.store.path.parent
        ui=NativeUI(source['client'],source['session'],source['check'])
        address=NavigationAddressInputs(PrivateFeatureState(directory/('ios-navigation-address-'+admission.binding['processIdentity']+'-inputs.json')),
            admission.binding,admission.run,admission.lock,admission.bound,ui,source['native'])
        return NavigationAddressDismiss(PrivateFeatureState(directory/('ios-navigation-address-dismiss-'+admission.binding['processIdentity']+'.json')),address)

    def _navigation_surface_actions(self,selector,admission):
        need(isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        ui=NativeUI(source['client'],source['session'],source['check'])
        return NavigationSurfaceActions(PrivateFeatureState(owner_path(admission,'ios-navigation-surface-actions.json')),
            admission,ui,source['native'])

    def _navigation_places_actions(self,selector,admission,*,floor=None):
        need(isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        def factory(intent,previous):
            return self._navigation_places_flow(selector,admission,intent,previous=previous,floor=floor)
        return NavigationPlacesActions(PrivateFeatureState(owner_path(admission,'ios-navigation-places-actions.json')),
            source['binding'],admission.run,admission.lock,source['check'],admission.fixture,factory,
            scope=admission if isinstance(admission,NavigationProcessScope) else None)

    def _navigation_places_flow(self,selector,admission,intent,*,previous=None,floor=None,surface=None):
        need(isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)));admission.bound()
        source=self._sources(selector);need(same(source['binding'],admission.binding)
            and admission.store.path.parent==self.state_path(selector).parent)
        proof=admission.archive();native=source['native']
        io=IOSPlacesIO(SimpleNamespace(native=native,capture=native.capture))
        return IOSPlacesFlow(io,source['observer'].places_model(source['clock_source']),source['binding'],admission.run,
            proof['providerInputs'],proof['originals']['ui']['instance'],admission.lock,source['check'],intent,
            previous=previous,floor=proof['originals']['ui'] if floor is None else floor,
            surface=self._navigation_surface_actions(selector,admission) if surface is None else surface)

    def _navigation_places_cleanup(self,selector,admission):
        from ios.adapters.navigation_places_cleanup import NavigationPlacesCleanup
        surface=self._navigation_surface_actions(selector,admission)
        return NavigationPlacesCleanup(PrivateFeatureState(owner_path(admission,'ios-navigation-places-cleanup.json')),
            admission,surface,lambda intent:self._navigation_places_flow(selector,admission,intent,surface=surface))

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
