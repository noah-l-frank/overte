//
//  XMLHttpRequestClass.cpp
//  libraries/script-engine/src/
//
//  Created by Ryan Huffman on 5/2/14.
//  Copyright (c) 2014 High Fidelity, Inc. All rights reserved.
//  Copyright 2023 Overte e.V.
//
//  This class is an implementation of the XMLHttpRequest object for scripting use.  It provides a near-complete implementation
//  of the class described in the Mozilla docs: https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//  SPDX-License-Identifier: Apache-2.0
//

#include "XMLHttpRequestClass.h"

#include <QEventLoop>
#include <qurlquery.h>

#include <AccountManager.h>
#include <NetworkAccessManager.h>
#include <NetworkingConstants.h>
#include <MetaverseAPI.h>

#include "ResourceRequestObserver.h"
#include "ScriptContext.h"
#include "ScriptEngine.h"
#include "ScriptEngineCast.h"
#include "ScriptValue.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "PlacesHttpObservation.h"
#include "AvatarSocialHttpObservation.h"
#include "ScriptManager.h"
#include <Finally.h>
#include <QThread>
#include <udt/PacketHeaders.h>
namespace {
overte::e2e::PlacesHttpObservation& placesHttp() {
    static overte::e2e::PlacesHttpObservation ledger;return ledger;
}
void snapshotHttpEvent(const QString& id,const char* kind) noexcept {
    if (id.isEmpty()) { return; }
    try { overte::e2e::snapshotPreflightHttp().event(id,QString::fromLatin1(kind)); }
    catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}
void snapshotHttpReplyEvent(const QString& id,const QString& reply,const char* kind) noexcept {
    if (id.isEmpty()) { return; }
    try { overte::e2e::snapshotPreflightHttp().event(id,QString::fromLatin1(kind),{{"replyId",reply}}); }
    catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}
void snapshotHttpCallback(const QString& id,bool enter,int state,const char* callback="readystatechange") noexcept {
    if (id.isEmpty()) { return; }
    try { overte::e2e::snapshotPreflightHttp().event(id,enter ? "callback-enter" : "callback-leave",{{"callback",QString::fromLatin1(callback)},{"readyState",state}}); }
    catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}
}

QVariantMap XMLHttpRequestClass::featurePlacesHttpObservation(const QVariantMap& command) { return placesHttp().snapshot(command); }

QVariantMap XMLHttpRequestClass::featureAvatarSocialHttpObservation(const QVariantMap& command) {
    return overte::e2e::avatarSocialHttp().snapshot(command);
}

QVariantMap XMLHttpRequestClass::featureSnapshotPreflightHttpObservation(const QVariantMap& command) noexcept {
    try { return overte::e2e::snapshotPreflightHttp().snapshot(command); }
    catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable();return {}; }
}

void XMLHttpRequestClass::featureSnapshotPreflightOpen() noexcept {
    try {
        using Observation=overte::e2e::AvatarSocialHttpObservation;
        if (!QCoreApplication::arguments().contains("--testScript") || !_async || _method!="GET" || !Observation::snapshotPreflightEndpoint(_url)
                || !_engine || !_engine->manager() || QThread::currentThread()!=_engine->thread()) { return; }
        const auto manager=_engine->manager();const auto membership=manager->featureLoadMembership(),submitted=manager->featureSourceIdentity();
        if (membership.value("assigned").userType()!=QMetaType::Bool || !membership.value("assigned").toBool()
                || !Observation::installed(membership.value("url").toString(),"/defaultScripts.js")
                || submitted.value("submitted").userType()!=QMetaType::Bool || !submitted.value("submitted").toBool()) { return; }
        const auto sources=manager->featureSnapshotHttpSources();
        if (sources.value("snapshotHttpSourcesVersion")!=QVariant(1) || sources.value("complete").userType()!=QMetaType::Bool
                || !sources.value("complete").toBool()) { Observation::snapshotUnavailable();return; }
        const auto callers=overte::e2e::AvatarV8Callers::resolve(manager->featureAvatarV8Stack(),sources.value("evaluations").toList());
        if (!callers.complete) { Observation::snapshotUnavailable();return; }
        if (!callers.snapshotPreflightOpen()) { return; }
        _featureSnapshotPreflightId=overte::e2e::snapshotPreflightHttp().create({{"engine",membership},{"submitted",submitted},
            {"requestUrl",_url.toString(QUrl::FullyEncoded)},{"method",_method},{"protocolSignature",protocolVersionsSignatureBase64()},{"codeSources",sources}},callers);
        if (_featureSnapshotPreflightId.isEmpty()) { return; }
        const auto id=_featureSnapshotPreflightId;
        QObject::connect(this,&QObject::destroyed,[id] { snapshotHttpEvent(id,"xhr-destroyed"); });
        QObject::connect(&_timer,&QObject::destroyed,[id] { snapshotHttpEvent(id,"timer-destroyed"); });
        QObject::connect(&_timer,&QTimer::timeout,this,[this] { featureSnapshotPreflightTimer(); });
    } catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}

