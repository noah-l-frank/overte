// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {

// Records only actual messageReceived emissions for an explicitly opened test
// run. It observes neither send intent nor an asserted delivery outcome. Direct
// signals can originate on script threads; the bounded cache is mutex protected.
class ChatObservation {
public:
    QString instance() const { return _instance; }
    void received(const QString& channel, const QString& raw, const QUuid& sender, bool localOnly) {
        if (channel != QStringLiteral("chat") || raw.size() > 4096 || sender.isNull()) { return; }
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(raw.toUtf8(), &error);
        if (error.error != QJsonParseError::NoError || !document.isObject()) { return; }
        const auto object = document.object();
        const auto keys = object.keys();
        const QSet<QString> required {"action", "channel", "message", "displayName", "position"};
        if (QSet<QString>(keys.begin(), keys.end()) != required
                || object.value("action") != QJsonValue(QStringLiteral("send_chat_message"))
                || !object.value("message").isString()
                || (object.value("channel") != QJsonValue(QStringLiteral("local")) && object.value("channel") != QJsonValue(QStringLiteral("domain")))) { return; }
        const auto text = object.value("message").toString();
        const auto match = QRegularExpression(QStringLiteral("\\A(?:Overte ä Ω 東京 |(?:reply|hidden|retry)-)([0-9a-f]{32})\\z")).match(text);
        if (!match.hasMatch()) { return; } // Never retain arbitrary user content or display names.
        const auto run = match.captured(1);
        QMutexLocker locker(&_mutex);
        if (!_available || !_scopes.contains(run)) { return; }
        const auto now = tick();
        if (!now) { return; }
        auto& scope = _scopes[run];
        if (scope.sequence >= MAX_SEQUENCE) { _available = false; return; }
        scope.events.append(QVariantMap {{"sequence", static_cast<qulonglong>(++scope.sequence)},
            {"capturedEpochMs", now}, {"senderSha256", identity(run, sender)},
            {"localOnly", localOnly}, {"channel", object.value("channel").toString()}, {"text", text}});
        if (scope.events.size() > 128) { scope.events.removeFirst(); }
    }

    QVariantMap request(const QVariantMap& command, const QUuid& self, const QUuid& mixer) {
        const auto keys = command.keys();
        const QSet<QString> required {"schemaVersion", "commandId", "action", "operation", "runId"};
        const auto json = QJsonObject::fromVariantMap(command);
        const auto run = json.value("runId").toString();
        const auto id = json.value("commandId").toString();
        const auto operation = json.value("operation").toString();
        if (QSet<QString>(keys.begin(), keys.end()) != required
                || json.value("schemaVersion") != QJsonValue(1)
                || json.value("action") != QJsonValue(QStringLiteral("feature-chat-observe"))
                || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || (operation != "observe" && operation != "retire" && operation != "inspect")
                || self.isNull() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        QMutexLocker locker(&_mutex);
        if (!_available || _sequence >= MAX_SEQUENCE) { return {}; }
        const auto now = tick();
        if (!now) { return {}; }
        if (operation == "observe") {
            if (_retired.contains(run) || (!_scopes.contains(run) && _scopes.size() >= 32)) { return {}; }
            if (!_scopes.contains(run)) { _scopes.insert(run, Scope {now, 0, {}}); }
        } else if (operation == "retire") {
            if (!_retired.contains(run) && _retired.size() >= 4096) { return {}; }
            _retired.insert(run); // Fence late signal emissions before clearing originals.
            _scopes.remove(run);
        }
        const bool present = _scopes.contains(run);
        const auto scope = _scopes.value(run);
        return {{"chatVersion", 1}, {"commandId", id}, {"runId", run}, {"operation", operation},
            {"instance", _instance}, {"sequence", static_cast<qulonglong>(++_sequence)},
            {"processId", QCoreApplication::applicationPid()}, {"capturedEpochMs", now},
            {"source", QVariantMap {{"scopePresent", present}, {"retired", _retired.contains(run)},
                {"selfSha256", identity(run, self)}, {"mixerPresent", !mixer.isNull()},
                {"mixerSha256", mixer.isNull() ? QString() : identity(run, mixer)},
                {"openedEpochMs", scope.openedEpochMs},
                {"eventSequence", static_cast<qulonglong>(scope.sequence)},
                {"droppedEvents", static_cast<qulonglong>(scope.sequence - scope.events.size())},
                {"events", scope.events}}}};
    }

private:
    struct Scope { qint64 openedEpochMs {0}; quint64 sequence {0}; QVariantList events; };
    static constexpr quint64 MAX_SEQUENCE = 9007199254740991ULL;
    static QString identity(const QString& run, const QUuid& value) {
        return QString::fromLatin1(QCryptographicHash::hash(run.toUtf8() + ':' + value.toRfc4122(), QCryptographicHash::Sha256).toHex());
    }
    qint64 tick() {
        const auto now = QDateTime::currentMSecsSinceEpoch();
        if (now <= 0 || now < _epoch) { _available = false; return 0; }
        _epoch = now; return now;
    }
    QMutex _mutex;
    bool _available {true};
    qint64 _epoch {0};
    quint64 _sequence {0};
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QMap<QString, Scope> _scopes;
    QSet<QString> _retired;
};
} // namespace overte::e2e
#endif
