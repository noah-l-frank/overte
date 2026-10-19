// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Read-only E2E history at actual CommonJS require completion/cache reuse.
// A foreign observer never touches a ScriptEngine heap or waits on its thread.
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMap>
#include <QUuid>
#include <QVariantMap>
#include <QVariantList>
#include <mutex>

namespace overte::e2e {
class RequiredModuleObservation {
public:
    RequiredModuleObservation() {
        if (QCoreApplication::arguments().contains("--testScript")) {
            _instance = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        }
    }
    // Capture exactly the UTF-16 code units passed to the real top-level
    // engine evaluation. No disk reread or requested URL stands in for code.
    void submitted(const QString& code) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return; }
        if (_submitted || code.size() > 4194304) { _valid = false; return; }
        QByteArray bytes; bytes.reserve(code.size()*2);
        for (auto character : code) {
            const auto unit = character.unicode();
            bytes.append(static_cast<char>(unit & 0xff)); bytes.append(static_cast<char>((unit >> 8) & 0xff));
        }
        _submitted = true; _codeUnits = code.size(); _submittedEpochMs = QDateTime::currentMSecsSinceEpoch();
        _codeDigest = QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
    }
    QVariantMap sourceIdentity() const {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return {}; }
        return {{"submitted", _submitted}, {"encoding", "utf-16le-code-units"},
            {"codeUnits", _codeUnits}, {"sha256", _codeDigest}, {"submittedEpochMs", _submittedEpochMs}};
    }
    void record(const QString& url, bool loaded, bool cached) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return; }
        if (url.isEmpty() || url.size() > 4096 || _sequence >= 1000000000
                || (!_modules.contains(url) && _modules.size() >= 256)) { _valid = false; return; }
        for (const auto character : url) {
            if (character.unicode() < 32) { _valid = false; return; }
        }
        _modules[url] = {{"url", url}, {"loaded", loaded}, {"cached", cached},
            {"sequence", static_cast<qulonglong>(++_sequence)},
            {"capturedEpochMs", QDateTime::currentMSecsSinceEpoch()}};
    }
    QVariantMap snapshot() const {
        std::lock_guard<std::mutex> lock(_mutex);
        if (_instance.isEmpty() || !_valid) { return {}; }
        QVariantList modules;
        for (auto it = _modules.cbegin(); it != _modules.cend(); ++it) { modules.append(it.value()); }
        return {{"instance", _instance}, {"sequence", static_cast<qulonglong>(_sequence)}, {"modules", modules}};
    }
private:
    mutable std::mutex _mutex;
    QString _instance;
    QMap<QString, QVariantMap> _modules;
    quint64 _sequence {0};
    bool _valid {true};
    bool _submitted {false};
    int _codeUnits {0};
    qint64 _submittedEpochMs {0};
    QString _codeDigest;
};
} // namespace overte::e2e
