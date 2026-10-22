"""Compile/execute the actual read-only header with synthetic native endpoints.

Qt and the observation header are real. The Entity/Model/Domain endpoints below
are test producers; this does not compile the application or qualify a device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
STUB=r'''#pragma once
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QVariant>
#include <QString>
#include <QUuid>
#include <QMap>
#include <memory>
#include <vector>
namespace glm {
struct vec3 { float x,y,z;vec3(float v=0):x(v),y(v),z(v){} vec3(float a,float b,float c):x(a),y(b),z(c){} };
inline bool operator==(const vec3&a,const vec3&b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}
inline bool operator!=(const vec3&a,const vec3&b){return !(a==b);}
struct quat {float x=0,y=0,z=0,w=1;};
}
namespace entity {enum class HostType {LOCAL,AVATAR,DOMAIN};}
namespace EntityTypes {enum EntityType{Unknown,Model,PolyVox,Box};
inline QString getEntityTypeName(EntityType t){return t==Model?"Model":t==PolyVox?"PolyVox":t==Box?"Box":"Unknown";}}
struct EntityItemProperties {
 EntityTypes::EntityType type=EntityTypes::Unknown;QString name,url,textures;QUuid edited;quint64 created=123456;
 EntityTypes::EntityType getType()const{return type;} QString getName()const{return name;}
 entity::HostType getEntityHostType()const{return entity::HostType::DOMAIN;}
 QString getModelURL()const{return url;}QString getTextures()const{return textures;}
 QUuid getParentID()const{return {};}glm::vec3 getPosition()const{return {1,2,3};}
 glm::quat getRotation()const{return {};}glm::vec3 getDimensions()const{return {1,1,1};}
 bool getVisible()const{return true;}bool getLocked()const{return false;}
 quint64 getCreated()const{return created;}QUuid getLastEditedBy()const{return edited;}
};
struct EntityItem {virtual ~EntityItem()=default;QString instance="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
 QString e2eEntityInstance()const{return instance;}EntityItemProperties properties;};
struct Geometry {QString originalURL="http://actual.invalid/model.gltf";
 bool isHFMModelLoaded()const{return true;}const Geometry&getHFMModel()const{return *this;}
 QString e2eGeometryInstance()const{return "ffffffffffffffffffffffffffffffff";}
 QVariantList e2eCreateTextures()const{return {QVariantMap{{"originalSha256","actual-consumed-bytes"}}};}};
struct Model {std::shared_ptr<Geometry>geometry=std::make_shared<Geometry>();
 std::shared_ptr<Geometry>getGeometry()const{return geometry;}QString e2eModelInstance()const{return "dddddddddddddddddddddddddddddddd";}
 bool isLoaded()const{return true;}bool isVisible()const{return true;}bool isAddedToScene()const{return true;}};
struct RenderableModelEntityItem:EntityItem {std::shared_ptr<Model>model=std::make_shared<Model>();
 std::shared_ptr<Model>e2eOriginalModel()const{return model;}};
struct PolyVoxEntityItem:EntityItem {QByteArray bytes="original-saved-compressed-volume";bool ready=true;
 QByteArray getVoxelData()const{return bytes;}glm::vec3 getVoxelVolumeSize()const{return glm::vec3(8);}
 bool isVoxelDataReady()const{return ready;}uint8_t getVoxel(int x,int y,int z)const{return x<2&&y<3&&z<4?255:0;}};
struct EntityTree {QMap<QUuid,std::shared_ptr<EntityItem>>objects;
 template<typename F>void withReadLock(F fn){fn();}
 std::shared_ptr<EntityItem>findEntityByEntityItemID(const QUuid&id){return objects.value(id);}};
struct EntityScriptingInterface {
 std::shared_ptr<EntityTree>tree=std::make_shared<EntityTree>();bool rez=false;
 std::shared_ptr<EntityTree>getEntityTree()const{return tree;}
 QList<QUuid>findEntities(glm::vec3,float,int)const{return tree->objects.keys();}
 EntityItemProperties getEntityProperties(const QUuid&id)const{
 auto p=tree->objects.value(id);return p?p->properties:EntityItemProperties();}
 bool canRez()const{return rez;}bool canRezTmp()const{return false;}bool canRezAvatarEntities()const{return true;}};
struct Domain {QUuid getUUID()const{return QUuid("12345678-1234-4234-8234-123456789abc");}bool isConnected()const{return true;}};
struct NodeList {Domain domain;const Domain&getDomainHandler()const{return domain;}
 QUuid getSessionUUID()const{return domain.getUUID();}};
struct PickFilter {enum class FlagBit {LOCAL_ENTITIES,DOMAIN_ENTITIES,AVATAR_ENTITIES,COARSE};static int getBitMask(FlagBit){return 1;}};
struct DependencyManager {template<typename T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}};
'''
MAIN=r'''#include "tests/device/native/PhoneCreateObservation.h"
#include <iostream>
int main(int argc,char**argv){QCoreApplication app(argc,argv);
 auto entities=DependencyManager::get<EntityScriptingInterface>();
 auto model=std::make_shared<RenderableModelEntityItem>();model->properties.type=EntityTypes::Model;
 model->properties.name="e2e-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-model";model->properties.url="http://requested.invalid/model.gltf";
 model->properties.edited=DependencyManager::get<NodeList>()->getSessionUUID();
 auto voxel=std::make_shared<PolyVoxEntityItem>();voxel->properties.type=EntityTypes::PolyVox;
 voxel->properties.name="e2e-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-voxel";
 entities->tree->objects[QUuid("11111111-1111-4111-8111-111111111111")]=model;
 entities->tree->objects[QUuid("22222222-2222-4222-8222-222222222222")]=voxel;
 QVariantMap command{{"schemaVersion",1},{"commandId","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
 {"action","phone-create-observe"},{"runId","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},{"trackedIds",QVariantList{}}};
 auto original=overte::e2e::phoneCreateObservationSource(command,{0,0,0});
 command["expected"]=QVariantList{};auto rejected=overte::e2e::phoneCreateObservationSource(command,{0,0,0});
 std::cout<<QJsonDocument::fromVariant(QVariantMap{{"original",original},{"rejected",rejected}}).toJson().toStdString();}
'''


class CreateNativeMeasurementTests(unittest.TestCase):
    def test_actual_source_header_reads_original_objects_models_cells_and_permission(self):
        build=ROOT/'build/create-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='measurements-',dir=build) as temporary:
            stage=Path(temporary);(stage/'synthetic.h').write_text(STUB)
            for name in ('EntityScriptingInterface','EntityItemProperties','EntityTree','PolyVoxEntityItem',
                         'RenderableModelEntityItem','NodeList','PickFilter'):
                (stage/(name+'.h')).write_text('#include "synthetic.h"\n')
            (stage/'main.cpp').write_text(MAIN)
            flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
            subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(stage),'-I'+str(ROOT),str(stage/'main.cpp'),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            value=json.loads(subprocess.check_output([str(stage/'check'),'--testScript'],text=True,timeout=5))
        self.assertEqual({},value['rejected']);observed=value['original'];self.assertFalse(observed['canRez'])
        self.assertEqual(2,observed['phoneCreateObservationVersion'])
        rows={row['type']:row for row in observed['entities']};model=rows['Model'];voxel=rows['PolyVox']['voxel']
        self.assertEqual('e'*32,model['instance']);self.assertEqual(123456,model['createdEpochUs'])
        self.assertEqual('d'*32,model['render']['modelInstance'])
        import hashlib
        self.assertEqual(hashlib.sha256(b'http://actual.invalid/model.gltf').hexdigest(),model['render']['geometry']['sourceSha256'])
        self.assertNotEqual(hashlib.sha256(model['modelUrl'].encode()).hexdigest(),model['render']['geometry']['sourceSha256'])
        self.assertEqual(24,voxel['cells']['occupied']);self.assertEqual([8,8,8],voxel['volumeSize'])
        self.assertEqual(hashlib.sha256(b'original-saved-compressed-volume').hexdigest(),voxel['savedSha256'])


if __name__=='__main__':unittest.main()
