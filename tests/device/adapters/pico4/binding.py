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
from adapters.native_account_origin import NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE
from adapters.recorded_preview_evidence import (RecordedPreviewEvidence, AndroidPreviewFiles,
    FILE as RECORDED_PREVIEW_FILE)
from adapters.native_script_observation import NativeScriptObservation, FILE as SCRIPT_EXECUTION_FILE
from adapters.pico4 import normal_scripts
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, FILE as SCRIPT_FIXTURE_FILE
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
            return sorted(set(values))

        def _script_paths(self, target):
            _need(self.pico_configuration is not None)
            key = hashlib.sha256(('org.overte.pico\0' + target).encode()).hexdigest()[:32]
            directory = self.pico_configuration[1]
            return directory / ('normal-script-state-' + key + '.json'), directory / ('normal-script-ui-' + key + '.json')

        def _scripts(self, target):
            scene = normal_scripts.configuration(os.environ)
            _need(scene is not None and self.pico_configuration is not None
                  and candidate['e2e_input_layer'] is True)
            identity = self.require_controlled_debug_identity(target)
            installed = self._installation(target)
            state, ui = self._script_paths(target)
            return normal_scripts.flow(self, target, scene, installed, identity, state, ui,
                lambda operation: super(PicoBoundAdapter, self).invoke(target, operation, {}))

        def _script_files_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'normal-script-files-')))

        @_private
        def _script_files(self, target):
            manager = self._scripts(target)
            native = self._native_feature_observer(target)
            files = NativeScriptFiles(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + SCRIPT_FIXTURE_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid)
            return OwnedScriptFiles(files, self._script_files_store(target), manager.binding)

        def _graphics_controls(self, target, intent):
            from adapters.token_graphics_ui import TokenGraphicsUI
            from adapters.pico4.normal_graphics import PicoGraphicsIO
            manager = self._scripts(target)
            return TokenGraphicsUI(PicoGraphicsIO(manager.ui.io),intent)

        def _world_render_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'world-render-owner-')))

        @_private
        def _world_render_capture(self, target):
            # Version 1 refuses real stereo captures. Connecting transport must
            # never substitute a desktop image or guess one eye for Pico.
            manager = self._scripts(target)
            native = self._native_feature_observer(target)
            owner = WorldRenderOwner(self._world_render_store(target), manager.binding, native.guard)
            receipts = AndroidWorldRenderReceipts(self.adb, target, 'org.overte.pico', native.guard)
            options = dict(monotonic=native.monotonic, sleep=native.sleep)
            storage = NativeWorldRenderStorage(native.send, receipts.read, native.clock_ms, native.guard,
                native.pid, receipt_intent=owner.receipt_intent, **options)
            capture = NativeWorldRenderCapture(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + WORLD_RENDER_FILE, attempts=1),
                storage, native.clock_ms, native.guard, native.pid, intent=owner.intent, **options)
            return OwnedWorldRenderCapture(capture, storage, owner, receipts)

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
            # Reuse the original candidate/OpenXR/normal Script UI context.
            # Persistent file ownership and the full v2 effect join come later.
            manager = self._scripts(target)
            return TokenScriptFilePicker(manager.ui.io, directory)

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
                if operation in NAVIGATION_OPERATIONS:
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
                _need(not script_error and not probe_error and not origin_error and not chat_error and PrivateFeatureState(state).read() is None
                      and self._script_files_store(target).read() is None and self._account_probe_store(target).read() is None
                      and self._account_origin_store(target).read() is None and self._chat_capture_store(target).read() is None)
            else:
                _need(not script_error and not probe_error and not origin_error and not chat_error)
            return result

    return PicoBoundAdapter(args.kind)
