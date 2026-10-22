// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QUuid>
#include <QUrl>
#include <QVariantMap>
namespace overte::e2e {
// Original returned ID at the successful ordinary avatar addEntity boundary.
// Discovery never grants deletion authority: the owner must also persist the
// issued normal input and verify its actual current entity/parent/model.
class FeatureAvatarEntityOrigins {
public:
    static FeatureAvatarEntityOrigins& instance() { static FeatureAvatarEntityOrigins source;return source; }
    void added(const QUuid& id,const QString& url,const QUuid& parent,int joint,bool treePresent) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return; }
        const auto match=QRegularExpression("\\A/feature-fixture/v1/runs/([0-9a-f]{32})/tickets/([0-9a-f]{32})/gltf-bundle/main\\.gltf\\z").match(QUrl(url).path());
        if (!match.hasMatch()) { return; }QMutexLocker guard(&_mutex);const auto now=QDateTime::currentMSecsSinceEpoch();
        if (id.isNull() || parent.isNull() || joint<0 || joint>65535 || _rows.size()>=256 || now<1 || now<_epoch) { _complete=false;return; }_epoch=now;
        _rows.append(QVariantMap{{"eventSequence",_rows.size()+1},{"capturedEpochMs",now},{"runId",match.captured(1)},{"ticket",match.captured(2)},
            {"entityId",id.toString(QUuid::WithoutBraces)},{"parentId",parent.toString(QUuid::WithoutBraces)},{"parentJointIndex",joint},{"treePresent",treePresent},
            {"modelUrlSha256",QString::fromLatin1(QCryptographicHash::hash(url.toUtf8(),QCryptographicHash::Sha256).toHex())}});
    }
    QVariantMap snapshot(const QString& run) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
        QMutexLocker guard(&_mutex);const auto now=QDateTime::currentMSecsSinceEpoch();if (now<1 || now<_epoch) { _complete=false;return {}; }_epoch=now;
        QVariantList rows;for (const auto& row:_rows) { if (row.toMap().value("runId")==run) { rows.append(row); } }
        return {{"avatarEntityOriginsVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},{"capturedEpochMs",now},{"runId",run},{"complete",_complete},{"events",rows}};
    }
private:
    QMutex _mutex;QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};QVariantList _rows;quint64 _sequence{0};qint64 _epoch{0};bool _complete{true};
};
}
#endif
