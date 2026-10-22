// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Whole original asynchronous renderer update + passive lifetime collector.
// Mesh/GPU/resource/cache/tree boundaries here are explicit host actors.
#include <QCoreApplication>
#include <QJsonDocument>
#include <QTextStream>
#include <QEvent>
#include <QUrl>
#include <array>
#include <cassert>
#include <thread>
#include <glm/glm.hpp>
#include <glm/gtc/quaternion.hpp>
#define OVERTE_E2E_FEATURE_TESTS 1
#define ANDROID_APP_PICO_INTERFACE 1
#include "CreatePolyvoxResources.h"
using glm::vec4;
namespace graphics {struct Mesh{struct Index{bool _buffer{true};};Index getIndexBuffer()const{return {};}};using MeshPointer=std::shared_ptr<Mesh>;}
struct Texture:QObject {QUrl url;explicit Texture(const QUrl& value):url(value){}QUrl getURL()const{return url;}};
using NetworkTexturePointer=QSharedPointer<Texture>;
struct TextureCache {int calls{0};QList<NetworkTexturePointer> cached;
    NetworkTexturePointer getTexture(const QString& url){++calls;auto value=NetworkTexturePointer(new Texture(QUrl(url)),[](Texture* p){p->deleteLater();});// Original ResourceCache::getResource moves new resources to qApp thread.
        value->moveToThread(QCoreApplication::instance()->thread());cached.append(value);return value;}};
struct DependencyManager{template<class T>static T* get(){static T value;return &value;}};
namespace BillboardMode {enum Mode{NONE};}
struct Volume {graphics::MeshPointer _mesh{std::make_shared<graphics::Mesh>()};QUuid id{QUuid::createUuid()};
    glm::mat4 voxelToLocalMatrix(){return glm::mat4(1);}glm::vec3 getCenterPosition(bool& success){success=true;return {0,1,-2};}
    auto getBillboardMode(){return BillboardMode::NONE;}glm::quat getWorldOrientation(){return {1,0,0,0};}glm::quat getLocalOrientation(){return {1,0,0,0};}
    glm::vec3 getVoxelVolumeSize(){return {8,8,8};}QUuid getID(){return id;}
    QString getXTextureURL(){return "qrc:/original/x.png";}QString getYTextureURL(){return "qrc:/original/y.png";}QString getZTextureURL(){return {};}
    template<class F>void withReadLock(F&& function){function();}
};
namespace render {namespace entities {
struct PolyVoxEntityRenderer:QObject,std::enable_shared_from_this<PolyVoxEntityRenderer>{
    using TypedEntityPointer=std::shared_ptr<Volume>;graphics::MeshPointer _mesh;
    struct Params{void setSubData(int,const glm::vec4&) {}};std::unique_ptr<Params> _params{std::make_unique<Params>()};
    glm::mat4 _lastVoxelToLocalMatrix;glm::vec3 _position,_lastVoxelVolumeSize;glm::quat _orientation;
    std::array<NetworkTexturePointer,3> _xyzTextures;int updates{0};void updateMaterials(){++updates;}
    void doRenderUpdateAsynchronousTyped(const TypedEntityPointer& entity);
};
#include "OriginalPolyvoxRenderUpdate.inc"
}}
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);auto& source=overte::e2e::CreatePolyvoxResources::get();const QString run(32,'a');
    if(!app.arguments().contains("--testScript")){assert(!source.arm(run));return 0;}
    assert(source.arm(run));auto entity=std::make_shared<Volume>();assert(source.entity(run,entity->id,entity->_mesh));
    auto renderer=std::shared_ptr<render::entities::PolyVoxEntityRenderer>(new render::entities::PolyVoxEntityRenderer(),[](auto* p){p->deleteLater();});
    auto output=[&]{const auto value=source.snapshot(run);assert(!value.isEmpty());QTextStream(stdout)<<QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact)<<'\n';return value;};
    auto before=output();assert(before.value("renderers").toList().isEmpty());
    std::thread originalRender([&]{renderer->doRenderUpdateAsynchronousTyped(entity);});originalRender.join();
    assert(renderer->updates==1 && DependencyManager::get<TextureCache>()->calls==2);auto first=output();
    assert(first.value("meshes").toList().size()==1 && first.value("textures").toList().size()==2);
    auto oldMesh=entity->_mesh;entity->_mesh=std::make_shared<graphics::Mesh>();assert(source.entity(run,entity->id,entity->_mesh));
    std::thread changedRender([&]{renderer->doRenderUpdateAsynchronousTyped(entity);});changedRender.join();
    assert(DependencyManager::get<TextureCache>()->calls==2);auto changed=output();assert(changed.value("meshes").toList().size()==2);
    entity.reset();oldMesh.reset();DependencyManager::get<TextureCache>()->cached.clear();
    auto retained=output();int alive=0;for(const auto& row:retained.value("meshes").toList()){alive+=row.toMap().value("alive").toBool();}assert(alive==1);
    renderer.reset();const auto deferred=output();assert(deferred.value("renderers").toList().first().toMap().value("alive").toBool());
    QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    const auto dead=output();for(const auto& key:{"meshes","renderers","textures"}){for(const auto& row:dead.value(key).toList()){assert(!row.toMap().value("alive").toBool());}}
}
