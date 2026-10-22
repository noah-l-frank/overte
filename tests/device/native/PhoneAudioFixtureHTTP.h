// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QTimer>
#include <QUuid>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
// Original HTTP input reader. Redirects, oversized/partial bodies, stale
// callbacks and replayed tickets cannot arm the microphone input seam.
class PhoneAudioFixtureHTTP : public QObject {
public:
    using Arm = std::function<bool(const QByteArray&, const QVariantMap&)>;
    using Read = std::function<QVariantMap()>;
    using Release = std::function<void()>;
    PhoneAudioFixtureHTTP(QObject* parent, Arm arm, Read read, Release release) :
        QObject(parent), _manager(this), _arm(std::move(arm)), _read(std::move(read)), _release(std::move(release)),
        _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) {}

    QVariantMap command(const QVariantMap& request) {
        const auto id = request.value("commandId").toString();
        const auto operation = request.value("operation").toString();
        const QStringList basic {"schemaVersion", "commandId", "operation"};
        const auto version = QJsonObject::fromVariantMap(request).value("schemaVersion");
        if (!version.isDouble() || version.toDouble() != 1
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
        if (_commands.contains(id)) { return request == _lastCommand ? _lastResult : QVariantMap(); }
        if (_commands.size() >= 4096) { return {}; }
        if (operation == "arm") {
            auto keys = basic; keys << "runId" << "ticket" << "url"; keys.sort();
            const QString run = request.value("runId").toString(), ticket = request.value("ticket").toString();
            const QUrl url(request.value("url").toString(), QUrl::StrictMode);
            const QString path = "/feature-fixture/v1/runs/" + run + "/tickets/" + ticket + "/preview-input.v1.pcm16le";
            if (request.keys() != keys || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                    || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(ticket).hasMatch()
                    || !url.isValid() || url.scheme() != "http" || url.host().isEmpty() || url.port() < 1
                    || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || url.path() != path
                    || url.toString() != request.value("url").toString() || _pending || _used.size() >= 128
                    || _used.contains(ticket) || _read().value("armed").toBool()) { return {}; }
            if (!_run.isEmpty() && (_run != run || _origin != url.adjusted(QUrl::RemovePath).toString())) { return {}; }
            _run = run; _origin = url.adjusted(QUrl::RemovePath).toString(); _used.insert(ticket);
            _error.clear(); _receipt.clear(); _body.clear(); _pending = true;
            const auto revision = ++_revision;
            QNetworkRequest network(url);
            network.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
            network.setRawHeader("Cache-Control", "no-store");
            network.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
            _reply = _manager.get(network); const auto reply = _reply;
            const auto started = QDateTime::currentMSecsSinceEpoch();
            connect(reply, &QNetworkReply::readyRead, this, [this, revision, reply] {
                if (_revision != revision || !_pending) { return; }
                _body += reply->read(144001 - _body.size());
                if (_body.size() > 144000 || reply->bytesAvailable() > 0) { _error = "oversized-input"; reply->abort(); }
            });
            connect(reply, &QNetworkReply::finished, this, [this, revision, reply, run, ticket, url, started] {
                if (_revision == revision && _pending) {
                    _body += reply->read(144001 - _body.size());
                    const auto response = QString::fromLatin1(reply->rawHeader("X-Overte-Fixture-Response"));
                    const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
                    const auto now = QDateTime::currentMSecsSinceEpoch();
                    if (_error.isEmpty() && reply->error() == QNetworkReply::NoError && status == 200
                            && reply->url() == url && _body.size() == 144000 && now >= started && now - started < 5000
                            && QRegularExpression("\\A[0-9a-f]{32}\\z").match(response).hasMatch()) {
                        _receipt = {{"runId", run}, {"ticket", ticket}, {"url", reply->url().toString()},
                            {"responseId", response}, {"status", status}, {"bytes", _body.size()},
                            {"sha256", QString::fromLatin1(QCryptographicHash::hash(_body, QCryptographicHash::Sha256).toHex())},
                            {"startedEpochMs", started}, {"completedEpochMs", now}};
                        if (!_arm(_body, _receipt)) { _error = "native-input-unavailable"; }
                    } else if (_error.isEmpty()) { _error = "original-http-input-unavailable"; }
                    _pending = false; _body.fill(0); _body.clear(); _body.squeeze(); _reply.clear();
                }
                reply->deleteLater();
            });
            QTimer::singleShot(5000, this, [this, revision, reply] {
                if (_revision == revision && _pending && reply) { _error = "input-timeout"; reply->abort(); }
            });
        } else {
            auto keys = basic; keys.sort();
            if (request.keys() != keys || (operation != "observe" && operation != "release")) { return {}; }
            if (operation == "release") {
                ++_revision; _pending = false;
                if (_reply) { _reply->abort(); _reply.clear(); }
                _body.fill(0); _body.clear(); _body.squeeze(); _release();
            }
        }
        const auto epoch = QDateTime::currentMSecsSinceEpoch();
        const QVariantMap result {{"schemaVersion", 1}, {"requestId", id}, {"instance", _instance}, {"sequence", ++_sequence},
            {"capturedEpochMs", epoch}, {"processId", QCoreApplication::applicationPid()},
            {"pending", _pending}, {"error", _error}, {"receipt", _receipt}, {"source", _read()},
            {"pendingBytes", _body.size()}, {"revision", _revision}};
        _commands.insert(id); _lastCommand = request; _lastResult = result; return result;
    }
private:
    QNetworkAccessManager _manager;
    Arm _arm; Read _read; Release _release;
    QString _instance, _run, _origin, _error;
    QSet<QString> _used;
    QSet<QString> _commands;
    QVariantMap _lastCommand, _lastResult;
    QPointer<QNetworkReply> _reply;
    QByteArray _body;
    QVariantMap _receipt;
    bool _pending {false};
    quint64 _revision {0}, _sequence {0};
};
}
