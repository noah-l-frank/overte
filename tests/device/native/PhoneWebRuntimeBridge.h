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
            || (object.value("action")!=QJsonValue("feature-phone-web-runtime-observe")
                && object.value("action")!=QJsonValue("feature-phone-web-reference-runtime-observe"))
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(object.value("commandId").toString()).hasMatch()) { return false; }
    if (object.value("action")==QJsonValue("feature-phone-web-reference-runtime-observe")) {
        const auto run=object.value("runId").toString(),raw=object.value("fixtureUrl").toString();const QUrl url(raw,QUrl::StrictMode);
        return object.value("schemaVersion")==QJsonValue(1) && QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
            && raw.size()<=512 && !raw.contains(QRegularExpression("[\\x00-\\x20\\x7f]")) && url.isValid()
            && (url.scheme()=="http" || url.scheme()=="https") && !url.host().isEmpty() && url.userInfo().isEmpty()
            && !raw.section('/',2,2).contains('@') && !url.hasQuery() && !url.hasFragment() && url.path()=="/parity/";
    }
    auto original=input;original.insert("action","feature-web-dom-observe");original.insert("surface","world");
    return webDOMCommand(original);
}
inline const char* phoneWebRuntimeProperty() { return "_overteE2EPhoneWebRuntimeProviderV1"; }
}
Q_DECLARE_METATYPE(overte::e2e::PhoneWebRuntimeProvider)
#endif
