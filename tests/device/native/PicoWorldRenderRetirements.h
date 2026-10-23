// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
inline bool picoWorldRetirementsCommand(const QVariantMap& command) {
    const auto json=QJsonObject::fromVariantMap(command);
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript")
            || command.keys()!=QStringList{"action","captures","commandId","runId","schemaVersion"}
            || json.value("schemaVersion")!=QJsonValue(1)
            || json.value("action")!=QJsonValue("feature-pico-world-render-retirements")
            || !json.value("commandId").isString() || !nonce.match(json.value("commandId").toString()).hasMatch()
            || !json.value("runId").isString() || !nonce.match(json.value("runId").toString()).hasMatch()
            || !json.value("captures").isArray()
            || QJsonDocument(json).toJson(QJsonDocument::Compact).size()>49152) { return false; }
    const auto captures=json.value("captures").toArray();QSet<QString> requests,receipts;
    if (captures.isEmpty() || captures.size()>256) { return false; }
    for (const auto& value:captures) {
        if (!value.isObject()) { return false; }
        const auto capture=value.toObject();auto keys=capture.keys();keys.sort();
        if (keys!=QStringList{"receiptIds","requestId"} || !capture.value("requestId").isString()
                || !nonce.match(capture.value("requestId").toString()).hasMatch()
                || requests.contains(capture.value("requestId").toString()) || !capture.value("receiptIds").isArray()) { return false; }
        requests.insert(capture.value("requestId").toString());const auto ids=capture.value("receiptIds").toArray();
        if (ids.isEmpty() || ids.size()>1024) { return false; }
        for (const auto& id:ids) {
            if (!id.isString() || !nonce.match(id.toString()).hasMatch() || receipts.contains(id.toString())) { return false; }
            receipts.insert(id.toString());if(receipts.size()>1024) { return false; }
        }
    }
    return true;
}

// One GUI dispatch obtains all original inventories inside the same bounded
// source window. The callback is the existing complete native receipts getter,
// always with inspect; no release, removal or requested verdict is introduced.
template<class Inspect> QVariantMap picoWorldRetirementsObservation(const QVariantMap& command,quint64& sequence,Inspect inspect) {
    if (!picoWorldRetirementsCommand(command) || sequence>=9007199254740991ULL) { return {}; }
    QElapsedTimer elapsed;elapsed.start();
    const auto requested=QDateTime::currentMSecsSinceEpoch();QVariantList originals;QString instance;
    for (const auto& value:command.value("captures").toList()) {
        const auto capture=value.toMap();const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        const auto original=inspect(QVariantMap{{"schemaVersion",1},{"commandId",id},{"action","feature-world-render-receipts"},
            {"requestId",capture.value("requestId")},{"receiptIds",capture.value("receiptIds")},{"operation","inspect"}});
        if (elapsed.elapsed()>=1500 || original.isEmpty() || original.value("commandId")!=QVariant(id) || original.value("operation")!=QVariant("inspect")
                || original.value("requestId")!=capture.value("requestId") || original.value("instance").toString().isEmpty()) { return {}; }
        if (instance.isEmpty()) { instance=original.value("instance").toString(); }
        if (original.value("instance")!=QVariant(instance)) { return {}; }
        originals.append(original);
    }
    const auto captured=QDateTime::currentMSecsSinceEpoch();
    if (captured<requested || captured-requested>=1500) { return {}; }
    const QVariantMap result{{"worldRenderRetirementsVersion",1},{"requestId",command.value("commandId")},
        {"runId",command.value("runId")},{"instance",instance},{"sequence",static_cast<qulonglong>(++sequence)},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},{"capturedEpochMs",captured},{"captures",originals}};
    if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>200000) { return {}; }
    const auto ended=QDateTime::currentMSecsSinceEpoch();
    if (ended<captured || ended-requested>=1500 || elapsed.elapsed()>=1500) { return {}; }
    return result;
}
} // namespace overte::e2e
#endif
