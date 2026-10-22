"""Original three editor QML pages and native IME/pending-event context checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_lifecycle_editor import source


class LifecycleEditorNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/lifecycle-editor-native';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='qt-',dir=parent);cls.addClassCleanup(cls.temp.cleanup);cls.stage=Path(cls.temp.name)
        for original,relative in [(ROOT/'scripts/system/create/qml', 'scripts/system/create/qml'),
                (ROOT/'scripts/communityScripts/armored-chat','scripts/communityScripts/armored-chat')]:
            shutil.copytree(original,cls.stage/relative)
        dialogs=cls.stage/'qml/hifi/dialogs';dialogs.mkdir(parents=True)
        for name in ('TabletRunningScripts.qml','NativeModelTree.qml','NativeKeyboardHost.qml'):
            shutil.copyfile(ROOT/'interface/resources/qml/hifi/dialogs'/name,dialogs/name)
        controls=cls.stage/'controlsUit';controls.mkdir()
        (controls/'qmldir').write_text('module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\nKeyboard 1.0 Keyboard.qml\n')
        (controls/'TouchUiMetrics.qml').write_text('import QtQml\nQtObject { readonly property bool systemImeAvailable:true }\n')
        (controls/'Keyboard.qml').write_text('import QtQuick\nItem {property bool raised:false;property bool numeric:false;property bool password:false;property real keyboardWidth:640;property real raisedHeight:300}\n')
        raw=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();start=raw.index('QVariantMap TestScriptingInterface::phoneLifecycleEditor(')
        method=raw[start:raw.index('\n}',start)+2]
        seams='''
#include <QSharedPointer>
class OffscreenUi {public:QQuickItem* root{nullptr};QQuickWindow* window{nullptr};QQuickItem* getRootItem(){return root;}QQuickWindow* getWindow(){return window;}};
class TabletScriptingInterface {public:QVariantMap getTouchUiRuntimeMetrics(){return {{"valid",true},{"keyboardVisible",false}};}};
class LifecycleDependencies {public:template<class T>static QSharedPointer<T>& service(){static QSharedPointer<T> value;return value;}
template<class T>static bool isSet(){return !service<T>().isNull();}template<class T>static QSharedPointer<T> get(){return service<T>();}};
class TestScriptingInterface:public QObject {public:QVariantMap phoneLifecycleEditor(const QVariantMap& command);
struct Lifecycle {QVariantMap snapshot(){return {{"explicit-host-seam",true}};}};
QString _testResultsLocation{"explicit-host-only"},_featureObservationInstance{QString(32,'f')};
std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
std::shared_ptr<overte::e2e::PhoneLifecycleEditor> _phoneLifecycleEditor;quint64 _phoneLifecycleEditorSequence{0};};
#define DependencyManager LifecycleDependencies
'''+method+'\n#undef DependencyManager\n'
        cpp=cls.stage/'lifecycle-editor-runtime.cpp';cpp.write_text((ROOT/'android/phone/tests/device/lifecycle-editor-runtime.cpp').read_text().replace('// ORIGINAL_TEST_BINDING',seams))
        subprocess.run(['/usr/lib64/qt6/libexec/moc',str(cpp),'-o',str(cls.stage/'lifecycle-editor-runtime.moc')],check=True,timeout=30)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Quick','Qt6Qml','Qt6Test'],text=True));cls.binary=cls.stage/'check'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),
            '-I'+str(cls.stage),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),str(cpp),
            str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(cls.binary),*flags],check=True,timeout=30)
    def case(self,mode):
        result=subprocess.run([str(self.binary),str(self.stage),mode,'--testScript'],text=True,capture_output=True,timeout=15,
            env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','XDG_CONFIG_HOME':str(self.stage/'config')})
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        for line in result.stdout.splitlines():
            packet=json.loads(line);source(packet['source'],'a'*32,packet['capturedEpochMs']);self.assertEqual('none',packet['source']['current']['status'])
    def test_actual_create_chat_scripts_native_text_and_real_retired_pending_event(self):self.case('normal')
    def test_foreign_field_token_does_not_focus_actual_editor(self):self.case('foreign-token')
    def test_private_external_draft_is_unavailable_and_never_exported(self):self.case('private-text')
    def test_same_named_foreign_qml_source_and_duplicate_actual_fields_are_unavailable(self):self.case('foreign-source');self.case('ambiguous')

if __name__=='__main__':unittest.main()
