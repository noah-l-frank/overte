// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QVariant>
#include <functional>
namespace overte::e2e {
using PicoSnapshotCancelProvider=std::function<QVariantMap(const QVariantMap&,const QVariantMap&)>;
inline const char* picoSnapshotCancelProperty() {return "_overteE2EPicoSnapshotCancelV1";}
inline bool picoSnapshotCancelCommand(const QVariantMap& command) {
    const auto value=QJsonObject::fromVariantMap(command);const auto keys=value.keys();
    QSet<QString> expected{"schemaVersion","commandId","action","runId","jobId","operation","request"};
    if(value.contains("closedReadWorkRequestId")) {expected.insert("closedReadWorkRequestId");}
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if(QSet<QString>(keys.begin(),keys.end())!=expected || value.value("schemaVersion")!=QJsonValue(1)
            || value.value("action")!="feature-pico-snapshot-cancel" || !value.value("request").isObject()) {return false;}
    for(const auto& key:{"commandId","runId","jobId"}) {
        if(!value.value(key).isString() || !nonce.match(value.value(key).toString()).hasMatch()) {return false;}
    }
    const auto operation=value.value("operation");
    if(!operation.isString() || !QStringList{"start","observe","retire"}.contains(operation.toString())
            || (operation!="start" && !value.value("request").toObject().isEmpty())) {return false;}
    return !value.contains("closedReadWorkRequestId") || (operation!="start" && value.value("closedReadWorkRequestId").isString()
        && nonce.match(value.value("closedReadWorkRequestId").toString()).hasMatch());
}
} // namespace overte::e2e
Q_DECLARE_METATYPE(overte::e2e::PicoSnapshotCancelProvider)
#endif
