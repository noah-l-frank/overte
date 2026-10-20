// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Default-off passive history of accepted top-level ScriptCache callbacks.
// No load, retry, cancellation, signal or engine lifetime is controlled here.
#include <QCoreApplication>
#include <QDateTime>
#include <QStringList>
#include <QUuid>
#include <QUrl>
#include <QVariantList>
#include <QVariantMap>
#include <mutex>

namespace overte::e2e {
class ScriptLoadObservation {
public:
    ScriptLoadObservation() {
        if (QCoreApplication::arguments().contains("--testScript")) {
            _instance = identifier();
        }
    }
    void record(const QString& manager, const QString& url, quint64 generation,
                bool isURL, bool success, const QString& status) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return; }
        const auto epoch = QDateTime::currentMSecsSinceEpoch();
        const QStringList statuses{"Success", "Cached", "Inline", "Error", "Timeout",
            "ServerUnavailable", "AccessDenied", "InvalidByteRange", "InvalidURL",
            "NotFound", "RedirectFail", "Cancelled"};
        const bool successful = status == "Success" || status == "Cached" || status == "Inline";
        if (!hexId(manager) || generation == 0
                || generation > 9007199254740991ULL || !statuses.contains(status)
                || success != successful || isURL == (status == "Inline")
                || _events.size() >= 256 || epoch <= 0 || epoch < _lastEpoch) {
            _valid = false; return;
        }
        // Inline callback "URLs" can contain source code. Never export it.
        const QString observedURL = isURL ? url : QString();
        if (isURL) {
            const QUrl parsed(url, QUrl::StrictMode);
            const QStringList schemes{"file", "http", "https", "atp"};
            if (url.isEmpty() || url.size() > 4096 || !parsed.isValid()
                    || !schemes.contains(parsed.scheme()) || !parsed.userInfo().isEmpty()
                    || parsed.hasQuery() || parsed.hasFragment()) { _valid = false; return; }
            for (const auto character : url) {
                if (character.unicode() < 32) { _valid = false; return; }
            }
        }
        for (const auto& raw : _events) {
            const auto old = raw.toMap();
            if (old.value("managerInstance").toString() == manager
                    && old.value("loadGeneration").toULongLong() >= generation) {
                _valid = false; return;
            }
        }
        const auto event = identifier();
        for (const auto& raw : _events) {
            if (raw.toMap().value("eventId").toString() == event) { _valid = false; return; }
        }
        _events.append(QVariantMap{{"sequence", _events.size() + 1}, {"eventId", event},
            {"managerInstance", manager}, {"url", observedURL}, {"loadGeneration", static_cast<qulonglong>(generation)},
            {"isURL", isURL}, {"success", success}, {"status", status}, {"callbackEpochMs", epoch}});
        _lastEpoch = epoch;
    }
    QVariantMap snapshot() const {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return {}; }
        return {{"complete", true}, {"instance", _instance}, {"sequence", _events.size()}, {"events", _events}};
    }
private:
    static QString identifier() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool hexId(const QString& value) {
        if (value.size() != 32) { return false; }
        for (const auto character : value) {
            const auto unit = character.unicode();
            if (!((unit >= '0' && unit <= '9') || (unit >= 'a' && unit <= 'f'))) { return false; }
        }
        return true;
    }
    mutable std::mutex _mutex;
    QString _instance;
    QVariantList _events;
    qint64 _lastEpoch{0};
    bool _valid{true};
};
} // namespace overte::e2e