void XMLHttpRequestClass::featureSnapshotPreflightSent() noexcept {
    if (_featureSnapshotPreflightId.isEmpty()) { return; }
    try {
        using Observation=overte::e2e::AvatarSocialHttpObservation;
        if (!_reply || !Observation::snapshotPreflightEndpoint(_reply->url()) || !_sendData.isEmpty()
                || !_request.rawHeader("Content-Type").isEmpty()) { Observation::snapshotUnavailable();return; }
        _featureSnapshotPreflightReplyId=Observation::nonce();_featureSnapshotPreflightTextRead=false;
        const auto id=_featureSnapshotPreflightId,reply=_featureSnapshotPreflightReplyId;
        const auto authorization=_request.rawHeader("Authorization");
        overte::e2e::snapshotPreflightHttp().event(id,"sent",{{"replyId",reply},{"url",_reply->url().toString(QUrl::FullyEncoded)},
            {"method",_method},{"body",Observation::bytes(_sendData)},
            {"authorizationAttached",authorization.startsWith("Bearer ") && authorization.size()>7},{"contentType",QString()}});
        QObject::connect(_reply,&QObject::destroyed,[id,reply] { snapshotHttpReplyEvent(id,reply,"reply-destroyed"); });
    } catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}

void XMLHttpRequestClass::featureSnapshotPreflightFinished() noexcept {
    if (_featureSnapshotPreflightId.isEmpty()) { return; }
    try {
        using Observation=overte::e2e::AvatarSocialHttpObservation;
        if (!_reply || !Observation::snapshotPreflightEndpoint(_reply->url()) || _reply->url().toEncoded()!=_url.toEncoded()) {
            Observation::snapshotUnavailable();return;
        }
        QByteArray response;int count {0};
        for (const auto& header:_reply->rawHeaderPairs()) { if (header.first.toLower()=="x-overte-fixture-response") { response=header.second;++count; } }
        bool known=count==1 && response.size()==32;
        for (const auto c:response) { known=known && ((c>='0' && c<='9') || (c>='a' && c<='f')); }
        if (count>1 || (count && !known) || (known && _rawResponseData.size()>16384)) { Observation::snapshotUnavailable();return; }
        overte::e2e::snapshotPreflightHttp().event(_featureSnapshotPreflightId,"reply-finished",{{"replyId",_featureSnapshotPreflightReplyId},
            {"httpStatus",_reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()},{"networkError",static_cast<int>(_reply->error())},
            {"responseId",QString::fromLatin1(response)},{"body",known ? QVariant(Observation::bytes(_rawResponseData)) : QVariant()}});
    } catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}

void XMLHttpRequestClass::featureSnapshotPreflightText() const noexcept {
    if (_featureSnapshotPreflightId.isEmpty() || _featureSnapshotPreflightTextRead || _readyState!=DONE) { return; }
    try {
        using Observation=overte::e2e::AvatarSocialHttpObservation;
        if (!_engine || !_engine->manager() || QThread::currentThread()!=_engine->thread()) { Observation::snapshotUnavailable();return; }
        const auto sources=_engine->manager()->featureSnapshotHttpSources();
        if (sources.value("complete").userType()!=QMetaType::Bool || !sources.value("complete").toBool()) { Observation::snapshotUnavailable();return; }
        const auto callers=overte::e2e::AvatarV8Callers::resolve(_engine->manager()->featureAvatarV8Stack(),sources.value("evaluations").toList());
        if (!callers.complete) { Observation::snapshotUnavailable();return; }
        if (!callers.snapshotPreflightText()) { return; }
        _featureSnapshotPreflightTextRead=true;
        overte::e2e::snapshotPreflightHttp().eventWithCallers(_featureSnapshotPreflightId,"text-read",{{"replyId",_featureSnapshotPreflightReplyId},
            {"scriptSource",callers.modules.first().toMap().value("url")},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(_rawResponseData,QCryptographicHash::Sha256).toHex())}},callers);
    } catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}

