"""Gated actual native call-site wiring; no Qt/V8 compilation is performed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]


class AvatarCallersNativeTests(unittest.TestCase):
    def read(self,path):return (ROOT/path).read_text()

    def test_timer_capture_uses_actual_manager_v8_and_submitted_code_before_both_births(self):
        source=self.read('libraries/script-engine/src/ScriptManager.cpp')
        start=source.index('int ScriptManager::setupTimerWithInterval(');end=source.index('\nint ScriptManager::setInterval(',start);body=source[start:end]
        capture=body.index('AvatarV8Callers::resolve(featureAvatarV8Stack(),')
        self.assertIn('_featureAvatarScript->snapshot().value("code").toList()',body)
        self.assertLess(body.index('newTimer->start(intervalMS);'),capture)
        for observer in ('_featureAvatarScript','_featureAvatarUiWork'):
            self.assertLess(capture,body.index(observer+'->created(handle,avatarCallers,newTimer.get())'))
        self.assertIn('_featureSnapshotTimerWork->created(handle,featureAvatarTimerCallers(),newTimer.get())',body)

    def test_actual_stack_table_keeps_full_originals_and_only_deduplicates_exact_equality(self):
        source=self.read('libraries/script-engine/src/AvatarV8Callers.h')
        self.assertIn('row.value("callerStack")==QVariant(actual.stack)',source)
        self.assertIn('row.value("callerModules")==QVariant(actual.modules)',source)
        self.assertIn('{"id",id},{"callerStack",actual.stack},{"callerModules",actual.modules}',source)
        self.assertNotIn('firstObservedEpochMs',source);self.assertNotIn('expected',source.split('class AvatarV8CallerTable')[1])
        self.assertIn('if (_entries.size()>=128)',source)

    def test_current_timer_sources_reference_immutable_tables_and_snapshot1_remains_legacy(self):
        script=self.read('libraries/script-engine/src/AvatarScriptObservation.h')
        self.assertIn('{"avatarScriptVersion",2}',script);self.assertIn('{"callerStackId",callerId}',script)
        self.assertIn('{"callerStacks",_callers.snapshot()}',script)
        work=self.read('libraries/script-engine/src/AvatarUiWorkObservation.h')
        self.assertIn('if (_version==2) { result.insert("callerStacks",_callers.snapshot()); }',work)
        self.assertIn('QString schema="avatarUiWorkVersion",int version=1',work)
        header=self.read('libraries/script-engine/src/ScriptManager.h')
        first=header.index('_featureSnapshotTimerWork');last=header.index('QStringList featureAvatarTimerCallers()',first)
        self.assertIn('"snapshotTimerWorkVersion")',header[first:last]);self.assertNotIn('"snapshotTimerWorkVersion",2',header[first:last])
        self.assertIn('"avatarUiWorkVersion",2)',header)
        self.assertIn('result["iosAvatarScriptsVersion"]=2',self.read('tests/device/native/IOSAvatarScriptsObservation.h'))

    def test_xhr_open_and_response_getter_capture_actual_same_engine_frames_and_original_bytes(self):
        source=self.read('libraries/script-engine/src/XMLHttpRequestClass.cpp')
        start=source.index('overte::e2e::AvatarV8Callers XMLHttpRequestClass::featureAvatarSocialV8Callers() const')
        end=source.index('void XMLHttpRequestClass::featureAvatarSocialFinished()',start);body=source[start:end]
        self.assertIn('QThread::currentThread()!=_engine->thread()',body)
        self.assertIn('AvatarV8Callers::resolve(manager->featureAvatarV8Stack(),',body)
        self.assertIn('manager->featureAvatarScriptObservation().value("code").toList()',body)
        self.assertIn('callers.top("/modules/request.js")',body);self.assertNotIn('featureAvatarSocialCallers()',body)
        start=source.index('ScriptValue XMLHttpRequestClass::getResponseText() const');end=source.index('return _engine->newValue(QString(_rawResponseData.data()));',start)
        body=source[start:end];self.assertIn('avatarSocialHttp().eventWithCallers(_featureAvatarSocialId,"text-read",',body)
        self.assertIn('QCryptographicHash::hash(_rawResponseData,QCryptographicHash::Sha256)',body)
        self.assertIn('featurePlacesCaller()',body);self.assertNotIn('featureAvatarSocialCallers()',body)
        ledger=self.read('libraries/script-engine/src/AvatarSocialHttpObservation.h')
        self.assertIn('{"iosAvatarSocialHttpVersion",2}',ledger)
        self.assertIn('{"callerStacks",_callers.snapshot()}',ledger)


if __name__=='__main__':unittest.main()
