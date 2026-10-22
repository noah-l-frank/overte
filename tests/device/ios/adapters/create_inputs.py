"""Ordinary Create recipes with original context tokens and durable input intent.

These recipes report delivery only. Entity, renderer, file, peer and quiet-window
judgments belong to the independent Create observation owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json

from adapters.native_feature_observation import integer, need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import TokenCreateUI, ascii_text
from ios.adapters import create_controls_v2 as controls


class IOSCreateUI(TokenCreateUI):
    def capture(self):
        value = deepcopy(controls.snapshot(self.io.capture())); original = value['scope']
        need(self.instance in (None, original['instance']) and self.pid in (None, original['processId'])
             and original['elapsedMs'] >= self.elapsed and original['sequence'] >= self.sequence
             and (not (type(self.generation) is int and type(original['generation']) is int)
                  or original['generation'] >= self.generation))
        self.instance, self.pid, self.elapsed, self.sequence, self.generation = (
            original[key] for key in ('instance', 'processId', 'elapsedMs', 'sequence', 'generation'))
        return value

    def input(self, identifier, action='activate', value=None):
        need(controls.control_id(identifier) and identifier != 'create.page'
             and action in ('activate', 'replace', 'select-index', 'scroll'))
        if action == 'replace': need(controls.field(identifier)); ascii_text(value)
        elif action == 'select-index': need(controls.choice(identifier) and integer(value, 0, 31))
        elif action == 'scroll': need(identifier == 'create.scrollbar' and value in ('up', 'down'))
        else: need(value is None and identifier != 'create.scrollbar')
        before = self.capture(); row = self.row(before, identifier)
        need(before['open'] and before['ready'] and row is not None)
        if action == 'replace': need(row['focused'])
        if action == 'select-index': need(value < row['count'])
        # Intent must be durable before crossing the input boundary. An unknown
        # return remains owned; this method has no retry path.
        self.intent(dict(createInputVersion=before['createControlsVersion'], action=action,
            controlId=identifier, controlToken=row['token'], scope=deepcopy(before['scope'])))
        if action == 'activate': self.io.activate(identifier, reference=before)
        elif action == 'replace': self.io.replace(identifier, value, reference=before)
        elif action == 'select-index': self.io.select_index(identifier, value, reference=before)
        else: self.io.scroll(identifier, value, reference=before)
        after = self.capture(); need(after['scope']['sequence'] > before['scope']['sequence'])
        return after

    def reveal(self, identifier):
        need(controls.control_id(identifier))
        current = self.capture()
        if self.row(current, identifier): return current
        deadline = self.now()+10
        for direction in ('up', 'down'):
            for _attempt in range(32):
                if self.now() >= deadline: raise NativeUIError('Normal Create reveal timed out')
                current = self.capture()
                if self.row(current, identifier): return current
                bar = self.row(current, 'create.scrollbar')
                if (bar is None or direction == 'up' and bar['position'] <= .000001
                        or direction == 'down' and bar['position']+bar['size'] >= .999999): break
                self.input('create.scrollbar', 'scroll', direction)
                value = self.wait(lambda observed: bool(self.row(observed, 'create.scrollbar') and
                    (self.row(observed, 'create.scrollbar')['position'] < bar['position'] if direction == 'up'
                     else self.row(observed, 'create.scrollbar')['position'] > bar['position'])))
                if self.row(value, identifier): return value
        raise NativeUIError('Normal Create control could not be revealed')

    def choose(self, identifier, index):
        need(controls.choice(identifier) and integer(index, 0, 31))
        self.reveal(identifier); self.input(identifier); self.input(identifier, 'select-index', index)
        return self.wait(lambda value: bool(self.row(value, identifier)
            and self.row(value, identifier)['currentIndex'] == index))

    def selected(self):
        return deepcopy(self.page(self.capture())['selectedIds'])

    def create_domain(self, kind, *, resource=None):
        need(kind in ('model', 'cube', 'voxel') and (resource is None) == (kind != 'model'))
        if kind == 'voxel':
            raise NativeUIError('Use the real filled-volume PolyVox dialog instead of empty NEW PolyVox')
        self.tab(0); self.choose('create.host', 0)
        if kind == 'model': self.replace('create.resource', ascii_text(resource))
        if kind == 'cube': self.choose('create.shape', 0)
        before = set(self.selected()); identifier = {'model': 'create.new-model',
            'cube': 'create.new-shape', 'voxel': 'create.new-voxel'}[kind]
        self.reveal(identifier); self.input(identifier)
        # Do not wait for selection here: denial is a meaningful outcome, and
        # original entity/permission/UI measurements decide denial or success.
        return dict(selectionBefore=sorted(before))

    def name_and_size(self, entity_id, name):
        need(self.selected() == [entity_id]); self.name_entity(ascii_text(name))
        for axis in ('x', 'y', 'z'): self.replace('create.field.dimensions.'+axis, '1')
        self.reveal('create.apply'); self.input('create.apply')

    def create_polyvox(self):
        """Existing detailed Box path; no direct voxel filling or setter."""
        self.tab(0); self.choose('create.host', 0); self.choose('create.detailed-type', 3)
        self.reveal('create.detailed-open'); self.input('create.detailed-open')
        current = self.wait(lambda value: bool(self.row(value, 'create.polyvox.initialShape')))
        root = self.row(current, 'create.polyvox.initialShape')['dialogRootId']
        self.choose('create.polyvox.texturePreset', 1)  # Existing bundled Grass+ground preset.
        for axis in ('X', 'Y', 'Z'): self.replace('create.polyvox.volumeSize'+axis, '8')
        self.choose('create.polyvox.surfaceStyle', 2); self.choose('create.polyvox.initialShape', 0)
        self.reveal('create.polyvox.accept')
        need(self.row(self.capture(), 'create.polyvox.accept')['dialogRootId'] == root)
        self.input('create.polyvox.accept')

    def texture(self, entity_id, url):
        need(self.selected() == [entity_id]); ascii_text(url)
        self.replace('create.property-search', 'textures')
        self.reveal('create.textures')
        self.replace('create.textures', json.dumps({'checker.png': url}, separators=(',', ':')))
        # The ordinary generated typed field uses Apply typed properties.
        self.reveal('create.apply-typed'); self.input('create.apply-typed')

    def open_import(self):
        self.tab(4); self.choose('create.import-host', 0)
        self.reveal('create.import-browse'); self.input('create.import-browse')
        return self.wait_picker('import')

    def wait_picker(self, role):
        need(role in ('import', 'export'))
        return self.wait(lambda value: bool(self.row(value, 'create.'+role+'.cancel')))

    def picker_state(self, role):
        value = self.capture(); rows = [row for row in value['controls']
            if row['id'].startswith('create.'+role+'.') and 'picker' in row]
        need(rows and all(row['picker'] == rows[0]['picker'] for row in rows))
        return deepcopy(controls.picker(rows[0]['picker'], role))

    def cancel_import(self, root_id):
        need(self.picker_state('import')['rootId'] == root_id)
        self.input('create.import.cancel')
        # Native hidden-root/lifetime inventory, rather than this hit-test list,
        # must separately prove destruction and the no-import quiet window.

    def accept_file(self, role, root_id, directory, run):
        controls.owned_path(directory, run)
        need(directory.endswith('/feature-create-'+run)
             and self.picker_state(role)['rootId'] == root_id)
        filename = directory+('/entity-import.json' if role == 'import' else '/export.json')
        controls.owned_path(filename, run)
        self.replace('create.'+role+'.filename', filename)
        need(self.picker_state(role)['rootId'] == root_id)
        self.input('create.'+role+'.accept')

    def export(self, entity_id):
        need(self.selected() == [entity_id]); self.tab(3)
        self.reveal('create.export'); self.input('create.export')
        return self.wait_picker('export')

    def voxel_settings(self, *, mode, shape, remove, dynamics, pointer, diameter, reach):
        need(type(remove) is bool)
        self.tab(3)
        # Subcontrols are hidden in object mode. Restore their real values in
        # voxel mode before restoring the original mode last.
        self.choose('create.voxel.mode', 1)
        for identifier, value in (('shape', shape), ('dynamics', dynamics), ('pointer', pointer)):
            self.choose('create.voxel.'+identifier, value)
        self.reveal('create.voxel.remove'); row = self.row(self.capture(), 'create.voxel.remove')
        need(row is not None)
        if row['checked'] != remove:
            self.input('create.voxel.remove')
            self.wait(lambda value: bool(self.row(value, 'create.voxel.remove')
                and self.row(value, 'create.voxel.remove')['checked'] == remove))
        for key, value in (('diameter', diameter), ('reach', reach)):
            self.replace('create.voxel.'+key, ascii_text(str(value)))
        self.reveal('create.voxel.apply'); self.input('create.voxel.apply')
        if mode != 1: self.choose('create.voxel.mode', mode)

    def close(self):
        need(not any(row['id'].startswith(('create.import.', 'create.export.')) for row in self.capture()['controls']))
        self.input('tablet.home')
        self.wait(lambda value: not self.row(value, 'create.page', enabled=False))
