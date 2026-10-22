// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "NormalCreateControls.h"
#include "NormalControlUi.h"
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <RenderableModelEntityItem.h>
#include <PolyVoxEntityItem.h>
#include <QPointer>
#include <QSet>
#include <algorithm>

namespace overte::e2e {
class IOSCreateStateObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const QList<QQuickItem*>& inputs,
            bool shown,EntityScriptingInterface* entities,const QString& domainId) {
        return _bracket.read("iosCreateStateVersion","native-main-create",request,run,[&]() -> QVariantMap {
            if (!entities || !entities->getEntityTree() || inputs.isEmpty()) { return {}; }
            auto tree=entities->getEntityTree();
            const auto first=tree->featureEntityInventory();
            if (!first.value("complete").toBool()) { return {}; }
            QVariantList rows;
            for (const auto& entry:first.value("entities").toList()) {
                const auto id=entry.toMap().value("id").toString();
                const auto item=tree->findEntityByID(QUuid(id));if (!item) { return {}; }
                const auto p=item->getProperties();
                if (p.getName().size()>256 || p.getModelURL().size()>4096 || p.getTextures().size()>8192) { return {}; }
                const auto host=p.getEntityHostType();const auto dimensions=p.getDimensions();
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
                    {"dimensions",QVariantList{dimensions.x,dimensions.y,dimensions.z}},{"shape",p.getShape()},{"modelURL",p.getModelURL()},
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
                if (!createComponentSource(item).isEmpty() || createFileBrowser(item)==item) {
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
            return {{"complete",complete},{"tabletShown",shown},{"domainId",domainId},
                {"canRez",entities->canRez()},{"canRezTmp",entities->canRezTmp()},
                {"tree",first},{"entities",rows},{"roots",roots}};
        });
    }
private:
    NativeReadBracket _bracket;
    QHash<QString,QPointer<QQuickItem>> _roots;
    QStringList _births;
};
} // namespace overte::e2e
#endif
