// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Original Snapshot.js events with VM-owned caller provenance. No capture,
// cancellation, state setter, supplied caller or history reset is exposed.
class PhoneSnapshotScriptHistory {
public:
    PhoneSnapshotScriptHistory() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }
    void record(const QString& kind,const QString& id,const QString& mode,int revision,const QVariantMap& caller) {
        if (!enabled()) { return; }
        QMutexLocker lock(&_mutex);
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (!_complete || _events.size()>=256 || epoch<=0 || epoch<_epoch || elapsed<_elapsed
                || !QStringList{"pending","processing","complete","cancelled","error"}.contains(kind)
                || !QRegularExpression("\\Asnap_[0-9]{1,16}_[0-9]{1,10}\\z").match(id).hasMatch()
                || !QStringList{"still","animated","panorama","cubemap"}.contains(mode) || revision<=0
                || caller.value("callerVersion")!=2 || caller.value("method")!="featureCaptureEvent"
                || caller.value("sequence").toULongLong()==0 || caller.value("invokedEpochMs").toLongLong()<=0
                || caller.value("invokedEpochMs").toLongLong()>epoch || caller.value("manager").toMap().isEmpty()
                || caller.value("code").toMap().isEmpty() || caller.value("compilation").toMap().isEmpty()
                || caller.value("snapshotWork").toMap().isEmpty()
                || QJsonDocument::fromVariant(caller).toJson(QJsonDocument::Compact).size()>16384) {
            _complete=false;return;
        }
        _epoch=epoch;_elapsed=elapsed;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"kind",kind},{"id",id},{"mode",mode},
            {"revision",revision},{"capturedEpochMs",epoch},{"elapsedMs",elapsed},{"caller",caller}});
    }
    QVariantMap snapshot() {
        if (!enabled()) { return {}; }
        QMutexLocker lock(&_mutex);
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_epoch || elapsed<_elapsed) { _complete=false; }
        return {{"snapshotScriptHistoryVersion",1},{"instance",_instance},{"complete",_complete},
            {"sequence",_events.size()},{"events",_events}};
    }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    QMutex _mutex;QElapsedTimer _clock;QString _instance;QVariantList _events;
    bool _complete{true};qint64 _epoch{0},_elapsed{0};
};
} // namespace overte::e2e
#endif