void XMLHttpRequestClass::featureSnapshotPreflightTimer() const noexcept {
    if (_featureSnapshotPreflightId.isEmpty()) { return; }
    try { overte::e2e::snapshotPreflightHttp().event(_featureSnapshotPreflightId,"timer-state",{{"active",_timer.isActive()}}); }
    catch (...) { overte::e2e::AvatarSocialHttpObservation::snapshotUnavailable(); }
}

QStringList XMLHttpRequestClass::featureAvatarSocialCallers() const {
    if (!QCoreApplication::arguments().contains("--testScript") || !_engine || !_engine->manager()
            || QThread::currentThread()!=_engine->thread()) { return {}; }
    QStringList result;auto context=_engine->currentContext();ScriptContextPointer owner;int depth {0};
    while (context && ++depth<=128) {
        const auto function=context->functionContext();
        if (function && function->functionType()==ScriptFunctionContext::ScriptFunction) {
            const auto source=function->fileName();
            if (result.isEmpty() && !overte::e2e::AvatarSocialHttpObservation::installed(source,"/modules/request.js")) { return {}; }
            if (source.size()>4096 || result.size()>=32) { return {}; }
            result.append(source);
        }
        owner=context->parentContext();context=owner.get();
    }
    return result;
}

overte::e2e::AvatarV8Callers XMLHttpRequestClass::featureAvatarSocialV8Callers() const {
    if (!_engine || !_engine->manager() || QThread::currentThread()!=_engine->thread()) { return {}; }
    const auto manager=_engine->manager();
    return overte::e2e::AvatarV8Callers::resolve(manager->featureAvatarV8Stack(),
        manager->featureAvatarScriptObservation().value("code").toList());
}

void XMLHttpRequestClass::featureAvatarSocialOpen() {
    if (!_async || !overte::e2e::AvatarSocialHttpObservation::endpoint(_url)
            || (_method!="GET" && _method!="POST" && _method!="DELETE") || !_engine || !_engine->manager()
            || QThread::currentThread()!=_engine->thread()) { return; }
    auto manager=_engine->manager();const auto membership=manager->featureLoadMembership(),submitted=manager->featureSourceIdentity();
    if (membership.value("assigned").userType()!=QMetaType::Bool || !membership.value("assigned").toBool()
            || !overte::e2e::AvatarSocialHttpObservation::installed(membership.value("url").toString(),"/defaultScripts.js")
            || submitted.value("submitted").userType()!=QMetaType::Bool || !submitted.value("submitted").toBool()) { return; }
    bool managerRelevant {false};for (const auto& item:manager->featureAvatarScriptObservation().value("code").toList()) {
        const auto source=item.toMap().value("url").toString();
        managerRelevant=managerRelevant || overte::e2e::AvatarSocialHttpObservation::installed(source,"/system/pal.js")
            || overte::e2e::AvatarSocialHttpObservation::installed(source,"/system/request-service.js")
            || overte::e2e::AvatarSocialHttpObservation::installed(source,"/system/libraries/peopleConnection.js");
    }
    if (!managerRelevant) { return; }
    const auto callers=featureAvatarSocialV8Callers();
    if (!callers.complete) { overte::e2e::avatarSocialHttp().unavailable();return; }
    if (!callers.top("/modules/request.js") || !(callers.has("/system/pal.js") || callers.has("/system/request-service.js")
            || callers.has("/system/libraries/peopleConnection.js"))) { return; }
    _featureAvatarSocialId=overte::e2e::avatarSocialHttp().create({{"engine",membership},{"submitted",submitted},
        {"requestUrl",_url.toString(QUrl::FullyEncoded)},{"method",_method},{"protocolSignature",protocolVersionsSignatureBase64()}},callers);
    if (_featureAvatarSocialId.isEmpty()) { return; }
    const auto id=_featureAvatarSocialId;
    QObject::connect(this,&QObject::destroyed,[id] { overte::e2e::avatarSocialHttp().event(id,"xhr-destroyed"); });
    QObject::connect(&_timer,&QObject::destroyed,[id] { overte::e2e::avatarSocialHttp().event(id,"timer-destroyed"); });
    QObject::connect(&_timer,&QTimer::timeout,this,[this,id] {
        overte::e2e::avatarSocialHttp().event(id,"timer-state",{{"active",_timer.isActive()}});
    });
}

