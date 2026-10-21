"""Synthetic compile originals and actual Python replay; no V8/client/compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest

from adapters.native_script_compilations import compilation,validate,accept,EMPTY
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_observation import Boundary,code_source,effect_source
from self_tests.test_native_script_membership import membership_source


def row(script_id=17,source='var actual = "Ω 東京";',resource='qrc:/scripts/system/+android_phoneInterface/phoneEmote.js'):
    raw=source.encode('utf-16-le',errors='surrogatepass')
    return dict(scriptId=script_id,resourceName=resource,encoding='utf-16le-code-units',codeUnits=len(raw)//2,
        sha256=hashlib.sha256(raw).hexdigest(),compiledEpochMs=19000)


def packet(rows=None):return dict(compiledSourcesVersion=1,complete=True,compilations=[row()] if rows is None else rows)


class ScriptCompilationsTests(unittest.TestCase):
    def test_actual_shared_manager_can_retain_distinct_same_named_v8_compilations(self):
        first=packet([row(),row(18,source='var foreign = 1;')]);value=accept(None,first,20000)
        self.assertNotEqual(value['compilations'][0]['sha256'],value['compilations'][1]['sha256'])
        self.assertEqual(value['compilations'][0]['resourceName'],value['compilations'][1]['resourceName'])
        first['compilations'][0]['sha256']='f'*64;self.assertNotEqual(first,value)

    def test_closed_rows_reject_expected_fields_bad_ids_encodings_digests_sizes_and_clocks(self):
        edits=[dict(scriptId=True),dict(scriptId=0),dict(scriptId=2147483648),dict(resourceName='a\n'),
            dict(resourceName='a'*4097),dict(codeUnits=True),dict(codeUnits=-1),dict(codeUnits=4194305),
            dict(encoding='utf-8'),dict(sha256='F'*64),dict(compiledEpochMs=True),dict(compiledEpochMs=20001),
            dict(expected=True),dict(executed=True),dict(codeUnits=0)]
        for edit in edits:
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):compilation(row()|edit,20000)

    def test_empty_code_and_empty_real_resource_name_remain_originals_without_becoming_emote(self):
        value=packet([row(source='',resource='')]);self.assertEqual(value,validate(value,20000))
        self.assertEqual(EMPTY,value['compilations'][0]['sha256'])

    def test_bounded_inventory_never_truncates_or_accepts_duplicate_unsorted_script_ids(self):
        maximum=packet([row(index) for index in range(1,257)]);self.assertEqual(maximum,accept(None,maximum,20000))
        bad=[packet(maximum['compilations']+[row(257)]),packet([row(),row()]),packet([row(18),row(17)]),
            maximum|dict(complete=True,expectedScript='phoneEmote.js'),maximum|dict(compiledSourcesVersion=True)]
        for value in bad:
            with self.subTest(value=str(value)[:60]),self.assertRaises(NativeUIError):validate(value,20000)

    def test_incomplete_inventory_is_explicit_but_cannot_advance_provenance(self):
        value=dict(compiledSourcesVersion=1,complete=False);self.assertEqual(value,validate(value,20000))
        with self.assertRaises(NativeUIError):accept(None,value,20000)
        with self.assertRaises(NativeUIError):validate(value|dict(compilations=[]),20000)

    def test_original_ids_cannot_disappear_relabel_change_bytes_or_be_retimed(self):
        original=packet()
        for edit in (dict(resourceName='qrc:/foreign.js'),dict(sha256='f'*64),dict(codeUnits=2),dict(compiledEpochMs=19001)):
            changed=deepcopy(original);changed['compilations'][0].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):accept(original,changed,20000)
        with self.assertRaises(NativeUIError):accept(original,packet([]),20000)
        appended=packet([row(),row(18)]);self.assertEqual(appended,accept(original,appended,20000))

    def boundary(self):
        source=Boundary();source.rows=[row()]
        def extend(value):
            value['source']['compiledSourceVersion']=1
            value['source']['engines'][0]['compiled']=packet(deepcopy(source.rows))
        source.mutate=extend;return source,source.reader()

    def test_actual_native_script_reader_retains_compile_identities_without_transport_parameters(self):
        source,reader=self.boundary();first=reader.read(0)
        source.rows.append(row(18));second=reader.read(first['sequence'])
        self.assertEqual(2,len(second['source']['engines'][0]['compiled']['compilations']))
        self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[0]))
        self.assertEqual(packet(source.rows),reader.engines['a'*32]['compiled'])

    def test_reader_rejects_changed_originals_or_disappearing_compilation_extension(self):
        for fault in ('changed','missing','incomplete'):
            source,reader=self.boundary();first=reader.read(0)
            if fault=='changed':source.rows[0]['sha256']='f'*64
            elif fault=='missing':source.mutate=None
            else:
                def invalid(value):
                    value['source']['compiledSourceVersion']=1
                    value['source']['engines'][0]['compiled']=dict(compiledSourcesVersion=1,complete=False)
                source.mutate=invalid
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(first['sequence'])
            self.assertEqual(first['sequence'],reader.sequence)

    def test_code_in_a_different_engine_has_an_independent_script_id_namespace(self):
        source,reader=self.boundary();original=source.mutate
        def second(value):
            original(value);other=deepcopy(value['source']['engines'][0]);other['required']['instance']='c'*32
            other['url']='qrc:/different-manager.js';other['compiled']['compilations'][0]['sha256']='f'*64
            value['source']['engines'].append(other)
        source.mutate=second;reader.read(0)
        self.assertNotEqual(reader.engines['a'*32]['compiled'],reader.engines['c'*32]['compiled'])

    def test_an_empty_native_engine_inventory_cannot_hide_a_missing_compilation_extension(self):
        source,reader=self.boundary();first=reader.read(0)
        source.mutate=lambda value:value['source'].update(engines=[])
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        self.assertEqual(first['sequence'],reader.sequence)

    def test_initial_empty_inventory_still_pins_the_observed_native_extension(self):
        source,reader=self.boundary();original=source.mutate
        def empty(value):original(value);value['source']['engines']=[]
        source.mutate=empty;first=reader.read(0);self.assertTrue(reader.compilations_required)
        source.mutate=lambda value:value['source'].update(engines=[])
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_historical_reader_replay_restores_compilation_origins_and_downgrade_guard(self):
        source,reader=self.boundary();original=source.mutate
        def full(value):
            original(value);code_source(value);effect_source(value);membership_source(value)
            value['source'].update(loadSourceVersion=1,loads=dict(complete=True,instance='d'*32,sequence=0,events=[]))
        source.mutate=full;first=reader.read(0);source.rows.append(row(18));second=reader.read(first['sequence'])
        restored=source.reader();commands=len(source.commands);restored.restore_history([first,second])
        self.assertEqual(commands,len(source.commands));self.assertTrue(restored.compilations_required)
        self.assertEqual(reader.engines,restored.engines)
        def missing(value):
            full(value);value['source'].pop('compiledSourceVersion')
            for engine in value['source']['engines']:engine.pop('compiled')
        source.mutate=missing
        with self.assertRaises(NativeUIError):restored.read(second['sequence'])

    def test_native_hooks_capture_actual_v8_code_and_script_id_before_execution_without_native_setters(self):
        root=Path(__file__).resolve().parents[3]
        engine=(root/'libraries/script-engine/src/v8/ScriptEngineV8.cpp').read_text()
        evaluated=engine[engine.index('ScriptValue ScriptEngineV8::evaluate(const QString&'):]
        self.assertLess(evaluated.index('featureRecordCompilation(script,actualSource)'),evaluated.index('script->Run(context)'))
        native=engine[engine.index('void ScriptEngineV8::featureRecordCompilation'):engine.index('ScriptValue ScriptEngineV8::evaluate(const QString&')]
        self.assertIn('original->GetId()',native);self.assertIn('String::Value codeUnits(getIsolate(),actualCode)',native)
        self.assertIn('QCoreApplication::arguments().contains("--testScript")',native)
        self.assertNotIn('QFile',native)
        wrapper=(root/'libraries/script-engine/src/v8/ScriptProgramV8Wrapper.cpp').read_text()
        self.assertIn('_engine->featureRecordCompilation(script,actualSource)',wrapper)
        defaults=(root/'scripts/+android_phoneInterface/defaultScripts.js').read_text()
        self.assertIn('"system/+android_phoneInterface/phoneEmote.js"',defaults)
        self.assertIn('Script.include(PHONE_DEFAULT_SCRIPTS[i])',defaults)
        self.assertNotIn('Script.load("/~/system/+android_phoneInterface/phoneEmote.js")',defaults)


if __name__=='__main__':unittest.main()
