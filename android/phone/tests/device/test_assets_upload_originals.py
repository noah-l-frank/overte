"""Compile actual passive bundle hooks and retire actual Qt network QObjects.

The normal AssetMappings product callbacks are deliberately not replaced or
qualified by this test. Explicit upload/mapping endpoints exercise the actual
E2E source blocks on real Qt owner threads, including hostile signal payloads.
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
STUB=r'''
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <QTimer>
#include <QVariantMap>
#include <memory>
#include <iostream>
#include <cassert>
#include "tests/device/native/AssetsUploadOriginals.h"
using overte::e2e::AssetsUploadOriginals;
static const QString run=QString(32,'a'),id="12345678-1234-4234-8234-123456789abc";
static const QString filename="/private/feature-assets-"+run+"/fbx-bundle/stand.fbx";
static const QByteArray bytes("actual body owned by the upload request");
static const QString hash=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());
static QVariantMap assetsOriginalConnection(){return {{"domainId",id},{"sessionId",id},{"assetServerId",id}};}
class AssetUpload:public QObject {Q_OBJECT
public:
 QString _filename=filename;QByteArray _data=bytes;int _error=0;QVariantMap e2eOriginalUpload()const;
 void finish(AssetUpload*payload=nullptr,bool null=false){assert(QThread::currentThread()==thread());emit finished(null?nullptr:(payload?payload:this),hash);}
signals:void finished(AssetUpload*,const QString&);
};
class SetMappingRequest:public QObject {Q_OBJECT
public:
 QString path="/e2e-"+run+"/stand.fbx";int error=0;
 QString getPath()const{assert(QThread::currentThread()==thread());return path;}QString getHash()const{assert(QThread::currentThread()==thread());return hash;}
 int getError()const{assert(QThread::currentThread()==thread());return error;}
 void finish(){emit finished(this);}
signals:void finished(SetMappingRequest*);
};
class AssetMappingsScriptingInterface:public QObject {Q_OBJECT
public:
 std::shared_ptr<AssetsUploadOriginals>_e2eBundles=std::make_shared<AssetsUploadOriginals>();
 QVariantMap e2eBundleOriginals(const QString&run)const{return _e2eBundles->observe(run);}
 QVariantMap e2eReleaseBundleOriginals(const QString&run,const QString&instance,const QStringList&ids){return _e2eBundles->release(run,instance,ids);}
 struct State{QString id;};
 void uploadHook(AssetUpload*upload,const QString& actualId){auto state=std::make_shared<State>();state->id=actualId;
 UPLOAD_HOOK
 }
 void mappingHook(SetMappingRequest*request,const QString&actualId){auto state=std::make_shared<State>();state->id=actualId;
 MAPPING_HOOK
 }
};
struct DependencyManager{template<typename T>static bool isSet(){return true;}template<typename T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}};
struct Lifecycle{QVariantMap snapshot(){return {{"launches",1}};}};
class TestScriptingInterface:public QObject {Q_OBJECT
public:
 QString _testResultsLocation="private-test-root",_featureObservationInstance=QString(32,'b');quint64 _phoneAssetsUploadsSequence{0};
 std::shared_ptr<Lifecycle>_featureLifecycle=std::make_shared<Lifecycle>();
 Q_INVOKABLE QVariantMap phoneAssetsUploads(const QVariantMap& command);
};
'''
MAIN=r'''
static bool waitFor(const std::function<bool()>&ready){QElapsedTimer timer;timer.start();while(timer.elapsed()<1200){QCoreApplication::processEvents();if(ready())return true;QThread::msleep(1);}return false;}
static bool begin(const std::shared_ptr<AssetsUploadOriginals>&source,const QString&actualId=id){return source->begin(actualId,{filename},{"stand.fbx"},"/e2e-"+run+"/","stand.fbx",assetsOriginalConnection());}
int main(int argc,char**argv){QCoreApplication app(argc,argv);QThread network;network.start();int code=0;
 auto check=[&]()->int{
 auto mappings=DependencyManager::get<AssetMappingsScriptingInterface>();auto source=mappings->_e2eBundles;TestScriptingInterface test;
 QVariantMap call{{"schemaVersion",1},{"commandId",QString(32,'c')},{"action","phone-assets-uploads"},{"operation","observe"},{"runId",run}};
 auto baseline=test.phoneAssetsUploads(call);if(baseline.value("source").toMap().value("retainedBundles")!=0)return 1;
 if(!begin(source))return 2;auto upload=new AssetUpload();upload->moveToThread(&network);mappings->uploadHook(upload,id);
 QObject::connect(upload,&AssetUpload::finished,upload,&QObject::deleteLater);
 QTimer::singleShot(10,upload,[upload]{upload->finish();});
 if(!waitFor([&]{return source->observe(run).value("liveRequests")==0;}))return 3;
 auto request=new SetMappingRequest();request->moveToThread(&network);mappings->mappingHook(request,id);
 QObject::connect(request,&SetMappingRequest::finished,request,&QObject::deleteLater);
 auto current=source->observe(run);if(!source->release(run,current.value("instance").toString(),{id}).isEmpty())return 4;
 QTimer::singleShot(10,request,[request]{request->finish();});
 if(!waitFor([&]{return source->observe(run).value("liveRequests")==0;}))return 5;
 source->end(id,{});call["commandId"]=QString(32,'d');auto actual=test.phoneAssetsUploads(call);
 auto receipt=actual.value("source").toMap();auto bundle=receipt.value("bundles").toList().first().toMap();auto originals=bundle.value("requests").toList();
 if(originals.size()!=2||originals[0].toMap().value("original").toMap().value("originalSha256")!=hash||receipt.value("liveRequests")!=0||receipt.value("activeBundles")!=0)return 6;
 auto instance=receipt.value("instance").toString();call["operation"]="release";call["instance"]=instance;call["bundleIds"]=QStringList{id};call["commandId"]=QString(32,'e');
 auto released=test.phoneAssetsUploads(call);if(released.value("source").toMap().value("retired")!=true||released.value("source").toMap().value("retainedBundles")!=0)return 7;
 call["commandId"]=QString(32,'f');if(test.phoneAssetsUploads(call).value("source").toMap().value("retired")!=true)return 8;
 // A late normal operation cannot reopen an already retired measurement scope.
 if(begin(source)||source->observe(run).value("valid")!=false)return 9;
 // Deleted-without-finished and hostile null/foreign signal payloads stay red.
 for(int fault=0;fault<3;++fault){
  auto collector=std::make_shared<AssetsUploadOriginals>();mappings->_e2eBundles=collector;if(!begin(collector))return 10;
  auto bad=new AssetUpload();bad->moveToThread(&network);mappings->uploadHook(bad,id);
  if(fault==0)QMetaObject::invokeMethod(bad,&QObject::deleteLater,Qt::QueuedConnection);
  else{QObject::connect(bad,&AssetUpload::finished,bad,&QObject::deleteLater);
   QTimer::singleShot(10,bad,[bad,fault]{if(fault==1)bad->finish(nullptr,true);else{AssetUpload foreign;bad->finish(&foreign);}});}
  if(!waitFor([&]{return collector->observe(run).value("liveRequests")==0;}))return 11;
  if(collector->observe(run).value("valid")!=false)return 12;
 }
 auto context=std::make_shared<AssetsUploadOriginals>();if(!begin(context))return 13;
 auto foreign=assetsOriginalConnection();foreign["assetServerId"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
 if(!context->issue(id,"mapping",foreign).isEmpty()||context->observe(run).value("valid")!=false)return 14;
 std::cout<<QJsonDocument::fromVariant(QVariantMap{{"actual",actual},{"released",released}}).toJson().toStdString();return 0;
 };code=check();network.quit();network.wait();return code;
}
'''


class AssetsUploadOriginalTests(unittest.TestCase):
    def test_actual_passive_owner_thread_hooks_and_native_retirement_refuse_null_dead_or_foreign_requests(self):
        upload=(ROOT/'libraries/networking/src/AssetUpload.cpp').read_text();start=upload.index('QVariantMap AssetUpload::e2eOriginalUpload()')
        upload=upload[start:upload.index('\n#endif',start)]
        product=(ROOT/'interface/src/scripting/AssetMappingsScriptingInterface.cpp').read_text()
        start=product.index('        const auto originals=_e2eBundles;const auto id=state->id;const auto instance=originals->issue(id,"upload"')
        upload_hook=product[start:product.index('\n#endif',start)]
        start=product.index('        const auto originals=_e2eBundles;const auto id=state->id;const auto instance=originals->issue(id,"mapping"')
        mapping_hook=product[start:product.index('\n#endif',start)]
        methods=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();start=methods.index('QVariantMap TestScriptingInterface::phoneAssetsUploads(')
        method=methods[start:methods.index('\nQVariantMap TestScriptingInterface::',start+1)]
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
        build=ROOT/'build/assets-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='upload-',dir=build) as temporary:
            stage=Path(temporary);source=stage/'source.cpp';source.write_text(STUB.replace(' UPLOAD_HOOK',upload_hook).replace(' MAPPING_HOOK',mapping_hook)+upload+method+MAIN+'\n#include "source.moc"\n')
            subprocess.run(['/usr/lib64/qt6/libexec/moc',str(source),'-o',str(stage/'source.moc')],check=True,timeout=30)
            subprocess.run(['c++','-std=c++17','-fPIC','-fmax-errors=2','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(ROOT),str(source),'-o',str(stage/'upload'),*flags],check=True,timeout=60)
            result=subprocess.run([str(stage/'upload'),'--testScript'],check=True,capture_output=True,text=True,timeout=20,env=os.environ.copy())
            sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
            from overte_phone_assets_uploads import source as validate
            value=json.loads(result.stdout)
            for packet in value.values():validate(packet['source'],packet['runId'],packet['capturedEpochMs'])
            self.assertEqual(0,value['released']['source']['liveRequests']);self.assertTrue(value['released']['source']['retired'])


if __name__=='__main__':unittest.main()
