// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <ScriptEngines.h>
namespace overte::e2e {
class IOSAvatarScriptsObservation {
public:
    QVariantMap read(const QString& request,const QString& run,ScriptEngines* scripts) {
        return _bracket.read("iosAvatarScriptsVersion","native-main-avatar-scripts",request,run,[&]() -> QVariantMap {
            return scripts ? scripts->featureAvatarScriptObservation() : QVariantMap();
        });
    }
private: NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
