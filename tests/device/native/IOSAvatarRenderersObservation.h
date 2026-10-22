// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "../../../interface/src/avatar/AvatarManager.h"
#include <EntityTree.h>
#include <RenderableModelEntityItem.h>
#include <QMap>

namespace overte::e2e {
// Loaded render-model facts, separate from the independently received Avatar
// packet/joint originals. No advertised URL is relabeled as loaded geometry.
class IOSAvatarRenderersObservation {
public:
    QVariantMap read(const QString& request,const QString& run,AvatarManager* avatars,const EntityTreePointer& tree) {
        auto result=_bracket.read("iosAvatarRenderersVersion","native-main-avatar-renderers",request,run,[&]() -> QVariantMap {
            if (!avatars || !tree) { return {}; }
            const auto before=tree->featureEntityInventory();
            if (before.isEmpty() || !before.value("complete").toBool()) { return {}; }
            const auto hash=avatars->getHashCopy();if (hash.size()>64) { return {}; }
            QMap<QString,QVariant> originalAvatars;
            for (auto it=hash.constBegin();it!=hash.constEnd();++it) {
                const auto avatar=std::dynamic_pointer_cast<Avatar>(it.value());
                if (!avatar || avatar->getSessionUUID().isNull()) { return {}; }
                const auto id=avatar->getSessionUUID().toString(QUuid::WithoutBraces);
                if (originalAvatars.contains(id)) { return {}; }
                const auto model=avatar->getSkeletonModel();if (!model) { return {}; }
                const bool geometry=model->isLoaded();const auto joints=avatar->getJointNames();
                if (joints.size()>1024) { return {}; }
                QVariantMap jointIndices;for (const auto& name:joints) { jointIndices.insert(name,avatar->getJointIndex(name)); }
                const auto rigOriginal=model->getRig().e2eAnimationObservation();QVariantMap rigPose;
                if (!rigOriginal.isEmpty()) {
                    for (const auto& key:QStringList {"rigId","capturedEpochMs","evaluationSequence","animationsEnabled",
                            "graphLoaded","overrideActive","joints"}) {
                        if (!rigOriginal.contains(key)) { return {}; }rigPose.insert(key,rigOriginal.value(key));
                    }
                }
                originalAvatars.insert(id,QVariantMap {{"sessionId",id},{"self",avatar->isMyAvatar()},
                    {"replicated",avatar->getIsReplicated()},
                    {"requestedUrl",avatar->getSkeletonModelURL().toString(QUrl::FullyEncoded)},
                    {"resourceUrl",model->getURL().toString(QUrl::FullyEncoded)},
                    {"geometryLoaded",geometry},{"rigReady",geometry && model->getRig().getAnimNode()!=nullptr && !joints.isEmpty()},
                    {"shouldRender",avatar->shouldRender()},{"addedToScene",model->isAddedToScene()},
                    {"targetScale",avatar->getTargetScale()},{"modelScale",avatar->getModelScale()},
                    {"jointNames",joints},{"jointIndices",jointIndices},{"hipsIndex",avatar->getJointIndex("Hips")},
                    {"rigPose",rigPose.isEmpty() ? QVariant() : QVariant(rigPose)}});
            }
            QVariantList attachments;
            for (const auto& entry:before.value("entities").toList()) {
                const auto id=entry.toMap().value("id").toString();
                const auto entity=tree->findEntityByID(QUuid(id));if (!entity) { return {}; }
                const auto properties=entity->getProperties();
                // Full actual avatar-host inventory, including hidden and
                // detached entries. An owned wearable is later joined by its
                // original creation ID, never guessed by name or URL.
                if (properties.getEntityHostType()!=entity::HostType::AVATAR) { continue; }
                const auto wrapper=std::dynamic_pointer_cast<ModelEntityWrapper>(entity);
                const auto model=wrapper ? wrapper->featureCreateModel() : ModelPointer();
                const auto parent=properties.getParentID();
                attachments.append(QVariantMap {{"id",id},{"name",properties.getName()},
                    {"type",EntityTypes::getEntityTypeName(properties.getType())},
                    {"parentId",parent.toString(QUuid::WithoutBraces)},
                    {"parentJointIndex",properties.getParentJointIndex()},
                    {"relayParentJoints",properties.getRelayParentJoints()},
                    {"visible",properties.getVisible()},{"modelUrl",properties.getModelURL()},
                    {"resourceUrl",model ? model->getURL().toString(QUrl::FullyEncoded) : QString()},
                    {"modelAvailable",bool(model)},{"geometryLoaded",model && model->isLoaded()},
                    {"addedToScene",model && model->isAddedToScene()},
                    {"loadFailed",model && model->didVisualGeometryRequestFail()},
                    {"lastEditedEpochUs",QString::number(properties.getLastEdited())}});
            }
            const auto after=tree->featureEntityInventory();
            if (after.isEmpty() || before!=after) { return {}; }
            QVariantList rows;for (auto it=originalAvatars.constBegin();it!=originalAvatars.constEnd();++it) { rows.append(it.value()); }
            return {{"complete",true},{"avatars",rows},{"avatarEntities",attachments},{"tree",before}};
        });
        if (!result.isEmpty()) { result["iosAvatarRenderersVersion"]=2; }
        return result;
    }
private:
    NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
