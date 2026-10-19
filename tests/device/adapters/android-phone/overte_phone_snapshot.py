"""Owned normal Phone SNAP input and original files; never a capture verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from adapters.normal_ui import Locator, NativeUI, NativeUIError
from contracts import validate_operation_arguments

PACKAGE = 'io.github.noah_be.overte.phone'
OPERATIONS = frozenset({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'})
MODES = ('still', 'animated', 'panorama', 'cubemap')
FORMATS = ('png', 'jpg', 'webp')
CONTEXT_FIELDS = {'sourceRevision', 'artifactSha256', 'processIdentity',
                  'sessionId', 'generation', 'targetFingerprint'}
STATE_FIELDS = CONTEXT_FIELDS | {'tabletOwned', 'snapshotOwned', 'capturePending',
    'originalMode', 'originalFormat', 'nonce', 'prefix', 'preflightEmpty'}


def resource(name):
    return Locator('id', PACKAGE + ':id/' + name)


def validate_state(value):
    if (not isinstance(value, dict) or set(value) != STATE_FIELDS
            or any(type(value[key]) is not bool for key in
                   ('tabletOwned', 'snapshotOwned', 'capturePending', 'preflightEmpty'))
            or type(value['generation']) is not int or value['generation'] < 0
            or any(not isinstance(value[key], str) or re.fullmatch(pattern, value[key]) is None
                   for key, pattern in (('sourceRevision', '[0-9a-f]{40}'),
                       ('artifactSha256', '[0-9a-f]{64}'), ('targetFingerprint', '[0-9a-f]{64}'),
                       ('sessionId', '[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}'),
                       ('processIdentity', '[!-~]{1,160}')))
            or value['originalMode'] not in (None, *MODES)
            or value['originalFormat'] not in (None, *FORMATS)
            or value['nonce'] is not None and (not isinstance(value['nonce'], str)
                or re.fullmatch('[0-9a-f]{16}', value['nonce']) is None)
            or value['prefix'] is not None and (not isinstance(value['prefix'], str)
                or re.fullmatch(r'parity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)',
                                value['prefix']) is None
                or value['prefix'].split('-')[1] != value['nonce'])
            or value['snapshotOwned'] and not value['tabletOwned']
            or value['capturePending'] and (not value['snapshotOwned'] or value['prefix'] is None)
            or value['preflightEmpty'] and value['prefix'] is None):
        raise NativeUIError('Normal Phone Snapshot private ownership is invalid')
    return value


class PrivateSnapshotState:
    """Phone-owned sidecar; leave the shared Appium session schema unchanged."""
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        if self.path.is_symlink():
            raise NativeUIError('Normal Phone Snapshot state is not a private file')
        try:
            metadata = self.path.lstat()
        except FileNotFoundError:
            return None
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_size > 4096 or os.name != 'nt'
                and (metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077)):
            raise NativeUIError('Normal Phone Snapshot state is not a private file')
        try:
            return validate_state(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError, UnicodeError, ValueError):
            raise NativeUIError('Normal Phone Snapshot state is unreadable') from None

    def write(self, value):
        validate_state(value)
        self.read()  # Never replace a foreign alias or malformed retry state.
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='phone-snapshot.')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, sort_keys=True, separators=(',', ':'))
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def discard(self):
        self.read()
        self.path.unlink(missing_ok=True)


class PhoneSnapshotUI(NativeUI):
    def checked(self, locator):
        element = self._resolve(locator)
        self._check()
        value = self._request('GET', element + '/attribute/checked')
        self._check()
        if type(value) is bool:
            return value
        if value in ('true', 'false'):
            return value == 'true'
        raise NativeUIError('Normal Phone Snapshot checked state is malformed')


class PhoneSnapshot:
    def __init__(self, ui, files, store, context):
        self.ui, self.files, self.store = ui, files, store
        self.context = dict(context)
        value = dict(context, tabletOwned=False, snapshotOwned=False, capturePending=False,
                     originalMode=None, originalFormat=None, nonce=None, prefix=None, preflightEmpty=False)
        validate_state(value)
        self.state = store.read() or value
        if any(self.state[key] != context[key] for key in CONTEXT_FIELDS):
            raise NativeUIError('Normal Phone Snapshot belongs to a different bound session')
        self.name, self.capture = resource('snapshotName'), resource('snapshotCapture')
        self.cancel = resource('snapshotCancelCapture')
        self.open_tablet, self.close_tablet = resource('tablet.open'), resource('nav.close')
        self.home = resource('nav.home')
        self.entry = Locator('accessibility id', 'SNAP')

    def mark(self, **values):
        self.state.update(values)
        self.store.write(self.state)

    def show(self):
        if not self.state['tabletOwned']:
            if (self.ui.available(self.close_tablet, require_enabled=False)
                    or self.ui.available(self.name, require_enabled=False)):
                raise NativeUIError('Normal Phone Snapshot found a pre-existing tablet')
            self.mark(tabletOwned=True)  # Intent survives a partially delivered click.
            self.ui.click(self.open_tablet)
        elif not self.ui.available(self.close_tablet, require_enabled=False):
            # A real capture can hide the tablet. Reopen only our owned panel.
            self.ui.click(self.open_tablet)
        self.ui.wait_control(self.close_tablet)
        if not self.ui.available(self.name, require_enabled=False):
            if self.ui.available(self.home):
                self.ui.click(self.home)
            if not self.ui.available(self.entry):
                # Normal Home pagination only, bounded even on a malformed UI.
                for page in range(1, 9):
                    button = resource('tabletPage.' + str(page))
                    if self.ui.available(button):
                        self.ui.click(button)
                    if self.ui.available(self.entry):
                        break
            self.mark(snapshotOwned=True)
            self.ui.click(self.entry)
        elif not self.state['snapshotOwned']:
            raise NativeUIError('Normal Phone Snapshot found an unowned review')
        self.ui.wait_control(self.name)
        self.ui.wait_control(resource('snapshotFormat'))

    def selected(self, control, options):
        self.ui.click(resource(control))
        # Native click delivery precedes the next Qt/Android accessibility
        # frame. Wait only for the popup read; never replay its opening click.
        self.ui.wait_control(resource(control + '.option.' + options[0]))
        selected = []
        for option in options:
            locator = resource(control + '.option.' + option)
            if self.ui.available(locator) and self.ui.checked(locator):
                selected.append(option)
        if len(selected) != 1:
            raise NativeUIError('Normal Phone Snapshot has no unique selected choice')
        self.ui.click(resource(control + '.option.' + selected[0]))
        return selected[0]

    def choose(self, control, options, value):
        self.ui.click(resource(control))
        self.ui.click(resource(control + '.option.' + value))
        if self.selected(control, options) != value:
            raise NativeUIError('Normal Phone Snapshot choice was not applied')

    def open(self):
        self.show()
        self.ui.wait_control(resource('snapshotMode'))
        self.ui.wait_control(self.capture)
        if self.state['originalMode'] is None:
            self.mark(originalMode=self.selected('snapshotMode', MODES))
        if self.state['originalFormat'] is None:
            self.mark(originalFormat=self.selected('snapshotFormat', FORMATS))
        self.mark(capturePending=False, prefix=None, preflightEmpty=False)

    def original_files(self, prefix):
        if not self.state['snapshotOwned']:
            raise NativeUIError('Normal Phone Snapshot original files require an owned review')
        nonce = prefix.split('-')[1]
        if self.state['nonce'] not in (None, nonce):
            raise NativeUIError('Normal Phone Snapshot prefix belongs to another run')
        if self.state['prefix'] not in (None, prefix):
            raise NativeUIError('Normal Phone Snapshot prefix differs from the current capture')
        self.mark(nonce=nonce, prefix=prefix)
        result = self.files.files(prefix)
        if not self.state['capturePending']:
            self.mark(preflightEmpty=not result['files'])
        return result

    def take(self, arguments):
        if (not self.state['snapshotOwned'] or self.state['capturePending']
                or not self.state['preflightEmpty'] or self.state['prefix'] != arguments['name']):
            raise NativeUIError('Normal Phone Snapshot requires its empty owned capture prefix')
        # A new matching file after the earlier journey precondition is not ours.
        if self.files.files(arguments['name'])['files']:
            raise NativeUIError('Normal Phone Snapshot prefix is no longer empty')
        self.ui.wait_control(self.capture)
        self.ui.replace_text(self.name, arguments['name'])
        self.choose('snapshotMode', MODES, arguments['mode'])
        self.choose('snapshotFormat', FORMATS, arguments['format'])
        self.mark(capturePending=True, preflightEmpty=False)
        self.ui.click(self.capture)

    def close(self):
        errors = []
        try:
            if self.state['snapshotOwned'] and (self.state['capturePending']
                    or self.state['originalMode'] is not None or self.state['originalFormat'] is not None):
                self.show()
                if self.state['capturePending'] and self.ui.available(self.cancel):
                    self.ui.click(self.cancel)
                self.ui.wait_control(self.capture)
                if self.state['originalMode'] is not None:
                    self.choose('snapshotMode', MODES, self.state['originalMode'])
                if self.state['originalFormat'] is not None:
                    self.choose('snapshotFormat', FORMATS, self.state['originalFormat'])
            if self.state['tabletOwned']:
                if self.ui.available(self.close_tablet, require_enabled=False):
                    self.ui.click(self.close_tablet)
                self.ui.wait_absent(self.close_tablet)
                # A modal popup can hide the footer without closing its panel.
                self.ui.wait_control(self.open_tablet)
        except BaseException as error:
            errors.append(error)
        try:
            # An uncertain restore/close keeps private intent for recovery.
            self.ui.release_actions()
        except BaseException as error:
            errors.append(error)
        if errors:
            raise errors[0]
        self.store.discard()

    def invoke(self, operation, arguments):
        if operation not in OPERATIONS:
            raise ValueError('Unknown normal Phone Snapshot operation')
        arguments = validate_operation_arguments(operation, arguments)
        if operation == 'snapshot.files':
            return self.original_files(arguments['prefix'])
        if operation == 'snapshot.open':
            self.open()
        elif operation == 'snapshot.capture':
            self.take(arguments)
        else:
            self.close()
        return {'performed': True}
