// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <EntityItem.h>
#include <RenderableModelEntityItem.h>
#include <Model.h>
#include <QCoreApplication>
#include <QDateTime>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <QMap>
#include <QList>
#include <memory>

namespace overte::e2e {
// Weak references observe real destruction without keeping product resources
// alive. No requested UUID, remove/reset operation or ownership hint is input.
class IOSCreateLifetimes {
public:
    static IOSCreateLifetimes& instance() { static IOSCreateLifetimes ledger;return ledger; }
    void observe(const EntityItemPointer& entity) {
        if (!main() || !entity || !_complete) { return; }
        const auto id=entity->getID().toString(QUuid::WithoutBraces);
        if (!_entities.contains(id)) {
            if (_entities.size()>=512) { _complete=false;return; }
            Item row;row.entity=entity;row.born=QDateTime::currentMSecsSinceEpoch();_entities.insert(id,row);
        }
        auto& row=_entities[id];
        if (row.entity.expired() || row.entity.lock()!=entity) { _complete=false;return; }
        if (auto wrapper=std::dynamic_pointer_cast<ModelEntityWrapper>(entity)) {
            const auto model=wrapper->featureCreateModel();if (!model) { return; }
            for (const auto& observed:row.models) { if (observed.model.lock()==model) { return; } }
            if (row.models.size()>=16) { _complete=false;return; }
            ModelLife life;life.model=model;life.born=QDateTime::currentMSecsSinceEpoch();
            life.instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');row.models.append(life);
        }
    }
    QVariantMap snapshot() {
        if (!main()) { return {}; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();QVariantList entries;
        for (auto it=_entities.begin();it!=_entities.end();++it) {
            auto& row=it.value();const bool destroyed=row.entity.expired();
            if (destroyed && row.destroyed==0) { row.destroyed=epoch; }
            QVariantList models;
            for (auto& life:row.models) {
                const bool gone=life.model.expired();if (gone && life.destroyed==0) { life.destroyed=epoch; }
                models.append(QVariantMap{{"instance",life.instance},{"bornEpochMs",life.born},
                    {"destroyed",gone},{"destructionObservedEpochMs",life.destroyed}});
            }
            entries.append(QVariantMap{{"id",it.key()},{"bornEpochMs",row.born},{"destroyed",destroyed},
                {"destructionObservedEpochMs",row.destroyed},{"models",models}});
        }
        return {{"createLifetimesVersion",1},{"complete",_complete},{"entities",entries}};
    }
private:
    bool main() const { auto app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread()
        && QCoreApplication::arguments().contains("--testScript"); }
    struct ModelLife { std::weak_ptr<Model> model;QString instance;qint64 born {0},destroyed {0}; };
    struct Item { std::weak_ptr<EntityItem> entity;qint64 born {0},destroyed {0};QList<ModelLife> models; };
    bool _complete {true};QMap<QString,Item> _entities;
};
} // namespace overte::e2e
#endif
