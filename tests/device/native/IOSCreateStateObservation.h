// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "NormalCreateControls.h"
#include "NormalControlUi.h"
#include "IOSCreateLifetimes.h"
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <RenderableModelEntityItem.h>
#include <PolyVoxEntityItem.h>
#include <ViewFrustum.h>
#include <NodeList.h>
#include <QPointer>
#include <QSet>
#include <algorithm>

namespace overte::e2e {
class IOSCreateStateObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const QList<QQuickItem*>& inputs,
            bool shown,EntityScriptingInterface* entities,const QString& domainId) {
        auto result=_bracket.read("iosCreateStateVersion","native-main-create",request,run,[&]() -> QVariantMap {
            if (!entities || !entities->getEntityTree() || inputs.isEmpty()) { return {}; }
            auto tree=entities->getEntityTree();
            const auto first=tree->featureEntityInventory();
            if (!first.value("complete").toBool()) { return {}; }
            QVariantList rows;
            for (const auto& entry:first.value("entities").toList()) {
                const auto id=entry.toMap().value("id").toString();
                const auto item=tree->findEntityByID(QUuid(id));if (!item) { return {}; }
                IOSCreateLifetimes::instance().observe(item);
                const auto p=item->getProperties();
                if (p.getName().size()>256 || p.getModelURL().size()>4096 || p.getTextures().size()>8192
                        || p.getSourceUrl().size()>4096 || p.getUserData().size()>8192) { return {}; }
                const auto host=p.getEntityHostType();const auto dimensions=p.getDimensions();
                const auto position=p.getPosition();const auto rotation=p.getRotation();
                QVariantMap model,voxels;
                if (auto original=std::dynamic_pointer_cast<ModelEntityWrapper>(item)) {
                    const auto actual=original->featureCreateModel();
                    const bool loaded=actual && actual->isLoaded();
                    model={{"present",bool(actual)},{"loaded",loaded},{"addedToScene",actual && actual->isAddedToScene()},
                        {"failed",actual && actual->didVisualGeometryRequestFail()},
                        {"textures",loaded ? actual->getGeometry()->featureCreateTextures() : QVariantList{}}};
                }
                if (auto original=std::dynamic_pointer_cast<PolyVoxEntityItem>(item)) {
                    const bool ready=original->isVoxelDataReady();const auto bytes=original->getVoxelData();
                    const auto volume=original->getVoxelVolumeSize();
                    voxels={{"ready",ready},{"bytes",bytes.size()},
                        {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
                        {"volume",QVariantList{volume.x,volume.y,volume.z}},{"onCount",original->getOnCount()}};
                }
                rows.append(QVariantMap{{"id",id},{"name",p.getName()},{"type",EntityTypes::getEntityTypeName(p.getType())},
                    {"hostType",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
                    {"dimensions",QVariantList{dimensions.x,dimensions.y,dimensions.z}},
                    {"position",QVariantList{position.x,position.y,position.z}},
                    {"rotation",QVariantList{rotation.x,rotation.y,rotation.z,rotation.w}},
                    {"shape",p.getShapeAsString()},{"modelURL",p.getModelURL()},
                    {"sourceUrl",p.getSourceUrl()},{"userData",p.getUserData()},{"collisionless",p.getCollisionless()},
                    {"textures",p.getTextures()},{"lastEditedBy",p.getLastEditedBy().toString(QUuid::WithoutBraces)},
                    {"createdEpochUs",QString::number(p.getCreated())},{"lastEditedEpochUs",QString::number(p.getLastEdited())},
                    {"locked",p.getLocked()},{"visible",p.getVisible()},{"model",model},{"voxels",voxels}});
            }
            const auto last=tree->featureEntityInventory();
            if (!last.value("complete").toBool() || first!=last) { return {}; }
            bool complete=true;QSet<QQuickItem*> visited;
            std::function<void(QQuickItem*,int)> visit=[&](QQuickItem* item,int depth) {
                if (!item || !complete || visited.contains(item)) { return; }
                if (depth>128 || visited.size()>=8192 || item->thread()!=QCoreApplication::instance()->thread()) { complete=false;return; }
                visited.insert(item);
                if (!createComponentSource(item).isEmpty() || createFileBrowser(item)==item || createPolyVoxDialog(item)==item) {
                    auto id=item->property("_overteE2ECreateRootId").toString();
                    if (id.isEmpty()) {
                        id=QUuid::createUuid().toString(QUuid::WithoutBraces);
                        item->setProperty("_overteE2ECreateRootId",id);
                    }
                    if (!_roots.contains(id)) {
                        if (_roots.size()>=64) { complete=false;return; }
                        _roots.insert(id,item);_births.append(id);
                    } else if (_roots.value(id)!=item) { complete=false;return; }
                }
                for (auto child:item->childItems()) { visit(child,depth+1); }
            };
            for (auto input:inputs) {
                if (!input || !input->window()) { complete=false;continue; }
                visit(input->window()->contentItem(),0);
            }
            QVariantList roots;
            for (const auto& id:_births) {
                const auto item=_roots.value(id).data();
                QVariantMap row{{"id",id},{"destroyed",!item}};
                if (item) {
                    const bool visible=item->window() && !NormalControlUi::visibleRect(item,item->window()).isEmpty();
                    row["visible"]=visible;row["active"]=shown && visible;
                    if (auto file=createFileBrowser(item)) {
                        row["kind"]=createFileRole(file);row["picker"]=createFileObservation(file).toVariantMap();
                    } else if (createPolyVoxDialog(item)==item) {
                        row["kind"]="polyvox";QVariantMap original{{"componentSource",createPolyVoxSource(item)}};
                        const auto objects=item->findChildren<QQuickItem*>();
                        if (objects.size()>4096) { return {}; }
                        for (const auto& name:QStringList{"initialShape","surfaceStyle","texturePreset","volumeSizeX","volumeSizeY","volumeSizeZ",
                                "xTextureURL","yTextureURL","zTextureURL","button1"}) {
                            QQuickItem* found=nullptr;
                            for (auto object:objects) {
                                if (loginQmlId(object,name)) {
                                    if (found) { return {}; }found=object;
                                }
                            }
                            if (!found) { return {}; }
                            const auto property=name=="button1" ? "enabled" :
                                (name=="initialShape" || name=="surfaceStyle" || name=="texturePreset") ? "currentIndex" : "text";
                            const auto value=found->property(property);
                            if (!value.isValid()) { return {}; }original[name]=value;
                        }
                        row["dialog"]=original;
                    } else {
                        QJsonObject page;appendCreateControlObservation(page,item,"create.page");
                        if (!page.contains("profile")) { complete=false;return {}; }
                        row["kind"]="editor";row["page"]=page.toVariantMap();
                        row["changed"]=createVariant(item->property("changed"));
                        row["voxelSettings"]=createVariant(item->property("voxelSettings"));
                        const auto numeric=item->property("focusedNumber");
                        if (numeric.userType()==qMetaTypeId<QJSValue>()) {
                            const auto js=numeric.value<QJSValue>();
                            if (!js.isNull() && !js.isQObject()) { return {}; }
                            row["numericFocus"]=js.isQObject() && js.toQObject()!=nullptr;
                        } else if (numeric.canConvert<QObject*>()) { row["numericFocus"]=numeric.value<QObject*>()!=nullptr; }
                        else { return {}; }
                    }
                }
                roots.append(row);
            }
            if (!complete) { _complete=false; }
            const auto& camera=qApp->getCamera();ViewFrustum frustum;camera.loadViewFrustum(frustum);
            const auto position=frustum.getPosition();const auto orientation=frustum.getOrientation();const auto ui=qApp->getUiSize();
            return {{"complete",complete && _complete},{"tabletShown",shown},{"domainId",domainId},
                {"localSessionId",DependencyManager::get<NodeList>()->getSessionUUID().toString(QUuid::WithoutBraces)},
                {"canRez",entities->canRez()},{"canRezTmp",entities->canRezTmp()},
                {"tree",first},{"entities",rows},{"roots",roots},
                {"view",QVariantMap{{"position",QVariantList{position.x,position.y,position.z}},
                    {"rotation",QVariantList{orientation.x,orientation.y,orientation.z,orientation.w}},
                    {"fieldOfViewDegrees",frustum.getFieldOfView()},{"aspectRatio",frustum.getAspectRatio()},
                    {"perspective",frustum.isPerspective()},{"uiWidth",ui.x},{"uiHeight",ui.y}}}};
        });
        if (!result.isEmpty()) { result.insert("iosCreateStateVersion",3); }
        return result;
    }
private:
    NativeReadBracket _bracket;
    QHash<QString,QPointer<QQuickItem>> _roots;
    QStringList _births;
    bool _complete {true};
};
} // namespace overte::e2e
#endif
