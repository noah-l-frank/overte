"""Actual host weak census plus closed original-identity protocol countercases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters import chat_root_loaded_identity as observed
from adapters.native_chat_view import command, measured_view
from adapters.normal_ui import NativeUIError
from ios.self_tests.chat_roots_fixture import ChatRoots, Page, RootBoundary
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet


def cut(ownership, loaded, captured):
    birth = dict(qmlObservedLoadObjectIdentityVersion=1, observerInstance=loaded['instance'],
        **{key: loaded[key] for key in ('loadSequence', 'loadId', 'objectId', 'processId', 'clockDomain')},
        readBefore=dict(epochMs=captured, monotonicMs=captured - 19000),
        readAfter=dict(epochMs=captured, monotonicMs=captured - 19000))
    return dict(chatViewLoadedObjectIdentityCutVersion=1, cutCompletedEpochMs=captured + 1,
        objectLinks=dict(chatRootLoadedObjectLinksVersion=1, census=str(ownership['sequence']),
            rootSourceInstance=ownership['instance'], rootObservationSequence=ownership['sequence'],
            links=[dict(rootIdentity=page['page'], atWalk=deepcopy(birth), atRead=deepcopy(birth)) for page in ownership['pages']]))


class ChatLoadedIdentityTests(unittest.TestCase):
    def fixture(self):
        roots = ChatRoots(pid=42); page = Page(); owned = roots.capture([page])
        loaded = cache_packet(19000)['source']; value = cut(owned, loaded, owned['capturedEpochMs'])
        return roots, page, owned, loaded, value

    def test_same_actual_weak_root_matches_its_loader_birth_and_both_original_reads(self):
        roots, page, owned, loaded, value = self.fixture()
        observed.validate(value, owned, pid=42, captured=owned['capturedEpochMs'])
        self.assertEqual(owned['pages'][0]['page'], observed.match(value, loaded))
        later = roots.capture([page]); current = cut(later, loaded, later['capturedEpochMs'])
        observed.validate(current, later, pid=42, captured=later['capturedEpochMs'], previous=value)
        self.assertEqual(value['objectLinks']['links'][0]['rootIdentity'], current['objectLinks']['links'][0]['rootIdentity'])

    def test_equal_url_and_compiler_hash_cannot_replace_object_load_or_observer_identity(self):
        _roots, _page, _owned, loaded, value = self.fixture()
        for key, replacement in (('instance', '0' * 32), ('objectId', '0' * 32), ('loadId', '0' * 32), ('loadSequence', 2)):
            other = deepcopy(loaded); other[key] = replacement
            self.assertEqual(loaded['cacheAtLoad'], other['cacheAtLoad']); self.assertEqual(loaded['componentUrl'], other['componentUrl'])
            with self.subTest(key=key), self.assertRaises(NativeUIError): observed.match(value, other)

    def test_complete_membership_wrong_census_missing_page_duplicate_and_other_weak_root_refuse(self):
        _roots, _page, owned, _loaded, original = self.fixture()
        for fault in ('source-instance', 'sequence', 'missing', 'duplicate', 'foreign-root', 'numeric-census', 'incomplete'):
            value, census = deepcopy(original), deepcopy(owned); links = value['objectLinks']
            if fault == 'source-instance': links['rootSourceInstance'] = '0' * 32
            elif fault == 'sequence': links['rootObservationSequence'] += 1
            elif fault == 'missing': links['links'] = []
            elif fault == 'duplicate': links['links'].append(deepcopy(links['links'][0]))
            elif fault == 'foreign-root': links['links'][0]['rootIdentity'] = '0' * 32
            elif fault == 'numeric-census': links['census'] = 1
            else: census['complete'] = False
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): observed.validate(value, census, pid=42, captured=census['capturedEpochMs'])

    def test_second_original_weak_read_pid_birth_or_native_clock_cannot_change_inside_cut(self):
        _roots, _page, owned, _loaded, original = self.fixture()
        for fault in ('birth', 'pid', 'clock', 'future', 'body-tail'):
            value = deepcopy(original); row = value['objectLinks']['links'][0]['atRead']
            if fault == 'birth': row['objectId'] = '0' * 32
            elif fault == 'pid': row['processId'] = 43
            elif fault == 'clock': row['clockDomain'] = 'host-wall-clock'
            elif fault == 'future': row['readAfter']['epochMs'] = value['cutCompletedEpochMs'] + 1
            else: value['cutCompletedEpochMs'] = owned['capturedEpochMs'] - 1
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): observed.validate(value, owned, pid=42, captured=owned['capturedEpochMs'])

    def test_cached_hidden_root_reappearance_cannot_adopt_a_new_loader_birth_from_same_url(self):
        roots, page, owned, loaded, before = self.fixture()
        page.in_tree = False; hidden = roots.capture([page]); absent = cut(hidden, loaded, hidden['capturedEpochMs'])
        observed.validate(absent, hidden, pid=42, captured=hidden['capturedEpochMs'], previous=before)
        self.assertTrue(hidden['roots'][0]['weakAlive']); self.assertEqual([], absent['objectLinks']['links'])
        page.in_tree = True; later = roots.capture([page]); other = deepcopy(loaded); other['objectId'] = '0' * 32
        current = cut(later, other, later['capturedEpochMs']); observed.validate(current, later, pid=42, captured=later['capturedEpochMs'], previous=absent)
        with self.assertRaises(NativeUIError): observed.preserve(current['objectLinks']['links'], before['objectLinks']['links'])

    def test_explicit_reader_profile_never_silently_upgrades_legacy_or_accepts_a_legacy_response(self):
        from self_tests.test_native_chat_view import RUN
        boundary = RootBoundary()
        def promote(value):
            loaded = cache_packet(19000)['source']; loaded['processId'] = 123
            value['chatViewVersion'] = 4
            value['loadedObjectIdentity'] = cut(value['source']['rootOwnership'], loaded, value['capturedEpochMs'])
        boundary.final_mutate = promote
        reader = boundary.reader(ios=True, loaded_object_identity=True); value = reader.read(RUN)
        self.assertEqual(dict(open=False, channel='none', draft='', focused=False, keyboard=False, messages=[]), measured_view(value))
        self.assertEqual(2, boundary.commands[-1]['schemaVersion']); self.assertEqual(observed.PROFILE, boundary.commands[-1]['profile'])
        with self.assertRaises(NativeUIError): boundary.reader(ios=True).read(RUN)
        boundary.final_mutate = None
        with self.assertRaises(NativeUIError): boundary.reader(ios=True, loaded_object_identity=True).read(RUN)
        request = dict(schemaVersion=2, action='feature-chat-view-observe', commandId='ios-' + 'f' * 32, runId=RUN, profile=observed.PROFILE)
        for changed in (request | dict(profile='default'), request | dict(expectedObjectId='0' * 32)):
            with self.assertRaises(NativeUIError): command(changed, ios=True)
        with self.assertRaises(NativeUIError): command(request, ios=False)


if __name__ == '__main__': unittest.main()
