"""Normal iOS Script controls, explicitly native UI component scope only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib

from adapters.normal_feature_state import need
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import Locator, NativeUIError
from adapters.token_script_ui import TokenScriptUI

PROFILE = 'ios-native-qt-scripts-v1'


def configuration(target):
    profile = target.get('normalScripts')
    if profile is None: return None
    if (type(profile) is not dict or set(profile) != {'contractVersion', 'profile'}
            or type(profile['contractVersion']) is not int or profile['contractVersion'] != 1
            or profile['profile'] != PROFILE or target.get('physical') is not True
            or target.get('nativeUiObservation') != {'kind': 'uikit-documents', 'version': 1}
            or type(target['nativeUiObservation']['version']) is not int
            or target.get('probe') != {'kind': 'ios-documents'} or not target.get('testBuild')):
        raise NativeUIError('Normal iOS Scripts requires its explicit native UI component profile')
    return profile


class IOSScriptIO:
    def __init__(self, ui, native):
        self.ui, self.native = ui, native
        self.capture()  # Missing native instrumentation fails before UI input.

    def capture(self):
        value = self.native.capture()
        need(type(value.get('featureControlsVersion')) is int and value['featureControlsVersion'] == 1)
        return dict(value, open=value['tabletShown'])

    def activate(self, identifier, *, source=None):
        current = self.capture()
        rows = [row for row in current['controls'] if row['id'] == identifier and row['enabled']]
        need(len(rows) == 1 and (source is None or rows[0].get('sourceUrl') == source))
        locator = Locator('accessibility id', 'OverteNavigation.' + identifier)
        if identifier.startswith(('scripts.', 'script-file.')):
            self.ui.click_with_token(locator, rows[0]['token'])
        else:
            self.ui.click(locator)

    def replace(self, identifier, text):
        need(identifier in {'scripts.url.field', 'script-file.folder'})
        self.native.edit('replace', text, field=identifier)

    def submit(self, identifier):
        need(identifier == 'script-file.folder')
        self.native.edit('submit', field=identifier)

    def select_index(self, identifier, index):
        need(identifier == 'script-file.primary' and type(index) is int and 0 <= index < 32)
        self.activate(identifier)
        self.native.edit('select-index', field=identifier, index=index)

    def tablet(self, opened):
        need(type(opened) is bool)
        self.ui.click(Locator('accessibility id', 'OverteTabletOpen' if opened else 'OverteTabletClose'))

    def release(self):
        self.ui.release_actions()


def runtime(ui, native, observer, session, state):
    io = IOSScriptIO(ui, native)
    observed = io.capture()
    binding = dict(scope='NATIVE_UI_COMPONENT_ONLY', processIdentity=str(observed['processId']),
        sessionId=hashlib.sha256((session + '\0' + observed['instance']).encode()).hexdigest(),
        generation=state['generation'], targetFingerprint=state['targetFingerprint'])
    def observe(after):
        value = observer.read(after)
        return value, observer.epoch_ms()
    return TokenScriptUI(io), observe, binding


def manager(ui, observe, binding, store, *, file_owner=None, file_picker=None):
    options = {} if file_owner is None else dict(source_kind='script-file-bundle',
        file_owner=file_owner, file_picker=file_picker)
    need(file_owner is not None or file_picker is None)
    result = NormalScriptManager(ui, observe, store, binding, component_only=True, **options)
    result.sample()
    return result


def flow(ui, native, observer, store, session, state):
    return manager(*runtime(ui, native, observer, session, state), store)
