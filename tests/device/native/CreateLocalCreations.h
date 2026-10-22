// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QVariantMap>
#include <QSet>
#include <QUuid>
namespace overte::e2e {
// Successful original local Tree insertion only; never a requested name, ACK,
// remote Tree packet or caller-selected adoption. No strong entity references.
class CreateLocalCreations {
public:
    QVariantMap snapshot(const QString& run) {
        QMutexLocker lock(&_mutex);
        if (!_valid || !enabled() || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
        if (!_runs.contains(run)) {
            if (_runs.size()>=4) {return {};}
            _runs.insert(run,_sequence);
        }
        QVariantList rows;
        for (const auto& item:_events) {if (item.toMap().value("sequence").toULongLong()>_runs.value(run)) {rows.append(item);}}
        return {{"createLocalCreationsVersion",1},{"armedAfterSequence",_runs.value(run)},
            {"lastSequence",_sequence},{"events",rows}};
    }
    void inserted(const QUuid& id,const QString& type,quint64 created,const QUuid& session,const QString& host) {
        QMutexLocker lock(&_mutex);
        if (!enabled() || _runs.isEmpty() || !_valid || host!="domain") {return;}
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (id.isNull() || session.isNull() || !created || created>9007199254740991ULL || now<=0 || now<_epoch
                || type.isEmpty() || type.size()>64 || _ids.contains(id) || _events.size()>=128) {_valid=false;return;}
        _epoch=now;_ids.insert(id);
        _events.append(QVariantMap{{"sequence",++_sequence},{"id",id.toString(QUuid::WithoutBraces)},
            {"type",type},{"createdEpochUs",created},{"sessionId",session.toString(QUuid::WithoutBraces)},
            {"hostType",host},{"observedEpochMs",now}});
    }
private:
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    QMutex _mutex;bool _valid{true};quint64 _sequence{0};qint64 _epoch{0};
    QHash<QString,quint64> _runs;QSet<QUuid> _ids;QVariantList _events;
};
} // namespace overte::e2e
#endif
