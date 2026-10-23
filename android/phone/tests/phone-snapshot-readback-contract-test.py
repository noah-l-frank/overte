#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile original readback grammar and typed main-thread provider forwarding.

Real Qt metatypes/JSON/clocks and original core command function. Only the raw
JNI backend and lifecycle are seams; no Android/JVM or product effect is proved.
The consumer is separately linked with --no-undefined and has no module class.
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
end=source.index('\nQVariantMap TestScriptingInterface::phoneSnapshotCancel(',start)
original=source[start:end]
(build/'original-function.sha256').write_text(hashlib.sha256(original.encode()).hexdigest()+'\n')
common=r'''
#pragma once
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QThread>
#include <QDateTime>
#include <QObject>
#include <QVariantMap>
#include <memory>
#include <thread>
#include "tests/device/native/PhoneSnapshotNativeBridge.h"
struct SyntheticLifecycle { QVariantMap snapshot() const {return {{"available",true}};} };
class TestScriptingInterface : public QObject {
public:
    QString _testResultsLocation{"private-synthetic-test-root"},_featureObservationInstance{QString(32,'f')};
    std::shared_ptr<SyntheticLifecycle> _featureLifecycle{std::make_shared<SyntheticLifecycle>()};
    quint64 _phoneSnapshotReadbackSequence{0};
    QVariantMap phoneSnapshotReadback(const QVariantMap& command);
};
QString consumerExport();
QString consumerRawReadback(const QString& command);
'''
(build/'common.h').write_text(common)
consumer=build/'consumer.cpp'
consumer.write_text('#include "common.h"\n'+original+'''
QString consumerExport() { return overte::e2e::phoneSnapshotExportObservation(); }
QString consumerRawReadback(const QString& command) { return overte::e2e::phoneSnapshotReadbackCommand(command); }
''')
harness=r'''
#include "common.h"
struct ForeignSnapshotProvider {
    std::function<QString()> exportObservation;
    std::function<QString(const QString&)> readbackCommand;
};
Q_DECLARE_METATYPE(ForeignSnapshotProvider)
struct Backend {
    static int calls,exports;
    static QJsonObject last;
    static QString lastRaw,exportRaw,replyRaw;
};
int Backend::calls=0;int Backend::exports=0;
QJsonObject Backend::last;
QString Backend::lastRaw,Backend::exportRaw,Backend::replyRaw;
'''+r'''

int main(int argc,char** argv) {
    if(!consumerExport().isEmpty() || !consumerRawReadback("before-app").isEmpty())return 20;
    QCoreApplication app(argc,argv);TestScriptingInterface owner;
    overte::e2e::PhoneSnapshotNativeProvider provider{
        [] { ++Backend::exports;return Backend::exportRaw; },
        [](const QString& raw) { ++Backend::calls;Backend::lastRaw=raw;
            Backend::last=QJsonDocument::fromJson(raw.toUtf8()).object();return Backend::replyRaw; }};
    const auto key=overte::e2e::phoneSnapshotNativeProviderProperty();
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","phone-snapshot-readback"},
        {"runId",QString(32,'b')},{"operation","read"},{"exportRequest",QString(32,'c')},{"resourceId",QString(32,'d')}};
    if(!app.arguments().contains("--testScript")) {
        app.setProperty(key,QVariant::fromValue(provider));
        return owner.phoneSnapshotReadback(command).isEmpty() && consumerExport().isEmpty()
            && consumerRawReadback("disabled").isEmpty() && !Backend::calls && !Backend::exports ? 0 : 1;
    }
    const auto unavailable=[&] {
        const int calls=Backend::calls,exports=Backend::exports;
        const auto sequence=owner._phoneSnapshotReadbackSequence;
        return consumerExport().isEmpty() && consumerRawReadback("no-provider").isEmpty()
            && owner.phoneSnapshotReadback(command).isEmpty() && Backend::calls==calls && Backend::exports==exports
            && owner._phoneSnapshotReadbackSequence==sequence;
    };
    if(!unavailable())return 21;
    ForeignSnapshotProvider foreignProvider{provider.exportObservation,provider.readbackCommand};
    app.setProperty(key,QVariant::fromValue(foreignProvider));if(!unavailable())return 22;
    app.setProperty(key,QVariant::fromValue(overte::e2e::PhoneSnapshotNativeProvider{provider.exportObservation,{}}));
    if(!unavailable())return 23;
    app.setProperty(key,QVariant::fromValue(overte::e2e::PhoneSnapshotNativeProvider{{},provider.readbackCommand}));
    if(!unavailable())return 24;
    app.setProperty(key,QVariant::fromValue(provider));
    Backend::exportRaw=QString::fromUtf8("  {\"originalEpochMs\":71,\"note\":\"Ω\"}\n");
    if(consumerExport()!=Backend::exportRaw || Backend::exports!=1)return 25;
    QString opaque=QString::fromUtf8("raw Ω\n");opaque.append(QChar(0xd800));opaque.append(QChar(0));
    Backend::replyRaw=opaque;
    if(consumerRawReadback(opaque)!=opaque || Backend::lastRaw!=opaque || Backend::calls!=1)return 26;
    const int calls=Backend::calls,exports=Backend::exports;bool threadRejected=false;
    std::thread worker([&] { threadRejected=consumerExport().isEmpty() && consumerRawReadback(opaque).isEmpty(); });
    worker.join();if(!threadRejected || Backend::calls!=calls || Backend::exports!=exports)return 27;
    for(const auto& raw:QStringList{QString(),QStringLiteral("invalid original JSON")}) {
        Backend::replyRaw=raw;const auto sequence=owner._phoneSnapshotReadbackSequence;
        if(!owner.phoneSnapshotReadback(command).isEmpty() || owner._phoneSnapshotReadbackSequence!=sequence)return 28;
    }
    Backend::replyRaw="{\"accepted\":true}"; // ACK only, as in the original grammar seam.
    auto reject=[&](const QVariantMap& value) {const int before=Backend::calls;return owner.phoneSnapshotReadback(value).isEmpty() && Backend::calls==before;};
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
    if(Backend::last!=QJsonObject{{"snapshotReadbackCommandVersion",1},{"action","read"},{"request",QString(32,'c')},{"id",QString(32,'d')}})return 10;
    for(const auto& operation:QStringList{"observe","retire-copies","cancel","remove-copy","inspect-destinations","inspect-shares"}) {
        auto value=command;value["operation"]=operation;value["exportRequest"]="";
        value["resourceId"]=(operation=="observe" || operation=="retire-copies") ? QString() : QString(32,'d');
        if(owner.phoneSnapshotReadback(value).isEmpty())return 11;
    }
    for(const auto& operation:QStringList{"remove-destination","revoke-share"}) {
        auto value=command;value["operation"]=operation;
        if(owner.phoneSnapshotReadback(value).isEmpty())return 12;
        value["exportRequest"]="";if(!reject(value))return 13;
    }
    app.setProperty(key,QVariant());
    if(!unavailable())return 29;
    return 0;
}
'''
cpp=build/'main.cpp';cpp.write_text(harness);binary=build/'check';library=build/'libsnapshot-core-consumer.so'
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
base=['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),'-I'+str(build)]
subprocess.run([*base,'-shared','-Wl,--no-undefined',str(consumer),'-o',str(library),*flags],check=True,timeout=60)
subprocess.run([*base,str(cpp),'-L'+str(build),'-lsnapshot-core-consumer','-Wl,-rpath,'+str(build),'-o',str(binary),*flags],check=True,timeout=60)
subprocess.run([str(binary)],check=True,timeout=10)
subprocess.run([str(binary),'--testScript'],check=True,timeout=10)
print('Original Snapshot grammar, raw typed provider/thread checks and separate --no-undefined consumer link passed.')
