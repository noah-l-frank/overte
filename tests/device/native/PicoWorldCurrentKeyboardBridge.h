// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "PicoWorldCurrentInputBridge.h"
#include <functional>
#include <QObject>
namespace overte::e2e {
inline bool picoWorldCurrentKeyboardCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
    if(QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl","operation","ownerToken","focusNonce"}
        || object.value("operation")!=QJsonValue("observe-current-keyboard")
        || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("focusNonce").toString()).hasMatch()
        || object.value("focusNonce")==object.value("commandId"))return false;
    auto base=input;base.remove("focusNonce");base.insert("operation","observe-current-document");return picoWorldCurrentDocumentCommand(base);
}
Q_DECL_EXPORT PicoCurrentAnchor picoCurrentKeyboardAnchor(const QVariantMap& command);
// Called on the original GUI thread. The callback observes the actual Keyboard;
// it receives no requested key, label, position or desired editor effect.
Q_DECL_EXPORT QVariantMap picoObserveCurrentKeyboard(const QVariantMap& command,PicoCurrentAnchor anchor,
    QObject* keyboard,const std::function<QVariantMap()>& capture);
}
#endif
