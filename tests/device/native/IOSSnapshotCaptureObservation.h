// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NativeReadBracket.h"
#include "../../../interface/src/ui/SnapshotCapture.h"
#include <QHash>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QRegularExpression>

namespace overte::e2e {
// Weak observers never extend a renderer, worker, timer or Qt callback owner.
class IOSSnapshotCaptureObservation {
public:
    static IOSSnapshotCaptureObservation& instance() {static IOSSnapshotCaptureObservation value;return value;}
    void begin(const SnapshotCapture& capture) {
        if (!enabled() || !capture) {return;}QMutexLocker guard(&_mutex);
        if (!_complete || _captures.size()>=64) {_complete=false;return;}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _byPointer[capture.get()]=id;
        _captures[id]={capture,{{"instance",id},{"requestId",request(capture->id)},{"bornEpochMs",QDateTime::currentMSecsSinceEpoch()}}};
        append(id,"begin");
    }
    void event(const SnapshotCapture& capture,const QString& kind,const QVariantMap& detail={}) {
        if (!enabled() || !capture) {return;}QMutexLocker guard(&_mutex);
        const auto id=_byPointer.value(capture.get());
        if (id.isEmpty() || _captures.value(id).weak.lock()!=capture) {_complete=false;return;}
        append(id,kind,detail);
    }
    void resource(const SnapshotCapture& capture,QObject* object,const QString& kind) {
        if (!enabled() || !capture || !object) {return;}QMutexLocker guard(&_mutex);
        const auto owner=_byPointer.value(capture.get());
        if (!_complete || owner.isEmpty() || _captures.value(owner).weak.lock()!=capture || _resources.size()>=256) {_complete=false;return;}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _resources[id]={object,{{"instance",id},{"capture",owner},{"kind",kind},{"bornEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"destroyedEpochMs",QVariant()}}};
        QObject::connect(object,&QObject::destroyed,[this,id] {
            QMutexLocker lock(&_mutex);_resources[id].original["destroyedEpochMs"]=QDateTime::currentMSecsSinceEpoch();
        });
    }
    QVariantMap read(const QString& nonce,const QString& run,const std::function<QVariantMap()>& activity) {
        return _bracket.read("iosSnapshotCapturesVersion","native-main-snapshot-captures",nonce,run,[&]() -> QVariantMap {
            const auto active=activity();if (active.isEmpty()) {return {};}
            QMutexLocker guard(&_mutex);QVariantList captures,resources;
            for (const auto& entry:_captures) {
                auto row=entry.original;
                {const auto held=entry.weak.lock();row["alive"]=bool(held);
                    if (held) {row["state"]=static_cast<int>(held->state.load());row["announced"]=held->announced.load();}
                    else {row["state"]=QVariant();row["announced"]=QVariant();}
                }
                captures.append(row);
            }
            for (const auto& entry:_resources) {auto row=entry.original;row["alive"]=bool(entry.weak);resources.append(row);}
            return {{"complete",_complete},{"captures",captures},{"resources",resources},{"events",_events},{"activity",active}};
        });
    }
private:
    static bool enabled() {return QCoreApplication::arguments().contains("--testScript");}
    static QString request(const QString& value) {
        return QRegularExpression("\\Asnap_[0-9]{1,16}_[0-9]{1,10}\\z").match(value).hasMatch()?value:QString();
    }
    void append(const QString& id,const QString& kind,const QVariantMap& detail={}) {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (!_complete || _events.size()>=1024 || epoch<_epoch) {_complete=false;return;}_epoch=epoch;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"capture",id},{"kind",kind},{"capturedEpochMs",epoch},{"detail",detail}});
    }
    struct Capture {std::weak_ptr<SnapshotCaptureRequest> weak;QVariantMap original;};
    struct Resource {QPointer<QObject> weak;QVariantMap original;};
    NativeReadBracket _bracket;QMutex _mutex;bool _complete{true};qint64 _epoch{0};
    QMap<QString,Capture> _captures;QHash<const SnapshotCaptureRequest*,QString> _byPointer;
    QMap<QString,Resource> _resources;QVariantList _events;
};
}
#endif
