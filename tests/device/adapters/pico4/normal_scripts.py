"""Ordinary native VR tablet Script input on the existing bound Pico route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.pico4.navigation import NativeNavigationIO, PicoNavigation, need
from adapters.token_script_ui import TokenScriptUI
from navigation_observation import viewpoint_urls


def configuration(environment):
    enabled = environment.get('OVERTE_PICO_NORMAL_SCRIPTS', '0')
    need(enabled in {'0', '1'})
    if enabled == '0': return None
    need(environment.get('OVERTE_ANDROID_E2E_DEBUG') == '1'
         and environment.get('OVERTE_PICO_OPENXR_INPUT') == '1')
    scene = environment.get('OVERTE_E2E_SCENE_URL')
    viewpoint_urls(scene)
    return scene


class PicoScriptIO:
    def __init__(self, navigation):
        self.navigation = navigation
        navigation.io.bind_input()
        value = navigation.snapshot()
        need(type(value.get('featureControlsVersion')) is int and value['featureControlsVersion'] == 1)
        self.bridge = value['bridgeId']
        navigation.io.bind_input()

    def capture(self):
        self.navigation.io.bind_input()
        value = self.navigation.snapshot()
        need(value['bridgeId'] == self.bridge)
        self.navigation.io.bind_input()
        return value

    def activate(self, identifier, *, source=None):
        value = self.capture()
        if source is not None:
            row = self.navigation.control(value, identifier)
            need(row is not None and row.get('sourceUrl') == source)
        self.navigation.input(identifier, source=source)

    def replace(self, identifier, text):
        self.navigation.input(identifier, 'replace', text)

    def submit(self, identifier):
        need(identifier == 'script-file.folder')
        self.navigation.input(identifier, 'submit')

    def select_index(self, identifier, index):
        need(identifier == 'script-file.primary')
        self.activate(identifier)
        self.navigation.input(identifier, 'select-index', index=index)

    def tablet(self, opened):
        need(type(opened) is bool)
        self.navigation.controller('tablet.open' if opened else 'tablet.close')

    def release(self):
        # Every native pointer/key operation releases its own input in the
        # source transport. There is no script-owned held Controller mapping.
        self.navigation.io.bind_input()


def runtime(adapter, target, scene, installed, identity, ui_path, controller, *, before_native=None, original_reader=None):
    need(before_native is None or callable(before_native))
    need(original_reader is None or callable(original_reader))
    native = NativeNavigationIO(adapter, target, identity, controller)
    binding_check=None if before_native is None else before_native(native)
    need(before_native is None or callable(binding_check))
    navigation = PicoNavigation(native, ui_path, installed, identity, scene)
    io = PicoScriptIO(navigation)  # Refuse a missing actual producer before UI.
    observer = (adapter._feature_observer(target) if original_reader is None else
        adapter._feature_observer(target, original_reader=original_reader))
    def observe(after):
        value = observer.read(after)
        return value, adapter.adb.epoch_milliseconds(target)
    binding = {key: installed[key] for key in ('sourceRevision', 'artifactSha256')}
    binding.update(processIdentity=identity, sessionId=io.bridge, generation=0,
        targetFingerprint=hashlib.sha256((target + '\0' + str(adapter.pico_configuration)).encode()).hexdigest())
    if binding_check is not None:need(binding_check(binding) is not False)
    return TokenScriptUI(io), observe, binding


def manager(ui, observe, binding, state_path, *, file_owner=None, file_picker=None):
    options = {} if file_owner is None else dict(source_kind='script-file-bundle',
        file_owner=file_owner, file_picker=file_picker)
    need(file_owner is not None or file_picker is None)
    result = NormalScriptManager(ui, observe, PrivateFeatureState(state_path), binding, **options)
    result.sample()
    return result


def flow(adapter, target, scene, installed, identity, state_path, ui_path, controller):
    return manager(*runtime(adapter, target, scene, installed, identity, ui_path, controller), state_path)
