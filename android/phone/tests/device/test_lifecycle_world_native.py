"""Actual ordinary Qt input and original KeyboardMouse source component checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import os
import shlex
import subprocess
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_lifecycle_world import validate


def method(raw,signature):
    start=raw.index(signature);opening=raw.index('{',start);depth=0
    for offset in range(opening,len(raw)):
        if raw[offset]=='{':depth+=1
        elif raw[offset]=='}':
            depth-=1
            if depth==0:return raw[start:offset+1]
    raise AssertionError('Original native method is incomplete')


class LifecycleWorldNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/lifecycle-world-native';parent.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='qt-',dir=parent);cls.addClassCleanup(cls.temporary.cleanup);cls.stage=Path(cls.temporary.name)
        raw=(ROOT/'libraries/input-plugins/src/input-plugins/KeyboardMouseDevice.cpp').read_text()
        functions='\n'.join(method(raw,signature) for signature in ['void KeyboardMouseDevice::keyPressEvent(',
            'void KeyboardMouseDevice::keyReleaseEvent(','QVariantMap KeyboardMouseDevice::e2eForwardKeyObservation(',
            'controller::Input KeyboardMouseDevice::InputDevice::makeInput(Qt::Key'])
        device=(ROOT/'libraries/controllers/src/controllers/InputDevice.cpp').read_text()
        functions+='\n'+method(device,'float InputDevice::getButton(').replace('float InputDevice::','float controller::InputDevice::')
        raw=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();test=method(raw,'QVariantMap TestScriptingInterface::phoneLifecycleWorldInput(')
        seams='''
class TestScriptingInterface:public QObject {public:QVariantMap phoneLifecycleWorldInput(const QVariantMap& command);
struct Lifecycle {QVariantMap snapshot(){return {{"explicit-host-seam",true}};}};
QString _testResultsLocation{"explicit-host-only"},_featureObservationInstance{QString(32,'f')};
std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
std::shared_ptr<overte::e2e::PhoneLifecycleWorldInput> _phoneLifecycleWorldInput;quint64 _phoneLifecycleWorldInputSequence{0};};
#undef qApp
#define qApp (static_cast<HostApplication*>(QCoreApplication::instance()))
'''+test
        cpp=cls.stage/'actual.cpp';cpp.write_text((ROOT/'android/phone/tests/device/lifecycle-world-runtime.cpp').read_text().replace('// ORIGINAL_KEYBOARD_METHODS',functions).replace('// ORIGINAL_TEST_BINDING',seams))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Gui','Qt6Core','Qt6Test'],text=True));cls.binary=cls.stage/'check'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),str(cpp),'-o',str(cls.binary),*flags],check=True,timeout=30)
    def case(self,mode):
        value=subprocess.run([str(self.binary),mode,'--testScript'],capture_output=True,text=True,timeout=15,
            env=os.environ|{'QT_QPA_PLATFORM':'offscreen','XDG_CONFIG_HOME':str(self.stage/'config')})
        self.assertEqual(0,value.returncode,value.stdout+value.stderr)
        for line in value.stdout.splitlines():
            frame=json.loads(line);request=dict(schemaVersion=1,commandId=frame['requestId'],action='phone-lifecycle-world-input',operation='observe',runId='a'*32,gestureId='')
            validate(frame,request,frame['processId'],frame['capturedEpochMs'])
    def test_original_native_press_mapping_readback_and_one_release(self):self.case('normal')
    def test_real_receiver_swallow_records_attempt_without_effective_keyboard_input(self):self.case('swallowed')
    def test_inactive_or_preexisting_foreign_key_cannot_acquire(self):self.case('inactive');self.case('preexisting')
    def test_foreign_release_or_late_foreign_key_cannot_borrow_owned_event(self):self.case('foreign-release');self.case('foreign-key')
    def test_actual_ten_second_native_watchdog_releases_without_extending_lease(self):self.case('expiry')

if __name__=='__main__':unittest.main()
