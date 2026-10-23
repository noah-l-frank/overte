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


def _candidate_arguments(args):
    return (tuple(sorted((key,type(value).__name__,str(value)) for key,value in vars(args).items())),
        dict(os.environ),os.getcwd(),str(verifier.WEB_ROOT),str(verifier.PICO_MANIFEST),
        id(verifier.verify_candidate),id(verifier.decoder_inputs))


def _candidate_seal(args,frozen,candidate,admission):
    """Freeze only an original complete verifier result, never partial evidence."""
    from adapters.pico4.candidate_read_seal import CandidateReadSeal,CandidateReadSealUnavailable,bounded_decoder_tree
    from schema.terminal_evidence import read_document,relative_file
    network=candidate.get('network_capability')
    if not isinstance(network,dict) or not all(isinstance(network.get(key),dict)
            for key in ('source_inputs_sha256','decoder_inputs_sha256')):
        # Explicit reduced component seams retain the original full verifier
        # on every call. They cannot acquire this optimization's qualification.
        return None
    _need(_candidate_arguments(args)==admission)
    evidence,_=read_document(args.build_evidence)
    files={str(Path(getattr(args,name)).absolute()):digest for name,digest in frozen.items() if not name.startswith('build_receipt:')}
    for entry in evidence['receipts']:
        path=relative_file(args.build_evidence.parent,entry['path'])
        files[str(path.absolute())]=frozen['build_receipt:'+entry['tier']]
    for key in ('source_inputs_sha256','decoder_inputs_sha256'):
        for path,digest in network[key].items():
            name=str(Path(path).absolute());_need(name not in files or files[name]==digest);files[name]=digest
    def metadata():
        # Preserve argument TYPES as well as values (True is not integer 1).
        return _candidate_arguments(args)
    expected_metadata=admission
    decoder_records=[];directories={};decoder_inventory=set()
    for name in ('apkanalyzer','aapt2'):
        path=Path(verifier.resolve_tool(getattr(args,name),name)).resolve(strict=True)
        values={str(path)};sdk=path.parent.parent
        classpath=path.name=='apkanalyzer' and (sdk/'lib/apkanalyzer-classpath.jar').is_file()
        java=None
        if classpath:
            jars,tree=bounded_decoder_tree(sdk/'lib');directories.update(tree)
            values.update(jars);values.add(str(sdk/'source.properties'))
            java=(Path(os.environ['JAVA_HOME'])/'bin/java' if os.environ.get('JAVA_HOME')
                else Path(verifier.resolve_tool(None,'java'))).resolve(strict=True)
            values.update(str(item) for item in (java,java.parent.parent/'release',java.parent.parent/'lib/modules',java.parent.parent/'lib/server/libjvm.so'))
        decoder_inventory.update(values);decoder_records.append((name,path,classpath,java))
    _need(decoder_inventory==set(network['decoder_inputs_sha256']))
    def inventory():
        _need(metadata()==expected_metadata)
        source={str(path) for path in (verifier.WEB_ROOT/'network_policy.py',verifier.WEB_ROOT/'network-capability.json',
            verifier.WEB_ROOT/'res/xml/overte_embedded_web_network_security_config.xml',verifier.PICO_MANIFEST)}
        _need(source==set(network['source_inputs_sha256']))
        for name,original,classpath,java in decoder_records:
            path=Path(verifier.resolve_tool(getattr(args,name),name)).resolve(strict=True)
            _need(path==original and (path.name=='apkanalyzer' and (path.parent.parent/'lib/apkanalyzer-classpath.jar').is_file())==classpath)
            if classpath:
                current=(Path(os.environ['JAVA_HOME'])/'bin/java' if os.environ.get('JAVA_HOME')
                    else Path(verifier.resolve_tool(None,'java'))).resolve(strict=True)
                _need(current==java)
        # Held original directory identities reject every added/removed entry.
        # No recursive SDK/JVM walk occurs inside a native source query.
        # Also freeze actual aapt/apksigner resolution, including PATH lookup.
        for name in ('aapt','apksigner'):
            path=Path(verifier.resolve_tool(getattr(args,name),name))
            _need(path.resolve(strict=True)==Path(getattr(args,name)).resolve(strict=True))
        return dict(files)
    try:return CandidateReadSeal(inventory,metadata,candidate,directories=directories)
    except CandidateReadSealUnavailable:return None


