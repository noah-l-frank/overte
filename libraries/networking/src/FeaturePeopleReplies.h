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
#include <QThread>
#include <QUuid>
namespace overte::e2e {
// Original XMLHttpRequest completion, before scripts consume its response.
// No authorization bytes or body bytes are retained. A matching fixture wire
// ID is discovery only; the host separately joins its exact owned TLS origin.
class FeaturePeopleReplies {
public:
    static FeaturePeopleReplies& instance() { static FeaturePeopleReplies source;return source; }
    void completed(QNetworkReply* reply,const QUrl& requested,const QString& method,const QByteArray& body) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !reply) { return; }
        if (requested.scheme()!="https" || !requested.userInfo().isEmpty() || requested.hasFragment()
                || !QRegularExpression("\\A/api/v1/(?:user/connection_request|users(?:/connections)?|user/connections/[A-Za-z0-9_-]{1,128})\\z").match(requested.path()).hasMatch()) { return; }
        const auto response=QString::fromLatin1(reply->rawHeader("X-Overte-Fixture-Response"));
        if (response.isEmpty()) { return; }QMutexLocker guard(&_mutex);
        int headers=0;for (const auto& header:reply->rawHeaderPairs()) { if (header.first.toLower()=="x-overte-fixture-response") { ++headers; } }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (headers!=1 || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(response).hasMatch()
                || !reply->isFinished() || reply->thread()!=QThread::currentThread() || _rows.size()>=512
                || body.size()>65536 || now<1 || now<_epoch || reply->bytesAvailable()<0 || reply->bytesAvailable()>65536) { _complete=false;return; }
        const auto raw=reply->peek(65537);if (raw.size()!=reply->bytesAvailable() || raw.size()>65536) { _complete=false;return; }_epoch=now;
        _rows.append(QVariantMap{{"eventSequence",_rows.size()+1},{"responseId",response},{"method",method},
            {"requestedUrlSha256",hash(requested.toString().toUtf8())},{"replyUrlSha256",hash(reply->url().toString().toUtf8())},
            {"requestBodySha256",hash(body)},{"httpStatus",reply->attribute(QNetworkRequest::HttpStatusCodeAttribute)},
            {"networkError",int(reply->error())},{"fromCache",reply->attribute(QNetworkRequest::SourceIsFromCacheAttribute).toBool()},
            {"redirected",reply->url()!=requested || reply->attribute(QNetworkRequest::RedirectionTargetAttribute).isValid()},
            {"capturedEpochMs",now},{"bytes",raw.size()},{"sha256",hash(raw)}});
    }
    QVariantMap snapshot() {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        QMutexLocker guard(&_mutex);const auto now=QDateTime::currentMSecsSinceEpoch();if (now<1 || now<_epoch) { _complete=false;return {}; }_epoch=now;
        return {{"peopleRepliesVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"capturedEpochMs",now},{"complete",_complete},{"events",_rows}};
    }
private:
    static QString hash(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
    QMutex _mutex;QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantList _rows;quint64 _sequence{0};qint64 _epoch{0};bool _complete{true};
};
}
#endif
