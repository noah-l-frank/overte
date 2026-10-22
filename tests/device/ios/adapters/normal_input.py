"""Source-owned native Qt field/pointer events, never installed-code or feature proof.

UIKit controls receive ordinary W3C clicks. Only replacing/submitting the already
focused real Qt address/owned fields, and original Graphics slider or
Audio/Graphics scrollbar pointer input and sequenced original Create pointer/field/choice input use this closed E2E transport. A process/nonce
join is deliberately not a cryptographic association with installed code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import math
import re
import time
import uuid
from urllib.request import Request
from ios.adapters.feature_observation import post_request as urlopen

from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import AppiumAdapter
from adapters.token_script_ui import script_control, metadata_fields, validate_metadata
from adapters.token_graphics_ui import graphics_control,metadata_fields as graphics_metadata_fields,validate_metadata as validate_graphics_metadata,on_grid
from adapters.token_chat_ui import metadata as chat_metadata,control_id as chat_control,text as chat_text,same_reference as chat_same_reference
from adapters.token_create_ui import metadata as create_metadata,control_id as create_control,field as create_field,choice as create_choice,ascii_text,same_reference
from adapters.token_login_ui import IDS as LOGIN_IDS, VERSION as LOGIN_VERSION,metadata_fields as login_metadata_fields,validate_metadata as validate_login_metadata
from adapters.native_account_origin import origin_text
from ios.adapters.account_menu import IDS as ACCOUNT_IDS,FIELDS as ACCOUNT_FIELDS,metadata as account_metadata
from ios.adapters.account_preferences import CONTROL_ID as REMEMBER_ID,CONTROL_FIELDS as REMEMBER_FIELDS,control_metadata as remember_metadata
from ios.adapters.view_controls import IDS as VIEW_IDS,FIELDS as VIEW_FIELDS,metadata as view_metadata
from adapters.token_audio_ui import audio_control, metadata_fields as audio_metadata_fields, validate_metadata as validate_audio_metadata
from adapters.token_script_file_ui import (file_control, folder_text,
    metadata_fields as file_metadata_fields, validate_metadata as validate_file_metadata)
from ios.adapters.places_controls import (PROFILES as PLACES_PROFILES,metadata as places_metadata,
    control_id as places_control,text as places_text,FIELDS as PLACES_FIELDS)
from ios.adapters.navigation_dialog_controls import IDS as ERROR_IDS,metadata as error_metadata

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
    fields = {'schemaVersion', 'instance', 'frameSpace', 'processId', 'sampleEpochMs',
              'elapsedMs', 'lastSequence', 'tabletShown', 'ready', 'controls'}
    if type(value) is dict and 'navigationDialogControlsVersion' in value:
        if (type(value['navigationDialogControlsVersion']) is not int or value['navigationDialogControlsVersion']!=1
                or not _integer(value.get('navigationDialogSourceSequence'),1)):
            raise NativeUIError('Native iOS navigation modal source version is invalid')
        fields |= {'navigationDialogControlsVersion','navigationDialogSourceSequence'}
    if type(value) is dict and 'featureControlsVersion' in value:
        if type(value['featureControlsVersion']) is not int or value['featureControlsVersion'] != 1:
            raise NativeUIError('Native iOS feature control version is invalid')
        fields.add('featureControlsVersion')
    if type(value) is dict and 'scriptObservationVersion' in value:
        from adapters.script_ui_inventory import validate as validate_script_inventory
        if (type(value['scriptObservationVersion']) is not int or value['scriptObservationVersion'] != 1
                or not _integer(value.get('scriptSourceSequence'), 1)):
            raise NativeUIError('Original iOS Script observation version or cursor is invalid')
        validate_script_inventory(value.get('scriptInventory'))
        if value['scriptInventory']['tabletShown'] != value.get('tabletShown'):
            raise NativeUIError('Original Script inventory and tablet visibility disagree')
        fields |= {'scriptObservationVersion', 'scriptSourceSequence', 'scriptInventory'}
    if type(value) is dict and 'loginClearInputVersion' in value:
        if type(value['loginClearInputVersion']) is not int or value['loginClearInputVersion']!=1:
            raise NativeUIError('Native iOS login clear input source version is invalid')
        fields.add('loginClearInputVersion')
    if type(value) is dict and 'accountPreferences' in value:
        from ios.adapters.account_preferences import validate as validate_account_preferences
        validate_account_preferences(value['accountPreferences']);fields.add('accountPreferences')
    if type(value) is dict and 'accountMenuControlsVersion' in value:
        if type(value['accountMenuControlsVersion']) is not int or value['accountMenuControlsVersion']!=1:
            raise NativeUIError('Native iOS account menu control version is invalid')
        fields.add('accountMenuControlsVersion')
    if type(value) is dict and 'viewMenuControlsVersion' in value:
        if type(value['viewMenuControlsVersion']) is not int or value['viewMenuControlsVersion']!=1:
            raise NativeUIError('Native iOS View menu control version is invalid')
        fields.add('viewMenuControlsVersion')
    if type(value) is dict and 'fileControlsVersion' in value:
        if type(value['fileControlsVersion']) is not int or value['fileControlsVersion'] != 1:
            raise NativeUIError('Native iOS file control version is invalid')
        fields.add('fileControlsVersion')
    if type(value) is dict and 'audioControlsVersion' in value:
        if type(value['audioControlsVersion']) is not int or value['audioControlsVersion'] != 1:
            raise NativeUIError('Native iOS Audio control version is invalid')
        fields.add('audioControlsVersion')
    if type(value) is dict and 'graphicsControlsVersion' in value:
        if type(value['graphicsControlsVersion']) is not int or value['graphicsControlsVersion']!=1:
            raise NativeUIError('Native iOS Graphics control version is invalid')
        fields.add('graphicsControlsVersion')
    if type(value) is dict and 'placesControlsVersion' in value:
        if (type(value['placesControlsVersion']) is not int or value['placesControlsVersion'] not in PLACES_PROFILES
                or not _integer(value.get('placesSourceSequence'),1)):
            raise NativeUIError('Native iOS Places controls lack their original source sequence')
        fields |= {'placesControlsVersion','placesSourceSequence'}
    if type(value) is dict and 'chatControlsVersion' in value:
        if type(value['chatControlsVersion']) is not int or value['chatControlsVersion']!=1 or not _uuid(value.get('chatGeneration')):
            raise NativeUIError('Native iOS Chat control version/context is invalid')
        fields |= {'chatControlsVersion','chatGeneration'}
    if type(value) is dict and 'createControlsVersion' in value:
        if type(value['createControlsVersion']) is not int or value['createControlsVersion']!=1 or not _uuid(value.get('createGeneration')):
            raise NativeUIError('Native iOS Create control version/context is invalid')
        fields |= {'createControlsVersion','createGeneration'}
    if type(value) is dict and 'loginControlsVersion' in value:
        if type(value['loginControlsVersion']) is not int or value['loginControlsVersion']!=LOGIN_VERSION or not _uuid(value.get('generation')):
            raise NativeUIError('Native iOS login control version/context is invalid')
        fields |= {'loginControlsVersion','generation'}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
            or not _uuid(value['instance']) or value['frameSpace'] != 'qt-window-logical'
            or not _integer(value['processId'], 1) or value['processId'] != pid
            or not _fresh(value['sampleEpochMs'], now_ms)
            or not _integer(value['elapsedMs']) or not _integer(value['lastSequence'])
            or type(value['tabletShown']) is not bool or value['ready'] is not True
            or not isinstance(value['controls'], list) or len(value['controls']) > 384):
        raise NativeUIError('Native iOS input observation is invalid')
    seen, tokens = set(), set()
    for control in value['controls']:
        fields = {'id', 'token', 'enabled', 'focused', 'frame'}
        is_graphics=type(control) is dict and graphics_control(control.get('id')) and value.get('graphicsControlsVersion')==1
        if type(control) is dict and type(control.get('id')) is str and control['id'].startswith('graphics.') and not is_graphics:
            raise NativeUIError('Native iOS Graphics controls lack their source extension')
        is_create=type(control) is dict and type(control.get('id')) is str and control['id'].startswith('create.')
        is_chat=type(control) is dict and type(control.get('id')) is str and control['id'].startswith('chat.')
        is_places=type(control) is dict and control.get('profile') in PLACES_PROFILES.values()
        is_error=type(control) is dict and control.get('id') in ERROR_IDS
        if is_error:
            if value.get('navigationDialogControlsVersion')!=1:raise NativeUIError('Native iOS navigation modal source is missing')
            original=dict(control);original.pop('frame',None);error_metadata(original);fields=set(control)
        elif is_places:
            if control['profile']!=PLACES_PROFILES.get(value.get('placesControlsVersion')):raise NativeUIError('Native iOS Places controls lack their source extension')
            original=dict(control);original.pop('frame',None);places_metadata(original);fields=set(control)
        elif is_chat:
            if value.get('chatControlsVersion')!=1:raise NativeUIError('Native iOS Chat controls lack their source extension')
            original=dict(control);original.pop('frame',None);chat_metadata(original);fields=set(control)
        elif is_create:
            if value.get('createControlsVersion')!=1:raise NativeUIError('Native iOS Create controls lack their source extension')
            original=dict(control);original.pop('frame',None);create_metadata(original);fields=set(control)
        elif type(control) is dict and control.get('id') in VIEW_IDS:
            if value.get('viewMenuControlsVersion')!=1:raise NativeUIError('Native iOS View menu lacks its source extension')
            view_metadata(control);fields |= VIEW_FIELDS
        elif type(control) is dict and control.get('id')==REMEMBER_ID:
            if value.get('accountPreferences',{}).get('accountPreferenceVersion')!=2:
                raise NativeUIError('Native iOS Remember control lacks its preference source')
            remember_metadata(control);fields |= REMEMBER_FIELDS
        elif type(control) is dict and control.get('id') in ACCOUNT_IDS:
            if value.get('accountMenuControlsVersion')!=1:raise NativeUIError('Native iOS account menu lacks its source extension')
            account_metadata(control);fields |= ACCOUNT_FIELDS
        elif type(control) is dict and type(control.get('id')) is str and control['id'] in LOGIN_IDS:
            if value.get('loginControlsVersion')!=LOGIN_VERSION:raise NativeUIError('Native iOS login controls lack their source extension')
            fields |= login_metadata_fields(control['id'])
        elif is_graphics:
            fields |= graphics_metadata_fields(control['id'])
        elif type(control) is dict and audio_control(control.get('id')):
            if value.get('audioControlsVersion') != 1:
                raise NativeUIError('Native iOS Audio controls lack their source extension')
            fields |= audio_metadata_fields(control['id'])
        if type(control) is dict and file_control(control.get('id')):
            if value.get('fileControlsVersion') != 1:
                raise NativeUIError('Native iOS file controls lack their source extension')
            fields |= file_metadata_fields(control['id'], control)
        if type(control) is dict and script_control(control.get('id')):
            if value.get('featureControlsVersion') != 1:
                raise NativeUIError('Native iOS Script controls lack their source extension')
            fields |= metadata_fields(control['id'])
        if isinstance(control, dict) and isinstance(control.get('id'), str) and control['id'] in SNAPSHOT_CHOICES:
            fields.add('checked')
        if (not isinstance(control, dict) or set(control) != fields
                or not isinstance(control['id'], str)
                or not (control['id'] in CONTROLS or script_control(control['id']) or file_control(control['id']) or audio_control(control['id']) or graphics_control(control['id']) or control['id'] in LOGIN_IDS or control['id'] in ACCOUNT_IDS or control['id'] in VIEW_IDS or control['id']==REMEMBER_ID or is_create and create_control(control['id']) or is_chat and chat_control(control['id']) or is_places and places_control(control['id']) or is_error) or control['id'] in seen
                or not _uuid(control['token']) or control['token'] in tokens
                or type(control['enabled']) is not bool or type(control['focused']) is not bool):
            raise NativeUIError('Native iOS input controls are invalid')
        if control['id'] in SNAPSHOT_CHOICES and type(control['checked']) is not bool:
            raise NativeUIError('Native iOS Snapshot choice state is invalid')
        if control['id'] in LOGIN_IDS:
            original=dict(control);original.pop('frame');validate_login_metadata(original)
        elif is_graphics:validate_graphics_metadata(control)
        elif audio_control(control['id']): validate_audio_metadata(control)
        if script_control(control['id']): validate_metadata(control)
        if file_control(control['id']): validate_file_metadata(control)
        frame = control['frame']
        offscreen=is_graphics and control['viewport'] in ('above','below')
        if offscreen:
            if frame is not None:raise NativeUIError('Offscreen Graphics control cannot expose a clickable frame')
            seen.add(control['id']);tokens.add(control['token']);continue
        if (not isinstance(frame, dict) or set(frame) != {'x', 'y', 'width', 'height'}
                or any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 10000
                       for n in frame.values()) or frame['width'] <= 0 or frame['height'] <= 0):
            raise NativeUIError('Native iOS input frame is invalid')
        seen.add(control['id'])
        tokens.add(control['token'])
    return value


class NativeInput:
    def __init__(self, client, session, target, observe_process, *,
                 monotonic=time.monotonic, sleep=time.sleep, native_epoch_ms=None):
        if (not isinstance(session, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', session) is None
                or not callable(observe_process) or native_epoch_ms is not None and not callable(native_epoch_ms)
                or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
                or type(target['nativeUiObservation']['version']) is not int):
            raise NativeUIError('Native iOS input requires an explicit native observation session')
        self.client, self.session, self.target = client, session, target
        self.observe_process, self.monotonic, self.sleep = observe_process, monotonic, sleep
        self.process, self.instance = None, None
        self.last_clock = None
        self.last_receipt = None
        self.native_epoch_ms = native_epoch_ms

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
        self.last_receipt = None
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
                self.last_receipt = deepcopy(receipt)
                return receipt[key]
            if self._now() >= deadline:
                break
            self.sleep(0.1)
        raise NativeUIError('Native iOS input did not produce this request receipt')

    def capture(self, *, native_epoch_ms=None):
        native_epoch_ms = native_epoch_ms or getattr(self, 'native_epoch_ms', None)
        value = self._request('observe')
        if native_epoch_ms is not None and not callable(native_epoch_ms):
            raise NativeUIError('An independent original native clock reader is required')
        epoch = None if native_epoch_ms is None else native_epoch_ms()
        value = observation(value, self.process['pid'], epoch)
        if self.instance is not None and value['instance'] != self.instance:
            raise NativeUIError('Native iOS input instance changed')
        self.instance = value['instance']
        return value

    def clear_login_username(self,*,token):
        observed=self.capture()
        rows=[row for row in observed['controls'] if row['id']=='login.username']
        if (observed.get('loginControlsVersion')!=LOGIN_VERSION or observed.get('loginClearInputVersion')!=1
                or len(rows)!=1 or not rows[0]['enabled'] or not rows[0]['focused'] or not rows[0]['inputReady']
                or rows[0]['token']!=token):
            raise NativeUIError('Native iOS username clear requires the actual focused current source')
        return self.deliver(dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=observed['instance'],
            sequence=observed['lastSequence']+1,observedElapsedMs=observed['elapsedMs'],fieldToken=token,
            operation='clear-login-username'))

    def edit(self, operation, text=None, *, field='address.field', index=None):
        if (field not in {'address.field', 'snapshot.name', 'scripts.url.field', 'script-file.folder', 'script-file.primary','login.server'}
                or operation not in {'replace', 'submit', 'select-index'}
                or operation == 'submit' and (text is not None or field not in {'address.field', 'script-file.folder'})
                or operation == 'select-index' and (text is not None or field != 'script-file.primary'
                    or type(index) is not int or not 0 <= index < 32)
                or operation != 'select-index' and (index is not None or field == 'script-file.primary')):
            raise NativeUIError('Native iOS input operation is invalid')
        if operation == 'replace':
            try:
                valid = (isinstance(text, str) and len(text.encode('utf-16-le')) // 2 <= 4096
                         and all(ord(character) >= 32 and ord(character) != 127 for character in text))
            except UnicodeError:
                valid = False
            if not valid:
                raise NativeUIError('Native iOS field text is invalid')
            if field=='login.server':
                origin_text(text) # Non-secret supported origin only; no credentials on HTTP.
            elif field == 'snapshot.name':
                from contracts import validate_operation_arguments
                validate_operation_arguments('snapshot.files', {'prefix': text})
            elif field == 'script-file.folder':
                folder_text(text)
            elif field == 'scripts.url.field':
                from scripts_observation import script_url
                from create_observation import owned_url
                if '/script-management/' in text:
                    script_url(text, missing=text.endswith('/missing.js'))
                elif '/feature-fixture/' in text:
                    from adapters.normal_script_manager import missing_script_url
                    missing_script_url(text)
                else:
                    owned_url(text, {'observer.js'})
        observed = self.capture()
        if field == 'scripts.url.field' and observed.get('featureControlsVersion') != 1:
            raise NativeUIError('Native iOS Script field lacks its source extension')
        if field=='login.server' and observed.get('loginControlsVersion')!=LOGIN_VERSION:
            raise NativeUIError('Native iOS server field lacks its login extension')
        if file_control(field) and observed.get('fileControlsVersion') != 1:
            raise NativeUIError('Native iOS file field lacks its source extension')
        fields = [c for c in observed['controls'] if c['id'] == field and c['focused'] and c['enabled']]
        if len(fields) != 1:
            raise NativeUIError('Native iOS input requires the actual focused requested field')
        command = {'schemaVersion': 1, 'commandId': str(uuid.uuid4()), 'instance': observed['instance'],
            'sequence': observed['lastSequence'] + 1, 'observedElapsedMs': observed['elapsedMs'],
            'fieldToken': fields[0]['token'], 'operation': operation}
        if operation == 'replace':
            command['text'] = text
        if operation == 'select-index':
            command['index'] = index
        return self.deliver(command)

    def navigation_error_input(self,*,reference):
        from ios.adapters.navigation_dialog_controls import project,same_reference
        row=same_reference(reference,project(self.capture()))
        if not row['enabled'] or not row['inputReady']:raise NativeUIError('Native iOS navigation modal input is unavailable')
        original=reference['scope']
        return self.deliver(dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=original['instance'],
            sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],fieldToken=row['token'],operation='activate'))

    def places_input(self,identifier,action,*,reference,value=None):
        from ios.adapters.places_controls import project,same_reference
        if not places_control(identifier) or identifier=='places.page' or action not in ('activate','replace'):
            raise NativeUIError('Native iOS Places input is invalid')
        observed=project(self.capture());row=same_reference(reference,observed,identifier)
        if not observed['open'] or not row['enabled'] or not row['inputReady']:
            raise NativeUIError('Native iOS Places control is unavailable')
        if action=='replace':
            if identifier not in PLACES_FIELDS or not row['focused']:raise NativeUIError('Native iOS Places field lacks focus')
            places_text(value)
            if identifier=='places.server-url' and value:
                from ios.adapters.places_preferences import origin as places_origin
                places_origin(value)
            if len(value.encode('utf-16-le'))//2>4096:raise NativeUIError('Native iOS Places field exceeds its input bound')
        elif value is not None:raise NativeUIError('Native iOS Places activation has an unexpected value')
        original=reference['scope']
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=original['instance'],
            sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],fieldToken=row['token'],operation=action)
        if action=='replace':command['text']=value
        return self.deliver(command)

    def chat_input(self,identifier,action,*,reference,value=None):
        from ios.adapters.chat_controls import project
        if not chat_control(identifier) or identifier=='chat.page' or action not in ('activate','replace','submit'):
            raise NativeUIError('Native iOS Chat input is invalid')
        observed=project(self.capture());row=chat_same_reference(reference,observed,identifier)
        if not observed['open'] or not observed['ready'] or not row['enabled'] or not row.get('inputReady',True):
            raise NativeUIError('Native iOS Chat control is unavailable')
        if action in ('replace','submit') and (identifier!='chat.input' or not row['focused']):
            raise NativeUIError('Native iOS Chat field lacks actual focus')
        if action=='replace':chat_text(value)
        elif value is not None:raise NativeUIError('Native iOS Chat input has an unexpected value')
        original=reference['scope']
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=original['instance'],
            sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],fieldToken=row['token'],operation=action)
        if action=='replace':command['text']=value
        return self.deliver(command)

    def create_input(self,identifier,action,*,reference,value=None):
        from ios.adapters.create_controls import project
        if not create_control(identifier) or identifier=='create.page' or action not in ('activate','replace','select-index','scroll'):
            raise NativeUIError('Native iOS Create input is invalid')
        observed=project(self.capture());row=same_reference(reference,observed,identifier)
        if not observed['open'] or not observed['ready'] or not row['enabled'] or not row.get('inputReady',True):
            raise NativeUIError('Native iOS Create control is unavailable')
        if action=='replace':
            if not create_field(identifier) or not row['focused']:raise NativeUIError('Native iOS Create field lacks focus')
            ascii_text(value)
        elif action=='select-index':
            if not create_choice(identifier) or type(value) is not int or not 0<=value<row['count']:raise NativeUIError('Native iOS Create choice is invalid')
        elif action=='scroll':
            if identifier!='create.scrollbar' or value not in ('up','down'):raise NativeUIError('Native iOS Create scroll is invalid')
        elif identifier=='create.scrollbar' or value is not None:raise NativeUIError('Native iOS Create activation is invalid')
        original=reference['scope']
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=original['instance'],
            sequence=original['sequence']+1,observedElapsedMs=original['elapsedMs'],fieldToken=row['token'],operation=action)
        if action=='replace':command['text']=value
        elif action=='select-index':command['index']=value
        elif action=='scroll':command['direction']=value
        return self.deliver(command)

    def scroll(self, direction, *, token, field='audio.scrollbar'):
        if direction not in ('up','down') or not _uuid(token) or field not in ('audio.scrollbar','graphics.scrollbar'):
            raise NativeUIError('Native iOS scrollbar input is invalid')
        observed=self.capture();rows=[r for r in observed['controls'] if r['id']==field]
        version='graphicsControlsVersion' if field=='graphics.scrollbar' else 'audioControlsVersion'
        if (observed.get(version)!=1 or len(rows)!=1 or not rows[0]['enabled'] or not rows[0]['inputReady']
                or rows[0].get('viewport','visible')!='visible' or rows[0]['token']!=token):
            raise NativeUIError('Native iOS original scrollbar token is unavailable')
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=observed['instance'],
            sequence=observed['lastSequence']+1,observedElapsedMs=observed['elapsedMs'],
            fieldToken=token,operation='scroll',direction=direction)
        return self.deliver(command)

    def set_value(self,identifier,value,*,token):
        if identifier!='graphics.resolution' or not _uuid(token):
            raise NativeUIError('Native iOS original slider input is invalid')
        observed=self.capture();rows=[r for r in observed['controls'] if r['id']==identifier]
        if (observed.get('graphicsControlsVersion')!=1 or len(rows)!=1 or not rows[0]['enabled']
                or not rows[0]['inputReady'] or rows[0]['viewport']!='visible' or rows[0]['token']!=token
                or not on_grid(value,rows[0])):
            raise NativeUIError('Native iOS original slider token or value is unavailable')
        command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=observed['instance'],
            sequence=observed['lastSequence']+1,observedElapsedMs=observed['elapsedMs'],
            fieldToken=token,operation='set-value',value=value)
        return self.deliver(command)

    def deliver(self, command):
        value = self._request('edit', command)
        clock = getattr(self, 'native_epoch_ms', None)
        epoch = clock() if clock is not None else time.time() * 1000
        def receipt_fresh(captured):
            if clock is None:return _fresh(captured,epoch)
            return (type(captured) in (int,float) and math.isfinite(captured)
                    and type(epoch) in (int,float) and math.isfinite(epoch) and -250<=epoch-captured<=1500)
        if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'commandId', 'instance', 'sequence',
                'performed', 'processId', 'sampleEpochMs'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['commandId'] != command['commandId'] or value['instance'] != self.instance
                or not _integer(value['sequence'], 1) or value['sequence'] != command['sequence']
                or not _integer(value['processId'], 1) or value['processId'] != self.process['pid']
                or value['performed'] is not True or not receipt_fresh(value['sampleEpochMs'])):
            raise NativeUIError('Native iOS field input was not freshly delivered')
        return {'performed': True}
