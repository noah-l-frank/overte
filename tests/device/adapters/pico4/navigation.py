"""Normal Pico VR-tablet Go To/history; input acknowledgements are not verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
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
from adapters.token_lifecycle_ui import ID as LIFECYCLE_ID,text as lifecycle_text,metadata as lifecycle_metadata,same_reference as lifecycle_same_reference
from adapters.token_chat_ui import metadata as chat_metadata,control_id as chat_control,text as chat_text,same_reference as chat_same_reference
from adapters.token_create_ui import metadata as create_metadata,control_id as create_control,field as create_field,choice as create_choice,ascii_text,same_reference
from adapters.token_login_ui import IDS as LOGIN_IDS,VERSION as LOGIN_VERSION,metadata_fields as login_metadata_fields,validate_metadata as validate_login_metadata
from adapters.token_account_menu_ui import IDS as ACCOUNT_MENU_IDS,FIELDS as ACCOUNT_MENU_FIELDS,validate_metadata as validate_account_menu_metadata
from adapters.token_script_ui import script_control, metadata_fields, validate_metadata
from adapters.token_graphics_ui import graphics_control,metadata_fields as graphics_metadata_fields,validate_metadata as validate_graphics_metadata,on_grid
from adapters.token_audio_ui import audio_control, metadata_fields as audio_metadata_fields, validate_metadata as validate_audio_metadata
from adapters.token_script_file_ui import (file_control, metadata_fields as file_metadata_fields,
    validate_metadata as validate_file_metadata, folder_text)
from adapters.token_places_ui import control_id as places_control, metadata as places_metadata, same_reference as places_same_reference
from adapters.token_navigation_error_ui import control_id as error_control, metadata as error_metadata, same_reference as error_same_reference

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
    if type(value) is dict and 'navigationAddressVersion' in value:
        fields.add('navigationAddressVersion')
        need(type(value['navigationAddressVersion']) is int and value['navigationAddressVersion']==1)
    if type(value) is dict and 'featureControlsVersion' in value:
        fields.add('featureControlsVersion')
        need(type(value['featureControlsVersion']) is int and value['featureControlsVersion'] == 1)
    if type(value) is dict and 'fileControlsVersion' in value:
        fields.add('fileControlsVersion')
        need(type(value['fileControlsVersion']) is int and value['fileControlsVersion'] == 1)
    if type(value) is dict and ('picoAudioPageVersion' in value or 'picoAudioPages' in value):
        from adapters.pico4.audio_pages import validate as audio_pages
        fields|={'picoAudioPageVersion','picoAudioPages'}
        need(type(value.get('picoAudioPageVersion')) is int and value['picoAudioPageVersion']==1)
        audio_pages(value.get('picoAudioPages'),epoch_ms)
    if type(value) is dict and 'audioControlsVersion' in value:
        fields.add('audioControlsVersion')
        need(type(value['audioControlsVersion']) is int and value['audioControlsVersion'] == 1)
    if type(value) is dict and 'graphicsControlsVersion' in value:
        fields.add('graphicsControlsVersion')
        need(type(value['graphicsControlsVersion']) is int and value['graphicsControlsVersion']==1)
    if type(value) is dict and 'chatControlsVersion' in value:
        fields.add('chatControlsVersion')
        need(type(value['chatControlsVersion']) is int and value['chatControlsVersion']==1)
    if type(value) is dict and 'lifecycleControlsVersion' in value:
        fields.add('lifecycleControlsVersion')
        need(type(value['lifecycleControlsVersion']) is int and value['lifecycleControlsVersion']==1)
    if type(value) is dict and 'createControlsVersion' in value:
        fields.add('createControlsVersion')
        need(type(value['createControlsVersion']) is int and value['createControlsVersion']==1)
    if type(value) is dict and 'loginControlsVersion' in value:
        fields.add('loginControlsVersion')
        need(type(value['loginControlsVersion']) is int and value['loginControlsVersion']==LOGIN_VERSION)
    if type(value) is dict and 'accountMenuControlsVersion' in value:
        fields.add('accountMenuControlsVersion')
        need(type(value['accountMenuControlsVersion']) is int and value['accountMenuControlsVersion']==1)
    if type(value) is dict and 'placesControlsVersion' in value:
        fields.add('placesControlsVersion')
        need(type(value['placesControlsVersion']) is int and value['placesControlsVersion']==1)
    if type(value) is dict and 'navigationErrorControlsVersion' in value:
        fields.add('navigationErrorControlsVersion')
        need(type(value['navigationErrorControlsVersion']) is int and value['navigationErrorControlsVersion']==1)
    if type(value) is dict and 'navigationLookupControlsVersion' in value:
        fields.add('navigationLookupControlsVersion')
        need(type(value['navigationLookupControlsVersion']) is int and value['navigationLookupControlsVersion']==1)
    if type(value) is dict and 'navigationOriginControlsVersion' in value:
        fields.add('navigationOriginControlsVersion')
        need(type(value['navigationOriginControlsVersion']) is int and value['navigationOriginControlsVersion']==1)
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
        if control['id']=='navigation.address' and value.get('navigationAddressVersion')==1:
            fields|={'textSha256','textLength','inputReady'}
        if control['id'].startswith('graphics.'):need(value.get('graphicsControlsVersion')==1)
        is_graphics=graphics_control(control['id']) and value.get('graphicsControlsVersion')==1
        is_create=control['id'].startswith('create.')
        is_chat=control['id'].startswith('chat.')
        is_places=control['id'].startswith('places.')
        is_error=control['id'].startswith('navigation.error.ok.')
        if control['id'].startswith('lifecycle.'):
            need(control['id']==LIFECYCLE_ID and value.get('lifecycleControlsVersion')==1);lifecycle_metadata(control);fields=set(control)
        elif is_error:
            need(value.get('navigationErrorControlsVersion')==1);error_metadata(control);fields=set(control)
        elif is_places:
            need(value.get('placesControlsVersion')==1);places_metadata(control);fields=set(control)
        elif is_chat:
            need(value.get('chatControlsVersion')==1);chat_metadata(control);fields=set(control)
        elif is_create:
            need(value.get('createControlsVersion')==1);create_metadata(control);fields=set(control)
        elif control['id'] in ACCOUNT_MENU_IDS:
            need(value.get('accountMenuControlsVersion')==1);fields |= ACCOUNT_MENU_FIELDS
        elif control['id'] in LOGIN_IDS:
            need(value.get('loginControlsVersion')==LOGIN_VERSION);fields |= login_metadata_fields(control['id'])
        elif is_graphics:
            fields |= graphics_metadata_fields(control['id'])
        elif audio_control(control['id']):
            need(value.get('audioControlsVersion') == 1)
            fields |= audio_metadata_fields(control['id'])
        elif file_control(control['id']):
            need(value.get('fileControlsVersion') == 1)
            fields |= file_metadata_fields(control['id'], control)
        elif script_control(control['id']):
            need(value.get('featureControlsVersion') == 1)
            fields |= metadata_fields(control['id'])
        if control['id'] in SNAPSHOT_CHOICES:
            fields.add('checked')
        need(set(control) == fields
             and isinstance(control['id'], str) and (control['id'] in CONTROL_IDS
                 or script_control(control['id']) or file_control(control['id']) or audio_control(control['id'])
                 or graphics_control(control['id']) or control['id'] in LOGIN_IDS or control['id'] in ACCOUNT_MENU_IDS
                 or is_create and create_control(control['id']) or is_chat and chat_control(control['id'])
                 or is_places and places_control(control['id']) or is_error and error_control(control['id']) or control['id']==LIFECYCLE_ID)
             and identifier(control['token']) and control['id'] not in ids
             and control['token'] not in tokens and type(control['enabled']) is bool
             and type(control['focused']) is bool)
        if control['id']=='navigation.address' and value.get('navigationAddressVersion')==1:
            need(type(control['textSha256']) is str and re.fullmatch('[0-9a-f]{64}',control['textSha256'])
                and type(control['textLength']) is int and 0<=control['textLength']<=2048
                and type(control['inputReady']) is bool
                and (not control['inputReady'] or control['enabled'] and control['focused']))
        if control['id'] in SNAPSHOT_CHOICES:
            need(type(control['checked']) is bool)
        if is_error:error_metadata(control)
        elif is_places:places_metadata(control)
        elif is_chat:chat_metadata(control)
        elif is_create:create_metadata(control)
        elif control['id'] in ACCOUNT_MENU_IDS:validate_account_menu_metadata(control)
        elif control['id'] in LOGIN_IDS:validate_login_metadata(control)
        elif is_graphics:validate_graphics_metadata(control)
        elif audio_control(control['id']): validate_audio_metadata(control)
        elif file_control(control['id']): validate_file_metadata(control)
        elif script_control(control['id']):
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
                 *, monotonic=time.monotonic, sleep=time.sleep, address_authority=None):
        need(address_authority is None or callable(address_authority))
        self.address_authority=address_authority
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

    def input(self, control_id, action='activate', text=None, *, source=None, index=None, token=None, direction=None, value=None, reference=None, expected_address=None, expected_scope=None):
        # SDK/package verification can take longer than the native input's
        # freshness window. Bind bytes first, then capture the current UI.
        self.io.bind_input()
        snapshot = self.snapshot()
        control = self.control(snapshot, control_id)
        need(snapshot['ready'] and control is not None and snapshot['lastCommandSequence'] < MAX_INTEGER)
        if token is not None: need(control['token'] == token)
        if expected_scope is not None:
            from adapters.token_create_ui import scope
            scope(expected_scope)
            need((snapshot.get('navigationOriginControlsVersion')==1 and control_id in ('login.server','tablet.home')
                  or snapshot.get('navigationLookupControlsVersion')==1 and (control_id in ('navigation.goto','navigation.address')
                      or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',control_id)))
                 and token is not None and reference is None
                 and snapshot['bridgeId']==expected_scope['instance'] and snapshot['generation']==expected_scope['generation']
                 and snapshot['processId']==expected_scope['processId'] and snapshot['lastCommandSequence']==expected_scope['sequence']
                 and 0<=snapshot['elapsedMs']-expected_scope['elapsedMs']<=5000)
        need(expected_address is None or control_id=='navigation.address' and action=='submit')
        if expected_address is not None:
            need(type(expected_address) is str and 0<len(expected_address)<=2048
                and snapshot.get('navigationAddressVersion')==1 and control['inputReady'] and control['focused']
                and control['textLength']==len(expected_address)
                and control['textSha256']==hashlib.sha256(expected_address.encode()).hexdigest())
            need(self.address_authority(expected_address) is True if self.address_authority is not None else expected_address in self.urls)
        is_create=control_id.startswith('create.')
        is_chat=control_id.startswith('chat.')
        is_places=control_id.startswith('places.')
        is_error=control_id.startswith('navigation.error.ok.')
        if reference is not None:
            need(type(reference) is dict)
            if 'lifecycleControlsVersion' in reference:
                from adapters.pico4.normal_lifecycle import project as lifecycle_project
                original=lifecycle_same_reference(reference,lifecycle_project(snapshot),control_id)
            elif 'navigationErrorControlsVersion' in reference:
                from adapters.pico4.normal_navigation_error import project as error_project
                original=error_same_reference(reference,error_project(snapshot),control_id)
            elif 'placesControlsVersion' in reference:
                from adapters.pico4.normal_places import project as places_project
                original=places_same_reference(reference,places_project(snapshot),control_id)
            elif 'chatControlsVersion' in reference:
                from adapters.pico4.normal_chat import project as chat_project
                original=chat_same_reference(reference,chat_project(snapshot),control_id)
            else:
                from adapters.pico4.normal_create import project
                original=same_reference(reference,project(snapshot),control_id)
            need(original['token']==control['token'])
        if control_id.startswith('lifecycle.'):
            need(control_id==LIFECYCLE_ID and reference is not None and snapshot.get('lifecycleControlsVersion')==1
                and control['inputReady'] and action in ('activate','replace')
                and all(v is None for v in (source,index,direction,value)))
            if action=='replace':need(control['focused']);lifecycle_text(text)
            else:need(text is None)
        elif is_error:
            need(reference is not None and snapshot.get('navigationErrorControlsVersion')==1 and control['inputReady']
                 and action=='activate' and all(v is None for v in (text,source,index,direction,value)))
        elif is_places:
            need(reference is not None and snapshot.get('placesControlsVersion')==1 and control['inputReady']
                 and control_id!='places.page' and index is None and source is None and value is None
                 and action in ('activate','replace','scroll'))
            if action=='replace':need(control_id in ('places.search','places.bookmark.name','places.server.url') and control['focused']);ascii_text(text)
            elif action=='scroll':need(control_id.startswith('places.scroll.') and direction in ('up','down') and text is None)
            else:need(not control_id.startswith('places.scroll.') and direction is None and text is None)
        elif control_id in ACCOUNT_MENU_IDS:
            need(snapshot.get('accountMenuControlsVersion')==1 and control['inputReady'] and token is not None
                 and action=='activate' and all(v is None for v in (text,source,index,direction,value,reference)))
        elif is_chat:
            need(reference is not None and snapshot.get('chatControlsVersion')==1 and control['inputReady']
                 and control_id!='chat.page' and value is None and direction is None and index is None and source is None
                 and action in ('activate','replace','submit'))
            if action in ('replace','submit'):need(control_id=='chat.input' and control['focused'])
            if action=='replace':chat_text(text)
            else:need(text is None)
        elif is_create:
            need(reference is not None and snapshot.get('createControlsVersion')==1 and control['inputReady']
                 and control_id!='create.page' and value is None and action in ('activate','replace','select-index','scroll'))
            if action=='replace':need(create_field(control_id) and control['focused']);ascii_text(text)
            elif action=='select-index':need(create_choice(control_id) and type(index) is int and 0<=index<control['count'])
            elif action=='scroll':need(control_id=='create.scrollbar' and direction in ('up','down'))
            else:need(control_id!='create.scrollbar' and direction is None)
        elif control_id in LOGIN_IDS:
            need(snapshot.get('loginControlsVersion')==LOGIN_VERSION and token is not None
                 and control_id!='login.page' and control['inputReady'] and direction is None and value is None
                 and action in ('activate','replace','submit'))
            if action in ('replace','submit'):need(control['focused'])
            if action=='replace':need(control_id in ('login.username','login.password','login.server'))
            if action=='submit':need(control_id=='login.password' or control_id=='login.server' and snapshot.get('navigationOriginControlsVersion')==1)
        elif graphics_control(control_id) and snapshot.get('graphicsControlsVersion')==1:
            need(token is not None and control['inputReady'] and control['viewport']=='visible'
                 and control_id!='graphics.page' and action in ('activate','scroll','set-value'))
            if action=='set-value':need(control_id=='graphics.resolution' and direction is None and on_grid(value,control))
            elif action=='scroll':need(control_id=='graphics.scrollbar' and direction in ('up','down') and value is None)
            else:need(control_id not in ('graphics.scrollbar','graphics.resolution') and direction is None and value is None)
        elif audio_control(control_id):
            need(value is None)
            need(snapshot.get('audioControlsVersion') == 1 and control['inputReady']
                 and token is not None and control_id != 'audio.page' and action in ('activate','scroll'))
            if action == 'activate': need(control_id != 'audio.scrollbar' and direction is None)
            else: need(control_id == 'audio.scrollbar' and direction in ('up','down'))
        else: need(direction is None and value is None and action in ('activate','replace','submit','select-index'))
        if source is not None:
            need(control.get('sourceUrl') == source)
        if file_control(control_id):
            need(snapshot.get('fileControlsVersion') == 1)
        if action in ('replace', 'submit', 'select-index') and control_id.startswith('script-file.'):
            need(control['focused'])
        command = {'schemaVersion': 1, 'commandId': str(uuid.uuid4()),
            'bridgeId': snapshot['bridgeId'], 'generation': snapshot['generation'],
            'sequence': snapshot['lastCommandSequence'] + 1,
            'observedElapsedMs': snapshot['elapsedMs'], 'controlId': control_id,
            'controlToken': control['token'], 'action': action}
        if expected_scope is not None:
            command.update(observedElapsedMs=expected_scope['elapsedMs'],sequence=expected_scope['sequence']+1)
        if reference is not None:
            command.update(observedElapsedMs=reference['scope']['elapsedMs'],sequence=reference['scope']['sequence']+1,controlToken=original['token'])
        if action == 'replace':
            if control_id == 'navigation.address':
                need(type(text) is str and 0<len(text)<=2048)
                need(self.address_authority(text) is True if self.address_authority is not None else text in self.urls)
            elif control_id == 'snapshot.name':
                validate_operation_arguments('snapshot.files', {'prefix': text})
            elif control_id == 'scripts.url.field':
                from scripts_observation import script_url
                from create_observation import owned_url
                need(type(text) is str)
                if '/script-management/' in text:
                    script_url(text, missing=text.endswith('/missing.js'))
                elif '/feature-fixture/' in text:
                    from adapters.normal_script_manager import missing_script_url
                    missing_script_url(text)
                else:
                    owned_url(text, {'observer.js'})
            elif is_places:
                need(control_id in ('places.search','places.bookmark.name','places.server.url'));ascii_text(text)
            elif control_id==LIFECYCLE_ID:
                lifecycle_text(text)
            elif is_chat:
                need(control_id=='chat.input');chat_text(text)
            elif is_create:
                need(create_field(control_id));ascii_text(text)
            elif control_id in ('login.username','login.password','login.server'):
                need(type(text) is str and re.fullmatch('[\x20-\x7e]{1,4096}',text))
            elif control_id == 'script-file.folder':
                folder_text(text)
            else:
                raise NavigationError()
            command['text'] = text
        if action == 'select-index':
            need((control_id == 'script-file.primary' or is_create and create_choice(control_id)) and type(index) is int and 0 <= index < 32)
            command['index'] = index
        if action == 'scroll': command['direction'] = direction
        if action == 'set-value':command['value']=value
        self.io.guard()
        if control_id=='navigation.address' and snapshot.get('navigationAddressVersion')==1 and action in ('replace','submit'):
            need(control['inputReady'] and control['focused'])
        if control_id=='navigation.address' and action=='replace' and self.address_authority is not None:
            need(self.address_authority(text) is True)
        if expected_address is not None:
            need(self.address_authority(expected_address) is True if self.address_authority is not None else expected_address in self.urls)
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

    def __init__(self, adapter, target, process_identity, controller, *, before_send=None):
        self.adapter, self.target, self.identity = adapter, target, process_identity
        self._controller = controller
        self._before_send = None
        if before_send is not None:
            self.bind_before_send(before_send)

    def bind_before_send(self, callback):
        """Bind one owner to the final validated QML command before publication."""
        need(callable(callback) and (self._before_send is None or self._before_send is callback))
        self._before_send = callback

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
        if self._before_send is not None:
            self._before_send(deepcopy(command))
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

    def clear_private_input(self):
        # Same bound process and fixed owned input channel; never a new device.
        # The existing atomic writer independently reads back the exact empty
        # command. Native ignores its absent identity and cannot replay input.
        self.bind_input()
        self.adapter.adb.write_debug_app_file(self.target,'org.overte.pico',self.DIRECTORY+'command.json','{}\n')
        need(self.adapter.adb.read_debug_app_file(self.target,'org.overte.pico',self.DIRECTORY+'command.json',attempts=1)=='{}\n')
        self.guard()

    def controller(self, operation):
        need(operation in {'tablet.open', 'tablet.close'})
        # Preserve the canonical real OpenXR controller route, including its
        # native session/nonce/sequence and process guards.
        result = self._controller(operation)
        need(type(result) is dict and result.get('performed') is True)
