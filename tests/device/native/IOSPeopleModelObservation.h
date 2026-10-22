// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalAvatarControls.h"
#include "NativeReadBracket.h"
#include <QJSValueIterator>
#include <QSet>
#include <algorithm>
#include <functional>

namespace overte::e2e {
// Actual Pal model/prompt/QML callback-key inventory. No handler is invoked,
// no timer is stopped and no backend/receiver state is promoted to QML state.
class IOSPeopleModelObservation {
public:
    QVariantMap read(const QString& request,const QString& run,const QList<QQuickItem*>& inputs,bool shown) {
        return _bracket.read("iosPeopleModelVersion","native-main-people-model",request,run,[&]() -> QVariantMap {
            bool complete=!inputs.isEmpty();QSet<QQuickItem*> visited;
            std::function<void(QQuickItem*,int)> visit=[&](QQuickItem* item,int depth) {
                if (!item || !complete || visited.contains(item)) { return; }
                if (depth>128 || visited.size()>=8192 || item->thread()!=qApp->thread()) { complete=false;return; }
                visited.insert(item);
                if (avatarComponentSource(item).endsWith("/hifi/Pal.qml")) { _roots.insert(item,item); }
                for (auto child:item->childItems()) { visit(child,depth+1); }
            };
            for (auto input:inputs) {
                if (!input || !input->window()) { complete=false;continue; }
                visit(input->window()->contentItem(),0);
            }
            for (auto it=_roots.begin();it!=_roots.end();) {
                if (it.value().isNull()) { it=_roots.erase(it); } else { ++it; }
            }
            if (_roots.size()>32) { complete=false; }
            QVariantList roots;
            for (const auto& pointer:_roots) {
                const auto value=snapshot(pointer.data(),shown);
                if (value.isEmpty()) { complete=false;continue; }roots.append(value);
            }
            std::sort(roots.begin(),roots.end(),[](const QVariant& a,const QVariant& b) {
                return a.toMap().value("rootId").toString()<b.toMap().value("rootId").toString();
            });
            return {{"complete",complete},{"tabletShown",shown},{"roots",roots}};
        });
    }
private:
    static bool rows(QAbstractItemModel* model,QVariantList& result) {
        if (!model || model->thread()!=qApp->thread() || model->rowCount()<0 || model->rowCount()>1000) { return false; }
        const auto roles=model->roleNames();if (roles.size()>64) { return false; }
        for (int index=0;index<model->rowCount();++index) {
            QVariantMap row;
            for (auto role=roles.cbegin();role!=roles.cend();++role) {
                const auto value=createVariant(model->data(model->index(index,0),role.key()));
                if (role.value().isEmpty() || role.value().size()>256 || !value.isValid()) { return false; }
                row.insert(QString::fromUtf8(role.value()),value);
            }
            result.append(row);
        }
        return true;
    }
    static QVariantMap snapshot(QQuickItem* root,bool shown) {
        const auto source=avatarComponentSource(root),id=avatarRootId(root);
        if (!source.endsWith("/hifi/Pal.qml") || id.isEmpty()) { return {}; }
        const auto visible=!NormalControlUi::visibleRect(root,root->window()).isEmpty();
        QVariantMap result {{"rootId",id},{"qmlSource",source},{"windowPresent",root->window()!=nullptr},
            {"visible",visible},{"active",shown && visible}};
        for (const auto& name:QList<QByteArray>{"connectionState","activeTab","myData","ignored","nearbyUserModelData"}) {
            const auto value=createVariant(root->property(name.constData()));
            if (!value.isValid()) { return {}; }result.insert(QString::fromUtf8(name),value);
        }
        QVariantMap timers;
        for (const auto& name:QStringList{"selectionTimer","connectionsTimeoutTimer","connectionsRefreshScrollTimer"}) {
            const auto timer=avatarNamed(root,name);
            if (!timer || timer->property("running").userType()!=QMetaType::Bool) { return {}; }
            timers.insert(name,timer->property("running"));
        }
        result["timers"]=timers;
        QVariantMap panels;
        for (const auto& name:QStringList{"connectionPrompt","letterboxMessage","comboDialog"}) {
            const auto panel=avatarNamed(root,name);
            if (!panel || panel->property("visible").userType()!=QMetaType::Bool) { return {}; }
            panels.insert(name,panel->property("visible"));
        }
        result["panels"]=panels;
        auto nearby=qobject_cast<QAbstractItemModel*>(avatarNamed(root,"nearbyUserModel"));
        auto connections=qobject_cast<QAbstractItemModel*>(avatarNamed(root,"connectionsUserModel"));
        auto table=avatarNamed(root,"connectionsTable");auto http=avatarNamed(root,"http");
        if (!table || !http || createVariant(table->property("model")).value<QObject*>()!=connections) { return {}; }
        QVariantList nearRows,connectionRows;
        if (!rows(nearby,nearRows) || !rows(connections,connectionRows)) { return {}; }
        result["nearbyRows"]=nearRows;result["connectionRows"]=connectionRows;
        QVariantMap pagination;
        for (const auto& name:QList<QByteArray>{"endpoint","initialized","requestPending","additionalFirstPageRequested",
                "delayedClear","retrievedAtLeastOnePage","currentPageToRetrieve","totalPages","totalEntries",
                "itemsPerPage","sortKey","searchFilter"}) {
            const auto value=createVariant(connections->property(name.constData()));
            if (!value.isValid()) { return {}; }pagination.insert(QString::fromUtf8(name),value);
        }
        result["pagination"]=pagination;
        const auto raw=http->property("httpCalls");QStringList callbacks;
        if (raw.userType()!=qMetaTypeId<QJSValue>()) { return {}; }
        const auto calls=raw.value<QJSValue>();if (!calls.isObject() || calls.isArray()) { return {}; }
        QJSValueIterator iterator(calls);
        while (iterator.hasNext()) {
            iterator.next();const auto key=iterator.name();bool number {false};const auto index=key.toULongLong(&number);
            if (!number || QString::number(index)!=key || index>9007199254740991ULL || callbacks.size()>=256) { return {}; }
            callbacks.append(key);
        }
        callbacks.sort();result["httpCallbacks"]=callbacks;
        const auto counter=createVariant(http->property("httpCounter"));
        if (!counter.isValid()) { return {}; }result["httpCounter"]=counter;
        return result;
    }
    NativeReadBracket _bracket;
    QHash<QQuickItem*,QPointer<QQuickItem>> _roots;
};
} // namespace overte::e2e
#endif