void XMLHttpRequestClass::featureAvatarSocialFinished() {
    if (_featureAvatarSocialId.isEmpty() || !_reply) { return; }
    QByteArray response;int count {0};
    for (const auto& header:_reply->rawHeaderPairs()) {
        if (header.first.toLower()=="x-overte-fixture-response") { response=header.second;++count; }
    }
    bool known=count==1 && response.size()==32;
    for (const auto c:response) { known=known && ((c>='0' && c<='9') || (c>='a' && c<='f')); }
    if (count>1 || (count && !known) || (known && _rawResponseData.size()>65536)) {
        overte::e2e::avatarSocialHttp().invalid(_featureAvatarSocialId);return;
    }
    overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"reply-finished",{{"replyId",_featureAvatarSocialReplyId},
        {"httpStatus",_reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()},
        {"networkError",static_cast<int>(_reply->error())},{"responseId",QString::fromLatin1(response)},
        {"body",known ? QVariant(overte::e2e::AvatarSocialHttpObservation::bytes(_rawResponseData)) : QVariant()}});
}


QString XMLHttpRequestClass::featurePlacesCaller() const {
    if (!QCoreApplication::arguments().contains("--testScript") || !_engine || !_engine->manager()
            || QThread::currentThread()!=_engine->thread()) { return {}; }
    auto context=_engine->currentContext();ScriptContextPointer owner;int depth {0};
    while (context && ++depth<=128) {
        const auto function=context->functionContext();
        if (function && function->functionType()==ScriptFunctionContext::ScriptFunction) {
            const auto source=function->fileName();
            return overte::e2e::PlacesHttpObservation::installed(source,"/system/places/places.js") ? source : QString();
        }
        owner=context->parentContext();context=owner.get();
    }
    return {};
}

void XMLHttpRequestClass::featurePlacesOpen() {
    const auto caller=featurePlacesCaller();
    if (caller.isEmpty() || _method!="GET" || !overte::e2e::PlacesHttpObservation::directory(_url) || !_async) { return; }
    auto manager=_engine->manager();const auto membership=manager->featureLoadMembership(),submitted=manager->featureSourceIdentity();
    const auto load=membership.value("url").toString();
    if (membership.value("assigned").userType()!=QMetaType::Bool || !membership.value("assigned").toBool()
            || !overte::e2e::PlacesHttpObservation::installed(load,"/defaultScripts.js")
            || submitted.value("submitted").userType()!=QMetaType::Bool || !submitted.value("submitted").toBool()) { return; }
    _featurePlacesId=placesHttp().create({{"scriptSource",caller},{"engine",membership},{"submitted",submitted},
        {"requestUrl",_url.toString(QUrl::FullyEncoded)},{"protocolSignature",protocolVersionsSignatureBase64()}});
    if (_featurePlacesId.isEmpty()) { return; }
    const auto id=_featurePlacesId;
    QObject::connect(this,&QObject::destroyed,[id] { placesHttp().event(id,"xhr-destroyed"); });
    QObject::connect(&_timer,&QObject::destroyed,[id] { placesHttp().event(id,"timer-destroyed"); });
    QObject::connect(&_timer,&QTimer::timeout,this,[this,id] {
        placesHttp().event(id,"timer-state",{{"active",_timer.isActive()}});
    });
}

