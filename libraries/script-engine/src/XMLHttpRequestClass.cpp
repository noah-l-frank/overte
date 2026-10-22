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
#include "ScriptManager.h"
#include <Finally.h>
#include <QThread>
#include <udt/PacketHeaders.h>
namespace {
overte::e2e::PlacesHttpObservation& placesHttp() {
    static overte::e2e::PlacesHttpObservation ledger;return ledger;
}
}

QVariantMap XMLHttpRequestClass::featurePlacesHttpObservation(const QVariantMap& command) { return placesHttp().snapshot(command); }

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
#endif
}

ScriptValue XMLHttpRequestClass::getResponseText() const {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
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
