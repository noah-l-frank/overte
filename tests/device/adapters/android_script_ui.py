"""Reviewed Android screen-space Running Scripts UI; no product API input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import xml.etree.ElementTree as ET

from adapters.normal_feature_state import need
from adapters.normal_ui import Locator, NativeUI


class AndroidScriptUI:
    def __init__(self, native, package):
        need(isinstance(native, NativeUI) and package == 'io.github.noah_be.overte.phone')
        self.native, self.package = native, package
        self.field = Locator('class name', 'android.widget.EditText')

    def resource(self, name):
        return Locator('id', self.package + ':id/' + name)

    def tree(self):
        self.native._check()
        source = self.native._request('GET', '/source')
        self.native._check()
        need(type(source) is str and len(source.encode()) <= 2 * 1024 * 1024
             and '<!DOCTYPE' not in source.upper() and '<!ENTITY' not in source.upper())
        try:
            root = ET.fromstring(source)
        except ET.ParseError:
            need(False)
        need(len(list(root.iter())) <= 4096)
        return root

    def tablet_visible(self):
        return self.native.available(self.resource('nav.close'), require_enabled=False)

    def manager_visible(self):
        return self.native.available(self.resource('scriptFromUrl'), require_enabled=False)

    def open_tablet(self):
        self.native.click(self.resource('tablet.open'))
        self.native.wait_control(self.resource('nav.close'))

    def open_manager(self):
        if self.native.available(self.resource('nav.home')):
            self.native.click(self.resource('nav.home'))
        entry = self.resource('app.scripts')
        if not self.native.available(entry):
            for page in range(1, 9):
                button = self.resource('tabletPage.' + str(page))
                if self.native.available(button):
                    self.native.click(button)
                if self.native.available(entry):
                    break
        self.native.click(entry)

    def wait_manager(self):
        self.native.wait_control(self.resource('scriptFromUrl'))

    def dialog(self):
        # TabletQueryDialog has no objectName on its field. Restrict the class
        # locator to that real dialog's displayed label/title and a UNIQUE
        # enabled text field; an unexported modal fails without input.
        root = self.tree()
        labels = {node.get('text') or node.get('content-desc') for node in root.iter()
                  if node.get('package') == self.package and node.get('displayed', 'true') == 'true'}
        need({'Script URL', 'Open and Run Script'} <= labels)
        self.native.wait_control(self.field)

    def open_url_dialog(self):
        self.native.click(self.resource('scriptFromUrl'))
        # Only reads are retried while the native dialog materializes.
        deadline = self.native._now() + self.native.timeout
        for _attempt in range(201):
            try:
                self.dialog()
                return
            except Exception:
                self.native._check()
                if self.native._now() >= deadline:
                    raise
                self.native.sleep(0.1)
        need(False)

    def fill_url(self, url):
        self.dialog()
        self.native.replace_text(self.field, url)
        need(self.native.text(self.field) == url)

    def submit_url(self):
        self.dialog()
        self.native.click(Locator('accessibility id', 'OK'))

    def cancel_dialog(self):
        root = self.tree()
        if any(node.get('text') == 'Script URL' for node in root.iter()):
            self.dialog()
            self.native.click(Locator('accessibility id', 'Cancel'))

    def wait_dialog_absent(self):
        self.native.wait_absent(self.field)

    def check_row(self, index, name, action):
        root = self.tree()
        suffix = str(index)
        identifier = self.package + ':id/script' + action.capitalize() + suffix
        parents = [parent for parent in root.iter() for node in parent
                   if node.get('resource-id') == identifier]
        need(len(parents) == 1)
        # Qt exports the real depth-first children, sometimes omitting the
        # non-accessible RowLayout. In either shape the reviewed row has exactly
        # Label, Restart, Stop in that order. Verify this actual local trio.
        children = list(parents[0])
        stop_id = self.package + ':id/scriptStop' + suffix
        positions = [i for i, node in enumerate(children) if node.get('resource-id') == stop_id]
        need(len(positions) == 1 and positions[0] >= 2)
        label, restart, _stop = children[positions[0] - 2:positions[0] + 1]
        need(restart.get('resource-id') == self.package + ':id/scriptRestart' + suffix
             and label.get('class') == 'android.widget.TextView'
             and (label.get('text') or label.get('content-desc')) == name
             and all(node.get('package') == self.package for node in (label, restart, _stop)))

    def row_action(self, index, name, action):
        self.check_row(index, name, action)
        self.native.click(self.resource('script' + action.capitalize() + str(index)))

    def close_tablet(self):
        if self.tablet_visible():
            self.native.click(self.resource('nav.close'))

    def wait_tablet_absent(self):
        self.native.wait_absent(self.resource('nav.close'))

    def release(self):
        self.native.release_actions()
