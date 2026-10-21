// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "PhoneWebRuntimeBridge.h"
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <EntityItem.h>
#include <EntityItemProperties.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <QUrl>
#include <ViewFrustum.h>
#include <cmath>
#include <algorithm>
#include <memory>
#include <vector>
#include <QJsonArray>

namespace overte::e2e {
// Fixture inputs only. Product observations, pixels and Browser retirement are
// separate sources. Only the exact two local objects created here may be removed.
class PhoneEmoteFixture {
public:
    QVariantMap input(const QVariantMap& command, const ViewFrustum& view, const QString& mode,
            const glm::vec3& feet, float scale, float boom) {
        const auto object=QJsonObject::fromVariantMap(command);
        const auto operation=object.value("operation").toString();
        const auto id=object.value("commandId").toString(),run=object.value("runId").toString();
        const auto allowed=operation=="prepare" ? QStringList{"action","commandId","fixtureUrl","imageExtent","markerRoi",
            "operation","runId","schemaVersion","ticket"} : QStringList{"action","commandId","fixtureInstance","operation","runId","schemaVersion"};
        if (QThread::currentThread()!=qApp->thread() || command.keys()!=allowed
                || !object.value("schemaVersion").isDouble() || object.value("schemaVersion").toDouble()!=1
                || object.value("action").toString()!="phone-emote-fixture-input"
                || !hex(id) || !hex(run) || (operation!="prepare" && operation!="release")) { return {}; }
        if (!_lastInput.isEmpty() && _lastInput.value("commandId")==id) {
            return command==_lastInput ? _lastReceipt : QVariantMap();
        }
        auto entities=DependencyManager::get<EntityScriptingInterface>();
        if (!entities || !entities->getEntityTree()) { return {}; }
        QVariantMap receipt;
        if (operation=="prepare") {
            auto root=QVariantMap{{"schemaVersion",1},{"commandId",id},{"action","feature-phone-web-runtime-observe"},
                {"runId",run},{"fixtureUrl",command.value("fixtureUrl")}};
            const auto ticket=object.value("ticket").toString();
            auto finite=[](double value,double low,double high) { return std::isfinite(value)&&value>=low&&value<=high; };
            auto vectorFinite=[&](const glm::vec3& value) { return finite(value.x,-1e6,1e6)&&finite(value.y,-1e6,1e6)&&finite(value.z,-1e6,1e6); };

            if (!phoneWebRuntimeCommand(root) || !hex(ticket) || !view.isPerspective() || mode!="selfie"
                    || !finite(scale,.0001,1000) || !finite(boom,3,12) || !vectorFinite(feet) || !vectorFinite(view.getPosition())
                    || !finite(view.getFieldOfView(),1,179) || !finite(view.getAspectRatio(),.1,10)
                    || !finite(view.getNearClip(),.00001,1e6) || !finite(view.getFarClip(),.001,1e9)
                    || view.getFarClip()<=view.getNearClip()
                    || (!_instance.isEmpty() && (_phase!="drained" || _run==run))) { return {}; }
            const auto extent=object.value("imageExtent").toArray(),roi=object.value("markerRoi").toArray();
            auto whole=[](const QJsonValue& v,int low,int high) {
                return v.isDouble() && std::isfinite(v.toDouble()) && v.toDouble()>=low && v.toDouble()<=high
                    && std::floor(v.toDouble())==v.toDouble();
            };
            if (extent.size()!=2 || roi.size()!=4 || !whole(extent[0],240,16384) || !whole(extent[1],240,16384)) { return {}; }
            const double width=extent[0].toDouble(),height=extent[1].toDouble();
            for (const auto& v:roi) { if (!whole(v,0,16384)) { return {}; } }
            const double x0=roi[0].toDouble(),y0=roi[1].toDouble(),x1=roi[2].toDouble(),y1=roi[3].toDouble();
            if (x1>width || y1>height || x1-x0<160 || y1-y0<40 || (x1-x0)*(y1-y0)>.1*width*height
                    || std::abs(width/height-view.getAspectRatio())>.005) { return {}; }
            const auto projection=view.getProjection();
            for (int column=0;column<4;++column) { for (int row=0;row<4;++row) {
                if (!std::isfinite(projection[column][row])) { return {}; }
            } }
            const auto inverse=glm::inverse(projection);
            auto at=[&](double x,double y,double distance,glm::vec3& result) {
                auto p=inverse*glm::vec4(float(2*x/width-1),float(1-2*y/height),-1,1);
                if (!std::isfinite(p.w) || std::abs(p.w)<1e-8) { return false; }
                glm::vec3 local=glm::vec3(p)/p.w;
                if (!std::isfinite(local.z) || local.z>=-1e-8) { return false; }
                local*=float(-distance/local.z);
                result=view.getPosition()+view.getOrientation()*local;
                return std::isfinite(result.x)&&std::isfinite(result.y)&&std::isfinite(result.z);
            };
            const auto forward=view.getOrientation()*glm::vec3(0,0,-1);
            const auto depth=glm::dot(feet-view.getPosition(),forward)+4*scale;
            if (!std::isfinite(depth) || depth<=view.getNearClip()*4) { return {}; }
            glm::vec3 markerTop,markerBottom,backTop,backBottom;
            const double near=std::max(.25,double(view.getNearClip())*2);
            if (!at(x0,y0,near,markerTop) || !at(x1,y1,near,markerBottom)
                    || !at(-.05*width,-.05*height,depth,backTop) || !at(1.05*width,1.05*height,depth,backBottom)) { return {}; }
            const auto unrotate=glm::inverse(view.getOrientation());
            const auto markerSize=unrotate*(markerBottom-markerTop),backSize=unrotate*(backBottom-backTop);
            auto dimensions=[](const glm::vec3& delta) { return glm::vec3(std::abs(delta.x),std::abs(delta.y),.01f); };
            _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');_run=run;_phase="creating";
            _created=QDateTime::currentMSecsSinceEpoch();_objects.clear();_originalInput=command;
            QVariantList matrix;
            for (int row=0;row<4;++row) { for (int column=0;column<4;++column) { matrix.append(projection[column][row]); } }
            _view={{"position",vec(view.getPosition())},{"rotation",quat(view.getOrientation())},{"projection",matrix},
                {"fieldOfViewDegrees",view.getFieldOfView()},{"aspectRatio",view.getAspectRatio()},
                {"nearClip",view.getNearClip()},{"farClip",view.getFarClip()},{"perspective",view.isPerspective()},
                {"feetPosition",vec(feet)},{"modelScale",scale},{"boomLength",boom},{"mode",mode}};
            const QString url=command.value("fixtureUrl").toString()+"tickets/"+ticket+"/graphics-marker.v1.html";
            auto add=[&](const QString& role,EntityTypes::EntityType type,const glm::vec3& position,const glm::vec3& size) {
                _objects.push_back({role,{}, {}});
                EntityItemProperties properties;
                properties.setType(type);properties.setName("e2e-"+run+"-emote-"+role);
                properties.setPosition(position);properties.setRotation(view.getOrientation());properties.setDimensions(size);
                properties.setVisible(true);properties.setCollisionless(true);properties.setCanCastShadow(false);properties.setLocked(false);
                if (role=="marker") { properties.setSourceUrl(url);properties.setDpi(100); }
                else { properties.setColor(glm::u8vec3(128)); }
                const auto entity=entities->addEntity(properties,QStringLiteral("local"));
                _objects.back().id=entity;
                if (entity.isNull()) { return false; }
                entities->getEntityTree()->withReadLock([&] { _objects.back().object=entities->getEntityTree()->findEntityByEntityItemID(entity); });
                return !_objects.back().object.expired();
            };
            const bool back=add("backdrop",EntityTypes::Box,(backTop+backBottom)*.5f,dimensions(backSize));
            const bool marker=back && add("marker",EntityTypes::Web,(markerTop+markerBottom)*.5f,dimensions(markerSize));
            _phase=back&&marker ? "active" : "failed";
            receipt={{"phoneEmoteFixtureInputVersion",1},{"commandId",id},{"runId",run},{"fixtureInstance",_instance},
                {"operation",operation},{"recorded",true}};
        } else {
            if (!hex(object.value("fixtureInstance").toString()) || _run!=run
                    || object.value("fixtureInstance").toString()!=_instance || _phase=="creating") { return {}; }
            // Identity/host/lock/child preflight and deletion share one tree
            // write lock. A same-UUID replacement cannot race into deletion;
            // unknown children never join the deletion set.
            bool refused=false;
            entities->getEntityTree()->withWriteLock([&] {
                std::vector<EntityItemPointer> originals;
                for (const auto& entry:_objects) {
                    if (entry.id.isNull()) { continue; }
                    auto actual=entities->getEntityTree()->findEntityByEntityItemID(entry.id);
                    if (!actual) { continue; }
                    if (actual!=entry.object.lock() || !actual->isLocalEntity() || actual->getLocked() || actual->hasChildren()
                            || !actual->getParentID().isNull() || !actual->getCloneOriginID().isNull() || !actual->getCloneIDs().isEmpty()) {
                        refused=true;return;
                    }
                    originals.push_back(actual);
                }
                _phase="releasing";
                entities->getEntityTree()->deleteEntitiesByPointer(originals);
            });
            if (refused) { return {}; }
            receipt={{"phoneEmoteFixtureInputVersion",1},{"commandId",id},{"runId",run},{"fixtureInstance",_instance},
                {"operation",operation},{"recorded",true}};
        }
        _lastInput=command;_lastReceipt=receipt;return receipt; // Input receipt only.
    }

