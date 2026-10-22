// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive, test-only process ledger. Never retain a ScriptManager, QThread or
// script value: doing so would change manager-destruction -> worker-quit life.
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMap>
#include <QUuid>
#include <QVariantMap>
#include <mutex>

namespace overte::e2e {
class ScriptTerminalObservation {
public:
    static ScriptTerminalObservation& process() {
        static ScriptTerminalObservation value;
        return value;
    }

    QString bind(const QVariantMap& manager) {
        std::lock_guard<std::mutex> guard(_mutex);
        if (_instance.isEmpty() || !_complete) { return {}; }
        // Entity/networkless managers without an assigned native load are not
        // an eligible owned file Script. They cannot satisfy a later join.
        if (manager.isEmpty() || !manager.value("assigned").toBool()) { return {}; }
        const auto identity=manager.value("instance").toString();
        if (identity.isEmpty() || _threads.contains(identity)) { _complete=false;return {}; }
        const auto token=nonce();
        _threads.insert(identity,{{"threadInstance",token},{"manager",manager},{"code",QVariant()}, {"stage",0}});
        if (!append("thread-bound",token,manager,QVariant(),QVariant())) { return {}; }
        return token;
    }

    void shutdownDrained(const QString& token,const QVariantMap& manager,const QVariantMap& code,
                         quint64 signalCallbacks,quint64 timerCallbacks,bool evaluating,quint64 timers) {
        std::lock_guard<std::mutex> guard(_mutex);
        if (_instance.isEmpty() || token.isEmpty()) { return; }
        auto* state=find(token);
        if (!state || state->value("stage").toInt()!=0 || state->value("manager").toMap()!=manager
                || code.isEmpty() || signalCallbacks || timerCallbacks || evaluating || timers) {
            _complete=false;return;
        }
        const QVariantMap work {{"signalCallbacks",static_cast<qulonglong>(signalCallbacks)},
            {"timerCallbacks",static_cast<qulonglong>(timerCallbacks)},{"evaluating",evaluating},
            {"timers",static_cast<qulonglong>(timers)}};
        if (!append("shutdown-drained",token,manager,code,work)) { return; }
        (*state)["code"]=code;(*state)["stage"]=1;
    }

    // Call only from the actual QThread::finished DirectConnection. A caller
    // must capture token by value; do not capture the ScriptManager pointer.
    void threadFinished(const QString& token) {
        std::lock_guard<std::mutex> guard(_mutex);
        if (_instance.isEmpty() || token.isEmpty()) { return; }
        auto* state=find(token);
        if (!state || state->value("stage").toInt()!=1) { _complete=false;return; }
        if (append("thread-finished",token,state->value("manager").toMap(),state->value("code"),QVariant())) {
            (*state)["stage"]=2;
        }
    }

    QVariantMap snapshot() const {
        std::lock_guard<std::mutex> guard(_mutex);
        if (_instance.isEmpty()) { return {}; }
        return {{"scriptTerminalVersion",1},{"instance",_instance},{"processId",QCoreApplication::applicationPid()},
            {"complete",_complete},{"eventSequence",static_cast<qulonglong>(_events.size())},{"events",_events}};
    }

private:
    ScriptTerminalObservation() {
        if (QCoreApplication::arguments().contains("--testScript")) { _instance=nonce();_clock.start(); }
    }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    QVariantMap* find(const QString& token) {
        for (auto it=_threads.begin();it!=_threads.end();++it) {
            if (it.value().value("threadInstance").toString()==token) { return &it.value(); }
        }
        return nullptr;
    }
    bool append(const QString& kind,const QString& token,const QVariantMap& manager,const QVariant& code,const QVariant& work) {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();const auto mono=_clock.elapsed();
        if (!_complete || _events.size()>=512 || epoch<=0 || mono<0 || epoch<_lastEpoch || mono<_lastMono) {
            _complete=false;return false;
        }
        _events.append(QVariantMap{{"eventSequence",static_cast<qulonglong>(_events.size()+1)},
            {"capturedEpochMs",epoch},{"monotonicMs",mono},{"kind",kind},{"threadInstance",token},
            {"manager",manager},{"code",code},{"work",work}});
        _lastEpoch=epoch;_lastMono=mono;return true;
    }
    mutable std::mutex _mutex;
    QString _instance;
    bool _complete {true};
    QElapsedTimer _clock;
    qint64 _lastEpoch {0},_lastMono {0};
    QMap<QString,QVariantMap> _threads;
    QVariantList _events;
};
} // namespace overte::e2e
#endif
