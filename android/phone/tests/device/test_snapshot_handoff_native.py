"""Actual bounded Qt timer and exact Test gateway; original getters are host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]

PREFIX=r'''
#include <QCoreApplication>
#include <QSharedPointer>
#include <QTemporaryDir>
#include <QFile>
#include <QSaveFile>
#include <QJsonDocument>
#include <QTest>
#include <iostream>
#include "tests/device/native/PhoneSnapshotHandoff.h"
struct LifecycleSeam { QJsonObject snapshot() { return {{"explicitHostLifecycle",true}}; } };
class AccountManager:public QObject { public: QVariantMap featureAccountObservation() { return {{"explicitHostAccountSeam",true}}; } };
struct DependencyManager { template<typename T> static QSharedPointer<T> get() { static QSharedPointer<T> value(new T);return value; } };
class TestScriptingInterface:public QObject {
public:
    QVariantMap phoneSnapshotHandoff(const QVariantMap& command);
    QVariantMap featureScriptRoots(const QVariantMap&) { return original(); }
    QVariantMap featureScriptObservation(const QString&) { return original(); }
    QVariantMap phoneSnapshotObservation(const QVariantMap&) { return original(); }
    QVariantMap phoneSnapshotReadback(const QVariantMap&) { return original(); }
    QVariantMap phoneSnapshotCaptureFiles(const QVariantMap&) { return original(); }
    QVariantMap phoneSnapshotUploadObservation(const QVariantMap&) { return original(); }
    QVariantMap original() { return missing ? QVariantMap{} : QVariantMap{{"explicitOriginalGetterSeam",++samples},{"epoch",QDateTime::currentMSecsSinceEpoch()}}; }
    void saveObject(const QVariant& value,const QString& name) {
        QSaveFile file(_testResultsLocation+"/"+name);file.setDirectWriteFallback(false);
        const auto bytes=QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
        if(!file.open(QIODevice::WriteOnly) || !file.setPermissions(QFile::ReadOwner|QFile::WriteOwner)
            || file.write(bytes)!=bytes.size() || !file.commit()) { throw std::runtime_error("Actual private source publication failed"); }
    }
    QString _testResultsLocation,_featureObservationInstance{32,'e'};
    LifecycleSeam lifecycle;LifecycleSeam* _featureLifecycle{&lifecycle};bool missing{false};int samples{0};
    quint64 _phoneSnapshotHandoffSequence{0};
    QMap<QString,std::shared_ptr<overte::e2e::PhoneSnapshotHandoff>> _phoneSnapshotHandoffs;
};
'''
SUFFIX=r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir root;if(!root.isValid())return 1;
    const QString mode=QString::fromLocal8Bit(argv[1]);TestScriptingInterface test;test._testResultsLocation=root.path();
    const auto query=[&](QString operation,QString run=QString(32,'a'),QString id=QString(32,'b')) {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"action","phone-snapshot-handoff"},{"runId",run},{"handoffId",id},{"operation",operation}};
    };
    if(mode=="disabled")return test.phoneSnapshotHandoff(query("start")).isEmpty() && test.samples==0 ? 0 : 2;
    if(mode=="missing") {
        test.missing=true;
        if(!test.phoneSnapshotHandoff(query("start")).isEmpty())return 3;
        auto owner=test._phoneSnapshotHandoffs.value(QString(32,'b'));
        if(!owner || owner->observation().value("complete").toBool() || owner->summary().value("timerActive").toBool())return 4;
        if(test.phoneSnapshotHandoff(query("retire")).isEmpty() || !owner->retired() || owner->observation().value("complete").toBool())return 5;
        return 0;
    }
    auto invalid=query("start");invalid.insert("desiredState",true);
    if(!test.phoneSnapshotHandoff(invalid).isEmpty() || !test._phoneSnapshotHandoffs.isEmpty())return 6;
    const auto first=test.phoneSnapshotHandoff(query("start"));if(first.isEmpty())return 7;
    auto owner=test._phoneSnapshotHandoffs.value(QString(32,'b'));if(!owner)return 8;
    const auto initial=owner->observation();if(!initial.value("complete").toBool() || !initial.value("timerActive").toBool()
        || initial.value("retired").toBool() || initial.value("readActive").toBool() || initial.value("sequence").toInt()!=1)return 9;
    if(!test.phoneSnapshotHandoff(query("start",QString(32,'c'))).isEmpty()
        || !test.phoneSnapshotHandoff(query("start",QString(32,'a'),QString(32,'c'))).isEmpty())return 10;
    QTest::qWait(320);
    const auto observed=owner->observation();if(observed.value("sequence").toInt()<=1 || test.samples<14)return 11;
    QFile file(root.path()+"/phone-snapshot-handoff.json");if(!file.open(QIODevice::ReadOnly))return 12;
    const auto published=QJsonDocument::fromJson(file.readAll()).object();file.close();
    if(published.value("source").toObject().value("sequence").toInt()!=observed.value("sequence").toInt())return 13;
    if(mode=="expiry") {
        QTest::qWait(60200);
        const auto expired=owner->observation();if(expired.value("complete").toBool() || expired.value("error")!="lease-expired"
            || expired.value("timerActive").toBool() || expired.value("retired").toBool())return 14;
    }
    const auto retired=test.phoneSnapshotHandoff(query("retire"));if(retired.isEmpty() || !owner->retired())return 15;
    const auto last=owner->observation();const auto count=test.samples;QTest::qWait(320);
    if(test.samples!=count || owner->observation()!=last || !test.phoneSnapshotHandoff(query("start")).isEmpty())return 16;
    if(mode!="expiry" && !last.value("complete").toBool())return 17;
    if(test.phoneSnapshotHandoff(query("retire")).isEmpty() || !owner->retired())return 18;
    std::cout<<"PASS: actual Qt original-read timer, atomic source, owner/command grammar, stop/no revival; explicit native getter seams\n";
    return 0;
}
'''


class SnapshotHandoffNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-handoff-native';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='qt-',dir=parent);cls.addClassCleanup(temporary.cleanup)
        stage=Path(temporary.name);cls.binary=stage/'handoff'
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=source.index('QVariantMap TestScriptingInterface::phoneSnapshotHandoff(')
        method=source[start:source.index('\n}',start)+2]
        cpp=stage/'actual.cpp';cpp.write_text(PREFIX+method+SUFFIX)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Test'],text=True))
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-I'+str(ROOT),str(cpp),'-o',str(cls.binary),*flags],check=True,timeout=60)
    def case(self,mode,enabled=True):
        subprocess.run([str(self.binary),mode,*(['--testScript'] if enabled else [])],check=True,timeout=65)
    def test_actual_native_timer_acquisition_original_private_file_and_strict_retirement(self):self.case('normal')
    def test_missing_original_getter_is_unavailable_and_does_not_become_green_on_retirement(self):self.case('missing')
    def test_default_off_source_cannot_start_or_read_any_original_getter(self):self.case('disabled',False)
    def test_actual_sixty_second_qt_deadline_stops_without_refresh_or_revival(self):self.case('expiry')


if __name__=='__main__':unittest.main()
