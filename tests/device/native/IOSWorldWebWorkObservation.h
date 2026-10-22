// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include <QJsonObject>
#include <QMutex>
#include <QRegularExpression>

namespace overte::e2e {
class IOSWorldWebWorkObservation final {
public:
    static IOSWorldWebWorkObservation& instance() { static IOSWorldWebWorkObservation actual;return actual; }
    // Caller is supplied only by the actual ScriptObjectV8Proxy invocation.
    // JavaScript supplies original callback arguments, never native identity.
    void event(const QVariantMap& value,const QVariantMap& caller) {
        const auto args=QCoreApplication::arguments();
        if (!args.contains("--testScript") || !args.contains("--testResultsLocation")) { return; }
        QMutexLocker guard(&_mutex);const auto json=QJsonObject::fromVariantMap(value);
        QStringList fields{"worldWebWorkEventVersion","runId","nonce","event","call","payload"};fields.sort();
        const auto run=value.value("runId").toString(),nonce=value.value("nonce").toString(),kind=value.value("event").toString();
        const auto manager=caller.value("manager").toMap(),code=caller.value("code").toMap();
        const auto call=json.value("call").toDouble(-1);const auto callerSequence=caller.value("sequence").toULongLong();
        const auto payload=value.value("payload").toMap();
        const QRegularExpression id("\\A[0-9a-f]{32}\\z");
        if (!_complete || value.keys()!=fields || json.value("worldWebWorkEventVersion")!=QJsonValue(1)
                || !id.match(run).hasMatch() || !id.match(nonce).hasMatch() || !json.value("payload").isObject()
                || QJsonDocument::fromVariant(payload).toJson(QJsonDocument::Compact).size()>8192
                || caller.value("method")!="featureIOSWorldWebEvent" || !manager.value("assigned").toBool()
                || !code.value("submitted").toBool() || call<0 || call>1000000000 || call!=static_cast<quint64>(call)
                || _sequence>=1000000000 || (_workers.size()>=32 && !_workers.contains(run+nonce))) { _complete=false;return; }
        auto& row=_workers[run+nonce];
        if (row.isEmpty()) {
            if (kind!="loaded" || call!=0) { _complete=false;return; }
            row={{"runId",run},{"nonce",nonce},{"manager",manager},{"code",code},{"calls",QVariantList{}},
                {"events",QVariantList{}},{"ended",false}};
        } else if (row.value("manager")!=manager || row.value("code")!=code || row.value("ended").toBool() || kind=="loaded") {
            _complete=false;return;
        }
        const auto instance=manager.value("instance").toString();
        if (instance.isEmpty() || !callerSequence || callerSequence<=_callers.value(instance)) { _complete=false;return; }
        _callers[instance]=callerSequence;auto calls=row.value("calls").toList();
        if (kind!="loaded") {
            const auto dash=kind.lastIndexOf('-');const auto prefix=kind.left(dash),phase=kind.mid(dash+1);
            if (!QStringList{"world-event","script-reply","ending"}.contains(prefix)
                    || !QStringList{"enter","return","finally"}.contains(phase) || call<=0) { _complete=false;return; }
            if (phase=="enter") {
                if (calls.size()>=32 || call<=_lastCalls.value(run+nonce)) { _complete=false;return; }
                _lastCalls[run+nonce]=call;
                calls.append(QVariantMap{{"call",call},{"kind",prefix},{"payload",payload},{"returned",false}});
            } else {
                if (calls.isEmpty()) { _complete=false;return; }
                auto current=calls.last().toMap();
                if (current.value("call").toDouble()!=call || current.value("kind")!=prefix || current.value("payload")!=payload
                        || (phase=="return" && current.value("returned").toBool())) { _complete=false;return; }
                if (phase=="return") { current["returned"]=true;calls.last()=current; }
                else { calls.removeLast(); }
            }
        }
        auto events=row.value("events").toList();
        if (events.size()>=256) { _complete=false;return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<_epoch || caller.value("invokedEpochMs").toLongLong()>epoch) { _complete=false;return; }
        _epoch=epoch;
        events.append(QVariantMap{{"sequence",static_cast<qulonglong>(++_sequence)},{"event",kind},{"call",call},{"payload",payload},
            {"callerSequence",static_cast<qulonglong>(callerSequence)},{"invokedEpochMs",caller.value("invokedEpochMs")},{"capturedEpochMs",epoch}});
        row["events"]=events;row["calls"]=calls;row["ended"]=(kind=="ending-finally");
    }
    QVariantMap read(const QString& request,const QString& run) {
        return _bracket.read("iosWorldWebWorkVersion","native-main-ios-world-web-work",request,run,[&] {
            QMutexLocker guard(&_mutex);QVariantList rows;
            for (const auto& row:_workers) { if (row.value("runId")==run) { rows.append(row); } }
            return QVariantMap{{"complete",_complete},{"eventSequence",static_cast<qulonglong>(_sequence)},{"workers",rows}};
        });
    }
private:
    NativeReadBracket _bracket;QMutex _mutex;bool _complete {true};quint64 _sequence {0};qint64 _epoch {0};
    QMap<QString,QVariantMap> _workers;QMap<QString,quint64> _callers,_lastCalls;
};
} // namespace overte::e2e
#endif
