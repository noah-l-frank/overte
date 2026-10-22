// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <Application.h>
#include <EntityScriptingInterface.h>
#include <EntityTree.h>
#include <ViewFrustum.h>

namespace overte::e2e {
// No requested Entity IDs or geometry. Read the actual complete tree and its
// current Web entities, without retaining them beyond this original read.
class IOSWorldWebGeometryObservation {
public:
    QVariantMap read(const QString& request,const QString& run,EntityScriptingInterface* entities) {
        return _bracket.read("iosWorldWebGeometryVersion","native-main-ios-world-web-geometry",request,run,[&]() -> QVariantMap {
            if (!entities || !entities->getEntityTree()) { return {}; }
            const auto tree=entities->getEntityTree();const auto first=tree->featureEntityInventory();
            if (!first.value("complete").toBool()) { return {}; }
            QVariantList rows;
            for (const auto& entry:first.value("entities").toList()) {
                const auto original=entry.toMap();const auto id=original.value("id").toString();
                const auto item=tree->findEntityByID(QUuid(id));if (!item) { return {}; }
                const auto p=item->getProperties();if (p.getType()!=EntityTypes::Web) { continue; }
                if (rows.size()>=64 || p.getSourceUrl().size()>4096 || p.getUserData().size()>8192) { return {}; }
                const auto position=p.getPosition();const auto rotation=p.getRotation();const auto dimensions=p.getDimensions();
                const auto registration=p.getRegistrationPoint();const auto host=p.getEntityHostType();
                rows.append(QVariantMap{{"id",id},{"hostType",host==entity::HostType::LOCAL ? "local" : host==entity::HostType::AVATAR ? "avatar" : "domain"},
                    {"parentId",p.getParentID().toString(QUuid::WithoutBraces)},{"position",QVariantList{position.x,position.y,position.z}},
                    {"rotation",QVariantList{rotation.x,rotation.y,rotation.z,rotation.w}},
                    {"dimensions",QVariantList{dimensions.x,dimensions.y,dimensions.z}},
                    {"registrationPoint",QVariantList{registration.x,registration.y,registration.z}},
                    {"dpi",p.getDpi()},{"inputMode",p.getInputModeAsString()},{"billboardMode",p.getBillboardModeAsString()},
                    {"visible",p.getVisible()},{"locked",p.getLocked()},
                    {"sourceUrl",p.getSourceUrl()},{"userData",p.getUserData()},
                    {"lastEditedEpochUs",QString::number(p.getLastEdited())}});
            }
            const auto last=tree->featureEntityInventory();if (first!=last || !last.value("complete").toBool()) { return {}; }
            const auto& camera=qApp->getCamera();ViewFrustum frustum;camera.loadViewFrustum(frustum);
            const auto position=frustum.getPosition();const auto rotation=frustum.getOrientation();const auto ui=qApp->getUiSize();
            return {{"complete",true},{"tree",first},{"entities",rows},
                {"view",QVariantMap{{"position",QVariantList{position.x,position.y,position.z}},
                    {"rotation",QVariantList{rotation.x,rotation.y,rotation.z,rotation.w}},
                    {"fieldOfViewDegrees",frustum.getFieldOfView()},{"aspectRatio",frustum.getAspectRatio()},
                    {"perspective",frustum.isPerspective()},{"uiWidth",ui.x},{"uiHeight",ui.y}}}};
        });
    }
private: NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
