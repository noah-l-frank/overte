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
#include <array>
#include <ranges>
#include <algorithm>
#include <numeric>
#include <cassert>
#include <GLMHelpers.h>
#include <optional>
#include <memory>
#include <atomic>
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
namespace EntityTypes {enum EntityType{PolyVox,Other};}
namespace Simulation {enum {DIRTY_SHAPE=1,DIRTY_MASS=2,DIRTY_UPDATEABLE=4};}
enum class BillboardMode{NONE};
namespace BillboardModeHelpers {
inline glm::quat getBillboardRotation(const glm::vec3&,const glm::quat& value,BillboardMode mode,const glm::vec3&){if(mode!=BillboardMode::NONE){qFatal("Billboard variants are outside the owned PolyVox join");}return value;}
inline glm::vec3 getPrimaryViewFrustumPosition(){return {0,1,0};}
}
class EntityItem;class RenderablePolyVoxEntityItem;class VoxelVolume;class HostTree;
using EntityItemPointer=std::shared_ptr<EntityItem>;
using EntityTreePointer=std::shared_ptr<HostTree>;
struct EntityPropertyFlags {void setHasProperty(int){qFatal("Network property publication is outside the CPU source join");}};
constexpr int PROP_VOXEL_DATA=1;
struct EntityItemProperties {
 void setVoxelDataDirty(){qFatal("Network edits are outside the CPU source join");}
 void setLastEdited(quint64){qFatal("Network edits are outside the CPU source join");}
};
namespace PacketType {enum Type{EntityEdit};}
struct EntityEditPacketSender {void queueEditEntityMessage(PacketType::Type,EntityTreePointer,const QUuid&,const EntityItemProperties&){qFatal("Network edits are outside the CPU source join");}};
struct HostSimulation {virtual ~HostSimulation()=default;std::atomic<int> changes{0};void changeEntity(const EntityItemPointer&){++changes;}};
struct PhysicalEntitySimulation:HostSimulation {EntityEditPacketSender* getPacketSender(){qFatal("Physical simulation is outside the CPU source join");return nullptr;}};
using EntitySimulationPointer=std::shared_ptr<HostSimulation>;
using PhysicalEntitySimulationPointer=std::shared_ptr<PhysicalEntitySimulation>;
struct HostElement {EntityTreePointer getTree(){qFatal("A product tree element was not supplied by this host fixture");return {};}};
using EntityTreeElementPointer=std::shared_ptr<HostElement>;
class HostTree {
 std::recursive_mutex mutex;
public:
 QHash<QUuid,EntityItemPointer> objects;EntitySimulationPointer simulation{std::make_shared<HostSimulation>()};
 template<class F>void withReadLock(F&& f){std::lock_guard<std::recursive_mutex> guard(mutex);f();}
 template<class F>void withWriteLock(F&& f){std::lock_guard<std::recursive_mutex> guard(mutex);f();}
 EntityItemPointer findEntityByEntityItemID(const QUuid& id){return objects.value(id);}
 EntitySimulationPointer getSimulation(){return simulation;}
};
class EntityItem:public QObject,public std::enable_shared_from_this<EntityItem> {
public:
 QUuid id;std::weak_ptr<HostTree> tree;quint64 lastEdited{0},lastBroadcast{0};
 explicit EntityItem(const QUuid& value):id(value){}
 virtual EntityTypes::EntityType getType()const{return EntityTypes::PolyVox;}
 QUuid getID()const{return id;}QString getName()const{return "owned-original-polyvox";}
 EntityItemPointer getThisPointer(){return shared_from_this();}
 EntityTreePointer getTree(){return tree.lock();}EntityTreeElementPointer getElement(){return {};}
 void setLastEdited(quint64 value){lastEdited=value;}void setLastBroadcast(quint64 value){lastBroadcast=value;}
 EntityItemProperties getProperties(const EntityPropertyFlags&,bool){qFatal("Unbound domain properties cannot be published");return {};}
 void markDirtyFlags(int){}void somethingChangedNotification(){}
 void computeShapeInfo(ShapeInfo&){qFatal("The canonical nonempty mesh must not use an empty physics fallback");}
};
class PolyVoxEntityItem:public EntityItem {
public:
 using EntityItem::EntityItem;
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
 EntityTreePointer _entityTree;
 bool polyVoxWorker(QUuid,std::function<bool(PolyVoxEntityItem&)>);
 bool setVoxelsInCuboid(const QUuid&,const glm::vec3&,const glm::vec3&,int);
};
// Texture lookup must stay unused for this actual empty-texture fixture.
struct HostVoxelTexture:QObject {QUrl getURL()const{qFatal("No texture was admitted");return {};}};
using NetworkTexturePointer=QSharedPointer<HostVoxelTexture>;
struct TextureCache {NetworkTexturePointer getTexture(const QString&){qFatal("Texture acquisition is outside the owned empty-texture fixture");return {};}};
struct DependencyManager {template<class T>static T* get(){static T value;return &value;}};
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
class NativeCreateVoxelJoin:public QObject {
 Q_OBJECT
 EntityTreePointer tree{std::make_shared<HostTree>()};EntityScriptingInterface entitiesApi;
 overte::e2e::CreateEntityLifetimes entityLifetimes;
 std::weak_ptr<RenderablePolyVoxEntityItem> original;std::shared_ptr<render::entities::PolyVoxEntityRenderer> renderer;
 std::weak_ptr<graphics::Mesh> lastRendered;
 QTimer scheduler;QElapsedTimer sourceClock;QString run{QString(32,'a')};QUuid identifier;int sequence{0},mutationCalls{0},deleteCalls{0};
 bool keepRenderer{false},ignoreInput{false};QVariantList originals;quint64 traceBytes{0};
 struct TimerOriginal {QPointer<QTimer> timer;int invocations{0};};QMap<int,TimerOriginal> timers;int timerSequence{0};
 void drive();void render();bool settle(int milliseconds);QVariantMap snapshot(const QString&);
public:
 explicit NativeCreateVoxelJoin(QObject* parent=nullptr);
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
