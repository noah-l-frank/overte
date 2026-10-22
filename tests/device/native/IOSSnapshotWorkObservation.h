// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QUrl>

namespace overte::e2e {
class IOSSnapshotWorkObservation {
public:
    static IOSSnapshotWorkObservation& instance() {static IOSSnapshotWorkObservation value;return value;}
    void event(const QVariantMap& value,const QVariantMap& caller) {
        if (!QCoreApplication::arguments().contains("--testScript")) {return;}
        QMutexLocker guard(&_mutex);const auto json=QJsonObject::fromVariantMap(value);
        QStringList fields{"snapshotWorkEventVersion","role","sourceUrl","event","closure","call","state"};fields.sort();
        const QUrl source(value.value("sourceUrl").toString());const auto kind=value.value("event").toString();
        const auto manager=caller.value("manager").toMap(),code=caller.value("code").toMap(),sources=caller.value("codeSources").toMap();
        const auto id=manager.value("instance").toString();const auto sequence=caller.value("sequence").toULongLong();
        const auto call=json.value("call").toDouble(-1);const auto closure=value.value("closure").toString();
        if (!_complete || value.keys()!=fields || json.value("snapshotWorkEventVersion")!=QJsonValue(1)
                || value.value("role")!="snapshot" || !source.isValid() || !QStringList{"file","qrc"}.contains(source.scheme())
                || !source.authority().isEmpty() || source.hasQuery() || source.hasFragment() || !source.path().endsWith("/system/snapshot.js")
                || !QStringList{"snapshot","entry","returned","finally","ending"}.contains(kind)
                || !json.value("state").isObject() || QJsonDocument(json.value("state").toObject()).toJson().size()>8192
                || caller.value("method")!="featureIOSSnapshotEvent" || !manager.value("assigned").toBool()
                || !code.value("submitted").toBool() || !sources.value("complete").toBool() || id.isEmpty()
                || sequence<=_callers.value(id) || call<0 || call>1000000000 || call!=static_cast<quint64>(call)
                || closure.size()>64 || ((kind=="snapshot" || kind=="ending")!=(call==0 && closure.isEmpty()))
                || _sequence>=1000000000 || (_workers.size()>=8 && !_workers.contains(id))) {_complete=false;return;}
        auto& row=_workers[id];
        if (row.isEmpty()) {
            if (kind!="snapshot") {_complete=false;return;}
            row={{"sourceUrl",source.toString()},{"manager",manager},{"code",code},{"calls",QVariantList{}},{"events",QVariantList{}},{"ended",false}};
        } else if (row.value("manager")!=manager || row.value("code")!=code || row.value("sourceUrl")!=source.toString() || row.value("ended").toBool()) {
            _complete=false;return;
        }
        auto calls=row.value("calls").toList();
        if (kind=="entry") {
            if (calls.size()>=32 || call<=_lastCalls.value(id)) {_complete=false;return;}
            _lastCalls[id]=call;calls.append(QVariantMap{{"call",call},{"closure",closure},{"returned",false}});
        } else if (kind=="returned" || kind=="finally") {
            if (calls.isEmpty()) {_complete=false;return;}auto current=calls.last().toMap();
            if (current.value("call").toDouble()!=call || current.value("closure")!=closure
                    || (kind=="returned" && current.value("returned").toBool())) {_complete=false;return;}
            if (kind=="returned") {current["returned"]=true;calls.last()=current;} else {calls.removeLast();}
        }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<_epoch || caller.value("invokedEpochMs").toLongLong()>epoch) {_complete=false;return;}_epoch=epoch;
        _callers[id]=sequence;
        QVariantMap event{{"sequence",static_cast<qulonglong>(++_sequence)},{"capturedEpochMs",epoch},
            {"callerSequence",static_cast<qulonglong>(sequence)},{"invokedEpochMs",caller.value("invokedEpochMs")},
            {"event",kind},{"closure",closure},{"call",call},{"state",value.value("state")}};
        auto events=row.value("events").toList();
        if (kind!="snapshot" || row.value("state")!=value.value("state")) {
            if (events.size()>=512) {_complete=false;return;}events.append(event);
        }
        row["events"]=events;row["calls"]=calls;row["state"]=value.value("state");row["latest"]=event;
        row["codeSources"]=sources;row["ended"]=(kind=="ending");
    }
    QVariantMap read(const QString& request,const QString& run,const std::function<QVariantMap()>& timers) {
        return _bracket.read("iosSnapshotWorkVersion","native-main-snapshot-work",request,run,[&]() -> QVariantMap {
            const auto original=timers();if (original.isEmpty()) {return {};}
            QMutexLocker guard(&_mutex);QVariantList rows;
            for (const auto& row:_workers) {rows.append(row);}
            return {{"complete",_complete},{"eventSequence",static_cast<qulonglong>(_sequence)},{"workers",rows},{"timerSources",original}};
        });
    }
private:
    NativeReadBracket _bracket;QMutex _mutex;bool _complete{true};quint64 _sequence{0};qint64 _epoch{0};
    QMap<QString,QVariantMap> _workers;QMap<QString,quint64> _callers,_lastCalls;
};
}
#endif
