"""Source-owned native Qt field events, never installed-code or feature proof.

UIKit controls receive ordinary W3C clicks. Only replacing/submitting the already
focused real Qt address or owned Snapshot name field uses this closed E2E
transport. A process/nonce
join is deliberately not a cryptographic association with installed code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import math
import re
import time
import uuid
from urllib.request import Request, urlopen

from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import AppiumAdapter

CONTROLS = frozenset({'hud.goto', 'hud.tablet', 'address.field', 'address.go',
    'address.cancel', 'address.back', 'tablet.home', 'tablet.close', 'tablet.places',
    'places.back', 'places.forward', 'snapshot.entry', 'snapshot.name', 'snapshot.mode',
    'snapshot.format', 'snapshot.capture', 'snapshot.cancel'} | {'tablet.page.' + str(page) for page in range(1, 33)}
    | {'snapshot.mode.' + value for value in ('still', 'animated', 'panorama', 'cubemap')}
    | {'snapshot.format.' + value for value in ('png', 'jpg', 'webp')})
SNAPSHOT_CHOICES = frozenset(value for value in CONTROLS
                           if value.startswith(('snapshot.mode.', 'snapshot.format.')))


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0
    except ValueError:
        return False


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 2**53 - 1


def _fresh(value, now_ms):
    return (type(value) in (int, float) and math.isfinite(value)
            and -1000 <= now_ms - value <= 3000)


def observation(value, pid, now_ms=None):
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'instance', 'frameSpace',
            'processId', 'sampleEpochMs', 'elapsedMs', 'lastSequence', 'tabletShown', 'ready', 'controls'}
            or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
            or not _uuid(value['instance']) or value['frameSpace'] != 'qt-window-logical'
            or not _integer(value['processId'], 1) or value['processId'] != pid
            or not _fresh(value['sampleEpochMs'], now_ms)
            or not _integer(value['elapsedMs']) or not _integer(value['lastSequence'])
            or type(value['tabletShown']) is not bool or value['ready'] is not True
            or not isinstance(value['controls'], list) or len(value['controls']) > len(CONTROLS)):
        raise NativeUIError('Native iOS input observation is invalid')
    seen, tokens = set(), set()
    for control in value['controls']:
        fields = {'id', 'token', 'enabled', 'focused', 'frame'}
        if isinstance(control, dict) and isinstance(control.get('id'), str) and control['id'] in SNAPSHOT_CHOICES:
            fields.add('checked')
        if (not isinstance(control, dict) or set(control) != fields
                or not isinstance(control['id'], str) or control['id'] not in CONTROLS or control['id'] in seen
                or not _uuid(control['token']) or control['token'] in tokens
                or type(control['enabled']) is not bool or type(control['focused']) is not bool):
            raise NativeUIError('Native iOS input controls are invalid')
        if control['id'] in SNAPSHOT_CHOICES and type(control['checked']) is not bool:
            raise NativeUIError('Native iOS Snapshot choice state is invalid')
        frame = control['frame']
        if (not isinstance(frame, dict) or set(frame) != {'x', 'y', 'width', 'height'}
                or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 10000
                       for n in frame.values()) or frame['width'] <= 0 or frame['height'] <= 0):
            raise NativeUIError('Native iOS input frame is invalid')
        seen.add(control['id'])
        tokens.add(control['token'])
    return value


class NativeInput:
    def __init__(self, client, session, target, observe_process, *,
                 monotonic=time.monotonic, sleep=time.sleep):
        if (not isinstance(session, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', session) is None
                or not callable(observe_process)
                or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
                or type(target['nativeUiObservation']['version']) is not int):
            raise NativeUIError('Native iOS input requires an explicit native observation session')
        self.client, self.session, self.target = client, session, target
        self.observe_process, self.monotonic, self.sleep = observe_process, monotonic, sleep
        self.process, self.instance = None, None
        self.last_clock = None

    def _check(self):
        process = self.observe_process()
        if (not isinstance(process, dict) or set(process) != {'bundleId', 'pid', 'foreground'}
                or process['bundleId'] != self.target['appId'] or not _integer(process['pid'], 1)
                or process['foreground'] is not True
                or self.process is not None and process != self.process):
            raise NativeUIError('Native iOS input lost its foreground process')
        self.process = dict(process)

    def _now(self):
        value = self.monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or self.last_clock is not None and value < self.last_clock):
            raise NativeUIError('Native iOS input clock is invalid')
        self.last_clock = value
        return value

    def _request(self, operation, native=None):
        self._check()
        command_id = 'ios-' + uuid.uuid4().hex
        payload = {'schemaVersion': 1, 'commandId': command_id,
                   'action': 'normal-ui-input', 'operation': operation}
        if native is not None:
            payload['input'] = native
        origin = self.target['testBuild']['fixtureOrigin']
        AppiumAdapter.controlled_http_url(origin, 'native input fixture origin')
        body = json.dumps(payload).encode()
        if len(body) > 32768:
            raise NativeUIError('Native iOS input exceeds its bounded transport')
        request = Request(origin + '/e2e-client-command.json', data=body, method='POST',
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=5) as response:
            result = response.read(32769)
            if response.status != 200 or len(result) > 32768 or json.loads(result) != payload:
                raise NativeUIError('Native iOS input fixture changed the request')
        self._check()
        remote = (f"@{self.target['appId']}:documents/"
                  f"{self.target['testBuild']['resultsDirectory']}/ios-normal-ui-request-result.json")
        deadline = self._now() + 5
        for _attempt in range(51):
            self._check()
            encoded = self.client.execute(self.session, 'mobile: pullFile', {'remotePath': remote})
            if not isinstance(encoded, str) or len(encoded) > 131072:
                raise NativeUIError('Native iOS input receipt exceeds its bounded transport')
            try:
                receipt = json.loads(base64.b64decode(encoded, validate=True))
            except (ValueError, UnicodeError):
                receipt = None
            if isinstance(receipt, dict) and receipt.get('commandId') == command_id:
                key = 'observation' if operation == 'observe' else 'status'
                if (set(receipt) != {'schemaVersion', 'commandId', key}
                        or type(receipt['schemaVersion']) is not int or receipt['schemaVersion'] != 1):
                    raise NativeUIError('Native iOS input receipt has an invalid schema')
                self._check()
                return receipt[key]
            if self._now() >= deadline:
                break
            self.sleep(0.1)
        raise NativeUIError('Native iOS input did not produce this request receipt')

    def capture(self):
        value = observation(self._request('observe'), self.process['pid'])
        if self.instance is not None and value['instance'] != self.instance:
            raise NativeUIError('Native iOS input instance changed')
        self.instance = value['instance']
        return value

    def edit(self, operation, text=None, *, field='address.field'):
        if (field not in {'address.field', 'snapshot.name'} or operation not in {'replace', 'submit'}
                or operation == 'submit' and (text is not None or field != 'address.field')):
            raise NativeUIError('Native iOS input operation is invalid')
        if operation == 'replace':
            try:
                valid = (isinstance(text, str) and len(text.encode('utf-16-le')) // 2 <= 4096
                         and all(ord(character) >= 32 and ord(character) != 127 for character in text))
            except UnicodeError:
                valid = False
            if not valid:
                raise NativeUIError('Native iOS field text is invalid')
            if field == 'snapshot.name':
                from contracts import validate_operation_arguments
                validate_operation_arguments('snapshot.files', {'prefix': text})
        observed = self.capture()
        fields = [c for c in observed['controls'] if c['id'] == field and c['focused'] and c['enabled']]
        if len(fields) != 1:
            raise NativeUIError('Native iOS input requires the actual focused requested field')
        command = {'schemaVersion': 1, 'commandId': str(uuid.uuid4()), 'instance': observed['instance'],
            'sequence': observed['lastSequence'] + 1, 'observedElapsedMs': observed['elapsedMs'],
            'fieldToken': fields[0]['token'], 'operation': operation}
        if operation == 'replace':
            command['text'] = text
        value = self._request('edit', command)
        if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'commandId', 'instance', 'sequence',
                'performed', 'processId', 'sampleEpochMs'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['commandId'] != command['commandId'] or value['instance'] != self.instance
                or not _integer(value['sequence'], 1) or value['sequence'] != command['sequence']
                or not _integer(value['processId'], 1) or value['processId'] != self.process['pid']
                or value['performed'] is not True or not _fresh(value['sampleEpochMs'], time.time() * 1000)):
            raise NativeUIError('Native iOS field input was not freshly delivered')
        return {'performed': True}
