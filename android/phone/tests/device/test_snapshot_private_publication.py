"""Actual saveObject writes, permissions and alias refusal on a private host FS.

Only the unrelated GPU receipt service is an explicit unavailable seam. The
production saveObject body and Qt file operations run unchanged; no device or
complete TestScriptingInterface translation-unit build is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
PROBE=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
PRIVATE_NAMES=sorted(set(re.findall(r'Test\.saveObject\s*\([^;]*?,\s*"((?:phone-|feature-)[^"\n]+\.json)"\s*\)',PROBE)) | {'overte-probe.json'})
PREFIX=r'''
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTemporaryDir>
#include <QVariant>
#include <sys/stat.h>
#include <unistd.h>
#include "tests/device/native/PrivatePreviewFiles.h"
struct UnavailableGpuReceipt { QByteArray receiptDigest(const QString&,const QString&,bool) { return {}; } };
struct UnavailableGpuContext { UnavailableGpuReceipt* featureWorldRender() { return nullptr; } };
struct ApplicationSeam { UnavailableGpuContext* getGPUContext() { return nullptr; } };
#undef qApp
ApplicationSeam applicationSeam;
#define qApp (&applicationSeam)
class TestScriptingInterface {
public:QString _testResultsLocation;
    void saveObject(QVariant variant,const QString& filename);
};
'''
SUFFIX=r'''
static QByteArray read(const QString& path) { QFile f(path);return f.open(QIODevice::ReadOnly) ? f.readAll() : QByteArray(); }
static bool write(const QString& path,const QByteArray& raw) { QFile f(path);return f.open(QIODevice::WriteOnly) && f.write(raw)==raw.size(); }
static ino_t inode(const QString& path) { struct stat s{};return ::lstat(QFile::encodeName(path).constData(),&s)==0 ? s.st_ino : 0; }
static mode_t mode(const QString& path) { struct stat s{};return ::lstat(QFile::encodeName(path).constData(),&s)==0 ? s.st_mode&0777 : 0; }
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir temporary;if(!temporary.isValid())return 1;
    TestScriptingInterface test;test._testResultsLocation=temporary.path();
    const QString selected=QString::fromLocal8Bit(argv[1]);
    const QStringList names=selected=="ordinary" ? QStringList{
        "ios-primary-observation.json","pico-collaboration-observation.json","client-command-result.json",
        "voice-result.json","e2e-collaboration-observation.json","unrelated-ordinary.json"
    } : QStringList{PRIVATE_PRODUCER_NAMES};
    const QVariantMap packet{{"actualPrivateOriginal","private-path/uri"},{"sequence",1}};
    const auto raw=QJsonDocument::fromVariant(packet).toJson();
    ::umask(0022);
    for(const auto& name:names) {
        const auto path=QDir(temporary.path()).filePath(name);
        const auto foreign=path+".foreign";
        if(selected=="gate") {
            test.saveObject(packet,name);if(QFileInfo::exists(path))return 2;
        } else if(selected=="aliases") {
            if(!write(foreign,"FOREIGN") || !QFile::link(foreign,path))return 3;
            test.saveObject(packet,name);
            if(read(foreign)!="FOREIGN" || !QFileInfo(path).isSymLink())return 4;
            if(!QFile::remove(path) || !QFile::remove(foreign) || !QFile::link(foreign,path))return 5;
            test.saveObject(packet,name);
            if(QFileInfo::exists(foreign) || !QFileInfo(path).isSymLink())return 6;
        } else if(selected=="atomic-private") {
            test.saveObject(packet,name);if(read(path)!=raw || mode(path)!=0600)return 7;
            const auto initial=inode(path);if(!initial || ::link(QFile::encodeName(path).constData(),QFile::encodeName(foreign).constData())!=0)return 8;
            const QVariantMap next{{"actualPrivateOriginal","different-original"},{"sequence",2}};
            test.saveObject(next,name);
            if(inode(path)==initial || inode(foreign)!=initial || read(foreign)!=raw || mode(path)!=0600
                || read(path)!=QJsonDocument::fromVariant(next).toJson())return 9;
        } else if(selected=="publication-failure") {
            if(!write(path,"PRESERVED"))return 10;
            const auto initial=inode(path);
            if(::chmod(QFile::encodeName(temporary.path()).constData(),0500)!=0)return 11;
            test.saveObject(packet,name);
            const bool unchanged=inode(path)==initial && read(path)=="PRESERVED";
            if(::chmod(QFile::encodeName(temporary.path()).constData(),0700)!=0 || !unchanged)return 12;
        } else if(selected=="ordinary") {
            // The non-instrumented product path remains the existing generic
            // writer, including ordinary filenames in an E2E-capable binary.
            test.saveObject(packet,name);if(read(path)!=raw)return 13;
        } else if(selected=="disabled-build") {
            test.saveObject(packet,name);if(read(path)!=raw)return 14;
        } else return 15;
    }
    return 0;
}
'''


class SnapshotPrivatePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-private-publication';parent.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix='qt6-',dir=parent);cls.addClassCleanup(temp.cleanup);stage=Path(temp.name)
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=source.index('void TestScriptingInterface::saveObject(');end=source.index('\n}',start)+2
        assert len(PRIVATE_NAMES)>=50 and 'phone-snapshot-observation.json' in PRIVATE_NAMES
        names=','.join(json.dumps(name) for name in PRIVATE_NAMES)
        cpp=stage/'actual.cpp';cpp.write_text(PREFIX+source[start:end]+SUFFIX.replace('PRIVATE_PRODUCER_NAMES',names))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
        cls.binaries={}
        for enabled in (True,False):
            binary=stage/('e2e' if enabled else 'ordinary');cls.binaries[enabled]=binary
            subprocess.run(['c++','-std=c++17','-fPIC',*(['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE'] if enabled else []),
                '-I'+str(ROOT),str(cpp),'-o',str(binary),*flags],check=True,timeout=60)
    def case(self,mode,*,enabled=True,test_script=True):
        subprocess.run([str(self.binaries[enabled]),mode,*(['--testScript'] if test_script else [])],check=True,timeout=10)
    def test_all_actual_private_phone_and_shared_feature_producers_publish_atomically(self):self.case('atomic-private')
    def test_live_and_dangling_symlinks_cannot_publish_or_modify_foreign_files(self):self.case('aliases')
    def test_missing_testscript_gate_cannot_create_private_originals(self):self.case('gate',test_script=False)
    def test_failed_atomic_publication_preserves_the_previous_original(self):self.case('publication-failure')
    def test_uninstrumented_build_retains_the_ordinary_writer(self):self.case('disabled-build',enabled=False,test_script=False)
    def test_other_names_keep_the_existing_ordinary_writer(self):self.case('ordinary',test_script=False)


if __name__=='__main__':unittest.main()
