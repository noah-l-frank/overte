#!/usr/bin/env python3
"""Compile original passive serializer with explicit avatar/physics value seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
glm=[]
if environment.get('OVERTE_HOST_GLM_INCLUDE'):glm=['-I'+str(Path(environment['OVERTE_HOST_GLM_INCLUDE']).resolve(strict=True))]
with tempfile.TemporaryDirectory(prefix='lifecycle-drive-') as directory:
    binary=Path(directory)/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),*glm,
        str(Path(__file__).with_name('lifecycle-drive-observation-test.cpp')),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    for arguments in ([],['--testScript']):subprocess.run([str(binary),*arguments],check=True,timeout=10,env=environment)
    # Execute the original two C++ coordinate transforms, with explicit XR,
    # mapper and avatar boundaries. Their signs must match the actual reviewed
    # controller profile; this is not a physical OpenXR/controller execution.
    import json
    import sys
    sys.path.insert(0,str(ROOT/'tests/device'))
    from openxr_input.controller_protocol import compile_envelope
    profile=json.loads((ROOT/'tests/device/openxr_input/profiles/pico4-overte-controller.json').read_text())
    action=profile['controls']['thumbsticks']['left'];assert action=='left_thumbstick'
    amplitudes=[]
    for direction in ('forward','backward'):
        compiled=compile_envelope(dict(schemaVersion=1,sessionNonce='f'*64,sequence=1,
            commands=[dict(id='original-'+direction,operation='input.move',arguments=dict(direction=direction,durationSeconds=1.5))]),profile)
        amplitudes.append(next(event['state']['vector2f'][action][1] for event in compiled['events']
            if abs(event['state']['vector2f'][action][1])>.01))
    mapping=json.loads((ROOT/'interface/resources/controllers/standard.json').read_text())
    direct=[row for row in mapping['channels'] if row.get('from')=='Standard.LY' and row.get('to')=='Actions.TranslateZ']
    assert len(direct)==1 and direct[0].get('filters') is None
    assert direct[0]['when']==['Application.RightHandDominant','!Application.TabletShown']
    plugin=(ROOT/'plugins/openxr/src/OpenXrInputPlugin.cpp').read_text()
    start=plugin.index('    std::vector<std::tuple<std::string, StandardAxisChannel, StandardAxisChannel>> axesToUpdate = {')
    end=plugin.index('    std::vector<std::pair<std::string, StandardButtonChannel>> buttonsToUpdate = {',start)
    original_axes=plugin[start:end]
    application=(ROOT/'interface/src/Application.cpp').read_text()
    assignment=[line.strip() for line in application.splitlines() if
        'myAvatar->setDriveKey(MyAvatar::TRANSLATE_Z, -1.0f * userInputMapper->getActionState(controller::Action::TRANSLATE_Z));' in line]
    assert len(assignment)==1
    tsi=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    output=tsi.index('void TestScriptingInterface::saveObject(')
    alias=tsi.index('filename == "feature-chat-observation.json"',output)
    guard=tsi.rfind('    if (',output,alias)
    assert guard>output
    prefix=tsi.rfind('#if defined(OVERTE_E2E_FEATURE_TESTS)',output,guard)
    assert prefix>output
    private_prelude=tsi[prefix+len('#if defined(OVERTE_E2E_FEATURE_TESTS)'):guard]
    start=guard+len('    if (');end=tsi.index(') {',start)
    private_condition=tsi[start:end]
    fixture=r'''
#include <QRegularExpression>
#include <QString>
#include <cassert>
#include <map>
#include <memory>
#include <string>
#include <tuple>
#include <vector>
using StandardAxisChannel=int;
constexpr int LX=0,LY=1,RX=2,RY=3,LEFT_TRACKPAD_X=4,LEFT_TRACKPAD_Y=5,RIGHT_TRACKPAD_X=6,RIGHT_TRACKPAD_Y=7;
struct Axis { float value{0}; };
struct State { bool isActive{false};struct { float x{0},y{0}; } currentState; };
struct Action { State state;State getVector2f() const {return state;} };
namespace controller { enum class Action { TRANSLATE_Z }; }
struct MyAvatar { enum DriveKeys {TRANSLATE_Z};float observed{0};void setDriveKey(DriveKeys,float value){observed=value;} };
struct Mapper { float observed{0};float getActionState(controller::Action) const {return observed;} };
// Execute the actual admission statements, including void early returns.
// Filesystem writing, permissions and symlink gates are separate host checks.
bool privateOutput(const QString& filename) {
    bool admitted=false;
    const auto original=[&]() {
        PRIVATE_PRELUDE
        if (PRIVATE_CONDITION) {admitted=true;}
    };
    original();return admitted;
}
void original(float runtimeY) {
    std::map<StandardAxisChannel,Axis> _axisStateMap;
    std::map<std::string,std::shared_ptr<Action>> _actions;
    for (const auto& name:{"left_thumbstick","left_trackpad","right_thumbstick","right_trackpad"})
        _actions[name]=std::make_shared<Action>();
    _actions["left_thumbstick"]->state.isActive=true;
    _actions["left_thumbstick"]->state.currentState.y=runtimeY;
    ORIGINAL_AXES
    Mapper mapper;auto userInputMapper=&mapper;mapper.observed=_axisStateMap[LY].value;
    MyAvatar avatar;auto myAvatar=&avatar;
    ORIGINAL_ASSIGNMENT
    assert(avatar.observed==runtimeY);
    assert((avatar.observed>0)==(runtimeY>0));
}
int main() {
    original(FORWARD);original(BACKWARD);
    assert(privateOutput("feature-lifecycle-drive.json"));
    assert(!privateOutput("../feature-lifecycle-drive.json"));
    assert(!privateOutput("feature-lifecycle-drive.json.extra"));
}
'''.replace('PRIVATE_PRELUDE',private_prelude).replace('PRIVATE_CONDITION',private_condition).replace('ORIGINAL_AXES',original_axes).replace(
        'ORIGINAL_ASSIGNMENT',assignment[0]).replace('FORWARD',repr(amplitudes[0])+'f').replace('BACKWARD',repr(amplitudes[1])+'f')
    route_source=Path(directory)/'original-route.cpp';route_source.write_text(fixture)
    route_binary=Path(directory)/'original-route'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG',str(route_source),'-o',str(route_binary),*library_paths,*flags],
        check=True,timeout=90,env=environment)
    subprocess.run([str(route_binary)],check=True,timeout=10,env=environment)
