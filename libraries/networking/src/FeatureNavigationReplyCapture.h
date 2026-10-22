// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "RequestCancellation.h"
#include <QCoreApplication>
#include <QDateTime>
#include <QList>
#include <QMutex>
#include <QMutexLocker>
#include <QNetworkReply>
#include <QPointer>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Capture only on the actual reply owner thread, before the unchanged original
// finished connection queues its callback to AddressManager. NodeList readers
// copy immutable facts under a short mutex and never call into the GUI thread.
class NavigationReplyCapture {
public:
    void watch(QNetworkReply* reply,const overte::network::RequestTicket& ticket) {
        if (!enabled() || !ticket.scoped()) { return; }
        if (!reply || reply->thread()!=QThread::currentThread()) { fail();return; }
        {
            QMutexLocker lock(&_mutex);prune();
            if (!_valid || _entries.size()>=256) { _valid=false;return; }
            for (const auto& entry:_entries) { if (entry.reply==reply) { _valid=false;return; } }
            _entries.append({QPointer<QNetworkReply>(reply),ticket,{},false});
        }
        QObject::connect(reply,&QNetworkReply::finished,reply,[this,reply,ticket] { capture(reply,ticket); },Qt::DirectConnection);
    }
    QVariantMap original(QNetworkReply* reply,const overte::network::RequestTicket& lookup) {
        QMutexLocker lock(&_mutex);
        if (!_valid || !enabled() || !reply || !lookup.current()) { return {}; }
        for (const auto& entry:_entries) {
            if (entry.reply.data()==reply && entry.ticket.sameRequest(lookup) && entry.ticket.current()) {
                return entry.ready ? entry.facts : QVariantMap();
            }
        }
        return {};
    }
private:
    struct Entry {
        QPointer<QNetworkReply> reply;overte::network::RequestTicket ticket;QVariantMap facts;bool ready{false};
    };
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    static bool identifier(const QString& text) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(text).hasMatch(); }
    void fail() { QMutexLocker lock(&_mutex);_valid=false; }
    void prune() { for (auto i=_entries.begin();i!=_entries.end();) { if (!i->reply) { i=_entries.erase(i); }else { ++i; } } }
    void capture(QNetworkReply* reply,const overte::network::RequestTicket& ticket) {
        if (!enabled() || !reply || reply->thread()!=QThread::currentThread()) { fail();return; }
        const auto url=reply->url();
        const auto owned=QRegularExpression("\\A/api/v1/places/hidden-([0-9a-f]{32})\\z").match(url.path(QUrl::FullyEncoded));
        QVariantMap facts{{"owned",owned.hasMatch()}};
        if (!ticket.current()) {
            // A normally cancelled/superseded reply is not a corrupt source.
            // Its original callback will be discarded by the existing guard.
            facts.insert("cancelled",true);
        } else if (owned.hasMatch()) {
            const auto property=reply->property("_overte_request_ticket");
            const auto actual=property.value<overte::network::RequestTicket>();
            if (property.userType()!=qMetaTypeId<overte::network::RequestTicket>() || !actual.sameRequest(ticket)
                    || !ticket.current() || !actual.current() || (url.scheme()!="http" && url.scheme()!="https")
                    || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()) { fail();return; }
            int headers{0};QByteArray response;
            for (const auto& header:reply->rawHeaderPairs()) {
                if (header.first.toLower()=="x-overte-fixture-response") { ++headers;response=header.second; }
            }
            bool okay{false};const auto code=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
            const auto status=code.isValid()?code.toInt(&okay):0;const auto error=static_cast<int>(reply->error());
            const auto origin=url.adjusted(QUrl::RemovePath|QUrl::RemoveQuery|QUrl::RemoveFragment).toString(QUrl::FullyEncoded);
            const auto epoch=QDateTime::currentMSecsSinceEpoch();
            if (headers>1 || (!response.isEmpty() && !identifier(QString::fromLatin1(response)))
                    || (code.isValid() && !okay) || status<0 || status>599 || error<0 || error>499
                    || origin.isEmpty() || origin.size()>512 || epoch<=0) { fail();return; }
            facts={{"owned",true},{"captureId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
                {"capturedEpochMs",epoch},{"runId",owned.captured(1)},{"responseId",QString::fromLatin1(response)},
                {"origin",origin},{"httpStatus",status},{"networkError",error},{"contentNotFound",reply->error()==QNetworkReply::ContentNotFoundError}};
        }
        QMutexLocker lock(&_mutex);
        for (auto& entry:_entries) {
            if (entry.reply.data()!=reply || !entry.ticket.sameRequest(ticket)) { continue; }
            if (entry.ready) { _valid=false;return; }entry.facts=facts;entry.ready=true;return;
        }
        _valid=false;
    }
    QMutex _mutex;QList<Entry> _entries;bool _valid{true};
};
inline NavigationReplyCapture& navigationReplyCapture() { static NavigationReplyCapture source;return source; }
}
#endif
