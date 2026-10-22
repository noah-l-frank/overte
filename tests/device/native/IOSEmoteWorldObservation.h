// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
namespace overte::e2e {
class IOSEmoteWorldObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& reader) {
        return _bracket.read("iosEmoteWorldVersion","native-main-emote-world",request,run,reader);
    }
private: NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
