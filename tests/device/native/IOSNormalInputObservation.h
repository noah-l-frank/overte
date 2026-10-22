// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>

namespace overte::e2e {

// Passive original command reception and return. It changes no UI control,
// dispatches no event and deliberately excludes all login/private input.
class IOSNormalInputObservation {
public:
    enum class Profile { Avatar };
    static IOSNormalInputObservation& shared() { static IOSNormalInputObservation value;return value; }

    QString received(Profile profile,const QJsonObject& outer,const QString& control,const QJsonObject& root) {
        QMutexLocker locker(&_mutex);
        if (profile!=Profile::Avatar) { return {}; }
        const auto input=outer.value("input").toObject();
        if (!control.startsWith("avatar.") && !control.startsWith("people.")
                && control!="tablet.home" && !control.startsWith("tablet.page.")) { return {}; }
        if ((control=="tablet.home" || control.startsWith("tablet.page.")) && root.isEmpty()) { return {}; }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
        QJsonObject details{{"outerCommandId",outer.value("commandId")},{"command",input},
            {"controlId",control},{"root",root.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(root)}};
        if (!append(id,"received",details)) { return {}; }
        return id;
    }

    void returned(const QString& id,const QJsonObject& originalReceipt) {
        if (id.isEmpty()) { return; }QMutexLocker locker(&_mutex);
        append(id,"returned",originalReceipt);
    }

    QJsonObject observation(Profile profile,const QString& request,const QString& run) {
        QMutexLocker locker(&_mutex);const auto before=clock();
        if (profile!=Profile::Avatar) { return {}; }
        QJsonObject source{{"complete",_complete},{"events",_events}};
        return QJsonObject{{"iosNormalInputsVersion",1},{"profile","avatar"},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-process-normal-inputs"},{"clockBefore",before},{"clockAfter",clock()},{"source",source}};
    }

private:
    IOSNormalInputObservation() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }
    QJsonObject clock() const {
        return QJsonObject{{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"monotonicMs",static_cast<double>(_clock.elapsed())}};
    }
    bool append(const QString& id,const QString& kind,const QJsonObject& details) {
        if (!_complete) { return false; }
        QJsonObject row{{"sequence",static_cast<double>(_events.size()+1)},{"eventId",QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"inputId",id},{"kind",kind},{"clock",clock()},{"details",details}};
        const auto bytes=QJsonDocument(row).toJson(QJsonDocument::Compact).size();
        if (_events.size()>=512 || _bytes+bytes>524288) { _complete=false;return false; }
        _bytes+=bytes;_events.append(row);return true;
    }
    QMutex _mutex;
    QElapsedTimer _clock;
    QString _instance;
    QJsonArray _events;
    int _bytes {0};
    quint64 _sequence {0};
    bool _complete {true};
};
} // namespace overte::e2e
#endif
