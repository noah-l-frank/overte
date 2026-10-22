"""Pico extension of the canonical SH-004 Android adapter; no device auto-run."""
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
import importlib.util
import hashlib
import os
from pathlib import Path, PurePosixPath
import re

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
            manager=self._scripts(target)
            return TokenCreateUI(PicoCreateIO(manager.ui.io),intent)

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
                path,run,manager.binding,scene_url,guard,directory=directory,monotonic=native.monotonic,sleep=native.sleep)

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
            manager = self._scripts(target)
            return NavigationOrigin(PicoNavigationOriginIO(manager.ui.io), self._navigation_environment(target),
                path, run, manager.binding, guard)

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
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        def _chat_capture_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-capture-owner-')))

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
                    result = self._snapshot(target).invoke(operation, values)
                elif operation in SCRIPT_OPERATIONS:
                    result = self._scripts(target).invoke(operation, values)
                else:
                    result = super().invoke(target, operation, values)
            finally:
                self._installation(target)
            return result

        @_private
        def cleanup(self, target):
            feature_error = False
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
                for path in self._snapshot_paths(target):
                    discard_stopped_state(path)
                state, ui = self._script_paths(target)
                discard_stopped_state(ui)
                _need(not feature_error and not script_error and not probe_error and not origin_error and not chat_error and PrivateFeatureState(state).read() is None
                      and self._script_restart_inputs_store(target).read() is None
                      and self._script_restart_store(target).read() is None
                      and self._script_files_store(target).read() is None and self._account_probe_store(target).read() is None
                      and self._account_origin_store(target).read() is None and self._chat_capture_store(target).read() is None)
            else:
                _need(not feature_error and not script_error and not probe_error and not origin_error and not chat_error)
            return result

    return PicoBoundAdapter(args.kind)
