"""Compile the actual Test Assets methods/jobs with explicit network endpoints.

Only AssetClient/NodeList endpoints are synthetic. Qt thread delivery, request
lifetimes and the unchanged native source methods/headers execute on this host.
This does not compile an Android client or run an Asset Server.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
STUB=r'''
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QEvent>
#include <QObject>
#include <QThread>
#include <QTimer>
#include <QTemporaryDir>
#include <QUuid>
#include <QVariantMap>
#include <QCryptographicHash>
#include <atomic>
#include <map>
#include <memory>
#include <cassert>
#include "tests/device/native/PhoneAssetsReadJob.h"
#include "tests/device/native/PrivateAssetsFiles.h"
using overte::e2e::PhoneAssetsReadJob;
static std::atomic<int> live{0};
static const QByteArray bytes("actual network-owned asset bytes");
static const QString hash=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
struct MappingInfo {QString hash;int status{4};QString bakingErrors;};
using Mappings=std::map<QString,MappingInfo>;
class MappingRequest:public QObject {Q_OBJECT
public:enum Error{NoError,NetworkError};int error{0};int getError()const{assert(QThread::currentThread()==thread());return error;}};
class GetAllMappingsRequest:public MappingRequest {Q_OBJECT
public:
 GetAllMappingsRequest(){++live;}~GetAllMappingsRequest(){--live;}
 bool blocked{false};Mappings original{{"/actual/main.fbx",{hash,4,{}}},{"/.baked/actual/original",{hash,0,{}}}};
 Mappings getMappings()const{assert(QThread::currentThread()==thread());return original;}
 void start(){if(QThread::currentThread()!=thread()){QMetaObject::invokeMethod(this,[this]{start();},Qt::QueuedConnection);return;}
  if(!blocked)QTimer::singleShot(10,this,[this]{emit finished(this);});}
signals:void finished(GetAllMappingsRequest*);
};
class GetMappingRequest:public MappingRequest {Q_OBJECT
public:
 QString path;bool redirected=false;
 GetMappingRequest(QString path,bool redirect):path(path),redirected(redirect){++live;}~GetMappingRequest(){--live;}
 QString e2eRequestedPath()const{assert(QThread::currentThread()==thread());return path;}
 QString getHash()const{assert(QThread::currentThread()==thread());return hash;}
 bool wasRedirected()const{assert(QThread::currentThread()==thread());return redirected;}
 QString getRedirectedPath()const{assert(QThread::currentThread()==thread());return redirected?"/.baked/"+hash+"/asset.fbx":QString();}
 void start(){if(QThread::currentThread()!=thread()){QMetaObject::invokeMethod(this,[this]{start();},Qt::QueuedConnection);return;}
  QTimer::singleShot(10,this,[this]{emit finished(this);});}
signals:void finished(GetMappingRequest*);
};
class AssetRequest:public QObject {Q_OBJECT
public:
 enum State{NotStarted,WaitingForData,Finished};enum Error{NoError,NetworkError};
 AssetRequest(QString requested):requested(requested){++live;}~AssetRequest(){--live;}
 QString requested;int state{NotStarted},error{0};
 int getError()const{assert(QThread::currentThread()==thread());return error;}
 int getState()const{assert(QThread::currentThread()==thread());return state;}
 QString getHash()const{assert(QThread::currentThread()==thread());return requested;}
 QByteArray getData()const{assert(QThread::currentThread()==thread());return bytes;}
 bool loadedFromCache()const{assert(QThread::currentThread()==thread());return false;}
 void start(){if(QThread::currentThread()!=thread()){QMetaObject::invokeMethod(this,[this]{start();},Qt::QueuedConnection);return;}
  QTimer::singleShot(10,this,[this]{state=Finished;emit finished(this);});}
signals:void finished(AssetRequest*);
};
class AssetClient:public QObject {
public:
 QThread network;bool block{false},fail{false},redirect{false};
 AssetClient(){network.start();}~AssetClient(){network.quit();network.wait();}
 GetAllMappingsRequest*createGetAllMappingsRequest(){auto request=new GetAllMappingsRequest();request->blocked=block;request->error=fail?1:0;request->moveToThread(&network);return request;}
 GetMappingRequest*createGetMappingRequest(const QString&path){auto request=new GetMappingRequest(path,redirect);request->error=fail?1:0;request->moveToThread(&network);return request;}
 AssetRequest*createRequest(const QString&requested){auto request=new AssetRequest(requested);request->moveToThread(&network);return request;}
};
struct Domain {QUuid id=QUuid("12345678-1234-4234-8234-123456789abc");bool connected=true;
 QUuid getUUID()const{return id;}bool isConnected()const{return connected;}};
namespace NodeType {enum Type {AssetServer};}
struct AssetNode {QUuid id=QUuid::createUuid();QUuid getUUID()const{return id;}};
struct NodeList {std::shared_ptr<AssetNode>server=std::make_shared<AssetNode>();std::shared_ptr<AssetNode>soloNodeOfType(NodeType::Type){return server;} Domain domain;bool write=true;Domain&getDomainHandler(){return domain;}QUuid getSessionUUID()const{return domain.id;}bool getThisNodeCanWriteAssets()const{return write;}};
struct DependencyManager {template<typename T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}
 template<typename T>static bool isSet(){return true;}};
struct Lifecycle {QVariantMap snapshot(){return {{"launches",1}};}};
class TestScriptingInterface:public QObject {Q_OBJECT
public:
 QString _testResultsLocation="actual-private-root",_featureObservationInstance=QString(32,'d');
 std::shared_ptr<Lifecycle>_featureLifecycle=std::make_shared<Lifecycle>();
 quint64 _phoneAssetsFilesSequence{0};std::shared_ptr<overte::e2e::PrivateAssetsFiles>_phoneAssetsFiles;
 Q_INVOKABLE QVariantMap phoneAssetsFiles(const QVariantMap& command);
 quint64 _phoneAssetsReadSequence{0};std::shared_ptr<PhoneAssetsReadJob>_phoneAssetsRead;
 Q_INVOKABLE QVariantMap phoneAssetsRead(const QVariantMap& command,bool abort=false);
};
'''
MAIN=r'''
static QVariantMap query(char letter,bool download=false){
 QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,letter)},{"action",download?"phone-assets-download":"phone-assets-observe"},{"runId",QString(32,'a')}};
 if(download)command["hash"]=hash;return command;
}
static QVariantMap finished(TestScriptingInterface&test,const QVariantMap&command){
 QElapsedTimer clock;clock.start();
 while(clock.elapsed()<1200){QCoreApplication::processEvents();auto packet=test.phoneAssetsRead(command);
  if(packet.contains("source"))return packet;QThread::msleep(1);}
 return {};
}
int main(int argc,char**argv){QCoreApplication app(argc,argv);TestScriptingInterface test;
 auto client=DependencyManager::get<AssetClient>();auto nodes=DependencyManager::get<NodeList>();
 auto request=query('b');auto first=test.phoneAssetsRead(request);
 if(first.value("pending")!=true||live!=1)return 1;
 auto forged=request;forged["expected"]=true;
 if(!test.phoneAssetsRead(query('c')).isEmpty()||!test.phoneAssetsRead(forged).isEmpty())return 2;
 auto result=finished(test,request);auto source=result.value("source").toMap();
 if(source.value("mappings").toList().size()!=2||source.value("canWrite")!=true||live!=0
   ||result.value("activeRequests")!=0||result.value("retainedResults")!=0)return 3;
 if(!test.phoneAssetsRead(request).isEmpty()||test._phoneAssetsRead->same(request))return 4;
 auto download=query('e',true);if(test.phoneAssetsRead(download).value("pending")!=true)return 5;
 result=finished(test,download);source=result.value("source").toMap();
 if(QByteArray::fromBase64(source.value("base64").toString().toLatin1())!=bytes||source.value("hash")!=hash||live!=0)return 6;
 if(!test.phoneAssetsRead(request).isEmpty()||live!=0)return 16;
 // Resolve the actual GetMapping request path/hash/redirect on its owner thread.
 auto resolve=query('d');resolve["action"]="phone-assets-resolve";resolve["path"]="/e2e-"+QString(32,'a')+"/stand.fbx";
 test.phoneAssetsRead(resolve);auto resolved=finished(test,resolve).value("source").toMap();
 if(resolved.value("requestedPath")!=resolve.value("path")||resolved.value("hash")!=hash||resolved.value("redirected")!=false||live!=0)return 25;
 client->redirect=true;resolve["commandId"]=QString(32,'0'); // All-zero command IDs remain forbidden.
 if(!test.phoneAssetsRead(resolve).isEmpty())return 26;resolve["commandId"]=QString(32,'6');test.phoneAssetsRead(resolve);
 resolved=finished(test,resolve).value("source").toMap();if(resolved.value("redirected")!=true||resolved.value("redirectedPath")!="/.baked/"+hash+"/asset.fbx"||live!=0)return 27;
 resolve["commandId"]=QString(32,'7');resolve["path"]="/foreign/stand.fbx";if(!test.phoneAssetsRead(resolve).isEmpty())return 28;
 // Permission is read again on the actual GUI owner after network data was copied.
 auto permission=query('f');test.phoneAssetsRead(permission);nodes->write=false;
 result=finished(test,permission);if(result.value("source").toMap().value("canWrite")!=false)return 7;
 // A real request error is retained as a failed original, never empty success.
 client->fail=true;auto failed=query('1');test.phoneAssetsRead(failed);result=finished(test,failed);
 if(result.value("source").toMap().value("complete")!=false||live!=0)return 8;client->fail=false;
 // Cancel only the actual read lease. The QObject must die on its own thread
 // before the native job admits a new request; no success packet is fabricated.
 client->block=true;auto pending=query('2');test.phoneAssetsRead(pending);
 if(test.phoneAssetsRead(pending,true).value("pending")!=true)return 9;
 QElapsedTimer clock;clock.start();while(clock.elapsed()<1200&&test._phoneAssetsRead->same(pending)){
  QCoreApplication::processEvents();test.phoneAssetsRead(pending,true);QThread::msleep(1);}
 if(live!=0||test._phoneAssetsRead->same(pending))return 10;client->block=false;
 auto resumed=query('3');test.phoneAssetsRead(resumed);if(finished(test,resumed).isEmpty())return 11;
 // A replaced Asset Server within the same domain cannot supply an old reply.
 auto serverChanged=query('8');test.phoneAssetsRead(serverChanged);nodes->server=std::make_shared<AssetNode>();
 QElapsedTimer serverClock;serverClock.start();while(serverClock.elapsed()<1200&&test._phoneAssetsRead->same(serverChanged)){
  QCoreApplication::processEvents();auto packet=test.phoneAssetsRead(serverChanged);if(packet.contains("source"))return 20;QThread::msleep(1);}
 if(live!=0||test._phoneAssetsRead->same(serverChanged))return 21;
 // Even an already copied but unconsumed reply is fenced at final delivery.
 auto afterCopy=query('9');test.phoneAssetsRead(afterCopy);serverClock.restart();
 while(serverClock.elapsed()<1200&&live){QCoreApplication::processEvents();QThread::msleep(1);}
 QCoreApplication::processEvents();nodes->server=std::make_shared<AssetNode>();
 if(test.phoneAssetsRead(afterCopy).contains("source")||test._phoneAssetsRead->same(afterCopy))return 22;
 auto missingServer=nodes->server;nodes->server.reset();if(!test.phoneAssetsRead(query('a')).isEmpty())return 23;nodes->server=missingServer;
 // A changed domain cannot adopt the original reply from a prior connection.
 auto changed=query('4');test.phoneAssetsRead(changed);nodes->domain.id=QUuid::createUuid();
 clock.restart();while(clock.elapsed()<1200&&test._phoneAssetsRead->same(changed)){
  QCoreApplication::processEvents();auto packet=test.phoneAssetsRead(changed);if(packet.contains("source"))return 12;QThread::msleep(1);}
 if(live!=0||test._phoneAssetsRead->same(changed))return 13;
 // Canonical byte identities are reduced, never trusted from the requested hash.
 if(!overte::e2e::assetsDownloadOriginal(QString(64,'0'),bytes,false,"domain","session","server").isEmpty())return 14;
 auto invalid=query('5');invalid["schemaVersion"]=true;if(!test.phoneAssetsRead(invalid).isEmpty())return 15;
 // Compile/execute the actual file-service wrapper against its real private filesystem.
 QTemporaryDir privateFiles;if(!privateFiles.isValid())return 17;test._testResultsLocation=privateFiles.path();
 QVariantMap fileInputs;for(const auto& name:overte::e2e::PrivateAssetsFiles::inputs())fileInputs[name]=QString::fromLatin1(bytes.toBase64());
 QVariantMap fileCall{{"schemaVersion",1},{"commandId",QString(32,'6')},{"action","phone-assets-files"},{"operation","stage"},
  {"runId",QString(32,'a')},{"ownerToken",QString(64,'c')},{"files",fileInputs}};
 auto fileResult=test.phoneAssetsFiles(fileCall);
 if(fileResult.value("source").toMap().value("exists")!=true||fileResult.value("sequence")!=1)return 18;
 fileCall.remove("files");fileCall["operation"]="release";fileCall["commandId"]=QString(32,'7');fileResult=test.phoneAssetsFiles(fileCall);
 if(fileResult.value("source").toMap().value("exists")!=false||fileResult.value("source").toMap().value("retired")!=true||fileResult.value("sequence")!=2)return 19;
 return 0;
}
'''


class AssetsNativeReadTests(unittest.TestCase):
    def test_actual_native_method_copies_network_originals_and_retires_real_requests(self):
        self.assertIsNotNone(shutil.which('c++'))
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
        moc=Path('/usr/lib64/qt6/libexec/moc');self.assertTrue(moc.is_file())
        text=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=text.index('QVariantMap TestScriptingInterface::phoneAssetsRead(')
        end=text.index('\nQVariantMap TestScriptingInterface::',start+1)
        method=text[start:end]
        file_start=text.index('QVariantMap TestScriptingInterface::phoneAssetsFiles(')
        file_end=text.index('\nQVariantMap TestScriptingInterface::',file_start+1)
        method=text[file_start:file_end]+method
        build=ROOT/'build/assets-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='read-',dir=build) as temporary:
            stage=Path(temporary);source=stage/'source.cpp'
            source.write_text(STUB+method+MAIN+'\n#include "source.moc"\n')
            subprocess.run([str(moc),str(source),'-o',str(stage/'source.moc')],check=True,timeout=30)
            subprocess.run(['c++','-std=c++17','-fPIC','-fmax-errors=1','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(ROOT),str(source),'-o',str(stage/'read'),*flags],check=True,timeout=60)
            subprocess.run([str(stage/'read'),'--testScript'],check=True,timeout=20,env=os.environ.copy())


if __name__=='__main__':unittest.main()
