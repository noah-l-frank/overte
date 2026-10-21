// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QHash>
#include <QPointer>
#include <QQmlComponent>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <algorithm>

namespace hifi::qml {
// Passive weak ownership of the real component and its original deferred
// statusChanged continuation. No cancellation, URL substitution or extra load.
class FeatureQmlLoads {
public:
    void begin(QQmlComponent* component,QObject* parent) {
        if (!enabled() || !component) { return; }
        prune();
        if (_known.size()>=128 || _retired.size()>=1024 || _known.contains(component)) { _complete=false;return; }
        _known.insert(component,{component,parent,QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),
            QString::fromLatin1(QCryptographicHash::hash(component->url().toEncoded(),QCryptographicHash::Sha256).toHex()),
            QStringLiteral("constructing"),false});
    }

    void waiting(QQmlComponent* component) {
        if (!enabled()) { return; }
        auto found=_known.find(component);
        if (found==_known.end()) { _complete=false;return; }
        found->phase=QStringLiteral("loading");found->pending=true;
    }

    class Finishing {
    public:
        Finishing(FeatureQmlLoads& owner,QQmlComponent* component) : _owner(owner),_component(component) {
            _owner.phase(_component,QStringLiteral("finishing"));
        }
        ~Finishing() { _owner.phase(_component,QStringLiteral("finished")); }
        Finishing(const Finishing&)=delete;
        Finishing& operator=(const Finishing&)=delete;
    private:
        FeatureQmlLoads& _owner;
        QQmlComponent* _component;
    };

    QVariantMap snapshot() {
        if (!enabled()) { return {}; }
        prune();
        QVariantList live,retired;
        auto keys=_retired.values();std::sort(keys.begin(),keys.end());
        for (const auto& key:keys) { retired.append(key); }
        auto rows=_known.values();
        std::sort(rows.begin(),rows.end(),[](const Row& a,const Row& b) { return a.id<b.id; });
        for (const auto& row:rows) {
            if (!row.component || row.component->thread()!=QThread::currentThread()) { _complete=false;break; }
            live.append(QVariantMap{{"id",row.id},{"sourceSha256",row.source},{"phase",row.phase},
                {"loading",row.component->isLoading()},{"callbackPending",row.pending},{"parentPresent",!row.parent.isNull()}});
        }
        return {{"qmlLoadInventoryVersion",1},{"instance",_instance},{"complete",_complete && _retired.size()<=1024},
            {"components",live},{"retiredComponents",retired}};
    }
private:
    struct Row { QPointer<QQmlComponent> component;QPointer<QObject> parent;QString id,source,phase;bool pending; };
    static bool enabled() {
        return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    void phase(QQmlComponent* component,const QString& value) {
        if (!enabled()) { return; }
        auto found=_known.find(component);
        if (found==_known.end()) { _complete=false;return; }
        found->phase=value;found->pending=false;
    }
    void prune() {
        for (auto i=_known.begin();i!=_known.end();) {
            if (!i->component) { _retired.insert(i->id);i=_known.erase(i); }
            else { ++i; }
        }
    }
    const QString _instance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
    bool _complete {true};
    QHash<QQmlComponent*,Row> _known;
    QSet<QString> _retired;
};
}
#endif