@_private
def create_adapter(args, base_class):
    _need(args.kind == 'pico')
    # Cleanup must still reach the original native cleanup if candidate files
    # disappeared or became invalid. It never emits an executionIdentity.
    cleanup_only = args.action == 'cleanup'
    cleanup_candidate = False
    frozen = candidate = seal = None
    if not cleanup_only:
        args.require_identity = True
        admission=_candidate_arguments(args)
        frozen = _inputs(args)
        _need(_candidate_arguments(args)==admission)
        candidate = verifier.verify_candidate(args)
        _need(_inputs(args) == frozen and _candidate_arguments(args)==admission)
        _need(candidate['package'] == 'org.overte.pico' and
              candidate['identity']['artifactSha256'] == frozen['apk'])
        seal=_candidate_seal(args,frozen,candidate,admission)

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
            if seal is not None:return seal.check()
            _need(_inputs(args) == frozen)
            current = verifier.verify_candidate(args)
            _need(current == candidate and _inputs(args) == frozen)
            return current

        def _recover_cleanup_candidate(self):
            nonlocal frozen, candidate, cleanup_candidate, seal
            _need(cleanup_only)
            args.require_identity = True
            admission=_candidate_arguments(args)
            original = _inputs(args)
            _need(_candidate_arguments(args)==admission)
            verified = verifier.verify_candidate(args)
            _need(_candidate_arguments(args)==admission and _inputs(args) == original and verified['package'] == 'org.overte.pico'
                  and verified['identity']['artifactSha256'] == original['apk'])
            frozen, candidate, cleanup_candidate = original, verified, True
            seal=_candidate_seal(args,frozen,candidate,admission)

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
            _need(seal.check()==candidate if seal is not None else _inputs(args)==frozen)
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
            foreign.extend(self._emote_world_render_store(target,value) for value in ('primary','actor'))
            foreign.extend(self._browser_world_render_store(target,value) for value in ('primary','actor'))
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

        def _bind_create_transport(self, ui, before_send):
            if before_send is not None:
                _need(callable(before_send))
                navigation=ui.io.navigation
                navigation.io.bind_before_send(lambda command:before_send(command,navigation))
            return ui

        @_private
        def _assets_uploads(self,target,*,source_lock,intent=None):
            from adapters.pico4.assets_uploads import PicoAssetsUploads,FILE
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            native=self._native_feature_observer(target)
            def guard():lock.assert_held();native.guard()
            return PicoAssetsUploads(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,guard,native.pid,intent=intent,monotonic=native.monotonic)

        @_private
        def _assets_source(self,target,*,source_lock,download=False,resolve=False,intent=None):
            from adapters.pico4.assets_source import PicoAssetsSource,FILE,DOWNLOAD_FILE,RESOLVE_FILE
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            native=self._native_feature_observer(target)
            def guard():lock.assert_held();native.guard()
            name=DOWNLOAD_FILE if download else RESOLVE_FILE if resolve else FILE
            return PicoAssetsSource(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+name,attempts=1),
                native.clock_ms,guard,native.pid,download=download,resolve=resolve,intent=intent,monotonic=native.monotonic)

        @_private
        def _assets_read_retirement(self,target,*,source_lock):
            from adapters.pico4.assets_read_retirement import AssetsReadRetirement,FILE
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            native=self._native_feature_observer(target)
            def guard():lock.assert_held();native.guard()
            return AssetsReadRetirement(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,guard,native.pid,monotonic=native.monotonic)

        def _assets_cancel_store(self,target,stage=1):
            _need(type(stage) is int and 1<=stage<=6)
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','normal-assets-cancel-stage'+str(stage)+'-')))

        @_private
        def _assets_cancel_owner(self,target,run,fixture_url,phase,*,source_lock,stage=1):
            from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            store=self._assets_cancel_store(target,stage);original=store.read()
            ticket=original['openTicket'] if original is not None else phase.read()['ticket']
            files=self._assets_file_owner(target,run,ticket,fixture_url,stage=stage)
            def guard():lock.assert_held();native.guard()
            owner=OwnedAssetsCancel(store,binding,run,fixture_url,files,
                self._assets_source(target,source_lock=lock),self._assets_uploads(target,source_lock=lock),
                ui.io.capture,lambda intent,**options:self._assets_controls(target,intent,**options),phase,guard,native.clock_ms,
                monotonic=native.monotonic)
            return owner

        def _assets_file_store(self,target,stage=None):
            _need(stage is None or type(stage) is int and 1<=stage<=6)
            state,_ui=self._script_paths(target)
            suffix='' if stage is None else '-stage'+str(stage)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','normal-assets-files'+suffix+'-')))

        def _assets_files_owned(self,target):
            # Native file absence alone cannot retire the whole UI/backend
            # owner. Keep even retired file transcripts until that final join.
            if any(self._assets_cancel_store(target,stage).read() is not None for stage in range(1,7)):return True
            for stage in (None,1,2,3,4,5,6):
                value=self._assets_file_store(target,stage).read()
                if value is not None:return True
            return False

        @_private
        def _assets_file_owner(self,target,run,ticket,fixture_url,*,stage=None):
            from adapters.pico4.assets_files import NativeAssetsFiles,FILE
            from adapters.pico4.assets_file_owner import OwnedAssetsFiles
            _ui,_observe,binding=self._script_runtime(target)
            native=self._native_feature_observer(target)
            files=NativeAssetsFiles(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,stage=stage)
            return OwnedAssetsFiles(files,self._assets_file_store(target,stage),binding,run,ticket,fixture_url)

        def _assets_controls(self,target,intent,*,before_send=None,audit=None):
            from adapters.token_assets_ui import TokenAssetsUI
            from adapters.pico4.assets_ui import PicoAssetsIO
            ui,_observe,_binding=self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return TokenAssetsUI(PicoAssetsIO(ui.io),intent,monotonic=ui.monotonic,sleep=ui.sleep,audit=audit)

        def _avatar_people_controls(self,target,intent,*,before_send=None):
            from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI,PicoAvatarPeopleIO
            ui,_observe,_binding=self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return TokenAvatarPeopleUI(PicoAvatarPeopleIO(ui.io),intent,monotonic=ui.monotonic,sleep=ui.sleep)

        def _create_controls(self, target, intent, *, before_send=None):
            from adapters.token_create_ui import TokenCreateUI
            from adapters.pico4.normal_create import PicoCreateIO
            ui, _observe, _binding = self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return TokenCreateUI(PicoCreateIO(ui.io),intent)

        def _create_extra_controls(self,target,intent,*,before_send=None):
            from adapters.pico4.create_extra_ui import TokenCreateExtraUI,PicoCreateExtraIO
            ui,_observe,_binding=self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return TokenCreateExtraUI(PicoCreateExtraIO(ui.io),intent,monotonic=ui.monotonic,sleep=ui.sleep)

        def _create_voxel_controls(self,target,intent,*,before_send=None):
            from adapters.pico4.create_voxel_ui import TokenCreateVoxelUI,PicoCreateVoxelIO
            ui,_observe,_binding=self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return TokenCreateVoxelUI(PicoCreateVoxelIO(ui.io),intent,monotonic=ui.monotonic,sleep=ui.sleep)

        def _create_management(self, target):
            return create_management.PicoCreateManagement(self, target)

        def _emote_controls(self, target, intent, receipt=None, *, before_send=None):
            from adapters.token_emote_ui import TokenEmoteUI
            from adapters.pico4.normal_emote import PicoEmoteIO
            ui, _observe, _binding = self._script_runtime(target)
            return TokenEmoteUI(PicoEmoteIO(ui.io,before_send=before_send), intent, receipt=receipt)

        def _emote_source_store(self, target, role):
            _need(role in ('primary', 'actor'))
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'emote-' + role + '-sources-')))

        @_private
        def _view_menu_controls(self,target,intent):
            from adapters.pico4.normal_view_menu import PicoViewMenu
            ui,_observe,_binding=self._script_runtime(target)
            return PicoViewMenu(ui.io,intent,monotonic=ui.monotonic,sleep=ui.sleep)

        def _emote_view_store(self,target):
            source=self._emote_source_store(target,'primary')
            return PrivateFeatureState(source.path.with_name(source.path.stem+'-view.json'))

        def _emote_scene_store(self,target):
            source=self._emote_source_store(target,'primary')
            return PrivateFeatureState(source.path.with_name(source.path.stem+'-scene.json'))

        @_private
        def _avatar_urls(self,target,run,*,source_lock=None):
            from adapters.feature_fixture_access import client
            from adapters.pico4.avatar_urls import PicoAvatarUrls
            from feature_journeys.phase_fixture import PhaseFixtureReader
            _need(bool(os.environ.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG')) and self.pico_configuration is not None)
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            phase=PhaseFixtureReader(client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL')),run,'avatar-people')
            ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
            store=PrivateFeatureState(self.pico_configuration[1]/('avatar-urls-owner-'+key+'-'+run+'.json'))
            return PicoAvatarUrls(store,binding,phase,lock,lambda:self._avatar_state_observer(target),ui.io.capture,
                lambda intent,before_send:self._avatar_people_controls(target,intent,before_send=before_send),native.guard,
                preferences=lambda:self._avatar_preferences_observer(target),
                favorites=lambda:self._avatar_favorites(target,run,source_lock=lock),
                monotonic=native.monotonic,sleep=native.sleep)

        def _avatar_urls_owned(self,target):
            if self.pico_configuration is None:return False
            key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32];parent=self.pico_configuration[1]
            for path in parent.glob('avatar-urls-owner-'+key+'-*.json'):
                _need(re.fullmatch('avatar-urls-owner-'+key+'-[0-9a-f]{32}\\.json',path.name))
                if PrivateFeatureState(path).read() is not None:return True
            # A failed root CAS can leave an already durable immutable original
            # leaf. It is still owned even if the first root was never saved.
            for path in parent.glob('avatar-urls-frame-'+key+'-*.json'):
                _need(re.fullmatch('avatar-urls-frame-'+key+'-[0-9a-f]{32}-[0-9a-f]{32}\\.json',path.name))
                if PrivateFeatureState(path).read() is not None:return True
            return False

        @_private
        def _avatar_favorites(self,target,run,*,source_lock=None):
            from adapters.feature_fixture_access import client
            from adapters.pico4.avatar_favorites import PicoAvatarFavorites
            from feature_journeys.phase_fixture import PhaseFixtureReader
            _need(bool(os.environ.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG')) and self.pico_configuration is not None)
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            phase=PhaseFixtureReader(client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL')),run,'avatar-people')
            ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
            store=PrivateFeatureState(self.pico_configuration[1]/('avatar-favorites-owner-'+key+'-'+run+'.json'))
            sources=dict(native=lambda:self._avatar_state_observer(target),preferences=lambda:self._avatar_preferences_observer(target),
                bookmarks=lambda:self._avatar_bookmarks_observer(target),loads=lambda:self._avatar_bookmark_loads_observer(target))
            return PicoAvatarFavorites(store,binding,phase,lock,sources,ui.io.capture,
                lambda intent,before_send:self._avatar_people_controls(target,intent,before_send=before_send),native.guard,
                lambda:self._avatar_urls(target,run,source_lock=lock),monotonic=native.monotonic,sleep=native.sleep)

        def _avatar_favorites_owned(self,target):
            if self.pico_configuration is None:return False
            key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32];parent=self.pico_configuration[1]
            for prefix,suffix in (('avatar-favorites-owner-',r'[0-9a-f]{32}'),('avatar-favorites-frame-',r'[0-9a-f]{32}-[0-9a-f]{32}')):
                for path in parent.glob(prefix+key+'-*.json'):
                    _need(re.fullmatch(prefix+key+'-'+suffix+r'\.json',path.name))
                    if PrivateFeatureState(path).read() is not None:return True
            return False

        @_private
        def _avatar_state_observer(self,target):
            from adapters.pico4.avatar_state import NativePicoAvatarState,FILE
            native=self._native_feature_observer(target)
            return NativePicoAvatarState(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _avatar_preferences_observer(self,target):
            from adapters.pico4.avatar_preferences import NativePicoAvatarPreferences,FILE
            native=self._native_feature_observer(target)
            return NativePicoAvatarPreferences(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _avatar_bookmarks_observer(self,target):
            from adapters.pico4.avatar_bookmarks import NativePicoAvatarBookmarks,FILE
            native=self._native_feature_observer(target)
            return NativePicoAvatarBookmarks(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _avatar_bookmark_loads_observer(self,target):
            from adapters.pico4.avatar_bookmark_loads import NativePicoAvatarBookmarkLoads,FILE
            native=self._native_feature_observer(target)
            return NativePicoAvatarBookmarkLoads(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _emote_scene_observer(self,target):
            from adapters.pico4.emote_scene_source import NativePicoEmoteScene,FILE
            native=self._native_feature_observer(target)
            return NativePicoEmoteScene(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _emote_scene(self,target,phase,source_lock):
            from adapters.pico4.emote_scene_owner import PicoEmoteScene
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            _ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            native.guard();_need(native.pid==int(binding['processIdentity'].split(':')[0]))
            return PicoEmoteScene(self._emote_scene_store(target),binding,phase,lock,
                lambda:self._emote_scene_observer(target),lambda:self._avatar_render_observer(target),native.guard,
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _emote_view(self,target,phase,source_lock):
            from adapters.pico4.emote_view import PicoEmoteView
            from adapters.pico4.tablet_home import bind_home
            journey=self._script_journey();lock=journey._lock(target,source_lock);lock.assert_held()
            ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            native.guard();_need(native.pid==int(binding['processIdentity'].split(':')[0]))
            return PicoEmoteView(self._emote_view_store(target),binding,phase,lock,lambda:ui.io,
                lambda:self._avatar_render_observer(target),native.guard,lambda:journey.existing_input_session(target),
                lambda:bind_home(self,target,native),lambda:self.pico_input_session(target),
                monotonic=native.monotonic,sleep=native.sleep)

        def _emote_world_render_store(self, target, role):
            source=self._emote_source_store(target,role)
            return PrivateFeatureState(source.path.with_name(source.path.stem+'-world-render.json'))

        def _emote_image_journals(self, target):
            sources=[self._emote_source_store(target,role).path for role in ('primary','actor')]
            root=sources[0].parent
            if not root.exists():return False
            PrivateFeatureState(root/'emote-image-boundary.json')._parent()
            prefixes=tuple(path.stem+'-image-' for path in sources)
            for index,path in enumerate(root.iterdir()):
                _need(index<4096)
                if path.name.startswith(prefixes):return True
            return False

        @_private
        def _emote_world_render_capture(self, target, source):
            from adapters.pico4.emote_sources import PicoEmoteSources
            from adapters.pico4.graphics_binding import PicoGraphicsBinding,SerializedWorldCapture
            from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles,INVENTORY_FILE
            _need(isinstance(source,PicoEmoteSources) and source.role in ('primary','actor')
                and source.store.path==self._emote_source_store(target,source.role).path)
            lock=self._script_journey()._lock(target,source.lock);lock.assert_held()
            _ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            _need(binding==source.binding and native.pid==source.pid)
            role=source.role;facade=PicoGraphicsBinding(self)
            foreign=[self._emote_world_render_store(target,'actor' if role=='primary' else 'primary'),self._world_render_store(target)]
            foreign.extend(facade.world_render_store(target,role=value) for value in ('primary','actor'))
            foreign.extend(self._browser_world_render_store(target,value) for value in ('primary','actor'))
            def world_guard():
                lock.assert_held();native.guard();_need(source.guard() is not False and all(store.read() is None for store in foreign));return True
            owner=WorldRenderOwner(self._emote_world_render_store(target,role),binding,world_guard,role=role)
            files=AndroidWorldRenderReceipts(self.adb,target,'org.overte.pico',world_guard)
            options=dict(monotonic=native.monotonic,sleep=native.sleep)
            storage=NativeWorldRenderStorage(native.send,files.read,native.clock_ms,world_guard,native.pid,receipt_intent=owner.receipt_intent,**options)
            inventory=NativeWorldReceiptInventory(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+INVENTORY_FILE,attempts=1),
                native.clock_ms,world_guard,native.pid,owner.owned,lambda:storage.instance,**options)
            receipts=NativeWorldReceiptBatchFiles(files,inventory)
            capture=NativeWorldRenderCapture(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+WORLD_RENDER_FILE,attempts=1),
                storage,native.clock_ms,world_guard,native.pid,intent=owner.intent,stereo=True,require_cameras=True,**options)
            return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=lock)

        @_private
        def _emote_capture(self, target, source, index, policy):
            from adapters.pico4.emote_capture import PicoEmoteCapture
            from adapters.pico4.emote_sources import PicoEmoteSources
            _need(isinstance(source,PicoEmoteSources) and source.store.path==self._emote_source_store(target,source.role).path)
            self._script_journey()._lock(target,source.lock).assert_held()
            return PicoEmoteCapture(source,index,policy,lambda:self._emote_world_render_capture(target,source),
                lambda:self._avatar_render_observer(target),lambda:self._emote_model_draws_observer(target),monotonic=source.monotonic)

        def _emote_input_store(self, target):
            state, _ui = self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-', 'emote-inputs-')))

        @_private
        def _emote_inputs(self, target, source):
            from adapters.pico4.emote_inputs import PicoEmoteInputs
            from adapters.pico4.emote_sources import PicoEmoteSources
            _need(isinstance(source, PicoEmoteSources) and source.role == 'primary'
                and source.store.path == self._emote_source_store(target, 'primary').path)
            source.lock.assert_held(); source.guard()
            ui, _observe, binding = self._script_runtime(target)
            _need(binding == source.binding)
            return PicoEmoteInputs(source, self._emote_input_store(target),
                lambda intent, receipt, before_send: self._emote_controls(target, intent, receipt=receipt,before_send=before_send), ui.io,
                lambda: self._script_journey().existing_input_session(target),controller=lambda:self.pico_input_session(target))

        def _emote_background_store(self, target):
            source = self._emote_source_store(target, 'primary')
            return PrivateFeatureState(source.path.with_name(source.path.stem + '-background.json'))

        @_private
        def _emote_background(self, target, phase, artifact_root, source_lock):
            from adapters.pico4.emote_background import PicoEmoteBackground
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.script_journey.lock import ScriptSourceLock
            _need(isinstance(source_lock, ScriptSourceLock)
                and source_lock.path == self._script_journey().state_path(target).with_name('script-sources.lock'))
            source_lock.assert_held()
            lifecycle = PicoGraphicsBinding(self)
            return PicoEmoteBackground(phase, source_lock, self._emote_source_store(target, 'primary'),
                self._emote_input_store(target),
                lambda: self._emote_sources(target, phase, 'primary', artifact_root, source_lock),
                lifecycle, target, lambda: lifecycle.existing_input_session(target), artifact_root=artifact_root)

        def _emote_lifetime_store(self, target, role):
            source = self._emote_source_store(target, role)
            return PrivateFeatureState(source.path.with_name(source.path.stem + '-lifetime.json'))

        @_private
        def _emote_lifetime(self, target, source):
            from adapters.pico4.emote_lifetime import PicoEmoteLifetime
            from adapters.pico4.emote_sources import PicoEmoteSources
            _need(isinstance(source, PicoEmoteSources)
                and source.store.path == self._emote_source_store(target, source.role).path)
            source.lock.assert_held(); source.guard()
            _ui, _observe, binding = self._script_runtime(target)
            _need(binding == source.binding)
            return PicoEmoteLifetime(source, lambda: self._script_work(target))

        @_private
        def _script_object_lifetimes(self,target,*,source_lock):
            from adapters.native_script_object_lifetimes import NativeScriptObjectLifetimes,FILE,command
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            native=self._native_feature_observer(target)
            def guard():
                lock.assert_held();return native.guard()
            def send(value):
                command(value);guard();native.send(value)
            return NativeScriptObjectLifetimes(send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

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
        def _emote_effects(self, target, inputs, *, current_source=None):
            from adapters.pico4.emote_effects import PicoEmoteEffects
            from adapters.pico4.emote_inputs import PicoEmoteInputs
            _need(isinstance(inputs, PicoEmoteInputs)
                and inputs.store.path == self._emote_input_store(target).path
                and inputs.source.store.path == self._emote_source_store(target, 'primary').path)
            source = inputs.source if current_source is None else current_source
            _need(source.store.path == self._emote_source_store(target, source.role).path)
            source.lock.assert_held(); source.guard()
            _ui, _observe, binding = self._script_runtime(target)
            _need(binding == source.binding)
            return PicoEmoteEffects(inputs, current_source=source)

        @_private
        def _emote_sources(self, target, phase, role, artifact_root, source_lock):
            from adapters.pico4.emote_sources import PicoEmoteSources
            from adapters.script_journey.lock import ScriptSourceLock
            _need(isinstance(source_lock, ScriptSourceLock)
                and source_lock.path == self._script_journey().state_path(target).with_name('script-sources.lock'))
            source_lock.assert_held()
            ui, _observe, binding = self._script_runtime(target)
            native = self._native_feature_observer(target)
            _need(native.pid == int(binding['processIdentity'].split(':')[0]))
            def readers():
                source_lock.assert_held(); native.guard()
                return (self._script_roots_observer(target), self._script_execution_observer(target),
                    self._animation_inventory_observer(target), self._native_feature_observer(target), ui.io)
            return PicoEmoteSources(self._emote_source_store(target, role), binding, phase, role,
                source_lock, artifact_root, readers, native.guard, native.clock_ms, monotonic=native.monotonic)

        @_private
        def _create_picker(self, target, run):
            from adapters.pico4.create_picker_owner import PicoCreatePicker
            return PicoCreatePicker(self,target,run)

        def _create_picker_owned(self, target):
            from adapters.pico4.create_picker_owner import PicoCreatePicker
            return PicoCreatePicker.owned_target(self,target)

        @_private
        def _create_models(self, target, run):
            from adapters.pico4.create_models import PicoCreateModels
            return PicoCreateModels(self,target,run)

        def _create_models_owned(self, target):
            from adapters.pico4.create_models import PicoCreateModels
            return PicoCreateModels.owned_target(self,target)

        @_private
        def _create_journey(self, target, run):
            from adapters.feature_fixture_access import client
            from adapters.pico4.create_journey import PicoCreateJourney
            from feature_journeys.phase_fixture import PhaseFixtureReader
            _need(bool(os.environ.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG')))
            source=PhaseFixtureReader(client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL')),run,'create')
            return PicoCreateJourney(self,target,run,source)

        def _create_feature_owned(self, target):
            from adapters.pico4.create_journey import PicoCreateJourney
            return PicoCreateJourney.owned_target(self,target)

        def _create_file_controls(self, target, intent, directory, run, ticket, role, before, *, before_send=None):
            from adapters.pico4.create_file_ui import CreateFileUI, PicoCreateFileIO
            ui, _observe, _binding = self._script_runtime(target)
            self._bind_create_transport(ui,before_send)
            return CreateFileUI(PicoCreateFileIO(ui.io), intent, directory, run, ticket, role, before,
                monotonic=ui.monotonic, sleep=ui.sleep)

        @_private
        def _create_callback_observer(self, target):
            from adapters.pico4.create_callbacks import NativeCreateCallbacks, FILE as CREATE_CALLBACK_FILE
            native=self._native_feature_observer(target)
            return NativeCreateCallbacks(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CREATE_CALLBACK_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _create_dialog_observer(self, target):
            from adapters.pico4.create_dialogs import NativeCreateDialogs, FILE as CREATE_DIALOG_FILE
            native=self._native_feature_observer(target)
            return NativeCreateDialogs(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CREATE_DIALOG_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _create_browse_setting_native(self, target):
            from adapters.pico4.create_browse_setting import NativeCreateBrowseSetting, FILE as SETTING_FILE
            native=self._native_feature_observer(target)
            return NativeCreateBrowseSetting(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+SETTING_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _create_entity_observer(self, target, run):
            from adapters.pico4.create_entities import NativeCreateEntities, FILE as CREATE_ENTITIES_FILE
            native=self._native_feature_observer(target)
            return NativeCreateEntities(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CREATE_ENTITIES_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,run=run,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _create_model_resources_observer(self, target, run):
            from adapters.pico4.create_model_resources import NativeCreateModelResources, FILE as MODEL_FILE
            native=self._native_feature_observer(target)
            return NativeCreateModelResources(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+MODEL_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,run=run,monotonic=native.monotonic,sleep=native.sleep)

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
        def _navigation_bookmark_adopt(self, target, path, previous_path, run, inputs, old_native, old_bookmark,
                                       phase_source, *, source_lock):
            from adapters.navigation_bookmark_restart import adopt_restart
            from adapters.token_places_ui import TokenPlacesUI
            from adapters.pico4.normal_places import PicoPlacesIO
            source_lock = self._script_journey()._lock(target, source_lock)
            source_lock.assert_held()
            normal, _observe, binding = self._script_runtime(target)
            native = self._native_feature_observer(target)
            return adopt_restart(inputs, PrivateFeatureState(previous_path), PrivateFeatureState(path),
                old_native, old_bookmark,
                lambda intent: TokenPlacesUI(PicoPlacesIO(normal.io), intent, run,
                    monotonic=phase_source.monotonic, sleep=native.sleep),
                native, self._process_presence(target), self._location_bookmarks(target), binding, run,
                phase_source, source_lock)

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
            from adapters.token_script_ui import TokenScriptUI
            from adapters.pico4.navigation_close import NavigationTabletClose
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.native_feature_observation import need
            manager=self._scripts(target);native=self._native_feature_observer(target)
            need(manager.binding==transit.binding)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock)
            def guard():
                lock.assert_held();return native.guard()
            # _scripts creates a fresh runtime. Retain the actual transit input
            # owner instead of substituting that new Navigation instance.
            normal=TokenScriptUI(transit.ui.io.original,monotonic=native.monotonic,sleep=native.sleep)
            return NavigationTabletClose(transit,normal,self._graphics_ui_observer(target),path,guard,
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_lookup_close(self,target,path,lookup,dismissal,*,source_lock):
            from adapters.pico4.navigation_close import NavigationTabletClose
            from adapters.pico4.navigation_lookup_close import NavigationDismissedLookup
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            manager=self._scripts(target);native=self._native_feature_observer(target)
            lock=PicoGraphicsBinding(self)._lock(target,source_lock);lock.assert_held()
            _need(manager.binding==lookup.binding==dismissal.binding)
            def guard():
                lock.assert_held();return native.guard()
            return NavigationTabletClose(NavigationDismissedLookup(lookup,dismissal),lookup.ui.normal,
                self._graphics_ui_observer(target),path,guard,monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _navigation_lookup_dismissal(self,target,path,lookup,*,source_lock):
            from adapters.navigation_missing import NavigationMissing
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            _need(isinstance(lookup,NavigationMissing))
            lock=PicoGraphicsBinding(self)._lock(target,source_lock);lock.assert_held()
            _need(lookup.store.read()==lookup.disk)
            native=self._native_feature_observer(target)
            def guard():
                lock.assert_held();return native.guard()
            return self._navigation_error_dismissal(target,path,lookup.run,lookup.status,lookup.provider,
                lookup.inputs,lookup.origin,guard,normal=lookup.ui.normal,binding=lookup.binding)

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
        def _navigation_error_dismissal(self, target, path, run, status, provider_instance, provider_inputs, owned_origin, guard,*,normal=None,binding=None):
            from adapters.token_script_ui import TokenScriptUI
            from adapters.navigation_error_dismissal import NavigationErrorDismissal
            from adapters.token_navigation_error_ui import TokenNavigationErrorUI
            from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
            manager = self._scripts(target)
            if normal is None:
                _need(binding is None);normal=manager.ui
            else:_need(binding==manager.binding)
            _need(isinstance(normal,TokenScriptUI) and isinstance(normal.io,normal_scripts.PicoScriptIO))
            return NavigationErrorDismissal(lambda intent: TokenNavigationErrorUI(PicoNavigationErrorIO(normal.io), intent, run),
                self._navigation_replies(target), self._navigation_modals(target), status, path, run, manager.binding,
                provider_instance, provider_inputs, owned_origin, guard,monotonic=normal.monotonic,sleep=normal.sleep)

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
                fence=getattr(observer,'phase_fence',None)
                if fence is not None and command.get('operation')!='inspect':fence.check()
                self.write_control_command(target, original.identity, 'native feature sources', command)
            observer=NativeFeatureObservation(send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + NATIVE_FEATURE_FILE, attempts=1),
                lambda: self.adb.epoch_milliseconds(target), guard,
                int(original.identity.split(':')[0]))
            return observer

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
        def _avatar_render_observer(self, target):
            from adapters.native_avatar_render import NativeAvatarRender, FILE as AVATAR_FILE
            native = self._native_feature_observer(target)
            return NativeAvatarRender(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + AVATAR_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
                monotonic=native.monotonic, sleep=native.sleep)

        @_private
        def _emote_model_draws_observer(self, target):
            from adapters.pico4.emote_model_draws import PicoWorldModelDraws, FILE as MODEL_FILE
            native = self._native_feature_observer(target)
            return PicoWorldModelDraws(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + MODEL_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
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
            return (any(path.exists() or path.is_symlink() for path in (store.path,
                store.path.with_name('snapshot-cancel-owner.json'),store.path.with_name('snapshot-cancel-files-owner.json'),
                store.path.with_name('snapshot-cancel-originals.json'),store.path.with_name('snapshot-save-owner.json'),
                store.path.with_name('snapshot-save-originals.json')))
                or any(path.name.startswith(('snapshot-cancel-originals.json.frame-','snapshot-save-originals.json.frame-')) for path in store.path.parent.iterdir()))

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

        def _browser_world_render_store(self,target,role):
            _need(role in ('primary','actor'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','browser-world-render-'+role+'-')))

        def _browser_world_render_capture(self,target,*,role,source_lock):
            from adapters.pico4.graphics_binding import PicoGraphicsBinding,SerializedWorldCapture
            from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles,INVENTORY_FILE
            _need(role in ('primary','actor'))
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            _ui,_observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            _need(native.pid==int(binding['processIdentity'].split(':')[0]))
            facade=PicoGraphicsBinding(self)
            foreign=[self._browser_world_render_store(target,'actor' if role=='primary' else 'primary'),self._world_render_store(target)]
            foreign.extend(facade.world_render_store(target,role=value) for value in ('primary','actor'))
            foreign.extend(self._emote_world_render_store(target,value) for value in ('primary','actor'))
            def world_guard():
                lock.assert_held();native.guard();_need(all(store.read() is None for store in foreign));return True
            owner=WorldRenderOwner(self._browser_world_render_store(target,role),binding,world_guard,role=role)
            files=AndroidWorldRenderReceipts(self.adb,target,'org.overte.pico',world_guard)
            options=dict(monotonic=native.monotonic,sleep=native.sleep)
            storage=NativeWorldRenderStorage(native.send,files.read,native.clock_ms,world_guard,native.pid,receipt_intent=owner.receipt_intent,**options)
            inventory=NativeWorldReceiptInventory(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+INVENTORY_FILE,attempts=1),
                native.clock_ms,world_guard,native.pid,owner.owned,lambda:storage.instance,**options)
            capture=NativeWorldRenderCapture(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+WORLD_RENDER_FILE,attempts=1),
                storage,native.clock_ms,world_guard,native.pid,intent=owner.intent,stereo=True,require_cameras=True,**options)
            return SerializedWorldCapture(capture,storage,owner,NativeWorldReceiptBatchFiles(files,inventory),source_lock=lock)

        @_private
        def _browser_stereo(self,target,path,artifact_root,run,scene_url,*,role,source_lock,journal_id,
                fixture_url,foreign_fixture_url,owner_token,script_url,http):
            from adapters.pico4.browser_stereo import PicoBrowserStereo
            from adapters.navigation_arrival import NavigationArrival
            lock=self._script_journey()._lock(target,source_lock);lock.assert_held()
            _ui,observe,binding=self._script_runtime(target);native=self._native_feature_observer(target)
            _need(native.pid==int(binding['processIdentity'].split(':')[0]))
            def probe(after):
                native.guard();value=self.read_probe_snapshot(target,'org.overte.pico',after);native.guard();return value
            arrival=NavigationArrival(probe,self._graphics_subject_observer(target),native.clock_ms,native.guard,
                run,binding,scene_url,monotonic=native.monotonic)
            return PicoBrowserStereo(arrival,lambda:self._browser_world_render_capture(target,role=role,source_lock=lock),
                path,artifact_root,run,binding,lock,native.guard,fixture_url=fixture_url,foreign_fixture_url=foreign_fixture_url,
                owner_token=owner_token,script_url=script_url,browser_factory=lambda:self._browser_originals(target,source_lock=lock),
                runtime_factory=lambda:self._web_runtime_observer(target),scripts=observe,http=http,role=role,journal_id=journal_id,
                ui_factory=lambda:self._graphics_ui_observer(target),native_factory=lambda:self._native_feature_observer(target),
                monotonic=native.monotonic)

        @_private
        def _browser_app_controls(self,target,*,source_lock,read_only=True):
            from adapters.pico4.browser_apps import PicoBrowserAppsIO
            source_lock=self._script_journey()._lock(target,source_lock);source_lock.assert_held()
            return PicoBrowserAppsIO(self._script_runtime(target)[0].io,source_lock=source_lock,read_only=read_only)

        @_private
        def _browser_originals(self,target,*,source_lock,tablet=True,read_only=True):
            from adapters.pico4.browser_source import PicoBrowserIO,FILE
            from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
            source_lock=self._script_journey()._lock(target,source_lock)
            _need(type(tablet) is bool and type(read_only) is bool)
            native=self._native_feature_observer(target)
            def guard():
                source_lock.assert_held();native.guard();return True
            return (PicoTabletBrowserIO if tablet else PicoBrowserIO)(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,guard,native.pid,source_lock=source_lock,read_only=read_only,
                monotonic=native.monotonic,sleep=native.sleep)

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

        def _chat_samples_store(self,target,role,*,erased=False,witness=False):
            _need(role in ('primary','actor') and type(erased) is bool and type(witness) is bool and (not witness or role=='actor'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-'+('erased-' if erased else '')+('witness' if witness else role)+'-samples-')))

        def _chat_script_source_store(self,target,role,*,witness=False,stage='active'):
            _need(role in ('primary','actor') and type(witness) is bool and (not witness or role=='actor')
                and stage in ('active','erase','final') and (not witness or stage=='active'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-'+('witness' if witness else role)+'-'+('' if stage=='active' else stage+'-')+'script-source-')))

        @_private
        def _chat_script_source(self,target,run,*,role,source_lock,witness=False,stage='active',predecessor=None):
            from adapters.chat_journey.script_source import ChatScriptSource
            from adapters.script_journey.lock import ScriptSourceLock
            store=self._chat_script_source_store(target,role,witness=witness,stage=stage)
            _need(isinstance(source_lock,ScriptSourceLock) and source_lock.path==store.path.with_name('script-sources.lock'))
            with source_lock.held():
                manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
                if stage=='active':
                    _need(predecessor is None);roots,scripts=self._script_roots_observer(target),self._script_execution_observer(target)
                else:
                    previous_stage='active' if stage=='erase' else 'erase'
                    _need(type(predecessor) is ChatScriptSource and not witness
                        and predecessor.store.path==self._chat_script_source_store(target,role,stage=previous_stage).path
                        and predecessor.run==run and predecessor.binding==manager.binding and predecessor.lock is source_lock)
                    roots,scripts=predecessor.roots,predecessor.scripts
                return ChatScriptSource(run,role,manager.binding,roots,scripts,store,source_lock,
                    monotonic=native.monotonic,predecessor=predecessor)

        def _chat_flow_inputs_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-flow-inputs-')))

        def _chat_witness_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-witness-publisher-')))

        @_private
        def _chat_flow_inputs(self,target,source,primary,actor,initial_primary,initial_actor):
            from adapters.chat_journey.flow_inputs import ChatFlowInputs
            from adapters.feature_fixture_access import AdapterFixtureClient
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(isinstance(source.client,AdapterFixtureClient) and primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path
                and initial_primary.store.path==self._chat_cache_absence_store(target,'primary',stage='initial').path
                and initial_actor.store.path==self._chat_cache_absence_store(target,'actor',stage='initial').path)
            return ChatFlowInputs(source,(primary,actor),self._chat_flow_inputs_store(target),
                self._chat_samples_store(target,'actor',witness=True),initial_roles=(initial_primary,initial_actor),
                initial_witness_store=self._chat_cache_absence_store(target,'actor',stage='initial',witness=True),monotonic=native.monotonic)

        @_private
        def _chat_witness(self,target,source,samples,initial_samples):
            from adapters.chat_journey.witness import ChatWitness
            from adapters.feature_fixture_access import AdapterFixtureClient
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(not isinstance(source.client,AdapterFixtureClient) and samples.binding==manager.binding
                and samples.store.path==self._chat_samples_store(target,'actor',witness=True).path
                and initial_samples.store.path==self._chat_cache_absence_store(target,'actor',stage='initial',witness=True).path)
            return ChatWitness(source,samples,self._chat_flow_inputs_store(target),self._chat_witness_store(target),initial_samples=initial_samples,monotonic=native.monotonic)

        def _chat_normal_input_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-normal-input-')))

        def _chat_composition_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-composition-')))

        def _chat_cleanup_admission_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cleanup-admission-')))

        def _chat_observation_store(self,target,role,*,stage,witness=False):
            _need(role in ('primary','actor') and stage in ('initial','active','cleanup')
                and type(witness) is bool and (not witness or role=='actor'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-'+('witness' if witness else role)+'-'+stage+'-observation-')))

        def _chat_cleanup_witness_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cleanup-witness-')))

        def _chat_cleanup_baseline_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cleanup-baseline-')))

        def _chat_cursor_cleanup_consumption_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-global-cleanup-consumption-')))

        def _chat_cursor_actor_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cursor-actor-owner-')))

        def _chat_cursor_actor_stop_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cursor-actor-stop-')))

        @_private
        def _chat_cursor_actor(self,target,source,peer_config):
            from adapters.pico4.chat_cursor_actor import PicoChatCursorActor
            return PicoChatCursorActor(self,target,source,peer_config)

        @_private
        def _chat_cursor_cleanup_consumption(self,target,parent,primary,actor):
            from adapters.chat_journey.cursor_cleanup_consumption import ChatCursorCleanupConsumption
            from adapters.chat_journey.observation_cursor import ChatObservationCursor
            from adapters.chat_journey.observation_publisher import ChatObservationPublisher
            from adapters.pico4.chat_composition import PicoChatComposition
            _need(type(parent) is PicoChatComposition and parent.adapter is self and parent.target==target
                and not parent.failed and parent.previous['phase']=='caches-retired' and parent.cache_release.defer_ipc
                and type(primary) is ChatObservationCursor and type(actor) is ChatObservationPublisher
                and primary.current.samples is parent.cache_release.roles[0]
                and primary.scope['runId']==parent.source.run and primary.scope['fixtureUrl']==parent.source.fixture_url
                and primary.scope['binding']==parent.binding and actor.scope['peerBinding']==parent.peer.binding)
            # These exact stage paths are supplied by Pico's original factories,
            # not an arbitrary generic source graph with the same final fields.
            for cursor,witness in ((primary,False),(actor.cursor,True)):
                for observation in cursor.owners:
                    role=observation.samples.role;stage=observation.stage
                    _need(observation.store.path==self._chat_observation_store(target,role,stage=stage,witness=witness).path)
                    expected=(self._chat_samples_store(target,role,witness=witness) if stage=='active' else
                        self._chat_cache_absence_store(target,role,stage='initial' if stage=='initial' else 'final',witness=witness))
                    _need(observation.samples.store.path==expected.path)
            admitted=deepcopy(parent.previous)
            def guard():
                _need(not parent.failed and parent.previous==admitted and parent.store.read()==admitted)
                parent.guard();return True
            guard()
            seals=[]
            try:
                seals.append(self._chat_cursor_source_seal(target,primary,witness=False))
                seals.append(self._chat_cursor_source_seal(target,actor,witness=True))
                return ChatCursorCleanupConsumption(primary,actor,tuple(seals),self._chat_cursor_cleanup_consumption_store(target),guard=guard)
            except Exception:
                parent.failed=True
                for seal in seals:seal.failed=True
                raise

        def _chat_observation_cursor_store(self,target,role,*,witness=False):
            _need(role in ('primary','actor') and type(witness) is bool and (not witness or role=='actor'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-'+('witness' if witness else role)+'-observation-cursor-')))

        def _chat_observation_publisher_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-original-observation-publisher-')))

        @_private
        def _chat_observation_publisher(self,target,cursor):
            from adapters.chat_journey.observation_cursor import ChatObservationCursor
            from adapters.chat_journey.observation_publisher import ChatObservationPublisher
            _need(type(cursor) is ChatObservationCursor and cursor.scope['role']=='actor'
                and cursor.store.path==self._chat_observation_cursor_store(target,'actor',witness=True).path)
            native=self._native_feature_observer(target);native.guard()
            _need(cursor.scope['binding']==self._scripts(target).binding)
            return ChatObservationPublisher(cursor,self._chat_observation_publisher_store(target))

        @_private
        def _chat_observation_cursor(self,target,initial,*,witness=False):
            from adapters.chat_journey.observation import ChatObservationOwner
            from adapters.chat_journey.observation_cursor import ChatObservationCursor
            from adapters.feature_fixture_access import AdapterFixtureClient
            _need(type(initial) is ChatObservationOwner and initial.stage=='initial' and type(witness) is bool
                and witness is (not isinstance(initial.source.client,AdapterFixtureClient))
                and initial.store.path==self._chat_observation_store(target,initial.samples.role,stage='initial',witness=witness).path)
            native=self._native_feature_observer(target);native.guard()
            _need(initial.samples.binding==self._scripts(target).binding)
            return ChatObservationCursor(initial,self._chat_observation_cursor_store(target,initial.samples.role,witness=witness))

        def _chat_cleanup_source_seal_store(self,target,*,witness):
            _need(type(witness) is bool);state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-cleanup-'+('witness' if witness else 'primary')+'-source-seal-')))

        def _chat_cursor_source_seal_store(self,target,*,witness):
            _need(type(witness) is bool);state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-global-'+('witness' if witness else 'primary')+'-source-seal-')))

        @_private
        def _chat_cursor_source_seal(self,target,owner,*,witness):
            from adapters.chat_journey.observation_cursor import ChatObservationCursor
            from adapters.chat_journey.observation_publisher import ChatObservationPublisher
            from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
            _need(type(witness) is bool and type(owner) is (ChatObservationPublisher if witness else ChatObservationCursor))
            cursor=owner.cursor if witness else owner
            _need(cursor.scope['role']==('actor' if witness else 'primary')
                and cursor.store.path==self._chat_observation_cursor_store(target,cursor.scope['role'],witness=witness).path
                and (not witness or owner.store.path==self._chat_observation_publisher_store(target).path))
            native=self._native_feature_observer(target);native.guard()
            _need(cursor.scope['binding']==self._scripts(target).binding)
            return ChatCursorSourceSeal(owner,self._chat_cursor_source_seal_store(target,witness=witness))

        @_private
        def _chat_source_seal(self,target,owner,*,witness):
            from adapters.chat_journey.source_seal import ChatSourceSeal
            from adapters.chat_journey.cleanup_witness import ChatCleanupWitness
            from adapters.chat_journey.observation import ChatObservationOwner
            from contextlib import ExitStack
            _need(type(witness) is bool and type(owner) is (ChatCleanupWitness if witness else ChatObservationOwner))
            observation=owner.observation if witness else owner
            _need(observation.stage=='cleanup' and observation.samples.role==('actor' if witness else 'primary')
                and observation.store.path==self._chat_observation_store(target,observation.samples.role,
                    stage='cleanup',witness=witness).path
                and (not witness or owner.store.path==self._chat_cleanup_witness_store(target).path))
            with ExitStack() as held:
                for lock in sorted(observation.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
                native=self._native_feature_observer(target);native.guard()
                _need(observation.samples.binding==self._scripts(target).binding)
                return ChatSourceSeal(owner,self._chat_cleanup_source_seal_store(target,witness=witness))

        @_private
        def _chat_observation(self,target,source,samples,*,stage,witness=False):
            from adapters.chat_journey.observation import ChatObservationOwner
            from adapters.feature_fixture_access import AdapterFixtureClient
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(stage in ('initial','active','cleanup') and type(witness) is bool
                and witness is (not isinstance(source.client,AdapterFixtureClient))
                and samples.binding==manager.binding and source.run==samples.run)
            expected=(self._chat_samples_store(target,samples.role,witness=witness) if stage=='active' else
                self._chat_cache_absence_store(target,samples.role,stage='initial' if stage=='initial' else 'final',witness=witness))
            _need(samples.store.path==expected.path)
            return ChatObservationOwner(source,samples,self._chat_flow_inputs_store(target),
                self._chat_observation_store(target,samples.role,stage=stage,witness=witness),stage=stage,
                cleanup_store=self._chat_cleanup_admission_store(target) if stage=='cleanup' else None,
                monotonic=native.monotonic)

        @_private
        def _chat_cleanup_witness(self,target,original):
            from adapters.pico4.chat_cleanup_witness import PicoChatCleanupWitness
            return PicoChatCleanupWitness(self,target,original)

        def _chat_cache_release_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cache-release-')))

        def _chat_peer_state_retained(self,target):
            from adapters.pico4.chat_composition import peer_retained
            return peer_retained(self,target)

        def _chat_archive_retirement_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-archive-retirement-')))

        def _chat_host_close_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-host-close-')))

        def _chat_application_retained(self,target):
            # Rootless successor/retirement chunks must not disappear behind
            # a missing parent root or ordinary application force-stop.
            stores=[self._chat_application_store(target),self._chat_restart_inputs_store(target),self._chat_archive_retirement_store(target),self._chat_host_close_store(target)]
            stores.append(self._chat_cleanup_witness_store(target))
            stores.append(self._chat_cleanup_baseline_store(target))
            stores.extend((self._chat_cursor_actor_store(target),self._chat_cursor_actor_stop_store(target)))
            stores.append(self._chat_cursor_cleanup_consumption_store(target))
            stores.append(self._chat_observation_publisher_store(target))
            stores.extend(self._chat_observation_cursor_store(target,role,witness=witness)
                for role,witness in (('primary',False),('actor',False),('actor',True)))
            stores.extend(self._chat_cleanup_source_seal_store(target,witness=witness) for witness in (False,True))
            stores.extend(self._chat_cursor_source_seal_store(target,witness=witness) for witness in (False,True))
            stores.extend(self._chat_observation_store(target,role,stage=stage,witness=witness)
                for role,witness in (('primary',False),('actor',False),('actor',True))
                for stage in ('initial','active','cleanup'))
            stores.extend(self._chat_postrestart_store(target,kind) for kind in ('ui','primary-code','actor-code','primary-absence','actor-absence'))
            retained=any(self._chat_chunk_store_retained(store) for store in stores)
            state,_ui=self._script_paths(target);key=state.stem.removeprefix('normal-script-state-')
            from adapters.chat_journey.evidence_archive import completed_archive
            for path in state.parent.iterdir():
                if not path.name.startswith('chat-evidence-'+key+'-'):continue
                run=path.name.removeprefix('chat-evidence-'+key+'-')
                _need(re.fullmatch('[0-9a-f]{32}',run))
                evidence=completed_archive(path);metadata=evidence['metadata']
                cursor_fields={'chatCursorCleanupConsumptionVersion','chatCursorCleanupConsumptionSha256',
                    'chatCursorSourceSeals','chatCursorSequenceSucceeded'}
                if cursor_fields&set(metadata):
                    _need(cursor_fields<=set(metadata) and metadata.get('picoChatArchivePlanVersion')==4
                        and not {'chatCleanupBaselineSha256','chatCleanupSourceSeals'}&set(metadata)
                        and type(metadata['chatCursorCleanupConsumptionVersion']) is int
                        and metadata['chatCursorCleanupConsumptionVersion']==1 and metadata['chatCursorSequenceSucceeded'] is True
                        and type(metadata['chatCursorCleanupConsumptionSha256']) is str
                        and re.fullmatch('[0-9a-f]{64}',metadata['chatCursorCleanupConsumptionSha256'])
                        and type(metadata['chatCursorSourceSeals']) is list and len(metadata['chatCursorSourceSeals'])==2
                        and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in metadata['chatCursorSourceSeals'])
                        and len(set(metadata['chatCursorSourceSeals']))==2)
                if {'chatCleanupBaselineSha256','chatCleanupSourceSeals'}&set(metadata):
                    _need(metadata.get('picoChatArchivePlanVersion')==4
                        and type(metadata.get('chatCleanupBaselineSha256')) is str
                        and re.fullmatch('[0-9a-f]{64}',metadata['chatCleanupBaselineSha256'])
                        and type(metadata.get('chatCleanupSourceSeals')) is list and len(metadata['chatCleanupSourceSeals'])==2
                        and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in metadata['chatCleanupSourceSeals'])
                        and len(set(metadata['chatCleanupSourceSeals']))==2)
                if metadata.get('picoChatArchivePlanVersion') in (2,3,4):_need(evidence.get('chatEvidenceArchiveVersion')==metadata['picoChatArchivePlanVersion'] and evidence.get('fileOwnership')=='closed-immutable-originals')
                if metadata.get('picoChatArchivePlanVersion') in (3,4):_need(evidence.get('unlinkPolicy')=='original-source-16-unlinks-250ms')
                if metadata.get('picoChatArchivePlanVersion')==4:_need(evidence.get('copyVerification')=='full-current-copy-and-original-physical-inventory')
                _need(type(metadata.get('picoChatArchivePlanVersion')) is int and metadata['picoChatArchivePlanVersion'] in (1,2,3,4) and metadata.get('runId')==run
                    and metadata['oldBinding']['targetFingerprint']==metadata['newBinding']['targetFingerprint']
                    ==hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest())
            return retained

        def _chat_application_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-application-close-')))

        def _chat_restart_inputs_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-restart-inputs-')))

        def _chat_postrestart_store(self,target,kind):
            _need(kind in ('ui','primary-code','actor-code','primary-absence','actor-absence'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-postrestart-'+kind+'-')))

        @_private
        def _chat_postrestart_sources(self,target,run,identity,peer,peer_binding,*,source_lock,peer_lock):
            # Never call _scripts/_script_runtime: their original old-PID
            # journals stay intact until actual ESRCH and immutable archival.
            from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
            from adapters.chat_journey.script_source import ChatScriptSource
            from adapters.script_journey.lock import ScriptSourceLock
            from adapters.native_chat_observation import NativeChatObservation,FILE as CHAT_FILE
            from adapters.native_chat_view import NativeChatView,FILE as VIEW_FILE
            _need(isinstance(source_lock,ScriptSourceLock) and isinstance(peer_lock,ScriptSourceLock))
            source_lock.assert_held();peer_lock.assert_held()
            _need(isinstance(peer,NativeChatObservation) and not peer.ios and not getattr(peer,'_chat_cache_lifetime_owned',False)
                and self.require_controlled_debug_identity(target)==identity and peer.pid==int(peer_binding['processIdentity'].split(':')[0]))
            scene=normal_scripts.configuration(os.environ);_need(scene is not None)
            ui_store=self._chat_postrestart_store(target,'ui');_need(ui_store.read() is None)
            def no_input(_operation):raise ValueError('Post-restart Chat sources cannot deliver controller input')
            _ui,_observe,binding=normal_scripts.runtime(self,target,scene,self._installation(target),identity,ui_store.path,no_input)
            roles=[]
            for role in ('primary','actor'):
                native=self._native_feature_observer(target);native.guard()
                code_store=self._chat_postrestart_store(target,role+'-code')
                store=self._chat_postrestart_store(target,role+'-absence')
                _need(source_lock.path==store.path.with_name('script-sources.lock') and code_store.read() is None and store.read() is None)
                code=ChatScriptSource(run,role,binding,self._script_roots_observer(target),self._script_execution_observer(target),
                    code_store,source_lock,monotonic=native.monotonic)
                def send(command,native=native):
                    _need(command.get('operation')=='inspect');native.send(command)
                primary=NativeChatObservation(send,
                    lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CHAT_FILE,attempts=1),
                    native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
                view=NativeChatView(native.send,
                    lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+VIEW_FILE,attempts=1),
                    native.clock_ms,native.guard,native.pid,vr=True,monotonic=native.monotonic,sleep=native.sleep)
                # Every independent role gets a new original peer reader on
                # the still-open restricted transport, never a copied packet.
                from adapters.native_chat_observation import NativeChatObservation as PeerReader
                remote=PeerReader(peer.send,peer.original,peer.clock_ms,peer.guard,peer.pid,monotonic=peer.monotonic,sleep=peer.sleep)
                remote._chat_transport=peer._chat_transport
                roles.append(CompiledChatCacheAbsence(run,role,binding,peer_binding,primary,remote,view,native,
                    store,source_lock,peer_lock,vr=True,script_source=code,monotonic=native.monotonic))
            return binding,tuple(roles)

        @_private
        def _chat_composition(self,target,source,peer_config,domain_ready):
            from adapters.pico4.chat_composition import PicoChatComposition
            return PicoChatComposition(self,target,source,peer_config,domain_ready)

        @_private
        def _chat_witness_composition(self,target,source,peer_config):
            from adapters.pico4.chat_composition import PicoChatWitness
            return PicoChatWitness(self,target,source,peer_config)

        def _chat_dispatcher_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-dispatcher-')))

        @staticmethod
        def _chat_chunk_store_retained(store):
            # A missing root never retires its original immutable children.
            # Inspect only this existing private namespace; no child is opened,
            # adopted, removed or inferred released from a process-stop ACK.
            if store.read() is not None:return True
            store._parent();prefix=store.path.name+'.frame-'
            return any(path.name.startswith(prefix) for path in store.path.parent.iterdir())

        @_private
        def _chat_normal_input(self,target,primary,actor,*,enter=False):
            from adapters.chat_journey.normal_input import ChatNormalInput
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path)
            return ChatNormalInput((primary,actor),lambda intent:self._chat_controls(target,intent,primary.run),
                self._chat_normal_input_store(target),enter=enter,monotonic=native.monotonic,sleep=native.sleep)

        def _chat_background_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-background-')))

        @_private
        def _chat_background_source(self,target,*,source_lock,intent):
            # Chat's existing parent owns this different lock namespace. The
            # ordinary Lifecycle factory keeps its Script-journey path check.
            import json
            from adapters.script_journey.lock import ScriptSourceLock
            from adapters.pico4.lifecycle_background_source import NativeLifecycleBackground,COMMAND,FILE,command
            _need(isinstance(source_lock,ScriptSourceLock) and callable(intent)
                and source_lock.path==self._chat_samples_store(target,'primary').path.with_name('script-sources.lock'))
            native=self._native_feature_observer(target)
            def send(request):
                command(request);source_lock.assert_held();_need(native.guard() is not False)
                fence=getattr(source,'phase_fence',None)
                if fence is not None and request['operation']!='observe':fence.check()
                self.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,json.dumps(request,separators=(',',':'))+'\n')
                _need(native.guard() is not False)
            source=NativeLifecycleBackground(send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,source_lock,intent=intent,monotonic=native.monotonic,sleep=native.sleep)
            return source

        @_private
        def _pico_lifecycle_input_once(self,target,operation,binding,*,before_input):
            from adapters.pico4.lifecycle_input import issue_once
            return issue_once(self,target,operation,binding,before_input=before_input)

        @_private
        def _chat_background(self,target,primary,actor):
            from adapters.chat_journey.background import ChatBackground
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path)
            return ChatBackground((primary,actor),
                lambda intent:self._chat_background_source(target,source_lock=primary.locks[0],intent=intent),
                PicoGraphicsBinding(self),target,self._chat_background_store(target),monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _chat_background_recover(self,target,*,source_lock=None):
            # An original HOME can make every foreground-only Qt factory
            # unavailable. Reacquire only candidate/kernel/OS evidence here.
            from adapters.chat_journey.background import ChatBackground
            from adapters.pico4.graphics_binding import PicoGraphicsBinding
            from adapters.script_journey.lock import ScriptSourceLock
            store=self._chat_background_store(target)
            if source_lock is None:source_lock=ScriptSourceLock(store.path.with_name('script-sources.lock'))
            return ChatBackground.recover_foreground(PicoGraphicsBinding(self),target,store,source_lock)

        def _chat_mixer_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-mixer-owner-')))

        @_private
        def _chat_mixer(self,target,controls,primary,actor):
            from adapters.chat_journey.mixer import ChatMixerOwner
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path)
            # The existing fixture owner supplies separately guarded original
            # private control transports; this factory launches no fixture.
            return ChatMixerOwner(controls,(primary,actor),self._chat_mixer_store(target),
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _chat_mixer_recovery(self,target,controls,run):
            from adapters.chat_journey.mixer_recovery import ChatMixerRecovery
            store=self._chat_mixer_store(target);original=store.read()
            _need(type(original) is dict and type(original.get('binding')) is dict)
            binding=original['binding']
            _need(original.get('runId')==run and original.get('transcripts')==
                [self._chat_samples_store(target,role).path.name for role in ('primary','actor')])
            def guard():
                _need(hashlib.sha256((target+'\0'+str(self.pico_configuration)).encode()).hexdigest()==binding['targetFingerprint'])
                installed=self._installation(target)
                _need(all(installed[key]==binding[key] for key in ('sourceRevision','artifactSha256')))
                return True
            guard()
            # No running app/Qt/OpenXR source is required for the distinct
            # original fixture process restoration. No native journal is read.
            return ChatMixerRecovery(controls,store,binding,run,guard)

        def _chat_no_replay_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-no-replay-')))

        def _chat_erase_restore_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-erase-restore-')))

        @_private
        def _chat_erase_restore(self,target,profile,before,after):
            from adapters.chat_journey.erase_restore import ChatEraseRestore
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(profile.binding==manager.binding and profile.store.path==self._chat_profile_store(target).path)
            for pair,erased in ((before,False),(after,True)):
                _need(type(pair) is tuple and len(pair)==2)
                for role,name in zip(pair,('primary','actor')):
                    _need(role.binding==manager.binding and role.role==name
                        and role.store.path==self._chat_samples_store(target,name,erased=erased).path)
            return ChatEraseRestore(profile,before,after,lambda intent:self._chat_controls(target,intent,profile.run),
                self._chat_erase_restore_store(target),monotonic=native.monotonic,sleep=native.sleep)

        def _chat_profile_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-profile-owner-')))

        @_private
        def _chat_profile(self,target,run,source_lock):
            from adapters.native_chat_profile import NativeChatProfile,OwnedChatProfile,FILE
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            reader=NativeChatProfile(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
            reader._chat_transport=native
            return OwnedChatProfile(reader,self._chat_profile_store(target),manager.binding,run,source_lock)

        @_private
        def _chat_restart_io(self,target,binding):
            from adapters.pico4.chat_restart_io import PicoChatRestartIO
            manager=self._scripts(target);_need(manager.binding==binding)
            return PicoChatRestartIO(self,target,binding)

        @_private
        def _chat_profile_current(self,target):
            from adapters.native_chat_profile_current import NativeChatProfileCurrent,FILE
            native=self._native_feature_observer(target);native.guard()
            return NativeChatProfileCurrent(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        def _chat_peer_input_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-peer-input-')))

        @_private
        def _chat_peer_position(self,target):
            from adapters.native_chat_peer_position import NativeChatPeerPosition, FILE
            native=self._native_feature_observer(target);native.guard()
            return NativeChatPeerPosition(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

        def _chat_peer_send_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-peer-send-')))

        def _chat_peer_distant_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-peer-distant-')))

        @_private
        def _chat_peer_distant(self,target,sender):
            from adapters.chat_journey.peer_distant import ChatPeerDistant
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(sender.roles[0].binding==sender.roles[1].binding==manager.binding
                and sender.store.path==self._chat_peer_send_store(target).path
                and sender.input.store.path==self._chat_peer_input_store(target).path)
            return ChatPeerDistant(sender,(self._chat_peer_position(target),self._chat_peer_position(target)),
                self._chat_peer_distant_store(target),monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _chat_peer_input(self,target,files,run):
            from adapters.chat_peer_input import ChatPeerInput
            native=self._native_feature_observer(target);native.guard()
            return ChatPeerInput(files,self._chat_peer_input_store(target),run)

        @_private
        def _chat_peer_send(self,target,input_owner,primary,actor):
            from adapters.chat_journey.peer_send import ChatPeerSend
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path
                and input_owner.store.path==self._chat_peer_input_store(target).path)
            return ChatPeerSend(input_owner,primary,actor,self._chat_peer_send_store(target),
                monotonic=native.monotonic,sleep=native.sleep)

        @_private
        def _chat_no_replay(self,target,primary,actor):
            from adapters.chat_journey.no_replay import ChatNoReplay
            manager=self._scripts(target);native=self._native_feature_observer(target);native.guard()
            _need(primary.binding==actor.binding==manager.binding
                and primary.store.path==self._chat_samples_store(target,'primary').path
                and actor.store.path==self._chat_samples_store(target,'actor').path)
            return ChatNoReplay(primary,actor,self._chat_no_replay_store(target),monotonic=native.monotonic,sleep=native.sleep)

        def _chat_cache_absence_store(self,target,role,*,stage,witness=False):
            _need(role in ('primary','actor') and stage in ('initial','final') and type(witness) is bool and (not witness or role=='actor'))
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-',
                'chat-'+stage+'-'+('witness' if witness else role)+'-cache-absence-')))

        @_private
        def _chat_cache_absence(self,target,run,peer,peer_binding,*,role,stage,source_lock,peer_lock,witness=False,script_source=None):
            from adapters.chat_journey.samples import ChatCacheAbsence
            from adapters.script_journey.lock import ScriptSourceLock
            store=self._chat_cache_absence_store(target,role,stage=stage,witness=witness)
            _need(isinstance(source_lock,ScriptSourceLock) and source_lock.path==store.path.with_name('script-sources.lock'))
            with source_lock.held():
                manager=self._scripts(target);native=self._native_feature_observer(target)
                capture=self._chat_capture(target,run)
                # No capture-owner begin/observe/retire or ownership write.
                # The actual inspect source must independently prove absence.
                native.guard();_need(peer.guard() is not False)
                selected=ChatCacheAbsence;extra={}
                if script_source is not None:
                    from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
                    _need(script_source.store.path in {self._chat_script_source_store(target,role,witness=witness).path,
                        self._chat_script_source_store(target,role,witness=witness,stage='active' if witness or stage=='initial' else 'final').path})
                    selected=CompiledChatCacheAbsence;extra=dict(script_source=script_source)
                return selected(run,role,manager.binding,peer_binding,capture.reader,peer,self._chat_view(target),native,
                    store,source_lock,peer_lock,vr=True,monotonic=native.monotonic,**extra)

        @_private
        def _chat_samples(self,target,run,peer,peer_binding,*,role,source_lock,peer_lock,erased=False,witness=False,pending_capture=False,script_source=None):
            from adapters.chat_journey.samples import ChatSamples
            from adapters.script_journey.lock import ScriptSourceLock
            store=self._chat_samples_store(target,role,erased=erased,witness=witness)
            _need(type(pending_capture) is bool and isinstance(source_lock,ScriptSourceLock) and source_lock.path==store.path.with_name('script-sources.lock'))
            with source_lock.held():
                manager=self._scripts(target);native=self._native_feature_observer(target)
                capture=self._chat_capture(target,run);owned=capture.owner.owned()
                _need(owned is not None and owned['runId']==run and (owned['active'] or pending_capture and owned['admitted']) and owned['binding']==manager.binding)
                # The peer is independently bound by its actual original
                # actor transport/process owner. This factory cannot launch,
                # infer or substitute that peer with the heartbeat fixture.
                native.guard();_need(peer.guard() is not False)
                original_guard=capture.reader.guard
                def cache_guard():
                    # owned() already calls this exact original guard before
                    # reading the private owner. Do not hash the APK twice.
                    _need(capture.owner.guard is original_guard)
                    current=capture.owner.owned()
                    _need(current is not None and current['active'] and current['runId']==run
                        and all(current[key]==owned[key] for key in ('binding','sourceInstance','selfSha256','admitted')))
                    if capture.reader.instance is not None:
                        _need(capture.reader.instance==owned['sourceInstance']
                            and capture.reader.source['selfSha256']==owned['selfSha256'])
                    return True
                capture.reader.guard=cache_guard
                selected=ChatSamples;extra={}
                if script_source is not None:
                    from adapters.chat_journey.compiled_samples import CompiledChatSamples
                    _need(script_source.store.path in {self._chat_script_source_store(target,role,witness=witness).path,
                        self._chat_script_source_store(target,role,witness=witness,stage='erase' if erased and not witness else 'active').path})
                    selected=CompiledChatSamples;extra=dict(script_source=script_source)
                return selected(run,role,manager.binding,peer_binding,capture.reader,peer,self._chat_view(target),native,
                    store,source_lock,peer_lock,vr=True,monotonic=native.monotonic,**extra)

        def _chat_cache_lifetime_store(self,target):
            state,_ui=self._script_paths(target)
            return PrivateFeatureState(state.with_name(state.name.replace('normal-script-state-','chat-cache-lifetime-')))

        @_private
        def _chat_cache_lifetime(self,target,run,*,source_lock):
            from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
            from adapters.script_journey.lock import ScriptSourceLock
            store=self._chat_cache_lifetime_store(target)
            _need(isinstance(source_lock,ScriptSourceLock) and source_lock.path==store.path.with_name('script-sources.lock'))
            with source_lock.held():
                capture=self._chat_capture(target,run)
                return ChatCacheLifetime(capture,store,source_lock,monotonic=capture.reader.monotonic)

        @_private
        def _chat_admit_capture(self,target,run,*,source_lock):
            from adapters.script_journey.lock import ScriptSourceLock
            _need(isinstance(source_lock,ScriptSourceLock) and source_lock.path==self._chat_samples_store(target,'primary').path.with_name('script-sources.lock'))
            with source_lock.held():
                capture=self._chat_capture(target,run);capture.owner.begin(run)
                original=capture.reader.perform(run,'inspect')
                _need(original['chatVersion']>=2 and not original['source']['scopePresent'] and not original['source']['retired'])
                capture.owner.admit(original)
                return capture

        @_private
        def _chat_capture(self,target,run):
            manager=self._scripts(target);native=self._native_feature_observer(target)
            owner=ChatCaptureOwner(self._chat_capture_store(target),manager.binding,native.guard)
            reader=NativeChatObservation(native.send,
                lambda:self.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+CHAT_FILE,attempts=1),
                native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
            reader._chat_transport=native
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
        def _animation_inventory_observer(self, target):
            from adapters.native_animation_inventory import NativeAnimationInventory, FILE as INVENTORY_FILE
            native = self._native_feature_observer(target)
            return NativeAnimationInventory(native.send,
                lambda: self.adb.read_debug_app_file(target, 'org.overte.pico',
                    'files/overte-e2e/' + INVENTORY_FILE, attempts=1),
                native.clock_ms, native.guard, native.pid,
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
                    _need(not self._create_feature_owned(target))
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
            try:
                if self.pico_configuration is not None:
                    from adapters.pico4.tablet_web_binding import retained
                    if retained(self,target):feature_error=True
                    if any(self._browser_world_render_store(target,role).read() is not None for role in ('primary','actor')):
                        feature_error=True
            except Exception:
                feature_error=True
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
                    # Source transcripts contain original unresolved role
                    # ownership. Process teardown cannot qualify their removal.
                    if any(self._chat_samples_store(target,role,erased=erased,witness=witness).read() is not None
                           for erased in (False,True) for role,witness in (('primary',False),('actor',False),('actor',True))):
                        chat_error=True
                    if any(self._chat_cache_absence_store(target,role,stage=stage,witness=witness).read() is not None
                           for stage in ('initial','final') for role,witness in (('primary',False),('actor',False),('actor',True))):chat_error=True
                    if self._chat_no_replay_store(target).read() is not None:chat_error=True
                    if self._chat_mixer_store(target).read() is not None:chat_error=True
                    if self._chat_chunk_store_retained(self._chat_normal_input_store(target)):chat_error=True
                    if self._chat_chunk_store_retained(self._chat_dispatcher_store(target)):chat_error=True
                    if self._chat_composition_store(target).read() is not None or self._chat_peer_state_retained(target) or self._chat_application_retained(target):chat_error=True
                    if self._chat_cleanup_admission_store(target).read() is not None:chat_error=True
                    if self._chat_chunk_store_retained(self._chat_cache_release_store(target)):chat_error=True
                    if any(self._chat_chunk_store_retained(self._chat_script_source_store(target,role,witness=witness,stage=stage))
                           for role,witness in (('primary',False),('actor',False),('actor',True))
                           for stage in (('active',) if witness else ('active','erase','final'))):chat_error=True
                    if self._chat_background_store(target).read() is not None:chat_error=True
                    if self._chat_flow_inputs_store(target).read() is not None or self._chat_witness_store(target).read() is not None:chat_error=True
                    if self._chat_peer_input_store(target).read() is not None or self._chat_peer_send_store(target).read() is not None:chat_error=True
                    if self._chat_peer_distant_store(target).read() is not None:chat_error=True
                    if self._chat_profile_store(target).read() is not None:chat_error=True
                    if self._chat_erase_restore_store(target).read() is not None:chat_error=True
                    lifetime=self._chat_cache_lifetime_store(target).read()
                    if lifetime is not None:chat_error=True
                    owned=self._chat_capture_store(target).read()
                    if owned is not None and lifetime is None:
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
                _need(not snapshot_error and not audio_error and not create_error and not self._assets_files_owned(target) and not self._create_management(target).owned() and not self._create_picker_owned(target) and not self._create_models_owned(target) and not self._create_feature_owned(target) and not self._avatar_urls_owned(target) and not self._avatar_favorites_owned(target)
                      and not feature_error and not script_error and not probe_error and not origin_error and not chat_error and PrivateFeatureState(state).read() is None
                      and self._lifecycle_back_store(target).read() is None
                      and (self._lifecycle_world_store(target,create=False) is None or self._lifecycle_world_store(target,create=False).read() is None)
                      and not self._lifecycle_background_owned(target)
                      and (self._audio_page_store(target,create=False) is None or self._audio_page_store(target,create=False).read() is None)
                      and not self._audio_capture_owned(target)
                      and self._script_restart_inputs_store(target).read() is None
                      and self._script_restart_store(target).read() is None
                      and self._script_files_store(target).read() is None and self._account_probe_store(target).read() is None
                      and self._account_origin_store(target).read() is None and self._chat_capture_store(target).read() is None
                      and self._chat_cache_lifetime_store(target).read() is None
                      and all(self._chat_cache_absence_store(target,role,stage=stage,witness=witness).read() is None
                              for stage in ('initial','final') for role,witness in (('primary',False),('actor',False),('actor',True)))
                      and self._chat_no_replay_store(target).read() is None
                      and self._chat_mixer_store(target).read() is None
                      and not self._chat_chunk_store_retained(self._chat_normal_input_store(target))
                      and not self._chat_chunk_store_retained(self._chat_dispatcher_store(target))
                      and self._chat_composition_store(target).read() is None and not self._chat_peer_state_retained(target) and not self._chat_application_retained(target)
                      and self._chat_cleanup_admission_store(target).read() is None
                      and not self._chat_chunk_store_retained(self._chat_cache_release_store(target))
                      and not any(self._chat_chunk_store_retained(self._chat_script_source_store(target,role,witness=witness,stage=stage))
                                  for role,witness in (('primary',False),('actor',False),('actor',True))
                                  for stage in (('active',) if witness else ('active','erase','final')))
                      and self._chat_background_store(target).read() is None
                      and self._chat_flow_inputs_store(target).read() is None and self._chat_witness_store(target).read() is None
                      and self._chat_peer_input_store(target).read() is None and self._chat_peer_send_store(target).read() is None
                      and self._chat_peer_distant_store(target).read() is None
                      and not self._emote_image_journals(target)
                      and self._emote_view_store(target).read() is None
                      and self._emote_scene_store(target).read() is None
                      and all(self._emote_world_render_store(target, role).read() is None for role in ('primary','actor'))
                      and self._emote_input_store(target).read() is None
                      and all(self._emote_source_store(target, role).read() is None for role in ('primary', 'actor'))
                      and all(self._emote_lifetime_store(target, role).read() is None for role in ('primary', 'actor'))
                      and self._emote_background_store(target).read() is None
                      and self._chat_profile_store(target).read() is None
                      and self._chat_erase_restore_store(target).read() is None
                      and all(self._chat_samples_store(target,role,erased=erased,witness=witness).read() is None
                              for erased in (False,True) for role,witness in (('primary',False),('actor',False),('actor',True))))
            else:
                _need(not snapshot_error and not audio_error and not create_error and not feature_error and not script_error and not probe_error and not origin_error and not chat_error)
            return result

    return PicoBoundAdapter(args.kind)
