#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile the original readback command grammar with explicit JNI/lifecycle seams.

Actual Qt JSON, QObject/thread dispatch and command function; synthetic backend
only returns an acknowledgement. This is not a full TestScriptingInterface TU.
"""
import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
parent=ROOT/'build';parent.mkdir(exist_ok=True)
build=Path(tempfile.mkdtemp(prefix='snapshot-readback-grammar-',dir=parent))
source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
start=source.index('QVariantMap TestScriptingInterface::phoneSnapshotReadback(')
end=source.index('\nQVariantMap TestScriptingInterface::phoneCreateFiles(',start)
original=source[start:end]
(build/'original-function.sha256').write_text(hashlib.sha256(original.encode()).hexdigest()+'\n')
harness=r'''
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QThread>
#include <QDateTime>
#include <QObject>
#include <QVariantMap>
#include <memory>
struct SyntheticLifecycle { QVariantMap snapshot() const {return {{"available",true}};} };
struct NativeSnapshotAdapter {
    static int calls;static QJsonObject last;
    static QString featureReadbackCommand(const QString& raw) {
        ++calls;last=QJsonDocument::fromJson(raw.toUtf8()).object();
        return "{\"accepted\":true}"; // ACK only; no file/product facts.
    }
};
int NativeSnapshotAdapter::calls=0;QJsonObject NativeSnapshotAdapter::last;
class TestScriptingInterface : public QObject {
public:
    QString _testResultsLocation{"private-synthetic-test-root"},_featureObservationInstance{QString(32,'f')};
    std::shared_ptr<SyntheticLifecycle> _featureLifecycle{std::make_shared<SyntheticLifecycle>()};
    quint64 _phoneSnapshotReadbackSequence{0};
    QVariantMap phoneSnapshotReadback(const QVariantMap& command);
};
'''+original+r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);TestScriptingInterface owner;
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","phone-snapshot-readback"},
        {"runId",QString(32,'b')},{"operation","read"},{"exportRequest",QString(32,'c')},{"resourceId",QString(32,'d')}};
    if(!app.arguments().contains("--testScript"))return owner.phoneSnapshotReadback(command).isEmpty() && !NativeSnapshotAdapter::calls ? 0 : 1;
    auto reject=[&](const QVariantMap& value) {const int before=NativeSnapshotAdapter::calls;return owner.phoneSnapshotReadback(value).isEmpty() && NativeSnapshotAdapter::calls==before;};
    for(const auto& key:QStringList{"uri","path","sha256","expected","saved"}) {auto foreign=command;foreign.insert(key,"foreign");if(!reject(foreign))return 2;}
    for(const auto& key:command.keys()) {auto missing=command;missing.remove(key);if(!reject(missing))return 3;}
    for(const auto& key:QStringList{"commandId","runId","exportRequest","resourceId"}) {auto foreign=command;foreign[key]="invalid";if(!reject(foreign))return 4;}
    for(const auto& operation:QStringList{"capture","set-result","delete-destination"}) {auto foreign=command;foreign["operation"]=operation;if(!reject(foreign))return 5;}
    auto foreign=command;foreign["schemaVersion"]=true;if(!reject(foreign))return 6;
    foreign=command;foreign["operation"]=1;if(!reject(foreign))return 7;
    owner._testResultsLocation.clear();if(!reject(command))return 8;owner._testResultsLocation="owned";
    const auto result=owner.phoneSnapshotReadback(command);
    if(result.value("requestId")!=command.value("commandId") || result.value("processId").toLongLong()!=QCoreApplication::applicationPid()
        || result.value("sequence")!=1 || result.value("source").toMap()!=QVariantMap{{"accepted",true}})return 9;
    if(NativeSnapshotAdapter::last!=QJsonObject{{"snapshotReadbackCommandVersion",1},{"action","read"},{"request",QString(32,'c')},{"id",QString(32,'d')}})return 10;
    for(const auto& operation:QStringList{"observe","retire-copies","cancel","remove-copy"}) {
        auto value=command;value["operation"]=operation;value["exportRequest"]="";
        value["resourceId"]=(operation=="observe" || operation=="retire-copies") ? QString() : QString(32,'d');
        if(owner.phoneSnapshotReadback(value).isEmpty())return 11;
    }
    return 0;
}
'''
cpp=build/'main.cpp';cpp.write_text(harness);binary=build/'check'
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
subprocess.run(['c++','-std=c++17','-fPIC',str(cpp),'-o',str(binary),*flags],check=True,timeout=60)
subprocess.run([str(binary)],check=True,timeout=10)
subprocess.run([str(binary),'--testScript'],check=True,timeout=10)
print('Original Snapshot readback command grammar compiled and closed-input counterexamples passed.')
