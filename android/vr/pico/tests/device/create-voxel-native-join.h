// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Current original volume/mesh/state-machine/collector sources are included by
// the CPP. Entity/domain/scene and SDK delivery stay named host boundaries.
#include <QObject>
#include <QPointer>
#include <QJsonObject>
#include <QJsonArray>
#include <QVariantMap>
#include <QJSValue>
#include <QTimer>
#include <QElapsedTimer>
#include <QDateTime>
#include <QThreadPool>
#include <QtConcurrent/QtConcurrentRun>
#include <QDataStream>
#include <QTest>
#include <QLoggingCategory>
#include <QSemaphore>
#include <QCryptographicHash>
#include <QSet>
#include <QVector>
#include <AACube.h>
#include "tests/device/native/ChatDomainSession.h"
#include "tests/device/native/CreateLocalCreations.h"
#include "OriginalCreateInsertionConstants.inc"
#include <array>
#include <ranges>
#include <algorithm>
#include <numeric>
#include <cassert>
#include <GLMHelpers.h>
#include <optional>
#include <memory>
#include <atomic>
#include <type_traits>
#include <mutex>
#include <graphics/Geometry.h>
#include <ShapeInfo.h>
#include <glm/gtx/transform.hpp>
#include <glm/gtx/component_wise.hpp>
#include "tests/device/native/CreatePolyvoxResources.h"
using glm::vec3;using glm::vec4;using glm::ivec3;
using EntityItemID=QUuid;
using OctreeElementPointer=std::shared_ptr<void>;
Q_DECLARE_LOGGING_CATEGORY(entitiesrenderer)
Q_DECLARE_LOGGING_CATEGORY(entities)
namespace entity {enum class HostType:uint8_t{DOMAIN,AVATAR,LOCAL};}
namespace EntityTypes {
enum EntityType{Unknown,Model,PolyVox,Shape,Box,Sphere};
inline QString getEntityTypeName(EntityType type){if(type==PolyVox){return "PolyVox";}if(type==Unknown){return "Unknown";}qFatal("A foreign entity type was not admitted");}
}
enum class BillboardMode{NONE};
namespace BillboardModeHelpers {
inline glm::quat getBillboardRotation(const glm::vec3&,const glm::quat& value,BillboardMode mode,const glm::vec3&){if(mode!=BillboardMode::NONE){qFatal("Billboard variants are outside the owned PolyVox join");}return value;}
inline glm::vec3 getPrimaryViewFrustumPosition(){return {0,1,0};}
}
class EntityItem;class RenderablePolyVoxEntityItem;class VoxelVolume;class EntityTree;
using EntityItemPointer=std::shared_ptr<EntityItem>;
using EntityTreePointer=std::shared_ptr<EntityTree>;
struct EntityPropertyFlags {void setHasProperty(int){qFatal("Network property publication is outside the CPU source join");}};
constexpr int PROP_VOXEL_DATA=1;
// Explicit property facade for the isolated entity/tree fixture. Mutable
// entity metadata is copied from the actual held object. Renderer statistics
// remain unobserved zeroes; no expected Mesh/voxel result is supplied here.
struct EntityItemProperties {
 EntityTypes::EntityType type{EntityTypes::Unknown};entity::HostType host{entity::HostType::DOMAIN};
 QString name;glm::vec3 position{0,1,-2},dimensions{1},natural{0};glm::quat rotation{1,0,0,0};
 bool locked{false},visible{true};quint64 created{UNKNOWN_CREATED_TIME},edited{0};
 QUuid lastEditedBy{QStringLiteral("22222222-2222-2222-2222-222222222222")};
 auto getType()const{return type;}auto getEntityHostType()const{return host;}
 QString getName()const{return name;}QString getModelURL()const{return {};}QString getTextures()const{return {};}
 QString getShapeAsString()const{qFatal("Shape serialization is outside the owned PolyVox fixture");}
 auto getPosition()const{return position;}auto getDimensions()const{return dimensions;}auto getNaturalDimensions()const{return natural;}
 auto getRotation()const{return rotation;}QUuid getParentID()const{return {};}
 bool getVisible()const{return visible;}bool getLocked()const{return locked;}
 auto getCreated()const{return created;}auto getLastEdited()const{return edited;}auto getLastEditedBy()const{return lastEditedBy;}
 QVariantMap getTextureNames()const{return {};}
 qulonglong getRenderInfoVertexCount()const{return 0;}int getRenderInfoTextureCount()const{return 0;}
 qulonglong getRenderInfoTextureSize()const{return 0;}int getRenderInfoDrawCalls()const{return 0;}
 bool queryAACubeRelatedPropertyChanged()const{return false;}
 void setQueryAACube(const AACube&){qFatal("Parented query bounds were not admitted");}
 void setVoxelDataDirty(){qFatal("Network edits are outside the CPU source join");}
 void setLastEdited(quint64 value){edited=value;}
};
namespace EntityTypes {EntityItemPointer constructEntityItem(EntityType,const EntityItemID&,const EntityItemProperties&);}
struct AddEntityOperator {
 EntityTreePointer tree;EntityItemPointer entity;
 AddEntityOperator(const EntityTreePointer& tree,const EntityItemPointer& entity):tree(tree),entity(entity){}
};

