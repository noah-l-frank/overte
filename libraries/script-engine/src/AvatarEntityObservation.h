// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "PlacesHttpObservation.h"
#include <QElapsedTimer>
#include <QMutex>
#include <QMutexLocker>

namespace overte::e2e {
// Only original EntityScriptingInterface returns/deletions, together with the
// native V8 caller context. No entity ID or caller is accepted from a test query.
class AvatarEntityObservation {
public:
    AvatarEntityObservation() { _clock.start(); }
    static AvatarEntityObservation& instance() { static AvatarEntityObservation ledger;return ledger; }
    void event(const QString& kind,const QVariantMap& entity,const QVariantMap& caller) {
        if (!QCoreApplication::arguments().contains("--testScript")) { return; }
        const auto chain=caller.value("callerChain").toStringList();bool relevant {false};
        for (const auto& source:chain) { relevant=relevant || PlacesHttpObservation::installed(source,"/system/avatarapp.js"); }
        if (!relevant || entity.value("hostType")!="avatar") { return; }
        QMutexLocker lock(&_mutex);
        if (!_complete || _events.size()>=256 || chain.isEmpty() || chain.size()>32
                || caller.value("callerVersion")!=1 || !caller.value("manager").toMap().value("assigned").toBool()
                || !caller.value("code").toMap().value("submitted").toBool()
                || !caller.value("avatarCode").toMap().value("complete").toBool()
                || (kind=="add-returned" ? caller.value("method")!="addEntity" :
                    kind!="deleted-local" || caller.value("method")!="deleteEntity")
                || QUuid(entity.value("entityId").toString()).isNull()) { _complete=false;return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_epoch || elapsed<_elapsed) { _complete=false;return; }
        _epoch=epoch;_elapsed=elapsed;
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"eventId",PlacesHttpObservation::nonce()},
            {"kind",kind},{"clock",QVariantMap{{"epochMs",epoch},{"monotonicMs",elapsed}}},
            {"caller",caller},{"entity",entity}});
    }
    QVariantMap snapshot() const {
        QMutexLocker lock(&_mutex);
        return {{"avatarEntitiesLedgerVersion",1},{"instance",_instance},{"complete",_complete},{"events",_events}};
    }
private:
    mutable QMutex _mutex;QElapsedTimer _clock;
    const QString _instance {PlacesHttpObservation::nonce()};QVariantList _events;
    qint64 _epoch {0},_elapsed {0};bool _complete {true};
};
} // namespace overte::e2e
#endif
