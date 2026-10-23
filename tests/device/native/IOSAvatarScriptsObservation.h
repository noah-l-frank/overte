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
        auto result=_bracket.read("iosAvatarScriptsVersion","native-main-avatar-scripts",request,run,[&]() -> QVariantMap {
            return scripts ? scripts->featureAvatarScriptObservation() : QVariantMap();
        });
        if (!result.isEmpty()) { result["iosAvatarScriptsVersion"]=2; }return result;
    }
private: NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
