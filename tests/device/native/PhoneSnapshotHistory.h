// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Passive original callbacks only. There is no reset, capture/export input or
// desired state API. Overflow/clock regression permanently invalidates history.
class PhoneSnapshotHistory {
public:
    PhoneSnapshotHistory() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }
    void record(const QString& kind,const QString& id,const QString& phase={},const QString& path={},const QString& error={}) {
        if (!enabled()) { return; }
        QMutexLocker lock(&_mutex);
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (!_complete || _events.size()>=256 || epoch<=0 || epoch<_epoch || elapsed<_elapsed
                || !QStringList{"capture-begin","capture-status","upload-begin","upload-status"}.contains(kind)
                || id.isEmpty() || id.size()>2048 || path.size()>2048 || error.size()>256
                || ((kind=="capture-begin" || kind=="capture-status")
                    && !QRegularExpression("\\A[A-Za-z0-9_-]{1,64}\\z").match(id).hasMatch())
                || ((kind=="capture-begin" || kind=="upload-begin") && (!phase.isEmpty() || !error.isEmpty()))
                || (kind=="capture-status" && !QStringList{"processing","complete","cancelled","error"}.contains(phase))
                || (kind=="upload-status" && !QStringList{"success","cancelled","error"}.contains(phase))) {
            _complete=false;return;
        }
        _epoch=epoch;_elapsed=elapsed;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"kind",kind},{"id",id},{"phase",phase},
            {"path",path},{"error",error},{"capturedEpochMs",epoch},{"elapsedMs",elapsed}});
    }
    QVariantMap snapshot() {
        if (!enabled()) { return {}; }
        QMutexLocker lock(&_mutex);
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_epoch || elapsed<_elapsed) { _complete=false; }
        return {{"snapshotHistoryVersion",1},{"instance",_instance},{"complete",_complete},
            {"sequence",_events.size()},{"events",_events}};
    }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    QMutex _mutex;QElapsedTimer _clock;QString _instance;QVariantList _events;
    bool _complete{true};qint64 _epoch{0},_elapsed{0};
};
} // namespace overte::e2e
#endif