namespace PacketType {enum Type{EntityEdit};}
struct EntityEditPacketSender {void queueEditEntityMessage(PacketType::Type,EntityTreePointer,const QUuid&,const EntityItemProperties&){qFatal("Network edits are outside the CPU source join");}};
struct HostSimulation {virtual ~HostSimulation()=default;std::atomic<int> changes{0};void changeEntity(const EntityItemPointer&){++changes;}};
struct PhysicalEntitySimulation:HostSimulation {EntityEditPacketSender* getPacketSender(){qFatal("Physical simulation is outside the CPU source join");return nullptr;}};
using EntitySimulationPointer=std::shared_ptr<HostSimulation>;
using PhysicalEntitySimulationPointer=std::shared_ptr<PhysicalEntitySimulation>;
struct HostElement {EntityTreePointer getTree(){qFatal("A product tree element was not supplied by this host fixture");return {};}};
using EntityTreeElementPointer=std::shared_ptr<HostElement>;
class EntityTree:public std::enable_shared_from_this<EntityTree> {
 std::recursive_mutex mutex;
public:
 QHash<QUuid,EntityItemPointer> objects;EntitySimulationPointer simulation{std::make_shared<HostSimulation>()};
 template<class F>void withReadLock(F&& f){std::lock_guard<std::recursive_mutex> guard(mutex);f();}
 template<class F>void withWriteLock(F&& f){std::lock_guard<std::recursive_mutex> guard(mutex);f();}
 EntityItemPointer findEntityByEntityItemID(const QUuid& id){return objects.value(id);}
 EntitySimulationPointer getSimulation(){return simulation;}
 bool _serverlessDomain{false};bool getIsClient()const{return true;}
 EntityTreePointer getThisPointer(){return shared_from_this();}
 EntityTreeElementPointer getContainingElement(const EntityItemID& id){return objects.contains(id)?std::make_shared<HostElement>():nullptr;}
 EntityItemPointer addEntity(const EntityItemID&,const EntityItemProperties&,bool isClone=false,const bool isImport=false);
 void recurseTreeWithOperator(AddEntityOperator*);void postAddEntity(const EntityItemPointer&);

};
class EntityItem:public QObject,public std::enable_shared_from_this<EntityItem> {
public:
 QUuid id;std::weak_ptr<EntityTree> tree;QString name;
 quint64 _created{UNKNOWN_CREATED_TIME},_lastEdited{0},_lastUpdated{0},_lastSimulated{0},lastBroadcast{0};
 bool visible{true};QUuid editedBy;entity::HostType host{entity::HostType::DOMAIN};mutable std::mutex metadataMutex;
 uint8_t priority{0};

 explicit EntityItem(const QUuid& value):id(value){}
 virtual EntityTypes::EntityType getType()const{return EntityTypes::PolyVox;}
 QUuid getID()const{return id;}QString getName()const{return name;}
 void recordCreationTime();quint64 getCreated()const{return _created;}
 quint64 getLastEdited()const{std::lock_guard<std::mutex> guard(metadataMutex);return _lastEdited;}
 entity::HostType getEntityHostType()const{return host;}
 void upgradeScriptSimulationPriority(uint8_t value){priority=value;}
 AACube getQueryAACube(bool&)const{qFatal("Parented query bounds were not admitted");}
#include "OriginalCreateEntityInline.inc"

