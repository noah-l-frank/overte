// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QNetworkReply>
#include <QRegularExpression>
#include <QUuid>
#include <QThread>
#include <QVariantMap>
namespace overte::e2e {
// Passive original HTTPResourceRequest completion before the consumer reads
// bytes. Peek never drains the reply. Only owned fixture paths are retained.
class FeatureResourceReplies {
public:
    static FeatureResourceReplies& instance() { static FeatureResourceReplies value;return value; }
    void completed(QNetworkReply* reply,const QUrl& original) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !reply) { return; }
        const auto match=QRegularExpression("\\A/feature-fixture/v1/runs/([0-9a-f]{32})/tickets/([0-9a-f]{32})/(avatar-a\\.fst|missing\\.fst|mannequin/[A-Za-z0-9_.-]+|gltf-bundle/(?:main\\.gltf|mesh/triangle\\.bin|textures/checker\\.png))\\z").match(original.path());
        if (!match.hasMatch()) { return; }QMutexLocker guard(&_mutex);
        if (!reply->isFinished() || reply->thread()!=QThread::currentThread()) { _complete=false;return; }
        int headers=0;for (const auto& pair:reply->rawHeaderPairs()) { if (pair.first.toLower()=="x-overte-fixture-response") { ++headers; } }
        const auto response=QString::fromLatin1(reply->rawHeader("X-Overte-Fixture-Response"));
        if (headers>1 || !response.isEmpty() && !QRegularExpression("\\A[0-9a-f]{32}\\z").match(response).hasMatch()) { _complete=false;return; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<1 || now<_epoch || _rows.size()>=1024) { _complete=false;return; }_epoch=now;
        constexpr qint64 LIMIT=16*1024*1024;
        if (reply->bytesAvailable()<0 || reply->bytesAvailable()>LIMIT) { _complete=false;return; }
        const auto raw=reply->peek(LIMIT+1);
        if (raw.size()!=reply->bytesAvailable() || raw.size()>LIMIT) { _complete=false;return; }
        auto hash=[](const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); };
        _rows.append(QVariantMap{{"sequence",_rows.size()+1},{"runId",match.captured(1)},{"ticket",match.captured(2)},
            {"resource",match.captured(3)},{"requestedUrlSha256",hash(original.toString().toUtf8())},
            {"replyUrlSha256",hash(reply->url().toString().toUtf8())},{"responseId",QString::fromLatin1(reply->rawHeader("X-Overte-Fixture-Response"))},
            {"httpStatus",reply->attribute(QNetworkRequest::HttpStatusCodeAttribute)},{"networkError",int(reply->error())},
            {"fromCache",reply->attribute(QNetworkRequest::SourceIsFromCacheAttribute).toBool()},
            {"redirected",reply->attribute(QNetworkRequest::RedirectionTargetAttribute).isValid() || reply->url()!=original},
            {"capturedEpochMs",now},{"bytes",raw.size()},{"sha256",hash(raw)}});
    }
    QVariantMap snapshot(const QString& run) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
        QMutexLocker guard(&_mutex);QVariantList rows;for (const auto& row:_rows) { if (row.toMap().value("runId")==run) { rows.append(row); } }
        const auto now=QDateTime::currentMSecsSinceEpoch();if (now<1 || now<_epoch) { _complete=false;return {}; }_epoch=now;
        return {{"resourceRepliesVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"capturedEpochMs",now},{"complete",_complete},{"runId",run},{"events",rows}};
    }
private:
    QMutex _mutex;QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantList _rows;quint64 _sequence{0};qint64 _epoch{0};bool _complete{true};
};
}
#endif
