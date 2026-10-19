// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// E2E-only protected GET with actual cached authority. Never updates account/UI.
#include <functional>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QTimer>
#include <QVariantMap>
#include <QStringList>
#include "CredentialTransportPolicy.h"
#include "NetworkAccessManager.h"
#include "RequestCancellation.h"

#if defined(OVERTE_E2E_FEATURE_TESTS)
namespace overte::e2e {
class AccountProbe final : public QObject {
public:
    struct State {
        QUrl endpoint;
        QString principal;
        QByteArray authorization;
        bool tokenPresent {false};
        overte::network::RequestTicket credentials;
    };
    using Reader=std::function<State()>;
    AccountProbe(QObject* parent,QString instance,Reader reader) : QObject(parent),_instance(instance),_reader(reader) {}
    ~AccountProbe() override {
        if (_reply) { QObject::disconnect(_reply,nullptr,this,nullptr); _reply->abort(); _reply->deleteLater(); }
    }
    QVariantMap request(const QVariantMap& command,const QString& origin) {
        if (QThread::currentThread() != thread()) { return {}; }
        const auto json=QJsonObject::fromVariantMap(command);
        auto keys=json.keys();keys.sort();
        const auto id=json.value("commandId").toString(),request=json.value("requestId").toString();
        const auto run=json.value("runId").toString(),ticket=json.value("ticket").toString(),op=json.value("operation").toString();
        const QRegularExpression nonce("\\A(?:ios-)?[0-9a-f]{32}\\z"),scope("\\A[0-9a-f]{32}\\z");
        if (keys != QStringList{"action","commandId","operation","requestId","runId","schemaVersion","ticket"}
                || !json.value("schemaVersion").isDouble() || json.value("schemaVersion").toDouble() != 1
                || json.value("action").toString() != "feature-account-probe"
                || !nonce.match(id).hasMatch() || !nonce.match(request).hasMatch()
                || !scope.match(run).hasMatch() || !scope.match(ticket).hasMatch()
                || id.startsWith("ios-") != request.startsWith("ios-")
                || (op != "read" && op != "release" && op != "inspect") || (op=="read" ? id!=request : id==request)) { return {}; }
        if (id==_lastCommand.value("commandId").toString()) {
            return command==_lastCommand ? _lastCommandResult : QVariantMap();
        }
        if (op=="read") {
            if (request==_request) {
                if (run!=_run || ticket!=_ticket || origin!=_origin || _released) { return {}; }
                if (_reply && _elapsed.elapsed()>=2000) { fail(); }
                if (_reply) { return {{"schemaVersion",1},{"requestId",id},{"pending",true}}; }
                return _completed;
            }
            if (_reply || _used.contains(request) || _used.size()>=4032) { return {}; }
            const auto state=_reader();
            const QUrl owned(origin,QUrl::StrictMode);
            auto actual=state.endpoint;if (actual.path()=="/") { actual.setPath(QString()); }
            if (!overte::network::credentialTransportAllowed(owned) || !owned.path().isEmpty()
                    || owned.hasQuery() || owned.hasFragment() || QString::fromLatin1(owned.toEncoded())!=origin
                    || actual!=owned || state.authorization.size()>512 || !state.credentials.current() || !state.credentials.scoped()
                    || (!state.principal.isEmpty() && state.principal!="e2e-"+run)
                    || (state.tokenPresent && state.principal!="e2e-"+run)) { return {}; }
            _used.insert(request);_request=request;_run=run;_ticket=ticket;_origin=origin;_state=state;
            _released=false;_failed=false;_finishing=false;_completed.clear();_pending.clear();_body.clear();
            _requested=QDateTime::currentMSecsSinceEpoch();_elapsed.start();
            if (_requested<=0 || _requested<_lastEpoch) { _failed=true;clearPrivate();return {}; }
            auto target=owned;target.setPath("/api/v1/user/profile");
            QNetworkRequest network(target);
            network.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);
            network.setRawHeader("X-Overte-E2E-Run",run.toLatin1());
            network.setRawHeader("X-Overte-E2E-Ticket",ticket.toLatin1());
            network.setRawHeader("X-Overte-E2E-Request",request.toLatin1());
            if (!state.authorization.isEmpty()) { network.setRawHeader("Authorization",state.authorization); }
            _reply=overte::network::getCredentials(NetworkAccessManager::getInstance(),network);
            if (!_reply) { _failed=true;clearPrivate();return {}; }
            _reply->setReadBufferSize(4097);
            overte::network::watchRequest(_reply,state.credentials);
            auto timeout=new QTimer(_reply);timeout->setSingleShot(true);
            connect(timeout,&QTimer::timeout,this,[this] { fail(); });timeout->start(2000);
            connect(_reply,&QNetworkReply::readyRead,this,[this] { collect(); });
            connect(_reply,&QNetworkReply::finished,this,[this,timeout,target] {
                timeout->stop();collect();
                if (!_reply || _finishing) { return; }
                _finishing=true;
                const auto current=_reader();
                const auto now=QDateTime::currentMSecsSinceEpoch();
                if (_released || _failed || _elapsed.elapsed()>=2000 || now<_requested || now-_requested>=2000
                        || !current.credentials.current() || !current.credentials.sameRequest(_state.credentials)
                        || current.endpoint!=_state.endpoint || current.principal!=_state.principal
                        || current.authorization!=_state.authorization || current.tokenPresent!=_state.tokenPresent
                        || _reply->url()!=target) { _failed=true; }
                const auto status=_reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
                const auto networkError=static_cast<int>(_reply->error());
                if ((status!=200 && status!=401) || (status==401 && networkError!=QNetworkReply::NoError
                        && networkError!=QNetworkReply::AuthenticationRequiredError)) { _failed=true; }
                QJsonParseError error;const auto document=QJsonDocument::fromJson(_body,&error);
                const auto object=document.object();const auto user=object.value("data").toObject().value("user").toObject();
                const auto principal=user.value("username").toString();
                const bool parsed=error.error==QJsonParseError::NoError && document.isObject()
                    && (status==200 ? networkError==0 && object.value("status").toString()=="success"
                        && user.value("username").isString() && !principal.isEmpty() && principal.size()<=512
                        : object.value("status").toString()=="fail" && object.value("error").toString()=="unauthorized");
                if (!parsed || (status==200 && principal!="e2e-"+_run)) { _failed=true; }
                if (!_failed) {
                    const QVariantMap source{{"httpStatus",status},{"networkError",networkError},{"parsed",parsed},
                        {"principalSha256",digest(status==200 ? principal.toUtf8() : QByteArray())},
                        {"responseSha256",digest(_body)},{"responseBytes",_body.size()},
                        {"tokenAttached",!_state.authorization.isEmpty()},
                        {"credentialGeneration",static_cast<qulonglong>(_state.credentials.featureGeneration())},
                        {"endpointSha256",digest(_state.endpoint.toEncoded())},
                        {"sentEpochMs",_requested},{"completedEpochMs",now}};
                    _pending=source;
                }
                clearPrivate();_reply->deleteLater();
            });
            connect(_reply,&QObject::destroyed,this,[this] {
                _reply=nullptr;clearPrivate();
                if (!_released && !_failed && !_pending.isEmpty()) { _completed=envelope(_request,"read",_pending,_requested); }
                _pending.clear();
            });
            return {{"schemaVersion",1},{"requestId",id},{"pending",true}};
        }
        // Retire an owned but never-delivered intent before a late dispatch can
        // issue a GET. This cannot displace an active different native request.
        if (op=="release" && request!=_request && !_reply && !_used.contains(request) && _used.size()<4094) {
            clearPrivate();_used.insert(request);_request=request;_run=run;_ticket=ticket;_origin.clear();
            _released=true;_failed=true;_completed.clear();_pending.clear();
        }
        if (request!=_request || run!=_run || ticket!=_ticket || _used.size()>=4096 || _used.contains(id)) { return {}; }
        _used.insert(id);
        if (op=="release") {
            _released=true;_completed.clear();_pending.clear();clearPrivate();
            if (_reply) { _reply->abort(); }
        }
        const QVariantMap source=op=="release" ? QVariantMap{{"performed",true}}
            : QVariantMap{{"inflight",bool(_reply)},{"responseBytes",_body.size()},
                          {"credentialBytes",_state.authorization.size()+_state.principal.toUtf8().size()},{"released",_released}};
        _lastCommand=command;_lastCommandResult=envelope(id,op,source,QDateTime::currentMSecsSinceEpoch());
        return _lastCommandResult;
    }
private:
    static QString digest(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
    void clearPrivate() { _body.clear();_state.authorization.clear();_state.principal.clear(); }
    void fail() { _failed=true; if (_reply) { _reply->abort(); } }
    void collect() {
        if (!_reply) { return; }
        if (_released || _failed) { _reply->read(4097);return; }
        const auto bytes=_reply->read(4097-_body.size());_body.append(bytes);
        if (_body.size()>4096 || _reply->bytesAvailable()>0) { fail(); }
    }
    QVariantMap envelope(const QString& id,const QString& operation,const QVariantMap& source,qint64 requested) {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (_sequence>=9007199254740991ULL || now<requested || now<=0 || requested<_lastEpoch || now<_lastEpoch
                || (operation=="read" && (now-requested>=2000 || _elapsed.elapsed()>=2000))) { return {}; }
        _lastEpoch=now;
        return {{"probeVersion",1},{"commandId",id},{"requestId",_request},{"runId",_run},{"ticket",_ticket},
            {"operation",operation},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},{"capturedEpochMs",now},{"source",source}};
    }
    QString _instance,_request,_run,_ticket,_origin;
    Reader _reader;State _state;QPointer<QNetworkReply> _reply;
    QElapsedTimer _elapsed;qint64 _requested {0},_lastEpoch {0};quint64 _sequence {0};
    bool _released {false},_failed {false},_finishing {false};QSet<QString> _used;
    QByteArray _body;QVariantMap _completed,_pending,_lastCommand,_lastCommandResult;
};
} // namespace overte::e2e

#endif // OVERTE_E2E_FEATURE_TESTS