void XMLHttpRequestClass::featurePlacesFinished() {
    if (_featurePlacesId.isEmpty() || !_reply) { return; }
    QByteArray response;int count {0};
    for (const auto& header:_reply->rawHeaderPairs()) {
        if (header.first.toLower()=="x-overte-fixture-response") { response=header.second;++count; }
    }
    bool known=count==1 && response.size()==32;
    for (const auto character:response) { known=known && ((character>='0' && character<='9') || (character>='a' && character<='f')); }
    if (count>1 || (count && !known) || (known && _rawResponseData.size()>4096)) { placesHttp().invalid(_featurePlacesId);return; }
    QVariant body;
    if (known) {
        body=QVariantMap {{"bytes",_rawResponseData.size()},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(_rawResponseData,QCryptographicHash::Sha256).toHex())},
            {"contentBase64",QString::fromLatin1(_rawResponseData.toBase64())}};
    }
    placesHttp().event(_featurePlacesId,"reply-finished",{{"replyId",_featurePlacesReplyId},
        {"httpStatus",_reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()},
        {"networkError",static_cast<int>(_reply->error())},{"responseId",QString::fromLatin1(response)},{"body",body}});
}
#endif

Q_DECLARE_METATYPE(QByteArray*)

XMLHttpRequestClass::XMLHttpRequestClass(ScriptEngine* engine) :
    _engine(engine),
    _onTimeout(engine->nullValue()),
    _onReadyStateChange(engine->nullValue()),
    _timer(this) {

    _request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::NoLessSafeRedirectPolicy);
    _timer.setSingleShot(true);
}

XMLHttpRequestClass::~XMLHttpRequestClass() {
    if (_reply) { _reply->deleteLater(); }
    Q_ASSERT(_engine);
    {
        auto guard = _engine->getScopeGuard();
        _responseData = ScriptValue();
        _onTimeout = ScriptValue();
        _onReadyStateChange = ScriptValue();
    }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    placesHttp().event(_featurePlacesId,"callbacks-released");
    overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"callbacks-released");
    snapshotHttpEvent(_featureSnapshotPreflightId,"callbacks-released");
#endif
}

ScriptValue XMLHttpRequestClass::getResponseText() const {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    featureSnapshotPreflightText();
    if (!_featureAvatarSocialId.isEmpty() && !_featureAvatarSocialTextRead && _readyState==DONE) {
        const auto callers=featureAvatarSocialV8Callers();
        if (!callers.complete) { overte::e2e::avatarSocialHttp().invalid(_featureAvatarSocialId); }
        else if (callers.top("/modules/request.js")) {
            _featureAvatarSocialTextRead=true;
            overte::e2e::avatarSocialHttp().eventWithCallers(_featureAvatarSocialId,"text-read",{{"replyId",_featureAvatarSocialReplyId},
                {"scriptSource",callers.modules.first().toMap().value("url")},
                {"sha256",QString::fromLatin1(QCryptographicHash::hash(_rawResponseData,QCryptographicHash::Sha256).toHex())}},callers);
        }
    }
    const auto caller=_featurePlacesId.isEmpty() ? QString() : featurePlacesCaller();
    if (!_featurePlacesTextRead && !caller.isEmpty() && _readyState==DONE) {
        _featurePlacesTextRead=true;
        placesHttp().event(_featurePlacesId,"text-read",{{"replyId",_featurePlacesReplyId},{"scriptSource",caller},
            {"sha256",QString::fromLatin1(QCryptographicHash::hash(_rawResponseData,QCryptographicHash::Sha256).toHex())}});
    }
#endif
    return _engine->newValue(QString(_rawResponseData.data()));
}

ScriptValue XMLHttpRequestClass::constructor(ScriptContext* context, ScriptEngine* engine) {
    return engine->newQObject(new XMLHttpRequestClass(engine), ScriptEngine::ScriptOwnership);
}

ScriptValue XMLHttpRequestClass::getStatus() const {
    if (_reply) {
        return _engine->newValue(_reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt());
    } 
    return ScriptValue(_engine->newValue(0));
}

QString XMLHttpRequestClass::getStatusText() const {
    if (_reply) {
        return _reply->attribute(QNetworkRequest::HttpReasonPhraseAttribute).toString();
    }
    return "";
}

void XMLHttpRequestClass::abort() {
    abortRequest();
}

