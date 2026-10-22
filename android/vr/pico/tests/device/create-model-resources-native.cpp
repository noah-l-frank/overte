// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original observer/getter, substituted entity/model/material/network actor.
#include <QCoreApplication>
#include <QDateTime>
#include <QHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QSemaphore>
#include <QSet>
#include <QTextStream>
#include <QThread>
#include <QUrl>
#include <QUuid>
#include <atomic>
#include <cassert>
#include <memory>
#include <thread>
#include <unordered_map>
#include <vector>
#define OVERTE_E2E_FEATURE_TESTS 1
#define ANDROID_APP_PICO_INTERFACE 1
struct Resource;
struct Cache {
    QSharedPointer<Resource> stored;
    void addUnusedResource(const QSharedPointer<Resource>& value){stored=value;}
    void removeResource(const QUrl&,int,int){}void resetTotalResourceCounter(){}
};
struct Resource:QObject {
    Cache* _cache=nullptr;QWeakPointer<Resource> self;
    void allReferencesCleared();void deleter(){allReferencesCleared();}
    void setSelf(const QSharedPointer<Resource>& value){self=value;}void reinsert(){}
    bool isCacheable()const{return true;}QUrl getURL()const{return QUrl();}int getExtraHash(){return 0;}int getBytes(){return 0;}
};
#include "OriginalResourceRetirement.inc"
struct NetworkTexture:Resource {
    QUrl url;bool loaded=true,failed=false;int reads=0;
    const QUrl& getURL(){assert(thread()==QThread::currentThread());++reads;return url;}
    bool isLoaded(){assert(thread()==QThread::currentThread());return loaded;}
    bool isFailed(){assert(thread()==QThread::currentThread());return failed;}
};
struct NetworkMaterial {
    enum MapChannel {ALBEDO=0};struct Texture {QString name;QSharedPointer<NetworkTexture> texture;};
    std::unordered_map<MapChannel,Texture> textures;
    auto getTextures(){return textures;}
};
QString birth(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
struct Geometry {
    QString id=birth();struct HFM {QString originalURL="http://controlled.test/main.gltf";} hfm;
    bool loaded=true;using NetworkMaterials=std::vector<std::shared_ptr<NetworkMaterial>>;NetworkMaterials _materials;
    QString e2eGeometryInstance()const{return id;}bool isHFMModelLoaded()const{return loaded;}const HFM& getHFMModel()const{return hfm;}
#include "OriginalMaterials.inc"
};
struct Model:QObject {
    QString id=birth();std::shared_ptr<Geometry> geometry;
    QString e2eModelInstance()const{return id;}auto getGeometry()const{return geometry;}bool isLoaded()const{return geometry && geometry->loaded;}
};
using ModelPointer=std::shared_ptr<Model>;
#include "CreateModelResources.h"
#include "ChatDomainSession.h"
struct EntityItem {virtual ~EntityItem()=default;};using EntityItemPointer=std::shared_ptr<EntityItem>;
struct RenderableModelEntityItem:EntityItem {
    ModelPointer original;ModelPointer getModel()const{return original;}
#include "OriginalAssociation.inc"
};
struct EntityTree {QHash<QUuid,EntityItemPointer> objects;
    template<class F>void withReadLock(F&& f){f();}auto findEntityByEntityItemID(const QUuid& id){return objects.value(id);}};
struct EntityScriptingInterface {EntityTree tree;EntityTree* getEntityTree(){return &tree;}};
struct Domain {overte::e2e::ChatDomainSession session;QVariantMap featureChatSession(const QString& run){return session.snapshot(run);}};
struct NodeList {Domain domain;Domain& getDomainHandler(){return domain;}};
auto entities=std::make_shared<EntityScriptingInterface>();auto nodes=std::make_shared<NodeList>();bool available=true;int gets=0;
struct DependencyManager {
    template<class T>static bool isSet(){return available;}
    template<class T>static auto get(){++gets;if constexpr(std::is_same_v<T,EntityScriptingInterface>){return entities;}else{return nodes;}}
};
struct Lifecycle {QVariantMap snapshot(){return {{"alive",true}};}};
struct TestScriptingInterface:QObject {
    QVariantMap featureCreateModels(const QVariantMap& command);
    QString _testResultsLocation="/private-owned",_featureObservationInstance=QString(32,'f');
    std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
    QHash<QString,QSet<QUuid>> _featureCreateEntityIds;
    quint64 _featureCreateModelsSequence=0;
    QHash<QString,QVariantMap> _featureCreateModelsCommands,_featureCreateModelsResults;
    std::shared_ptr<overte::e2e::CreateModelResources> _featureCreateModelResources;
};
#include "OriginalCreateModels.inc"
const QString run(32,'a');const QUuid entityId("33333333-3333-3333-3333-333333333333");
QVariantMap command(int i){return {{"schemaVersion",1},{"commandId",QString::number(i,16).rightJustified(32,'0')},{"action","feature-create-models-observe"},{"runId",run}};}
QVariantMap source(const QVariantMap& p){return p.value("source").toMap();}
QVariantMap first(const QVariantMap& p,const char* key){return source(p).value(key).toList().first().toMap();}
void print(const QVariantMap& p){assert(!p.isEmpty());QTextStream(stdout)<<QJsonDocument::fromVariant(p).toJson(QJsonDocument::Compact)<<'\n';}
int main(int argc,char** argv){
    QCoreApplication app(argc,argv);TestScriptingInterface target;target._featureCreateEntityIds.insert(run,{});
    if(!app.arguments().contains("--testScript")){assert(target.featureCreateModels(command(1)).isEmpty());assert(gets==0);return 0;}
    nodes->domain.session.changed(QUuid("11111111-1111-1111-1111-111111111111"),true,true);
    available=false;assert(target.featureCreateModels(command(1)).isEmpty() && gets==0);available=true;
    auto extra=command(1);extra.insert("expectedUrl","invented");assert(target.featureCreateModels(extra).isEmpty() && gets==0);
    TestScriptingInterface untracked;assert(untracked.featureCreateModels(command(1)).isEmpty());
    const auto initial=target.featureCreateModels(command(1));assert(source(initial).value("bindings").toList().isEmpty());print(initial);
    auto entity=std::make_shared<RenderableModelEntityItem>();auto model=std::make_shared<Model>();auto geometry=std::make_shared<Geometry>();
    auto material=std::make_shared<NetworkMaterial>();auto texture=QSharedPointer<NetworkTexture>::create();texture->url=QUrl("http://controlled.test/original/checker.png");
    material->textures[NetworkMaterial::ALBEDO]={"checker.png",texture};geometry->_materials={material};model->geometry=geometry;entity->original=model;
    entities->tree.objects.insert(entityId,entity);target._featureCreateEntityIds[run].insert(entityId);
    const auto loaded=target.featureCreateModels(command(2));print(loaded);
    assert(first(loaded,"bindings").value("model")==model->id && first(loaded,"bindings").value("geometry")==geometry->id);
    assert(first(loaded,"resources").value("state").toMap().value("url")==texture->url.toString());
    // Actual geometry/material binding changes independently of entity text.
    auto replacement=QSharedPointer<NetworkTexture>::create();replacement->url=QUrl("http://controlled.test/other/checker.png");replacement->loaded=false;
    material->textures[NetworkMaterial::ALBEDO].texture=replacement;
    const auto changed=target.featureCreateModels(command(3));print(changed);assert(source(changed).value("resources").toList().size()==2);
    assert(target.featureCreateModels(command(2))==loaded); // Frozen original nonce, not later desired state.
    // Original Resource may rebuild its shared control block while same QObject survives.
    texture.clear();const auto died=target.featureCreateModels(command(4));print(died);
    auto cachedRaw=new NetworkTexture;cachedRaw->url=QUrl("http://controlled.test/cache/checker.png");
    Cache cache;cachedRaw->_cache=&cache;
    QSharedPointer<NetworkTexture> cached(cachedRaw,&Resource::deleter);
    material->textures[NetworkMaterial::ALBEDO].texture=cached;
    const auto cachedFrame=target.featureCreateModels(command(5));const auto rows=source(cachedFrame).value("resources").toList();QString cacheId;
    for(const auto& row:rows){auto r=row.toMap();if(r.value("state").toMap().value("url")==cachedRaw->url.toString()){cacheId=r.value("instance").toString();}}
    assert(!cacheId.isEmpty());print(cachedFrame);
    material->textures.clear();cached.clear();assert(cache.stored.data()==cachedRaw);
    const auto weakExpired=target.featureCreateModels(command(6));print(weakExpired);
    for(const auto& value:source(weakExpired).value("resources").toList()){auto row=value.toMap();if(row.value("instance")==cacheId){assert(row.value("alive").toBool() && !row.value("sharedAvailable").toBool() && row.value("state").isNull());}}
    cached=cache.stored.staticCast<NetworkTexture>();material->textures[NetworkMaterial::ALBEDO]={"checker.png",cached};
    const auto rebound=target.featureCreateModels(command(7));print(rebound);assert(source(rebound).value("resources").toList().size()==3);
    material->textures.clear();cached.clear();cachedRaw->_cache=nullptr;cache.stored.clear();
    QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    // Retained actual Model/Geometry/material/resource outlive entity/tree absence.
    entities->tree.objects.clear();entity.reset();const auto retained=target.featureCreateModels(command(8));print(retained);
    assert(first(retained,"bindings").value("model").isNull() && first(retained,"models").value("alive").toBool());
    model.reset();const auto geometryRetained=target.featureCreateModels(command(9));print(geometryRetained);
    assert(!first(geometryRetained,"models").value("alive").toBool() && first(geometryRetained,"geometries").value("alive").toBool());
    geometry.reset();material.reset();replacement.clear();const auto retired=target.featureCreateModels(command(10));print(retired);
    for(const auto& key:{"models","geometries","materials","resources"}){for(const auto& row:source(retired).value(key).toList()){assert(!row.toMap().value("alive").toBool());}}
    // Reused immutable native instance is rejected after actual object death.
    entity=std::make_shared<RenderableModelEntityItem>();model=std::make_shared<Model>();model->id=first(loaded,"models").value("instance").toString();entity->original=model;entities->tree.objects.insert(entityId,entity);
    assert(target.featureCreateModels(command(11)).isEmpty());entities->tree.objects.clear();entity.reset();model.reset();
    // Original resource owner thread; blocked queue cannot hang the GUI or be a positive observation.
    QThread worker;worker.start();auto remote=QSharedPointer<NetworkTexture>::create();remote->url=QUrl("http://controlled.test/worker/checker.png");remote->moveToThread(&worker);
    model=std::make_shared<Model>();geometry=std::make_shared<Geometry>();material=std::make_shared<NetworkMaterial>();material->textures[NetworkMaterial::ALBEDO]={"checker.png",remote};geometry->_materials={material};model->geometry=geometry;
    entity=std::make_shared<RenderableModelEntityItem>();entity->original=model;entities->tree.objects.insert(entityId,entity);
    const auto remoteFrame=target.featureCreateModels(command(12));print(remoteFrame);assert(remote->reads==1);
    QSemaphore entered,release;QMetaObject::invokeMethod(remote.data(),[&]{entered.release();release.acquire();},Qt::QueuedConnection);assert(entered.tryAcquire(1,1000));
    QElapsedTimer elapsed;elapsed.start();assert(target.featureCreateModels(command(13)).isEmpty());assert(elapsed.elapsed()>=600 && elapsed.elapsed()<1250);
    release.release();QMetaObject::invokeMethod(remote.data(),[]{},Qt::BlockingQueuedConnection);assert(target.featureCreateModels(command(13)).isEmpty());
    const auto recovered=target.featureCreateModels(command(14));print(recovered);
    QMetaObject::invokeMethod(remote.data(),[&]{remote->moveToThread(app.thread());},Qt::BlockingQueuedConnection);worker.quit();assert(worker.wait(1000));
    // A stopped original resource thread refuses without queuing work.
    QThread stopped;auto stoppedTexture=QSharedPointer<NetworkTexture>::create();stoppedTexture->url=QUrl("http://controlled.test/stopped");stoppedTexture->moveToThread(&stopped);
    material->textures[NetworkMaterial::ALBEDO].texture=stoppedTexture;
    assert(target.featureCreateModels(command(16)).isEmpty());
    stopped.start();QMetaObject::invokeMethod(stoppedTexture.data(),[&]{stoppedTexture->moveToThread(app.thread());},Qt::BlockingQueuedConnection);stopped.quit();assert(stopped.wait(1000));
    material->textures[NetworkMaterial::ALBEDO].texture=remote;stoppedTexture.clear();
    // Actual caller worker marshals to original GUI receiver; an unserviced GUI
    // expires the weak queued request without capturing a later state.
    QVariantMap foreignResult;std::atomic_bool done {false};
    std::thread caller([&]{foreignResult=target.featureCreateModels(command(17));done.store(true);});
    elapsed.restart();while(!done.load() && elapsed.elapsed()<2500){QCoreApplication::processEvents();}caller.join();
    assert(!foreignResult.isEmpty());
    const auto sequence=target._featureCreateModelsSequence;
    std::thread blockedCaller([&]{assert(target.featureCreateModels(command(18)).isEmpty());});blockedCaller.join();
    QCoreApplication::processEvents();assert(target._featureCreateModelsSequence==sequence && !target._featureCreateModelsCommands.contains(command(18).value("commandId").toString()));
    // Same UUID reconnect has a distinct original Domain connection generation.
    nodes->domain.session.changed(QUuid("11111111-1111-1111-1111-111111111111"),false,true);
    nodes->domain.session.changed(QUuid("11111111-1111-1111-1111-111111111111"),true,true);
    const auto reconnected=target.featureCreateModels(command(15));print(reconnected);
    // Finite passive history never retires or overwrites earlier resources.
    overte::e2e::CreateModelResources bounded;
    auto capModel=std::make_shared<Model>();auto capGeometry=std::make_shared<Geometry>();auto capMaterial=std::make_shared<NetworkMaterial>();
    capModel->geometry=capGeometry;capGeometry->_materials={capMaterial};
    for(int i=0;i<64;++i){auto resource=QSharedPointer<NetworkTexture>::create();resource->url=QUrl("http://controlled.test/finite/"+QString::number(i));
        capMaterial->textures[NetworkMaterial::ALBEDO]={"checker.png",resource};
        assert(!bounded.observe(run,{{entityId.toString(QUuid::WithoutBraces),capModel}}).isEmpty());}
    auto exhausted=QSharedPointer<NetworkTexture>::create();exhausted->url=QUrl("http://controlled.test/exhausted");
    capMaterial->textures[NetworkMaterial::ALBEDO]={"checker.png",exhausted};assert(bounded.observe(run,{{entityId.toString(QUuid::WithoutBraces),capModel}}).isEmpty());
    overte::e2e::CreateModelResources runs;for(const auto c:QString("abcd")){assert(!runs.observe(QString(32,c),{}).isEmpty());}assert(runs.observe(QString(32,'e'),{}).isEmpty());
    overte::e2e::CreateModelResources oversized;capGeometry->_materials.clear();
    for(int i=0;i<64;++i){auto item=std::make_shared<NetworkMaterial>();auto resource=QSharedPointer<NetworkTexture>::create();
        resource->url=QUrl("http://controlled.test/"+QString::number(i)+"/"+QString(3970,'x'));
        item->textures[NetworkMaterial::ALBEDO]={"checker.png",resource};capGeometry->_materials.push_back(item);}
    assert(oversized.observe(run,{{entityId.toString(QUuid::WithoutBraces),capModel}}).isEmpty());
    target._featureLifecycle.reset();assert(target.featureCreateModels(command(2)).isEmpty());
    return 0;
}
