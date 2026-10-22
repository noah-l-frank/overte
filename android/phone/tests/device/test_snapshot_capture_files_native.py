"""Actual original Snapshot save method and passive FD/retirement contract.

Qt image encoding/files/descriptors/hash/unlink are real. Account/address/UI
services and capture callback scheduling are explicit host seams. This is not
an Android build or renderer/phone permission acceptance test.
"""
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
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
import overte_phone_snapshot_capture_source as contract
PREFIX=r'''
#include <QCoreApplication>
#include <QImage>
#include <QUrl>
#include <QRegularExpression>
#include <QTemporaryFile>
#include <QDebug>
#include <QJsonDocument>
#include "interface/src/ui/SnapshotStorage.h"
#include "tests/device/native/PhoneSnapshotCaptureFiles.h"
struct AddressManager { QUrl currentPublicAddress(){return QUrl("https://controlled.invalid/source-only");} };
struct AccountInfo { QString getUsername(){return "synthetic-host-user";} };
struct AccountManager { AccountInfo getAccountInfo(){return {};} };
struct DependencyManager { template<class T>static T* get(){static T value;return &value;} };
struct Reticle { void setVisible(bool){} void setAllowMouseCapture(bool){} };
struct Compositor { Reticle* getReticleInterface(){static Reticle value;return &value;} };
struct FakeApp { Compositor& getApplicationCompositor(){static Compositor value;return value;} };
static FakeApp fakeApp;
#undef qApp
#define qApp (&fakeApp)
struct OffscreenUi { static QString getExistingDirectory(void*,const QString&,const QString&){throw std::runtime_error("Unplanned host UI");} };
struct Location { void set(const QString&){} };
static const QString URL="overte_url",DEFAULT_FORMAT="png",FILENAME_PATH_FORMAT="overte-snap-by-%1-on-%2",DATETIME_FORMAT="yyyy-MM-dd_hh-mm-ss";
static const QList<QString> SUPPORTED_IMAGE_FORMATS={"jpg","jpeg","png","webp"};
class Snapshot {
public:
    QString saveSnapshot(QImage image,const QString& filename,const QString& pathname=QString());
    QFile* savedFileForSnapshot(QImage& image,bool temporary,const QString& filename=QString(),const QString& pathname=QString());
    bool nativeReviewEnabled(){return true;}
    QString getSnapshotsLocation(){return overte::snapshot::storageRoot();}
    QString getSnapshotFormat(){return "png";}
    Location _snapshotsLocation;
};
'''
SUFFIX=r'''
static void need(bool value){if(!value)throw std::runtime_error("Original capture file source contract");}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);QCoreApplication::setApplicationName("actual-capture-files");Snapshot service;
    const QString mode=argv[1],root=overte::snapshot::storageRoot();need(QDir().mkpath(root));
    const QString run(32,'a'),planId(32,'b'),operation(32,'c'),prefix="e2e-"+run,capture="original_native_capture_1",name=prefix+"-"+capture+".png",path=QDir(root).filePath(name);
    QImage image(64,48,QImage::Format_ARGB32);image.fill(Qt::cyan);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    using overte::e2e::PhoneSnapshotCaptureFiles;auto& owner=PhoneSnapshotCaptureFiles::get();
    if(!app.arguments().contains("--testScript")) {
        need(!owner.plan(run,prefix,planId,root));need(!service.saveSnapshot(image,name).isEmpty() && owner.snapshot().isEmpty());return 0;
    }
    if(mode=="foreign") { QFile old(path);need(old.open(QIODevice::WriteOnly));need(old.write("prior-user-capture")==18);old.close();need(!owner.plan(run,prefix,planId,root)); }
    else need(owner.plan(run,prefix,planId,root));
    owner.begin(capture);PhoneSnapshotCaptureFiles::Scope scope(capture);
    if(mode=="partial")image=QImage();
    if(mode=="pending" || mode=="pending-close") {
        const auto ticket=owner.opening(path,root);QFile actual(path);need(actual.open(QIODevice::WriteOnly));owner.opened(ticket,actual.handle());need(actual.write("real partial original")==21);
        need(!owner.retire(run,ticket,operation));
        owner.beforeClose(ticket,actual.handle());
        if(mode=="pending-close") { owner.closed(ticket,actual.isOpen());owner.terminal(capture,"cancelled",{});need(!owner.retire(run,ticket,operation));return 0; }
        actual.close();owner.closed(ticket,actual.isOpen());owner.terminal(capture,"cancelled",{});need(owner.retire(run,ticket,operation));return 0;
    }
    const auto saved=service.saveSnapshot(image,name);need((mode=="partial")==saved.isEmpty());
    owner.terminal(capture,mode=="partial" ? "error" : mode=="cancelled" ? "cancelled" : "complete",mode=="partial" || mode=="cancelled" ? QString() : path);
    auto original=owner.snapshot();auto rows=original.value("rows").toList();need(original.value("complete")==true && rows.size()==1);
    auto row=rows[0].toMap();const auto id=row.value("id").toString();need(row.value("closed")==true && row.value("opened")==true);
    if(mode=="foreign") { need(row.value("preexisting")==true && row.value("planId").toString().isEmpty() && !owner.retire(run,id,operation) && QFileInfo(path).exists());return 0; }
    need(row.value("planId")==planId && row.value("runId")==run && row.value("preexisting")==false);
    if(mode!="partial") {
        QFile actual(path);need(actual.open(QIODevice::ReadOnly));const auto bytes=actual.readAll();actual.close();
        need(row.value("bytes").toLongLong()==bytes.size() && row.value("sha256")==QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()));
    }
    if(mode=="changed-inode") {
        need(QFile::rename(path,path+".old"));QFile replacement(path);need(replacement.open(QIODevice::WriteOnly));QFile old(path+".old");need(old.open(QIODevice::ReadOnly));replacement.write(old.readAll());replacement.close();old.close();
        need(!owner.retire(run,id,operation) && QFileInfo(path).exists());return 0;
    }
    if(mode=="changed-bytes") { QFile changed(path);need(changed.open(QIODevice::ReadWrite));auto one=changed.read(1);need(one.size()==1 && changed.seek(0));one[0]=char(one[0]^1);changed.write(one);changed.close();need(!owner.retire(run,id,operation) && QFileInfo(path).exists());return 0; }
    if(mode=="early-missing") { need(QFile::remove(path));need(!owner.retire(run,id,operation));return 0; }
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'d')},{"action","phone-snapshot-files-observe"},{"runId",run}};quint64 sequence=0;
    for(const auto& key:QStringList{"path","sha256","expected","fileId"}) { auto foreign=command;foreign[key]="foreign";need(overte::e2e::phoneSnapshotCaptureFileObservation(foreign,QString(32,'f'),sequence).isEmpty()); }
    const auto packet=overte::e2e::phoneSnapshotCaptureFileObservation(command,QString(32,'f'),sequence);need(!packet.isEmpty());
    std::cout<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
    need(owner.retire(run,id,operation) && !QFileInfo(path).exists());need(owner.retire(run,id,operation));need(!owner.retire(run,id,QString(32,'e')));
    if(mode=="late-file") { QFile late(path);need(late.open(QIODevice::WriteOnly));late.write("late");late.close();need(!owner.retire(run,id,operation));need(owner.snapshot().value("complete")==false && QFileInfo(path).exists());return 0; }
    need(owner.seal(run,planId,QString(32,'7')));need(owner.seal(run,planId,QString(32,'7')));
    if(mode=="late-namespace") { QFile late(QDir(root).filePath(prefix+"-unknown.png"));need(late.open(QIODevice::WriteOnly));late.write("late");late.close();need(owner.snapshot().value("complete")==false);return 0; }
    if(mode=="new-scope") { need(owner.plan(QString(32,'8'),"e2e-"+QString(32,'8'),QString(32,'9'),root));owner.begin("new_original_capture"); }
    command["commandId"]=QString(32,'e');const auto retired=overte::e2e::phoneSnapshotCaptureFileObservation(command,QString(32,'f'),sequence);
    std::cout<<QJsonDocument::fromVariant(retired).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
#else
    need(!service.saveSnapshot(image,name).isEmpty() && QFileInfo(path).exists());
#endif
    return 0;
}
'''

class SnapshotCaptureFilesNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-capture-files-native';parent.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='cpp-',dir=parent);cls.addClassCleanup(cls.temporary.cleanup);cls.build=Path(cls.temporary.name)
        raw=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
        save=raw[raw.index('QString Snapshot::saveSnapshot('):raw.index('\n\nstatic const float CUBEMAP_SIDE',raw.index('QString Snapshot::saveSnapshot('))]
        original=raw[raw.index('QFile* Snapshot::savedFileForSnapshot('):raw.index('\nvoid Snapshot::uploadSnapshot(',raw.index('QFile* Snapshot::savedFileForSnapshot('))]
        test=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=test.index('QVariantMap TestScriptingInterface::phoneSnapshotCaptureFiles(')
        method=test[start:test.index('\n}',start)+2]
        bridge='''
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QObject>
#include <QThread>
struct LifecycleSourceSeam { QVariantMap snapshot(){return {{"explicit-host-seam",true}};} };
class TestScriptingInterface:public QObject {
public: QVariantMap phoneSnapshotCaptureFiles(const QVariantMap& command);
QString _testResultsLocation{"host-source-only"},_featureObservationInstance{32,'f'};
LifecycleSourceSeam storage;LifecycleSourceSeam* _featureLifecycle{&storage};quint64 _phoneSnapshotCaptureFilesSequence{0};
};
'''+method+'\n#endif\n'
        suffix=SUFFIX.replace('const auto packet=overte::e2e::phoneSnapshotCaptureFileObservation(command,QString(32,\'f\'),sequence);',
            'TestScriptingInterface testBridge;const auto packet=testBridge.phoneSnapshotCaptureFiles(command);')
        cpp=cls.build/'actual.cpp';cpp.write_text('#include <iostream>\n'+PREFIX+save+'\n'+original+bridge+suffix)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui'],text=True));cls.binaries={}
        for profile,defines in [('phone',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PHONE_INTERFACE']),('production',[]),('other-android',['OVERTE_E2E_FEATURE_TESTS'])]:
            binary=cls.build/profile;subprocess.run(['c++','-std=c++17','-fPIC','-I'+str(ROOT),*['-D'+key for key in defines],str(cpp),'-o',str(binary),*flags],check=True,timeout=30);cls.binaries[profile]=binary
    def case(self,mode,profile='phone',enabled=True):
        with tempfile.TemporaryDirectory(prefix='original-',dir=self.build) as data:
            result=subprocess.run([str(self.binaries[profile]),mode,*(['--testScript'] if enabled else [])],capture_output=True,text=True,timeout=10,env=os.environ|{'XDG_DATA_HOME':data})
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            for line in result.stdout.splitlines():
                value=json.loads(line);self.assertTrue(value['source']['complete']);self.assertGreater(value['processId'],0)
                roots={row['path'].rsplit('/',1)[0] for row in value['source']['rows']}
                with patch.object(contract,'ROOTS',roots):contract.source(value['source'],value['capturedEpochMs'])
    def test_actual_qfile_png_bytes_fd_close_and_one_send_retirement(self):self.case('success')
    def test_cancelled_still_and_failed_empty_write_are_retired_without_success_adoption(self):
        self.case('cancelled');self.case('partial')
    def test_actual_pending_write_and_original_close_cannot_retire(self):
        self.case('pending');self.case('pending-close')
    def test_preexisting_foreign_file_is_never_adopted_or_deleted(self):self.case('foreign')
    def test_same_bytes_foreign_inode_and_changed_original_bytes_remain_owned_red(self):
        self.case('changed-inode');self.case('changed-bytes')
    def test_early_unexplained_absence_and_late_file_never_qualify(self):
        self.case('early-missing');self.case('late-file');self.case('late-namespace')
    def test_retired_scope_keeps_original_rows_while_new_scope_reports_a_live_capture(self):self.case('new-scope')
    def test_missing_test_script_and_nonphone_production_profiles_have_no_owner(self):
        self.case('disabled',enabled=False);self.case('production','production');self.case('other-android','other-android')
if __name__=='__main__':unittest.main()
