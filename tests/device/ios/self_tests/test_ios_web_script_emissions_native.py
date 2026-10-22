"""No-build source checks at exact original Qt/V8 invocation boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]
PROPOSED=Path(os.environ.get('OVT_IOS_NATIVE_SOURCE_ROOT',ROOT))
def read(path):
    proposed=PROPOSED/path
    return (proposed if proposed.exists() else ROOT/path).read_text()


class WebScriptEmissionNativeTests(unittest.TestCase):
    def test_world_relay_keeps_original_public_listener_position_and_Qt_receiver_cancellation(self):
        raw=read('libraries/entities-renderer/src/RenderableWebEntityItem.cpp')
        body=raw.split('void WebEntityRenderer::emitScriptEvent(',1)[1]
        self.assertEqual('const QVariant& message) {\n    emit scriptEventReceived(message);\n}',body.strip())
        registration=raw.split('_webSurface->resume();',1)[1].split('const EntityItemID entityItemID',1)[0]
        self.assertIn('&WebEntityRenderer::featureScriptEventReceived,\n            _webSurface.data(), &OffscreenQmlSurface::featureEmitScriptEvent, Qt::AutoConnection',registration)
        relay=registration.split('&WebEntityRenderer::scriptEventReceived,this,[this]',1)[1].split('},Qt::DirectConnection)',1)[0]
        self.assertIn('emit featureScriptEventReceived(message,nativeCapture)',relay)
        for unsafe in ('_webSurface','QPointer','invokeMethod','receiver.data()'):self.assertNotIn(unsafe,relay)
        self.assertIn('} else\n#endif\n    {\n    _connections.push_back(QObject::connect(this, &WebEntityRenderer::scriptEventReceived, _webSurface.data(), &OffscreenQmlSurface::emitScriptEvent));',registration)
        actual=read('interface/src/Application_Setup.cpp')
        route=actual.split('EntityTree::setEmitScriptEventOperator(',1)[1].split('});',1)[0]
        self.assertIn('auto entity = entities->renderableForEntityId(id)',route);self.assertIn('entity->emitScriptEvent(message)',route)

    def test_each_actual_slot_clears_foreign_TLS_and_preserves_one_original_body_even_on_metadata_failure(self):
        for name,path in (('OffscreenQmlSurface','libraries/ui/src/ui/OffscreenQmlSurface.cpp'),('QmlWindowClass','libraries/ui/src/QmlWindowClass.cpp')):
            raw=read(path);body=raw.split('void '+name+'::featureEmitScriptEvent(',1)[1].split('\n#endif',1)[0]
            self.assertIn('Scope neutral({})',body);self.assertIn('qMetaTypeId<overte::e2e::web_script_emissions::Capture>()',body)
            self.assertIn('qvariant_cast<overte::e2e::web_script_emissions::Capture>',body)
            self.assertEqual(2,body.count('emitScriptEvent(message);')) # inactive early return + one active original
            self.assertLess(body.index('catch (...)'),body.rindex('emitScriptEvent(message);'))
            self.assertNotIn('delete ',body);self.assertNotIn('QPointer',body)
        tablet=read('libraries/ui/src/ui/TabletScriptingInterface.cpp').split('void TabletProxy::emitScriptEvent(',1)[1].split('void TabletProxy::',1)[0]
        self.assertIn('invokeMethod(this,[this,msg,capture]',tablet);self.assertIn('Dispatch dispatched(capture,true)',tablet)
        self.assertNotIn('target.data()',tablet);self.assertNotIn('Qt::BlockingQueuedConnection',tablet)

    def test_compiled_identity_is_actual_indexed_frame_source_not_a_URL_alias_or_top_wrapper(self):
        header=read('tests/device/native/IOSV8ScriptStack.h')
        for actual in ('frame->GetScriptSource()','frame->GetScriptName()','v8::String::Value units(isolate,source)',
                '(*units)[j]','_scripts.insert(scriptId,actualCode)','CurrentStackTrace(isolate,33,',
                'static_cast<v8::StackTrace::StackTraceOptions>(v8::StackTrace::kDetailed|v8::StackTrace::kScriptId)',
                'trace->GetFrame(isolate,i)','frame->GetScriptId()','frame->GetLineNumber()','frame->GetColumn()',
                'actualCode.value("urlSha256")!=urlSha256'):
            self.assertIn(actual,header)
        for forbidden in ('functionContext(', 'parentContext(', 'GetFunctionName(', 'evaluate(', 'QFile', 'arguments[', 'compiledEpochMs'):
            self.assertNotIn(forbidden,header)
        engine=read('libraries/script-engine/src/v8/ScriptEngineV8.h')
        self.assertLess(engine.index('#include <QtCore/QByteArray>'),engine.index('#include "../../../../tests/device/native/IOSV8ScriptStack.h"'))
        self.assertIn('std::unique_ptr<overte::e2e::IOSV8ScriptStack> _featureV8Stack',engine)
        self.assertNotIn('featureV8Compiled',engine)
        repeated=header.split('if(_scripts.contains(scriptId))',1)[1].split('else if(scriptId',1)[0]
        self.assertIn('original.remove("firstObservedEpochMs");candidate.remove("firstObservedEpochMs")',repeated)
        self.assertIn('actualCode["firstObservedEpochMs"]=first.value("firstObservedEpochMs")',repeated)
        self.assertNotIn('_scripts.insert',repeated)

    def test_actual_native_scope_gets_emit_only_stack_without_mutating_Avatar_timer_or_other_caller_grammar(self):
        proxy=read('libraries/script-engine/src/v8/ScriptObjectV8Proxy.cpp')
        block=proxy.split('const QMetaMethod& meta = _metas[bestMeta];',1)[1].split('int returnTypeId',1)[0]
        self.assertIn('meta.name()=="emitScriptEvent"',block);self.assertIn('_engine->featureV8Stack()',block)
        self.assertIn('(_engine->manager(),meta.name(),featureEmitStack)',block)
        manager=read('libraries/script-engine/src/ScriptManager.cpp')
        context=manager.split('FeatureNativeCallScope::FeatureNativeCallScope(ScriptManager*',1)[1].split('FeatureNativeCallScope::~',1)[0]
        self.assertIn('if (method=="emitScriptEvent")',context);self.assertIn('++manager->_featureNativeCallSequence',context)
        self.assertIn('if (method=="addEntity" || method=="deleteEntity")',context)
        self.assertEqual(read('libraries/script-engine/src/ScriptManager.cpp').split('QStringList ScriptManager::featureAvatarTimerCallers()',1)[1].split('\n#endif',1)[0],
            (ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text().split('QStringList ScriptManager::featureAvatarTimerCallers()',1)[1].split('\n#endif',1)[0])

    def test_capture_owns_metadata_only_and_real_callback_return_never_implies_weak_expiry(self):
        raw=read('tests/device/native/IOSWebScriptEmissions.h')
        self.assertIn('QPointer<QObject> value',raw);self.assertIn('std::weak_ptr<void> capture',raw)
        self.assertIn('struct Capture {CallPointer call;std::shared_ptr<Queue> row;std::shared_ptr<void> life;}',raw)
        self.assertIn('row->capture.expired() && row->expired.isEmpty()',raw)
        self.assertIn('std::uncaught_exceptions()==_exceptions',raw);self.assertIn('Scope _scope',raw)
        self.assertIn('fixture(row->identity)!=root',raw);self.assertIn('!echo(message)',raw)
        self.assertNotIn('QSharedPointer<QObject>',raw);self.assertNotIn('shared_ptr<QObject>',raw)
        self.assertNotIn('setParent(',raw);self.assertNotIn('processEvents(',raw)


if __name__=='__main__':unittest.main()
