"""Pico extension of the canonical SH-004 Android adapter; no device auto-run."""
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
import importlib.util
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import time

from execution_identity import file_digest
from adapters.pico4.navigation import NativeNavigationIO, PicoNavigation, configured_scene, discard_stopped_state
from navigation_observation import OPERATIONS as NAVIGATION_OPERATIONS
from adapters.android_snapshot_files import AndroidSnapshotFiles
from adapters.pico4.feature_observation import PicoFeatureObservation
from adapters.native_feature_observation import NativeFeatureObservation, FILE as NATIVE_FEATURE_FILE
from adapters.native_account_probe import (NativeAccountProbe, AccountProbeOwner, OwnedAccountProbe,
    FILE as ACCOUNT_PROBE_FILE)
from adapters.native_chat_observation import NativeChatObservation, ChatCaptureOwner, OwnedChatCapture, FILE as CHAT_FILE
from adapters.native_chat_view import NativeChatView, FILE as CHAT_VIEW_FILE
from adapters.native_web_dom import NativeWebDOMObservation, FILE as WEB_DOM_FILE
from adapters.native_navigation_replies import NativeNavigationReplies, FILE as NAVIGATION_REPLIES_FILE
from adapters.native_location_bookmarks import NativeLocationBookmarks, FILE as LOCATION_BOOKMARKS_FILE
from adapters.native_navigation_modals import NativeNavigationModals, FILE as NAVIGATION_MODALS_FILE
from adapters.native_navigation_environment import NativeNavigationEnvironment, FILE as NAVIGATION_ENVIRONMENT_FILE
from adapters.native_navigation_directory import NativeNavigationDirectory, FILE as NAVIGATION_DIRECTORY_FILE
from adapters.native_process_presence import NativeProcessPresence, FILE as PROCESS_PRESENCE_FILE
from adapters.pending_commit_owner import NativePendingCommitOwner, FILE as PENDING_OWNER_FILE
from adapters.native_account_origin import NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE
from adapters.recorded_preview_evidence import (RecordedPreviewEvidence, AndroidPreviewFiles,
    FILE as RECORDED_PREVIEW_FILE)
from adapters.native_script_observation import NativeScriptObservation, FILE as SCRIPT_EXECUTION_FILE
from adapters.pico4 import normal_scripts
from adapters.pico4 import script_journey
from adapters.pico4 import authentication_journey
from adapters.pico4 import graphics_journey
from adapters.pico4 import create_management
from create_observation import OPERATIONS as CREATE_OPERATIONS
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, FILE as SCRIPT_FIXTURE_FILE
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.restart_inputs import RestartInputs, run_script_restart, validate_native_restart
from adapters.android_process_query import AndroidProcessQuery
from adapters.normal_feature_state import PrivateFeatureState
from adapters.android_world_render import AndroidWorldRenderReceipts
from adapters.world_render_evidence import NativeWorldRenderCapture, FILE as WORLD_RENDER_FILE
from adapters.world_render_storage import NativeWorldRenderStorage
from adapters.owned_world_render import WorldRenderOwner, OwnedWorldRenderCapture
from scripts_observation import OPERATIONS as SCRIPT_OPERATIONS
from adapters.pico4.snapshot import (PicoSnapshot, OPERATIONS as SNAPSHOT_OPERATIONS,
                                    configured_scene as configured_snapshot)

ROOT = Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location(
    'pico_bound_candidate_verifier', ROOT / 'android/vr/pico/ci/verify-pico-apk.py')
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)


def _need(condition):
    if not condition:
        raise ValueError('OVT_PICO_BINDING_REJECTED')


