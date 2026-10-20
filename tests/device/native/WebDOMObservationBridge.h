// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <functional>
#include <QCoreApplication>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QUrl>
#include <QVariant>
namespace overte::e2e {
using WebDOMProvider=std::function<QVariantMap(const QVariantMap&)>;
inline bool webDOMCommand(const QVariantMap& input) {
    const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();
    const auto id=object.value("commandId").toString(),run=object.value("runId").toString();
    const auto surface=object.value("surface").toString();const auto raw=object.value("fixtureUrl").toString();
    const QUrl url(raw,QUrl::StrictMode);
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId","surface","fixtureUrl"}
        && object.value("schemaVersion")==QJsonValue(1) && object.value("action")==QJsonValue("feature-web-dom-observe")
        && QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch() && (surface=="world" || surface=="tablet")
        && !raw.isEmpty() && raw.size()<=512 && !raw.contains(QRegularExpression("[\\x00-\\x20\\x7f]"))
        && url.isValid() && (url.scheme()=="http" || url.scheme()=="https") && !url.host().isEmpty()
        && url.userInfo().isEmpty() && !raw.section('/',2,2).contains('@') && !url.hasQuery() && !url.hasFragment()
        && url.path()=="/feature-fixture/v1/runs/"+run+"/";
}
inline const char* webDOMProviderProperty() { return "_overteE2EOriginalWebDOMProviderV1"; }
} // namespace overte::e2e
Q_DECLARE_METATYPE(overte::e2e::WebDOMProvider)
#endif
