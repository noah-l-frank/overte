"""Owned ordinary Create foundation; independent entity journal judges effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import math

from adapters.normal_feature_state import context, need
from adapters.normal_ui import NativeUIError
from contracts import validate_operation_arguments
from create_observation import OPERATIONS, PREFIX, NAME, owned_url

UUID = re.compile(r'(?:\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}|'
                  r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})')


def avatar_entities(value):
    need(value.get('entitiesComplete') is True and type(value.get('entitiesComplete')) is bool
         and type(value.get('avatarEntities')) is list and len(value['avatarEntities']) <= 256)
    ids = set()
    for row in value['avatarEntities']:
        need(type(row) is dict and set(row) == {'id', 'name', 'type'}
             and type(row['id']) is str and UUID.fullmatch(row['id']) is not None
             and row['id'].lower().strip('{}') not in ids
             and type(row['name']) is str and len(row['name']) <= 256
             and type(row['type']) is str and 1 <= len(row['type']) <= 64)
        ids.add(row['id'].lower().strip('{}'))
    return value['avatarEntities']


class NormalCreate:
    def __init__(self, ui, scripts, store, binding):
        need(scripts.source_kind == 'create-observer')
        self.ui, self.scripts, self.store = ui, scripts, store
        self.binding = dict(context(binding))
        self.previous = store.read()
        self.state = self.previous or dict(schemaVersion=1, binding=self.binding, scriptUrl=None,
            names=[], ownedIds={}, pendingBeforeIds=None, pendingName=None,
            pendingImportBeforeIds=None, historyOwned=False, importAttempted=False)
        value = self.state
        need(type(value) is dict and set(value) == {'schemaVersion', 'binding', 'scriptUrl', 'names', 'ownedIds',
             'pendingBeforeIds', 'pendingName', 'pendingImportBeforeIds', 'historyOwned', 'importAttempted'}
             and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
             and context(value['binding']) == self.binding
             and type(value['historyOwned']) is bool and type(value['importAttempted']) is bool
             and type(value['names']) is list and len(value['names']) <= 3
             and all(type(name) is str and NAME.fullmatch(name) for name in value['names'])
             and len(set(value['names'])) == len(value['names']))
        need(type(value['ownedIds']) is dict and set(value['ownedIds']) <= set(value['names'])
             and all(type(ids) is list and 1 <= len(ids) <= 16
                     and len(set(ids)) == len(ids)
                     and all(type(item) is str and UUID.fullmatch(item) for item in ids)
                     for ids in value['ownedIds'].values()))
        if value['scriptUrl'] is not None:
            nonce = owned_url(value['scriptUrl'], {'observer.js'})
            need(all(NAME.fullmatch(name)[1] == nonce for name in value['names']))
        else:
            need(not value['names'] and not value['historyOwned'] and not value['importAttempted'])
        need((value['pendingBeforeIds'] is None and value['pendingName'] is None)
             or type(value['pendingBeforeIds']) is list and len(value['pendingBeforeIds']) <= 256
             and all(type(item) is str and UUID.fullmatch(item) for item in value['pendingBeforeIds'])
             and value['pendingName'] in value['names'])
        need(value['pendingImportBeforeIds'] is None or type(value['pendingImportBeforeIds']) is list
             and len(value['pendingImportBeforeIds']) <= 256
             and all(type(item) is str and UUID.fullmatch(item) for item in value['pendingImportBeforeIds']))

    def mark(self, **changes):
        value = self.state | changes
        self.store.write(value, self.previous)
        self.state = self.previous = value

    def sample(self):
        return avatar_entities(self.scripts.sample_full())

    def wait(self, predicate):
        started = previous = self.scripts.monotonic()
        need(type(started) in (int, float) and math.isfinite(started))
        for _attempt in range(41):
            rows = self.sample()
            if predicate(rows):
                return rows
            now = self.scripts.monotonic()
            need(type(now) in (float, int) and math.isfinite(now) and now >= previous)
            previous = now
            if now - started >= 10:
                break
            self.scripts.sleep(0.25)
        raise NativeUIError('Normal Create did not observe its owned native entity transition')

    def owned_names(self, names):
        nonce = owned_url(self.state['scriptUrl'], {'observer.js'})
        need(all(type(name) is str and NAME.fullmatch(name) and NAME.fullmatch(name)[1] == nonce
                 for name in names))

    def resolve(self, rows, name):
        found = [row for row in rows if row['name'] == name]
        need(len(found) <= 1)
        return found[0] if found else None

    def remember_owned_effect(self, rows):
        # Only called following an owned creation/import/history operation.
        # A historically owned name alone must not authorize a later foreign ID.
        ids = {name: list(values) for name, values in self.state['ownedIds'].items()}
        for name in self.state['names']:
            row = self.resolve(rows, name)
            if row is not None:
                need(row['type'] in {'Shape', 'Box'})
                ids.setdefault(name, [])
                if row['id'] not in ids[name]:
                    need(len(ids[name]) < 16)
                    ids[name].append(row['id'])
        self.mark(ownedIds=ids)

    def require_owned_id(self, row):
        need(row['id'] in self.state['ownedIds'].get(row['name'], []))

    def recover_import(self):
        before = self.state['pendingImportBeforeIds']
        if before is None:
            return
        rows = self.sample()
        names = [PREFIX + owned_url(self.state['scriptUrl'], {'observer.js'}) + '_' + role
                 for role in ('import-parent', 'import-child')]
        found = [self.resolve(rows, name) for name in names]
        # A timed-out import has no exposed cancellation/completion token.
        # Retire intent only after its complete actual owned result appeared;
        # absence cannot prove an outstanding import will never finish later.
        need(all(row is not None and row['id'] not in before for row in found))
        self.remember_owned_effect(rows)
        self.mark(pendingImportBeforeIds=None)

    def recover_pending(self, *, delete=False):
        if self.state['pendingBeforeIds'] is None:
            return
        rows = self.sample()
        added = [row for row in rows if row['id'] not in self.state['pendingBeforeIds']]
        need(len(added) <= 1)
        if not added:
            # Retain an uncertain intent until a full fresh three-second window
            # has observed no late native creation. Never turn a failed read
            # into absence or simply forget an unacknowledged Shape click.
            started = self.scripts.monotonic()
            for _attempt in range(33):
                self.scripts.sleep(0.1)
                rows = self.sample()
                added = [row for row in rows if row['id'] not in self.state['pendingBeforeIds']]
                need(len(added) <= 1)
                if added or self.scripts.monotonic() - started >= 3:
                    break
            need(bool(added) or self.scripts.monotonic() - started >= 3)
        if added:
            # Exactly one new actual avatar entity after the recorded Create
            # intent. Keep its ID while naming, including an uncertain response.
            need(added[0]['type'] in {'Shape', 'Box'})
            self.ui.select_entity(added[0]['id'])
            if delete:
                # Cleanup must not depend on the failed name/edit path being
                # functional. This native ID was measured after our recorded
                # Shape input and was absent from the saved pre-input scope.
                identifier = added[0]['id']
                self.ui.delete_entity()
                self.wait(lambda current: not any(row['id'] == identifier for row in current))
            else:
                self.ui.name_entity(self.state['pendingName'])
                rows = self.wait(lambda current: self.resolve(current, self.state['pendingName']) is not None)
                self.remember_owned_effect(rows)
        self.mark(pendingBeforeIds=None, pendingName=None)

    def open(self, script_url):
        nonce = owned_url(script_url, {'observer.js'})
        need(self.state['scriptUrl'] in (None, script_url))
        if self.state['scriptUrl'] is None:
            rows = self.sample()
            need(not any(row['name'].startswith(PREFIX + nonce + '_') for row in rows))
            self.mark(scriptUrl=script_url)
        self.scripts.open()
        if not self.scripts.state['loadAttempted']:
            self.scripts.load_source(script_url)
        self.ui.open_create()
        self.ui.wait_create()

    def delete(self, names):
        self.owned_names(names)
        self.recover_import()
        self.recover_pending(delete=True)
        for name in names:
            rows = self.sample()
            row = self.resolve(rows, name)
            if row is None:
                continue
            need(name in self.state['names'])
            self.require_owned_id(row)
            self.ui.select_entity(row['id'])
            self.ui.delete_entity()
            self.wait(lambda current: self.resolve(current, name) is None)

    def close(self, script_url):
        need(self.state['scriptUrl'] in (None, script_url))
        if self.state['scriptUrl'] is not None:
            self.delete(self.state['names'])
            # Do not stop the independent read-only observer before measuring
            # actual empty owned scope. Unnamed partial creates remain tracked.
            self.recover_pending()
            prefix = PREFIX + owned_url(script_url, {'observer.js'}) + '_'
            need(not any(row['name'].startswith(prefix) for row in self.sample()))
            self.scripts.open()
            if self.scripts.state['source'] is not None:
                self.scripts.stop_source(script_url)
        self.scripts.close()
        self.store.discard(self.previous)
        self.previous = None

    def invoke(self, operation, arguments):
        need(operation in OPERATIONS)
        arguments = validate_operation_arguments(operation, arguments)
        if operation == 'create.reference.open':
            self.open(arguments['scriptUrl'])
        elif operation == 'create.reference.close':
            self.close(arguments['scriptUrl'])
        else:
            need(self.state['scriptUrl'] is not None)
            self.ui.wait_create()
            self.recover_import()
            if operation == 'create.cube':
                name = arguments['name']
                self.owned_names([name])
                need(name.endswith('_cube') and name not in self.state['names'])
                rows = self.sample()
                need(self.resolve(rows, name) is None)
                self.mark(names=self.state['names'] + [name], historyOwned=True,
                          pendingBeforeIds=[row['id'] for row in rows], pendingName=name)
                self.ui.create_cube()
                before = set(self.state['pendingBeforeIds'])
                self.wait(lambda current: len([row for row in current if row['id'] not in before]) >= 1)
                self.recover_pending()
                self.ui.edit_properties(arguments['properties'])
            elif operation == 'create.update':
                name = arguments['name']
                self.owned_names([name])
                need(name in self.state['names'])
                row = self.resolve(self.sample(), name)
                need(row is not None)
                self.require_owned_id(row)
                self.ui.select_entity(row['id'])
                self.ui.edit_properties(arguments['properties'])
            elif operation == 'create.delete':
                self.delete(arguments['names'])
            elif operation in {'create.undo', 'create.redo'}:
                need(self.state['historyOwned'])
                self.ui.history(operation.rsplit('.', 1)[1])
                # History can recreate real native IDs. Measure a stable fresh
                # post-input identity set; never invent IDs from entity names.
                previous = None
                started = self.scripts.monotonic()
                stable = started
                rows = []
                for _attempt in range(41):
                    rows = self.sample()
                    identities = sorted((row['id'], row['name']) for row in rows)
                    now = self.scripts.monotonic()
                    need(type(now) in (int, float) and math.isfinite(now) and now >= stable)
                    if identities != previous:
                        previous, stable = identities, now
                    if now - stable >= 0.5:
                        break
                    need(now - started < 10)
                    self.scripts.sleep(0.25)
                need(self.scripts.monotonic() - stable >= 0.5)
                self.remember_owned_effect(rows)
            elif operation == 'create.import':
                url = arguments['url']
                base = self.state['scriptUrl'].removesuffix('observer.js')
                need(url in (base + 'entities.json', base + 'missing.json'))
                names = [PREFIX + owned_url(url, {'entities.json', 'missing.json'}) + '_' + role
                         for role in ('import-parent', 'import-child')]
                rows = self.sample()
                need(not any(self.resolve(rows, name) for name in names))
                self.mark(names=sorted(set(self.state['names']) | set(names)),
                          historyOwned=True, importAttempted=True,
                          pendingImportBeforeIds=[row['id'] for row in rows] if url.endswith('entities.json') else None)
                self.ui.import_entities(url)
                if url.endswith('entities.json'):
                    rows = self.wait(lambda current: all(self.resolve(current, name) for name in names))
                    self.remember_owned_effect(rows)
                    self.mark(pendingImportBeforeIds=None)
        return {'performed': True}
