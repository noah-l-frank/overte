// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original Test getter; only dependency/entity-tree boundaries are substituted.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QObject>
#include <QRegularExpression>
#include <QSet>
#include <QTextStream>
#include <QThread>
#include <QTimer>
#include <QPointer>
#include <QUuid>
#include <QVariant>
#include <QUrl>
#define ANDROID_APP_PICO_INTERFACE 1
#include <algorithm>
#include <cassert>
#include <memory>
#include <type_traits>
#define OVERTE_E2E_FEATURE_TESTS 1
struct EntityItem:QObject{};using EntityItemPointer=std::shared_ptr<EntityItem>;
using RenderableModelEntityItem=EntityItem;
#include "CreateEntityLifetimes.h"
#include "ChatDomainSession.h"
namespace glm {struct vec3 {float x=0,y=0,z=0;};struct quat {float x=0,y=0,z=0,w=1;};}
namespace entity {enum class HostType {DOMAIN,AVATAR,LOCAL};}
namespace EntityTypes {enum Type {Unknown,Model};QString getEntityTypeName(Type t){return t==Model ? "Model" : "Unknown";}}
struct EntityItemProperties {
    QString name,model,textures;EntityTypes::Type type=EntityTypes::Model;entity::HostType host=entity::HostType::DOMAIN;
    glm::vec3 position {0,1,-2},dimensions {1,1,1},natural {1,1,1};bool ready=true,visible=true;glm::quat orientation;QUuid parent;
    qulonglong edited=static_cast<qulonglong>(QDateTime::currentMSecsSinceEpoch())*1000;
    QString getName() const{return name;}QString getModelURL() const{return model;}QString getTextures() const{return textures;}
    auto getType() const{return type;}auto getEntityHostType() const{return host;}auto getPosition() const{return position;}
    auto getDimensions() const{return dimensions;}auto getRotation() const{return orientation;}auto getParentID() const{return parent;}
    auto getNaturalDimensions() const{return natural;}QVariantMap getTextureNames() const{return {{"checker.png",QUrl("http://controlled.test/original/checker.png")}};}
    size_t getRenderInfoVertexCount() const{return ready ? 3 : 0;}int getRenderInfoTextureCount() const{return ready ? 1 : 0;}size_t getRenderInfoTextureSize() const{return ready ? 256 : 0;}int getRenderInfoDrawCalls() const{return ready ? 1 : 0;}
    bool getVisible() const{return visible;}bool getLocked() const{return false;}auto getLastEdited() const{return edited;}
};
struct PickFilter {enum class FlagBit {DOMAIN_ENTITIES,COARSE};static int getBitMask(FlagBit b){return b==FlagBit::DOMAIN_ENTITIES ? 1 : 2;}};
struct EntityTree {QHash<QUuid,EntityItemProperties>* values;QHash<QUuid,EntityItemPointer> objects;
    template<typename F>void withReadLock(F&& fn){fn();}
    EntityItemPointer findEntityByEntityItemID(const QUuid& id){if(!values->contains(id)){objects.remove(id);return {};}
        if(!objects.contains(id)){objects.insert(id,std::make_shared<EntityItem>());}return objects[id];}
};
struct EntityScriptingInterface {
    QHash<QUuid,EntityItemProperties> values;QVector<QUuid> scan;int reads=0;EntityTree tree{&values,{}};
    EntityTree* getEntityTree(){return &tree;}bool isLoaded(const QUuid& id){return values.contains(id) && values[id].ready;}
    auto findEntities(const glm::vec3&,float radius,int mask){assert(radius==128.0f && mask==3);return scan;}
    EntityItemProperties getEntityProperties(const QUuid& id){++reads;if(values.contains(id)){return values.value(id);}EntityItemProperties p;p.type=EntityTypes::Unknown;return p;}
};
struct Avatar {glm::vec3 getWorldPosition(){return {0,1,0};}};
struct AvatarManager {std::shared_ptr<Avatar> getMyAvatar(){return std::make_shared<Avatar>();}};
struct DomainHandler {overte::e2e::ChatDomainSession session;
    QVariantMap featureChatSession(const QString& run){return session.snapshot(run);}
    QUuid getUUID() const{return QUuid("{11111111-1111-1111-1111-111111111111}");}bool isConnected() const{return true;}};
struct NodeList {DomainHandler domain;DomainHandler& getDomainHandler(){return domain;}
    QUuid getSessionUUID(){return QUuid("{22222222-2222-2222-2222-222222222222}");}bool getThisNodeCanRez(){return true;}bool getThisNodeCanRezTmp(){return false;}};
