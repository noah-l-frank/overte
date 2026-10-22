// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "NormalPlacesControls.h"
#include "NormalControlUi.h"
#include <QAbstractItemModel>
#include <QJsonArray>
#include <QSet>
#include <algorithm>
#include <functional>

namespace overte::e2e {

// Original materialized models and retained roots, never a reconstructed search
// result, a queued-command ACK or proof of network consumption/arrival.
class IOSPlacesModelObservation {
public:
    IOSPlacesModelObservation() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }

    QVariantMap read(const QString& request,const QString& run,const QList<QQuickItem*>& inputs,bool shown) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || _sequence>=1000000000) { return {}; }
        const auto before=clock();bool complete=!inputs.isEmpty();QSet<QQuickItem*> visited;
        std::function<void(QQuickItem*,int)> visit=[&](QQuickItem* item,int depth) {
            if (!item || !complete || visited.contains(item)) { return; }
            if (depth>128 || visited.size()>=8192 || item->thread()!=qApp->thread()) { complete=false;return; }
            visited.insert(item);
            if (item->property("semanticScreenId").toString()=="places.home") {
                if (placesRootSource(item).isEmpty()) { complete=false;return; }
                _roots.insert(item,item);
            }
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
            auto root=pointer.data();auto original=snapshot(root,shown);
            if (original.isEmpty()) { complete=false;continue; }
            roots.append(original);
        }
        // QHash traversal is not a model order. Stabilize only the root set;
        // original model row order and multiplicity remain unchanged.
        std::sort(roots.begin(),roots.end(),[](const QVariant& a,const QVariant& b) {
            return a.toMap().value("rootId").toString()<b.toMap().value("rootId").toString();
        });
        const auto after=clock();
        QVariantMap result {{"iosPlacesModelVersion",1},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-main-places-model"},{"clockBefore",before},{"clockAfter",after},
            {"complete",complete},{"tabletShown",shown},{"roots",roots}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>262144) { return {}; }
        return result;
    }

private:
    QVariantMap clock() const {
        return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"monotonicMs",static_cast<double>(_clock.elapsed())}};
    }
    static QObject* named(QQuickItem* root,const QString& name) {
        const auto objects=root->findChildren<QObject*>();if (objects.size()>4096) { return nullptr; }
        QObject* result {nullptr};
        for (auto object:objects) {
            int depth {0};bool matches {false};
            for (auto context=qmlContext(object);context && ++depth<=128;context=context->parentContext()) {
                if (context->nameForObject(object)==name) { matches=true;break; }
            }
            if (matches) { if (result && result!=object) { return nullptr; }result=object; }
        }
        return result;
    }
    static bool list(QQuickItem* root,const QString& name,const QList<QByteArray>& expected,QVariantMap& result) {
        auto view=qobject_cast<QQuickItem*>(named(root,name));
        if (!view || !view->inherits("QQuickListView") || placesPage(view)!=root) { return false; }
        auto model=qobject_cast<QAbstractItemModel*>(createVariant(view->property("model")).value<QObject*>());
        if (!model || model->thread()!=qApp->thread() || model->rowCount()<0 || model->rowCount()>1000) { return false; }
        const auto roles=model->roleNames();QVariantList rows;
        for (int index=0;index<model->rowCount();++index) {
            QVariantMap row;
            for (const auto& name:expected) {
                const auto role=roles.key(name,-1);if (role<0) { return false; }
                const auto original=model->data(model->index(index,0),role);
                if (!original.isValid()) { return false; }row.insert(QString::fromUtf8(name),original);
            }
            rows.append(row);
        }
        result={{"visible",!NormalControlUi::visibleRect(view,view->window()).isEmpty()},{"rows",rows}};return true;
    }
    static QVariantMap snapshot(QQuickItem* root,bool shown) {
        if (placesRootSource(root).isEmpty()) { return {}; }
        const auto id=placesRootId(root);if (id.isEmpty()) { return {}; }
        QVariantMap result {{"rootId",id},{"qmlSource",placesRootSource(root)},{"windowPresent",root->window()!=nullptr},
            {"visible",!NormalControlUi::visibleRect(root,root->window()).isEmpty()}};
        result["active"]=shown && result.value("visible").toBool();
        for (const auto& name:QList<QByteArray>{"loading","currentAddress","directoryWarning","records","bookmarkAddresses",
                "maturityFilter","pendingCommands"}) {
            const auto original=createVariant(root->property(name.constData()));
            if (!original.isValid()) { return {}; }result.insert(QString::fromUtf8(name),original);
        }
        auto timer=named(root,"commandInterval"),tabs=named(root,"tabs"),search=named(root,"search"),name=named(root,"bookmarkName");
        auto dialog=placesBookmarkDialog(root);
        if (!timer || !tabs || !search || !name || !dialog || timer->property("running").userType()!=QMetaType::Bool
                || tabs->property("currentIndex").userType()!=QMetaType::Int || search->property("text").userType()!=QMetaType::QString
                || name->property("text").userType()!=QMetaType::QString) { return {}; }
        result["timerRunning"]=timer->property("running");result["tab"]=tabs->property("currentIndex");result["search"]=search->property("text");
        result["dialog"]=QVariantMap {{"visible",dialog->property("visible")},{"originalName",dialog->property("originalName")},
            {"address",dialog->property("address")},{"name",name->property("text")}};
        QVariantMap places,bookmarks,servers;
        if (!list(root,"placesList",{"placeName","placeAddress","placeDescription","attendance","capacity","placeId"},places)
                || !list(root,"bookmarksList",{"bookmarkName","bookmarkAddress"},bookmarks)
                || !list(root,"serversList",{"serverUrl","serverIndex","serverRegion","fetched","pinned","failed"},servers)) { return {}; }
        result["lists"]=QVariantMap {{"places",places},{"bookmarks",bookmarks},{"servers",servers}};return result;
    }
    QString _instance;
    quint64 _sequence {0};
    QElapsedTimer _clock;
    QHash<QQuickItem*,QPointer<QQuickItem>> _roots;
};
} // namespace overte::e2e
#endif
