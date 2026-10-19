"""Owned Pico SNAP input and original output through the existing VR session."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from adapters.pico4.navigation import decode, identifier, need
from contracts import validate_operation_arguments
from navigation_observation import viewpoint_urls

OPERATIONS = frozenset({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'})
MODES = ('still', 'animated', 'panorama', 'cubemap')
FORMATS = ('png', 'jpg', 'webp')
PREFERENCE_FIELDS = {'bridgeId', 'originalMode', 'originalFormat', 'nonce', 'prefix',
                     'preflightEmpty', 'capturePending'}


def configured_scene(environment):
    enabled = environment.get('OVERTE_PICO_NORMAL_SNAPSHOT', '0')
    need(enabled in ('0', '1'))
    if enabled == '0':
        return None
    need(environment.get('OVERTE_ANDROID_E2E_DEBUG') == '1'
         and environment.get('OVERTE_PICO_OPENXR_INPUT') == '1')
    scene = environment.get('OVERTE_E2E_SCENE_URL')
    viewpoint_urls(scene)
    return scene


class PicoSnapshot:
    def __init__(self, native_ui, files, preference_path):
        # NativeNavigationIO/PicoNavigation retain the original candidate,
        # process/OpenXR, native UI token/instance and fresh-input machinery.
        self.ui, self.files, self.path = native_ui, files, Path(preference_path)
        need(re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}', native_ui.context['processIdentity']) is not None)
        need(self.path.parent == self.ui.path.parent and self.path != self.ui.path)
        self.ui._private_parent()
        self.state = self._read()
        if self.state is not None:
            self._validate(self.state)
            need(self.ui.state is not None and self.state['bridgeId'] == self.ui.state['bridgeId'])

    def _validate(self, value):
        context = self.ui.context
        need(type(value) is dict and set(value) == set(context) | PREFERENCE_FIELDS
             and all(type(value[key]) is type(expected) and value[key] == expected
                     for key, expected in context.items())
             and identifier(value['bridgeId'])
             and value['originalMode'] in (None, *MODES)
             and value['originalFormat'] in (None, *FORMATS)
             and type(value['preflightEmpty']) is bool and type(value['capturePending']) is bool
             and (value['nonce'] is None or isinstance(value['nonce'], str)
                  and re.fullmatch('[0-9a-f]{16}', value['nonce']) is not None))
        if value['prefix'] is not None:
            validate_operation_arguments('snapshot.files', {'prefix': value['prefix']})
            need(value['prefix'].split('-')[1] == value['nonce'])
        need(not value['capturePending'] or value['prefix'] is not None)
        need(not value['preflightEmpty'] or value['prefix'] is not None)

    def _read(self):
        self.ui._private_parent()
        try:
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                 and info.st_uid == os.getuid() and info.st_nlink == 1 and info.st_size <= 4096)
            value = decode(stream.read(4097), limit=4096)
        return value

    def mark(self, **changes):
        self.ui._private_parent()
        prior = self._read()
        if prior is not None:
            self._validate(prior)
            need(prior == self.state)
        if self.state is None:
            observed = self.ui.snapshot()
            need(self.ui.state is not None and self.ui.state['tabletOwned'])
            self.state = self.ui.context | dict(bridgeId=observed['bridgeId'], originalMode=None,
                originalFormat=None, nonce=None, prefix=None, preflightEmpty=False, capturePending=False)
        value = self.state | changes
        self._validate(value)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='snapshot-preferences.')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, sort_keys=True, separators=(',', ':'))
                stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.state = value

    def click(self, control):
        self.ui.wait(lambda value: self.ui.control(value, control))
        self.ui.input(control)

    def show(self):
        self.ui.open()
        observed = self.ui.snapshot()
        if self.ui.control(observed, 'snapshot.name', enabled=False) is None:
            if self.ui.control(observed, 'tablet.home'):
                self.click('tablet.home')
                observed = self.ui.snapshot()
            observed = self.ui.wait(lambda value: self.ui.control(value, 'snapshot.entry')
                or any(row['id'].startswith('tablet.page.') for row in value['controls']))
            pages = sorted((row['id'] for row in observed['controls']
                            if row['id'].startswith('tablet.page.')),
                           key=lambda name: int(name.rsplit('.', 1)[1]))
            for page in (None, *pages):
                if page is not None:
                    self.click(page)
                until = self.ui.monotonic() + 0.6
                found = False
                while True:
                    if self.ui.control(self.ui.snapshot(), 'snapshot.entry'):
                        self.click('snapshot.entry')
                        found = True
                        break
                    if self.ui.monotonic() >= until:
                        break
                    self.ui.sleep(0.1)
                if found:
                    break
            self.ui.wait(lambda value: self.ui.control(value, 'snapshot.name'))
        self.ui.wait(lambda value: self.ui.control(value, 'snapshot.format'))

    def selected(self, control, options):
        self.click(control)
        value = self.ui.wait(lambda observed: self.ui.control(observed, control + '.' + options[0]))
        # wait() returns the actual observation, never its predicate's value.
        selected = [option for option in options
                    if (choice := self.ui.control(value, control + '.' + option)) is not None
                    and choice['checked']]
        need(len(selected) == 1)
        self.click(control + '.' + selected[0])
        return selected[0]

    def choose(self, control, options, option):
        self.click(control)
        self.click(control + '.' + option)
        need(self.selected(control, options) == option)

    def open(self):
        self.show()
        self.ui.wait(lambda value: self.ui.control(value, 'snapshot.capture')
                     and self.ui.control(value, 'snapshot.mode'))
        if self.state is None or self.state['originalMode'] is None:
            self.mark(originalMode=self.selected('snapshot.mode', MODES))
        if self.state['originalFormat'] is None:
            self.mark(originalFormat=self.selected('snapshot.format', FORMATS))
        self.mark(prefix=None, preflightEmpty=False, capturePending=False)

    def original_files(self, prefix):
        need(self.state is not None and self.ui.state is not None and self.ui.state['tabletOwned'])
        nonce = prefix.split('-')[1]
        need(self.state['nonce'] in (None, nonce) and self.state['prefix'] in (None, prefix))
        self.mark(nonce=nonce, prefix=prefix)
        result = self.files.files(prefix)
        if not self.state['capturePending']:
            self.mark(preflightEmpty=not result['files'])
        return result

    def take(self, arguments):
        need(self.state is not None and self.state['preflightEmpty']
             and not self.state['capturePending'] and self.state['prefix'] == arguments['name'])
        need(not self.files.files(arguments['name'])['files'])
        self.show()
        self.ui.wait(lambda value: self.ui.control(value, 'snapshot.capture'))
        self.click('snapshot.name')
        self.ui.input('snapshot.name', 'replace', arguments['name'])
        self.choose('snapshot.mode', MODES, arguments['mode'])
        self.choose('snapshot.format', FORMATS, arguments['format'])
        self.mark(capturePending=True, preflightEmpty=False)
        self.click('snapshot.capture')

    def close(self):
        if self.state is not None:
            if (self.state['capturePending'] or self.state['originalMode'] is not None
                    or self.state['originalFormat'] is not None):
                self.show()
                if self.state['capturePending'] and self.ui.control(self.ui.snapshot(), 'snapshot.cancel'):
                    self.click('snapshot.cancel')
                self.ui.wait(lambda value: self.ui.control(value, 'snapshot.capture'))
                if self.state['originalMode'] is not None:
                    self.choose('snapshot.mode', MODES, self.state['originalMode'])
                if self.state['originalFormat'] is not None:
                    self.choose('snapshot.format', FORMATS, self.state['originalFormat'])
            current = self._read()
            self._validate(current)
            need(current == self.state)
        # The original owned OpenXR close route confirms actual native closure.
        # Failed restoration/close keeps both private intents for recovery.
        self.ui.close()
        if self.state is not None:
            self.path.unlink()
            self.state = None

    def invoke(self, operation, values):
        need(operation in OPERATIONS)
        values = validate_operation_arguments(operation, values)
        if operation == 'snapshot.files':
            return self.original_files(values['prefix'])
        if operation == 'snapshot.open':
            self.open()
        elif operation == 'snapshot.capture':
            self.take(values)
        else:
            self.close()
        return {'performed': True}
