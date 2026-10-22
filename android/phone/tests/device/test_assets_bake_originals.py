"""Compile real BakeAssetTask with actual QProcess and a synthetic oven executable.

The explicit PathUtils/AssetUtils/oven endpoints provide no real baked product
output. This proves passive original threading/file transport only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device')]
from fixture.assets_originals import original

CPP=r'''
#include <QCoreApplication>
#include <QEventLoop>
#include <QThreadPool>
#include <QTimer>
#include <QJsonDocument>
#include <iostream>
#include "tests/device/native/AssetsBakeOriginals.h"
#include "BakeAssetTask.h"
static const QString id="12345678-1234-4234-8234-123456789abc",hash=QString(64,'a');
int main(int argc,char**argv){QCoreApplication app(argc,argv);auto source=std::make_shared<overte::e2e::AssetsBakeOriginals>();
 if(!source->enabled())return 1;auto task=std::make_shared<BakeAssetTask>(hash,"/e2e-"+QString(32,'b')+"/stand.fbx",argv[1]);task->setAutoDelete(false);
 const auto instance=source->begin(hash,"/e2e-"+QString(32,'b')+"/stand.fbx",7);
 task->e2eOriginalEvent=[source,instance](const QString&kind,qint64 pid,int code,int status){source->event(instance,kind,pid,code,status);};
 QObject::connect(task.get(),&QObject::destroyed,[source,instance]{source->event(instance,"destroyed");});
 bool complete=false,failed=false;QEventLoop loop;
 QObject::connect(task.get(),&BakeAssetTask::bakeComplete,&app,[&](QString,QString,QString){source->event(instance,"complete");complete=true;loop.quit();});
 QObject::connect(task.get(),&BakeAssetTask::bakeFailed,&app,[&](QString,QString,QString){source->event(instance,"failed");failed=true;loop.quit();});
 QTimer::singleShot(2000,&loop,&QEventLoop::quit);QThreadPool pool;pool.start(task.get());loop.exec();pool.waitForDone();
 if(!complete||failed)return 2;task.reset();source->publish(id,id,{}, {},0);return 0;}
'''

class AssetsBakeNativeTests(unittest.TestCase):
    def test_actual_worker_qprocess_receipts_and_exclusive_private_transport(self):
        base=ROOT/'build/assets-native-contract';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='bake-',dir=base) as tmp:
            root=Path(tmp);seam=root/'seam';seam.mkdir();out=root/'originals';out.mkdir(mode=0o700);work=root/'work';work.mkdir()
            (seam/'AssetUtils.h').write_text('#pragma once\n#include <QString>\nnamespace AssetUtils{using AssetHash=QString;using AssetPath=QString;}\n')
            (seam/'PathUtils.h').write_text('#pragma once\n#include <QString>\nnamespace PathUtils{inline QString generateTemporaryDir(){return qEnvironmentVariable("E2E_TEST_WORK");}inline bool deleteMyTemporaryDir(const QString&){return true;}}\n')
            cpp=root/'check.cpp';cpp.write_text(CPP);moc=root/'moc.cpp'
            env=os.environ|dict(OVERTE_E2E_ASSETS_ORIGINALS=str(out.resolve()),E2E_TEST_WORK=str(work.resolve()))
            (root/'oven').write_text('#!/bin/sh\nexit 0\n');(root/'oven').chmod(0o700)
            body=root/'input.fbx';body.write_bytes(b'explicit synthetic oven input')
            flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
            subprocess.run(['/usr/lib64/qt6/libexec/moc','-DOVERTE_E2E_FEATURE_TESTS',str(ROOT/'assignment-client/src/assets/BakeAssetTask.h'),'-o',str(moc)],check=True,capture_output=True,text=True)
            run=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),'-I'+str(seam),'-I'+str(ROOT/'assignment-client/src/assets'),str(cpp),str(moc),str(ROOT/'assignment-client/src/assets/BakeAssetTask.cpp'),'-o',str(root/'check'),*flags],capture_output=True,text=True)
            self.assertEqual(0,run.returncode,run.stderr)
            run=subprocess.run([str(root/'check'),str(body.resolve())],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(0,run.returncode,run.stderr)
            value=original(json.loads((out/'assets-bakes.json').read_text()));job=value['jobs'][0]
            self.assertEqual('complete',job['outcome']);self.assertGreater(job['ovenProcessId'],0);self.assertIsNotNone(job['destroyedEpochMs']);self.assertIsNotNone(job['runExitedEpochMs'])
            self.assertEqual(0,value['pending']);self.assertEqual(0o600,(out/'assets-bakes.json').stat().st_mode&0o777)
            # A second native lifetime cannot adopt or truncate the first file.
            before=(out/'assets-bakes.json').read_bytes()
            again=subprocess.run([str(root/'check'),str(body.resolve())],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(1,again.returncode);self.assertEqual(before,(out/'assets-bakes.json').read_bytes())

    def test_actual_server_snapshot_reads_current_files_and_requires_owner_thread(self):
        base=ROOT/'build/assets-native-contract';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='bake-server-',dir=base) as tmp:
            root=Path(tmp);out=root/'originals';out.mkdir(mode=0o700);files=root/'files';files.mkdir()
            import hashlib
            data=b'actual stored server bytes';sha=hashlib.sha256(data).hexdigest();(files/sha).write_bytes(data)
            method=(ROOT/'assignment-client/src/assets/AssetServer.cpp').read_text().split('void AssetServer::e2ePublishBakeOriginals() {',1)[1].rsplit('\n#endif',1)[0]
            code=r'''#include <QCoreApplication>
#include <QDir>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QThread>
#include <memory>
#include <map>
#include "tests/device/native/AssetsBakeOriginals.h"
static const QUuid id("12345678-1234-4234-8234-123456789abc");
struct Domain{QUuid getUUID(){return id;}};
struct NodeList{Domain domain;Domain&getDomainHandler(){return domain;}QUuid getSessionUUID(){return id;}};
struct DependencyManager{template<typename T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}};
class AssetServer:public QObject{public:
 std::shared_ptr<overte::e2e::AssetsBakeOriginals>_e2eBakeOriginals=std::make_shared<overte::e2e::AssetsBakeOriginals>();
 std::map<QString,QString>_fileMappings;QDir _filesDirectory;QMap<QString,int>_pendingBakes;void e2ePublishBakeOriginals();};
void AssetServer::e2ePublishBakeOriginals(){METHOD
int main(int argc,char**argv){QCoreApplication app(argc,argv);AssetServer server;server._filesDirectory=QDir(argv[1]);server._fileMappings["/actual/original.fbx"]=argv[2];server.e2ePublishBakeOriginals();}
'''.replace('METHOD',method)
            cpp=root/'check.cpp';cpp.write_text(code);flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
            result=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),str(cpp),'-o',str(root/'check'),*flags],capture_output=True,text=True)
            self.assertEqual(0,result.returncode,result.stderr)
            result=subprocess.run([str(root/'check'),str(files.resolve()),sha],env=os.environ|dict(OVERTE_E2E_ASSETS_ORIGINALS=str(out.resolve())),capture_output=True,text=True,timeout=5)
            self.assertEqual(0,result.returncode,result.stderr);packet=original(json.loads((out/'assets-bakes.json').read_text()))
            self.assertEqual([dict(path='/actual/original.fbx',hash=sha)],packet['mappings']);self.assertEqual([dict(hash=sha,actualSha256=sha,bytes=len(data))],packet['blobs'])

if __name__=='__main__':unittest.main()
