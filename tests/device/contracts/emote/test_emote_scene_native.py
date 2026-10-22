"""Original bounded Pico scene getter/header with Qt objects and real glm math.

Entity tree/dependency/model/camera APIs are explicit seams. No renderer,
Browser, Interface application, HMD or OpenXR/device execution is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
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
from adapters.pico4.emote_scene_source import validate,receipt,ready,retired,NativePicoEmoteScene
from adapters.native_avatar_render import controlled_resources
from adapters.normal_ui import NativeUIError

ENTITY=r'''
namespace entity {enum class HostType{LOCAL,DOMAIN};}
namespace EntityTypes {enum EntityType{Unknown,Box,Web};
QString getEntityTypeName(EntityType v){return v==Box ? "Box" : v==Web ? "Web" : "Unknown";}}
struct EntityItemProperties {
 EntityTypes::EntityType type{EntityTypes::Unknown};QString name,url;glm::vec3 position{},size{};glm::quat orientation{1,0,0,0};
 glm::u8vec3 color{0};bool visible{false},collisionless{false},shadow{true},locked{false};float dpi{30};QUuid parent;
 void setType(EntityTypes::EntityType v){type=v;}auto getType()const{return type;}
 void setName(const QString&v){name=v;}auto getName()const{return name;}
 void setPosition(const glm::vec3&v){position=v;}auto getPosition()const{return position;}
 void setRotation(const glm::quat&v){orientation=v;}auto getRotation()const{return orientation;}
 void setDimensions(const glm::vec3&v){size=v;}auto getDimensions()const{return size;}
 void setColor(const glm::u8vec3&v){color=v;}auto getColor()const{return color;}
 void setVisible(bool v){visible=v;}bool getVisible()const{return visible;}
 void setLocked(bool v){locked=v;}bool getLocked()const{return locked;}
 void setCollisionless(bool v){collisionless=v;}bool getCollisionless()const{return collisionless;}
 void setCanCastShadow(bool v){shadow=v;}bool getCanCastShadow()const{return shadow;}
 void setDpi(float v){dpi=v;}float getDpi()const{return dpi;}
 void setSourceUrl(const QString&v){url=v;}auto getSourceUrl()const{return url;}
 auto getParentID()const{return parent;}auto getEntityHostType()const{return entity::HostType::LOCAL;}
 qulonglong getLastEdited()const{return static_cast<qulonglong>(QDateTime::currentMSecsSinceEpoch())*1000;}
};
struct EntityItem:QObject {
 EntityItemProperties properties;QUuid id;bool child{false};
 auto getProperties()const{return properties;}bool isLocalEntity()const{return true;}
 bool getLocked()const{return properties.locked;}bool hasChildren()const{return child;}
 auto getParentID()const{return properties.parent;}QUuid getCloneOriginID()const{return {};}
 QVector<QUuid>getCloneIDs()const{return {};}
};
using WebEntityItem=EntityItem;using ShapeEntityItem=EntityItem;using EntityItemPointer=std::shared_ptr<EntityItem>;
struct EntityTree {
 QHash<QUuid,EntityItemPointer> objects;int deletions{0};
 template<class F>void withReadLock(F&&fn){fn();}template<class F>void withWriteLock(F&&fn){fn();}
 EntityItemPointer findEntityByEntityItemID(const QUuid&id){return objects.value(id);}
 void deleteEntitiesByPointer(const std::vector<EntityItemPointer>&list){for(const auto&item:list){assert(objects.value(item->id)==item);objects.remove(item->id);++deletions;}}
};
struct EntityScriptingInterface {
 EntityTree tree;int adds{0};bool failSecond{false};EntityTree*getEntityTree(){return &tree;}
 QUuid addEntity(const EntityItemProperties&properties,const QString&host){
  assert(host=="local");++adds;if(failSecond && adds==2)return {};
  auto webDeleter=ORIGINAL_WEB_DELETER;auto shapeDeleter=ORIGINAL_SHAPE_DELETER;
  EntityItemPointer item(new EntityItem,properties.type==EntityTypes::Web ? webDeleter : shapeDeleter);
  item->id=QUuid::createUuid();item->properties=properties;tree.objects.insert(item->id,item);return item->id;
 }
};
std::shared_ptr<EntityScriptingInterface> entities{new EntityScriptingInterface};bool dependencies{true};
'''
MAIN=r'''
QVariantMap prepare(QString run,int n){return {{"schemaVersion",1},{"commandId",QString::number(n,16).rightJustified(32,'0')},
 {"action","feature-pico-emote-scene-input"},{"operation","prepare"},{"runId",run},{"ticket",QString(32,'d')},
 {"fixtureUrl","http://controlled.invalid/feature-fixture/v1/runs/"+run+"/"},
 {"imageExtent",QVariantList{800,500}},{"markerRoi",QVariantList{40,20,240,60}}};}
QVariantMap observe(QString run,int n){return {{"schemaVersion",1},{"commandId",QString::number(n,16).rightJustified(32,'0')},
 {"action","feature-pico-emote-scene-observe"},{"runId",run}};}
void emitScene(const QVariantMap&request,const QVariantMap&packet){assert(!packet.isEmpty());
 std::cout<<QJsonDocument(QJsonObject::fromVariantMap({{"kind","scene"},{"request",request},{"packet",packet}})).toJson(QJsonDocument::Compact).constData()<<std::endl;}
void turn(){QTimer::singleShot(2,[]{QCoreApplication::quit();});QCoreApplication::exec();}
int main(int argc,char**argv){
 TestApp app(argc,argv);TestScriptingInterface test;const QString run(32,'b');
 assert(QResource::registerResource(app.arguments().value(app.arguments().indexOf("--resource-file")+1)));
 if(!app.arguments().contains("--testScript")){assert(test.featurePicoEmoteScene(prepare(run,1)).isEmpty()&&entities->adds==0&&managerReads==0);return 0;}
 manager.reset(new AvatarManager);manager->avatar->model->geometry->hfm.originalURL="qrc:/meshes/mannequin/mannequin.fbx";
 QVariantMap avatarCommand{{"schemaVersion",1},{"commandId",QString(32,'a')},{"action","feature-avatar-render-observe"}};
 const auto avatar=test.featureAvatarRenderObservation(avatarCommand);
 std::cout<<QJsonDocument(QJsonObject::fromVariantMap({{"kind","avatar"},{"packet",avatar}})).toJson(QJsonDocument::Compact).constData()<<std::endl;
 // A timed-out original queued functor never creates its old scene later.
 std::thread blocked([&]{assert(test.featurePicoEmoteScene(prepare(QString(32,'c'),10)).isEmpty());});blocked.join();
 assert(entities->adds==0);assert(test.featurePicoEmoteScene(prepare(run,11)).isEmpty());turn();assert(entities->adds==0);
 app.hmd=false;assert(test.featurePicoEmoteScene(prepare(run,12)).isEmpty());assert(entities->adds==0);app.hmd=true;
 const auto input=prepare(run,13);const auto receipt=test.featurePicoEmoteScene(input);emitScene(input,receipt);assert(entities->adds==2);
 assert(test.featurePicoEmoteScene(input)==receipt && entities->adds==2);
 auto wrong=input;wrong.insert("expected",true);assert(test.featurePicoEmoteScene(wrong).isEmpty());assert(entities->adds==2);
 auto query=observe(run,14);auto active=test.featurePicoEmoteScene(query);emitScene(query,active);
 // Measured property changes are observable and cannot be accepted as layout.
 const auto markerId=QUuid(active.value("source").toMap().value("objects").toList()[1].toMap().value("id").toString());
 entities->tree.objects[markerId]->properties.position.x+=2;
 auto changedRequest=observe(run,15);emitScene(changedRequest,test.featurePicoEmoteScene(changedRequest));
 entities->tree.objects[markerId]->properties.position.x-=2;
 auto replacement=std::make_shared<EntityItem>();replacement->id=markerId;
 auto original=entities->tree.objects[markerId];entities->tree.objects[markerId]=replacement;
 auto release=QVariantMap{{"schemaVersion",1},{"commandId",QString(30,'0')+"10"},{"action","feature-pico-emote-scene-input"},
  {"operation","release"},{"runId",run},{"fixtureInstance",active.value("source").toMap().value("fixtureInstance")}};
 assert(test.featurePicoEmoteScene(release).isEmpty() && entities->tree.deletions==0);entities->tree.objects[markerId]=original;
 // A distinct release request is not a retry of an uncertain product input.
 // The previous native preflight is proven to have performed zero deletions.
 release["commandId"]=QString(30,'0')+"11";emitScene(release,test.featurePicoEmoteScene(release));assert(entities->tree.deletions==2);
 auto absent=observe(run,18);emitScene(absent,test.featurePicoEmoteScene(absent));
 // A retained original shared owner and then actual deferred QObject death are
 // distinct from tree absence. Release our explicit original owner first.
 original.reset();replacement.reset();
 auto deferred=observe(run,19);emitScene(deferred,test.featurePicoEmoteScene(deferred));
 turn();auto drained=observe(run,20);emitScene(drained,test.featurePicoEmoteScene(drained));
 assert(test.featurePicoEmoteScene(prepare(run,21)).isEmpty());
 test._featureLifecycle.reset();assert(test.featurePicoEmoteScene(observe(run,22)).isEmpty());
}
'''


class EmoteSceneNativeTests(unittest.TestCase):
    def test_original_scene_header_getter_queue_and_actual_qobject_retirement(self):
        spec=importlib.util.spec_from_file_location('emote_avatar_template',Path(__file__).with_name('test_avatar_render_native.py'))
        base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        harness=base.HARNESS[:base.HARNESS.index('int main(')]+MAIN
        begin=harness.index('namespace glm {');end=harness.index('\nclass Geometry',begin)
        harness=harness[:begin]+'#include <glm/glm.hpp>\n#include <glm/gtc/quaternion.hpp>\n#include <glm/gtc/matrix_transform.hpp>\n#include <glm/gtc/type_precision.hpp>\n#include <vector>\n#include <QTimer>\n#include <QPointer>\n#include <QHash>\n#include <QVector>\n#include <thread>\n#include <type_traits>\n'+harness[end:]
        entity=ENTITY
        for name,filename in (('WEB','WebEntityItem.cpp.in'),('SHAPE','ShapeEntityItem.cpp.in')):
            code=(ROOT/'libraries/entities/src'/filename).read_text();marker='[]('+('Web' if name=='WEB' else 'Shape')+'EntityItem* ptr)'
            entity=entity.replace('ORIGINAL_'+name+'_DELETER',base.block(code,marker))
        pos=harness.index('class DependencyManager');end=harness.index('\nclass ViewFrustum',pos)
        harness=harness[:pos]+entity+'''class DependencyManager{public:template<class T>static bool isSet(){return dependencies && (std::is_same_v<T,AvatarManager>?bool(manager):bool(entities));}
 template<class T>static std::shared_ptr<T>get(){++managerReads;if constexpr(std::is_same_v<T,AvatarManager>)return manager;else return entities;}};\n'''+harness[end:]
        harness=harness.replace('return {0,0,0,1};','return glm::quat(1,0,0,0);').replace('return "third person";','return "look at";')
        harness=harness.replace('glm::mat4 projection;','glm::mat4 projection{glm::perspective(glm::radians(73.f),1.6f,.1f,1000.f)};')
        harness=harness.replace('class TestScriptingInterface:public QObject{','#include "tests/device/native/PicoEmoteSceneFixture.h"\n#include "tests/device/native/AudioSettingsQueue.h"\nclass TestScriptingInterface:public QObject{')
        harness=harness.replace('QVariantMap featureAvatarRenderObservation(const QVariantMap&command);','''QVariantMap featureAvatarRenderObservation(const QVariantMap&command);
 QVariantMap featurePicoEmoteScene(const QVariantMap&command);
 std::shared_ptr<overte::e2e::PicoEmoteSceneFixture>_featureEmoteScene;
 std::shared_ptr<overte::e2e::AudioSettingsQueue>_featureEmoteSceneQueue{new overte::e2e::AudioSettingsQueue};
 quint64 _featureEmoteSceneSequence{0};QHash<QString,QVariantMap>_featureEmoteSceneCommands,_featureEmoteSceneResults;''')
        model=(ROOT/'libraries/render-utils/src/Model.h').read_text();geometry=(ROOT/'libraries/model-networking/src/model-networking/ModelCache.h').read_text()
        rig=(ROOT/'libraries/animation/src/Rig.h').read_text();avatar_header=(ROOT/'interface/src/avatar/MyAvatar.h').read_text();avatar_code=(ROOT/'interface/src/avatar/MyAvatar.cpp').read_text()
        pieces=dict(GETTER=base.block(source,'QVariantMap TestScriptingInterface::featureAvatarRenderObservation(')+'\n'+base.block(source,'QVariantMap TestScriptingInterface::featurePicoEmoteScene('),
            MODEL_GETTER=base.block(model,'    QString e2eModelInstance()'),GEOMETRY_GETTER=base.block(geometry,'    QString e2eGeometryInstance()'),RIG_GETTER=base.block(rig,'    int e2eRigId()'),
            MODEL_IDENTITY=model[model.index('    const QString _e2eModelInstance'):model.index(';',model.index('    const QString _e2eModelInstance'))+1],
            GEOMETRY_IDENTITY=base.block(geometry,'    struct Identity')+' _e2eIdentity;',ORIGINAL_BOOM_GETTER=base.block(avatar_header,'    float getBoomLength() const'),
            ORIGINAL_ZOOM_CONSTANTS='\n'.join(line for line in avatar_code.splitlines() if line.startswith(('const float MyAvatar::ZOOM_MIN =','const float MyAvatar::ZOOM_DEFAULT ='))))
        for key in sorted(pieces,key=len,reverse=True):harness=harness.replace(key,pieces[key])
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');prefix=None;extra=[]
        self.assertIn(major,('5','6'))
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True);environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'));extra=['-L'+str(prefix/'usr/lib64')]
        if environment.get('OVERTE_TEST_GLM_INCLUDE'):extra+=['-I'+str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True))]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        rcc=prefix/'usr/lib64/qt5/bin/rcc' if prefix else Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt'+major+'Core'],text=True,env=environment).strip())/'rcc'
        with tempfile.TemporaryDirectory(prefix='pico-emote-scene-native-') as directory:
            path=Path(directory)
            for name in ('EntityScriptingInterface','EntityTree','EntityItem','EntityItemProperties','ViewFrustum'):(path/(name+'.h')).write_text('#pragma once\n')
            cpp=path/'test.cpp';cpp.write_text(harness);binary=path/'test';bundle=path/'avatar.rcc';qrc=path/'avatar.qrc'
            qrc.write_text('<RCC><qresource prefix="/meshes"><file alias="defaultAvatar_full.fst">'+str(ROOT/'interface/resources/meshes/defaultAvatar_full.fst')+'</file><file alias="mannequin/mannequin.fbx">'+str(ROOT/'interface/resources/meshes/mannequin/mannequin.fbx')+'</file></qresource></RCC>')
            subprocess.run([str(rcc),'--binary',str(qrc),'-o',str(bundle)],check=True,timeout=30,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE','-I'+directory,'-I'+str(ROOT),str(cpp),'-o',str(binary),*extra,*flags],text=True,capture_output=True,timeout=60,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:10000])
            subprocess.run([str(binary),'--resource-file',str(bundle)],check=True,timeout=10,env=environment,capture_output=True)
            ran=subprocess.run([str(binary),'--resource-file',str(bundle),'--testScript'],check=True,timeout=15,text=True,capture_output=True,env=environment)
            rows=[json.loads(line) for line in ran.stdout.splitlines()];avatar=rows[0]['packet'];controlled_resources(avatar);scenes=rows[1:]
            original=None;history=[]
            for row in scenes:
                request,packet=row['request'],row['packet'];(validate if request['action'].endswith('observe') else receipt)(packet,request,packet['processId'],packet['capturedEpochMs'])
                history.append(dict(request=request,packet=packet))
            prepare=scenes[0]['request'];ready(scenes[1]['packet'],prepare,avatar)
            with self.assertRaises(NativeUIError):ready(scenes[2]['packet'],prepare,avatar)
            self.assertFalse(retired(scenes[-3]['packet']));self.assertFalse(retired(scenes[-2]['packet']));self.assertTrue(retired(scenes[-1]['packet']))
            reader=NativePicoEmoteScene(lambda *_:self.fail('No input in restore'),lambda:self.fail('No reads in restore'),lambda:0,lambda:True,avatar['processId'])
            reader.restore(history);self.assertEqual(scenes[-1]['packet'],reader.last_observation)


if __name__=='__main__':unittest.main()