void XMLHttpRequestClass::setRequestHeader(const QString& name, const QString& value) {
    _request.setHeader(QNetworkRequest::UserAgentHeader, NetworkingConstants::OVERTE_USER_AGENT);
    _request.setRawHeader(QByteArray(name.toLatin1()), QByteArray(value.toLatin1()));
}

void XMLHttpRequestClass::requestMetaDataChanged() {
    QVariant redirect = _reply->attribute(QNetworkRequest::RedirectionTargetAttribute);

    // If this is a redirect, abort the current request and start a new one
    if (redirect.isValid() && _numRedirects < MAXIMUM_REDIRECTS) {
        _numRedirects++;
        abortRequest();

        QUrl newUrl = _url.resolved(redirect.toUrl().toString());
        _request.setUrl(newUrl);
        doSend();
    }
}

void XMLHttpRequestClass::requestDownloadProgress(qint64 bytesReceived, qint64 bytesTotal) {
    if (_readyState == OPENED && bytesReceived > 0) {
        setReadyState(HEADERS_RECEIVED);
        setReadyState(LOADING);
    }
}

ScriptValue XMLHttpRequestClass::getAllResponseHeaders() const {
    if (_reply) {
        QList<QNetworkReply::RawHeaderPair> headerList = _reply->rawHeaderPairs();
        QByteArray headers;
        for (int i = 0; i < headerList.size(); i++) {
            headers.append(headerList[i].first);
            headers.append(": ");
            headers.append(headerList[i].second);
            headers.append("\n");
        }
        return _engine->newValue(QString(headers.data()));
    }
    return _engine->newValue("");
}

ScriptValue XMLHttpRequestClass::getResponseHeader(const QString& name) const {
    if (_reply && _reply->hasRawHeader(name.toLatin1())) {
        return _engine->newValue(QString(_reply->rawHeader(name.toLatin1())));
    }
    return _engine->nullValue();
}

/*@jsdoc
 * Called when the request's ready state changes.
 * @callback XMLHttpRequest~onReadyStateChangeCallback
 */
void XMLHttpRequestClass::setReadyState(ReadyState readyState) {
    if (readyState != _readyState) {
        _readyState = readyState;
        if (_onReadyStateChange.isFunction()) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
            placesHttp().event(_featurePlacesId,"callback-enter",{{"callback","readystatechange"},{"readyState",static_cast<int>(_readyState)}});
            overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"callback-enter",{{"callback","readystatechange"},{"readyState",static_cast<int>(_readyState)}});
            snapshotHttpCallback(_featureSnapshotPreflightId,true,static_cast<int>(_readyState));
            Finally socialCallbackLeft([&] { overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"callback-leave",{{"callback","readystatechange"},{"readyState",static_cast<int>(_readyState)}});snapshotHttpCallback(_featureSnapshotPreflightId,false,static_cast<int>(_readyState)); });
            Finally callbackLeft([&] { placesHttp().event(_featurePlacesId,"callback-leave",{{"callback","readystatechange"},{"readyState",static_cast<int>(_readyState)}}); });
#endif
            _onReadyStateChange.call(_onReadyStateChange.engine()->nullValue());
        }
    }
}

void XMLHttpRequestClass::open(const QString& method, const QString& url, bool async, const QString& username,
                               const QString& password) {
    if (_readyState == UNSENT) {
        _method = method;
        _url.setUrl(url);
        _async = async;

        const QString METAVERSE_API_URL = MetaverseAPI::getCurrentMetaverseServerURL().toString() + "/api/";

        if (url.toLower().left(METAVERSE_API_URL.length()) == METAVERSE_API_URL) {
            auto accountManager = DependencyManager::get<AccountManager>();
                
            if (accountManager->hasValidAccessToken()) {
                static const QString HTTP_AUTHORIZATION_HEADER = "Authorization";
                QString bearerString = "Bearer " + accountManager->getAccountInfo().getAccessToken().token;
                _request.setRawHeader(HTTP_AUTHORIZATION_HEADER.toLocal8Bit(), bearerString.toLocal8Bit());
            }
        }

        if (!username.isEmpty()) {
            _url.setUserName(username);
        }
        if (!password.isEmpty()) {
            _url.setPassword(password);
        }
        _request.setUrl(_url);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
        featurePlacesOpen();
        featureAvatarSocialOpen();
        featureSnapshotPreflightOpen();
#endif
        setReadyState(OPENED);
    }
}

