"""Full candidate Script runtime on existing iOS HTTP/AFC and ordinary Qt input.

This facade keeps component operations unchanged. It cannot create a WebDriver
session, install an application, or repair a lost input channel. Native clocks
are acquired independently; no host/AFC timestamp becomes product evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.native_clock_join import NativeClockAcquisition
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.native_script_files import OwnedScriptFiles
from adapters.normal_ui import NativeUI
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.restart_inputs import RestartInputs, run_script_restart
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.script_feature.actions import ScriptActions
from adapters.script_feature.scope import transfer_file_scope
from adapters.script_feature.measurements import ScriptMeasurements
from adapters.script_feature.history import ScriptSourceHistory, DurableScriptMeasurements
from adapters.script_feature.observation import ScriptObservation
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import appium_adapter as backend
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.normal_input import NativeInput
from ios.adapters.normal_scripts import IOSScriptIO, configuration
from ios.adapters.script_ui_source import IOSScriptUISource
from ios.adapters.script_observation import IOSScriptObservation


class IOSScriptRuntime:
    def __init__(self, adapter):
        need(callable(getattr(adapter,'_candidate_guard',None)) and callable(getattr(adapter,'_binding',None)))
        self.adapter=adapter

    def state_path(self, selector):return self.adapter.state_path(selector)
    def script_store(self, selector):return self.adapter.script_store(selector)
    def script_files_store(self, selector):return self.adapter.script_files_store(selector)
    def script_restart_store(self, selector):return self.adapter.script_restart_store(selector)
    def script_restart_inputs_store(self, selector):return self.adapter.script_restart_inputs_store(selector)

    def _existing(self,selector):
        base=self.adapter;base._candidate_guard()
        target=base._target(selector);state=deepcopy(base.read_session(selector))
        need(type(state) is dict and type(state.get('sessionId')) is str)
        session=state['sessionId'];scope=base._scope(selector,session,state,target)
        client=backend.WebDriver(target['serverUrl'])
        client.call('GET','/session/'+session)
        need(base.read_session(selector)==state and base._scope(selector,session,state,target)==scope)
        return client,session,state,target,scope

    @contextmanager
    def existing_input_session(self,selector):
        base=self.adapter
        _client,_session,_state,_target,scope=self._existing(selector)
        old=base._session_recreation_forbidden;base._session_recreation_forbidden=True
        try:
            yield
            need(self._existing(selector)[4]==scope)
        finally:base._session_recreation_forbidden=old

    def _sources(self,selector):
        base=self.adapter;client,session,state,target,scope=self._existing(selector)
        need(configuration(target) is not None)
        gate=base._binding(selector,client,session,state,target)
        installed=gate.verify();actual=gate.continuity();pid=actual['pid']
        binding=dict(scope,processIdentity=str(pid))
        def check():
            base._candidate_guard()
            need(base._scope(selector,session,state,target)==scope and gate.continuity()==actual)
        def process():check();return deepcopy(actual)
        clock_source=FeatureObservation(client,session,target,process).native_observer()
        def native_clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        observer=FeatureObservation(client,session,target,process,epoch_ms=native_clock)
        native=NativeInput(client,session,target,process,native_epoch_ms=native_clock)
        def observe(after):
            value=observer.read(after);return value,native_clock()
        check()
        return dict(client=client,session=session,state=state,target=target,binding=binding,check=check,
            installed=installed,observer=observer,native=native,native_clock=native_clock,clock_source=clock_source,
            observe=observe,process=process)

    def normal_feature_runtime(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        source=self._sources(selector)
        ui=TokenScriptUI(IOSScriptIO(NativeUI(source['client'],source['session'],source['check']),source['native']))
        return ui,source['observe'],source['binding'],source['check'],source['installed']

    def _script_file_runtime(self,selector,*,read_only=False):
        ui,observe,binding,_check,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        return ui,observe,binding

    def _script_files(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        source=self._sources(selector)
        return OwnedScriptFiles(source['observer'].script_fixture_files(),self.script_files_store(selector),source['binding'])

    def _script_execution_observer(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        return self._sources(selector)['observer'].script_execution_observer()

    def _process_presence(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        return self._sources(selector)['observer'].process_presence()

    def _script_file_io(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        s=self._sources(selector)
        return IOSScriptUISource(s['native'],s['native_clock'],s['check'],int(s['binding']['processIdentity']))

    def _script_file_manager(self,selector,*,read_only=False,run=None):
        ui,observe,binding=self._script_file_runtime(selector,read_only=read_only)
        files=self._script_files(selector,read_only=read_only)
        need(run is None or files.owned()['runId']==run)
        directory=files.verify()
        manager=NormalScriptManager(ui,observe,self.script_store(selector),binding,source_kind='script-file-bundle',
            file_owner=files,file_picker=TokenScriptFilePicker(ui.io,directory))
        manager.sample();return manager

    def _script_missing_manager(self,selector,*,read_only=False):
        ui,observe,binding=self._script_file_runtime(selector,read_only=read_only)
        manager=NormalScriptManager(ui,observe,self.script_store(selector),binding,source_kind='feature-script-missing')
        manager.sample();return manager

    def _script_missing_from_files(self,selector,run):
        transfer_file_scope(run,self._script_file_manager(selector,read_only=True,run=run),
            self._script_execution_observer(selector,read_only=True),self._script_file_io(selector,read_only=True))
        return self._script_missing_manager(selector,read_only=True)

    def _script_actions(self,selector,run,fixture_url):return ScriptActions(self,selector,run,fixture_url)
    def script_actions_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('script-feature-actions.json'))
    def script_feature_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('script-feature-owner.json'))
    def script_retirement_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('script-feature-retirement.json'))

    def _role_store(self,selector,role,stage,kind):
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1) and kind in ('history','observation','clock'))
        return PrivateFeatureState(self.state_path(selector).with_name('script-feature-'+role+'-'+kind+('-restart' if stage else '')+'.json'))

    def script_clock_store(self,selector,role,*,stage=0):return self._role_store(selector,role,stage,'clock')

    def script_history_store(self,selector,role,*,stage=0):return self._role_store(selector,role,stage,'history')
    def script_observation_store(self,selector,role,*,stage=0):return self._role_store(selector,role,stage,'observation')

    def _script_feature(self,selector,run,*,role='primary',client=None):
        from ios.adapters.feature_configuration import configuration,reader
        from ios.adapters.script_feature import IOSScriptFeature,ScriptFixtureReader
        need(role in ('primary','actor'))
        if role=='primary':
            need(client is None);config=configuration();need(config is not None);client=reader(config)
        else:need(client is not None)
        return IOSScriptFeature(self,selector,ScriptFixtureReader(client,run),role=role)

    def _location_bookmarks_observer(self,selector):
        source=self._sources(selector)
        return source['observer'].location_bookmarks(source['clock_source'])

    def _places_model_observer(self,selector):
        source=self._sources(selector)
        return source['observer'].places_model(source['clock_source'])

    def _places_http_observer(self,selector):
        source=self._sources(selector)
        return source['observer'].places_http(source['clock_source'])

    def _navigation_dialogs_observer(self,selector):
        source=self._sources(selector)
        return source['observer'].navigation_dialogs(source['clock_source'])

    def _clock_acquisition(self,selector,host_barrier):
        s=self._sources(selector)
        window=NativeClockAcquisition(s['clock_source']);window.begin(host_barrier)
        return window

    def _script_measurements(self,selector,run,fixture_url,*,read_only=True,fixture_state='present',retired_owner=None):
        need(read_only is True)
        need(fixture_state in ('present','absent') and (retired_owner is None or fixture_state=='absent'))
        s=self._sources(selector);real_store=self.script_files_store(selector);retired_owner=deepcopy(retired_owner)
        def check():
            s['check']();need(retired_owner is None or real_store.read() is None)
        class RetiredScope:
            def read(self):return deepcopy(retired_owner)
        check()
        storage=s['observer'].script_fixture_files()
        files=OwnedScriptFiles(storage,real_store if retired_owner is None else RetiredScope(),s['binding'])
        def verify():
            check();need(files.owned()['runId']==run)
            if fixture_state=='present':return files.verify()
            location=files.locate();need(location['exists'] is False);return location['directory']
        directory=verify()
        reader=ScriptMeasurements(run,directory,fixture_url,s['observer'].script_execution_observer(),
            IOSScriptUISource(s['native'],s['native_clock'],check,int(s['binding']['processIdentity'])),
            s['observe'],s['observer'].native_observer(),verify,check,file_instance=lambda:storage.instance)
        reader.file_observation=lambda:deepcopy(storage.last_packet)
        reader.binding=deepcopy(s['binding'])
        return reader

    def _script_durable_measurements(self,selector,run,fixture_url,*,role,fixture_state='present',retired_owner=None,source_lock=None,stage=0):
        lock_path=self.state_path(selector).with_name('script-feature-sources.lock')
        lock=ScriptSourceLock(lock_path) if source_lock is None else source_lock
        need(isinstance(lock,ScriptSourceLock) and lock.path==lock_path)
        with lock.held():
            reader=self._script_measurements(selector,run,fixture_url,fixture_state=fixture_state,retired_owner=retired_owner)
            history=ScriptSourceHistory(self.script_history_store(selector,role,stage=stage),reader.binding,run,role,reader.directory,fixture_url)
            reader.guard()
            return DurableScriptMeasurements(reader,history,source_lock=lock)

    def _script_observation(self,selector,run,fixture_url,*,role,fixture_state='present',retired_owner=None,stage=0,source_lock=None):
        lock_path=self.state_path(selector).with_name('script-feature-sources.lock')
        lock=ScriptSourceLock(lock_path) if source_lock is None else source_lock
        need(isinstance(lock,ScriptSourceLock) and lock.path==lock_path)
        def make(held):return self._script_durable_measurements(selector,run,fixture_url,role=role,
            fixture_state=fixture_state,retired_owner=retired_owner,source_lock=held,stage=stage)
        with lock.held():
            s=self._sources(selector)
            result=ScriptObservation(self.script_observation_store(selector,role,stage=stage),s['binding'],run,role,
                fixture_url,make,lock,s['check'])
            clock_store=self.script_clock_store(selector,role,stage=stage)
            return IOSScriptObservation(result,s['clock_source'],self.script_history_store(selector,role,stage=stage),clock_store)

    def _script_restart_handoff(self,selector):
        return ScriptRestartHandoff(self.script_restart_store(selector),self.script_files_store(selector),
            self.script_store(selector),require_membership=True)

    def _script_restart_inputs(self,selector):
        return RestartInputs(self.script_restart_inputs_store(selector),
            [self.script_restart_store(selector),self.script_files_store(selector),self.script_store(selector)])

    def _script_restart_source(self,selector):
        base=self.adapter;owned=base._binding_store(selector).read()
        if owned is not None and owned['phase']=='preparing':base._recover_script_restart_launch(selector,inputs=self._script_restart_inputs(selector))
        s=self._sources(selector)
        return s['binding'],s['observer'].native_observer()

    def _script_restart_prepare(self,selector):
        return self._script_restart_handoff(selector).prepare(self._script_file_manager(selector),self._script_execution_observer(selector))

    def _script_restart_adopt(self,selector):
        s=self._sources(selector);ui=TokenScriptUI(IOSScriptIO(NativeUI(s['client'],s['session'],s['check']),s['native']))
        handoff=self._script_restart_handoff(selector)
        return handoff.adopt(s['binding'],s['observer'].process_presence(),s['observer'].script_execution_observer(),
            s['observer'].script_fixture_files(),ui,s['observe'],TokenScriptFilePicker(ui.io,handoff.directory()))

    def _lifecycle(self,selector,operation):
        need(operation in ('app.stop','app.launch'))
        intent=self._script_restart_inputs(selector).read()
        need(intent['phase']==('stop-issued' if operation=='app.stop' else 'launch-issued'))
        base=self.adapter;outer=base._operation
        need(outer in (None,'feature.scripts.act'))
        base._operation=None
        try:return base.invoke(selector,operation,{})
        finally:base._operation=outer

    def _script_restart_stopped(self,selector):
        base=self.adapter;client,state,target=base._script_restart_session(selector,inputs=self._script_restart_inputs(selector))
        gate=base._binding(selector,client,state['sessionId'],state,target)
        record=gate.record()
        if record is not None and record['phase']=='retiring':gate.finish_retirement()
        gate.retired_absence();base.reset_launch_state(selector,state)
        return {'running':False,'identity':None}

    def _script_restart(self,selector):
        return run_script_restart(self._script_restart_inputs(selector),self._script_restart_handoff(selector),
            lambda:self._script_restart_source(selector),lambda:self._script_restart_prepare(selector),
            lambda:self._lifecycle(selector,'app.stop'),lambda:self._script_restart_stopped(selector),
            lambda:self._lifecycle(selector,'app.launch'),lambda:self._script_restart_adopt(selector))
