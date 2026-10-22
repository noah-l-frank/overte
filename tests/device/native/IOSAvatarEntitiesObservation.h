// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <AvatarEntityObservation.h>

namespace overte::e2e {
class IOSAvatarEntitiesObservation {
public:
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosAvatarEntitiesVersion","native-main-avatar-entities",request,run,[] {
            return AvatarEntityObservation::instance().snapshot();
        });
    }
private:
    NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
