"""Compile the original avatar getter and identity fragments with real Qt5.

AvatarManager, SkeletonModel, loaded geometry, Rig and camera values are explicit
seams. This is not full Model, Geometry, TSI, application or GPU compilation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


def block(source,marker):
    start=source.index(marker);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


HARNESS=r'''
#include <QCoreApplication>
#include <QThread>
#include <QVariantMap>
#include <QJsonObject>
#include <QDateTime>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QUuid>
#include <cassert>
#include <memory>
#include <atomic>
namespace glm {
struct vec3{float x,y,z;};struct quat{float x,y,z,w;};
struct mat4{float v[4][4]{};const float*operator[](int i)const{return v[i];}};
}
class Geometry {
public:
    GEOMETRY_GETTER
    bool isHFMModelLoaded()const{return loaded;}
    struct HFM{QString originalURL;}hfm{QString("file:///original/loaded-avatar.fbx")};
    const HFM&getHFMModel()const{return hfm;}
    bool loaded{true};
private:
    GEOMETRY_IDENTITY
};
class Rig{public:RIG_GETTER private:int _rigId{17};};
class Model {
public:
    MODEL_GETTER
    std::shared_ptr<Geometry>getGeometry()const{return geometry;}
    const Rig&getRig()const{return rig;}bool isLoaded()const{return loaded;}
    bool isVisible()const{return visible;}bool isAddedToScene()const{return added;}
    std::shared_ptr<Geometry>geometry{new Geometry};Rig rig;bool loaded{true},visible{false},added{true};
private:
    MODEL_IDENTITY
};
class Avatar {
public:
    ORIGINAL_BOOM_GETTER
    float _boomLength{4.25f};
    std::shared_ptr<Model>getSkeletonModel()const{return model;}
    bool getShouldRenderLocally()const{return local;}bool shouldRender()const{return render;}
    glm::vec3 getWorldFeetPosition()const{return {2,3,4};}
    glm::quat getWorldOrientation()const{return {0,0,0,1};}float getModelScale()const{return 1.25f;}
    std::shared_ptr<Model>model{new Model};bool local{false},render{true};
};
class AvatarManager{public:std::shared_ptr<Avatar>getMyAvatar()const{return avatar;}std::shared_ptr<Avatar>avatar{new Avatar};};
std::shared_ptr<AvatarManager>manager;int managerReads{0};
class DependencyManager{public:template<class T>static bool isSet(){return bool(manager);}
    template<class T>static std::shared_ptr<T>get(){++managerReads;return manager;}};
class ViewFrustum {
public:
    const glm::mat4&getProjection()const{return projection;}
    glm::vec3 getPosition()const{return {8,9,10};}glm::quat getOrientation()const{return {0,0,0,1};}
    float getFieldOfView()const{return 73;}float getAspectRatio()const{return 1.6f;}
    float getNearClip()const{return .1f;}float getFarClip()const{return 1000;}bool isPerspective()const{return true;}
    glm::mat4 projection;
};
class Camera{public:void loadViewFrustum(ViewFrustum&v)const{v=frustum;}
    QString getModeString()const{return "third person";}ViewFrustum frustum;};
class MyAvatar{public:static const float ZOOM_MIN,ZOOM_DEFAULT;};
ORIGINAL_ZOOM_CONSTANTS
class TestApp:public QCoreApplication{public:using QCoreApplication::QCoreApplication;
    const Camera&getCamera()const{return camera;}Camera camera;bool hmd{true};bool isHMDMode()const{return hmd;}};
#undef qApp
#define qApp static_cast<TestApp*>(QCoreApplication::instance())
struct Lifecycle{QVariantMap snapshot()const{return active?QVariantMap{{"original",true}}:QVariantMap{};}bool active{true};};
class TestScriptingInterface:public QObject{
public:
    QVariantMap featureAvatarRenderObservation(const QVariantMap&command);
    QString _testResultsLocation{"owned-results"};std::unique_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
    QString _featureObservationInstance{QString(32,'a')};quint64 _featureAvatarRenderSequence{0};
};
GETTER
int main(int argc,char**argv){
    TestApp app(argc,argv);TestScriptingInterface test;
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'b')},{"action","feature-avatar-render-observe"}};
    if(!app.arguments().contains("--testScript")){
        assert(test.featureAvatarRenderObservation(command).isEmpty()&&!manager&&managerReads==0);return 0;
    }
    assert(test.featureAvatarRenderObservation(command).isEmpty()&&!manager&&managerReads==0);
    manager.reset(new AvatarManager);auto model=manager->avatar->model;
    app.camera.frustum.projection.v[2][3]=23;app.camera.frustum.projection.v[3][2]=32;
    const auto first=test.featureAvatarRenderObservation(command);const auto source=first.value("source").toMap();
    assert(first.value("instance")==QString(32,'a')&&first.value("sequence").toLongLong()==1);
    assert(source.value("modelInstance")==model->e2eModelInstance()&&source.value("rigId")==17);
    const auto geometry=source.value("geometry").toMap();
    assert(geometry.value("instance")==model->geometry->e2eGeometryInstance());
    assert(geometry.value("sourceSha256")==QString::fromLatin1(QCryptographicHash::hash(
        model->geometry->hfm.originalURL.toUtf8(),QCryptographicHash::Sha256).toHex()));
    assert(source.value("loaded")==true&&source.value("visible")==false&&source.value("localRenderingEnabled")==false);
    assert(source.value("cameraStateVersion")==1);
    assert(source.value("cameraState").toMap()==QVariantMap({{"hmd",true},{"boomLength",4.25f},{"zoomMin",MyAvatar::ZOOM_MIN},{"zoomDefault",MyAvatar::ZOOM_DEFAULT}}));
    app.hmd=false;manager->avatar->_boomLength=2.75f;
    auto next=test.featureAvatarRenderObservation(command).value("source").toMap().value("cameraState").toMap();
    assert(!next.value("hmd").toBool()&&next.value("boomLength").toFloat()==2.75f);app.hmd=true;
    assert(source.value("pose").toMap().value("feetPosition").toList()==QVariantList({2.f,3.f,4.f}));
    const auto projection=source.value("view").toMap().value("projection").toList();
    assert(projection[11]==32.f&&projection[14]==23.f); // Original row-major contract.
    auto copied=Geometry(*model->geometry);assert(copied.e2eGeometryInstance()!=model->geometry->e2eGeometryInstance());
    copied=*model->geometry;assert(copied.e2eGeometryInstance()!=model->geometry->e2eGeometryInstance());
    auto old=model->e2eModelInstance();manager->avatar->model.reset(new Model);
    assert(test.featureAvatarRenderObservation(command).value("source").toMap().value("modelInstance")!=old);
    model=manager->avatar->model;model->loaded=false;model->geometry->loaded=false;
    assert(!test.featureAvatarRenderObservation(command).value("source").toMap().value("geometry").isValid());
    for(auto bad:{QVariant(true),QVariant("1")}){auto invalid=command;invalid["schemaVersion"]=bad;
        assert(test.featureAvatarRenderObservation(invalid).isEmpty());}
    auto invalid=command;invalid["expectedModel"]="wanted";assert(test.featureAvatarRenderObservation(invalid).isEmpty());
    test._featureLifecycle->active=false;assert(test.featureAvatarRenderObservation(command).isEmpty());
    test._featureLifecycle->active=true;test._testResultsLocation.clear();assert(test.featureAvatarRenderObservation(command).isEmpty());
    test._testResultsLocation="owned-results";manager->avatar.reset();assert(test.featureAvatarRenderObservation(command).isEmpty());
    manager->avatar.reset(new Avatar);manager->avatar->model.reset();assert(test.featureAvatarRenderObservation(command).isEmpty());
    manager->avatar->model.reset(new Model);
    std::atomic<bool>done{false};std::thread worker([&]{assert(!test.featureAvatarRenderObservation(command).isEmpty());done=true;});
    while(!done){app.processEvents();QThread::msleep(1);}worker.join();
}
'''


class OriginalAvatarGetter(unittest.TestCase):
    def test_original_getter_identities_and_runtime_gate(self):
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        model=(ROOT/'libraries/render-utils/src/Model.h').read_text()
        geometry=(ROOT/'libraries/model-networking/src/model-networking/ModelCache.h').read_text()
        rig=(ROOT/'libraries/animation/src/Rig.h').read_text()
        avatar_header=(ROOT/'interface/src/avatar/MyAvatar.h').read_text()
        avatar_code=(ROOT/'interface/src/avatar/MyAvatar.cpp').read_text()
        pieces=dict(GETTER=block(source,'QVariantMap TestScriptingInterface::featureAvatarRenderObservation('),
            MODEL_GETTER=block(model,'    QString e2eModelInstance()'),
            GEOMETRY_GETTER=block(geometry,'    QString e2eGeometryInstance()'),RIG_GETTER=block(rig,'    int e2eRigId()'),
            MODEL_IDENTITY=model[model.index('    const QString _e2eModelInstance'):model.index(';',model.index('    const QString _e2eModelInstance'))+1],
            GEOMETRY_IDENTITY=block(geometry,'    struct Identity')+' _e2eIdentity;',
            ORIGINAL_BOOM_GETTER=block(avatar_header,'    float getBoomLength() const'),
            ORIGINAL_ZOOM_CONSTANTS='\n'.join(line for line in avatar_code.splitlines()
                if line.startswith(('const float MyAvatar::ZOOM_MIN =','const float MyAvatar::ZOOM_DEFAULT ='))))
        harness=HARNESS.replace('#include <atomic>','#include <atomic>\n#include <thread>')
        for key in sorted(pieces,key=len,reverse=True):harness=harness.replace(key,pieces[key])
        env=dict(os.environ);extra=[];major=env.get('OVERTE_NATIVE_QT_MAJOR','6')
        if major not in ('5','6'):raise ValueError('Unsupported Qt major')
        if major=='5' and env.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(env['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            env.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=env))
        with tempfile.TemporaryDirectory(prefix='native-avatar-source-') as directory:
            path=Path(directory);cpp=path/'test.cpp';cpp.write_text(harness);binary=path/'test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG',str(cpp),'-o',str(binary),*extra,*flags],check=True,timeout=60,env=env)
            for args in ([],['--testScript']):subprocess.run([str(binary),*args],check=True,timeout=10,env=env)


if __name__=='__main__':unittest.main()
