"""Source-owned Phone NativeCreate normal controls and bounded native choices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.android_script_ui import AndroidScriptUI
from adapters.normal_feature_state import need
from adapters.normal_ui import Locator, NativeUIError


class AndroidCreateUI(AndroidScriptUI):
    def open_create(self):
        self.native.click(self.resource('nav.home'))
        entry = Locator('accessibility id', 'CREATE')
        if not self.native.available(entry):
            for page in range(1, 9):
                button = self.resource('tabletPage.' + str(page))
                if self.native.available(button):
                    self.native.click(button)
                if self.native.available(entry):
                    break
        self.native.click(entry)
        self.wait_create()

    def wait_create(self):
        self.native.wait_control(self.resource('NativeCreateTab_0'))

    def tab(self, index):
        need(type(index) is int and 0 <= index <= 4)
        self.native.click(self.resource('NativeCreateTab_' + str(index)))

    def avatar_host(self, name):
        need(name in {'NativeCreateHost', 'NativeCreateImportHost'})
        self.native.click(self.resource(name))
        # Stock Controls 2 ComboBox options have no objectName. The actual
        # current ComboBox and its option can share an accessibility name;
        # select only the unique visible/enabled native Button option.
        deadline = self.native._now() + self.native.timeout
        for _attempt in range(201):
            self.native._check()
            values = self.native._request('POST', '/elements',
                {'using': 'accessibility id', 'value': 'My avatar'})
            need(type(values) is list and len(values) <= 16)
            choices = []
            for value in values:
                element = self.native._element(value)
                kind = self.native._request('GET', element + '/attribute/className')
                identifier = self.native._request('GET', element + '/attribute/resourceId')
                package = self.native._request('GET', element + '/attribute/package')
                visible = self.native._request('GET', element + '/displayed')
                enabled = self.native._request('GET', element + '/enabled')
                need(type(kind) is str and type(identifier) is str and type(package) is str
                     and type(visible) is bool and type(enabled) is bool)
                if (kind in {'android.widget.Button', 'android.view.View'}
                        and identifier != self.package + ':id/' + name
                        and package == self.package and visible and enabled):
                    choices.append(element)
            self.native._check()
            need(len(choices) <= 1)
            if choices:
                self.native._check()
                self.native._request('POST', choices[0] + '/click', {})
                self.native._check()
                return
            if self.native._now() >= deadline:
                break
            self.native.sleep(0.1)
        raise NativeUIError('Normal Create avatar host choice is unavailable')

    def create_cube(self):
        self.tab(0)
        self.avatar_host('NativeCreateHost')
        # The unowned panel was refused before entry. Its normal, actual shape
        # chooser must expose Cube. Do not rely on a requested shape echo.
        self.native.wait_control(Locator('accessibility id', 'Cube'))
        self.native.click(self.resource('NativeCreateNew_Shape'))

    def select_entity(self, identifier):
        from adapters.normal_create import UUID
        need(type(identifier) is str and UUID.fullmatch(identifier) is not None)
        self.tab(1)
        self.native.click(self.resource('NativeCreateRefresh'))
        self.native.click(self.resource('NativeCreateEntity_' + identifier))
        self.native.wait_control(self.resource('NativeCreateName'))

    def name_entity(self, name):
        self.native.replace_text(self.resource('NativeCreateName'), name)
        self.native.click(self.resource('NativeCreateApply'))

    def edit_properties(self, properties):
        from create_observation import properties as validate
        validate(properties)
        for group, values in properties.items():
            for component, value in values.items():
                self.native.replace_text(self.resource('NativeCreateField_' + group + '_' + component), str(value))
        self.native.click(self.resource('NativeCreateApply'))

    def delete_entity(self):
        self.native.click(self.resource('NativeCreateDelete'))

    def history(self, action):
        need(action in {'undo', 'redo'})
        self.native.click(self.resource('NativeCreate' + action.capitalize()))

    def import_entities(self, url):
        self.tab(4)
        self.avatar_host('NativeCreateImportHost')
        self.native.replace_text(self.resource('NativeCreateImportUrl'), url)
        self.native.click(self.resource('NativeCreateImport'))
