"""Internal Pico Graphics owner namespaces; no complete feature operation yet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from copy import deepcopy
import hashlib
import re
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1


class PicoGraphicsBinding(PicoScriptJourney):
    state_area='graphics'

    def __init__(self,adapter,*,fixture_profile=None):
        from feature_journeys.graphics_fixture import LEGACY_PROFILE
        from feature_journeys.graphics_resources import profile_name
        self.fixture_profile=profile_name(LEGACY_PROFILE if fixture_profile is None else fixture_profile)
        super().__init__(adapter)

    @property
    def graphics_scene_policy(self):
        from adapters.pico4.graphics_scene import PicoGraphicsScenePolicy,PicoGraphicsSurfaceScenePolicy
        from feature_journeys.graphics_fixture import PICO_PROFILE
        return (PicoGraphicsSurfaceScenePolicy if self.fixture_profile==PICO_PROFILE else PicoGraphicsScenePolicy)()

    def _graphics_subject_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._graphics_subject_observer(target)

    def _scene_load_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._scene_load_observer(target)

    def _graphics_ui_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._graphics_ui_observer(target)

    def _web_runtime_observer(self,target,*,read_only=False):
        need(read_only is True);self._guard(target)
        reader=self.original._web_runtime_observer(target)
        need(reader.require_renderers is True);return reader

    def _tablet_http_observer(self,target,*,read_only=False):
        need(read_only is True);self._guard(target)
        return self.original._tablet_http_observer(target)

    def _graphics_retired_capture_observer(self,target,proof,lock,*,previous=None):
        from adapters.graphics_journey.samples import retirement
        from adapters.world_render_receipts import NativeWorldReceiptInventory,INVENTORY_FILE
        self._lock(target,lock).assert_held()
        _ui,_observer,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        native=self._native_feature_observer(target,read_only=True);packet=native.read(0)
        role=proof['owner']['role'];retirement(proof,proof['owner'],native.pid,binding,role)
        need(packet['instance']==proof['memory']['instance'])
        stores=[self.world_render_store(target,role=value) for value in ('primary','actor')]
        stores.append(self.original._world_render_store(target))
        def quiet_guard():
            lock.assert_held();need(guard() is not False and native.guard() is not False
                and all(store.read() is None for store in stores));return True
        floor=proof['files']['absent'] if previous is None else previous
        updated=deepcopy(proof);updated['files']['absent']=deepcopy(floor)
        retirement(updated,proof['owner'],native.pid,binding,role)
        need(floor['sequence']>=proof['files']['absent']['sequence'])
        quiet_guard()
        reader=NativeWorldReceiptInventory(native.send,
            lambda:self.original.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+INVENTORY_FILE,attempts=1),
            native.clock_ms,quiet_guard,native.pid,lambda:deepcopy(proof['owner']),lambda:packet['instance'],
            monotonic=native.monotonic,sleep=native.sleep)
        reader.sequence,reader.captured=floor['sequence'],floor['capturedEpochMs']
        reader.histories={floor['requestId']:{row['receiptId']:row['issued'] for row in floor['source']['receipts']}}
        return reader

    def _script_file_io(self,target,*,read_only=False):
        need(type(read_only) is bool)
        return super()._script_file_io(target)

    def _graphics_surface(self,target,run,intent,owns,lease,allow_url,*,lock):
        self._lock(target,lock).assert_held();self._guard(target)
        return self.original._graphics_surface(target,run,intent,owns,lease,allow_url)

    def world_render_store(self,target,*,role):
        need(type(role) is str and role in ('primary','actor'))
        return self._store(target,'graphics-'+role+'-world-render-owner.json')

    def _graphics_lifecycle_status(self,target,binding):
        """Current kernel/foreground source; no Qt reads or foreground repair.

        The binding identifies the existing owner scope. Its GUI bridge is
        independently reacquired/verified after actual foreground activation.
        """
        context(binding);original=self.original
        need(original.pico_configuration is not None and binding['targetFingerprint']==hashlib.sha256(
            (target+'\0'+str(original.pico_configuration)).encode()).hexdigest())
        before=original._installation(target)
        need(all(before[key]==binding[key] for key in ('sourceRevision','artifactSha256')))
        state=original.adb.process_state(target,'org.overte.pico')
        need(type(state) is dict and state.get('running') is True and state.get('identity')==binding['processIdentity']
            and original.require_pico_session_identity(target)==state['identity'])
        foreground=original.adb.foreground_package(target)
        need(type(foreground) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+',foreground)
            and original.require_pico_session_identity(target)==state['identity']
            and original._installation(target)==before)
        return dict(binding=deepcopy(binding),foreground=foreground=='org.overte.pico',running=state['running'])

    def _graphics_lifecycle_input(self,target,operation,binding):
        need(operation in ('lifecycle.background','app.launch'))
        status=self._graphics_lifecycle_status(target,binding)
        if operation=='lifecycle.background':
            need(status['foreground'] is True)
            self._guard(target)
        # Ordinary controlled activation must preserve this process; do not
        # use a missing probe as an invitation to bootstrap or repair it.
        need(self.original.require_controlled_debug_identity(target)==binding['processIdentity'])
        return self.original.invoke(target,operation,{})

    def invoke(self,target,operation,values):
        need(operation in ('app.launch','app.stop') and values=={})
        return self.original.invoke(target,operation,values)

    def _graphics_restart_stopped(self,target,old):
        from adapters.android_process_query import AndroidProcessQuery
        context(old)
        def guard():
            need(hashlib.sha256((target+'\0'+str(self.original.pico_configuration)).encode()).hexdigest()==old['targetFingerprint'])
            installed=self.original._installation(target)
            need(all(installed[key]==old[key] for key in ('sourceRevision','artifactSha256')))
        packet=AndroidProcessQuery(self.original.adb,'org.overte.pico',guard).read(target,int(old['processIdentity'].split(':')[0]))
        return dict(running=bool(packet['processIds']),identity=old['processIdentity'] if packet['processIds'] else None)

    def _graphics_restart_source(self,target,inputs,restart):
        from adapters.graphics_journey.restart import GraphicsRestart
        from adapters.script_journey.history import same
        need(isinstance(restart,GraphicsRestart) and restart.adapter is self and restart.selector==target
            and restart.inputs is inputs)
        def owner_check():
            restart.lock.assert_held();value=restart.store.read()
            need(same(value,restart.previous) and restart.state['phase']=='prepared'
                and inputs.store.path==self._store(target,'graphics-restart-inputs.json').path
                and same(restart.scene_store.read(),restart.state['oldScene'])
                and same(restart.preferences_store.read(),restart.state['oldPreferences'])
                and all(store.read() is None for store in restart.world_stores))
            return dict(restart=value,scene=restart.state['oldScene'],preferences=restart.state['oldPreferences'])
        owner_check()
        if inputs.read()['phase']=='launch-issued':
            self.original._script_restart_recover_binding(target,restart_inputs=inputs,owner_check=owner_check,monotonic=restart.monotonic)
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        return binding,self._native_feature_observer(target,read_only=True),guard

    def _graphics_restart_quiet_ui(self,target,run):
        from adapters.pico4.graphics_source import resources
        from adapters.script_ui_inventory import validate as inventory
        ui,_observe,_binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        value=self._graphics_ui_observer(target,read_only=True).capture()
        need(value['graphicsObservationVersion']==2 and resources(value)==[])
        tablet=self._script_file_io(target,read_only=True).capture();actual=inventory(tablet['scriptInventory'])
        need(actual['complete'] and not actual['tabletShown'] and not actual['managers'] and not actual['pickers']
            and not ui.tablet_visible() and not ui.available('navigation.address',enabled=False) and guard() is not False)
        return deepcopy(dict(graphics=value,tablet=tablet))

    def _world_render_capture(self,target,*,read_only=True,role,require_frame_view=True,source_lock):
        need(read_only is True and require_frame_view is True)
        return self.original._world_render_capture(target,read_only=True,role=role,require_frame_view=True,source_lock=source_lock)


class SerializedWorldCapture(OwnedWorldRenderCapture):
    """Use the same explicit source-lock instance across role/native channels."""
    def __init__(self,*args,source_lock,**options):
        need(isinstance(source_lock,ScriptSourceLock));self.source_lock=source_lock
        super().__init__(*args,**options)

    def read(self,after_sequence):
        with self.source_lock.held():return super().read(after_sequence)

    def release(self):
        with self.source_lock.held():return super().release()
