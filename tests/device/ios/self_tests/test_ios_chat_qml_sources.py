"""Strict source/clock semantics, with explicit uncompiled native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import chat_qml_sources as source
from ios.self_tests.chat_qml_source_fixture import ROOT, URL, packet, advance


class ChatQmlSourcesTests(unittest.TestCase):
    def test_reviewed_utf16_pin_and_direct_scope_are_independent_of_the_observed_digest(self):
        raw = (ROOT / 'scripts' / source.QML).read_bytes().decode('utf-8').encode('utf-16le')
        self.assertEqual(dict(codeUnits=len(raw) // 2, sha256=hashlib.sha256(raw).hexdigest()), source.pins())
        value = packet(); copied = source.admit_direct_unit(value, URL)
        copied['compilerInput']['sha256'] = '0' * 64
        self.assertNotEqual(copied, source.admit_direct_unit(value, URL))
        source.original(dict(value, pageControlSourceSha256='9' * 64))
        for field, foreign in (('sha256', '0' * 64), ('codeUnits', 1), ('resolvedUrl', 'qrc:/foreign.qml')):
            changed = deepcopy(value); changed['source']['compilerInput'][field] = foreign
            source.original(changed)
            with self.subTest(field=field), self.assertRaises(NativeUIError):
                source.admit_direct_unit(changed, URL)

    def test_cache_or_foreign_unit_cannot_replace_actual_compiler_input_association(self):
        for field, foreign in (('qtVersion', '6.11.0'), ('unitSha256', '0' * 64), ('compilerUnitBytes', 2049),
                ('unitGeneration', 1000000000), ('encoding', 'utf-8'), ('processId', 43),
                ('qtOverteQmlCompilerInputVersion', True), ('codeUnits', True), ('unitBytes', 4194305)):
            value = packet(); value['source']['compilerInput'][field] = foreign
            with self.subTest(field=field), self.assertRaises(NativeUIError): source.original(value)
        for missing in ('sourceBeforeEpochMs', 'sourceAfterEpochMs', 'compilerUnitSha256', 'unitGeneration'):
            value = packet(); del value['source']['compilerInput'][missing]
            with self.subTest(missing=missing), self.assertRaises(NativeUIError): source.original(value)
        value = packet(); value['source']['compilerInput'] = {}
        with self.assertRaises(NativeUIError): source.original(value)

    def test_original_compile_and_load_clocks_cannot_be_moved_into_a_new_read_envelope(self):
        for fault in ('before-load', 'after-load', 'reverse', 'future', 'load-clock', 'read-clock', 'domain'):
            value = packet(); loaded = value['source']; code = loaded['compilerInput']
            if fault == 'before-load': code['sourceBeforeEpochMs'] = loaded['loadBefore']['epochMs'] - 1
            elif fault == 'after-load': code['compiledEpochMs'] = loaded['loadCompleted']['epochMs'] + 1
            elif fault == 'reverse': code['sourceAfterEpochMs'] = code['sourceBeforeEpochMs'] - 1
            elif fault == 'future': loaded['loadCompleted']['epochMs'] = value['clockBefore']['epochMs'] + 1
            elif fault == 'load-clock': loaded['loadCompleted']['monotonicMs'] += 251
            elif fault == 'read-clock': value['clockAfter']['monotonicMs'] += 251
            else: loaded['clockDomain'] = value['clockDomain']
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): source.original(value)
        value = packet()
        # A historical successful load is not stamped fresh by this current read.
        for name in ('clockBefore', 'clockAfter'):
            value[name]['epochMs'] += 100000; value[name]['monotonicMs'] += 100000
        source.original(value)

    def test_unit_component_and_context_urls_reject_foreign_or_ambiguous_locations(self):
        for foreign in ('file://foreign/armored-chat/armored_chat.qml', URL + '?', URL + '#',
                'https://example.invalid/armored_chat.qml', 'qrc:/scripts/../armored-chat/armored_chat.qml',
                'qrc:/scripts/%2e%2e/armored-chat/armored_chat.qml', URL + '%00'):
            value = packet(); value['source']['componentUrl'] = foreign
            with self.subTest(foreign=foreign), self.assertRaises(NativeUIError): source.original(value)
        value = packet(); value['source']['componentUrl'] = 'qrc:/foreign.qml'
        with self.assertRaises(NativeUIError): source.original(value)
        value = packet(); value['source']['objectContextUrl'] = ''
        source.original(value)

    def test_same_root_preserves_its_exact_original_load_receipt_across_fresh_queries(self):
        before = packet(); after = advance(before)
        query = dict(schemaVersion=1, action=source.ACTION, commandId=after['requestId'], runId=after['runId'])
        source.validate(after, query, 42, previous=before)
        for field in ('creationContextId', 'objectId', 'loadSequence', 'loadCompleted', 'compilerInput'):
            changed = deepcopy(after)
            if field == 'loadSequence': changed['source'][field] += 1
            elif field == 'loadCompleted': changed['source'][field]['epochMs'] += 1
            elif field == 'compilerInput': changed['source'][field]['unitGeneration'] += 1
            else: changed['source'][field] = '9' * 32
            with self.subTest(field=field), self.assertRaises(NativeUIError): source.validate(changed, query, 42, previous=before)

    def test_recreated_root_needs_its_own_later_actual_compilation_and_native_identity(self):
        before = packet(); after = advance(before); loaded = after['source']
        loaded.update(loadSequence=2, loadId='7' * 32, objectId='8' * 32)
        loaded['loadBefore'] = dict(epochMs=loaded['loadBefore']['epochMs'] + 100, monotonicMs=190)
        loaded['loadCompleted'] = dict(epochMs=loaded['loadCompleted']['epochMs'] + 100, monotonicMs=210)
        loaded['compilerInput']['sequence'] += 1
        for key in ('sourceBeforeEpochMs', 'sourceAfterEpochMs', 'compiledEpochMs'): loaded['compilerInput'][key] += 100
        query = dict(schemaVersion=1, action=source.ACTION, commandId=after['requestId'], runId=after['runId'])
        source.validate(after, query, 42, previous=before)
        for fault in ('old-input', 'load-sequence', 'same-object', 'qt-instance', 'loader-instance'):
            value = deepcopy(after)
            if fault == 'old-input': value['source']['compilerInput'] = deepcopy(before['source']['compilerInput'])
            elif fault == 'load-sequence': value['source']['loadSequence'] = 1
            elif fault == 'same-object': value['source']['objectId'] = before['source']['objectId']
            elif fault == 'qt-instance': value['source']['compilerInput']['instance'] = '9' * 32
            else: value['source']['instance'] = '9' * 32
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): source.validate(value, query, 42, previous=before)


if __name__ == '__main__': unittest.main()
