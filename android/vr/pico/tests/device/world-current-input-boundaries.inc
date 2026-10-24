// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Explicit entity/avatar/HMD dependencies; actual Qt window/context/provider.
#include <QQmlContext>
#include <QQmlEngine>
#include <glm/gtc/quaternion.hpp>
#include <type_traits>
struct CurrentAppBoundary:QGuiApplication {using QGuiApplication::QGuiApplication;bool isHMDMode(){return true;}};
#undef qApp
#define qApp static_cast<CurrentAppBoundary*>(QCoreApplication::instance())
namespace EntityTypes {enum Type{Web,Box};}
namespace entity {enum class HostType{LOCAL,DOMAIN};}
struct CurrentProperties {
    QString url;glm::vec3 dimensions{640.f/(39.3701f*40),480.f/(39.3701f*40),.01f};
    auto getType()const{return EntityTypes::Web;}auto getEntityHostType()const{return entity::HostType::LOCAL;}
    QString getName()const{return "OVERTE_PARITY_WEB_REFERENCE";}auto getSourceUrl()const{return url;}
    QUuid getParentID()const{return {};}bool getVisible()const{return true;}bool getIgnorePickIntersection()const{return false;}
    auto getDimensions()const{return dimensions;}glm::vec3 getRegistrationPoint()const{return {.5f,.5f,.5f};}
    float getDpi()const{return 40;}glm::vec3 getPosition()const{return {0,1.4f,-2.5f};}glm::quat getRotation()const{return {1,0,0,0};}
};
struct EntityScriptingInterface {CurrentProperties props;CurrentProperties getEntityProperties(const QUuid&){return props;}};
struct CurrentAvatar {glm::mat4 getSensorToWorldMatrix(){return glm::mat4(1);}};
struct AvatarManager {auto getMyAvatar(){return std::make_shared<CurrentAvatar>();}};
struct HMDScriptingInterface {bool isHMDMode(){return true;}glm::vec3 getPosition(){return {0,1.6f,0};}};
EntityScriptingInterface currentEntities;AvatarManager currentAvatars;HMDScriptingInterface currentHmd;
struct DependencyManager {
    template<class T>static bool isSet(){return true;}
    template<class T>static T* get(){
        if constexpr(std::is_same_v<T,EntityScriptingInterface>)return &currentEntities;
        else if constexpr(std::is_same_v<T,AvatarManager>)return &currentAvatars;
        else if constexpr(std::is_same_v<T,HMDScriptingInterface>)return &currentHmd;
        else return &tabletBoundary;
    }
};
