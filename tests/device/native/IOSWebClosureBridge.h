// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS)
#include <functional>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QUrl>
#include <QVariant>
namespace overte::ios::feature_closures {
using Provider = std::function<QVariantMap(const QVariantMap&)>;
inline const char* providerProperty() { return "_overteE2EIOSWebClosureProviderV1"; }
inline bool command(const QVariantMap& value) {
    const QSet<QString> fields {"schemaVersion", "commandId", "action", "runId", "fixtureUrl"};
    if (QSet<QString>(value.keyBegin(), value.keyEnd()) != fields || QJsonObject::fromVariantMap(value).value("schemaVersion") != QJsonValue(1)
            || value.value("action").toString() != "feature-ios-web-closures"
            || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(value.value("commandId").toString()).hasMatch()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.value("runId").toString()).hasMatch()) { return false; }
    for (const auto* key : {"commandId", "action", "runId", "fixtureUrl"}) {
        if (value.value(key).typeId() != QMetaType::QString) { return false; }
    }
    const auto root = value.value("fixtureUrl").toString(); const QUrl url(root);
    return root.size() <= 512 && !root.contains(QRegularExpression("[\\x00-\\x20\\x7f]"))
        && url.isValid() && (url.scheme() == "http" || url.scheme() == "https") && !url.host().isEmpty()
        && url.userName().isEmpty() && url.password().isEmpty() && !url.hasQuery() && !url.hasFragment()
        && url.path() == "/feature-fixture/v1/runs/" + value.value("runId").toString() + "/"
        && url.toString(QUrl::FullyEncoded) == root;
}
} // namespace overte::ios::feature_closures
Q_DECLARE_METATYPE(overte::ios::feature_closures::Provider)
#endif
