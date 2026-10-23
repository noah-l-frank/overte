// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Property storage, unparented transforms, model factory, Octree placement,
// packet dispatch, avatar pose and renderer are explicit host endpoints.
// Complete original API/normalization/Tree-add/factory bodies execute below.
#include <QObject>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLoggingCategory>
#include <QDateTime>
#include <QMutex>
#include <QThread>
#include <QJSValue>
#include <QCoreApplication>
#include <QMutexLocker>
#include <QVariantMap>
#include <memory>
#include <chrono>
#include <cassert>
#include <GLMHelpers.h>
#include <NumericalConstants.h>
#include <ShapeInfo.h>
#include <SimulationFlags.h>
#include "assets-dependency-host.h"
#include "assets-read-nodes-host.h"
#include "tests/device/native/CreateLocalCreations.h"
#ifndef PROFILE_RANGE
#define PROFILE_RANGE(...)
#endif
Q_DECLARE_LOGGING_CATEGORY(entities)
using EntityItemID=QUuid;
class EntityItemProperties;
class EntityItem;
using EntityItemPointer=std::shared_ptr<EntityItem>;
using EntityTypeFactory=EntityItemPointer(*)(const EntityItemID&,const EntityItemProperties&);
class EntityTypes {
public:
#include "AssetsEntityEnum.inc"
 static const QString& getEntityTypeName(EntityType);
 static bool registerEntityType(EntityType,const char*,EntityTypeFactory);
 static EntityItemPointer constructEntityItem(EntityType,const EntityItemID&,const EntityItemProperties&);
 inline static QMap<EntityType,QString> _typeToNameMap;
 inline static QMap<QString,EntityType> _nameToTypeMap;
 inline static EntityTypeFactory _factories[NUM_TYPES];inline static bool _factoriesInitialized=false;
};
const QString ENTITY_TYPE_NAME_UNKNOWN="Unknown";
namespace entity {enum class HostType{DOMAIN,AVATAR,LOCAL};}
constexpr quint64 UNKNOWN_CREATED_TIME=0;

