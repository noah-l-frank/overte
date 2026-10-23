"""Source-only provenance boundaries of the native original-stack accessor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]
CPP=ROOT/'libraries/script-engine/src/ScriptManager.cpp'
HEADER=ROOT/'libraries/script-engine/src/ScriptManager.h'


def body(source,signature):
    start=source.index(signature);begin=source.index('{',start);depth=0
    for index in range(begin,len(source)):
        depth+=(source[index]=='{')-(source[index]=='}')
        if depth==0:return source[begin:index+1]
    raise AssertionError('Unterminated original native method')


def native_boundary(source):
    signature='QVariantMap ScriptManager::featureAvatarV8Stack() const'
    start=source.index(signature)
    if source[:start].rstrip().splitlines()[-1]!='#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)':return False
    actual=body(source,signature)
    required=('overte::e2e::IOSV8ScriptStack::enabled()','!_engine','QThread::currentThread()!=thread()',
        'qobject_cast<ScriptEngineV8*>(_engine.get())','!engine','QThread::currentThread()!=engine->thread()',
        'return engine->featureV8Stack();')
    forbidden=('evaluate(', 'newProgram(', 'newScriptEngine(', 'fileName(', 'currentContext(', 'setProperty(', 'invokeMethod(')
    return all(token in actual for token in required) and not any(token in actual for token in forbidden)


class AvatarV8StackAccessorTests(unittest.TestCase):
    def test_actual_manager_and_engine_threads_gates_and_snapshot_origin_are_required(self):
        actual=CPP.read_text();self.assertTrue(native_boundary(actual))
        for original,replacement in (
            ('QThread::currentThread()!=engine->thread()','false'),
            ('overte::e2e::IOSV8ScriptStack::enabled()','true'),
            ('qobject_cast<ScriptEngineV8*>(_engine.get())','someOtherEngine()'),
            ('return engine->featureV8Stack();','return expectedCallerStack();')):
            with self.subTest(original=original):self.assertFalse(native_boundary(actual.replace(original,replacement,1)))

    def test_legacy_parent_wrapper_walk_is_not_relabelled_as_actual_frames(self):
        actual=CPP.read_text();legacy=body(actual,'QStringList ScriptManager::featureAvatarTimerCallers() const')
        self.assertIn('context->parentContext()',legacy);self.assertIn('function->fileName()',legacy)
        self.assertNotIn('featureV8Stack',legacy)
        header=HEADER.read_text();self.assertIn('QVariantMap featureAvatarV8Stack() const;',header)
        declaration=next(line for line in header.splitlines() if 'featureAvatarV8Stack()' in line)
        self.assertNotIn('Q_INVOKABLE',declaration)
        for filename in ('ScriptManagerScriptingInterface.h','ScriptManagerScriptingInterface.cpp'):
            self.assertNotIn('featureAvatarV8Stack',(ROOT/'libraries/script-engine/src'/filename).read_text())

    def test_delegated_source_is_actual_current_v8_frame_metadata_only(self):
        native=(ROOT/'tests/device/native/IOSV8ScriptStack.h').read_text()
        for token in ('isolate->IsCurrent()','v8::StackTrace::CurrentStackTrace','trace->GetFrame(isolate,i)',
            'frame->GetScriptId()','frame->GetScriptSource()','frame->GetLineNumber()','frame->GetColumn()',
            'firstObservedEpochMs'):
            self.assertIn(token,native)
        self.assertNotIn('Compile(',native);self.assertNotIn('evaluate(',native)


if __name__=='__main__':unittest.main()
