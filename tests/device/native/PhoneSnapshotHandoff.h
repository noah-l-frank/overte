// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QObject>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QTimer>
#include <QUuid>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
// Foreground authorization starts only passive original getters. No input,
// desired state, caller source, URI, target component or source refresh exists
// in this lease. Paused Qt events yield an old frame, never fresh success.
class PhoneSnapshotHandoff : public QObject {
public:
    using Read=std::function<QVariantMap()>;
    using Publish=std::function<void(const QVariantMap&)>;
    static constexpr int INTERVAL_MS=250,LEASE_MS=60000,MAX_BYTES=1024*1024;
    PhoneSnapshotHandoff(const QString& run,const QString& handoff,Read read,Publish publish)
        : _run(run),_handoff(handoff),_read(std::move(read)),_publish(std::move(publish)) {
        _timer.setInterval(INTERVAL_MS);_timer.setTimerType(Qt::PreciseTimer);
        connect(&_timer,&QTimer::timeout,this,[this] { sample(); });
    }
    static bool nonce(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static bool validCommand(const QVariantMap& input) {
        const auto value=QJsonObject::fromVariantMap(input);const auto keys=value.keys();
        return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId","handoffId","operation"}
            && value.value("schemaVersion")==QJsonValue(1) && value.value("action")==QJsonValue("phone-snapshot-handoff")
            && nonce(value.value("commandId").toString()) && nonce(value.value("runId").toString()) && nonce(value.value("handoffId").toString())
            && QSet<QString>{"start","observe","retire"}.contains(value.value("operation").toString());
    }
    bool start() {
        if (!enabled() || _reading || _retired || !_read || !_publish || !nonce(_run) || !nonce(_handoff)) { return false; }
        if (_started) { return _error.isEmpty() && _timer.isActive(); }
        _started=QDateTime::currentMSecsSinceEpoch();if (_started<=0) { return fail("clock-invalid"); }
        _age.start();_timer.start();sample();return _error.isEmpty() && _timer.isActive();
    }
    bool retire() {
        if (!enabled() || !_started || _reading) { return false; }
        _timer.stop();_retired=true;sample();return !_reading && !_timer.isActive();
    }
    bool retired() const { return _retired && !_timer.isActive() && !_reading; }
    QVariantMap summary() const {
        return {{"runId",_run},{"handoffId",_handoff},{"instance",_instance},{"retired",retired()},
            {"timerActive",_timer.isActive()},{"readActive",_reading},{"complete",_error.isEmpty()}};
    }
    QVariantMap observation() const {
        return {{"snapshotHandoffVersion",1},{"instance",_instance},{"runId",_run},{"handoffId",_handoff},
            {"processId",QCoreApplication::applicationPid()},{"sequence",static_cast<qulonglong>(_sequence)},
            {"startedEpochMs",_started},{"deadlineEpochMs",_started+LEASE_MS},{"capturedEpochMs",_captured},
            {"complete",_error.isEmpty()},{"error",_error},{"retired",retired()},{"timerActive",_timer.isActive()},
            {"readActive",_reading},{"source",_source}};
    }
private:
    bool enabled() const { return QCoreApplication::instance() && QThread::currentThread()==thread()
        && QCoreApplication::arguments().contains("--testScript"); }
    bool fail(const QString& reason) { if (_error.isEmpty()) { _error=reason; }_timer.stop();return false; }
    void sample() {
        if (!enabled() || !_started) { return; }
        if (_reading) { fail("reentrant-source");return; }
        if (!_retired && _age.elapsed()>=LEASE_MS) { fail("lease-expired"); }
        if (_sequence>=1000000000) { fail("source-limit");return; }
        const auto requested=QDateTime::currentMSecsSinceEpoch();QElapsedTimer elapsed;elapsed.start();
        if (requested<_captured || requested<_started) { fail("clock-regressed"); }
        _reading=true;QVariantMap original;
        try { original=_read(); }catch (...) { fail("source-unavailable"); }
        _reading=false;
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        if (original.isEmpty() || QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact).size()>MAX_BYTES
                || captured<requested || captured-requested>=1500 || elapsed.elapsed()>=1500) { fail("source-unavailable"); }
        _source=std::move(original);_captured=captured;++_sequence;
        // Publish contains only this actual acquisition. The reader separately
        // validates all individual original getter contracts and current age.
        try { _publish(observation()); }catch (...) { fail("publication-unavailable"); }
    }
    QString _run,_handoff,_error;const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    Read _read;Publish _publish;QTimer _timer;QElapsedTimer _age;QVariantMap _source;
    qint64 _started{0},_captured{0};quint64 _sequence{0};bool _reading{false},_retired{false};
};
}
#endif
