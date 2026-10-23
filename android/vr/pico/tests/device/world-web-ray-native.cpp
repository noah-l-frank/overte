// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original provider/projection bodies; entity/avatar/HMD are explicit seams.
#include "tests/device/native/PicoWorldWebRay.h"
#include <QDateTime>
#include <QGuiApplication>
#include <QQuickWindow>
#include <QQmlContext>
#include <QQmlEngine>
#include <QJsonDocument>
#include <QFile>
#include <QThread>
#include <QUuid>
#include <glm/glm.hpp>
#include <glm/gtc/quaternion.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <memory>
#include <type_traits>
#include <cassert>
#undef assert
#define assert(c) do {if(!(c)){fprintf(stderr,"Original world ray assertion %d: %s\n",__LINE__,#c);abort();}}while(false)
struct ApplicationBoundary:QGuiApplication {
    using QGuiApplication::QGuiApplication;bool hmd{true};bool isHMDMode(){return hmd;}
};
#undef qApp
#define qApp static_cast<ApplicationBoundary*>(QCoreApplication::instance())
namespace EntityTypes {enum Type {Web,Box};}
namespace entity {enum class HostType {LOCAL,DOMAIN};}
struct PropertiesBoundary {
    EntityTypes::Type type{EntityTypes::Web};entity::HostType host{entity::HostType::LOCAL};
    QString name{"OVERTE_PARITY_WEB_REFERENCE"},url;QUuid parent;
    bool visible{true},ignore{false};float dpi{40};
    glm::vec3 dimensions{1.8f,2.2f,.01f},registration{.5f},position{0,1.4f,-2.5f};glm::quat rotation{1,0,0,0};
    auto getType()const{return type;}auto getEntityHostType()const{return host;}
    auto getName()const{return name;}auto getSourceUrl()const{return url;}auto getParentID()const{return parent;}
    bool getVisible()const{return visible;}bool getIgnorePickIntersection()const{return ignore;}
    auto getDimensions()const{return dimensions;}auto getRegistrationPoint()const{return registration;}
    auto getPosition()const{return position;}auto getRotation()const{return rotation;}float getDpi()const{return dpi;}
};
struct EntityScriptingInterface {
    PropertiesBoundary props;QUuid id,last;PropertiesBoundary getEntityProperties(const QUuid& value){last=value;return props;}
};
struct AvatarBoundary {glm::mat4 sensor{1};auto getSensorToWorldMatrix(){return sensor;}};
struct AvatarManager {std::shared_ptr<AvatarBoundary> avatar=std::make_shared<AvatarBoundary>();auto getMyAvatar(){return avatar;}};
struct HMDScriptingInterface {bool enabled{true};bool isHMDMode(){return enabled;}glm::vec3 getPosition(){return {0,1.6f,0};}};
EntityScriptingInterface entities;AvatarManager avatars;HMDScriptingInterface hmd;bool dependencies{true};
struct DependencyManager {
    template<class T>static bool isSet(){return dependencies;}
    template<class T>static T* get(){
        if constexpr(std::is_same_v<T,EntityScriptingInterface>)return &entities;
        else if constexpr(std::is_same_v<T,AvatarManager>)return &avatars;
        else return &hmd;
    }
};
bool enabled{true},privateDirectory{true};const QString BRIDGE_DIRECTORY="explicit-host-boundary";
bool bridgeEnabled(){return enabled;}bool previewDirectory(const QString&){return privateDirectory;}
struct EntityBoundary {glm::vec3 dimensions;auto getScaledDimensions(){return dimensions;}};
using TypedEntityPointer=std::shared_ptr<EntityBoundary>;
struct PointerEvent {
    glm::vec2 point;auto getPos2D()const{return point;}void setPos2D(glm::vec2 value){point=value;}
};
struct SurfaceBoundary {glm::vec2 measured{};void handlePointerEvent(const PointerEvent& event,int&){measured=event.point;}};
struct WebEntityRenderer {
    float _dpi{40};int _touchDevice{0};std::shared_ptr<SurfaceBoundary> _webSurface=std::make_shared<SurfaceBoundary>();
    glm::vec2 getWindowSize(const TypedEntityPointer&)const;void handlePointerEventAsTouch(const PointerEvent&);
};
struct RayPick {static glm::vec2 projectOntoXYPlane(const glm::vec3&,const glm::vec3&,const glm::quat&,const glm::vec3&,const glm::vec3&,bool);};
#include "actual-world-ray.inc"
int main(int argc,char** argv){
    ApplicationBoundary app(argc,argv);assert(argc==2);QQuickWindow window;window.show();window.requestActivate();
    QCoreApplication::processEvents();assert(app.applicationState()==Qt::ApplicationActive);
    QQmlEngine engine;QQmlContext context(engine.rootContext());QQuickItem clipper(window.contentItem());QQuickItem item(&clipper);
    QQuickItem overlay(window.contentItem());overlay.setZ(100);overlay.setVisible(false);
    QQmlEngine::setContextForObject(&item,&context);
    entities.id=QUuid("12345678-1234-1234-1234-123456789abc");
    const auto identity="web-entity:"+entities.id.toString(QUuid::WithoutBraces);
    const QString run(32,'a'),root="http://127.0.0.1/feature-fixture/v1/runs/"+run+"/";
    entities.props.url=root+"tickets/"+QString(32,'e')+"/index.html";
    item.setProperty("sourceIdentity",identity);item.setProperty("url",entities.props.url);context.setContextProperty("nativeWebSourceIdentity",identity);
    installWorldWebRayProvider();auto provider=app.property(overte::e2e::picoWorldWebRayProperty()).value<overte::e2e::PicoWorldWebRayProvider>();assert(provider);
    QVariantList originals;
    for(int variant=0;variant<3;++variant){
        if(variant==1){entities.props.dimensions={8,9,.01f};entities.props.rotation=glm::angleAxis(.7f,glm::vec3(0,1,0));}
        if(variant==2){entities.props.dimensions={1.8f,2.2f,.01f};entities.props.rotation=glm::quat(1,0,0,0);}
        WebEntityRenderer renderer;auto entity=std::make_shared<EntityBoundary>();entity->dimensions=entities.props.dimensions;
        const auto size=renderer.getWindowSize(entity);window.resize(int(size.x),int(size.y));
        clipper.setSize(QSizeF(window.size()));
        item.setPosition(variant==2?QPointF(12,20):QPointF());item.setSize(QSizeF(window.width()-(variant==2?24:0),window.height()*(variant==2?.6:1)));
        const QPointF local(item.width()*.25,item.height()*(100./480));
        const auto ray=provider(&item,local);assert(!ray.isEmpty());assert(entities.last==entities.id);
        const auto xyz=ray.value("worldPoint").toList();assert(xyz.size()==3);
        const glm::vec3 point(xyz[0].toFloat(),xyz[1].toFloat(),xyz[2].toFloat());
        const auto projected=RayPick::projectOntoXYPlane(point,entities.props.position,entities.props.rotation,
            entities.props.dimensions,entities.props.registration,true);
        // Real original renderer receives the real original RayPick result.
        renderer.handlePointerEventAsTouch(PointerEvent{projected});const auto scene=item.mapToScene(local);
        assert(glm::length(renderer._webSurface->measured-glm::vec2(scene.x(),scene.y()))<.01f);
        originals.append(ray);
    }
    const auto good=entities.props;const auto local=QPointF(item.width()/2,item.height()/2);
    for(int variant=0;variant<20;++variant){
        entities.props=good;enabled=true;privateDirectory=true;dependencies=true;app.hmd=true;hmd.enabled=true;item.setVisible(true);item.setEnabled(true);item.setOpacity(1);
        overlay.setVisible(false);clipper.setClip(false);clipper.setSize(QSizeF(window.size()));
        item.setProperty("sourceIdentity",identity);item.setProperty("url",good.url);context.setContextProperty("nativeWebSourceIdentity",identity);
        if(variant==0)enabled=false;if(variant==1)privateDirectory=false;if(variant==2)dependencies=false;
        if(variant==3)app.hmd=false;if(variant==4)hmd.enabled=false;if(variant==5)item.setVisible(false);
        if(variant==6)entities.props.name="foreign";if(variant==7)entities.props.parent=QUuid::createUuid();
        if(variant==8)entities.props.host=entity::HostType::DOMAIN;if(variant==9)entities.props.type=EntityTypes::Box;
        if(variant==10)entities.props.ignore=true;if(variant==11)entities.props.registration={0,0,0};
        if(variant==12)item.setProperty("url","https://foreign.invalid");
        if(variant==13)context.setContextProperty("nativeWebSourceIdentity","web-entity:foreign");
        if(variant==14)entities.props.rotation=glm::quat(2,0,0,0);
        if(variant==15)item.setProperty("sourceIdentity","tablet:foreign");
        if(variant==16){overlay.setSize(QSizeF(window.size()));overlay.setVisible(true);}
        if(variant==17){clipper.setClip(true);clipper.setSize(QSizeF(10,10));}
        if(variant==18)item.setEnabled(false);
        if(variant==19)item.setOpacity(.005);
        assert(provider(&item,local).isEmpty());
    }
    QFile output(argv[1]);assert(output.open(QIODevice::WriteOnly));assert(output.write(QJsonDocument::fromVariant(originals).toJson())>0);output.close();
    puts("PASS original world ray provider, RayPick and renderer projection; explicit entity/HMD seams");
}
