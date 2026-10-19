// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Dedicated test-build instrumentation. No lifecycle operation is performed
// here: counters describe application notifications and actual process starts.
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QThread>
#include <QUuid>
#include <cmath>

namespace overte::e2e {

class FeatureLifecycle : public QObject {
public:
    explicit FeatureLifecycle(QObject* parent) : QObject(parent) {}

    bool start(const QString& directory) {
        if (_started || QThread::currentThread() != qApp->thread()) { return false; }
        _path = directory + QStringLiteral("/feature-lifecycle.v1.json");
        QFileInfo info(_path);
        if (info.exists()) {
            if (info.isSymLink() || !info.isFile() || info.size() > 4096) { return false; }
            QFile input(_path);
            if (!input.open(QIODevice::ReadOnly)) { return false; }
            QJsonParseError error;
            const auto bytes = input.read(4097);
            const auto document = QJsonDocument::fromJson(bytes, &error);
            const auto value = document.object();
            if (error.error != QJsonParseError::NoError || !document.isObject()
                    || document.toJson(QJsonDocument::Compact) != bytes
                    || value.size() != 4 || value.value("schemaVersion") != QJsonValue(1)
                    || !counter(value.value("backgrounds"), _backgrounds)
                    || !counter(value.value("activations"), _activations)
                    || !counter(value.value("launches"), _launches)) { return false; }
        }
        if (_launches >= LIMIT) { return false; }
        ++_launches; // This object is started once by the new native process.
        _started = true;
        stateChanged(QGuiApplication::applicationState());
        if (!_valid || !persist()) { _valid = false; return false; }
        connect(qApp, &QGuiApplication::applicationStateChanged, this,
                [this](Qt::ApplicationState state) { stateChanged(state); });
        return true;
    }

    QJsonObject snapshot() const {
        if (!_started || !_valid || QThread::currentThread() != qApp->thread()) { return {}; }
        return {{"backgrounds", _backgrounds}, {"activations", _activations}, {"launches", _launches}};
    }

private:
    static constexpr int LIMIT = 1000000;
    static bool counter(const QJsonValue& value, int& output) {
        const auto number = value.toDouble(-1);
        if (!value.isDouble() || !std::isfinite(number) || number < 0 || number > LIMIT
                || std::floor(number) != number) { return false; }
        output = static_cast<int>(number);
        return true;
    }

    void stateChanged(Qt::ApplicationState state) {
        if (!_valid) { return; }
        // Inactive includes transient native sheets/interruptions. Count a
        // background once for Hidden/Suspended, and its later real activation.
        if (state == Qt::ApplicationHidden || state == Qt::ApplicationSuspended) {
            if (!_background && _everActive) { ++_backgrounds; }
            _background = true;
        } else if (state == Qt::ApplicationActive) {
            if (!_everActive || _background) { ++_activations; }
            _everActive = true;
            _background = false;
        }
        if (_backgrounds > LIMIT || _activations > LIMIT || !persist()) { _valid = false; }
    }

    bool persist() const {
        QSaveFile output(_path);
        // Never fall back to a truncating write of an existing document.
        output.setDirectWriteFallback(false);
        if (!output.open(QIODevice::WriteOnly)
                || !output.setPermissions(QFile::ReadOwner | QFile::WriteOwner)) { return false; }
        const auto bytes = QJsonDocument(QJsonObject{{"schemaVersion", 1},
            {"backgrounds", _backgrounds}, {"activations", _activations}, {"launches", _launches}})
            .toJson(QJsonDocument::Compact);
        return output.write(bytes) == bytes.size() && output.commit();
    }

    QString _path;
    int _backgrounds {0}, _activations {0}, _launches {0};
    bool _started {false}, _valid {true}, _background {false}, _everActive {false};
};

} // namespace overte::e2e
