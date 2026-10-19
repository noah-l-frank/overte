"""Normal Pico VR-tablet Go To/history; input acknowledgements are not verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from contracts import validate_operation_arguments
from navigation_observation import OPERATIONS, viewpoint_urls
from adapters.token_script_ui import script_control, metadata_fields, validate_metadata

UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CONTROL_IDS = {'navigation.goto', 'navigation.address', 'navigation.back',
    'navigation.forward', 'tablet.home', 'snapshot.entry', 'snapshot.name', 'snapshot.mode',
    'snapshot.format', 'snapshot.capture', 'snapshot.cancel'} | {'tablet.page.' + str(n) for n in range(1, 33)}
SNAPSHOT_CHOICES = {'snapshot.mode.' + mode for mode in ('still', 'animated', 'panorama', 'cubemap')} | {
    'snapshot.format.' + value for value in ('png', 'jpg', 'webp')}
CONTROL_IDS |= SNAPSHOT_CHOICES
MAX_INTEGER = 9007199254740991


class NavigationError(RuntimeError):
    def __init__(self):
        super().__init__('OVT_PICO_NAVIGATION_REJECTED')


def need(condition):
    if not condition:
        raise NavigationError()


def integer(value):
    return type(value) is int and 0 <= value <= MAX_INTEGER


def identifier(value):
    return isinstance(value, str) and UUID.fullmatch(value) is not None


def decode(raw, limit=262144):
    need(isinstance(raw, str) and len(raw.encode('utf-8')) <= limit)

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result)
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _value: (_ for _ in ()).throw(NavigationError()))
    except (ValueError, UnicodeError):
        raise NavigationError() from None


def validate_snapshot(value, process_id, epoch_ms):
    fields = {'schemaVersion', 'bridgeId', 'generation', 'processId', 'elapsedMs',
        'updatedEpochMs', 'lastCommandSequence', 'open', 'ready', 'controls'}
    if type(value) is dict and 'featureControlsVersion' in value:
        fields.add('featureControlsVersion')
        need(type(value['featureControlsVersion']) is int and value['featureControlsVersion'] == 1)
    need(type(value) is dict and set(value) == fields
         and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and identifier(value['bridgeId']) and identifier(value['generation'])
         and integer(value['processId']) and value['processId'] == process_id
         and integer(value['elapsedMs']) and integer(value['lastCommandSequence'])
         and integer(value['updatedEpochMs']) and integer(epoch_ms)
         and -500 <= epoch_ms - value['updatedEpochMs'] <= 5000
         and type(value['open']) is bool and type(value['ready']) is bool
         and (not value['ready'] or value['open'])
         and type(value['controls']) is list and len(value['controls']) <= 384)
    ids, tokens = set(), set()
    for control in value['controls']:
        need(type(control) is dict and isinstance(control.get('id'), str))
        fields = {'id', 'token', 'enabled', 'focused'}
        if script_control(control['id']):
            need(value.get('featureControlsVersion') == 1)
            fields |= metadata_fields(control['id'])
        if control['id'] in SNAPSHOT_CHOICES:
            fields.add('checked')
        need(set(control) == fields
             and isinstance(control['id'], str) and (control['id'] in CONTROL_IDS or script_control(control['id']))
             and identifier(control['token']) and control['id'] not in ids
             and control['token'] not in tokens and type(control['enabled']) is bool
             and type(control['focused']) is bool)
        if control['id'] in SNAPSHOT_CHOICES:
            need(type(control['checked']) is bool)
        if script_control(control['id']):
            validate_metadata(control)
        ids.add(control['id']); tokens.add(control['token'])
    need(value['ready'] or not value['controls'])
    return value


def configured_scene(environment):
    opt = environment.get('OVERTE_PICO_NORMAL_NAVIGATION', '0')
    need(opt in {'0', '1'})
    if opt == '0':
        return None
    need(environment.get('OVERTE_ANDROID_E2E_DEBUG') == '1'
         and environment.get('OVERTE_PICO_OPENXR_INPUT') == '1')
    scene = environment.get('OVERTE_E2E_SCENE_URL')
    viewpoint_urls(scene)
    return scene


def discard_stopped_state(path):
    """Retire only the fixed target state after native cleanup confirmed stop."""
    path = Path(path)
    need(path.is_absolute() and path.parent.resolve(strict=True) == path.parent)
    info = path.parent.lstat()
    need(stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o077 and info.st_uid == os.getuid())
    # Unlink the managed entry itself; never follow an invalid leftover link.
    path.unlink(missing_ok=True)


class PicoNavigation:
    def __init__(self, io, state_path, identity, process_identity, scene_url,
                 *, monotonic=time.monotonic, sleep=time.sleep):
        self.io, self.path = io, Path(state_path)
        self.monotonic, self.sleep = monotonic, sleep
        self.urls = set(viewpoint_urls(scene_url).values())
        need(type(identity) is dict and set(identity) == {'schemaVersion', 'sourceRevision',
            'artifactSha256', 'installedCandidateVerified'}
            and type(identity['schemaVersion']) is int and identity['schemaVersion'] == 1
            and identity['installedCandidateVerified'] is True
            and isinstance(identity['sourceRevision'], str)
            and re.fullmatch('[0-9a-f]{40}', identity['sourceRevision']) is not None
            and isinstance(identity['artifactSha256'], str)
            and re.fullmatch('[0-9a-f]{64}', identity['artifactSha256']) is not None
            and isinstance(process_identity, str)
            and re.fullmatch('[1-9][0-9]{0,9}:[!-~]{1,150}', process_identity) is not None)
        self.process_id = int(process_identity.split(':', 1)[0])
        self.context = {'schemaVersion': 1, 'sourceRevision': identity['sourceRevision'],
            'artifactSha256': identity['artifactSha256'], 'processIdentity': process_identity,
            'sceneSha256': hashlib.sha256(scene_url.encode()).hexdigest()}
        self._private_parent()
        self.state = self._load()
        if self.state is not None:
            need(set(self.state) == set(self.context) | {'bridgeId', 'tabletOwned'}
                 and type(self.state['schemaVersion']) is int
                 and all(self.state.get(key) == value for key, value in self.context.items())
                 and identifier(self.state['bridgeId']) and type(self.state['tabletOwned']) is bool)

    def _private_parent(self):
        need(self.path.is_absolute() and self.path.parent.resolve(strict=True) == self.path.parent)
        info = self.path.parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o077 and info.st_uid == os.getuid())

    def _load(self):
        try:
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                 and info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_size <= 4096)
            value = decode(stream.read(4097), limit=4096)
        need(type(value) is dict)
        return value

    def _mark(self, snapshot, owned):
        self._private_parent()
        value = self.context | {'bridgeId': snapshot['bridgeId'], 'tabletOwned': owned}
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, sort_keys=True); stream.write('\n')
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.state = value

    def snapshot(self):
        self.io.guard()
        value, now = self.io.read()
        value = validate_snapshot(value, self.process_id, now)
        self.io.guard()
        if self.state is not None:
            need(value['bridgeId'] == self.state['bridgeId'])
        return value

    @staticmethod
    def control(snapshot, control_id, *, enabled=True):
        for value in snapshot['controls']:
            if value['id'] == control_id and (not enabled or value['enabled']):
                return value
        return None

    def input(self, control_id, action='activate', text=None, *, source=None):
        # SDK/package verification can take longer than the native input's
        # freshness window. Bind bytes first, then capture the current UI.
        self.io.bind_input()
        snapshot = self.snapshot()
        control = self.control(snapshot, control_id)
        need(snapshot['ready'] and control is not None and snapshot['lastCommandSequence'] < MAX_INTEGER)
        if source is not None:
            need(control.get('sourceUrl') == source)
        command = {'schemaVersion': 1, 'commandId': str(uuid.uuid4()),
            'bridgeId': snapshot['bridgeId'], 'generation': snapshot['generation'],
            'sequence': snapshot['lastCommandSequence'] + 1,
            'observedElapsedMs': snapshot['elapsedMs'], 'controlId': control_id,
            'controlToken': control['token'], 'action': action}
        if action == 'replace':
            if control_id == 'navigation.address':
                need(text in self.urls)
            elif control_id == 'snapshot.name':
                validate_operation_arguments('snapshot.files', {'prefix': text})
            elif control_id == 'scripts.url.field':
                from scripts_observation import script_url
                from create_observation import owned_url
                need(type(text) is str)
                if '/script-management/' in text:
                    script_url(text, missing=text.endswith('/missing.js'))
                else:
                    owned_url(text, {'observer.js'})
            else:
                raise NavigationError()
            command['text'] = text
        self.io.guard()
        # The owning transport writes exactly once, then only polls status.
        try:
            status, now = self.io.send(command)
        finally:
            self.io.bind_input()
        self.io.guard()
        need(type(status) is dict and set(status) == {'schemaVersion', 'bridgeId', 'commandId',
            'sequence', 'performed', 'error', 'processId', 'updatedEpochMs'}
            and type(status['schemaVersion']) is int and status['schemaVersion'] == 1
            and status['bridgeId'] == snapshot['bridgeId']
            and status['commandId'] == command['commandId'] and type(status['sequence']) is int
            and status['sequence'] == command['sequence'] and status['performed'] is True
            and status['error'] == '' and type(status['processId']) is int
            and status['processId'] == self.process_id and integer(status['updatedEpochMs'])
            and integer(now) and -500 <= now - status['updatedEpochMs'] <= 5000)

    def wait(self, predicate, seconds=15):
        deadline = self.monotonic() + seconds
        while True:
            value = self.snapshot()
            if predicate(value):
                return value
            need(self.monotonic() < deadline)
            self.sleep(0.1)

    def open(self):
        snapshot = self.snapshot()
        owned = self.state is not None and self.state['tabletOwned']
        need(not snapshot['open'] or owned)
        if not snapshot['open']:
            self._mark(snapshot, True)  # Persist gesture intent before input.
            self.controller('tablet.open')
        self.wait(lambda value: value['open'] and value['ready'])

    def editor(self):
        self.open()
        snapshot = self.snapshot()
        if self.control(snapshot, 'navigation.address'):
            return
        if self.control(snapshot, 'tablet.home'):
            self.input('tablet.home')
            snapshot = self.wait(lambda value: self.control(value, 'navigation.goto')
                or any(row['id'].startswith('tablet.page.') for row in value['controls']))
        pages = sorted((row['id'] for row in snapshot['controls'] if row['id'].startswith('tablet.page.')),
                       key=lambda name: int(name.rsplit('.', 1)[1]))
        for page in [None, *pages]:
            if page is not None:
                self.input(page)
            until = self.monotonic() + 0.6
            while True:
                snapshot = self.snapshot()
                if self.control(snapshot, 'navigation.goto'):
                    self.input('navigation.goto')
                    self.wait(lambda value: self.control(value, 'navigation.address'))
                    return
                if self.monotonic() >= until:
                    break
                self.sleep(0.1)
        raise NavigationError()

    def close(self):
        if self.state is None:
            return
        snapshot = self.snapshot()
        if self.state['tabletOwned'] and snapshot['open']:
            self.controller('tablet.close')
            self.wait(lambda value: not value['open'])
        self._private_parent()
        self.path.unlink(missing_ok=True)
        self.state = None

    def controller(self, operation):
        self.io.bind_input()
        try:
            self.io.controller(operation)
        finally:
            self.io.bind_input()

    def invoke(self, operation, arguments):
        need(operation in OPERATIONS)
        values = validate_operation_arguments(operation, arguments)
        if operation == 'places.open':
            self.editor()
        elif operation == 'places.goto':
            need(values['url'] in self.urls)
            self.editor()
            self.input('navigation.address')
            self.input('navigation.address', 'replace', values['url'])
            self.input('navigation.address', 'submit')
        elif operation in {'places.back', 'places.forward'}:
            self.editor()
            control_id = 'navigation.back' if operation == 'places.back' else 'navigation.forward'
            self.wait(lambda value: self.control(value, control_id))
            self.input(control_id)
        else:
            self.close()
        return {'performed': True}


class NativeNavigationIO:
    """Only the original candidate-bound Pico adapter may construct this IO."""
    DIRECTORY = 'files/overte-e2e/navigation-ui-'

    def __init__(self, adapter, target, process_identity, controller):
        self.adapter, self.target, self.identity = adapter, target, process_identity
        self._controller = controller

    def guard(self):
        self.adapter.require_same_process(self.target, self.identity, 'normal navigation input')
        need(self.adapter.require_pico_session_identity(self.target) == self.identity
             and self.adapter.adb.foreground_package(self.target) == 'org.overte.pico')

    def bind_input(self):
        self.adapter._installation(self.target)
        self.guard()

    def _read(self, kind):
        return self.adapter.adb.read_debug_app_file(self.target, 'org.overte.pico',
            self.DIRECTORY + kind + '.json', attempts=1)

    def read(self):
        attempts, interval = self.adapter.probe_retry_policy()
        for attempt in range(attempts):
            self.guard()
            raw = self._read('observation')
            if raw:
                return decode(raw), self.adapter.adb.epoch_milliseconds(self.target)
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise NavigationError()

    def send(self, command):
        self.guard()
        self.adapter.adb.write_debug_app_file(self.target, 'org.overte.pico',
            self.DIRECTORY + 'command.json', json.dumps(command, sort_keys=True, separators=(',', ':')) + '\n')
        attempts, interval = self.adapter.probe_retry_policy()
        for attempt in range(attempts):
            self.guard()
            raw = self._read('status')
            if raw:
                value = decode(raw)
                need(type(value) is dict)
                if value.get('commandId') == command['commandId']:
                    return value, self.adapter.adb.epoch_milliseconds(self.target)
            if attempt + 1 < attempts:
                time.sleep(interval)
        raise NavigationError()

    def controller(self, operation):
        need(operation in {'tablet.open', 'tablet.close'})
        # Preserve the canonical real OpenXR controller route, including its
        # native session/nonce/sequence and process guards.
        result = self._controller(operation)
        need(type(result) is dict and result.get('performed') is True)
