// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>
#include <QVariantMap>
#include <QMap>

namespace overte::e2e {
// Actual EntityScriptingInterface API returns, captured on the invoking VM
// thread. An add-returned UUID is a real return value; a delete-returned UUID
// is only the original operand. Successful removal and weak expiry are
// independent EntityTree observations, never inferred from either API return.
class CreateEntityObservation {
public:
    CreateEntityObservation() { _clock.start(); }
    static CreateEntityObservation& instance() { static CreateEntityObservation value;return value; }
    void returned(const QString& kind,const QUuid& id,bool localTree,const QVariantMap& context) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || context.isEmpty()) { return; }
        QMutexLocker lock(&_mutex);
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        const auto manager=context.value("manager").toMap(),code=context.value("code").toMap();
        const auto method=context.value("method").toString(),who=manager.value("instance").toString();
        const auto sequence=context.value("sequence").toULongLong();
        if (!_complete || _events.size()>=512 || context.value("callerVersion")!=1 || who.isEmpty() || !manager.value("assigned").toBool()
                || !code.value("submitted").toBool() || sequence==0 || sequence<=_calls.value(who)
                || (kind=="add-returned" ? method!="addEntity" : kind!="delete-returned" || method!="deleteEntity")
                || epoch<=0 || epoch<_epoch || elapsed<_elapsed || context.value("invokedEpochMs").toLongLong()>epoch) {
            _complete=false;return;
        }
        // Select original fields into this native DTO. Do not accept a caller,
        // code identity or entity ID from an observer/JavaScript test argument.
        QVariantMap caller{{"callerVersion",context.value("callerVersion")},{"method",method},{"sequence",context.value("sequence")},
            {"invokedEpochMs",context.value("invokedEpochMs")},{"manager",manager},{"code",code}};
        _calls[who]=sequence;_epoch=epoch;_elapsed=elapsed;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"eventId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"kind",kind},{"clock",QVariantMap{{"epochMs",epoch},{"monotonicMs",elapsed}}},{"caller",caller},
            {"entityId",id.isNull() ? QVariant() : QVariant(id.toString(QUuid::WithoutBraces))},{"localTreeAvailable",localTree}});
    }
    QVariantMap snapshot() const {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        QMutexLocker lock(&_mutex);
        return {{"createEntityCallsVersion",1},{"instance",_instance},{"complete",_complete},{"events",_events}};
    }
private:
    mutable QMutex _mutex;QElapsedTimer _clock;
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantList _events;QMap<QString,quint64> _calls;
    qint64 _epoch {0},_elapsed {0};bool _complete {true};
};
} // namespace overte::e2e
#endif
