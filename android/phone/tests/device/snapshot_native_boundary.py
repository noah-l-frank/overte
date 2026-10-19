"""Synthetic W3C/SDK boundary, actual Phone flow, verifier and private file scripts.

Images supplied by host tests are synthetic. No app, target, renderer or device
is executed and this fixture cannot provide product/device acceptance.
"""
# SPDX-License-Identifier: Apache-2.0
import copy
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from adb_transport import AdbTransport
from adapters.normal_ui import W3C_ELEMENT

PACKAGE = 'io.github.noah_be.overte.phone'
SELECTOR = 'test-only-appium'
PREFIX = 'parity-0123456789abcdef-still-png'
SDK = r'''#!/usr/bin/env python3
import os,shlex,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
assert args[:3]==['-s','test-only-native-target','exec-out'] and len(args)==4
remote=shlex.split(args[3])
assert remote[:4]==['run-as','io.github.noah_be.overte.phone','sh','-c']
assert remote[5]=='overte-snapshot-files'
result=subprocess.run(['sh','-c',remote[4],*remote[5:]],
    cwd=Path(os.environ['OVERTE_PHONE_SNAPSHOT_TEST_APP']),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
sys.stdout.buffer.write(result.stdout)
raise SystemExit(0)
'''


class NativeSnapshotPhone:
    def __init__(self, root, mutation='', fixtures=None):
        self.root, self.mutation, self.fixtures = Path(root), mutation, fixtures
        self.process = '31415:2718281828'
        self.clock = 0.0
        self.clock_scale = 1
        self.screen, self.last_screen = None, 'settings'
        self.page = 1
        self.mode, self.format, self.field = 'animated', 'webp', ''
        self.popup, self.capturing = None, False
        self.popup_reads_pending = 0
        self.calls, self.inputs, self.reports = [], [], []
        self.releases, self.captures = 0, 0
        self.app = self.root / 'synthetic app root'
        self.files = self.app / 'files/Snapshots'
        self.files.mkdir(parents=True)
        self.artifacts = self.root / 'artifacts'
        self.sdk = self.root / 'adb.py'
        self.sdk.write_text(SDK)
        self.sdk.chmod(0o700)
        names = ['tablet.open', 'nav.home', 'nav.close', 'SNAP', 'tabletPage.1', 'tabletPage.2',
                 'snapshotName', 'snapshotMode', 'snapshotFormat', 'snapshotCapture', 'snapshotCancelCapture']
        names += ['snapshotMode.option.' + value for value in ('still', 'animated', 'panorama', 'cubemap')]
        names += ['snapshotFormat.option.' + value for value in ('png', 'jpg', 'webp')]
        self.references = {name: 's' + str(index) for index, name in enumerate(names)}
        self.by_reference = {value: key for key, value in self.references.items()}

    def visible(self, name):
        if name == 'tablet.open': return self.screen is None
        if name == 'nav.close': return self.screen is not None and self.popup is None
        if name == 'nav.home': return self.screen not in (None, 'home') and self.popup is None
        if name == 'SNAP': return self.screen == 'home' and self.page == 2
        if name.startswith('tabletPage.'): return self.screen == 'home' and name in self.references
        if '.option.' in name: return self.popup is not None and name.startswith(self.popup + '.option.')
        if name == 'snapshotCancelCapture': return self.screen == 'snapshot' and self.capturing and self.popup is None
        return self.screen == 'snapshot' and self.popup is None and name in self.references

    def call(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path.endswith('/elements'):
            name = body['value'].removeprefix(PACKAGE + ':id/')
            if self.popup and name.startswith(self.popup + '.option.') and self.popup_reads_pending:
                self.popup_reads_pending -= 1
                return []
            return [{W3C_ELEMENT: self.references[name]}] if self.visible(name) else []
        if '/element/' in path:
            reference = path.split('/element/', 1)[1].split('/')[0]
            name = self.by_reference[reference]
            if path.endswith('/displayed'): return self.visible(name)
            if path.endswith('/enabled'):
                return not self.capturing if name in ('snapshotCapture', 'snapshotMode') else True
            if path.endswith('/attribute/checked'):
                if self.mutation == 'malformed-checked': return 'checked'
                return str(name.rsplit('.', 1)[1] ==
                           (self.mode if self.popup == 'snapshotMode' else self.format)).lower()
            if path.endswith('/clear'):
                self.field = ''
                return None
            if path.endswith('/value'):
                if self.mutation != 'name-ignored': self.field = body['text']
                return None
            if path.endswith('/click'):
                self.inputs.append(name)
                if name == 'tablet.open': self.screen = 'home' if self.mutation == 'reopen-home' else self.last_screen
                elif name == 'nav.home': self.screen = 'home'
                elif name == 'nav.close': self.last_screen, self.screen = self.screen, None
                elif name.startswith('tabletPage.'): self.page = int(name.rsplit('.', 1)[1])
                elif name == 'SNAP':
                    if self.mutation != 'entry-ignored': self.screen = 'snapshot'
                    if self.mutation == 'partial-entry-error':
                        raise RuntimeError('synthetic delivery failed after opening review')
                elif name in ('snapshotMode', 'snapshotFormat'):
                    self.popup = name
                    self.popup_reads_pending = 3 if self.mutation == 'delayed-popup' else 0
                elif '.option.' in name:
                    value = name.rsplit('.', 1)[1]
                    if name.startswith('snapshotMode') and self.mutation != 'mode-ignored': self.mode = value
                    if name.startswith('snapshotFormat') and self.mutation != 'format-ignored': self.format = value
                    self.popup = None
                elif name == 'snapshotCapture': self.take()
                elif name == 'snapshotCancelCapture': self.capturing = False
                return None
        if method == 'DELETE' and path.endswith('/actions'):
            self.releases += 1
            return None
        if method == 'DELETE' and path == '/session/owned-session':
            if self.mutation == 'session-delete-error': raise RuntimeError('synthetic Appium delete failed')
            return None
        raise AssertionError('Unexpected synthetic W3C endpoint')

    def execute(self, session, operation, values):
        assert session == 'owned-session' and operation == 'mobile: terminateApp'
        raise RuntimeError('Synthetic terminateApp failure must not count as process stop')

    def take(self):
        self.captures += 1
        if self.mutation == 'ack-only': return
        self.capturing = self.mutation == 'capture-pending'
        if not self.capturing:
            formats = (self.format, 'gif') if self.mode == 'animated' else (self.format,)
            for extension in formats:
                if self.mutation == 'missing-gif' and extension == 'gif': continue
                label = ('gif' if extension == 'gif' else 'still-' + self.format
                         if self.mode == 'still' else self.mode)
                payload = self.fixtures[label] if self.fixtures is not None else b'original synthetic file bytes'
                if self.mutation == 'corrupt': payload = b'not an image'
                ticket = 'wrong-ticket' if self.mutation == 'wrong-ticket' and extension == 'gif' else 'snap_1792368000000_' + str(self.captures)
                (self.files / (self.field + '-' + ticket + '.' + extension)).write_bytes(payload)
        if self.mutation != 'keep-review-open':
            self.last_screen, self.screen = 'snapshot', None

    def sleep(self, seconds): self.clock += seconds * self.clock_scale


def attach(test, appium, *, mutation='', fixtures=None):
    """Keep the caller's original SH009 verifier and installed-byte observations."""
    native = NativeSnapshotPhone(test.root, mutation, fixtures)
    instance, target = test.appium_instance()
    target.update(scene={'kind': 'android-debug-e2e'},
        probe={'kind': 'android-run-as', 'relativePath': instance.ANDROID_DEBUG_PROBE},
        clientControl={'kind': 'android-run-as-command', 'relativePath': instance.ANDROID_CLIENT_COMMAND})
    path = test.root / 'phone-appium-session.json'
    instance.state_path = lambda _selector: path
    state = {'sessionId': 'owned-session', 'generation': 1,
             'targetFingerprint': instance.snapshot_fingerprint(target)}
    instance.save_session(SELECTOR, state)
    ui_class = appium.PhoneSnapshotUI
    sdk = AdbTransport(str(native.sdk))
    for boundary in (
            patch.dict(os.environ, {'OVERTE_PHONE_NORMAL_SNAPSHOT': '1',
                'OVERTE_DEVICE_ARTIFACT_DIR': str(native.artifacts),
                'OVERTE_PHONE_SNAPSHOT_TEST_APP': str(native.app)}),
            patch.object(test.adb, 'execute_bytes', side_effect=sdk.execute_bytes, create=True),
            patch.object(appium.AppiumAdapter, 'ensure_session',
                         side_effect=lambda _selector: (native, 'owned-session', instance.read_session(SELECTOR))),
            patch.object(instance, 'query_app_state', return_value=4),
            patch.object(instance, 'process_state', side_effect=lambda *_arguments:
                         {'running': True, 'identity': native.process}),
            patch.object(appium, 'PhoneSnapshotUI', side_effect=lambda client, session, check:
                ui_class(client, session, check, timeout=0.4, monotonic=lambda: native.clock, sleep=native.sleep))):
        boundary.start()
        test.addCleanup(boundary.stop)
    native.invoke = lambda operation, values=None: instance.invoke(SELECTOR, operation, values or {})
    return instance, target, native, path


@contextmanager
def cleanup_boundary(test, native, *, stopped=True):
    """Actual force-stop/wait code; only Android process and Appium seams vary."""
    original = test.adb.shell
    def shell(selector, *arguments, **values):
        assert selector == 'test-only-native-target'
        if arguments in (('am', 'force-stop', PACKAGE), ('pidof', '-s', PACKAGE)):
            test.adb.events.append(arguments)
            return '' if arguments[0] == 'am' or stopped else '31415'
        return original(selector, *arguments, **values)
    clock = SimpleNamespace(monotonic=lambda: native.clock,
                            sleep=lambda seconds: setattr(native, 'clock', native.clock + seconds * 20))
    with ExitStack() as stack:
        stack.enter_context(patch.object(test.adb, 'require_connected', create=True))
        stack.enter_context(patch.object(test.adb, 'shell', side_effect=shell))
        stack.enter_context(patch('adapters.android.adapter.time', clock))
        stack.enter_context(patch('adapters.shared_appium.adapter.WebDriver', return_value=native))
        yield