 EntityItemPointer getThisPointer(){return shared_from_this();}
 EntityTreePointer getTree(){return tree.lock();}EntityTreeElementPointer getElement(){return {};}
 void setLastEdited(quint64 value){std::lock_guard<std::mutex> guard(metadataMutex);_lastEdited=value;}void setLastBroadcast(quint64 value){lastBroadcast=value;}
 EntityItemProperties getProperties(const EntityPropertyFlags&,bool){qFatal("Unbound domain properties cannot be published");return {};}
 void markDirtyFlags(int){}void somethingChangedNotification(){}
 void computeShapeInfo(ShapeInfo&){qFatal("The canonical nonempty mesh must not use an empty physics fallback");}
};
class PolyVoxEntityItem:public EntityItem {
public:
 using EntityItem::EntityItem;
#include "OriginalCreatePolyvoxBaseInline.inc"
 enum PolyVoxSurfaceStyle{SURFACE_MARCHING_CUBES,SURFACE_CUBIC,SURFACE_EDGED_CUBIC,SURFACE_EDGED_MARCHING_CUBES};
 static constexpr float MAX_VOXEL_DIMENSION=128;
 glm::vec3 _voxelVolumeSize{8.0f},_registrationPoint{.5f};int _voxelSurfaceStyle{3};
 glm::vec3 position{0,1,-2},dimensions{1};glm::quat orientation{1,0,0,0};
 bool _locked{false},_collisionless{false};int _flags{0};QByteArray _voxelData;
 mutable std::recursive_mutex volumeMutex;
 template<class F>void withReadLock(F&& f)const{std::lock_guard<std::recursive_mutex> guard(volumeMutex);f();}
 template<class F>void withWriteLock(F&& f){std::lock_guard<std::recursive_mutex> guard(volumeMutex);f();}
 static bool isEdged(PolyVoxSurfaceStyle);bool isEdged()const;
 glm::vec3 getSurfacePositionAdjustment()const;glm::mat4 voxelToLocalMatrix()const;
 glm::mat4 voxelToWorldMatrix(bool=false)const;glm::mat4 worldToVoxelMatrix(bool=false)const;
 glm::vec3 worldCoordsToVoxelCoords(const glm::vec3&)const;
 glm::vec3 getScaledDimensions()const{return dimensions;}
 glm::vec3 getCenterPosition(bool& success)const{success=true;return position;}
 glm::vec3 getWorldPosition(bool& success)const{success=true;return position;}
 glm::vec3 getWorldPosition()const{return position;}
 glm::quat getWorldOrientation()const{return orientation;}glm::quat getLocalOrientation()const{return orientation;}
 BillboardMode getBillboardMode()const{return BillboardMode::NONE;}
 glm::vec3 getVoxelVolumeSize()const{return _voxelVolumeSize;}
 QString getXTextureURL()const{return {};};QString getYTextureURL()const{return {};};QString getZTextureURL()const{return {};};
 virtual bool setCuboid(const glm::vec3&,const glm::vec3&,int)=0;
};
enum class PolyVoxState{Ready,Uncompressing,UncompressingFinished,BakingMesh,BakingMeshFinished,BakingMeshNoCompress,BakingMeshNoCompressFinished,Compressing,CompressingFinished,BakingShape,BakingShapeFinished};
struct UnknownNeighbor {bool isInvalidID()const{return true;}};
class RenderablePolyVoxEntityItem:public PolyVoxEntityItem {
public:
 explicit RenderablePolyVoxEntityItem(const EntityItemID&);
 ~RenderablePolyVoxEntityItem()override;void initializePolyVox();
 static EntityItemPointer factory(const EntityItemID&,const EntityItemProperties&);void setProperties(const EntityItemProperties&);
 std::shared_ptr<VoxelVolume> _volData;int _onCount{0};
 bool _meshReady{false},_volDataDirty{false},_voxelDataDirty{false},_shapeReady{false},_updateNeeded{true};
 bool _neighborXNeedsUpdate{false},_neighborYNeedsUpdate{false},_neighborZNeedsUpdate{false};
 bool _updateFromNeighborXEdge{false},_updateFromNeighborYEdge{false},_updateFromNeighborZEdge{false};
 PolyVoxState _state{PolyVoxState::Ready};graphics::MeshPointer _mesh;ShapeInfo _shapeInfo;
 UnknownNeighbor _xPNeighborID,_yPNeighborID,_zPNeighborID;
 void changeUpdates(bool);void startUpdates();void stopUpdates();void update(const quint64&);
 void setVoxelVolumeSize(const glm::vec3&);bool setCuboid(const glm::vec3&,const glm::vec3&,int)override;
 bool setVoxelInternal(const glm::ivec3&,uint8_t);uint8_t getVoxelInternal(const glm::ivec3&)const;
 void setVoxelMarkNeighbors(int,int,int,uint8_t);bool updateOnCount(const glm::ivec3&,uint8_t);
 QByteArray volDataToArray(quint16,quint16,quint16)const;
 void forEachVoxelValue(const glm::ivec3&,std::function<void(const glm::ivec3&,uint8_t)>);
 void uncompressVolumeData();void setVoxelsFromData(QByteArray,quint16,quint16,quint16);
 void compressVolumeDataAndSendEditPacket();void compressVolumeDataFinished(const QByteArray&);
 void recomputeMesh();void setMesh(graphics::MeshPointer);void computeShapeInfoWorker();void setCollisionPoints(ShapeInfo::PointCollection,AABox);
 bool isVoxelDataReady()const;
 QVariantMap featureCreateVoxels(const std::function<void(const std::shared_ptr<void>&)>& observed = {})const;
 bool findDetailedRayIntersection(const glm::vec3&,const glm::vec3&,const glm::vec3&,OctreeElementPointer&,float&,BoxFace&,glm::vec3&,QVariantMap&,bool)const;
 void cacheNeighbors(){}void tellNeighborsToRecopyEdges(bool force){if(force || _neighborXNeedsUpdate || _neighborYNeedsUpdate || _neighborZNeedsUpdate){_neighborXNeedsUpdate=_neighborYNeedsUpdate=_neighborZNeedsUpdate=false;}}
 void copyUpperEdgesFromNeighbors(){if(_voxelSurfaceStyle!=SURFACE_EDGED_MARCHING_CUBES){qFatal("Only the original isolated edged fixture is admitted");}}
};
class EntityScriptingInterface {
public:
 EntityTreePointer _entityTree;overte::e2e::CreateLocalCreations _featureCreateLocalCreations;
 QVariantMap featureCreateLocalCreations(const QString& run){return _featureCreateLocalCreations.snapshot(run);}
 EntityTreePointer getEntityTree(){return _entityTree;}
 EntityItemProperties getEntityProperties(const QUuid&);QVector<QUuid> findEntities(const glm::vec3&,float,int);
 bool isLoaded(const QUuid&);bool isVoxelDataReady(const QUuid&);bool addLocalEntityCopy(EntityItemProperties&,EntityItemID&,bool isClone=false);
 bool polyVoxWorker(QUuid,std::function<bool(PolyVoxEntityItem&)>);
 bool setVoxelsInCuboid(const QUuid&,const glm::vec3&,const glm::vec3&,int);
};
// Texture lookup must stay unused for this actual empty-texture fixture.
struct HostVoxelTexture:QObject {QUrl getURL()const{qFatal("No texture was admitted");return {};}};
using NetworkTexturePointer=QSharedPointer<HostVoxelTexture>;
struct TextureCache {NetworkTexturePointer getTexture(const QString&){qFatal("Texture acquisition is outside the owned empty-texture fixture");return {};}};
struct Avatar {glm::vec3 getWorldPosition()const{return {0,1,0};}glm::quat getWorldOrientation()const{return {1,0,0,0};}};
struct AvatarManager {Avatar* getMyAvatar(){return &avatar;}Avatar avatar;};
struct DomainHandler {
 QUuid id{QStringLiteral("11111111-1111-1111-1111-111111111111")};bool connected{true};overte::e2e::ChatDomainSession observer;
 DomainHandler(){observer.changed(id,connected,true);}
 QVariantMap featureChatSession(const QString& run){return observer.snapshot(run);}QUuid getUUID()const{return id;}
 bool isConnected()const{return connected;}
};
struct NodeList {
 DomainHandler domain;bool canRez{true},canRezTmp{false};
 DomainHandler& getDomainHandler(){return domain;}
 QUuid getSessionUUID()const{return QUuid(QStringLiteral("22222222-2222-2222-2222-222222222222"));}
 bool getThisNodeCanRez()const{return canRez;}bool getThisNodeCanRezTmp()const{return canRezTmp;}
};
struct PickFilter {enum class FlagBit{DOMAIN_ENTITIES,COARSE};static int getBitMask(FlagBit bit){return bit==FlagBit::DOMAIN_ENTITIES?1:2;}};
struct DependencyManager {
 inline static EntityScriptingInterface* activeEntities{nullptr};
 template<class T>static bool isSet(){if constexpr(std::is_same_v<T,EntityScriptingInterface>){return activeEntities!=nullptr;}return true;}
 template<class T>static T* get(){if constexpr(std::is_same_v<T,EntityScriptingInterface>){return activeEntities;}else{static T value;return &value;}}
};
namespace render::entities {
class PolyVoxEntityRenderer:public QObject,public std::enable_shared_from_this<PolyVoxEntityRenderer> {
public:
 using TypedEntityPointer=std::shared_ptr<RenderablePolyVoxEntityItem>;
 TypedEntityPointer entityOwner;graphics::MeshPointer _mesh;
 struct Params {glm::vec4 actual;void setSubData(int offset,const glm::vec4& value){if(offset){qFatal("Unknown original params offset");}actual=value;}};
 std::unique_ptr<Params> _params{std::make_unique<Params>()};
 glm::mat4 _lastVoxelToLocalMatrix;glm::vec3 _position,_lastVoxelVolumeSize;glm::quat _orientation;
 std::array<NetworkTexturePointer,3> _xyzTextures;int materialUpdates{0};
 void updateMaterials(){++materialUpdates;}
 void doRenderUpdateAsynchronousTyped(const TypedEntityPointer&);
};
}
#include "tests/device/native/CreateEntityLifetimes.h"
struct Lifecycle {QVariantMap snapshot(){return {{"hostQtLifecycleEndpoint",true}};}};
class TestScriptingInterface:public QObject {
public:
 QVariantMap featureCreateEntities(const QVariantMap&);
 QString _testResultsLocation{QStringLiteral("/private-owned-create-source")};
 QString _featureObservationInstance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
 std::shared_ptr<Lifecycle> _featureLifecycle{std::make_shared<Lifecycle>()};
 quint64 _featureCreateEntitiesSequence{0};
 QHash<QString,QVariantMap> _featureCreateEntitiesCommands,_featureCreateEntitiesResults;
 QHash<QString,QSet<QUuid>> _featureCreateEntityIds;
 std::shared_ptr<overte::e2e::CreateEntityLifetimes> _featureCreateEntityLifetimes;
};
class NativeCreateVoxelJoin:public QObject {
 Q_OBJECT
 EntityTreePointer tree{std::make_shared<EntityTree>()};EntityScriptingInterface entitiesApi;
 TestScriptingInterface entitySource;
 std::weak_ptr<RenderablePolyVoxEntityItem> original;std::shared_ptr<render::entities::PolyVoxEntityRenderer> renderer;
 std::weak_ptr<graphics::Mesh> lastRendered;
 QTimer scheduler;QElapsedTimer sourceClock;QString run{QString(32,'a')};QUuid identifier;int sequence{0},mutationCalls{0},deleteCalls{0};
 bool keepRenderer{false},ignoreInput{false};QVariantList originals;quint64 traceBytes{0};
 struct TimerOriginal {QPointer<QTimer> timer;int invocations{0};};QMap<int,TimerOriginal> timers;int timerSequence{0};
 void drive();void render();bool settle(int milliseconds);QVariantMap snapshot(const QString&);
public:
 explicit NativeCreateVoxelJoin(QObject* parent=nullptr);
 ~NativeCreateVoxelJoin()override{if(DependencyManager::activeEntities==&entitiesApi){DependencyManager::activeEntities=nullptr;}}
 Q_INVOKABLE QString entityId()const{return identifier.toString(QUuid::WithoutBraces);}
 Q_INVOKABLE QVariantMap properties(const QString&);
 Q_INVOKABLE QVariantMap voxelCoords(const QString&,const QVariantMap&);
 Q_INVOKABLE QVariantMap ray(const QVariantMap&,const QVariantMap&);
 Q_INVOKABLE bool setCuboid(const QString&,const QVariantMap&,const QVariantMap&,int);
 Q_INVOKABLE bool ready(const QString&);
 Q_INVOKABLE QVariantList values();
 Q_INVOKABLE int registerTimer(const QJSValue&,int);
 Q_INVOKABLE void clearTimer(int);
 Q_INVOKABLE bool waitForTimers();
 Q_INVOKABLE bool remove(const QString&);
 Q_INVOKABLE QVariantMap observe(const QString& phase){return snapshot(phase);}
 Q_INVOKABLE QVariantList history()const{return originals;}
 Q_INVOKABLE bool ignored()const{return ignoreInput;}
};
