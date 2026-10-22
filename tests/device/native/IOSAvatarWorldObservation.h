// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "../../../interface/src/avatar/AvatarManager.h"
#include <DependencyManager.h>
#include <QDateTime>
#include <QMap>
#include <QUuid>
namespace overte::e2e {
class IOSAvatarWorldObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& reader) {
        return _bracket.read("iosAvatarWorldVersion","native-main-avatar-world",request,run,[&]() -> QVariantMap {
            auto source=reader();if (source.isEmpty() || !DependencyManager::isSet<AvatarManager>()) { return {}; }
            const auto avatars=DependencyManager::get<AvatarManager>();const auto hash=avatars->getHashCopy();
            if (hash.size()>64) { return {}; }QMap<QString,QVariant> bodies;
            for (auto it=hash.constBegin();it!=hash.constEnd();++it) {
                const auto avatar=std::dynamic_pointer_cast<Avatar>(it.value());
                if (!avatar || avatar->getSessionUUID().isNull()) { return {}; }
                const auto id=avatar->getSessionUUID().toString(QUuid::WithoutBraces);
                if (bodies.contains(id)) { return {}; }
                const auto position=avatar->getWorldPosition(),velocity=avatar->getWorldVelocity();
                const auto orientation=avatar->getWorldOrientation();
                bodies.insert(id,QVariantMap{{"sessionId",id},{"self",avatar->isMyAvatar()},{"replicated",avatar->getIsReplicated()},
                    {"position",QVariantList{position.x,position.y,position.z}},
                    {"orientation",QVariantList{orientation.x,orientation.y,orientation.z,orientation.w}},
                    {"velocity",QVariantList{velocity.x,velocity.y,velocity.z}}});
            }
            source["bodies"]=QVariantMap{{"avatarBodyCollectionVersion",1},{"instance",_bodyInstance},
                {"sequence",++_bodySequence},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
                {"complete",true},{"avatars",bodies.values()}};
            return source;
        });
    }
private:
    NativeReadBracket _bracket;
    const QString _bodyInstance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _bodySequence {0};
};
} // namespace overte::e2e
#endif
