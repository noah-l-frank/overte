// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QCryptographicHash>
#include <QMap>
#include <QSet>
#include <mutex>

namespace overte::e2e {
// Original Application::loadDialog listener/callback boundaries. No QObject,
// manager, callback or Script value is retained; capture never dispatches work.
class IOSScriptDialogObservation {
public:
    static IOSScriptDialogObservation& process() { static IOSScriptDialogObservation value;return value; }
    QString born() {
        std::lock_guard<std::mutex> guard(_mutex);if (!enabled()) { return {}; }
        const auto token=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        if (_stages.contains(token) || !_complete || _stages.size()>=128) { _complete=false;return {}; }
        _stages.insert(token,0);append(token,"listener-created",QVariant(),QVariant(),QVariant());return token;
    }
    void responseStarted(const QString& token,const QString& response,bool fileExists) {
        std::lock_guard<std::mutex> guard(_mutex);if (token.isEmpty()) { return; }
        if (!_stages.contains(token) || _stages.value(token)!=0 || response.size()>4096) { _complete=false;return; }
        const QByteArray raw(reinterpret_cast<const char*>(response.utf16()),response.size()*2);
        const QVariantMap original {{"text",response},{"encoding","utf-16le-code-units"},
            {"codeUnits",response.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}};
        append(token,"response-entered",original,fileExists,QVariant());_stages[token]=1;
    }
    void responseFinished(const QString& token,const QVariantMap& manager) {
        std::lock_guard<std::mutex> guard(_mutex);if (token.isEmpty()) { return; }
        if (!_stages.contains(token) || _stages.value(token)!=1) { _complete=false;return; }
        append(token,"response-returned",QVariant(),QVariant(),manager.isEmpty() ? QVariant() : QVariant(manager));_stages[token]=2;
    }
    void listenerDestroyed(const QString& token) {
        std::lock_guard<std::mutex> guard(_mutex);if (token.isEmpty()) { return; }
        if (!_stages.contains(token) || _destroyed.contains(token)) { _complete=false;return; }
        _destroyed.insert(token);append(token,"listener-destroyed",QVariant(),QVariant(),QVariant());
    }
    QVariantMap snapshot() {
        std::lock_guard<std::mutex> guard(_mutex);if (!enabled()) { return {}; }
        return {{"scriptDialogLedgerVersion",1},{"instance",_instance},{"processId",QCoreApplication::applicationPid()},
            {"complete",_complete},{"eventSequence",_events.size()},{"events",_events}};
    }
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosScriptDialogVersion","native-main-script-dialog",request,run,[&] { return snapshot(); });
    }
private:
    IOSScriptDialogObservation() { _clock.start(); }
    bool enabled() const { return QCoreApplication::arguments().contains("--testScript"); }
    void append(const QString& token,const QString& kind,const QVariant& response,const QVariant& exists,const QVariant& manager) {
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=_clock.elapsed();
        if (!_complete || _events.size()>=512 || epoch<_lastEpoch || mono<_lastMono || epoch<=0) { _complete=false;return; }
        _events.append(QVariantMap{{"eventSequence",_events.size()+1},{"capturedEpochMs",epoch},{"monotonicMs",mono},
            {"dialogInstance",token},{"kind",kind},{"response",response},{"fileExists",exists},{"manager",manager}});
        _lastEpoch=epoch;_lastMono=mono;
    }
    std::mutex _mutex;QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    bool _complete {true};QElapsedTimer _clock;qint64 _lastEpoch {0},_lastMono {0};
    QMap<QString,int> _stages;QSet<QString> _destroyed;QVariantList _events;NativeReadBracket _bracket;
};
} // namespace overte::e2e
#endif
