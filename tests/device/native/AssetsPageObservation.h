// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalAssetsControls.h"
#include <QDateTime>
#include <QElapsedTimer>
#include <QPointer>
#include <QUuid>

namespace overte::e2e {
// Page/context ownership is separate from browser/model file consumers. The
// persistent tablet window and loader are borrowed originals, never killed by
// observation or interpreted as owned resources that Home must destroy.
class AssetsPageObservation {
public:
    QJsonObject observe(QQuickItem* root,QQuickWindow* window,bool shown,bool home,const QVariantMap& qmlLoads) {
        if(!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
                || !_valid || !root || !window || root->window()!=window || root->thread()!=qApp->thread()
                || window->thread()!=qApp->thread() || qmlLoads.isEmpty() || _sequence>=9007199254740991ULL) {return {};}
        if(!_clock.isValid()) {_clock.start();}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();if(epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        QSet<QQuickItem*> visited;int visiblePages=0;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if(!item || !_valid) {return;}
            if(depth>128 || visited.size()>=4096 || visited.contains(item) || item->thread()!=qApp->thread()) {_valid=false;return;}
            visited.insert(item);
            if(item->objectName()=="AssetServer") {
                auto context=pageContext(item);auto loader=pageLoader(item,root);
                if(!context || !loader || assetsPage(item)!=item) {_valid=false;return;}
                Row* found=nullptr;for(auto& row:_rows) {if(row.page==item) {found=&row;break;}}
                if(!found) {
                    if(_rows.size()>=64) {_valid=false;return;}
                    Row row;row.id=nonce();row.page=item;row.context=context;row.window=window;row.loader=loader;row.first=epoch;
                    row.pageId=identity(item);row.contextId=identity(context);row.windowId=identity(window);row.loaderId=identity(loader);
                    row.source=context->baseUrl().toString(QUrl::FullyEncoded);
                    if(row.pageId.isEmpty() || row.contextId.isEmpty() || row.windowId.isEmpty() || row.loaderId.isEmpty()) {_valid=false;return;}
                    _rows.append(row);found=&_rows.last();
                }
                if(found->context!=context || found->window!=window || found->loader!=loader) {_valid=false;return;}
                if(shown && visible(item)) {++visiblePages;}
            }
            for(auto child:item->childItems()) {walk(child,depth+1);}
        };
        walk(root,0);if(!_valid || visiblePages>1 || (home && visiblePages)) {return {};}
        QJsonArray rows;
        for(auto& row:_rows) {
            if(row.page && row.page->thread()!=qApp->thread() || row.context && row.context->thread()!=qApp->thread()
                    || row.loader && row.loader->thread()!=qApp->thread() || row.window && row.window->thread()!=qApp->thread()) {_valid=false;return {};}
            const bool pageAlive=!row.page.isNull(),contextAlive=!row.context.isNull();
            rows.append(QJsonObject{{"id",row.id},{"pageId",row.pageId},{"contextId",row.contextId},{"windowId",row.windowId},
                {"loaderId",row.loaderId},{"componentSource",row.source},{"firstObservedEpochMs",static_cast<double>(row.first)},
                {"pageAlive",pageAlive},{"contextAlive",contextAlive},{"contextValid",contextAlive && row.context->isValid()},
                {"windowAlive",!row.window.isNull()},{"loaderAlive",!row.loader.isNull()},
                {"inCurrentTree",pageAlive && visited.contains(row.page)},{"visible",pageAlive && visible(row.page)}});
        }
        return {{"schemaVersion",1},{"instance",_instance},{"generation",_instance},{"sourceSequence",static_cast<double>(++_sequence)},
            {"lastCommandSequence",0},{"elapsedMs",static_cast<double>(_clock.elapsed())},{"capturedEpochMs",static_cast<double>(epoch)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"assetsPagesVersion",1},
            {"source",QJsonObject{{"complete",true},{"tabletShown",shown},{"onHomeScreen",home},{"pages",rows},
                {"qmlLoads",QJsonObject::fromVariantMap(qmlLoads)}}}};
    }
private:
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QQmlContext* pageContext(QQuickItem* page) {
        const auto find=[&](QQmlContext* start)->QQmlContext* {
            int depth=0;for(auto context=start;context && ++depth<=128;context=context->parentContext()) {
                if(context->thread()!=qApp->thread()) {return nullptr;}
                if(context->nameForObject(page)=="root" && context->baseUrl()==PathUtils::qmlUrl("hifi/dialogs/TabletAssetServer.qml")) {return context;}
            }return nullptr;
        };
        if(auto context=find(qmlContext(page))) {return context;}
        int count=0;for(auto child:page->childItems()) {if(++count>64) {return nullptr;}if(auto context=find(qmlContext(child))) {return context;}}
        return nullptr;
    }
    static QQuickItem* pageLoader(QQuickItem* page,QQuickItem* root) {
        int depth=0;for(auto item=page->parentItem();item && ++depth<=128;item=item->parentItem()) {
            if(item->objectName()=="loader" && (assetsComponent(item,"/hifi/tablet/TabletRoot.qml","loader")
                    || assetsComponent(item,"/hifi/tablet/TabletPageLoader.qml","loader"))) {return item;}
            if(item==root) {break;}
        }return nullptr;
    }
    static bool visible(QQuickItem* page) {
        int depth=0;for(auto item=page;item;item=item->parentItem()) {
            if(++depth>128 || !item->isVisible() || !std::isfinite(item->opacity()) || item->opacity()<=.01) {return false;}
        }return true;
    }
    QString identity(QObject* object) {
        const auto previous=_objects.value(object);if(previous.object==object) {return previous.id;}
        if(_objects.size()>=256) {return {};}
        const auto id=nonce();_objects.insert(object,{object,id});return id;
    }
    struct Object {QPointer<QObject> object;QString id;};QHash<QObject*,Object> _objects;
    struct Row {QString id,pageId,contextId,windowId,loaderId,source;QPointer<QQuickItem> page,loader;
        QPointer<QQmlContext> context;QPointer<QQuickWindow> window;qint64 first{0};};
    QList<Row> _rows;QString _instance{nonce()};QElapsedTimer _clock;quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
};
}
#endif