void XMLHttpRequestClass::send() {
    send(_engine->nullValue());
}

void XMLHttpRequestClass::send(const ScriptValue& data) {
    if (_readyState == OPENED && !_reply) {

        if (!data.isNull()) {
            if (data.isObject()) {
                _sendData = scriptvalue_cast<QByteArray>(data);
            } else {
                _sendData = data.toString().toUtf8();
            }
        }

        doSend();

        if (!_async) {
            QEventLoop loop;
            connect(this, SIGNAL(requestComplete()), &loop, SLOT(quit()));
            loop.exec();
        }
    }
}

void XMLHttpRequestClass::doSend() {
    DependencyManager::get<ResourceRequestObserver>()->update(_url, -1, "XMLHttpRequestClass::doSend");
    _reply = NetworkAccessManager::getInstance().sendCustomRequest(_request, _method.toLatin1(), _sendData);
    connectToReply(_reply);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    featureSnapshotPreflightSent();
    if (!_featureAvatarSocialId.isEmpty()) {
        _featureAvatarSocialReplyId=overte::e2e::AvatarSocialHttpObservation::nonce();_featureAvatarSocialTextRead=false;
        const auto id=_featureAvatarSocialId,replyId=_featureAvatarSocialReplyId;
        const auto authorization=_request.rawHeader("Authorization");
        if (!overte::e2e::AvatarSocialHttpObservation::endpoint(_reply->url()) || _sendData.size()>4096) {
            overte::e2e::avatarSocialHttp().invalid(id);
        } else {
            overte::e2e::avatarSocialHttp().event(id,"sent",{{"replyId",replyId},{"url",_reply->url().toString(QUrl::FullyEncoded)},
                {"method",_method},{"body",overte::e2e::AvatarSocialHttpObservation::bytes(_sendData)},
                {"authorizationAttached",authorization.startsWith("Bearer ") && authorization.size()>7},
                {"contentType",QString::fromLatin1(_request.rawHeader("Content-Type"))}});
        }
        QObject::connect(_reply,&QObject::destroyed,[id,replyId] { overte::e2e::avatarSocialHttp().event(id,"reply-destroyed",{{"replyId",replyId}}); });
    }
    if (!_featurePlacesId.isEmpty()) {
        _featurePlacesReplyId=overte::e2e::PlacesHttpObservation::nonce();_featurePlacesTextRead=false;
        const auto id=_featurePlacesId,replyId=_featurePlacesReplyId;
        if (!overte::e2e::PlacesHttpObservation::directory(_reply->url())) { placesHttp().invalid(id); }
        else { placesHttp().event(id,"sent",{{"replyId",replyId},{"url",_reply->url().toString(QUrl::FullyEncoded)}}); }
        QObject::connect(_reply,&QObject::destroyed,[id,replyId] { placesHttp().event(id,"reply-destroyed",{{"replyId",replyId}}); });
    }
#endif

    if (_timeout > 0) {
        _timer.start(_timeout);
        connect(&_timer, SIGNAL(timeout()), this, SLOT(requestTimeout()));
    }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    placesHttp().event(_featurePlacesId,"timer-state",{{"active",_timer.isActive()}});
    overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"timer-state",{{"active",_timer.isActive()}});
    featureSnapshotPreflightTimer();
#endif
}

/*@jsdoc
 * Called when the request times out.
 * @callback XMLHttpRequest~onTimeoutCallback 
 */
void XMLHttpRequestClass::requestTimeout() {
    if (_onTimeout.isFunction()) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
        placesHttp().event(_featurePlacesId,"callback-enter",{{"callback","timeout"},{"readyState",static_cast<int>(_readyState)}});
        overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"callback-enter",{{"callback","timeout"},{"readyState",static_cast<int>(_readyState)}});
        snapshotHttpCallback(_featureSnapshotPreflightId,true,static_cast<int>(_readyState),"timeout");
        Finally socialCallbackLeft([&] { overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"callback-leave",{{"callback","timeout"},{"readyState",static_cast<int>(_readyState)}});snapshotHttpCallback(_featureSnapshotPreflightId,false,static_cast<int>(_readyState),"timeout"); });
        Finally callbackLeft([&] { placesHttp().event(_featurePlacesId,"callback-leave",{{"callback","timeout"},{"readyState",static_cast<int>(_readyState)}}); });