auto entities=std::make_shared<EntityScriptingInterface>();auto avatars=std::make_shared<AvatarManager>();auto nodes=std::make_shared<NodeList>();
bool dependencies=true;int gets=0;
struct DependencyManager {
    template<typename T> static bool isSet(){return dependencies;}
    template<typename T> static auto get(){++gets;if constexpr(std::is_same_v<T,EntityScriptingInterface>){return entities;}
        else if constexpr(std::is_same_v<T,AvatarManager>){return avatars;}else{return nodes;}}
};
struct Lifecycle {QVariantMap snapshot(){return {{"launches",1}};}};
struct TestScriptingInterface:QObject {
    QVariantMap featureCreateEntities(const QVariantMap& command);
    QString _testResultsLocation {"/owned-private-result"},_featureObservationInstance {QString(32,'f')};
    std::shared_ptr<Lifecycle> _featureLifecycle {std::make_shared<Lifecycle>()};
    quint64 _featureCreateEntitiesSequence {0};
    QHash<QString,QVariantMap> _featureCreateEntitiesCommands,_featureCreateEntitiesResults;
    QHash<QString,QSet<QUuid>> _featureCreateEntityIds;
    std::shared_ptr<overte::e2e::CreateEntityLifetimes> _featureCreateEntityLifetimes;
};
#include "OriginalCreateEntities.inc"
QVariantMap command(int number,QString run=QString(32,'a')) {return {{"schemaVersion",1},{"commandId",QString::number(number,16).rightJustified(32,'0')},
    {"action","feature-create-entities-observe"},{"runId",run}};}
QVariantMap source(const QVariantMap& value){return value.value("source").toMap();}
QVariantMap entityRow(const QVariantMap& value){return source(value).value("entities").toList().first().toMap();}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);TestScriptingInterface target;
    if(!app.arguments().contains("--testScript")){assert(target.featureCreateEntities(command(1)).isEmpty());assert(gets==0);return 0;}
    nodes->domain.session.changed(nodes->domain.getUUID(),true,true);
    dependencies=false;assert(target.featureCreateEntities(command(1)).isEmpty());assert(gets==0);dependencies=true;
    QThread idle;auto foreign=new TestScriptingInterface;foreign->moveToThread(&idle);
    assert(foreign->featureCreateEntities(command(1)).isEmpty());assert(gets==0);
    idle.start();assert(QMetaObject::invokeMethod(foreign,[&]{foreign->moveToThread(app.thread());},Qt::BlockingQueuedConnection));idle.quit();assert(idle.wait(1000));delete foreign;
    const auto baseline=target.featureCreateEntities(command(1));assert(source(baseline).value("entities").toList().isEmpty());
    assert(baseline.value("processId").toLongLong()==app.applicationPid());assert(source(baseline).value("canRez").toBool());
    const QUuid id("{33333333-3333-3333-3333-333333333333}");EntityItemProperties p;
    p.name="e2e-"+QString(32,'a')+"-model";p.model="http://controlled.test/feature-fixture/v1/runs/"+QString(32,'a')+"/tickets/"+QString(32,'b')+"/gltf-bundle/main.gltf";
    entities->values.insert(id,p);entities->scan={id};const auto imported=target.featureCreateEntities(command(2));
    assert(entityRow(imported).value("id")==id.toString(QUuid::WithoutBraces));assert(entityRow(imported).value("modelUrl")==p.model);
    auto rendererRetains=entities->tree.findEntityByEntityItemID(id);
    p.name="renamed-original";p.position={500,500,500};p.host=entity::HostType::LOCAL;entities->values[id]=p;entities->scan.clear();
    const auto moved=target.featureCreateEntities(command(3));assert(entityRow(moved).value("name")==p.name);assert(entityRow(moved).value("hostType")=="local");
    assert(source(moved).value("scan").toMap().value("scannedEntities").toInt()==0); // Direct retained-ID read, not another radius guess.
    entities->values.remove(id);const auto deleted=target.featureCreateEntities(command(4));assert(source(deleted).value("entities").toList().isEmpty());
    assert(source(deleted).value("absentIds").toList()==QVariantList{id.toString(QUuid::WithoutBraces)});
    assert(source(deleted).value("entityLifetimes").toList().first().toMap().value("alive").toBool());
    rendererRetains.reset();const auto retired=target.featureCreateEntities(command(514));
    assert(!source(retired).value("entityLifetimes").toList().first().toMap().value("alive").toBool());
    assert(target.featureCreateEntities(command(2))==imported);assert(target.featureCreateEntities(command(2,QString(32,'b'))).isEmpty());
    auto extra=command(5);extra.insert("expected",QVariantMap());const int before=gets;assert(target.featureCreateEntities(extra).isEmpty());assert(gets==before);
    for(const auto& packet:{baseline,imported,moved,deleted,retired}){QTextStream(stdout)<<QJsonDocument::fromVariant(packet).toJson(QJsonDocument::Compact)<<'\n';}
    const QUuid other("{44444444-4444-4444-4444-444444444444}");p.host=entity::HostType::DOMAIN;p.model="http://foreign.test/other.gltf";entities->values.insert(other,p);entities->scan={other};
    const auto unowned=target.featureCreateEntities(command(5));assert(source(unowned).value("scan").toMap().value("unowned").toList().size()==1);
    const auto raw=source(unowned).value("scan").toMap().value("unowned").toList().first().toMap();assert(raw.value("sha256").toString().size()==64);
    nodes->domain.session.changed(nodes->domain.getUUID(),false,true);nodes->domain.session.changed(nodes->domain.getUUID(),true,true);
    const auto reconnect=target.featureCreateEntities(command(6));
    assert(source(reconnect).value("domainId")==source(deleted).value("domainId"));
    assert(source(reconnect).value("domainSession").toMap().value("connectionBirth")!=source(deleted).value("domainSession").toMap().value("connectionBirth"));
    QTextStream(stdout)<<QJsonDocument::fromVariant(reconnect).toJson(QJsonDocument::Compact)<<'\n';
    // Actual run-ticket URL is visible before original Model naming/loading.
    TestScriptingInterface unnamed;const QUuid initial("{66666666-6666-6666-6666-666666666666}");
    EntityItemProperties initialProperties;initialProperties.name="Model";initialProperties.visible=false;initialProperties.ready=false;
    const auto ownedUrl="http://controlled.test/feature-fixture/v1/runs/"+QString(32,'a')+"/tickets/"+QString(32,'b')+"/obj-bundle/main.obj";
    for(const auto& suffix:QStringList{"?foreign=1","#fragment"}){
        TestScriptingInterface excluded;initialProperties.model=ownedUrl+suffix;entities->values.insert(initial,initialProperties);entities->scan={initial};
        assert(source(excluded.featureCreateEntities(command(1))).value("entities").toList().isEmpty());
    }
    initialProperties.model=ownedUrl;entities->values[initial]=initialProperties;
    const auto initialModel=unnamed.featureCreateEntities(command(1));assert(entityRow(initialModel).value("name")==QVariant("Model"));
    assert(!entityRow(initialModel).value("visible").toBool() && !entityRow(initialModel).value("visuallyReady").toBool());
    assert(entityRow(initialModel).value("renderInfo").toMap().value("vertices").toULongLong()==0);
    const auto firstLife=source(initialModel).value("entityLifetimes").toList().first().toMap();
    entities->values[initial].ready=true;entities->values[initial].visible=true;
    const auto loaded=unnamed.featureCreateEntities(command(2));assert(entityRow(loaded).value("visuallyReady").toBool());
    assert(entityRow(loaded).value("renderInfo").toMap().value("vertices").toULongLong()==3);
    assert(source(loaded).value("entityLifetimes").toList().first().toMap()==firstLife);
    const auto originalObject=entities->tree.findEntityByEntityItemID(initial);
    entities->tree.objects[initial]=std::make_shared<EntityItem>();
    assert(unnamed.featureCreateEntities(command(3)).isEmpty()); // Never adopt a replacement tree object with the same UUID.
    entities->values.remove(initial);entities->scan={other};entities->tree.objects.remove(initial);
    for(int i=7;i<512;++i){assert(!target.featureCreateEntities(command(i)).isEmpty());}
    assert(target.featureCreateEntities(command(512)).isEmpty());assert(target.featureCreateEntities(command(2))==imported);
    target._featureLifecycle.reset();assert(target.featureCreateEntities(command(2)).isEmpty());
    // Exact original factory deleter: shared holder retirement precedes actual
    // QObject death; only the ordinary Qt event loop delivers deleteLater().
    auto originalDeleter=
