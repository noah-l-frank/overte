// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "PlacesHttpObservation.h"
#include <QHash>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QTimer>

namespace overte::e2e {
// Actual installed Avatar/Pal timer state. Counter snapshots avoid logging a
// 100ms periodic callback forever; immutable births and native destruction are
// retained. pendingDispatch spans the original entire timerFired invocation,
// including singleShot destruction before callback entry.
class AvatarUiWorkObservation {
public:
    QString created(int handle,const QStringList& callers,const QTimer* timer) {
        const QStringList suffixes{"/system/avatarapp.js","/system/pal.js","/system/libraries/peopleConnection.js",
            "/modules/request.js","/system/request-service.js"};
        bool relevant{false};for (const auto& caller:callers) { for (const auto& suffix:suffixes) {
            relevant=relevant || PlacesHttpObservation::installed(caller,suffix);
        } }
        if (!enabled() || !relevant) { return {}; }QMutexLocker lock(&_mutex);
        if (!_complete || !timer || handle<=0 || _handles.contains(handle) || _states.size()>=256 || callers.size()>32) {
            _complete=false;return {};
        }
        const auto id=PlacesHttpObservation::nonce();const auto epoch=now();_handles.insert(handle,id);
        _states.insert(id,QVariantMap{{"timerId",id},{"handle",handle},{"callerChain",callers},{"createdEpochMs",epoch},
            {"singleShot",timer->isSingleShot()},{"intervalMs",timer->interval()},{"activeAtBirth",timer->isActive()},
            {"remainingAtBirthMs",timer->remainingTime()},{"destroyedEpochMs",QVariant()},
            {"fired",0},{"entered",0},{"left",0},{"depth",0},{"pendingDispatch",0},
            {"lastFiredEpochMs",QVariant()},{"lastCallbackEpochMs",QVariant()},{"lastDispatchEpochMs",QVariant()}});
        return id;
    }
    QString fired(int handle,const QTimer* timer) {
        QMutexLocker lock(&_mutex);const auto id=_handles.value(handle);if (id.isEmpty()) { return {}; }
        if (!_complete || !timer || !_states.contains(id)) { _complete=false;return {}; }
        auto& row=_states[id];
        if (row.value("destroyedEpochMs").isValid() || row.value("pendingDispatch").toInt()>=16) { _complete=false;return {}; }
        increment(row,"fired");increment(row,"pendingDispatch");row["lastFiredEpochMs"]=now();return id;
    }
    void callback(const QString& id,bool entering) {
        if (id.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        if (!_complete || !_states.contains(id)) { _complete=false;return; }auto& row=_states[id];
        const auto depth=row.value("depth").toInt();
        if (row.value("pendingDispatch").toInt()<=0 || (entering && depth>=16) || (!entering && depth<=0)) { _complete=false;return; }
        increment(row,entering ? "entered" : "left");row["depth"]=depth+(entering ? 1 : -1);row["lastCallbackEpochMs"]=now();
    }
    void dispatchReturned(const QString& id) {
        if (id.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        if (!_complete || !_states.contains(id)) { _complete=false;return; }auto& row=_states[id];
        const auto pending=row.value("pendingDispatch").toInt();
        if (pending<=0 || row.value("depth").toInt()>pending-1) { _complete=false;return; }
        row["pendingDispatch"]=pending-1;row["lastDispatchEpochMs"]=now();
    }
    void destroyed(const QString& id) {
        if (id.isEmpty()) { return; }QMutexLocker lock(&_mutex);
        const auto handle=_handles.key(id,-1);
        if (!_complete || handle<=0 || !_states.contains(id) || _states[id].value("destroyedEpochMs").isValid()) { _complete=false;return; }
        _handles.remove(handle);_states[id]["destroyedEpochMs"]=now();
    }
    QVariantMap snapshot() const {
        QMutexLocker lock(&_mutex);QVariantList states;
        for (auto it=_states.cbegin();it!=_states.cend();++it) { states.append(it.value()); }
        return {{"avatarUiWorkVersion",1},{"instance",_instance},{"complete",_complete},{"timers",states}};
    }
    void unavailable() { QMutexLocker lock(&_mutex);_complete=false; }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    void increment(QVariantMap& row,const QString& field) {
        const auto value=row.value(field).toULongLong();
        if (value>=9007199254740991ULL) { _complete=false;return; }
        row[field]=static_cast<qulonglong>(value+1);
    }
    qint64 now() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if (epoch<=0 || epoch<_epoch) { _complete=false;return 0; }
        _epoch=epoch;return epoch;
    }
    mutable QMutex _mutex;
    const QString _instance{PlacesHttpObservation::nonce()};
    QHash<int,QString> _handles;
    QMap<QString,QVariantMap> _states;
    qint64 _epoch{0};bool _complete{true};
};
} // namespace overte::e2e
#endif
