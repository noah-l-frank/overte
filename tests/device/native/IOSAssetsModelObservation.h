// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSAssetsModelOrigin.h"
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <RenderableModelEntityItem.h>
#include <NodeList.h>

namespace overte::e2e {
class IOSAssetsModelObservation {
public:
    QVariantMap read(const QString& request,const QString& run,EntityScriptingInterface* entities,const QString& domain) {
        return _bracket.read("iosAssetsModelOriginVersion","native-main-assets-model-origin",request,run,[&]() -> QVariantMap {
            if (!entities || !entities->getEntityTree()) {return {};}
            const auto tree=entities->getEntityTree();const auto before=tree->featureEntityInventory();
            if (!before.value("complete").toBool()) {return {};}QVariantList models;
            for (const auto& value:before.value("entities").toList()) {
                const auto id=value.toMap().value("id").toString();const auto item=tree->findEntityByID(QUuid(id));
                if (!item) {return {};}
                const auto wrapper=std::dynamic_pointer_cast<ModelEntityWrapper>(item);if (!wrapper) {continue;}
                const auto actual=wrapper->featureCreateModel();
                models.append(QVariantMap{{"entityId",id},{"present",bool(actual)},
                    {"loaded",actual && actual->isLoaded()},{"addedToScene",actual && actual->isAddedToScene()},
                    {"failed",actual && actual->didVisualGeometryRequestFail()},
                    {"origin",actual ? QVariant(actual->featureAssetsModelOrigin()) : QVariant()}});
            }
            const auto after=tree->featureEntityInventory();if (before!=after || !after.value("complete").toBool()) {return {};}
            const auto history=IOSAssetsModelOrigin::shared().snapshot();if (history.isEmpty()) {return {};}
            return {{"complete",history.value("complete")},{"domainId",domain},
                {"localSessionId",DependencyManager::get<NodeList>()->getSessionUUID().toString(QUuid::WithoutBraces)},
                {"tree",before},{"models",models},{"history",history},
                // A consumed definition has no cache/texture/decoder lifetime inventory.
                {"resourceRetirementAvailable",false}};
        });
    }
private:NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
