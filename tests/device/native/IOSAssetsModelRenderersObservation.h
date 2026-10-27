// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <RenderableModelEntityItem.h>
#include <NodeList.h>
#include <algorithm>
#include <cmath>

namespace overte::e2e {
// Passive current render-item/bound inventory. A Model's actual mesh bound is
// separate from its requested entity dimensions and from original draw pixels.
// No Model/payload is retained after this read and no lifetime verdict follows.
class IOSAssetsModelRenderersObservation {
public:
    QVariantMap read(const QString& request,const QString& run,EntityScriptingInterface* entities,const QString& domain) {
        return _bracket.read("iosAssetsModelRenderersVersion","native-main-assets-model-renderers",request,run,[&]() -> QVariantMap {
            if (!entities || !entities->getEntityTree()) {return {};}
            const auto tree=entities->getEntityTree();const auto before=tree->featureEntityInventory();
            if (!before.value("complete").toBool()) {return {};}QVariantList models;int items=0;
            for (const auto& value:before.value("entities").toList()) {
                const auto id=value.toMap().value("id").toString();const auto entity=tree->findEntityByID(QUuid(id));
                if (!entity) {return {};}
                const auto wrapper=std::dynamic_pointer_cast<ModelEntityWrapper>(entity);if (!wrapper) {continue;}
                const auto actual=wrapper->featureCreateModel();const auto first=model(actual);
                if (first.isEmpty()) {return {};}
                // Read actual mesh state twice. A changed payload/bound is
                // unavailable, rather than filled from entity properties.
                if (first!=model(actual)) {return {};}
                const auto current=wrapper->featureCreateModel();if (current!=actual) {return {};}
                const auto count=first.value("renderItemIds").toList().size();
                if (count>4096-items) {return {};}items+=count;
                auto row=first;row.insert("entityId",id);models.append(row);
            }
            const auto after=tree->featureEntityInventory();if (before!=after || !after.value("complete").toBool()) {return {};}
            return {{"complete",true},{"domainId",domain},
                {"localSessionId",DependencyManager::get<NodeList>()->getSessionUUID().toString(QUuid::WithoutBraces)},
                {"tree",before},{"models",models},{"renderedPixelsAvailable",false},{"resourceRetirementAvailable",false}};
        });
    }
private:
    static QVariantMap model(const ModelPointer& actual) {
        const bool loaded=actual && actual->isLoaded(),added=actual && actual->isAddedToScene();
        const bool renderable=actual && actual->isRenderable(),fixup=actual && actual->needsFixupInScene();
        QVariantList ids;
        if (actual) {
            auto items=actual->fetchRenderItemIDs();if (items.size()>4096) {return {};}
            std::sort(items.begin(),items.end());render::ItemID previous{render::Item::INVALID_ITEM_ID};
            for (const auto id:items) {
                if (!render::Item::isValidID(id) || id==previous) {return {};}
                ids.append(qulonglong(id));previous=id;
            }
        }
        const bool meshReady=loaded && added && renderable && !fixup && !ids.isEmpty();
        const auto box=meshReady ? actual->getRenderableMeshBound() : AABox();
        const auto corner=box.getCorner(),size=box.getDimensions();
        // Planar meshes are valid: a zero depth is not an empty 2-D subject.
        const bool bounded=meshReady && !box.isInvalid() && std::isfinite(corner.x) && std::isfinite(corner.y) && std::isfinite(corner.z)
            && std::isfinite(size.x) && std::isfinite(size.y) && std::isfinite(size.z)
            && size.x>=0.0f && size.y>=0.0f && size.z>=0.0f
            && (int(size.x>0.0f)+int(size.y>0.0f)+int(size.z>0.0f)>=2);
        return {{"present",bool(actual)},{"loaded",loaded},{"addedToScene",added},{"renderable",renderable},{"needsFixup",fixup},
            {"visible",actual && actual->isVisible()},{"failed",actual && actual->didVisualGeometryRequestFail()},
            {"origin",actual ? QVariant(actual->featureAssetsModelOrigin()) : QVariant()},
            {"renderItemIds",ids},{"boundsReady",bounded},{"bounds",bounded ? QVariant(QVariantMap{
                {"corner",QVariantList{corner.x,corner.y,corner.z}},{"dimensions",QVariantList{size.x,size.y,size.z}}}) : QVariant()}};
    }
    NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
