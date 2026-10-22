// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original successful local insertion and atomic renderer observation bodies.
// Tree/factory/packet/PolyVox storage are declared host actor boundaries.
#include <QCoreApplication>
#include <QDateTime>
#include <QDebug>
#include <QVariantMap>
#include <QJsonDocument>
#include <QTextStream>
#include <QThread>
#include <cassert>
#include <array>
#include <memory>
#include <functional>
#include <mutex>
#include <glm/glm.hpp>
#define OVERTE_E2E_FEATURE_TESTS 1
#define ANDROID_APP_PICO_INTERFACE 1
#include "CreateLocalCreations.h"
using EntityItemID=QUuid;
namespace entity {enum class HostType{DOMAIN,AVATAR,LOCAL};}
namespace EntityTypes {enum Type{PolyVox,Shape};QString getEntityTypeName(Type value){return value==PolyVox ? "PolyVox" : "Shape";}}
struct AACube{};constexpr int VOLUNTEER_SIMULATION_PRIORITY=1;
quint64 usecTimestampNow(){return QDateTime::currentMSecsSinceEpoch()*1000;}
struct EntityItemProperties {
    QUuid editor{QString("22222222-2222-2222-2222-222222222222")};quint64 edited{0};
    bool queryAACubeRelatedPropertyChanged() const{return false;}void setQueryAACube(AACube){};
    void setLastEdited(quint64 value){edited=value;}QUuid getLastEditedBy() const{return editor;}
};
struct EntityItem {
    QUuid id;quint64 created{usecTimestampNow()};
    explicit EntityItem(QUuid value):id(value){}
    auto getEntityHostType() const{return entity::HostType::DOMAIN;}
    auto getType() const{return EntityTypes::PolyVox;}QUuid getID() const{return id;}
    quint64 getCreated() const{return created;}quint64 getLastEdited() const{return created;}
    AACube getQueryAACube(bool& success){success=true;return {};}
    void setLastBroadcast(quint64){}void upgradeScriptSimulationPriority(int value){assert(value==1);}
};
using EntityItemPointer=std::shared_ptr<EntityItem>;
struct EntityTree {
    bool fail{false};int inserted{0};EntityItemPointer last;
    template<class F>void withWriteLock(F&& function){function();}
    EntityItemPointer addEntity(const EntityItemID& id,EntityItemProperties&,bool){
        if(fail){return {};}++inserted;last=std::make_shared<EntityItem>(id);return last;}
};
#define qCDebug(...) qDebug()
struct EntityScriptingInterface {
    std::shared_ptr<EntityTree> _entityTree{std::make_shared<EntityTree>()};
    overte::e2e::CreateLocalCreations _featureCreateLocalCreations;
    bool addLocalEntityCopy(EntityItemProperties&,EntityItemID&,bool isClone=false);
};
#include "OriginalLocalInsertion.inc"
struct RenderablePolyVoxEntityItem {
    enum class PolyVoxState{Ready,Other};
    PolyVoxState _state{PolyVoxState::Ready};bool _volDataDirty{false},_voxelDataDirty{false};
    struct Mesh {int getNumVertices() const{return 64;}int getNumIndices() const{return 96;}};
    bool _meshReady{true};std::shared_ptr<Mesh> _mesh{std::make_shared<Mesh>()};
    glm::vec3 _voxelVolumeSize{8.0f};int _voxelSurfaceStyle{3};QByteArray _voxelData{"actual-original-compressed-bytes"};
    std::unique_ptr<std::array<uint8_t,512>> _volData{std::make_unique<std::array<uint8_t,512>>()};
    mutable std::recursive_mutex mutex;mutable int locked{0};mutable int reads{0};
    template<class F>void withReadLock(F&& function) const{std::lock_guard<std::recursive_mutex> lock(mutex);++locked;function();--locked;}
    uint8_t getVoxelInternal(const glm::ivec3& point) const{assert(locked==1);++reads;return _volData->at(point.z*64+point.y*8+point.x);}
    QVariantMap featureCreateVoxels(const std::function<void(const std::shared_ptr<void>&)>& observed=std::function<void(const std::shared_ptr<void>&)>()) const;
};
#include "OriginalAtomicVoxels.inc"
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);const auto run=QString(32,'a');EntityScriptingInterface target;RenderablePolyVoxEntityItem volume;
    EntityItemProperties properties;EntityItemID id;
    if(!app.arguments().contains("--testScript")){
        assert(target._featureCreateLocalCreations.snapshot(run).isEmpty());assert(volume.featureCreateVoxels().isEmpty());return 0;}
    assert(target.addLocalEntityCopy(properties,id)); // Before observation, no retroactive adoption.
    const auto initial=target._featureCreateLocalCreations.snapshot(run);assert(initial.value("events").toList().isEmpty());
    assert(target.addLocalEntityCopy(properties,id));const auto original=id;
    auto source=target._featureCreateLocalCreations.snapshot(run);auto events=source.value("events").toList();assert(events.size()==1);
    auto row=events.first().toMap();assert(row.value("id")==id.toString(QUuid::WithoutBraces));
    assert(row.value("type")==QVariant("PolyVox") && row.value("createdEpochUs")==QVariant(target._entityTree->last->getCreated()));
    assert(row.value("sessionId")==properties.editor.toString(QUuid::WithoutBraces));
    target._entityTree->fail=true;assert(!target.addLocalEntityCopy(properties,id));assert(id!=original);
    assert(target._featureCreateLocalCreations.snapshot(run)==source); // Failed original Tree insertion is not creation.
    const auto baseline2=target._featureCreateLocalCreations.snapshot(QString(32,'b'));assert(baseline2.value("events").toList().isEmpty());
    target._entityTree->fail=false;assert(target.addLocalEntityCopy(properties,id));
    assert(target._featureCreateLocalCreations.snapshot(run).value("events").toList().size()==2);
    assert(target._featureCreateLocalCreations.snapshot(QString(32,'b')).value("events").toList().size()==1);
    for(int z=2;z<6;++z){for(int y=2;y<6;++y){for(int x=2;x<6;++x){volume._volData->at(z*64+y*8+x)=255;}}}
    const auto actual=volume.featureCreateVoxels();assert(actual.value("ready").toBool() && actual.value("nonzero").toInt()==64);
    assert(volume.reads==512 && volume.locked==0);
    assert(QByteArray::fromBase64(actual.value("valuesBase64").toByteArray()).size()==512);
    assert(QByteArray::fromBase64(actual.value("dataBase64").toByteArray())==volume._voxelData);
    assert(actual.value("meshReady").toBool() && actual.value("vertices").toInt()==64 && actual.value("indices").toInt()==96);
    volume._meshReady=false;assert(!volume.featureCreateVoxels().value("meshReady").toBool());
    volume._meshReady=true;const auto originalMesh=volume._mesh;volume._mesh.reset();
    const auto missingMesh=volume.featureCreateVoxels();assert(!missingMesh.value("meshReady").toBool());
    assert(missingMesh.value("vertices").toInt()==0 && missingMesh.value("indices").toInt()==0);volume._mesh=originalMesh;
    volume._volDataDirty=true;volume.reads=0;const auto dirty=volume.featureCreateVoxels();assert(!dirty.value("ready").toBool());
    assert(dirty.value("valuesBase64").toString().isEmpty() && volume.reads==0);
    volume._volDataDirty=false;volume._voxelDataDirty=true;assert(!volume.featureCreateVoxels().value("ready").toBool());
    volume._voxelDataDirty=false;volume._state=RenderablePolyVoxEntityItem::PolyVoxState::Other;
    assert(!volume.featureCreateVoxels().value("ready").toBool());volume._state=RenderablePolyVoxEntityItem::PolyVoxState::Ready;
    volume._voxelVolumeSize={64,64,64};volume.reads=0;assert(volume.featureCreateVoxels().value("valuesBase64").toString().isEmpty() && volume.reads==0);
    volume._voxelVolumeSize={8,8,8};volume._voxelData=QByteArray(8193,'x');assert(volume.featureCreateVoxels().isEmpty());
    // Native collector limits refuse ambiguity without dropping old ownership.
    overte::e2e::CreateLocalCreations bounded;assert(!bounded.snapshot(run).isEmpty());
    for(int index=0;index<128;++index){bounded.inserted(QUuid::createUuid(),"Shape",usecTimestampNow(),properties.editor,"domain");}
    assert(bounded.snapshot(run).value("events").toList().size()==128);
    bounded.inserted(QUuid::createUuid(),"Shape",usecTimestampNow(),properties.editor,"domain");assert(bounded.snapshot(run).isEmpty());
    QTextStream(stdout)<<QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact)<<'\n';
    QTextStream(stdout)<<QJsonDocument::fromVariant(actual).toJson(QJsonDocument::Compact)<<'\n';
}