#include "AssetsEntityDefaults.inc"
// Store every field touched by the original bodies. Unused property families
// have no changed flags; unsupported changed transforms fail explicitly.
class GrabPropertyGroup {
public:
 bool grabbable{false},delegate{false};
 void setGrabbable(bool value){grabbable=value;}
 void setGrabDelegateToParent(bool value){delegate=value;}
#define ASSETS_UNUSED_GRAB(name,type) void set##name(type){qFatal("Unsupported host grab property");} bool name##Changed() const{return false;}
 ASSETS_UNUSED_GRAB(Triggerable,bool) ASSETS_UNUSED_GRAB(GrabFollowsController,bool)
 ASSETS_UNUSED_GRAB(GrabKinematic,bool) ASSETS_UNUSED_GRAB(Equippable,bool)
 ASSETS_UNUSED_GRAB(EquippableLeftPosition,const glm::vec3&) ASSETS_UNUSED_GRAB(EquippableRightPosition,const glm::vec3&)
 ASSETS_UNUSED_GRAB(EquippableLeftRotation,const glm::quat&) ASSETS_UNUSED_GRAB(EquippableRightRotation,const glm::quat&)
 ASSETS_UNUSED_GRAB(EquippableIndicatorURL,const QString&) ASSETS_UNUSED_GRAB(EquippableIndicatorScale,const glm::vec3&)
 ASSETS_UNUSED_GRAB(EquippableIndicatorOffset,const glm::vec3&)
#undef ASSETS_UNUSED_GRAB
};
struct AACube {};
class EntityItemProperties {
public:
 EntityTypes::EntityType type{EntityTypes::Unknown};entity::HostType host{entity::HostType::DOMAIN};
 QString name,url,textures,userData;QUuid editor;bool dynamic{ENTITY_ITEM_DEFAULT_DYNAMIC},collisionless{ENTITY_ITEM_DEFAULT_COLLISIONLESS},dimensionsInitialized{false};
 glm::vec3 position{ENTITY_ITEM_DEFAULT_POSITION},gravity{ENTITY_ITEM_DEFAULT_GRAVITY},dimensions{ENTITY_ITEM_DEFAULT_DIMENSIONS};
 bool changedPosition{false},changedUserData{false};ShapeType _shapeType{SHAPE_TYPE_NONE};bool _shapeTypeChanged{false};
 quint64 created{0},edited{0};GrabPropertyGroup grab;
 void setType(EntityTypes::EntityType value){type=value;}auto getType()const{return type;}
 void setName(const QString& value){name=value;}void setModelURL(const QString& value){url=value;}
 void setTextures(const QString& value){textures=value;}void setDynamic(bool value){dynamic=value;}
 void setCollisionless(bool value){collisionless=value;}void setUserData(const QString& value){userData=value;changedUserData=true;}
 bool userDataChanged()const{return changedUserData;}QString getUserData()const{return userData;}
 void setPosition(const glm::vec3& value){position=value;changedPosition=true;}auto getPosition()const{return position;}
 bool positionChanged()const{return changedPosition;}void setGravity(const glm::vec3& value){gravity=value;}
 void setEntityHostType(entity::HostType value){host=value;}auto getEntityHostType()const{return host;}
 void setOwningAvatarID(QUuid){qFatal("Avatar entity is outside this qualification");}
 void setLastEditedBy(QUuid value){editor=value;}QUuid getLastEditedBy()const{return editor;}
 void setLastEdited(quint64 value){edited=value;}quint64 getCreated()const{return created;}
 bool getScalesWithParent()const{return false;} // Explicit unparented-only transform endpoint.
 QUuid getParentID()const{return {};}int getParentJointIndex()const{return -1;}
 void setDimensionsInitialized(bool value){dimensionsInitialized=value;}bool dimensionsChanged()const{return false;}
 bool queryAACubeRelatedPropertyChanged()const{return false;}void setQueryAACube(AACube){qFatal("Unsupported host parent cube");}
 bool grabbingRelatedPropertyChanged()const{return false;}GrabPropertyGroup& getGrab(){return grab;}
 void setShapeTypeFromString(const QString&);
 void markAllChanged(){} // Factory-storage endpoint; not generated product flag qualification.
#define ASSETS_UNCHANGED(name,Type,initial) bool name##Changed()const{return false;} Type get##name()const{return initial;}
 // The original conversion calls lower-case getters differently from flags.
 bool localPositionChanged()const{return false;}glm::vec3 getLocalPosition()const{return {};}
 bool localRotationChanged()const{return false;}glm::quat getLocalRotation()const{return {};}
 bool rotationChanged()const{return false;}glm::quat getRotation()const{return {};}
 bool localVelocityChanged()const{return false;}glm::vec3 getLocalVelocity()const{return {};}
 bool velocityChanged()const{return false;}glm::vec3 getVelocity()const{return {};}
 bool localAngularVelocityChanged()const{return false;}glm::vec3 getLocalAngularVelocity()const{return {};}
 bool angularVelocityChanged()const{return false;}glm::vec3 getAngularVelocity()const{return {};}
 bool localDimensionsChanged()const{return false;}glm::vec3 getLocalDimensions()const{return dimensions;}
 glm::vec3 getDimensions()const{return dimensions;}
 void setRotation(const glm::quat&){qFatal("Unsupported host rotation edit");}
 void setVelocity(const glm::vec3&){qFatal("Unsupported host velocity edit");}
 void setAngularVelocity(const glm::vec3&){qFatal("Unsupported host angular velocity edit");}
 void setDimensions(const glm::vec3&){qFatal("Unsupported host dimensions edit");}
#undef ASSETS_UNCHANGED
};
struct SpatiallyNestable {
 template<class T>static T worldToLocal(const T& value,const QUuid& parent,int joint,bool scale,bool& success){assert(parent.isNull() && joint==-1 && !scale);success=true;return value;}
 template<class T>static T worldToLocalVelocity(const T&,const QUuid&,int,bool,bool&){qFatal("Unsupported host velocity transform");return {};}
 template<class T>static T worldToLocalAngularVelocity(const T&,const QUuid&,int,bool,bool&){qFatal("Unsupported host angular transform");return {};}
 template<class T>static T worldToLocalDimensions(const T&,const QUuid&,int,bool,bool&){qFatal("Unsupported host dimensions transform");return {};}
};
class Vec3 {public:glm::vec3 sum(const glm::vec3&,const glm::vec3&);glm::vec3 multiply(float,const glm::vec3&);glm::vec3 multiply(const glm::vec3&,float);glm::vec3 fromPolar(const glm::vec3&);glm::vec3 fromPolar(float,float);};
class Quat {public:glm::vec3 getForward(const glm::quat&);};
QVariantMap vec3ToQMap(const glm::vec3&);glm::vec3 qMapToVec3(const QVariant&);glm::quat qMapToQuat(const QVariant&);
void convertGrabUserDataToProperties(EntityItemProperties&);
// The API path has only legacy userData; new-style grab edits are unavailable.
inline void synchronizeGrabbableKey(const GrabPropertyGroup&,QJsonObject&,bool&){qFatal("Unsupported new-style host grab edit");}
inline void synchronizeEquipHotspot(const GrabPropertyGroup&,QJsonObject&,bool&){qFatal("Unsupported host equip edit");}
inline void synchronizeWearable(const GrabPropertyGroup&,QJsonObject&,bool&){qFatal("Unsupported host wearable edit");}
class EntityItem:public QObject {
public:
 EntityItemID id;EntityItemProperties properties;quint64 _created{0},_lastEdited{0},_lastUpdated{0},_lastSimulated{0},lastBroadcast{0};int priority{0};
 EntityItem(EntityItemID value,const EntityItemProperties& props):id(value),properties(props){}
 auto getEntityHostType()const{return properties.host;}auto getType()const{return properties.type;}
 auto getID()const{return id;}quint64 getCreated()const{return _created;}quint64 getLastEdited()const{return _lastEdited;}
 AACube getQueryAACube(bool& success){success=false;return {};}
 void setLastBroadcast(quint64 value){lastBroadcast=value;}void upgradeScriptSimulationPriority(int value){priority=value;}
 void recordCreationTime();
};
struct HostTreeElement {};
using EntityTreeElementPointer=std::shared_ptr<HostTreeElement>;
class EntityTree;
struct AddEntityOperator {EntityTree* tree;EntityItemPointer entity;AddEntityOperator(EntityTree* value,EntityItemPointer object):tree(value),entity(object){}};
class EntityTree {
public:
 QHash<QUuid,EntityItemPointer> objects;QHash<QUuid,EntityTreeElementPointer> elements;QMutex mutex;
 bool _serverlessDomain{false};int inserted{0},postAdded{0};
 bool getIsClient()const{return true;}EntityTree* getThisPointer(){return this;}
 EntityTreeElementPointer getContainingElement(const EntityItemID& id){return elements.value(id);}
 template<class F>void withWriteLock(F&& f){QMutexLocker lock(&mutex);f();}
 EntityItemPointer addEntity(const EntityItemID&,const EntityItemProperties&,bool=false,const bool=false);
 void recurseTreeWithOperator(AddEntityOperator* op){assert(op->tree==this && !objects.contains(op->entity->id));objects.insert(op->entity->id,op->entity);elements.insert(op->entity->id,std::make_shared<HostTreeElement>());++inserted;}
 void postAddEntity(EntityItemPointer item){assert(objects.value(item->id)==item);++postAdded;} // Octree/simulation endpoint, no renderer.
};
namespace PacketType {enum Value{EntityAdd};}
class EntityScriptingInterface {
public:
 struct {int addedEntityCount{0};} _activityTracking;
 std::shared_ptr<EntityTree> _entityTree{std::make_shared<EntityTree>()};overte::e2e::CreateLocalCreations _featureCreateLocalCreations;
 QVariantList packets;
#include "AssetsEntityInline.inc"
 QUuid addModelEntity(const QString&,const QString&,const QString&,const QString&,bool,bool,bool,const glm::vec3&,const glm::vec3&);
 QUuid addEntityInternal(const EntityItemProperties&,entity::HostType);
 bool addLocalEntityCopy(EntityItemProperties&,EntityItemID&,bool=false);
 void queueEntityMessage(PacketType::Value type,const QUuid& id,const EntityItemProperties& properties){assert(type==PacketType::EntityAdd);packets.append(QVariantMap{{"id",id.toString(QUuid::WithoutBraces)},{"url",properties.url},{"editor",properties.editor.toString(QUuid::WithoutBraces)}});}
};
class AssetsEntityBridge:public QObject {
 Q_OBJECT
public:
 EntityScriptingInterface api;QUuid returned;quint64 calls{0},sequence{0};QString run;
 Q_INVOKABLE QVariantMap forward(const QVariantMap& q){return vec3ToQMap(Quat().getForward(qMapToQuat(q)));}
 Q_INVOKABLE QVariantMap sum(const QVariantMap& a,const QVariantMap& b){return vec3ToQMap(Vec3().sum(qMapToVec3(a),qMapToVec3(b)));}
 Q_INVOKABLE QVariantMap multiply(const QJSValue& a,const QJSValue& b){return a.isNumber() ? vec3ToQMap(Vec3().multiply(a.toNumber(),qMapToVec3(b.toVariant()))) : vec3ToQMap(Vec3().multiply(qMapToVec3(a.toVariant()),b.toNumber()));}
 Q_INVOKABLE QVariantMap polar(float elevation,float azimuth){return vec3ToQMap(Vec3().fromPolar(elevation,azimuth));}
 Q_INVOKABLE QString addModel(const QString& name,const QString& url,const QString& textures,const QString& shape,bool dynamic,bool collisionless,bool grabbable,const QVariantMap& position,const QVariantMap& gravity){
  ++calls;returned=api.addModelEntity(name,url,textures,shape,dynamic,collisionless,grabbable,qMapToVec3(position),qMapToVec3(gravity));return returned.toString();
 }
 QJsonObject snapshot(const QString& requestedRun){
  assert(QThread::currentThread()==thread());if(run.isEmpty())run=requestedRun;assert(run==requestedRun);QJsonArray rows;
  if(api._entityTree)api._entityTree->withWriteLock([&]{for(auto entity:api._entityTree->objects){const auto& p=entity->properties;rows.append(QJsonObject{
   {"id",entity->id.toString(QUuid::WithoutBraces)},{"type",EntityTypes::getEntityTypeName(p.type)},{"name",p.name},{"modelUrl",p.url},
   {"shape",ShapeInfo::getNameForShapeType(p._shapeType)},{"dynamic",p.dynamic},{"collisionless",p.collisionless},{"userData",p.userData},
   {"grabbable",p.grab.grabbable},{"delegateToParent",p.grab.delegate},{"dimensionsInitialized",p.dimensionsInitialized},
   {"position",QJsonObject::fromVariantMap(vec3ToQMap(p.position))},{"gravity",QJsonObject::fromVariantMap(vec3ToQMap(p.gravity))},
   {"dimensions",QJsonObject::fromVariantMap(vec3ToQMap(p.dimensions))},{"editor",p.editor.toString(QUuid::WithoutBraces)},
   {"createdEpochUs",static_cast<double>(entity->_created)},{"lastEditedEpochUs",static_cast<double>(entity->_lastEdited)},
   {"lastBroadcastEpochUs",static_cast<double>(entity->lastBroadcast)},{"simulationPriority",entity->priority},{"ownerThread",entity->thread()==QThread::currentThread()}});}});
  return {{"assetsEntityHostVersion",1},{"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
   {"sequence",static_cast<double>(++sequence)},{"calls",static_cast<double>(calls)},{"returnedId",returned.toString(QUuid::WithoutBraces)},
   {"treeAttached",bool(api._entityTree)},{"inserted",api._entityTree ? api._entityTree->inserted : 0},{"postAdded",api._entityTree ? api._entityTree->postAdded : 0},
   {"objects",rows},{"packets",QJsonArray::fromVariantList(api.packets)},{"creations",QJsonObject::fromVariantMap(api._featureCreateLocalCreations.snapshot(run))}};
 }
};