    QVariantMap observe(const QString& run) {
        if (QThread::currentThread()!=qApp->thread() || _instance.isEmpty() || run!=_run) { return {}; }
        auto entities=DependencyManager::get<EntityScriptingInterface>();
        if (!entities || !entities->getEntityTree()) { return {}; }
        QVariantList objects,present,absent;int retained {0};
        for (const auto& entry:_objects) {
            const QString id=entry.id.isNull() ? QString() : entry.id.toString(QUuid::WithoutBraces);
            objects.append(QVariantMap{{"role",entry.role},{"id",id.isEmpty() ? QVariant() : QVariant(id)}});
            if (!entry.object.expired()) { ++retained; }
            if (entry.id.isNull()) { continue; }
            bool original=false,exists=false;EntityItemProperties p;
            entities->getEntityTree()->withReadLock([&] {
                auto actual=entities->getEntityTree()->findEntityByEntityItemID(entry.id);
                exists=bool(actual);original=exists && actual==entry.object.lock();
                if (actual) { p=actual->getProperties(); }
            });
            if (!exists) { absent.append(id);continue; }
            const auto color=p.getColor();
            if (p.getType()==EntityTypes::Unknown || p.getName().size()>256 || p.getSourceUrl().size()>2048) { return {}; }
            present.append(QVariantMap{{"id",id},{"role",entry.role},{"originalObject",original},
                {"name",p.getName()},{"type",EntityTypes::getEntityTypeName(p.getType())},
                {"parentId",p.getParentID().toString(QUuid::WithoutBraces)},
                {"hostType",p.getEntityHostType()==entity::HostType::LOCAL ? "local" : "foreign"},
                {"position",vec(p.getPosition())},{"rotation",quat(p.getRotation())},{"dimensions",vec(p.getDimensions())},
                {"color",QVariantList{int(color.x),int(color.y),int(color.z)}},{"visible",p.getVisible()},
                {"sourceUrl",p.getSourceUrl()},{"locked",p.getLocked()},{"collisionless",p.getCollisionless()},{"canCastShadow",p.getCanCastShadow()},
                {"dpi",p.getDpi()},{"lastEditedEpochUs",static_cast<qulonglong>(p.getLastEdited())}});
        }
        if (_phase=="releasing" && present.isEmpty() && retained==0) { _phase="drained"; }
        return {{"phoneEmoteFixtureVersion",1},{"fixtureInstance",_instance},{"runId",_run},{"phase",_phase},
            {"createdEpochMs",_created},{"originalInput",_originalInput},{"originalView",_view},{"objects",objects},
            {"entities",present},{"absentIds",absent},{"retainedObjects",retained}};
    }
private:
    struct Object { QString role;QUuid id;std::weak_ptr<EntityItem> object; };
    static bool hex(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QVariantList vec(const glm::vec3& value) { return {value.x,value.y,value.z}; }
    static QVariantList quat(const glm::quat& value) { return {value.x,value.y,value.z,value.w}; }
    QString _instance,_run,_phase;
    qint64 _created {0};
    QVariantMap _originalInput,_view,_lastInput,_lastReceipt;
    std::vector<Object> _objects;
};
}
#endif
