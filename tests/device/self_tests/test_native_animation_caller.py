"""Original included-code caller counterexamples; no V8/client/compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest

from adapters.native_animation_caller import validate,selected
from adapters.native_animation_history import accept
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_compilations import row


def legacy(kind='override',epoch=20000):
    from adapters.emote_source_profile import pins
    source=next(p for p in pins() if p['id']=='tablet-one-shot-sit-hold-v1')
    return dict(callerVersion=1,method='overrideAnimation' if kind=='override' else 'restoreAnimation',
        sequence=1 if kind=='override' else 2,invokedEpochMs=epoch,
        manager=dict(instance='a'*32,assigned=True,url='qrc:/scripts/system/emote.js',loadGeneration=1,assignedEpochMs=14000),
        code=dict(submitted=True,encoding=source['encoding'],codeUnits=source['codeUnits'],
            sha256=source['sha256'],submittedEpochMs=15000))


def original(kind='override',sequence=1,script_id=17):
    value=legacy(kind,20000)
    value.update(callerVersion=2,sequence=sequence,compilation=row(script_id,resource='qrc:/scripts/system/emote.js'))
    return value


def profile(caller):
    manager=caller['manager']
    return dict(engineInstance=manager['instance'],assignedUrl=manager['url'],loadGeneration=manager['loadGeneration'],
        assignedEpochMs=manager['assignedEpochMs'],code=deepcopy(caller['code']),compilation=deepcopy(caller['compilation']))


def event(caller,sequence=1,kind='override'):
    return dict(kind=kind,eventSequence=sequence,capturedEpochMs=caller['invokedEpochMs'],caller=deepcopy(caller))


class AnimationCallerTests(unittest.TestCase):
    def test_actual_compiled_origin_joins_independent_manager_and_compilation_facts(self):
        caller=original();selected_profile=profile(caller)
        self.assertEqual(caller,validate(caller,'override',20000))
        self.assertEqual(caller,selected(event(caller),selected_profile,after_epoch=19999))

    def test_same_resource_name_with_foreign_script_id_or_code_is_not_the_selected_origin(self):
        caller=original();selected_profile=profile(caller)
        for edit in (dict(scriptId=18),dict(sha256='f'*64),dict(codeUnits=42),dict(compiledEpochMs=18000),dict(resourceName='qrc:/foreign.js')):
            foreign=deepcopy(caller);foreign['compilation'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):selected(event(foreign),selected_profile)

    def test_unknown_dynamic_or_native_origin_is_explicit_but_cannot_become_selected_code(self):
        caller=original();selected_profile=profile(caller);caller['compilation']=None
        self.assertEqual(caller,validate(caller,'override',20000))
        with self.assertRaises(NativeUIError):selected(event(caller),selected_profile)

    def test_legacy_standalone_records_remain_readable_but_cannot_adopt_compiled_caller_identity(self):
        caller=legacy('override',20000);selected_profile=profile(original())
        self.assertEqual(caller,validate(caller,'override',20000))
        with self.assertRaises(NativeUIError):selected(event(caller),selected_profile)
        selected_profile.pop('compilation')
        self.assertEqual(caller,selected(event(caller),selected_profile))
        with self.assertRaises(NativeUIError):selected(event(original()),selected_profile)

    def test_closed_versions_and_original_compilation_clocks_reject_desired_or_future_facts(self):
        caller=original()
        for edit in (dict(callerVersion=True),dict(callerVersion=3),dict(expectedSource='phoneEmote.js'),dict(compilation=dict(scriptId=17))):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(caller|edit,'override',20000)
        caller['compilation']['compiledEpochMs']=20001
        with self.assertRaises(NativeUIError):validate(caller,'override',20000)

    def test_original_call_cursor_and_compilation_cannot_be_changed_after_history_trimming(self):
        a=original();first=dict(historyVersion=2,instance='a'*32,callSequence=1,overrideSequence=1,
            frameSequence=0,droppedEvents=0,droppedFrames=0,events=[event(a)],frames=[])
        before=accept(None,2,first)
        trimmed=deepcopy(first);trimmed.update(droppedEvents=1,events=[])
        before=accept(before,2,trimmed)
        b=original('restore',2);b['compilation']['sha256']='f'*64
        later=deepcopy(trimmed);later.update(callSequence=2,events=[event(b,2,'restore')])
        with self.assertRaises(NativeUIError):accept(before,2,later)
        b['compilation']=deepcopy(a['compilation']);later['events']=[event(b,2,'restore')]
        self.assertEqual(before['origins'],accept(before,2,later)['origins'])

    def test_one_manager_can_call_from_distinct_original_scripts_without_relabelling_either(self):
        first=original();second=original('restore',2,18)
        history=dict(historyVersion=2,instance='a'*32,callSequence=2,overrideSequence=1,
            frameSequence=0,droppedEvents=0,droppedFrames=0,events=[event(first),event(second,2,'restore')],frames=[])
        state=accept(None,2,history);self.assertEqual(2,len(state['origins']))

    def test_caller_version_cannot_switch_inside_one_actual_manager_history(self):
        first=original();second=legacy('restore',20000);second['sequence']=2
        history=dict(historyVersion=2,instance='a'*32,callSequence=2,overrideSequence=1,
            frameSequence=0,droppedEvents=0,droppedFrames=0,events=[event(first),event(second,2,'restore')],frames=[])
        with self.assertRaises(NativeUIError):accept(None,2,history)

    def test_native_dispatch_uses_real_nearest_v8_script_id_and_native_compilation_lookup(self):
        root=Path(__file__).resolve().parents[3]
        engine=(root/'libraries/script-engine/src/v8/ScriptEngineV8.cpp').read_text()
        native=engine[engine.index('int ScriptEngineV8::featureCurrentScriptId()'):engine.index('void ScriptEngineV8::featureRecordCompilation')]
        self.assertIn('StackTrace::CurrentStackTrace(_v8Isolate,1,v8::StackTrace::kScriptId)',native)
        self.assertIn('frame->GetScriptId()',native);self.assertNotIn('GetScriptNameOrSourceURL',native)
        method=(root/'libraries/script-engine/src/v8/ScriptObjectV8Proxy.cpp').read_text()
        self.assertIn('_engine->featureCurrentScriptId() : 0',method)
        manager=(root/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        self.assertIn('manager->_e2eRequiredModules.compilation(originalScriptId)',manager)
        self.assertIn('{"callerVersion",2}',manager)


if __name__=='__main__':unittest.main()