#endif
        _onTimeout.call(_engine->nullValue());
    }
    abortRequest();
    _errorCode = QNetworkReply::TimeoutError;
    setReadyState(DONE);
    emit requestComplete();
}

void XMLHttpRequestClass::requestError(QNetworkReply::NetworkError code) {
}

void XMLHttpRequestClass::requestFinished() {
    disconnect(&_timer, SIGNAL(timeout()), this, SLOT(requestTimeout()));

    _errorCode = _reply->error();

    if (_errorCode == QNetworkReply::NoError) {
        _rawResponseData.append(_reply->readAll());
        auto scopeGuard = _engine->getScopeGuard();
        if (_responseType == "json") {
            // V8TODO: V8 JSON parser needs to be used instead
            // V8TODO: make sure this always happens on script engine thread on script engines that have a script manager
            _responseData = _engine->evaluate("(" + QString(_rawResponseData.data()) + ")");
            if (_responseData.isError()) {
                _engine->clearExceptions();
                _responseData = _engine->nullValue();
            }
        } else if (_responseType == "arraybuffer") {
            _responseData = _engine->newArrayBuffer(_rawResponseData);
        } else {
            _responseData = _engine->newValue(QString(_rawResponseData.data()));
        }
    }

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    featurePlacesFinished();
    featureAvatarSocialFinished();
    featureSnapshotPreflightFinished();
#endif
    setReadyState(DONE);
    emit requestComplete();

    disconnectFromReply(_reply);
    _reply->deleteLater();
    _reply = nullptr;
}

void XMLHttpRequestClass::abortRequest() {
    // Disconnect from signals we don't want to receive any longer.
    disconnect(&_timer, SIGNAL(timeout()), this, SLOT(requestTimeout()));
    if (_reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
        placesHttp().event(_featurePlacesId,"aborted",{{"replyId",_featurePlacesReplyId}});
        overte::e2e::avatarSocialHttp().event(_featureAvatarSocialId,"aborted",{{"replyId",_featureAvatarSocialReplyId}});
        snapshotHttpReplyEvent(_featureSnapshotPreflightId,_featureSnapshotPreflightReplyId,"aborted");
#endif
        disconnectFromReply(_reply);
        _reply->abort();
        _reply->deleteLater();
        _reply = nullptr;
    }
}

void XMLHttpRequestClass::connectToReply(QNetworkReply* reply) {
    connect(reply, SIGNAL(finished()), this, SLOT(requestFinished()));
#if QT_VERSION >= QT_VERSION_CHECK(5, 15, 0)
    connect(reply, &QNetworkReply::errorOccurred, this, &XMLHttpRequestClass::requestError);
#else
    connect(reply, SIGNAL(error(QNetworkReply::NetworkError)), this, SLOT(requestError(QNetworkReply::NetworkError)));
#endif
    connect(reply, SIGNAL(downloadProgress(qint64, qint64)), this, SLOT(requestDownloadProgress(qint64, qint64)));
    connect(reply, SIGNAL(metaDataChanged()), this, SLOT(requestMetaDataChanged()));
}

void XMLHttpRequestClass::disconnectFromReply(QNetworkReply* reply) {
    disconnect(reply, SIGNAL(finished()), this, SLOT(requestFinished()));
#if QT_VERSION >= QT_VERSION_CHECK(5, 15, 0)
    disconnect(reply, &QNetworkReply::errorOccurred, this, &XMLHttpRequestClass::requestError);
#else
    disconnect(reply, SIGNAL(error(QNetworkReply::NetworkError)), this, SLOT(requestError(QNetworkReply::NetworkError)));
#endif
    disconnect(reply, SIGNAL(downloadProgress(qint64, qint64)), this, SLOT(requestDownloadProgress(qint64, qint64)));
    disconnect(reply, SIGNAL(metaDataChanged()), this, SLOT(requestMetaDataChanged()));
}
