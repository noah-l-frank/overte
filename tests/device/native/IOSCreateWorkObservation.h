// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "IOSCreateLifetimes.h"
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QSet>
#include <QUrl>

namespace overte::e2e {
class IOSCreateWorkObservation {
public:
    static IOSCreateWorkObservation& instance() { static IOSCreateWorkObservation value;return value; }
    // Called directly on the real invoking VM thread. The caller map is made
    // by ScriptObjectV8Proxy, never accepted from JavaScript arguments.
    void event(const QVariantMap& value,const QVariantMap& caller) {
        if (!QCoreApplication::arguments().contains("--testScript")) { return; }
        QMutexLocker lock(&_mutex);
        const auto role=value.value("role").toString(),kind=value.value("event").toString();
        const QMap<QString,QString> paths{{"edit","/system/create/edit.js"},
            {"bridge","/system/create/modules/nativeCreateBridge.js"},
            {"entity-list","/system/create/entityList/entityList.js"},
            {"voxels","/system/create/editModes/editVoxels.js"}};
        QStringList fields{"createWorkEventVersion","role","sourceUrl","event","closure","call","state"};fields.sort();
        const auto json=QJsonObject::fromVariantMap(value);const QUrl source(value.value("sourceUrl").toString());
        if (!_complete || value.keys()!=fields || json.value("createWorkEventVersion")!=QJsonValue(1)
                || !paths.contains(role) || !source.isValid() || !source.path().endsWith(paths.value(role))
                || !source.userInfo().isEmpty() || source.hasQuery() || source.hasFragment()
                || !QStringList{"snapshot","entry","returned","finally","ending"}.contains(kind)
                || !json.value("state").isObject() || QJsonDocument(json.value("state").toObject()).toJson().size()>8192
                || caller.value("method")!="featureIOSCreateEvent" || caller.value("manager").toMap().isEmpty()
                || caller.value("codeSources").toMap().isEmpty() || _sequence>=1000000000) { _complete=false;return; }
        const auto manager=caller.value("manager").toMap();const auto id=manager.value("instance").toString();
        const auto sources=caller.value("codeSources").toMap();
        if (!manager.value("assigned").toBool() || !caller.value("code").toMap().value("submitted").toBool()
                || !sources.value("complete").toBool() || id.isEmpty()) { _complete=false;return; }
        auto& row=_roles[role];
        if (row.isEmpty()) {
            row={{"role",role},{"sourceUrl",source.toString()},{"manager",manager},{"code",caller.value("code")},
                {"calls",QVariantList{}},{"events",QVariantList{}},{"ended",false}};
        } else if (row.value("manager")!=manager || row.value("code")!=caller.value("code")
                || row.value("sourceUrl")!=source.toString() || row.value("ended").toBool()) { _complete=false;return; }
        const auto call=json.value("call").toDouble(-1);const auto closure=value.value("closure").toString();
        const auto callerSequence=caller.value("sequence").toULongLong();
        if (callerSequence<=_callerSequences.value(id) || call<0 || call>1000000000 || call!=static_cast<quint64>(call)
                || closure.size()>64 || ((kind=="snapshot" || kind=="ending")!=(call==0 && closure.isEmpty()))) {
            _complete=false;return;
        }
        _callerSequences[id]=callerSequence;
        auto calls=row.value("calls").toList();
        if (kind=="entry") {
            if (calls.size()>=32 || call<=_lastCalls.value(role)) { _complete=false;return; }
            _lastCalls[role]=call;calls.append(QVariantMap{{"call",call},{"closure",closure},{"returned",false}});
        } else if (kind=="returned" || kind=="finally") {
            if (calls.isEmpty()) { _complete=false;return; }
            auto current=calls.last().toMap();
            if (current.value("call").toDouble()!=call || current.value("closure")!=closure
                    || (kind=="returned" && current.value("returned").toBool())) { _complete=false;return; }
            if (kind=="returned") { current["returned"]=true;calls.last()=current; }
            else { calls.removeLast(); }
        }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        QVariantMap event{{"sequence",static_cast<qulonglong>(++_sequence)},{"capturedEpochMs",epoch},
            {"callerSequence",static_cast<qulonglong>(callerSequence)},{"invokedEpochMs",caller.value("invokedEpochMs")},
            {"event",kind},{"closure",closure},{"call",call},{"state",value.value("state")}};
        auto history=row.value("events").toList();
        // Repeated read-only heartbeats refresh actual VM liveness. Every real
        // closure entry/return/finally and every state transition stays retained.
        if (kind!="snapshot" || row.value("state")!=value.value("state")) {
            if (history.size()>=512) { _complete=false;return; }history.append(event);
        }
        row["events"]=history;row["calls"]=calls;row["state"]=value.value("state");
        row["latest"]=event;row["codeSources"]=sources;row["ended"]=(kind=="ending");
    }
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosCreateWorkVersion","native-main-create-work",request,run,[&] {
            QMutexLocker lock(&_mutex);QVariantList rows;
            for (const auto& row:_roles) { rows.append(row); }
            return QVariantMap{{"complete",_complete},{"eventSequence",static_cast<qulonglong>(_sequence)},{"roles",rows},
                {"entityLifetimes",IOSCreateLifetimes::instance().snapshot()}};
        });
    }
private:
    QMutex _mutex;bool _complete {true};quint64 _sequence {0};NativeReadBracket _bracket;
    QMap<QString,QVariantMap> _roles;QMap<QString,quint64> _callerSequences,_lastCalls;
};
} // namespace overte::e2e
#endif
