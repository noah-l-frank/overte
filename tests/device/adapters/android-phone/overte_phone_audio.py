"""Original Phone Audio controls using the existing private token UI channel."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid
from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.normal_ui import NativeUIError
from adapters.token_audio_ui import audio_control, metadata_fields, validate_metadata
from overte_phone_script_files import PhoneScriptFileIO, nonce

FILE = 'phone-audio-ui.json'


def validate(value, command, pid, epoch):
    exact(value, {'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','audioControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['commandId'] == command and value['action'] == 'observe'
         and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence'])
         and integer(value['elapsedMs']) and integer(value['processId'],1) and value['processId'] == pid
         and type(value['audioControlsVersion']) is int and value['audioControlsVersion'] == 1
         and value['ready'] is True and type(value['controls']) is list and len(value['controls']) <= 384)
    fresh(value['capturedEpochMs'],epoch)
    ids, tokens = set(),set()
    for row in value['controls']:
        need(type(row) is dict and audio_control(row.get('id')))
        exact(row, {'id','token','enabled','focused'} | metadata_fields(row['id']))
        need(nonce(row['token']) and row['token'] not in tokens and row['id'] not in ids
             and type(row['enabled']) is bool and type(row['focused']) is bool)
        validate_metadata(row); ids.add(row['id']); tokens.add(row['token'])
    return value


class PhoneAudioIO(PhoneScriptFileIO):
    wire_action = 'phone-audio-ui'
    validate_capture = staticmethod(validate)

    def input(self, identifier, action, *, token, direction=None):
        try:
            need(audio_control(identifier) and nonce(token) and identifier != 'audio.page'
                 and action in ('activate','scroll'))
            if action == 'scroll': need(identifier == 'audio.scrollbar' and direction in ('up','down'))
            else: need(identifier != 'audio.scrollbar' and direction is None)
            observed = self.capture()
            rows = [r for r in observed['controls'] if r['id'] == identifier]
            need(len(rows) == 1 and rows[0]['enabled'] and rows[0]['inputReady'] and rows[0]['token'] == token)
            request = dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=observed['instance'],
                generation=observed['generation'],sequence=observed['lastCommandSequence']+1,
                observedElapsedMs=observed['elapsedMs'],controlId=identifier,controlToken=token)
            if action == 'scroll': request['direction'] = direction
            self.deliver(request, observed)
        except Exception:
            raise NativeUIError('Phone original Audio input delivery failed') from None

    def activate(self, identifier, *, token): self.input(identifier,'activate',token=token)
    def scroll(self, identifier, direction, *, token): self.input(identifier,'scroll',token=token,direction=direction)
