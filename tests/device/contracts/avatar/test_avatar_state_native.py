"""Whole original Model/Avatar URL bodies and passive Pico getter with real Qt.

ModelCache/resources, scene/rig/geometry and AvatarManager are explicit seams.
Original callback/fallback/marshaling and the complete bounded queue execute;
this does not compile full Interface, download resources or draw an avatar.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.avatar_state import validate,failed,continuity


def block(source,marker):
    start=source.index(marker);end=source.index('{',start)+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

HARNESS=r'''
#include <QCoreApplication>
#include <QThread>
#include <QTimer>
#include <QElapsedTimer>
#include <QVariantMap>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QUuid>
#include <QUrl>
#include "libraries/shared/src/shared/ReadWriteLockable.h"
#include <QDebug>
#include <memory>
#include <thread>
#include <cassert>
#include <iostream>
#include "libraries/render-utils/src/FeatureModelLoads.h"
#include "tests/device/native/AudioSettingsQueue.h"
namespace render {struct Transaction{};struct Scene{void enqueueTransaction(Transaction&){}};using ScenePointer=std::shared_ptr<Scene>;}
struct AbstractViewStateInterface{static AbstractViewStateInterface*instance(){static AbstractViewStateInterface v;return &v;}render::ScenePointer getMain3DScene(){return std::make_shared<render::Scene>();}};
struct Resource {void setLoadPriorityOperator(void*,int){}};
struct ModelCache {std::shared_ptr<Resource>getGeometryResource(const QUrl&){return std::make_shared<Resource>();}};
struct NodeList{bool isIgnoringNode(const QUuid&){return false;}};
int managerReads=0;
class AvatarManager;
std::shared_ptr<AvatarManager>manager;
class DependencyManager {public:template<class T>static bool isSet(){return bool(manager);}template<class T>static std::shared_ptr<T>get(){
 if constexpr(std::is_same_v<T,AvatarManager>){++managerReads;return manager;}else{return std::make_shared<T>();}}};
struct Geometry {QString e2eGeometryInstance()const{return instance;}bool isHFMModelLoaded()const{return true;}
 struct HFM{QString originalURL;}hfm;const HFM&getHFMModel()const{return hfm;}QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};};
struct Rig{int e2eRigId()const{return 17;}void initFlow(bool){}};
struct RenderWatcher {QUrl url;QUrl getURL()const{return url;}void setResource(const std::shared_ptr<Resource>&){url=pending;}QUrl pending;};
class Model:public QObject{Q_OBJECT
public:
 Q_INVOKABLE void setURL(const QUrl&url);void loadURLFinished(bool success);
 void removeFromScene(const render::ScenePointer&,render::Transaction&){}void invalidCalculatedMeshBoxes(){}void deleteGeometry(){geometry.reset();}
 void onInvalidate(){}void setTextures(const QVariantMap&){}QUrl getURL()const{return _url;}
 std::shared_ptr<Geometry>getGeometry()const{return geometry;}Rig&getRig(){return _rig;}bool isLoaded()const{return bool(geometry);}
 QString e2eModelInstance()const{return identity;}ORIGINAL_MODEL_LOADS_GETTER
 int getResourceDownloadAttemptsRemaining()const{return 0;}int getResourceDownloadAttempts()const{return 5;}
 void request(const QUrl&url){_renderWatcher.pending=url;setURL(url);}void complete(bool success,const QString&actual={}){
   if(success){geometry=std::make_shared<Geometry>();geometry->hfm.originalURL=actual;}loadURLFinished(success);}
 QUrl _url;RenderWatcher _renderWatcher;Rig _rig;bool _needsReload=false,_visualGeometryRequestFailed=false,_needsFixupInScene=false;
 int _loadingPriorityOperator=0;QVariantMap _pendingTextures;std::shared_ptr<Geometry>geometry;
 QString identity{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};overte::e2e::FeatureModelLoads _e2eModelLoads;
signals:void setURLFinished(bool success);
};
class AvatarData {public:
 QVariantMap e2eAvatarEntityStorage()const;
 mutable ReadWriteLockable _avatarEntitiesLock;QMap<QUuid,QByteArray>_packedAvatarEntityData;
 static QUrl defaultFullAvatarModelUrl(){return QUrl("qrc:/meshes/defaultAvatar_full.fst");}
 void setSkeletonModelURL(const QUrl&url){_skeletonModelURL=url;}QUrl _skeletonModelURL;};
enum class LoadingStatus{LoadModel,LoadFailure,LoadSuccess};
class Avatar:public QObject,public AvatarData{Q_OBJECT
public:Avatar(){QObject::connect(_skeletonModel.get(),&Model::setURLFinished,this,&Avatar::setModelURLFinished);}
 Q_INVOKABLE void setSkeletonModelURL(const QUrl&url);void setModelURLFinished(bool success);
 bool isMyAvatar()const{return true;}void createOrb(){}void indicateLoadingStatus(LoadingStatus){}void invalidateJointIndicesCache(){}
 QUrl getSkeletonModelURL()const{return _skeletonModelURL;}QUuid getSessionUUID()const{return QUuid("11111111-1111-4111-8111-111111111111");}
 auto getSkeletonModel()const{return _skeletonModel;}ORIGINAL_AVATAR_LOADS_GETTER
 float getModelScale()const{return 1;}float getTargetScale()const{return 1;}int getJointIndex(const QString&name)const{assert(name=="Hips");return 3;}
 ORIGINAL_AVATAR_PREF_URL
 ORIGINAL_AVATAR_MODEL_NAME
 QUrl _fullAvatarURLFromPreferences{"qrc:/meshes/defaultAvatar_full.fst"};QString _fullAvatarModelName{"mannequin"};
 bool getShouldRenderLocally()const{return false;}
 std::shared_ptr<Model>_skeletonModel{new Model};bool _isAnimatingScale=false,_reconstructSoftEntitiesJointMap=false;
 overte::e2e::FeatureModelLoads _e2eAvatarLoads;
};
class AvatarManager{public:std::shared_ptr<Avatar>avatar{new Avatar};auto getMyAvatar(){return avatar;}};
struct Lifecycle{QVariantMap snapshot()const{return {{"active",true}};}};
class TestScriptingInterface:public QObject{public:
 QVariantMap featurePicoAvatarState(const QVariantMap&command);
 QString _testResultsLocation{"private-results"};std::unique_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
 std::shared_ptr<overte::e2e::AudioSettingsQueue>_featureAvatarStateQueue{new overte::e2e::AudioSettingsQueue};
 QSet<QString>_featureAvatarStateRequests;quint64 _featureAvatarStateSequence{0};QString _featureObservationInstance{QString(32,'a')};
};
#define renderutils "renderutils"
#define avatars_renderer "avatars_renderer"
#define qCWarning(x) qWarning()
ORIGINAL_AVATAR_STORAGE
ORIGINAL_MODEL_SET_URL
ORIGINAL_MODEL_FINISHED
ORIGINAL_AVATAR_SET_URL
ORIGINAL_AVATAR_FINISHED
ORIGINAL_GETTER
void turn(){QTimer::singleShot(1,[]{QCoreApplication::quit();});QCoreApplication::exec();}
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);TestScriptingInterface test;int n=0;
 auto request=[&]{return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++n,16).rightJustified(32,'0')},{"action","feature-pico-avatar-state-observe"}};};
 if(!app.arguments().contains("--testScript")){assert(test.featurePicoAvatarState(request()).isEmpty()&&managerReads==0);return 0;}
 assert(test.featurePicoAvatarState(request()).isEmpty()&&managerReads==0);manager.reset(new AvatarManager);auto avatar=manager->avatar;auto model=avatar->getSkeletonModel();
 auto publish=[&](const QString&kind){const auto command=request(),packet=test.featurePicoAvatarState(command);assert(!packet.isEmpty());
   std::cout<<QJsonDocument(QJsonObject::fromVariantMap({{"kind",kind},{"request",command},{"packet",packet}})).toJson(QJsonDocument::Compact).constData()<<std::endl;
   assert(test.featurePicoAvatarState(command).isEmpty());};
 const QUuid unowned("88888888-8888-4888-8888-888888888888");avatar->_packedAvatarEntityData.insert(unowned,"unowned-original-bytes");
 const QUrl a("https://controlled.invalid/owned/avatar-a.fst"),missing("https://controlled.invalid/owned/missing.fst");
 // Invoke the actual foreign-thread setter; only the original Qt slot dispatch
 // reaches AvatarData/Model. The resource cache is an explicit source seam.
 std::thread worker([&]{avatar->setSkeletonModelURL(a);});worker.join();assert(avatar->getSkeletonModelURL().isEmpty());turn();
 model->_renderWatcher.url=a;model->complete(true,"https://controlled.invalid/owned/mannequin/mannequin.fbx");publish("loaded-a");
 avatar->setSkeletonModelURL(missing);model->_renderWatcher.url=missing;publish("missing-pending");
 model->complete(false);publish("failed-unavailable");turn();
 assert(avatar->getSkeletonModelURL()==missing && model->getURL()==AvatarData::defaultFullAvatarModelUrl());
 model->_renderWatcher.url=AvatarData::defaultFullAvatarModelUrl();model->complete(true,"qrc:/meshes/mannequin/mannequin.fbx");publish("failed-fallback");
 avatar->setSkeletonModelURL(AvatarData::defaultFullAvatarModelUrl());model->_renderWatcher.url=model->getURL();model->complete(true,"qrc:/meshes/mannequin/mannequin.fbx");publish("restored");
 // A blocked original GUI thread cannot hang or later publish a timed-out read.
 const auto before=test._featureAvatarStateSequence;std::thread blocked([&]{assert(test.featurePicoAvatarState(request()).isEmpty());});blocked.join();
 assert(test._featureAvatarStateSequence==before);assert(test.featurePicoAvatarState(request()).isEmpty());turn();publish("after-timeout-drained");
 // The real original lock never supplies a fake empty inventory while busy.
 QSemaphore held,release;std::thread writer([&]{avatar->_avatarEntitiesLock.withWriteLock([&]{held.release();release.acquire();});});held.acquire();
 QElapsedTimer bounded;bounded.start();assert(test.featurePicoAvatarState(request()).isEmpty());assert(bounded.elapsed()<100);release.release();writer.join();
 avatar->_packedAvatarEntityData[unowned]=QByteArray(65537,'x');assert(test.featurePicoAvatarState(request()).isEmpty());avatar->_packedAvatarEntityData[unowned]="unowned-original-bytes";
 // Fixed native capacity has no counter reset or new instance workaround.
 while(test._featureAvatarStateRequests.size()<512){assert(!test.featurePicoAvatarState(request()).isEmpty());}
 assert(test.featurePicoAvatarState(request()).isEmpty());
 test._featureLifecycle.reset();assert(test.featurePicoAvatarState(request()).isEmpty());
}
#include "test.moc"
'''

class AvatarStateNativeTests(unittest.TestCase):
    def test_original_url_failure_fallback_restore_and_bounded_getter(self):
        model=(ROOT/'libraries/render-utils/src/Model.cpp').read_text()
        avatar=(ROOT/'libraries/avatars-renderer/src/avatars-renderer/Avatar.cpp').read_text()
        avatar_data=(ROOT/'libraries/avatars/src/AvatarData.cpp').read_text()
        my_avatar_header=(ROOT/'interface/src/avatar/MyAvatar.h').read_text()
        model_header=(ROOT/'libraries/render-utils/src/Model.h').read_text()
        avatar_header=block((ROOT/'libraries/avatars-renderer/src/avatars-renderer/Avatar.h').read_text(),'class Avatar :')
        tsi=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        source=HARNESS
        for key,body in {
            'ORIGINAL_AVATAR_STORAGE':block(avatar_data,'QVariantMap AvatarData::e2eAvatarEntityStorage('),
            'ORIGINAL_AVATAR_PREF_URL':block(my_avatar_header,'Q_INVOKABLE QUrl getFullAvatarURLFromPreferences(').replace('Q_INVOKABLE ',''),
            'ORIGINAL_AVATAR_MODEL_NAME':block(my_avatar_header,'Q_INVOKABLE QString getFullAvatarModelName(').replace('Q_INVOKABLE ',''),
            'ORIGINAL_MODEL_LOADS_GETTER':block(model_header,'QVariantMap e2eModelLoads('),
            'ORIGINAL_AVATAR_LOADS_GETTER':block(avatar_header,'QVariantMap e2eAvatarLoads('),
            'ORIGINAL_MODEL_SET_URL':block(model,'void Model::setURL('),
            'ORIGINAL_MODEL_FINISHED':block(model,'void Model::loadURLFinished('),
            'ORIGINAL_AVATAR_SET_URL':block(avatar,'void Avatar::setSkeletonModelURL('),
            'ORIGINAL_AVATAR_FINISHED':block(avatar,'void Avatar::setModelURLFinished('),
            'ORIGINAL_GETTER':block(tsi,'QVariantMap TestScriptingInterface::featurePicoAvatarState(')}.items():source=source.replace(key,body)
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');extra=[]
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
        else:moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=environment,text=True))
        with tempfile.TemporaryDirectory(prefix='pico-avatar-native-') as directory:
            stage=Path(directory);cpp=stage/'test.cpp';cpp.write_text(source);binary=stage/'test'
            subprocess.run([str(moc),str(cpp),'-o',str(stage/'test.moc')],check=True,timeout=20,env=environment)
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),str(cpp),'-o',str(binary),*extra,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],text=True,timeout=10,env=environment)
        rows=[json.loads(line) for line in output.splitlines()];self.assertEqual(['loaded-a','missing-pending','failed-unavailable','failed-fallback','restored','after-timeout-drained'],[r['kind'] for r in rows])
        previous=None
        for row in rows:
            value=row['packet'];validate(value,row['request'],value['processId'],value['capturedEpochMs']);continuity(previous,value);previous=value
            expected=row['kind'] in ('failed-unavailable','failed-fallback');self.assertEqual(expected,failed(value['source']))
        self.assertFalse(rows[2]['packet']['source']['loaded']);self.assertTrue(rows[3]['packet']['source']['loaded'])
        self.assertEqual('https://controlled.invalid/owned/missing.fst',rows[3]['packet']['source']['requestedUrl'])
        self.assertEqual('qrc:/meshes/mannequin/mannequin.fbx',rows[3]['packet']['source']['geometry']['url'])

if __name__=='__main__':unittest.main()
