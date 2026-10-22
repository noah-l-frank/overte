// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QVariantMap>
namespace overte::e2e {
inline bool picoSnapshotExportCommand(const QVariantMap& command) {
    const auto value=QJsonObject::fromVariantMap(command);const auto keys=value.keys();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if(QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId","operation","exportRequest","resourceId"}
            || value.value("schemaVersion")!=QJsonValue(1) || value.value("action")!="feature-pico-snapshot-exports") {return false;}
    for(const auto& key:{"commandId","runId"}) {if(!value.value(key).isString() || !nonce.match(value.value(key).toString()).hasMatch()) {return false;}}
    for(const auto& key:{"operation","exportRequest","resourceId"}) {if(!value.value(key).isString()) {return false;}}
    const auto operation=value.value("operation").toString(),request=value.value("exportRequest").toString(),id=value.value("resourceId").toString();
    if(operation=="observe" || operation=="retire-copies") {return request.isEmpty() && id.isEmpty();}
    if(operation=="read" || operation=="remove-destination" || operation=="revoke-share") {return nonce.match(request).hasMatch() && nonce.match(id).hasMatch();}
    return QStringList{"cancel","remove-copy","inspect-destinations","inspect-shares"}.contains(operation)
        && request.isEmpty() && nonce.match(id).hasMatch();
}
} // namespace overte::e2e
#endif