#include "OriginalEntityDeleter.inc"
    ;
    TestScriptingInterface deferred;
    const QUuid deferredId("77777777-7777-7777-7777-777777777777");
    EntityItemPointer pending(new EntityItem,originalDeleter);std::weak_ptr<EntityItem> weak=pending;QPointer<EntityItem> guard(pending.get());
    entities->values[deferredId]=initialProperties;entities->scan={deferredId};entities->tree.objects[deferredId]=pending;
    const auto live=deferred.featureCreateEntities(command(1));
    assert(source(live).value("entityLifetimes").toList().first().toMap().value("alive").toBool());
    entities->values.remove(deferredId);entities->tree.objects.remove(deferredId);entities->scan.clear();pending.reset();
    assert(weak.expired() && guard);const auto pendingDeath=deferred.featureCreateEntities(command(2));
    assert(source(pendingDeath).value("entities").toList().isEmpty());
    assert(source(pendingDeath).value("entityLifetimes").toList().first().toMap().value("alive").toBool());
    QObject::connect(guard.data(),&QObject::destroyed,&app,[&]{app.quit();});
    QTimer::singleShot(1000,&app,[&]{app.exit(1);});assert(app.exec()==0 && !guard);
    const auto actualDeath=deferred.featureCreateEntities(command(3));
    assert(!source(actualDeath).value("entityLifetimes").toList().first().toMap().value("alive").toBool());
    return 0;
}
