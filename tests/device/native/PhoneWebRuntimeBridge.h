// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "WebDOMObservationBridge.h"
namespace overte::e2e {
struct PhoneWebRuntimeProvider {
    std::function<QVariantMap(const QVariantMap&)> observe;
    explicit operator bool() const { return bool(observe); }
    QVariantMap operator()(const QVariantMap& command) const { return observe ? observe(command) : QVariantMap(); }
};
inline bool phoneWebRuntimeCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
    if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId","fixtureUrl"}
            || object.value("action")!=QJsonValue("feature-phone-web-runtime-observe")
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("commandId").toString()).hasMatch()) { return false; }
    auto original=input;original.insert("action","feature-web-dom-observe");original.insert("surface","world");
    return webDOMCommand(original);
}
inline const char* phoneWebRuntimeProperty() { return "_overteE2EPhoneWebRuntimeProviderV1"; }
}
Q_DECLARE_METATYPE(overte::e2e::PhoneWebRuntimeProvider)
#endif
