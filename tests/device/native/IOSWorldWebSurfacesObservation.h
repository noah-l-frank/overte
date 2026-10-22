// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <DependencyManager.h>
#include <ui/OffscreenQmlSurfaceCache.h>

namespace overte::e2e {
class IOSWorldWebSurfacesObservation {
public:
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosWorldWebSurfacesVersion","native-main-ios-world-web-surfaces",request,run,[]() -> QVariantMap {
            // Passive getter may inspect only the already existing dependency.
            // No test request can create/cache/navigate an offscreen surface.
            if (!DependencyManager::isSet<OffscreenQmlSurfaceCache>()) { return {}; }
            const auto cache=DependencyManager::get<OffscreenQmlSurfaceCache>();
            return cache ? cache->featureWebSurfaceOwnership() : QVariantMap();
        });
    }
private: NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
