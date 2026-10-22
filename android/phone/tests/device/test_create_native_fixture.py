"""Compile actual Create fixture ownership against explicit synthetic endpoints.

Qt matrix math and the production E2E header execute; this is not an Android
client build, renderer test or device acceptance.
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
#include <QMatrix4x4>
#include <QQuaternion>
#include <QVariant>
#include <QUuid>
#include <QMap>
#include <memory>
#include <vector>
namespace glm {
struct vec4 {float x,y,z,w;vec4(float a,float b,float c,float d):x(a),y(b),z(c),w(d){}};
struct vec3 {float x,y,z;vec3(float a=0):x(a),y(a),z(a){}vec3(float a,float b,float c):x(a),y(b),z(c){}vec3(vec4 a):x(a.x),y(a.y),z(a.z){}vec3&operator*=(float n){x*=n;y*=n;z*=n;return *this;}};
inline vec3 operator+(vec3 a,vec3 b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
inline vec3 operator-(vec3 a,vec3 b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
inline vec3 operator*(vec3 a,float n){return {a.x*n,a.y*n,a.z*n};}
inline vec3 operator/(vec3 a,float n){return a*(1/n);}
inline float dot(vec3 a,vec3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
struct quat {float x=0,y=0,z=0,w=1;};
inline quat inverse(quat q){return {-q.x,-q.y,-q.z,q.w};}
inline vec3 operator*(quat q,vec3 v){auto r=QQuaternion(q.w,q.x,q.y,q.z).rotatedVector(QVector3D(v.x,v.y,v.z));return {r.x(),r.y(),r.z()};}
struct mat4 {QMatrix4x4 m;const float*operator[](int column)const{return m.constData()+column*4;}};
inline mat4 inverse(mat4 a){return {a.m.inverted()};}
inline vec4 operator*(mat4 a,vec4 v){auto r=a.m*QVector4D(v.x,v.y,v.z,v.w);return {r.x(),r.y(),r.z(),r.w()};}
struct u8vec3 {unsigned char x,y,z;u8vec3(int n):x(n),y(n),z(n){}u8vec3(int a,int b,int c):x(a),y(b),z(c){}};
}
namespace entity {enum class HostType {LOCAL,DOMAIN};}
namespace EntityTypes {enum EntityType {Unknown,Box,Web};inline QString getEntityTypeName(EntityType type){return type==Box?"Box":type==Web?"Web":"Unknown";}}
struct EntityItemProperties {
 EntityTypes::EntityType type=EntityTypes::Unknown;QString name,url;glm::vec3 position,dimensions;glm::quat rotation;glm::u8vec3 color{128};
 bool visible=false,locked=false,collision=false,shadow=true;int dpi=0;
 void setType(EntityTypes::EntityType v){type=v;}void setName(QString v){name=v;}void setPosition(glm::vec3 v){position=v;}
 void setDimensions(glm::vec3 v){dimensions=v;}void setRotation(glm::quat v){rotation=v;}void setVisible(bool v){visible=v;}
 void setCollisionless(bool v){collision=v;}void setCanCastShadow(bool v){shadow=v;}void setLocked(bool v){locked=v;}
 void setSourceUrl(QString v){url=v;}void setDpi(int v){dpi=v;}void setColor(glm::u8vec3 v){color=v;}
 EntityTypes::EntityType getType()const{return type;}QString getName()const{return name;}QString getSourceUrl()const{return url;}
 glm::vec3 getPosition()const{return position;}glm::vec3 getDimensions()const{return dimensions;}glm::quat getRotation()const{return rotation;}
 bool getVisible()const{return visible;}bool getLocked()const{return locked;}bool getCollisionless()const{return collision;}bool getCanCastShadow()const{return shadow;}
 int getDpi()const{return dpi;}glm::u8vec3 getColor()const{return color;}QUuid getParentID()const{return {};}
 entity::HostType getEntityHostType()const{return entity::HostType::LOCAL;}quint64 getLastEdited()const{return 1;}
};
struct EntityItem {EntityItemProperties properties;bool child=false,local=true;QUuid clone;
 bool isLocalEntity()const{return local;}bool getLocked()const{return properties.locked;}bool hasChildren()const{return child;}
 QUuid getParentID()const{return {};}QUuid getCloneOriginID()const{return clone;}QList<QUuid>getCloneIDs()const{return {};}
 EntityItemProperties getProperties()const{return properties;}};
using EntityItemPointer=std::shared_ptr<EntityItem>;
struct EntityTree {QMap<QUuid,EntityItemPointer>objects;
 template<typename F>void withReadLock(F fn){fn();}template<typename F>void withWriteLock(F fn){fn();}
 EntityItemPointer findEntityByEntityItemID(QUuid id){return objects.value(id);}
 void deleteEntitiesByPointer(const std::vector<EntityItemPointer>& values){for(auto object:values){for(auto it=objects.begin();it!=objects.end();){if(it.value()==object)it=objects.erase(it);else ++it;}}}};
struct EntityScriptingInterface {std::shared_ptr<EntityTree>tree=std::make_shared<EntityTree>();
 auto getEntityTree(){return tree;}QUuid addEntity(EntityItemProperties properties,QString host){if(host!="local")return {};auto id=QUuid::createUuid();auto item=std::make_shared<EntityItem>();item->properties=properties;tree->objects[id]=item;return id;}};
struct DependencyManager {template<typename T>static std::shared_ptr<T>get(){static auto value=std::make_shared<T>();return value;}};
struct ViewFrustum {glm::mat4 projection;ViewFrustum(){projection.m.perspective(60.f,4.f/3.f,.1f,100.f);}
 bool isPerspective()const{return true;}glm::vec3 getPosition()const{return {0,1.6,0};}glm::quat getOrientation()const{return {};}
 float getFieldOfView()const{return 60;}float getAspectRatio()const{return 4.f/3.f;}float getNearClip()const{return .1f;}float getFarClip()const{return 100;}
 glm::mat4 getProjection()const{return projection;}};
'''
MAIN=r'''#include "tests/device/native/PhoneCreateFixture.h"
#include <iostream>
int main(int argc,char**argv){QCoreApplication app(argc,argv);overte::e2e::PhoneCreateFixture fixture;ViewFrustum view;
 QString run="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
 QVariantMap command{{"schemaVersion",1},{"commandId","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},{"action","phone-create-fixture-input"},{"operation","prepare"},
 {"runId",run},{"ticket","cccccccccccccccccccccccccccccccc"},{"fixtureUrl","http://controlled.invalid/feature-fixture/v1/runs/"+run+"/"},
 {"imageExtent",QVariantList{1000,750}},{"markerRoi",QVariantList{20,20,180,60}}};
 auto receipt=fixture.input(command,view,"first person look at",{0,0,0},1,0);auto active=fixture.observe(run);
 auto tree=DependencyManager::get<EntityScriptingInterface>()->tree;auto id=tree->objects.firstKey();auto original=tree->objects[id];
 QVariantMap release{{"schemaVersion",1},{"commandId","dddddddddddddddddddddddddddddddd"},{"action","phone-create-fixture-input"},{"operation","release"},
 {"runId",run},{"fixtureInstance",active.value("fixtureInstance")}};
 original->child=true;auto child=fixture.input(release,view,"first person look at",{0,0,0},1,0);original->child=false;
 auto replacement=std::make_shared<EntityItem>();replacement->properties=original->properties;tree->objects[id]=replacement;
 auto foreign=fixture.input(release,view,"first person look at",{0,0,0},1,0);auto sameId=fixture.observe(run);
 tree->objects[id]=original;auto removed=fixture.input(release,view,"first person look at",{0,0,0},1,0);auto retained=fixture.observe(run);
 original.reset();auto drained=fixture.observe(run);command["commandId"]="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
 auto replay=fixture.input(command,view,"first person look at",{0,0,0},1,0);
 std::cout<<QJsonDocument::fromVariant(QVariantMap{{"receipt",receipt},{"active",active},{"child",child},{"foreign",foreign},{"sameId",sameId},
 {"removed",removed},{"retained",retained},{"drained",drained},{"replay",replay}}).toJson().toStdString();}
'''


class CreateNativeFixtureTests(unittest.TestCase):
    def test_actual_fixture_header_owns_three_originals_refuses_foreign_children_and_drains_weak_lifetimes(self):
        build=ROOT/'build/create-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='fixture-',dir=build) as temporary:
            stage=Path(temporary);(stage/'synthetic.h').write_text(STUB)
            for name in ('EntityScriptingInterface','EntityTree','EntityItem','EntityItemProperties','ViewFrustum'):(stage/(name+'.h')).write_text('#include "synthetic.h"\n')
            (stage/'main.cpp').write_text(MAIN)
            flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui'],text=True).split()
            subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(stage),'-I'+str(ROOT),
                str(stage/'main.cpp'),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            value=json.loads(subprocess.check_output([str(stage/'check')],text=True,timeout=5))
        self.assertTrue(value['receipt']['recorded']);self.assertEqual(2,value['active']['phoneCreateFixtureVersion'])
        self.assertEqual(['backdrop','accent','marker'],[row['role'] for row in value['active']['objects']])
        self.assertEqual([40,70,100],value['active']['entities'][1]['color']);self.assertEqual('active',value['active']['phase'])
        self.assertEqual({},value['child']);self.assertEqual({},value['foreign']);self.assertTrue(any(not row['originalObject'] for row in value['sameId']['entities']))
        self.assertTrue(value['removed']['recorded']);self.assertEqual(1,value['retained']['retainedObjects']);self.assertEqual('releasing',value['retained']['phase'])
        self.assertEqual('drained',value['drained']['phase']);self.assertEqual(0,value['drained']['retainedObjects']);self.assertEqual([],value['drained']['entities']);self.assertEqual({},value['replay'])


if __name__=='__main__':unittest.main()
