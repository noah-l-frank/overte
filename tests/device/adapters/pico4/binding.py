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
            _need(not cleanup_only)
            _need(_inputs(args) == frozen)
            current = verifier.verify_candidate(args)
            _need(current == candidate and _inputs(args) == frozen)
            return current

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
                _need(not cleanup_only and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(NAVIGATION_OPERATIONS)
            if configured_snapshot(os.environ) is not None:
                _need(not cleanup_only and self.pico_configuration is not None
                      and candidate['e2e_input_layer'] is True)
                values.extend(SNAPSHOT_OPERATIONS)
            return sorted(set(values))

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
            _need(not cleanup_only and self.pico_configuration is not None
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
                else:
                    result = super().invoke(target, operation, values)
            finally:
                self._installation(target)
            return result

        @_private
        def cleanup(self, target):
            # No receipt gate and no identity claim. Keep base teardown intact.
            result = super().cleanup(target)
            # The canonical teardown has now confirmed force-stop. Retire the
            # owned host intent even when a partial input invalidated receipts.
            if self.pico_configuration is not None:
                discard_stopped_state(self._navigation_path(target))
                for path in self._snapshot_paths(target):
                    discard_stopped_state(path)
            return result

    return PicoBoundAdapter(args.kind)
