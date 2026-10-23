// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QDateTime>
#include <QJsonDocument>
#include <QMetaType>
#include <QRegularExpression>
#include <QSet>
#include <QVariantMap>

namespace overte::e2e {
inline bool snapshotSettingsNonce(const QString& value) {
    return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch();
}
inline bool snapshotSettingsCommand(const QVariantMap& command) {
    return command.keys()==QStringList{"commandId","runId","schemaVersion"}
        && (command.value("schemaVersion").userType()==QMetaType::Int || command.value("schemaVersion").userType()==QMetaType::Double)
        && command.value("schemaVersion").toDouble()==1 && command.value("commandId").userType()==QMetaType::QString
        && command.value("runId").userType()==QMetaType::QString && snapshotSettingsNonce(command.value("commandId").toString())
        && snapshotSettingsNonce(command.value("runId").toString());
}
inline QVariantMap snapshotSettingsOriginals(const QVariantMap& command,const QString& birth,const QVariantMap& manager,
        const QVariantMap& cache,quint64 sequence) {
    if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !snapshotSettingsCommand(command)
            || !snapshotSettingsNonce(birth) || sequence==0 || sequence>9007199254740991ULL
            || manager.keys()!=QStringList{"capturedEpochMs","entries","instance","snapshotSettingsEntriesVersion"}
            || manager.value("snapshotSettingsEntriesVersion").userType()!=QMetaType::Int || manager.value("snapshotSettingsEntriesVersion").toInt()!=1
            || manager.value("instance").userType()!=QMetaType::QString || manager.value("capturedEpochMs").userType()!=QMetaType::LongLong
            || !snapshotSettingsNonce(manager.value("instance").toString()) || manager.value("entries").userType()!=QMetaType::QVariantMap
            || cache.keys()!=QStringList{"defaultValue","initialized","set","value"}
            || cache.value("initialized").userType()!=QMetaType::Bool || cache.value("set").userType()!=QMetaType::Bool
            || cache.value("value").userType()!=QMetaType::QString || cache.value("defaultValue").userType()!=QMetaType::QString
            || cache.value("value").toString().size()>4096 || cache.value("defaultValue").toString().size()>4096
            || cache.value("value").toString().contains(QChar::Null) || cache.value("defaultValue").toString().contains(QChar::Null)) { return {}; }
    auto keys=QStringList{"alsoTakeAnimatedSnapshot","snapshotFormat","previousSnapshotHref","previousSnapshotDomainID",
        "previousStillSnapPath","previousStillSnapStoryID","previousStillSnapBlastingDisabled","previousStillSnapHifiSharingDisabled","previousStillSnapUrl",
        "previousAnimatedSnapPath","previousAnimatedSnapStoryID","previousAnimatedSnapBlastingDisabled","previousAnimatedSnapHifiSharingDisabled"};keys.sort();
    const auto entries=manager.value("entries").toMap();if (entries.keys()!=keys) { return {}; }
    for (const auto& value:entries) {
        if (value.userType()!=QMetaType::QVariantMap || value.toMap().keys()!=QStringList{"present","value"}
                || value.toMap().value("present").userType()!=QMetaType::Bool) { return {}; }
        const auto item=value.toMap().value("value");
        if ((!value.toMap().value("present").toBool() && item.isValid())
                || (item.isValid() && item.userType()!=QMetaType::Bool && item.userType()!=QMetaType::QString)) { return {}; }
    }
    const auto captured=QDateTime::currentMSecsSinceEpoch(),entriesEpoch=manager.value("capturedEpochMs").toLongLong();
    if (entriesEpoch<=0 || captured<entriesEpoch || captured-entriesEpoch>1500) { return {}; }
    const QVariantMap actual{{"entries",entries},{"formatCache",cache}};
    QByteArray bytes;QDataStream out(&bytes,QIODevice::WriteOnly);out.setVersion(QDataStream::Qt_5_12);out<<QVariant::fromValue(actual);
    if (out.status()!=QDataStream::Ok || bytes.isEmpty() || bytes.size()>32768) { return {}; }
    const QVariantMap source{{"snapshotInstance",birth},{"managerInstance",manager.value("instance")},{"entriesEpochMs",entriesEpoch},
        {"entries",entries},{"formatCache",cache},{"typedSerializedBase64",QString::fromLatin1(bytes.toBase64())},
        {"typedSha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}};
    const QVariantMap result{{"snapshotSettingsOriginalsVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
        {"pid",QCoreApplication::applicationPid()},{"sequence",static_cast<qulonglong>(sequence)},{"capturedEpochMs",captured},{"source",source}};
    return QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()<=65536 ? result : QVariantMap{};
}
}
#endif
