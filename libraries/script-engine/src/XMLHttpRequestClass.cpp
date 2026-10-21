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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "../../../tests/device/native/TabletHttpObservationBridge.h"
#include <QCryptographicHash>
#include <QUuid>
#endif
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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    featureTabletHttpState("destroying");
#endif
    if (_reply) { _reply->deleteLater(); }
    Q_ASSERT(_engine);
    {
        auto guard = _engine->getScopeGuard();
        _responseData = ScriptValue();
        _onTimeout = ScriptValue();
        _onReadyStateChange = ScriptValue();
    }
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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
        featureTabletHttpState("state");
#endif
        if (_onReadyStateChange.isFunction()) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
            ++_featureTabletHttpDepth;featureTabletHttpState("callback-enter");
#endif
            _onReadyStateChange.call(_onReadyStateChange.engine()->nullValue());
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
            --_featureTabletHttpDepth;featureTabletHttpState("callback-exit");
#endif
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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    featureTabletHttpReply();
#endif

    if (_timeout > 0) {
        _timer.start(_timeout);
        connect(&_timer, SIGNAL(timeout()), this, SLOT(requestTimeout()));
    }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    featureTabletHttpState("state");
#endif
}

/*@jsdoc
 * Called when the request times out.
 * @callback XMLHttpRequest~onTimeoutCallback 
 */
void XMLHttpRequestClass::requestTimeout() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    ++_featureTabletHttpDepth;featureTabletHttpState("callback-enter");
#endif
    if (_onTimeout.isFunction()) {
        _onTimeout.call(_engine->nullValue());
    }
    abortRequest();
    _errorCode = QNetworkReply::TimeoutError;
    setReadyState(DONE);
    emit requestComplete();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    --_featureTabletHttpDepth;featureTabletHttpState("callback-exit");
#endif
}

void XMLHttpRequestClass::requestError(QNetworkReply::NetworkError code) {
}

void XMLHttpRequestClass::requestFinished() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    ++_featureTabletHttpDepth;featureTabletHttpState("callback-enter");
#endif
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

    setReadyState(DONE);
    emit requestComplete();

    disconnectFromReply(_reply);
    _reply->deleteLater();
    _reply = nullptr;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    --_featureTabletHttpDepth;featureTabletHttpState("callback-exit");
#endif
}

void XMLHttpRequestClass::abortRequest() {
    // Disconnect from signals we don't want to receive any longer.
    disconnect(&_timer, SIGNAL(timeout()), this, SLOT(requestTimeout()));
    if (_reply) {
        disconnectFromReply(_reply);
        _reply->abort();
        _reply->deleteLater();
        _reply = nullptr;
    }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    featureTabletHttpState("state");
#endif
}

void XMLHttpRequestClass::connectToReply(QNetworkReply* reply) {
    connect(reply, SIGNAL(finished()), this, SLOT(requestFinished()));
    connect(reply, SIGNAL(error(QNetworkReply::NetworkError)), this, SLOT(requestError(QNetworkReply::NetworkError)));
    connect(reply, SIGNAL(downloadProgress(qint64, qint64)), this, SLOT(requestDownloadProgress(qint64, qint64)));
    connect(reply, SIGNAL(metaDataChanged()), this, SLOT(requestMetaDataChanged()));
}

void XMLHttpRequestClass::disconnectFromReply(QNetworkReply* reply) {
    disconnect(reply, SIGNAL(finished()), this, SLOT(requestFinished()));
    disconnect(reply, SIGNAL(error(QNetworkReply::NetworkError)), this, SLOT(requestError(QNetworkReply::NetworkError)));
    disconnect(reply, SIGNAL(downloadProgress(qint64, qint64)), this, SLOT(requestDownloadProgress(qint64, qint64)));
    disconnect(reply, SIGNAL(metaDataChanged()), this, SLOT(requestMetaDataChanged()));
}

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
void XMLHttpRequestClass::featureBindTabletHttp(const QString& lease) {
    if (!overte::e2e::tabletHttpEnabled() || QThread::currentThread()!=thread()
            || !_featureTabletHttpLease.isEmpty() || _readyState!=UNSENT || _reply || _timer.isActive()
            || _onReadyStateChange.isFunction() || _onTimeout.isFunction()
            || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(lease).hasMatch()) { return; }
    _featureTabletHttpLease=lease;
    featureTabletHttpState("bound");
    connect(this,&QObject::destroyed,QCoreApplication::instance(),[lease] {
        overte::e2e::TabletHttpEvent event;event.lease=lease;event.kind="destroyed";
        overte::e2e::postTabletHttpEvent(event);
    },Qt::DirectConnection);
    connect(&_timer,&QTimer::timeout,this,[this] { featureTabletHttpState("state"); });
}
void XMLHttpRequestClass::featureTabletHttpState(const QString& kind) {
    if (_featureTabletHttpLease.isEmpty()) { return; }
    overte::e2e::TabletHttpEvent event;event.lease=_featureTabletHttpLease;event.kind=kind;event.request=this;
    event.state={{"readyState",static_cast<int>(_readyState)},{"errorCode",static_cast<int>(_errorCode)},
        {"status",_reply ? _reply->attribute(QNetworkRequest::HttpStatusCodeAttribute) : QVariant()},
        {"timerActive",_timer.isActive()},{"readyHandler",_onReadyStateChange.isFunction()},
        {"timeoutHandler",_onTimeout.isFunction()},{"callbackDepth",_featureTabletHttpDepth}};
    overte::e2e::postTabletHttpEvent(event);
}
void XMLHttpRequestClass::featureTabletHttpReply() {
    if (_featureTabletHttpLease.isEmpty() || !_reply) { return; }
    const auto lease=_featureTabletHttpLease;
    const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    overte::e2e::TabletHttpEvent event;event.lease=lease;event.kind="reply";event.replyId=id;event.reply=_reply;
    event.urlSha256=QString::fromLatin1(QCryptographicHash::hash(_reply->url().toEncoded(QUrl::FullyEncoded),QCryptographicHash::Sha256).toHex());
    overte::e2e::postTabletHttpEvent(event);
    connect(_reply,&QObject::destroyed,QCoreApplication::instance(),[lease,id] {
        overte::e2e::TabletHttpEvent event;event.lease=lease;event.kind="reply-destroyed";event.replyId=id;
        overte::e2e::postTabletHttpEvent(event);
    },Qt::DirectConnection);
}
#endif
