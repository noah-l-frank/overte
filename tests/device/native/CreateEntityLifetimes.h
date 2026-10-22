// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QHash>
#include <QRegularExpression>
#include <QPointer>
#include <EntityItem.h>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <memory>
namespace overte::e2e {
// Original Tree objects only. Never holds a strong entity/renderer reference,
// removes an entity, or substitutes tree absence/shared-holder expiry for
// actual QObject death (the original Model factory uses deleteLater()).
class CreateEntityLifetimes {
public:
    QVariantMap observe(const QString& run,const QUuid& id,const std::shared_ptr<EntityItem>& actual) {
        if (!_valid || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || id.isNull()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        if (!_runs.contains(run)) {if (!actual || _runs.size()>=4) {return {};}_runs.insert(run,{});}
        auto& records=_runs[run];
        if (!records.contains(id)) {
            if (!actual || records.size()>=32) {return {};}
            records.insert(id,{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),epoch,actual,actual.get()});
        }
        const auto& original=records[id];
        if (actual) {
            const auto first=original.object.lock();
            if (!first || first.get()!=actual.get() || original.guard.data()!=actual.get()) {return {};}
        }
        return {{"id",id.toString(QUuid::WithoutBraces)},{"instance",original.instance},
            {"firstObservedEpochMs",original.created},{"alive",!original.object.expired() || !original.guard.isNull()},{"inTree",bool(actual)}};
    }
private:
    struct Original {QString instance;qint64 created;std::weak_ptr<EntityItem> object;QPointer<EntityItem> guard;};
    QHash<QString,QHash<QUuid,Original>> _runs;bool _valid {true};qint64 _epoch {0};
};
} // namespace overte::e2e
#endif