def _private(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            # Neither raw tool exceptions, artifact paths nor target selectors
            # become public adapter diagnostics, including direct callers.
            raise ValueError('OVT_PICO_BINDING_REJECTED') from None
    return call


def configure_parser(parser):
    # The same original candidate inputs, with named --apk because the runner
    # appends its action AFTER manifest-prefix options. No parallel schema.
    verifier.add_candidate_arguments(parser, native_binding=True)


def _inputs(args):
    from pico_candidate_identity import EVIDENCE_KEYS
    names = ('apk', 'identity_record', 'expected_inputs', 'build_evidence',
             'aapt', 'apksigner', *EVIDENCE_KEYS)
    _need(all(getattr(args, name, None) is not None for name in names))
    _need(args.source_revision and args.expected_version_code and
          args.expected_version_name and args.expected_signer_sha256 and
          args.minimum_version is not None and args.expected_artifact_sha256)
    frozen = {name: file_digest(getattr(args, name)) for name in names}
    # Parse paths using the original Shared bounded helpers. Full tier/identity
    # validation remains mandatory in verify_candidate, not reimplemented here.
    from schema.terminal_evidence import read_document, relative_file
    evidence, _ = read_document(args.build_evidence)
    for entry in evidence['receipts']:
        path = relative_file(args.build_evidence.parent, entry['path'])
        frozen['build_receipt:' + entry['tier']] = file_digest(path)
    return frozen


@_private
def create_adapter(args, base_class):
    _need(args.kind == 'pico')
    # Cleanup must still reach the original native cleanup if candidate files
    # disappeared or became invalid. It never emits an executionIdentity.
    cleanup_only = args.action == 'cleanup'
    cleanup_candidate = False
    frozen = candidate = None
    if not cleanup_only:
        frozen = _inputs(args)
        args.require_identity = True
        candidate = verifier.verify_candidate(args)
        _need(_inputs(args) == frozen)
        _need(candidate['package'] == 'org.overte.pico' and
              candidate['identity']['artifactSha256'] == frozen['apk'])

    class PicoBoundAdapter(base_class):
        @_private
        def debug_launcher_arguments(self,target):
            values=authentication_journey.launcher_arguments(os.environ)
            if values:
                _need(self.pico_configuration is not None and self._candidate()['e2e_input_layer'] is True)
                self._installation(target)
            return values

        @_private
        def _candidate(self):
            _need(not cleanup_only or cleanup_candidate)
            _need(_inputs(args) == frozen)
            current = verifier.verify_candidate(args)
            _need(current == candidate and _inputs(args) == frozen)
            return current

        def _recover_cleanup_candidate(self):
            nonlocal frozen, candidate, cleanup_candidate
            _need(cleanup_only)
            original = _inputs(args)
            args.require_identity = True
            verified = verifier.verify_candidate(args)
            _need(_inputs(args) == original and verified['package'] == 'org.overte.pico'
                  and verified['identity']['artifactSha256'] == original['apk'])
            frozen, candidate, cleanup_candidate = original, verified, True

        @_private
        def _package_path(self, target):
            raw = self.adb.shell(target, 'pm', 'path', 'org.overte.pico')
            _need(isinstance(raw, str) and len(raw) <= 2048)
            lines = raw.splitlines()
            # One PackageManager path means monolithic only: never silently
            # discard a split APK or a warning/malformed extra line.
            _need(len(lines) == 1 and lines[0].startswith('package:'))
            path = lines[0][len('package:'):]
            _need(re.fullmatch(r'/data/app/[A-Za-z0-9_./+=~-]+/base[.]apk', path) is not None)
            parsed = PurePosixPath(path)
            _need(str(parsed) == path and '..' not in parsed.parts and '.' not in parsed.parts)
            # ADB joins remote argv. This constrained absolute path contains
            # no shell metacharacters, whitespace, substitutions or options.
            return path

        @_private
        def _installed_hash(self, target, path):
            raw = self.adb.shell(target, 'toybox', 'sha256sum', path)
            _need(isinstance(raw, str) and len(raw) <= 2200)
            match = re.fullmatch(r'([0-9a-f]{64})  ' + re.escape(path) + r'\n?', raw)
            _need(match is not None)
            return match.group(1)

        @_private
        def _installation(self, target):
            self.require(target)
            _need(self.adb.prop(target, 'ro.kernel.qemu') != '1')
            current = self._candidate()
            before = self._package_path(target)
            first = self._installed_hash(target, before)
            _need(self._package_path(target) == before)
            second = self._installed_hash(target, before)
            _need(self._package_path(target) == before)
            _need(first == second == current['sha256'])
            _need(_inputs(args) == frozen)
            return dict(schemaVersion=1, sourceRevision=current['identity']['sourceRevision'],
                        artifactSha256=first, installedCandidateVerified=True)

        @_private
        def capabilities(self, target=None):
            # One pinned candidate cannot establish a two-candidate upgrade.
            values = [value for value in super().capabilities(target) if value != 'app.upgrade']
            if configured_scene(os.environ) is not None:
                _need((not cleanup_only or cleanup_candidate) and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(NAVIGATION_OPERATIONS)
            if configured_snapshot(os.environ) is not None:
                _need((not cleanup_only or cleanup_candidate) and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(SNAPSHOT_OPERATIONS)
            if normal_scripts.configuration(os.environ) is not None:
                _need((not cleanup_only or cleanup_candidate) and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(SCRIPT_OPERATIONS)
            if create_management.configuration(os.environ) is not None:
                _need((not cleanup_only or cleanup_candidate) and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(CREATE_OPERATIONS)
            if script_journey.configured(os.environ):
                _need(not cleanup_only and self.pico_configuration is not None and candidate['e2e_input_layer'] is True)
                values.extend(script_journey.OPERATIONS)
            if authentication_journey.configured(os.environ):
                _need(not cleanup_only and self.pico_configuration is not None and candidate['e2e_input_layer'] is True)
                values.extend(authentication_journey.OPERATIONS)
            if graphics_journey.configured(os.environ):
                _need(not cleanup_only and self.pico_configuration is not None and candidate['e2e_input_layer'] is True)
                values.extend(graphics_journey.OPERATIONS)
            return sorted(set(values))

        def _script_journey(self):
            return script_journey.PicoScriptJourney(self)

        def _authentication_journey(self):
            return authentication_journey.PicoAuthenticationJourney(self)

        def _graphics_journey(self):
            return graphics_journey.PicoGraphicsJourney(self)

        def _script_paths(self, target):
            _need(self.pico_configuration is not None)
            key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
            directory = self.pico_configuration[1]
            return directory / ('normal-script-state-' + key + '.json'), directory / ('normal-script-ui-' + key + '.json')

        def _script_runtime(self, target):
            scene = normal_scripts.configuration(os.environ)
            _need(scene is not None and self.pico_configuration is not None
                  and candidate['e2e_input_layer'] is True)
            identity = self.require_controlled_debug_identity(target)
            installed = self._installation(target)
            _state, ui = self._script_paths(target)
            return normal_scripts.runtime(self, target, scene, installed, identity, ui,
                lambda operation: super(PicoBoundAdapter, self).invoke(target, operation, {}))

        def _scripts(self, target):
            state, _ui = self._script_paths(target)
            return normal_scripts.manager(*self._script_runtime(target), state)

        def _script_files_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'normal-script-files-')))

        @_private
        def _script_files(self, target):
            _ui, _observe, binding = self._script_runtime(target)
            return self._bound_script_files(target, binding)

        def _bound_script_files(self, target, binding):
            native = self._native_feature_observer(target)
            files = NativeScriptFiles(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + SCRIPT_FIXTURE_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid)
            return OwnedScriptFiles(files, self._script_files_store(target), binding)

        @_private
        def _script_file_manager(self, target):
            ui, observe, binding = self._script_runtime(target)
            files = self._bound_script_files(target, binding)
            directory = files.verify()
            picker = TokenScriptFilePicker(ui.io, directory)
            state, _ui = self._script_paths(target)
            return normal_scripts.manager(ui, observe, binding, state, file_owner=files, file_picker=picker)

        @_private
        def _script_missing_manager(self, target):
            ui, observe, binding = self._script_runtime(target)
            state, _ui = self._script_paths(target)
            result = normal_scripts.NormalScriptManager(ui, observe, PrivateFeatureState(state), binding,
                source_kind='feature-script-missing')
            result.sample()
            return result

        @_private
        def _script_manager_status(self, target):
            from adapters.script_manager_status import manager_status
            ui, _observe, _binding = self._script_runtime(target)
            return manager_status(ui.io.capture())

        def _script_restart_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'normal-script-restart-')))

        def _script_restart_handoff(self, target):
            state, _ui = self._script_paths(target)
            return ScriptRestartHandoff(self._script_restart_store(target),
                self._script_files_store(target), PrivateFeatureState(state),
                require_membership=script_journey.configured(os.environ))

        @_private
        def _script_restart_prepare(self, target):
            return self._script_restart_handoff(target).prepare(
                self._script_file_manager(target), self._script_execution_observer(target))

        @_private
        def _script_restart_adopt(self, target):
            ui, observe, binding = self._script_runtime(target)
            handoff = self._script_restart_handoff(target)
            files = self._bound_script_files(target, binding)
            return handoff.adopt(binding, self._process_presence(target),
                self._script_execution_observer(target), files.native, ui, observe,
                TokenScriptFilePicker(ui.io, handoff.directory()))

        def _script_restart_inputs_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'normal-script-restart-inputs-')))

        def _script_restart_inputs(self, target):
            state, _ui = self._script_paths(target)
            return RestartInputs(self._script_restart_inputs_store(target),
                [self._script_restart_store(target), self._script_files_store(target), PrivateFeatureState(state)])

        def _script_restart_source(self, target):
            if self._script_restart_inputs_store(target).read() is not None:
                value = self._script_restart_inputs(target).read()
                if value['phase'] == 'launch-issued':
                    self._script_restart_recover_binding(target)
            _ui, _observe, binding = self._script_runtime(target)
            native = self._native_feature_observer(target)
            native.guard(); _need(native.pid == int(binding['processIdentity'].split(':')[0]))
            return binding, native

        @_private
        def _script_restart_recover_binding(self, target, *, monotonic=None, restart_inputs=None, owner_check=None):
            # This can create only the original host-side nonce journal. It
            # cannot launch, activate, submit an OpenXR grant or deliver input.
            import time
            _need(monotonic is None or callable(monotonic))
            clock = monotonic or time.monotonic
            started = previous = clock()
            def bound():
                nonlocal previous
                now = clock()
                _need(now >= previous and now - started < 30)
                previous = now
            _need((restart_inputs is None)==(owner_check is None))
            inputs = self._script_restart_inputs(target) if restart_inputs is None else restart_inputs
            from adapters.restart_inputs import RestartInputs as RestartInputOwner
            _need(isinstance(inputs,RestartInputOwner))
            origin = inputs.read(); _need(origin['phase'] == 'launch-issued')
            if restart_inputs is None:
                _need(origin['scriptHandoff'] is not None)
                check_owner=lambda:self._script_restart_handoff(target).snapshot()
                plan=check_owner();_need(plan==origin['scriptHandoff'] and plan['next'] is None)
            else:
                _need(callable(owner_check) and origin['scriptHandoff'] is None)
                check_owner=owner_check;plan=check_owner();_need(plan is not None)
            session = self.pico_input_session(target)
            unbound = session.is_unbound(); bound()
            if not unbound: return
            old = origin['oldBinding']
            _need(hashlib.sha256((target + '\0' + str(self.pico_configuration)).encode()).hexdigest()
                  == old['targetFingerprint'])
            installed = self._installation(target)
            _need(all(installed[key] == old[key] for key in ('sourceRevision', 'artifactSha256')))
            def guard():
                bound()
                _need(hashlib.sha256((target + '\0' + str(self.pico_configuration)).encode()).hexdigest()
                      == old['targetFingerprint'])
                installed = self._installation(target)
                _need(all(installed[key] == old[key] for key in ('sourceRevision', 'artifactSha256')))
                bound()
                _need(self.controlled_debug_identity(target) == identity)
                bound()
            bound()
            identity = self.controlled_debug_identity(target)
            _need(type(identity) is str and identity != old['processIdentity']
                  and identity.split(':')[0].isdigit() and int(identity.split(':')[0]) > 0)
            pid = int(identity.split(':')[0]); guard()
            def send(command):
                guard(); self.write_control_command(target, identity, 'restart binding observations', command)
            native = NativeFeatureObservation(send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NATIVE_FEATURE_FILE, attempts=1),
                lambda: self.adb.epoch_milliseconds(target), guard, pid)
            def verify(packet):
                validate_native_restart(origin['oldNative'], dict(pid=packet['processId'],
                    instance=packet['instance'], lifecycle=packet['lifecycle']))
            first = native.read(0); verify(first)
            presence = NativeProcessPresence(send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + PROCESS_PRESENCE_FILE, attempts=1),
                native.clock_ms, guard, pid)
            exited = presence.require_absent(origin['oldNative']['pid'])
            _need(exited['instance'] == first['instance'])
            final = native.read(first['sequence']); verify(final)
            _need(final['instance'] == first['instance'] and final['capturedEpochMs'] >= exited['capturedEpochMs'])
            guard()
            _need(inputs.read() == origin and check_owner() == plan
                  and session.is_unbound())
            bound()
            session.begin(identity)  # Original atomic/locked host binding, no SDK operation.
            guard(); _need(self.require_pico_session_identity(target) == identity)

        def _script_restart_stopped(self, target):
            origin = self._script_restart_inputs(target).read()['oldBinding']
            def guard():
                _need(hashlib.sha256((target + '\0' + str(self.pico_configuration)).encode()).hexdigest()
                      == origin['targetFingerprint'])
                installed = self._installation(target)
                _need(all(installed[key] == origin[key] for key in ('sourceRevision', 'artifactSha256')))
            source = AndroidProcessQuery(self.adb, 'org.overte.pico', guard)
            receipt = source.read(target, int(origin['processIdentity'].split(':')[0]))
            return {'running': bool(receipt['processIds']),
                    'identity': origin['processIdentity'] if receipt['processIds'] else None}

        @_private
        def _script_restart(self, target):
            return run_script_restart(self._script_restart_inputs(target), self._script_restart_handoff(target),
                lambda: self._script_restart_source(target), lambda: self._script_restart_prepare(target),
                lambda: self.invoke(target, 'app.stop', {}), lambda: self._script_restart_stopped(target),
                lambda: self.invoke(target, 'app.launch', {}), lambda: self._script_restart_adopt(target))

        def _graphics_controls(self, target, intent):
            from adapters.token_graphics_ui import TokenGraphicsUI
            from adapters.pico4.normal_graphics import PicoGraphicsIO
            manager = self._scripts(target)
            return TokenGraphicsUI(PicoGraphicsIO(manager.ui.io),intent)

        def _world_render_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'world-render-owner-')))

        @_private
        def _world_render_capture(self, target, *, read_only=False, role=None, require_frame_view=False, source_lock=None):
            _need(type(read_only) is bool and type(require_frame_view) is bool
                and (role is None or type(role) is str and role in ('primary','actor'))
                and (role is None or read_only is True and require_frame_view is True))
            # Legacy component ownership remains explicit v1. Whole Graphics
            # requires independent role v2, original used-camera v4 and native
            # complete issuer/file retirement, including undelivered intents.
            native = self._native_feature_observer(target)
            from adapters.pico4.graphics_binding import PicoGraphicsBinding,SerializedWorldCapture
            facade=PicoGraphicsBinding(self)
            lock=facade._lock(target,source_lock)
            if role is not None:
                _need(source_lock is not None);lock.assert_held()
            if role is None:
                manager = self._scripts(target);binding=manager.binding
                store=self._world_render_store(target)
            else:
                _ui,_observe,binding,guard,_installed=facade.normal_feature_runtime(target,read_only=True)
                guard();_need(native.pid==int(binding['processIdentity'].split(':')[0]))
                store=facade.world_render_store(target,role=role)
            foreign=[facade.world_render_store(target,role=value) for value in ('primary','actor') if value!=role]
            if role is not None:foreign.append(self._world_render_store(target))
            def world_guard():
                lock.assert_held();native.guard()
                _need(all(value.read() is None for value in foreign))
                lock.assert_held()
                return True
            owner = WorldRenderOwner(store,binding,world_guard,role=role)
            files = AndroidWorldRenderReceipts(self.adb,target,'org.overte.pico',world_guard)
            options = dict(monotonic=native.monotonic,sleep=native.sleep)
            storage = NativeWorldRenderStorage(native.send,files.read,native.clock_ms,world_guard,
                native.pid,receipt_intent=owner.receipt_intent,**options)
            if role is None:receipts=files
            else:
                from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles,INVENTORY_FILE
                cleanup=NativeWorldReceiptInventory(native.send,
                    lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+INVENTORY_FILE,attempts=1),
                    native.clock_ms,world_guard,native.pid,owner.owned,lambda:storage.instance,**options)
                receipts=NativeWorldReceiptBatchFiles(files,cleanup)
            capture = NativeWorldRenderCapture(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico',
                    'files/overte-e2e/'+WORLD_RENDER_FILE,attempts=1),
                storage,native.clock_ms,world_guard,native.pid,intent=owner.intent,stereo=True,
                require_cameras=require_frame_view,**options)
            return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=lock)

        def _create_controls(self, target, intent):
            from adapters.token_create_ui import TokenCreateUI
            from adapters.pico4.normal_create import PicoCreateIO
            ui, _observe, _binding = self._script_runtime(target)
            return TokenCreateUI(PicoCreateIO(ui.io),intent)

        def _create_management(self, target):
            return create_management.PicoCreateManagement(self, target)

        def _chat_controls(self, target, intent, run):
            from adapters.token_chat_ui import TokenChatUI
            from adapters.pico4.normal_chat import PicoChatIO
            manager=self._scripts(target)
            return TokenChatUI(PicoChatIO(manager.ui.io),intent,run)

        @_private
        def _places_controls(self, target, intent, run):
            from adapters.token_places_ui import TokenPlacesUI
            from adapters.pico4.normal_places import PicoPlacesIO
            manager = self._scripts(target)
            return TokenPlacesUI(PicoPlacesIO(manager.ui.io), intent, run)

        @_private
        def _bookmark_operations(self, target, path, run):
            from adapters.navigation_bookmarks import NavigationBookmarks
            from adapters.token_places_ui import TokenPlacesUI
            from adapters.pico4.normal_places import PicoPlacesIO
            manager = self._scripts(target)
            return NavigationBookmarks(lambda intent: TokenPlacesUI(PicoPlacesIO(manager.ui.io), intent, run),
                self._location_bookmarks(target), path, run, manager.binding)

        @_private
        def _navigation_arrival(self, target, run, scene_url):
            from adapters.navigation_arrival import NavigationArrival
            manager=self._scripts(target);native=self._native_feature_observer(target)
            def probe(after):
                native.guard()
                result=self.read_probe_snapshot(target,'org.overte.pico',after)
                native.guard();return result
            return NavigationArrival(probe,self._graphics_subject_observer(target),native.clock_ms,native.guard,
                run,manager.binding,scene_url,monotonic=native.monotonic)

        @_private
        def _navigation_stereo(self, target, path, artifact_root, run, scene_url, *, role='primary', source_lock=None, arrival=None, journal_id=None):
            from adapters.navigation_stereo import NavigationStereo
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            facade=PicoGraphicsBinding(self);lock=facade._lock(target,source_lock)
            manager=self._scripts(target);native=self._native_feature_observer(target)
            arrival=self._navigation_arrival(target,run,scene_url) if arrival is None else arrival
            return NavigationStereo(arrival,
                lambda:self._world_render_capture(target,read_only=True,role=role,require_frame_view=True,source_lock=lock),
                path,artifact_root,run,manager.binding,lock,native.guard,role=role,journal_id=journal_id,
                ui_factory=lambda:self._graphics_ui_observer(target),native_factory=lambda:self._native_feature_observer(target),
                monotonic=native.monotonic)

        @_private
        def _navigation_transit(self, target, path, artifact_root, run, scene_url, *, source_lock, directory=None, role='primary'):
            from adapters.navigation_transit import NavigationTransit
            from adapters.pico4.tablet_home import bind_home
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.pico4.normal_places import PicoPlacesIO
            from adapters.token_places_ui import TokenPlacesUI
            from feature_journeys.contract import identifier
            from pathlib import Path
            manager=self._scripts(target);native=self._native_feature_observer(target)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock);arrival=self._navigation_arrival(target,run,scene_url)
            def guard():
                lock.assert_held();return native.guard()
            def stereo(ticket):
                identifier(ticket)
                return self._navigation_stereo(target,Path(path).parent/('navigation-stereo-'+ticket+'.json'),
                    artifact_root,run,scene_url,role=role,source_lock=lock,arrival=arrival)
            return NavigationTransit(lambda intent:TokenPlacesUI(PicoPlacesIO(manager.ui.io),intent,run,
                    monotonic=native.monotonic,sleep=native.sleep),
                arrival,self._navigation_directory_source(target),self._location_bookmarks(target),stereo,
                path,run,manager.binding,scene_url,guard,directory=directory,home=bind_home(self,target,native),
                panels=self._navigation_panels(target),monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_tablet_close(self, target, path, transit, *, source_lock):
            from adapters.pico4.navigation_close import NavigationTabletClose
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.native_feature_observation import need
            manager=self._scripts(target);native=self._native_feature_observer(target)
            need(manager.binding==transit.binding)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock)
            def guard():
                lock.assert_held();return native.guard()
            return NavigationTabletClose(transit,manager.ui,self._graphics_ui_observer(target),path,guard,
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_frames(self, target, path, artifact_root, closed, *, source_lock, role='primary'):
            from adapters.navigation_frames import NavigationFrames
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.native_feature_observation import need
            from feature_journeys.stereo_navigation_evidence import original_name
            from pathlib import Path
            manager=self._scripts(target);native=self._native_feature_observer(target)
            need(manager.binding==closed.binding)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock)
            def guard():
                lock.assert_held();return native.guard()
            def stereo(journal):
                return self._navigation_stereo(target,Path(artifact_root)/original_name(closed.run,role,journal),artifact_root,
                    closed.run,closed.transit.scene_url,role=role,source_lock=lock,arrival=closed.transit.arrival,journal_id=journal)
            return NavigationFrames(closed,stereo,path,artifact_root,role,native.clock_ms,guard,monotonic=native.monotonic)

        @_private
        def _navigation_directory(self, target, path, run, status, provider_instance, inputs, origin, source_profile, guard):
            from adapters.navigation_directory import NavigationDirectory
            from adapters.pico4.normal_places import PicoPlacesIO
            from adapters.token_places_ui import TokenPlacesUI
            manager = self._scripts(target)
            return NavigationDirectory(lambda intent: TokenPlacesUI(PicoPlacesIO(manager.ui.io), intent, run),
                self._navigation_directory_source(target), status, path, run, manager.binding,
                provider_instance, inputs, origin, source_profile, guard)

        @_private
        def _navigation_origin(self, target, path, run, guard):
            from adapters.navigation_origin import NavigationOrigin
            from adapters.pico4.normal_navigation_origin import PicoNavigationOriginIO
            from adapters.pico4.tablet_home import bind_home
            manager = self._scripts(target)
            native=self._native_feature_observer(target)
            return NavigationOrigin(PicoNavigationOriginIO(manager.ui.io), self._navigation_environment(target),
                path, run, manager.binding, guard,home=bind_home(self,target,native),monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_missing(self,target,path,run,status,provider_instance,inputs,owned_origin,*,source_lock):
            from adapters.navigation_missing import NavigationMissing
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.pico4.tablet_home import bind_home
            manager=self._scripts(target);native=self._native_feature_observer(target)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock)
            def guard():
                lock.assert_held();return native.guard()
            return NavigationMissing(lambda intent:self._navigation_lookup_controls(target,intent,run),
                self._navigation_arrival(target,run,inputs['sceneUrl']),bind_home(self,target,native),self._location_bookmarks(target),
                self._navigation_replies(target),self._navigation_modals(target),status,path,run,manager.binding,
                provider_instance,inputs,owned_origin,guard,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_lookup_controls(self,target,intent,run):
            from adapters.pico4.navigation_lookup import PicoNavigationLookup
            return PicoNavigationLookup(self._scripts(target).ui,self._navigation_panels(target),intent,run)

        @_private
        def _navigation_error_controls(self, target, intent, run):
            from adapters.token_navigation_error_ui import TokenNavigationErrorUI
            from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
            manager = self._scripts(target)
            return TokenNavigationErrorUI(PicoNavigationErrorIO(manager.ui.io), intent, run)

        @_private
        def _navigation_error_dismissal(self, target, path, run, status, provider_instance, provider_inputs, owned_origin, guard):
            from adapters.navigation_error_dismissal import NavigationErrorDismissal
            from adapters.token_navigation_error_ui import TokenNavigationErrorUI
            from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
            manager = self._scripts(target)
            return NavigationErrorDismissal(lambda intent: TokenNavigationErrorUI(PicoNavigationErrorIO(manager.ui.io), intent, run),
                self._navigation_replies(target), self._navigation_modals(target), status, path, run, manager.binding,
                provider_instance, provider_inputs, owned_origin, guard)

        def _login_controls(self, target, intent, run, origin):
            from adapters.token_login_ui import TokenLoginUI
            from adapters.pico4.normal_login import PicoLoginIO
            manager=self._scripts(target)
            return TokenLoginUI(PicoLoginIO(manager.ui.io),intent,run,origin)

        def _audio_controls(self, target, intent):
            from adapters.token_audio_ui import TokenAudioUI
            from adapters.pico4.normal_audio import PicoAudioIO
            manager = self._scripts(target)
            return TokenAudioUI(PicoAudioIO(manager.ui.io), intent)

        def _script_file_picker(self, target, directory):
            # Original candidate/OpenXR UI source, independent of manager journal mode.
            ui, _observe, _binding = self._script_runtime(target)
            return TokenScriptFilePicker(ui.io, directory)

        def _navigation_path(self, target):
            _need(self.pico_configuration is not None)
            key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
            return self.pico_configuration[1] / ('normal-navigation-' + key + '.json')

        def _navigation(self, target):
            scene = configured_scene(os.environ)
            _need(scene is not None and self.pico_configuration is not None
                  and candidate['e2e_input_layer'] is True)
            identity = self.require_controlled_debug_identity(target)
            installed = self._installation(target)
            native = NativeNavigationIO(self, target, identity,
                lambda operation: super(PicoBoundAdapter, self).invoke(target, operation, {}))
            return PicoNavigation(native, self._navigation_path(target),
                                  installed, identity, scene)

        def _snapshot_paths(self, target):
            _need(self.pico_configuration is not None)
            key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
            directory = self.pico_configuration[1]
            return (directory / ('normal-snapshot-ui-' + key + '.json'),
                    directory / ('normal-snapshot-preferences-' + key + '.json'))

        @_private
        def _feature_observer(self, target):
            # Internal original-observation transport only. Complete feature
            # input, lifecycle/peer/artifact observers are not available yet,
            # so capabilities() deliberately advertises no feature.* triple.
            _need((not cleanup_only or cleanup_candidate) and self.pico_configuration is not None
                  and candidate['e2e_input_layer'] is True)
            self._installation(target)
            identity = self.require_controlled_debug_identity(target)
            observer = PicoFeatureObservation(self, target, identity)
            observer.guard()
            return observer

        def _snapshot(self, target):
            scene = configured_snapshot(os.environ)
            _need(scene is not None and self.pico_configuration is not None
                  and candidate['e2e_input_layer'] is True)
            identity = self.require_controlled_debug_identity(target)
            installed = self._installation(target)
            native = NativeNavigationIO(self, target, identity,
                lambda operation: super(PicoBoundAdapter, self).invoke(target, operation, {}))
            ui_path, preference_path = self._snapshot_paths(target)
            ui = PicoNavigation(native, ui_path, installed, identity, scene)
            files = AndroidSnapshotFiles(self.adb, target, 'org.overte.pico',
                {key: installed[key] for key in ('sourceRevision', 'artifactSha256')}
                | {'processIdentity': identity}, native.guard, os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR', ''))
            return PicoSnapshot(ui, files, preference_path)

        @_private
        def _native_feature_observer(self, target):
            original = self._feature_observer(target)
            installed = self._installation(target)
            def guard():
                original.guard()
                _need(self._installation(target) == installed)
            def send(command):
                guard()
                self.write_control_command(target, original.identity, 'native feature sources', command)
            return NativeFeatureObservation(send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NATIVE_FEATURE_FILE, attempts=1),
                lambda: self.adb.epoch_milliseconds(target), guard,
                int(original.identity.split(':')[0]))

        @_private
        def _graphics_surface(self,target,run,intent,owns,lease,allow_url):
            from adapters.pico4.graphics_surface import PicoGraphicsSurface
            from adapters.pico4.tablet_home import bind_home
            ui,_observe,_binding=self._script_runtime(target)
            subject=self._graphics_subject_observer(target)
            home=bind_home(self,target,self._native_feature_observer(target))
            return PicoGraphicsSurface(ui,subject,home,run,intent,owns,lease,allow_url)

        @_private
        def _graphics_ui_observer(self, target):
            from adapters.pico4.graphics_source import PicoGraphicsSource
            return PicoGraphicsSource(self,target,self._native_feature_observer(target))

        @_private
        def _web_runtime_observer(self, target):
            from adapters.native_web_runtime import NativeWebRuntime, FILE as RUNTIME_FILE
            native = self._native_feature_observer(target)
            return NativeWebRuntime(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + RUNTIME_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, require_renderers=True,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _tablet_http_observer(self, target):
            from adapters.native_tablet_http import NativeTabletHttp, FILE as HTTP_FILE
            native = self._native_feature_observer(target)
            return NativeTabletHttp(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + HTTP_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _scene_load_observer(self, target):
            from adapters.native_scene_loads import NativeSceneLoads, FILE as LOADS_FILE
            native = self._native_feature_observer(target)
            return NativeSceneLoads(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + LOADS_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _graphics_subject_observer(self, target):
            from adapters.native_graphics_subject import NativeGraphicsSubject, FILE as SUBJECT_FILE
            native = self._native_feature_observer(target)
            return NativeGraphicsSubject(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + SUBJECT_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, require_framework=True,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _process_presence(self, target):
            native = self._native_feature_observer(target)
            return NativeProcessPresence(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + PROCESS_PRESENCE_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _navigation_replies(self,target):
            native=self._native_feature_observer(target)
            return NativeNavigationReplies(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+NAVIGATION_REPLIES_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _location_bookmarks(self, target):
            native = self._native_feature_observer(target)
            return NativeLocationBookmarks(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + LOCATION_BOOKMARKS_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _navigation_panels(self, target):
            from adapters.native_navigation_panels import NativeNavigationPanels,FILE
            native=self._native_feature_observer(target)
            return NativeNavigationPanels(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_directory_source(self, target):
            native = self._native_feature_observer(target)
            return NativeNavigationDirectory(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NAVIGATION_DIRECTORY_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _navigation_environment(self, target):
            native = self._native_feature_observer(target)
            return NativeNavigationEnvironment(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NAVIGATION_ENVIRONMENT_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _navigation_modals(self, target):
            native = self._native_feature_observer(target)
            return NativeNavigationModals(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NAVIGATION_MODALS_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

        def _audio_page_store(self,target,*,create=True):
            store=self._lifecycle_world_store(target,create=create)
            return None if store is None else PrivateFeatureState(store.path.with_name('audio-page-owner.json'))

        def _audio_capture_store(self,target,cycle,*,create=True):
            _need(type(cycle) is int and 1<=cycle<=8)
            store=self._audio_page_store(target,create=create)
            return None if store is None else PrivateFeatureState(store.path.with_name(f'audio-capture-cycle-{cycle:02d}.json'))

        def _audio_capture_owned(self,target):
            store=self._audio_page_store(target,create=False)
            if store is None:return False
            # Orphan manifests and original PCM still own their scope. A base
            # process-stop acknowledgement cannot retire or delete them.
            return any(any(store.path.parent.glob(prefix)) for prefix in
                ('audio-capture-cycle-*','audio-capture-original-*','audio-background-cycle-*','audio-final-*','audio-recipe-*'))

        @_private
        def _snapshot_native_originals(self,target,*,source_lock=None):
            from adapters.pico4.snapshot_originals import PicoSnapshotOriginals,FILE
            source_lock=self._script_journey()._lock(target,source_lock)
            native=self._native_feature_observer(target)
            return PicoSnapshotOriginals(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,source_lock,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _script_work(self, target):
            from adapters.native_script_work import NativeScriptWork, FILE, command
            native = self._native_feature_observer(target)
            def send(value):
                command(value); native.guard(); native.send(value)
            return NativeScriptWork(send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _snapshot_capture_files(self,target,artifact_root,owner_path,binding,*,read_only=False,before_send=None,source_lock=None):
            from adapters.pico4.snapshot_capture_files import CaptureFileTransport,PicoSnapshotCaptureFiles
            from adapters.normal_feature_state import context
            _need(type(read_only) is bool and (read_only or callable(before_send)));context(binding)
            lock=self._script_journey()._lock(target,source_lock)
            _need(Path(owner_path).parent==lock.path.parent)
            with lock.held():
                snapshot=self._snapshot(target);observed=snapshot.ui.snapshot();installed=self._installation(target)
                _need(binding['processIdentity']==snapshot.ui.io.identity and binding['sessionId']==observed['bridgeId']
                    and all(binding[key]==installed[key] for key in ('sourceRevision','artifactSha256'))
                    and binding['targetFingerprint']==hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
                native=self._native_feature_observer(target);owner=None
                def admission(command):
                    _need(owner is not None);owner.before_source_send(command)
                    if before_send is not None:before_send(command)
                source=self._snapshot_capture_file_source(target,read_only=read_only,before_send=admission,source_lock=lock)
                transport=CaptureFileTransport(self.adb,target,'org.overte.pico',
                    {key:binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')},native.guard,artifact_root)
                owner=PicoSnapshotCaptureFiles(transport,source,binding,owner_path,read_only=read_only,clock_ms=native.clock_ms)
                return owner

        @_private
        def _snapshot_upload_source(self,target,*,source_lock=None):
            from adapters.pico4.snapshot_upload_source import PicoSnapshotUploadSource,FILE
            lock=self._script_journey()._lock(target,source_lock);native=self._native_feature_observer(target)
            return PicoSnapshotUploadSource(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,lock,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _snapshot_system_source(self,target,binding,authority,*,source_lock):
            from adapters.pico4.snapshot_system_source import PicoSnapshotSystemSource
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            # Existing OS/kernel/candidate/session source, never NativeNavigationIO
            # or a foreground-only Qt command with an exception bolted onto it.
            facade=PicoGraphicsBinding(self)
            return PicoSnapshotSystemSource(binding,lock,
                lambda:facade._graphics_lifecycle_status(target,binding),
                lambda *args:self.adb.shell(target,*args),
                lambda:self.adb.epoch_milliseconds(target),authority)

        @_private
        def _snapshot_exports(self,target,*,read_only=True,before_send=None,source_lock=None):
            from adapters.pico4.snapshot_exports import PicoSnapshotExports,PicoSnapshotExportIO
            _need(type(read_only) is bool and (read_only or callable(before_send)))
            lock=self._script_journey()._lock(target,source_lock)
            installed=self._installation(target);identity=self.require_controlled_debug_identity(target)
            native=self._native_feature_observer(target);source=None
            def final_admission(command):
                _need(source is not None)
                if before_send is not None:before_send(command)
                source.before_publish(command)
            io=PicoSnapshotExportIO(self,target,identity,lambda operation:None,before_send=final_admission)
            _need(installed==self._installation(target))
            source=PicoSnapshotExports(io,native.clock_ms,native.pid,lock,read_only=read_only,
                monotonic=native.monotonic,sleep=native.sleep)
            return source

        @_private
        def _snapshot_capture_file_source(self,target,*,read_only=True,before_send=None,source_lock=None):
            from adapters.pico4.snapshot_capture_source import PicoSnapshotCaptureFileSource,PicoSnapshotCaptureFileIO
            _need(type(read_only) is bool and (read_only or callable(before_send)))
            lock=self._script_journey()._lock(target,source_lock)
            installed=self._installation(target);identity=self.require_controlled_debug_identity(target)
            native=self._native_feature_observer(target)
            source=None
            def final_admission(command):
                _need(source is not None)
                if before_send is not None:before_send(command)
                source.before_publish(command)
            io=PicoSnapshotCaptureFileIO(self,target,identity,lambda operation:None,before_send=final_admission)
            _need(installed==self._installation(target))
            source=PicoSnapshotCaptureFileSource(io,native.clock_ms,native.pid,lock,read_only=read_only,
                monotonic=native.monotonic,sleep=native.sleep)
            return source

        @_private
        def _snapshot_cancel(self,target,*,before_send,source_lock=None):
            from adapters.pico4.snapshot_cancel import PicoSnapshotCancel,PicoSnapshotCancelIO
            _need(callable(before_send));lock=self._script_journey()._lock(target,source_lock)
            snapshot=self._snapshot(target);original=snapshot.ui.io;native=self._native_feature_observer(target)
            io=PicoSnapshotCancelIO(self,target,original.identity,original._controller,before_send=before_send)
            return PicoSnapshotCancel(io,native.clock_ms,native.pid,lock,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _snapshot_script_originals(self,target,*,source_lock=None):
            from adapters.pico4.snapshot_script_originals import PicoSnapshotScriptOriginals,FILE
            source_lock=self._script_journey()._lock(target,source_lock)
            native=self._native_feature_observer(target)
            return PicoSnapshotScriptOriginals(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,source_lock,monotonic=native.monotonic,sleep=native.sleep)

        def _snapshot_still_store(self,target,*,create=True):
            journey=self._script_journey();path=journey.state_path(target) if create else journey.existing_state_path(target)
            return None if path is None else PrivateFeatureState(path.with_name('snapshot-still-owner.json'))

        def _snapshot_originals_owned(self,target):
            store=self._snapshot_still_store(target,create=False)
            if store is None:return False
            names=('snapshot-cancel-owner.json','snapshot-cancel-files-owner.json','snapshot-cancel-originals.json',
                'snapshot-save-owner.json','snapshot-save-originals.json','snapshot-upload-fail-owner.json','snapshot-upload-owner.json',
                'snapshot-upload-fail-originals.json','snapshot-upload-originals.json','snapshot-background-owner.json','snapshot-background-originals.json')
            paths=[store.path]+[store.path.with_name(name) for name in names]
            paths.extend(store.path.with_name('snapshot-return-image-'+role+suffix) for role in ('primary','actor') for suffix in ('.json','-originals.json'))
            prefixes=('snapshot-cancel-originals.json.frame-','snapshot-save-originals.json.frame-','snapshot-upload-fail-originals.json.frame-',
                'snapshot-upload-originals.json.frame-','snapshot-background-originals.json.frame-',
                'snapshot-return-image-primary-originals.json.frame-','snapshot-return-image-actor-originals.json.frame-')
            return any(path.exists() or path.is_symlink() for path in paths) or any(path.name.startswith(prefixes) for path in store.path.parent.iterdir())

        @_private
        def _snapshot_cancel_owner(self,target,run,phase_source,*,source_lock=None):
            from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
            lock=self._script_journey()._lock(target,source_lock)
            snapshot=self._snapshot(target);observed=snapshot.ui.snapshot();installed=self._installation(target)
            binding={key:installed[key] for key in ('sourceRevision','artifactSha256')}
            binding.update(processIdentity=snapshot.ui.io.identity,sessionId=observed['bridgeId'],generation=0,
                targetFingerprint=hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
            owner=None
            def before_cancel(command):
                _need(owner is not None);owner.before_cancel(command)
            def before_file(command):
                _need(owner is not None);owner.before_file(command)
            files=self._snapshot_capture_files(target,snapshot.files.artifacts,lock.path.with_name('snapshot-cancel-files-owner.json'),
                binding,before_send=before_file,source_lock=lock)
            owner=PicoSnapshotCancelOwner(lock.path.with_name('snapshot-cancel-owner.json'),run,binding,snapshot,
                self._snapshot_native_originals(target,source_lock=lock),self._snapshot_script_originals(target,source_lock=lock),
                self._snapshot_cancel(target,before_send=before_cancel,source_lock=lock),files,
                self._script_roots_observer(target),self._script_execution_observer(target),self._script_work(target),self._snapshot_platform(target),self.pico_input_session(target),phase_source)
            return owner

        @_private
        def _snapshot_save_owner(self,target,run,phase_source,*,parent=None,source_lock=None):
            from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
            from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
            from adapters.pico4.snapshot_saved_files import PicoSnapshotSavedFiles
            if parent is not None:
                _need(isinstance(parent,PicoSnapshotCancelOwner))
                if source_lock is None:source_lock=parent.lock
            lock=self._script_journey()._lock(target,source_lock)
            if parent is None:parent=self._snapshot_cancel_owner(target,run,phase_source,source_lock=lock)
            _need(isinstance(parent,PicoSnapshotCancelOwner) and parent.run==run and parent.lock is lock and parent.source is phase_source)
            native=self._native_feature_observer(target);owner=None
            def admission(command):
                _need(owner is not None);owner.before_source_send(command)
            def publish(id,content):
                _need(owner is not None);return owner.publish(id,content)
            exports=self._snapshot_exports(target,read_only=False,before_send=admission,source_lock=lock)
            saved=PicoSnapshotSavedFiles(self.adb,target,'org.overte.pico',
                {key:parent.binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')},native.guard,
                parent.files.transport.artifacts,exports,run,publish)
            owner=PicoSnapshotSaveOwner(lock.path.with_name('snapshot-save-owner.json'),parent,exports,saved)
            return owner

        @_private
        def _snapshot_return_image(self,target,run,phase_source,artifact_root,*,parent=None,role='primary',source_lock=None):
            from adapters.pico4.snapshot_background_owner import PicoSnapshotBackgroundOwner
            from adapters.pico4.snapshot_return_image import PicoSnapshotReturnImage
            _need(role in ('primary','actor'))
            if parent is None:parent=self._snapshot_background_owner(target,run,phase_source,source_lock=source_lock)
            _need(isinstance(parent,PicoSnapshotBackgroundOwner) and parent.run==run and parent.source is phase_source
                and (source_lock is None or source_lock is parent.lock))
            lock=self._script_journey()._lock(target,parent.lock)
            return PicoSnapshotReturnImage(parent,lock.path.with_name('snapshot-return-image-'+role+'.json'),artifact_root,
                lambda:self._world_render_capture(target,read_only=True,role=role,require_frame_view=True,source_lock=lock),
                role=role,monotonic=phase_source.monotonic)

        @_private
        def _snapshot_background_owner(self,target,run,phase_source,*,parent=None,source_lock=None):
            from adapters.pico4.snapshot_background_owner import PicoSnapshotBackgroundOwner
            from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.normal_feature_state import context
            if parent is not None:
                _need(isinstance(parent,PicoSnapshotUploadOwner) and parent.run==run and parent.verb=='upload'
                    and parent.source is phase_source and (source_lock is None or source_lock is parent.lock))
                source_lock=parent.lock
            lock=self._script_journey()._lock(target,source_lock)
            path=lock.path.with_name('snapshot-background-owner.json');parent_disk=PrivateFeatureState(lock.path.with_name('snapshot-upload-owner.json')).read()
            _need(parent_disk is not None);binding=context(parent_disk['binding']);facade=PicoGraphicsBinding(self)
            def runtime():
                # This factory is called only after the original OS foreground
                # source has proved return. Cold BG load never enters Qt here.
                if parent is not None:return parent
                saved=self._snapshot_save_owner(target,run,phase_source,source_lock=lock)
                failed=self._snapshot_upload_owner(target,run,phase_source,'upload-fail',parent=saved,source_lock=lock)
                return self._snapshot_upload_owner(target,run,phase_source,'upload',parent=saved,source_lock=lock,failure=failed)
            return PicoSnapshotBackgroundOwner(path,run,binding,lock,phase_source,
                lambda owned:facade._graphics_lifecycle_status(target,owned),
                lambda operation,owned,*,before_input:self._pico_lifecycle_input_once(target,operation,owned,before_input=before_input),
                runtime,monotonic=phase_source.monotonic,sleep=parent.native.sleep if parent is not None else time.sleep)

        @_private
        def _snapshot_upload_owner(self,target,run,phase_source,verb,*,parent,source_lock=None,failure=None):
            from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner
            from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
            from adapters.pico4.snapshot_upload_fixture import SnapshotUploadFixtureReader
            from adapters.pico4.snapshot_upload_bytes import PicoSnapshotUploadBytes
            _need(isinstance(parent,PicoSnapshotSaveOwner) and parent.run==run and parent.source is phase_source and verb in ('upload-fail','upload'))
            if source_lock is None:source_lock=parent.lock
            lock=self._script_journey()._lock(target,source_lock);_need(parent.lock is lock)
            with lock.held():parent.load();_need(parent.state['stage']=='partial-ready')
            fixture=SnapshotUploadFixtureReader(phase_source.client,run,epoch_ms=phase_source.epoch_ms,monotonic=phase_source.monotonic)
            native=self._native_feature_observer(target)
            independent=PicoSnapshotUploadBytes(fixture,native.guard,native.clock_ms,monotonic=native.monotonic)
            return PicoSnapshotUploadOwner(lock.path.with_name('snapshot-'+verb+'-owner.json'),parent,
                self._snapshot_upload_source(target,source_lock=lock),fixture,independent,native,verb,failure=failure)

        @_private
        def _snapshot_platform(self,target):
            from adapters.pico4.snapshot_platform import PicoSnapshotPlatform
            native=self._native_feature_observer(target)
            return PicoSnapshotPlatform(lambda:self.adb.prop(target,'ro.build.version.sdk'),native.guard,native.clock_ms,
                monotonic=native.monotonic)

        @_private
        def _snapshot_still_owner(self,target,run,phase_source,*,source_lock=None):
            from adapters.pico4.snapshot_still_owner import PicoSnapshotStillOwner
            source_lock=self._script_journey()._lock(target,source_lock)
            snapshot=self._snapshot(target);observed=snapshot.ui.snapshot();installed=self._installation(target)
            binding={key:installed[key] for key in ('sourceRevision','artifactSha256')}
            binding.update(processIdentity=snapshot.ui.io.identity,sessionId=observed['bridgeId'],generation=0,
                targetFingerprint=hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
            return PicoSnapshotStillOwner(self._snapshot_still_store(target).path,run,binding,snapshot,
                self._snapshot_native_originals(target,source_lock=source_lock),self.pico_input_session(target),phase_source)

        @_private
        def _audio_recipe(self,target,run,phase_source,*,source_lock=None):
            from adapters.pico4.audio_recipe import PicoAudioRecipe
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.normal_feature_state import context
            source_lock=self._script_journey()._lock(target,source_lock)
            path=self._audio_page_store(target).path.with_name('audio-recipe-owner.json')
            disk=PrivateFeatureState(path).read()
            # Cold background construction reads only private original metadata.
            binding=context(disk['binding']) if disk is not None else self._scripts(target).binding
            facade=PicoGraphicsBinding(self)
            return PicoAudioRecipe(path,run,binding,source_lock,phase_source,
                lambda:self._audio_page_owner(target,run,source_lock=source_lock),
                lambda cycle,parent:self._audio_capture_owner(target,run,cycle,phase_source,parent=parent,source_lock=source_lock),
                lambda cycle,capture:self._audio_background_owner(target,run,cycle,phase_source,capture=capture,source_lock=source_lock),
                lambda cycle,capture:self._audio_final_close(target,run,cycle,phase_source,capture=capture,source_lock=source_lock),
                lambda owned:facade._graphics_lifecycle_status(target,owned),monotonic=phase_source.monotonic)

        @_private
        def _audio_final_close(self,target,run,cycle,phase_source,*,capture=None,source_lock=None):
            from adapters.pico4.audio_final_close import PicoAudioFinalClose
            from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
            if capture is not None:
                _need(isinstance(capture,PicoAudioCaptureOwner) and capture.run==run and capture.store.path==self._audio_capture_store(target,cycle).path)
                _need(source_lock is None or source_lock is capture.lock);source_lock=capture.lock
            source_lock=self._script_journey()._lock(target,source_lock)
            actual=capture or self._audio_capture_owner(target,run,cycle,phase_source,source_lock=source_lock)
            _need(actual.source is phase_source and actual.lock is source_lock)
            return PicoAudioFinalClose(actual.store.path.with_name('audio-final-close.json'),actual)

        def _audio_background_store(self,target,cycle,*,create=True):
            store=self._audio_capture_store(target,cycle,create=create)
            return None if store is None else PrivateFeatureState(store.path.with_name(f'audio-background-cycle-{cycle:02d}.json'))

        @_private
        def _audio_background_owner(self,target,run,cycle,phase_source,*,capture=None,source_lock=None):
            from adapters.pico4.audio_background_owner import PicoAudioBackground
            from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.normal_feature_state import context
            path=self._audio_background_store(target,cycle).path
            if capture is not None:
                _need(isinstance(capture,PicoAudioCaptureOwner) and capture.run==run and capture.store.path==self._audio_capture_store(target,cycle).path)
                _need(source_lock is None or source_lock is capture.lock);source_lock=capture.lock
            source_lock=self._script_journey()._lock(target,source_lock);disk=PrivateFeatureState(path).read()
            binding=context(disk['binding']) if disk is not None else self._scripts(target).binding
            facade=PicoGraphicsBinding(self)
            def runtime():
                actual=capture or self._audio_capture_owner(target,run,cycle,phase_source,source_lock=source_lock)
                _need(actual.binding==binding and actual.lock is source_lock);return actual
            return PicoAudioBackground(path,run,binding,source_lock,
                lambda owned:facade._graphics_lifecycle_status(target,owned),
                lambda operation,owned,*,before_input:self._pico_lifecycle_input_once(
                    target,operation,owned,before_input=before_input),runtime,phase_source,
                monotonic=capture.parent.settings.monotonic if capture is not None else time.monotonic,
                sleep=capture.parent.settings.sleep if capture is not None else time.sleep)

        @_private
        def _audio_capture_owner(self,target,run,cycle,phase_source,*,parent=None,source_lock=None):
            from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
            from adapters.pico4.audio_page_owner import PicoAudioPageOwner
            if parent is not None:
                _need(isinstance(parent,PicoAudioPageOwner) and parent.run==run and parent.store.path==self._audio_page_store(target).path)
                _need(source_lock is None or source_lock is parent.lock);source_lock=parent.lock
            source_lock=self._script_journey()._lock(target,source_lock)
            with source_lock.held():
                manager=self._scripts(target);self._native_feature_observer(target).guard()
                if parent is None:parent=self._audio_page_owner(target,run,source_lock=source_lock)
                _need(parent.binding==manager.binding and parent.lock is source_lock)
                return PicoAudioCaptureOwner(self._audio_capture_store(target,cycle).path,parent,phase_source)

        @_private
        def _audio_page_owner(self,target,run,*,source_lock=None):
            from adapters.pico4.audio_page_owner import PicoAudioPageOwner
            from adapters.pico4.normal_audio import PicoAudioIO
            from adapters.token_audio_ui import TokenAudioUI
            source_lock=self._script_journey()._lock(target,source_lock)
            with source_lock.held():
                manager=self._scripts(target);native=self._native_feature_observer(target)
                return PicoAudioPageOwner(self._audio_page_store(target).path,run,manager.binding,
                    self._audio_pages_source(target,source_lock=source_lock),self._audio_settings_source(target,source_lock=source_lock),
                    self._lifecycle_ui_source(target,source_lock=source_lock),self._audio_preview(target,run,source_lock=source_lock),
                    self.pico_input_session(target),TokenAudioUI(PicoAudioIO(manager.ui.io),lambda *_:None,
                        monotonic=native.monotonic,sleep=native.sleep),source_lock)

        @_private
        def _audio_pages_source(self,target,*,source_lock=None):
            from adapters.pico4.audio_pages import PicoAudioPages,FILE
            native=self._native_feature_observer(target);manager=self._scripts(target)
            source_lock=self._script_journey()._lock(target,source_lock)
            return PicoAudioPages(
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,manager.binding['sessionId'],source_lock,
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _audio_settings_source(self,target,*,source_lock=None):
            from adapters.pico4.audio_settings_source import PicoAudioSettings,FILE
            native=self._native_feature_observer(target)
            source_lock=self._script_journey()._lock(target,source_lock)
            return PicoAudioSettings(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,source_lock=source_lock)

        @_private
        def _lifecycle_drive_source(self,target,*,source_lock=None):
            from adapters.pico4.lifecycle_drive import PicoLifecycleDrive,FILE
            native=self._native_feature_observer(target)
            source_lock=self._script_journey()._lock(target,source_lock)
            return PicoLifecycleDrive(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,source_lock=source_lock)

        @_private
        def _lifecycle_gesture_source(self,target,*,source_lock=None):
            from adapters.pico4.lifecycle_gesture import PicoLifecycleGesture,FILE
            native=self._native_feature_observer(target)
            source_lock=self._script_journey()._lock(target,source_lock)
            return PicoLifecycleGesture(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,source_lock=source_lock)

        @_private
        def _lifecycle_ui_source(self, target,*,source_lock=None):
            from adapters.pico4.lifecycle_source import bind_source
            return bind_source(self, target, self._native_feature_observer(target),source_lock=source_lock)

        def _lifecycle_world_store(self,target,*,create=True):
            journey=self._script_journey()
            path=journey.state_path(target) if create else journey.existing_state_path(target)
            return None if path is None else PrivateFeatureState(path.with_name('lifecycle-world-owner.json'))

        def _lifecycle_background_owned(self,target):
            store=self._lifecycle_world_store(target,create=False)
            if store is None:return False
            parent=store.path.parent;store._parent()
            names={'lifecycle-background-owner.json','lifecycle-background-originals.json'}
            for index,path in enumerate(parent.iterdir()):
                _need(index<4096)
                if path.name in names or path.name.startswith('lifecycle-background-originals.json.frame-'):return True
            return False

        @_private
        def _lifecycle_world(self,target,run,*,source_lock=None):
            from adapters.pico4.lifecycle_world import PicoLifecycleWorld
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();identity=self.require_pico_session_identity(target)
            _need(identity==manager.binding['processIdentity'] and native.pid==int(identity.split(':')[0]))
            source_lock=self._script_journey()._lock(target,source_lock)
            return PicoLifecycleWorld(self._lifecycle_ui_source(target,source_lock=source_lock),self._lifecycle_gesture_source(target,source_lock=source_lock),
                self._lifecycle_drive_source(target,source_lock=source_lock),self.pico_input_session(target),self._lifecycle_world_store(target).path,
                run,manager.binding,native.guard,source_lock,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _lifecycle_x_join(self,target,run,*,source_lock=None):
            from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
            from adapters.pico4.lifecycle_back import PicoLifecycleBack
            from adapters.pico4.lifecycle_source import bind_source
            world=self._lifecycle_world(target,run,source_lock=source_lock);native=self._native_feature_observer(target)
            back=PicoLifecycleBack(bind_source(self,target,native,source_lock=world.lock),world.session,world.store.path.with_name('lifecycle-x-back-owner.json'),
                run,world.binding,native.guard,monotonic=native.monotonic,sleep=native.sleep,source_lock=world.lock)
            return PicoLifecycleXJoin(world,back,world.store.path.with_name('lifecycle-x-join.json'))

        @_private
        def _lifecycle_domain_source(self,target,*,source_lock=None):
            from adapters.pico4.lifecycle_process import PicoLifecycleDomain
            native=self._native_feature_observer(target);source_lock=self._script_journey()._lock(target,source_lock)
            reader=NativeChatObservation(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CHAT_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
            return PicoLifecycleDomain(reader,source_lock)

        @_private
        def _lifecycle_process_retirement(self,target,run,*,source_lock=None):
            from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement
            installed=self._installation(target);configuration=self.pico_configuration
            fingerprint=hashlib.sha256((target+'\0'+str(configuration)).encode()).hexdigest()
            def guard():
                _need(self.pico_configuration==configuration and self._installation(target)==installed)
            source_lock=self._script_journey()._lock(target,source_lock)
            path=self._lifecycle_world_store(target).path.with_name('lifecycle-process-owner.json')
            result=PicoLifecycleProcessRetirement(path,run,self.pico_input_session(target).profile,guard,source_lock)
            if result.state is not None:
                _need(result.state['binding']['targetFingerprint']==fingerprint
                    and all(result.state['binding'][key]==installed[key] for key in ('sourceRevision','artifactSha256')))
            return result

        @_private
        def _lifecycle_process_begin(self,target,run):
            world=self._lifecycle_world(target,run)
            if world.state is None:world.prepare()
            owner=self._lifecycle_process_retirement(target,run,source_lock=world.lock)
            return owner.begin(world,self._native_feature_observer(target),self._lifecycle_domain_source(target,source_lock=world.lock))

        @_private
        def _lifecycle_process_prepare(self,target,run):
            joined=self._lifecycle_x_join(target,run)
            owner=self._lifecycle_process_retirement(target,run,source_lock=joined.world.lock)
            return owner.prepare(joined,self._native_feature_observer(target),self._lifecycle_domain_source(target,source_lock=joined.world.lock))

        @_private
        def _lifecycle_process_new_binding(self,target,owner):
            # Read the original new-process bridge without constructing the
            # original process's still-owned normal Script manager journal.
            from adapters.pico4.navigation import validate_snapshot
            installed=self._installation(target);identity=self.require_controlled_debug_identity(target)
            _need(identity==self.require_pico_session_identity(target))
            native=NativeNavigationIO(self,target,identity,lambda _operation:_need(False))
            started=owner.now();value,epoch=native.read();validate_snapshot(value,int(identity.split(':')[0]),epoch)
            native.guard();elapsed=owner.now()-started
            _need(max(epoch-value['updatedEpochMs'],elapsed*1000)<=1500)
            binding={key:installed[key] for key in ('sourceRevision','artifactSha256')}
            binding.update(processIdentity=identity,sessionId=value['bridgeId'],generation=0,
                targetFingerprint=hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
            return binding

        @_private
        def _lifecycle_process_observe(self,target,run,*,owner=None):
            if owner is None:owner=self._lifecycle_process_retirement(target,run)
            binding=self._lifecycle_process_new_binding(target,owner)
            return owner.observe(binding,self._native_feature_observer(target),self._process_presence(target),
                self._lifecycle_domain_source(target,source_lock=owner.lock),self._lifecycle_ui_source(target,source_lock=owner.lock),
                self._lifecycle_gesture_source(target,source_lock=owner.lock),self._lifecycle_drive_source(target,source_lock=owner.lock))

        @_private
        def _lifecycle_process_restart(self,target,run):
            from adapters.pico4.lifecycle_process import run_lifecycle_restart
            owner=self._lifecycle_process_retirement(target,run)
            def prepare():
                joined=self._lifecycle_x_join(target,run,source_lock=owner.lock)
                owner.prepare(joined,self._native_feature_observer(target),self._lifecycle_domain_source(target,source_lock=owner.lock))
            def stopped():
                origin=owner.inputs.read()['oldBinding'];owner.guard()
                receipt=AndroidProcessQuery(self.adb,'org.overte.pico',owner.guard).read(target,int(origin['processIdentity'].split(':')[0]))
                return dict(running=bool(receipt['processIds']),identity=origin['processIdentity'] if receipt['processIds'] else None)
            return run_lifecycle_restart(owner,prepare,lambda:self._native_feature_observer(target),
                lambda:self.invoke(target,'app.stop',{}),stopped,lambda:self.invoke(target,'app.launch',{}),
                lambda:self._script_restart_recover_binding(target,restart_inputs=owner.inputs,owner_check=lambda:owner.store.read()),
                lambda:self._lifecycle_process_observe(target,run,owner=owner))

        @_private
        def _lifecycle_draft_controls(self,target,intent,run):
            from adapters.token_lifecycle_ui import TokenLifecycleUI
            from adapters.pico4.normal_lifecycle import PicoLifecycleIO
            manager=self._scripts(target)
            return TokenLifecycleUI(PicoLifecycleIO(manager.ui.io),intent,run)

        @_private
        def _lifecycle_editor(self,target,run,*,source_lock=None):
            from adapters.pico4.lifecycle_editor import PicoLifecycleEditor
            from adapters.token_create_ui import TokenCreateUI
            from adapters.token_lifecycle_ui import TokenLifecycleUI
            from adapters.pico4.normal_create import PicoCreateIO
            from adapters.pico4.normal_lifecycle import PicoLifecycleIO
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();identity=self.require_pico_session_identity(target)
            _need(identity==manager.binding['processIdentity'] and native.pid==int(identity.split(':')[0]))
            source_lock=self._script_journey()._lock(target,source_lock)
            def unavailable(_value):_need(False)
            route=TokenCreateUI(PicoCreateIO(manager.ui.io),unavailable)
            field=TokenLifecycleUI(PicoLifecycleIO(manager.ui.io),unavailable,run)
            return PicoLifecycleEditor(self._lifecycle_world_store(target).path.with_name('lifecycle-editor-owner.json'),run,
                manager.binding,self._lifecycle_ui_source(target,source_lock=source_lock),self.pico_input_session(target),route,field,source_lock)

        @_private
        def _lifecycle_create_world_back(self,target,run):
            from adapters.pico4.lifecycle_editor import run_create_world_back
            joined=self._lifecycle_x_join(target,run)
            return run_create_world_back(self._lifecycle_editor(target,run,source_lock=joined.world.lock),joined)

        @_private
        def _lifecycle_chat_editor(self,target,run,*,source_lock=None,joined=None):
            from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
            from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
            if joined is None:joined=self._lifecycle_x_join(target,run,source_lock=source_lock)
            else:
                _need(isinstance(joined,PicoLifecycleXJoin) and joined.world.run==run)
                source_lock=self._script_journey()._lock(target,source_lock or joined.world.lock)
                _need(source_lock is joined.world.lock)
                _need(joined.world.binding==self._scripts(target).binding)
            def unavailable(_value):_need(False)
            return PicoLifecycleChatDraft(joined,self._lifecycle_ui_source(target,source_lock=joined.world.lock),
                self._chat_controls(target,unavailable,run),joined.world.store.path.with_name('lifecycle-chat-owner.json'))

        @_private
        def _lifecycle_chat_draft(self,target,run,*,source_lock=None,joined=None):
            from adapters.pico4.lifecycle_chat import run_chat_draft
            return run_chat_draft(self._lifecycle_chat_editor(target,run,source_lock=source_lock,joined=joined))

        @_private
        def _lifecycle_background_source(self,target,*,source_lock=None,intent=None):
            from adapters.pico4.lifecycle_background_source import bind_source
            return bind_source(self,target,self._native_feature_observer(target),source_lock=source_lock,intent=intent)

        @_private
        def _lifecycle_background_owner(self,target,run,*,source_lock=None,world=None):
            from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
            from adapters.pico4.lifecycle_world import PicoLifecycleWorld
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.normal_feature_state import context
            path=self._lifecycle_world_store(target).path.with_name('lifecycle-background-owner.json')
            source_lock=self._script_journey()._lock(target,source_lock or (world.lock if world is not None else None))
            disk=PrivateFeatureState(path).read()
            # Reading an old private archive is not a foreground assertion.
            # The OS facade below revalidates actual PID/start and candidate
            # before normal activation or acquiring any live Qt runtime.
            binding=context(disk['binding']) if disk is not None else self._scripts(target).binding
            if world is not None:
                _need(isinstance(world,PicoLifecycleWorld) and world.lock is source_lock and world.run==run and world.binding==binding)
            facade=PicoGraphicsBinding(self)
            def runtime(intent):
                actual=world or self._lifecycle_world(target,run,source_lock=source_lock)
                _need(actual.binding==binding and self._scripts(target).binding==binding)
                native=self._native_feature_observer(target)
                return actual,self._lifecycle_background_source(target,source_lock=source_lock,intent=intent),native
            return PicoLifecycleBackground(path,run,binding,source_lock,
                lambda owned:facade._graphics_lifecycle_status(target,owned),
                lambda operation,owned:facade._graphics_lifecycle_input(target,operation,owned),runtime,
                monotonic=world.monotonic if world is not None else time.monotonic,
                sleep=world.sleep if world is not None else time.sleep)

        def _lifecycle_back_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','lifecycle-back-owner-')))

        @_private
        def _lifecycle_back(self,target,run):
            from adapters.pico4.lifecycle_back import PicoLifecycleBack
            from adapters.pico4.lifecycle_source import bind_source
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();identity=self.require_pico_session_identity(target)
            _need(identity==manager.binding['processIdentity'] and native.pid==int(identity.split(':')[0]))
            source_lock=self._script_journey()._lock(target)
            return PicoLifecycleBack(bind_source(self,target,native,source_lock=source_lock),self.pico_input_session(target),
                self._lifecycle_back_store(target).path,run,manager.binding,native.guard,
                monotonic=native.monotonic,sleep=native.sleep,source_lock=source_lock)

        @_private
        def _pending_owner(self,target,intent=None):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();_need(native.pid==int(manager.binding['processIdentity'].split(':')[0]))
            return NativePendingCommitOwner(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+PENDING_OWNER_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,intent=intent,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _web_dom(self,target):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();_need(native.pid==int(manager.binding['processIdentity'].split(':')[0]))
            return NativeWebDOMObservation(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+WEB_DOM_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _chat_view(self,target):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            native.guard();_need(native.pid==int(manager.binding['processIdentity'].split(':')[0]))
            return NativeChatView(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CHAT_VIEW_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,vr=True,monotonic=native.monotonic,sleep=native.sleep)

        def _chat_capture_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-capture-owner-')))

        @_private
        def _pico_lifecycle_input_once(self,target,operation,binding,*,before_input):
            from adapters.pico4.lifecycle_input import issue_once
            return issue_once(self,target,operation,binding,before_input=before_input)

        @_private
        def _chat_capture(self,target,run):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            owner=ChatCaptureOwner(self._chat_capture_store(target),manager.binding,native.guard)
            reader=NativeChatObservation(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CHAT_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
            native.guard();_need(native.pid==int(manager.binding['processIdentity'].split(':')[0]))
            return OwnedChatCapture(reader,owner,run)

        def _account_origin_store(self, target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','account-origin-owner-')))

        @_private
        def _account_origin(self, target):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            actual=native.read(0,require_account=True)
            source=NativeAccountOrigin(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+ACCOUNT_ORIGIN_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,actual['instance'],monotonic=native.monotonic,sleep=native.sleep)
            return OwnedAccountOrigin(source,self._account_origin_store(target),manager.binding)

        def _account_probe_store(self, target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','account-probe-owner-')))

        @_private
        def _account_probe(self, target):
            manager=self._scripts(target)
            native=self._native_feature_observer(target)
            owner=AccountProbeOwner(self._account_probe_store(target),manager.binding,native.guard)
            probe=NativeAccountProbe(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+ACCOUNT_PROBE_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,intent=owner.intent,monotonic=native.monotonic,sleep=native.sleep)
            return OwnedAccountProbe(probe,owner)

        @_private
        def _recorded_preview_evidence(self, target):
            native = self._native_feature_observer(target)
            return RecordedPreviewEvidence(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + RECORDED_PREVIEW_FILE, attempts=1),
                AndroidPreviewFiles(self.adb, target, 'org.overte.pico', native.guard),
                native.clock_ms, native.guard, native.pid)

        def _audio_preview_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'audio-preview-owner-')))

        @_private
        def _audio_preview(self, target, run, *, source_lock=None):
            # Internal cycle component only: no full-area capability, page
            # navigation, acoustic provider or journal retirement is inferred.
            from adapters.audio_preview import AudioPreview
            from adapters.token_audio_ui import TokenAudioUI
            from adapters.pico4.normal_audio import PicoAudioIO
            from adapters.script_journey.lock import ScriptSourceLock
            manager = self._scripts(target)
            native = self._native_feature_observer(target)
            native.guard()
            _need(native.pid == int(manager.binding['processIdentity'].split(':')[0]))
            store = self._audio_preview_store(target)
            lock = (ScriptSourceLock(store.path.with_suffix('.lock')) if source_lock is None
                else self._script_journey()._lock(target,source_lock))
            def guard():
                lock.assert_held()
                native.guard()
                manager.ui.io.navigation.io.bind_input()
            return AudioPreview(store, manager.binding, run,
                lambda intent: TokenAudioUI(PicoAudioIO(manager.ui.io), intent,
                    monotonic=native.monotonic, sleep=native.sleep), native,
                self._recorded_preview_evidence(target), guard, lock,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _script_roots_observer(self, target):
            from adapters.native_script_roots import NativeScriptRoots, FILE as ROOTS_FILE
            native = self._native_feature_observer(target)
            return NativeScriptRoots(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + ROOTS_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _script_execution_observer(self, target):
            native = self._native_feature_observer(target)
            return NativeScriptObservation(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + SCRIPT_EXECUTION_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid)

        @_private
        def discover(self):
            if not cleanup_only:
                self._candidate()
            return super().discover()

        @_private
        def describe(self, target):
            self._installation(target)
            description = super().describe(target)
            description['executionIdentity'] = self._installation(target)
            return description

        @_private
        def invoke(self, target, operation, values):
            _need(operation != 'app.upgrade')
            if operation == 'app.install':
                _need(type(values) is dict and set(values) == {'path'} and
                      isinstance(values['path'], str))
                path = Path(values['path'])
                _need(path.is_absolute() and not path.is_symlink() and
                      path.resolve() == args.apk.resolve() and file_digest(path) == frozen['apk'])
            # Bound suites begin with the candidate already provisioned: never
            # turn a foreign installation into an accepted initial describe.
            self._installation(target)
            try:
                if operation in graphics_journey.OPERATIONS:
                    _need(graphics_journey.configured(os.environ))
                    from feature_journeys.contract import arguments
                    arguments(operation,values)
                    flow=self._graphics_journey()._graphics_feature(target,values['runId'])
                    result=getattr(flow,operation.rsplit('.',1)[1])(values)
                elif operation in authentication_journey.OPERATIONS:
                    _need(authentication_journey.configured(os.environ))
                    from feature_journeys.contract import arguments
                    arguments(operation,values)
                    flow=self._authentication_journey()._authentication_feature(target,values['runId'])
                    result=getattr(flow,operation.rsplit('.',1)[1])(values)
                elif operation in script_journey.OPERATIONS:
                    _need(script_journey.configured(os.environ))
                    from feature_journeys.contract import arguments
                    arguments(operation, values)
                    flow = self._script_journey()._script_feature(target, values['runId'])
                    result = getattr(flow, operation.rsplit('.', 1)[1])(values)
                elif operation in NAVIGATION_OPERATIONS:
                    result = self._navigation(target).invoke(operation, values)
                elif operation in SNAPSHOT_OPERATIONS:
                    _need(not self._snapshot_originals_owned(target))
                    result = self._snapshot(target).invoke(operation, values)
                elif operation in SCRIPT_OPERATIONS:
                    result = self._scripts(target).invoke(operation, values)
                elif operation in CREATE_OPERATIONS:
                    _need(create_management.configuration(os.environ) is not None)
                    result = self._create_management(target).invoke(operation, values)
                else:
                    result = super().invoke(target, operation, values)
            finally:
                self._installation(target)
            return result

        @_private
        def cleanup(self, target):
            # Base stop remains available, but cannot retire this private
            # owner or its original normal preference/UI journals.
            snapshot_error=False
            try:
                snapshot_error=self.pico_configuration is not None and self._snapshot_originals_owned(target)
            except Exception:snapshot_error=True
            feature_error = False
            create_error = False
            try:
                if self.pico_configuration is not None and self._create_management(target).owned():
                    if cleanup_only:
                        self._recover_cleanup_candidate()
                    self._create_management(target).cleanup()
            except Exception:
                create_error = True
            try:
                if self.pico_configuration is not None and self._script_journey().existing_state_path(target) is not None:
                    journey = self._script_journey()
                    owner = journey.script_feature_store(target).read()
                    retirement = journey.script_retirement_store(target).read()
                    if owner is not None or retirement is not None:
                        if cleanup_only: self._recover_cleanup_candidate()
                        record = owner if owner is not None else retirement
                        # Internal cleanup has no fixture/actor credential and
                        # cannot advance a run. Finalization independently proves
                        # both roles' originals and actual resource absence.
                        from adapters.script_journey.feature import ScriptFeature, ScriptRetirementSource
                        flow = ScriptFeature(journey, target,
                            ScriptRetirementSource(record['runId'], record['fixtureUrl']))
                        flow.finalize()
                    else:
                        # An interrupted reservation without its owner cannot
                        # disappear behind ordinary application teardown.
                        path = journey.state_path(target).parent
                        _need(not any(p.name != 'script-sources.lock' for p in path.iterdir()))
            except Exception:
                feature_error = True
            try:
                if self.pico_configuration is not None and self._authentication_journey().existing_state_path(target) is not None:
                    journey=self._authentication_journey()
                    owner=journey.authentication_feature_store(target).read()
                    retirement=journey.authentication_retirement_store(target).read()
                    if owner is not None or retirement is not None:
                        if cleanup_only:self._recover_cleanup_candidate()
                        record=owner if owner is not None else retirement
                        # The existing adapter-only credential authorizes fresh
                        # retired-provider reads; it cannot register/activate runs.
                        journey._authentication_feature(target,record['runId']).finalize()
                    else:
                        path=journey.state_path(target).parent
                        _need(not any(p.name!='authentication-sources.lock' for p in path.iterdir()))
            except Exception:
                feature_error=True
            try:
                if self.pico_configuration is not None and self._graphics_journey().existing_state_path(target) is not None:
                    journey=self._graphics_journey()
                    owner=journey.graphics_feature_store(target).read()
                    retirement=journey.graphics_retirement_store(target).read()
                    if owner is not None or retirement is not None:
                        if cleanup_only:self._recover_cleanup_candidate()
                        record=owner if owner is not None else retirement
                        journey._graphics_cleanup_feature(target,record['runId']).finalize()
                    else:
                        path=journey.state_path(target).parent
                        _need(not any(p.name!='script-sources.lock' for p in path.iterdir()))
            except Exception:
                feature_error=True
            # Release only known E2E source leases before base force-stop, even
            # when full independent retirement could not complete. The feature
            # error and its original journals remain unresolved in that case.
            if self.pico_configuration is not None and self._authentication_journey().existing_state_path(target) is not None:
                journey=self._authentication_journey()
                for role in ('primary','actor'):
                    try:
                        if journey.account_probe_store(target,role=role).read() is not None:
                            if cleanup_only:self._recover_cleanup_candidate()
                            journey._account_probe(target,read_only=True,role=role).release()
                    except Exception:feature_error=True
                try:
                    if journey.account_origin_store(target).read() is not None:
                        if cleanup_only:self._recover_cleanup_candidate()
                        journey._account_origin(target,read_only=True).release()
                except Exception:feature_error=True
            audio_error = False
            try:
                if self.pico_configuration is not None:
                    owned = self._audio_preview_store(target).read()
                    if owned is not None:
                        # Drain known native work, but retained terminal history
                        # still needs the missing independent restart/role join.
                        # Base force-stop cannot retire that original journal.
                        audio_error = True
                        if not self._audio_capture_owned(target):
                            if cleanup_only: self._recover_cleanup_candidate()
                            self._audio_preview(target, owned['runId']).release_native()
            except Exception:
                audio_error = True
            chat_error=False
            try:
                if self.pico_configuration is not None:
                    owned=self._chat_capture_store(target).read()
                    if owned is not None:
                        if cleanup_only:self._recover_cleanup_candidate()
                        self._chat_capture(target,owned['runId']).retire()
            except Exception:chat_error=True
            probe_error=False
            try:
                if self.pico_configuration is not None and self._account_probe_store(target).read() is not None:
                    if cleanup_only:self._recover_cleanup_candidate()
                    self._account_probe(target).release()
            except Exception:probe_error=True
            origin_error=False
            try:
                if self.pico_configuration is not None and self._account_origin_store(target).read() is not None:
                    if cleanup_only:self._recover_cleanup_candidate()
                    self._account_origin(target).release()
            except Exception:origin_error=True
            script_error = False
            try:
                if self.pico_configuration is not None:
                    path, _ui = self._script_paths(target)
                    owned = PrivateFeatureState(path).read()
                    if owned is not None:
                        # Candidate revalidation is needed only to deliver
                        # normal source cleanup, never to reach base teardown.
                        if cleanup_only:
                            self._recover_cleanup_candidate()
                        scripts = self._scripts(target)
                        if owned['loadAttempted']:
                            scripts.invoke('scripts.manager.open', {})
                            scripts.invoke('scripts.stop', {'url': owned['source']})
                        scripts.invoke('scripts.manager.close', {})
            except Exception:
                script_error = True
            # Keep original teardown available after every source/candidate
            # failure. A stopped app cannot retire unresolved saved scripts.
            result = super().cleanup(target)
            # The canonical teardown has now confirmed force-stop. Retire the
            # owned host intent even when a partial input invalidated receipts.
            if self.pico_configuration is not None:
                discard_stopped_state(self._navigation_path(target))
                if not snapshot_error:
                    for path in self._snapshot_paths(target):
                        discard_stopped_state(path)
                state, ui = self._script_paths(target)
                discard_stopped_state(ui)
                _need(not snapshot_error and not audio_error and not create_error and not self._create_management(target).owned()
                      and not feature_error and not script_error and not probe_error and not origin_error and not chat_error and PrivateFeatureState(state).read() is None
                      and self._lifecycle_back_store(target).read() is None
                      and (self._lifecycle_world_store(target,create=False) is None or self._lifecycle_world_store(target,create=False).read() is None)
                      and not self._lifecycle_background_owned(target)
                      and (self._audio_page_store(target,create=False) is None or self._audio_page_store(target,create=False).read() is None)
                      and not self._audio_capture_owned(target)
                      and self._script_restart_inputs_store(target).read() is None
                      and self._script_restart_store(target).read() is None
                      and self._script_files_store(target).read() is None and self._account_probe_store(target).read() is None
                      and self._account_origin_store(target).read() is None and self._chat_capture_store(target).read() is None)
            else:
                _need(not audio_error and not create_error and not feature_error and not script_error and not probe_error and not origin_error and not chat_error)
            return result

    return PicoBoundAdapter(args.kind)
