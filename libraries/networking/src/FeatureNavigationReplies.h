// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QNetworkReply>
#include <QPointer>
#include <QVector>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include "RequestCancellation.h"
#if defined(ANDROID_APP_PICO_INTERFACE)
#include "FeatureNavigationReplyCapture.h"
#endif

namespace overte::e2e {
// Passive original current AddressManager error-callback provenance only.
// No request, signal, navigation, modal, address getter or product setter.
class FeatureNavigationReplies {
public:
    explicit FeatureNavigationReplies(QObject* owner=nullptr) : _owner(owner),_boundOwner(owner!=nullptr) { _clock.start(); }
    static bool command(const QVariantMap& request) {
        const auto value=QJsonObject::fromVariantMap(request);const auto keys=value.keys();
        return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
            && value.value("schemaVersion")==QJsonValue(1) && value.value("action")==QJsonValue("feature-navigation-replies")
            && value.value("commandId").isString() && identifier(value.value("commandId").toString(),true)
            && value.value("runId").isString() && identifier(value.value("runId").toString());
    }
    void recordCurrentError(QNetworkReply* reply, const overte::network::RequestTicket& lookup) {
        if (!enabled() || !reply || !lookup.current()) { return; }
#if defined(ANDROID_APP_PICO_INTERFACE)
        _presentation.clear();
        const auto facts=navigationReplyCapture().original(reply,lookup);
        if (facts.isEmpty()) { _valid=false;return; }
        if (!facts.value("owned").toBool()) { return; }
        if (!lookup.current()) { return; }
        const auto capture=facts.value("captureId").toString();const auto now=epoch();
        if (!_valid || !now || !identifier(capture) || facts.value("cancelled").toBool()
                || facts.value("capturedEpochMs").toLongLong()<=0 || facts.value("capturedEpochMs").toLongLong()>now
                || facts.value("networkError").toInt()<=0 || _events.size()>=128
                || lookup.featureGeneration()==0 || lookup.featureGeneration()>9007199254740991ULL) { _valid=false;return; }
        if (_captureIds.contains(capture)) { return; }
        const bool current=lookup.current();if (!current) { return; }
        _captureIds.insert(capture);
        QVariantMap event{{"sequence",static_cast<qulonglong>(++_eventSequence)},{"eventId",nonce()},
            {"runId",facts.value("runId")},{"responseId",facts.value("responseId")},{"origin",facts.value("origin")},
            {"httpStatus",facts.value("httpStatus")},{"networkError",facts.value("networkError")},
            {"contentNotFound",facts.value("contentNotFound")},{"current",current},
            {"lookupGeneration",static_cast<qulonglong>(lookup.featureGeneration())},{"callbackEpochMs",now},
            {"replyCaptureId",capture},{"replyCapturedEpochMs",facts.value("capturedEpochMs")}};
        _events.append(event);_presentation=event;
#else
        const auto url=reply->url();
        const auto match=QRegularExpression("\\A/api/v1/places/hidden-([0-9a-f]{32})\\z").match(url.path(QUrl::FullyEncoded));
        if (!match.hasMatch()) { return; } // Never export unrelated native URLs or errors.
        const auto scoped=reply->property("_overte_request_ticket");
        const auto ticket=scoped.value<overte::network::RequestTicket>();
        if (scoped.userType()!=qMetaTypeId<overte::network::RequestTicket>() || !lookup.scoped()
                || !ticket.scoped() || !ticket.current() || !ticket.sameRequest(lookup)
                || lookup.featureGeneration()==0 || lookup.featureGeneration()>9007199254740991ULL
                || reply->thread()!=QThread::currentThread() || !overte::network::replyCurrent(reply)
                || (url.scheme()!="http" && url.scheme()!="https") || url.host().isEmpty()
                || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()) { _valid=false;return; }
        for (const auto& original:_seen) { if (original.data()==reply) { return; } }
        const auto headers=reply->rawHeaderPairs();int headerCount{0};QByteArray response;
        for (const auto& header:headers) {
            if (header.first.toLower()=="x-overte-fixture-response") { ++headerCount;response=header.second; }
        }
        if (headerCount>1 || (!response.isEmpty() && !identifier(QString::fromLatin1(response)))) { _valid=false;return; }
        const auto code=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
        bool okay{false};const auto status=code.isValid()?code.toInt(&okay):0;
        const auto error=static_cast<int>(reply->error());
        const auto now=epoch();
        if (!_valid || !now || (code.isValid() && !okay) || status<0 || status>599 || error<=0 || error>499
                || _events.size()>=128 || _eventSequence>=1000000000) { _valid=false;return; }
        const auto origin=url.adjusted(QUrl::RemovePath|QUrl::RemoveQuery|QUrl::RemoveFragment).toString(QUrl::FullyEncoded);
        if (origin.isEmpty() || origin.size()>512) { _valid=false;return; }
        _seen.append(QPointer<QNetworkReply>(reply)); // Weak identity only; no reply property or ownership changes.
        _events.append(QVariantMap{{"sequence",static_cast<qulonglong>(++_eventSequence)},
            {"eventId",nonce()},{"runId",match.captured(1)},{"responseId",QString::fromLatin1(response)},
            {"origin",origin},{"httpStatus",status},{"networkError",error},
            {"contentNotFound",reply->error()==QNetworkReply::ContentNotFoundError},{"current",ticket.current()},
            {"lookupGeneration",static_cast<qulonglong>(lookup.featureGeneration())},{"callbackEpochMs",now}});
#endif
    }
    QVariantMap snapshot(const QVariantMap& request, const overte::network::RequestTicket& lookup) {
        if (!enabled() || !command(request) || !_valid || _sequence>=1000000000 || !lookup.scoped()
                || lookup.featureGeneration()==0 || lookup.featureGeneration()>9007199254740991ULL) { return {}; }
        const auto now=epoch();if (!now || !_valid) { return {}; }
#if defined(ANDROID_APP_PICO_INTERFACE)
        if (_requests.size()>=4096 || _requests.contains(request.value("commandId").toString())) { return {}; }
        _requests.insert(request.value("commandId").toString());
        const int version=2;
#else
        const int version=1;
#endif
        QVariantList events;
        const auto run=request.value("runId").toString();
        for (const auto& value:_events) { if (value.toMap().value("runId").toString()==run) { events.append(value); } }
        return {{"navigationReplyVersion",version},{"commandId",request.value("commandId")},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",now},{"currentLookupGeneration",static_cast<qulonglong>(lookup.featureGeneration())},
            {"currentLookupActive",lookup.featureActive()},{"events",events}};
    }
#if defined(ANDROID_APP_PICO_INTERFACE)
    QVariantMap presentation(const overte::network::RequestTicket& lookup) const {
        return enabled() && _valid && lookup.current() && _presentation.value("lookupGeneration").toULongLong()==lookup.featureGeneration()
            ? _presentation : QVariantMap();
    }
#endif
private:
    static bool identifier(const QString& value,bool request=false) {
        return QRegularExpression(request?"\\A(?:ios-)?[0-9a-f]{32}\\z":"\\A[0-9a-f]{32}\\z").match(value).hasMatch();
    }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    bool enabled() const {
        return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
            && (_boundOwner ? _owner && QThread::currentThread()==_owner->thread()
                            : QThread::currentThread()==QCoreApplication::instance()->thread());
    }
    qint64 epoch() {
        const auto now=QDateTime::currentMSecsSinceEpoch();const auto elapsed=_clock.elapsed();
        if (now<=0 || now<_lastEpoch || elapsed<_lastElapsed) { _valid=false;return 0; }
        _lastEpoch=now;_lastElapsed=elapsed;return now;
    }
    QString _instance{nonce()};QVariantList _events;QElapsedTimer _clock;QVector<QPointer<QNetworkReply>> _seen;
    quint64 _sequence{0},_eventSequence{0};qint64 _lastEpoch{0},_lastElapsed{0};bool _valid{true};
    QPointer<QObject> _owner;bool _boundOwner{false};
#if defined(ANDROID_APP_PICO_INTERFACE)
    QVariantMap _presentation;QSet<QString> _captureIds,_requests;
#endif
};
} // namespace overte::e2e
#endif
