"""Actual Pico Python input route; widget/Qt/OS boundaries are synthetic.

No native source, build, headset or device is executed. Persistence reads use
the real native-reader protocol against a separately modeled private host file.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import PicoNavigation, NavigationError, validate_snapshot
from adapters.pico4.normal_places import PicoPlacesIO, project
from adapters.token_places_ui import TokenPlacesUI, snapshot, same_reference, sha
from feature_journeys.fixtures import context

RUN = 'a' * 32
ADDRESS = 'http://controlled.invalid/scene.json?location=/2,0,4'
OTHER_ADDRESS = 'hifi://private-unowned.invalid'


class Widgets:
    """Normal input changes explicit widget state, never an outgoing verdict."""
    bridge = '11111111-1111-4111-8111-111111111111'
    generation = '22222222-2222-4222-8222-222222222222'
    def __init__(self, root):
        self.root = root
        self.clock = 0.
        self.sequence = 0
        self.page = False
        self.tab = 0
        self.dialog = False
        self.original = ''
        self.draft = ''
        self.dialog_address = ''
        self.query = ''
        self.focus = ''
        self.position = 0.
        self.tokens = {}
        self.calls = []
        self.ignore = self.ignore_effect = self.ignore_persistence = self.lose_ack = False
        self.alive = True
        self.before_read = None
        self.edit = None
        self.geometry = (10, 20, 100, 48)
        self.map = {'Private bookmark': OTHER_ADDRESS}
        self.disk = root / 'synthetic-product-bookmarks.json'
        self.persist()
        self.native_sequence = 0
        self.native_packet = None

    def epoch(self):
        return 20000 + round(self.clock * 1000)

    def sleep(self, seconds):
        self.clock += seconds

    def guard(self):
        if not self.alive:
            raise NativeUIError('Synthetic process disappeared')
        return True

    def bind_input(self):
        self.guard()

    def persist(self):
        self.disk.write_text(json.dumps(self.map, sort_keys=True))
        self.disk.chmod(0o600)

    def storage(self):
        raw = self.disk.read_bytes()
        unowned = {k: v for k, v in self.map.items() if k not in (context(RUN)['name'], context(RUN)['renamed'])}
        stat = self.disk.stat()
        return dict(count=len(self.map), mapSha256=sha(json.dumps(self.map, sort_keys=True)),
            unownedCount=len(unowned), unownedSha256=sha(json.dumps(unowned, sort_keys=True)),
            owned=[dict(name=name, addressSha256=sha(self.map[name])) for name in (context(RUN)['name'], context(RUN)['renamed']) if name in self.map],
            storageMatches=json.loads(raw) == self.map,
            file=dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                      revisionSha256=sha(str((stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)))))

    def native_send(self, command):
        self.native_sequence += 1
        self.native_packet = dict(bookmarkObservationVersion=1, commandId=command['commandId'], runId=command['runId'],
            instance='f' * 32, sequence=self.native_sequence, processId=123, requestedEpochMs=self.epoch(),
            capturedEpochMs=self.epoch(), storage=self.storage())

    def bookmarks(self):
        return NativeLocationBookmarks(self.native_send, lambda: json.dumps(self.native_packet), self.epoch,
            self.guard, 123, monotonic=lambda: self.clock, sleep=self.sleep)

    def raw(self):
        controls = []
        state = (self.page, self.tab, self.dialog, self.original, self.draft, self.query, self.focus,
                 tuple(sorted(self.map.items())), self.geometry, self.position)
        def row(identifier, **extra):
            if identifier not in self.tokens or self.tokens[identifier][0] != state:
                self.tokens[identifier] = state, str(uuid.uuid4())
            value = dict(id=identifier, token=self.tokens[identifier][1], enabled=True,
                         focused=self.focus == identifier, inputReady=True)
            value.update(extra);controls.append(value)
            return value
        home = row('tablet.home');home.pop('inputReady')
        if not self.page:
            row('places.entry')
        else:
            entries = [] if self.query == context(RUN)['hidden'] else [dict(placeNameSha256=sha(context(RUN)['name']),
                placeAddressSha256=sha(ADDRESS), placeIdSha256=sha(context(RUN)['destination']))]
            row('places.page', inputReady=False, profile='pico-places-v1', rootInstance='e' * 32, componentSourceSha256='d' * 64,
                tab=self.tab, loading=False, querySha256=sha(self.query), queryLength=len(self.query), currentAddressSha256=sha(ADDRESS),
                directory=dict(count=len(entries), rows=entries),
                bookmarks=dict(count=len(self.map), rows=[dict(bookmarkNameSha256=sha(k), bookmarkAddressSha256=sha(v)) for k, v in sorted(self.map.items())]),
                servers=dict(count=0, rows=[]), maturity=['everyone'], queueCount=0, dispatchTimerRunning=False,
                dialog=dict(visible=self.dialog, originalNameSha256=sha(self.original), addressSha256=sha(self.dialog_address),
                            draftSha256=sha(self.draft), draftLength=len(self.draft)))
            if self.dialog:
                row('places.bookmark.name', textSha256=sha(self.draft), textLength=len(self.draft))
                row('places.bookmark.cancel')
                row('places.bookmark.save')
            else:
                for identifier in ('places.tab.0', 'places.tab.1', 'places.tab.2', 'places.refresh'):
                    row(identifier)
                if self.tab == 0:
                    row('places.search', textSha256=sha(self.query), textLength=len(self.query))
                    for entry in entries:
                        row('places.visit.' + entry['placeNameSha256'], addressSha256=entry['placeAddressSha256'])
                if self.tab == 1:
                    row('places.bookmark.add')
                    for name, address in sorted(self.map.items()):
                        for action in ('visit', 'rename', 'delete'):
                            row('places.bookmark.' + action + '.' + sha(name), addressSha256=sha(address))
        value = dict(schemaVersion=1, bridgeId=self.bridge, generation=self.generation, processId=123,
            elapsedMs=100 + round(self.clock * 1000), updatedEpochMs=self.epoch(), lastCommandSequence=self.sequence,
            open=True, ready=True, placesControlsVersion=1, controls=controls)
        if self.edit:
            self.edit(value)
        return value

    def read(self):
        if self.before_read:
            self.before_read()
        return self.raw(), self.epoch()

    def send(self, command):
        self.calls.append(deepcopy(command))
        if not self.ignore:
            self.sequence += 1
        if not self.ignore and not self.ignore_effect:
            identifier = command['controlId']
            action = command['action']
            if identifier == 'places.entry':
                self.page = True
            elif identifier.startswith('places.tab.'):
                self.tab = int(identifier.rsplit('.', 1)[1]);self.focus = ''
            elif identifier == 'places.bookmark.add':
                self.dialog = True;self.original = '';self.draft = '';self.dialog_address = ADDRESS;self.focus = ''
            elif identifier in ('places.bookmark.name', 'places.search'):
                if action == 'activate':
                    self.focus = identifier
                elif identifier == 'places.bookmark.name':
                    self.draft = command['text']
                else:
                    self.query = command['text']
            elif identifier == 'places.bookmark.cancel':
                self.dialog = False;self.focus = ''
            elif identifier == 'places.bookmark.save':
                if not self.ignore_persistence:
                    self.map[self.draft] = self.dialog_address
                    if self.original:
                        del self.map[self.original]
                    self.persist()
                self.dialog = False;self.focus = ''
            elif identifier.startswith('places.bookmark.'):
                action, name_digest = identifier[len('places.bookmark.'):].split('.')
                name = next(k for k in self.map if sha(k) == name_digest)
                if action == 'rename':
                    self.dialog = True;self.original = name;self.draft = name;self.dialog_address = self.map[name];self.focus = ''
                elif action == 'delete' and not self.ignore_persistence:
                    del self.map[name];self.persist()
        if self.lose_ack:
            raise NativeUIError('Synthetic lost input reply')
        return dict(schemaVersion=1, bridgeId=self.bridge, commandId=command['commandId'], sequence=command['sequence'],
                    performed=True, error='', processId=123, updatedEpochMs=self.epoch()), self.epoch()


class PlacesControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.root.chmod(0o700)
        self.widgets = Widgets(self.root)
        self.store = PrivateFeatureState(self.root / 'intent.json')
        self.navigation = PicoNavigation(self.widgets, self.root / 'navigation.json',
            dict(schemaVersion=1, sourceRevision='a' * 40, artifactSha256='b' * 64, installedCandidateVerified=True),
            '123:synthetic-start', 'http://controlled.invalid/scene.json',
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        self.original = SimpleNamespace(capture=self.navigation.snapshot, navigation=self.navigation)
        self.ui = TokenPlacesUI(PicoPlacesIO(self.original), self.persist, RUN,
                                monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)

    def persist(self, value):
        old = self.store.read()
        self.store.write(dict(intents=(old or dict(intents=[]))['intents'] + [deepcopy(value)]), old)

    def quiet(self, source, expected):
        start = self.widgets.clock
        for _ in range(31):
            self.assertEqual(expected, source.read(RUN)['storage'])
            self.widgets.sleep(.1)
        self.assertGreaterEqual(self.widgets.clock - start, 3)

    def test_normal_cancel_add_rename_cancel_rename_delete_and_original_storage_are_independent(self):
        source = self.widgets.bookmarks()
        baseline = source.read(RUN)['storage']
        self.ui.open()
        self.ui.bookmark_dialog()
        self.ui.replace('places.bookmark.name', context(RUN)['name'])
        self.ui.dismiss_bookmark()
        self.quiet(source, baseline)
        self.ui.bookmark_dialog()
        self.ui.replace('places.bookmark.name', context(RUN)['name'])
        self.ui.dismiss_bookmark(save=True)
        created = source.read(RUN)['storage']
        self.assertEqual([dict(name=context(RUN)['name'], addressSha256=sha(ADDRESS))], created['owned'])
        self.assertEqual(baseline['unownedSha256'], created['unownedSha256'])
        self.ui.bookmark_dialog(original=context(RUN)['name'])
        self.ui.replace('places.bookmark.name', context(RUN)['renamed'])
        self.ui.dismiss_bookmark()
        self.quiet(source, created)
        self.ui.bookmark_dialog(original=context(RUN)['name'])
        self.ui.replace('places.bookmark.name', context(RUN)['renamed'])
        self.ui.dismiss_bookmark(save=True)
        renamed = source.read(RUN)['storage']
        self.assertEqual([dict(name=context(RUN)['renamed'], addressSha256=sha(ADDRESS))], renamed['owned'])
        self.ui.delete_bookmark(context(RUN)['renamed'])
        final = source.read(RUN)['storage']
        self.assertEqual([], final['owned'])
        self.assertEqual(baseline['unownedSha256'], final['unownedSha256'])
        self.assertEqual({'Private bookmark': OTHER_ADDRESS}, json.loads(self.widgets.disk.read_text()))
        self.assertTrue(self.store.read()['intents'])
        self.assertNotIn(OTHER_ADDRESS, json.dumps(self.ui.capture()))

    def test_query_and_loaded_model_are_separate_original_ui_fields(self):
        self.ui.open()
        original = self.ui.page(self.ui.capture())
        self.ui.replace('places.search', context(RUN)['hidden'])
        hidden = self.ui.page(self.ui.capture())
        self.assertEqual(sha(context(RUN)['hidden']), hidden['querySha256'])
        self.assertEqual([], hidden['directory']['rows'])
        self.ui.replace('places.search', context(RUN)['name'])
        visible = self.ui.page(self.ui.capture())
        self.assertEqual(original['directory'], visible['directory'])

    def test_ignored_consumed_or_lost_input_keeps_one_original_durable_intent(self):
        for fault in ('ignore', 'ignore_effect', 'lose_ack'):
            self.setUp()
            setattr(self.widgets, fault, True)
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, NavigationError)):
                self.ui.open()
            self.assertEqual(1, len(self.widgets.calls))
            self.assertEqual(1, len(self.store.read()['intents']))
            self.assertLessEqual(self.widgets.clock, 20.01)

    def test_dialog_save_ack_is_not_a_persisted_bookmark_verdict(self):
        self.ui.open();self.ui.bookmark_dialog()
        self.ui.replace('places.bookmark.name', context(RUN)['name'])
        self.widgets.ignore_persistence = True
        self.ui.dismiss_bookmark(save=True)
        observed = self.widgets.bookmarks().read(RUN)['storage']
        self.assertEqual([], observed['owned'])
        self.assertNotIn('bookmark', self.ui.page(self.ui.capture()))

    def test_changed_context_geometry_draft_or_model_cannot_retarget_a_captured_input(self):
        self.ui.open();self.ui.bookmark_dialog()
        reference = self.ui.capture()
        count = len(self.widgets.calls)
        for mutate, undo in (
            (lambda: setattr(self.widgets, 'geometry', (40, 20, 50, 48)), lambda: setattr(self.widgets, 'geometry', (10, 20, 100, 48))),
            (lambda: setattr(self.widgets, 'draft', 'foreign'), lambda: setattr(self.widgets, 'draft', '')),
            (lambda: self.widgets.map.update(Foreign='hifi://foreign.invalid'), lambda: self.widgets.map.pop('Foreign'))):
            reference = self.ui.capture()
            mutate()
            with self.assertRaises((NativeUIError, NavigationError)):
                PicoPlacesIO(self.original).activate('places.bookmark.cancel', reference=reference)
            undo()
        self.assertEqual(count, len(self.widgets.calls))

    def test_closed_versions_privacy_model_and_field_shapes_fail_before_input(self):
        self.ui.open()
        for edit in (lambda v: v.update(placesControlsVersion=True),
                     lambda v: v['controls'][1].update(expected='visible'),
                     lambda v: v['controls'][1]['directory'].update(count=2),
                     lambda v: v['controls'][1]['directory']['rows'][0].update(placeIdSha256='raw-private-name'),
                     lambda v: v['controls'][1].update(queryLength=True),
                     lambda v: v['controls'][1]['dialog'].update(visible=1)):
            self.widgets.edit = edit
            with self.subTest(edit=edit), self.assertRaises((NativeUIError, NavigationError)):
                self.ui.capture()
        self.widgets.edit = None
        before = len(self.widgets.calls)
        for identifier, action, value in (
            ('places.bookmark.delete.' + sha('Private bookmark'), 'activate', None),
            ('places.server.add', 'activate', None),
            ('places.bookmark.name', 'replace', context(RUN)['hidden']),
            ('places.search', 'replace', 'private search'),
            ('places.search', 'replace', 'line\nreturn')):
            with self.subTest(identifier=identifier), self.assertRaises((NativeUIError, NavigationError)):
                self.ui.input(identifier, action, value)
        self.assertEqual(before, len(self.widgets.calls))

    def test_expired_or_consumed_reference_and_invalid_replacement_do_not_issue_input(self):
        self.ui.open();self.ui.bookmark_dialog()
        reference = self.ui.capture();before = len(self.widgets.calls)
        self.widgets.clock += 5.001
        with self.assertRaises((NativeUIError, NavigationError)):
            PicoPlacesIO(self.original).activate('places.bookmark.cancel', reference=reference)
        reference = self.ui.capture();self.widgets.sequence += 1
        with self.assertRaises((NativeUIError, NavigationError)):
            PicoPlacesIO(self.original).activate('places.bookmark.cancel', reference=reference)
        with self.assertRaises(NativeUIError):
            self.ui.replace('places.bookmark.name', 'Unowned private name')
        self.assertEqual(before, len(self.widgets.calls))


if __name__ == '__main__':
    unittest.main()
