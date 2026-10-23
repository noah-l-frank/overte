// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalAssetsControls.h"
#include <QAbstractItemModel>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QMap>
#include <QPointer>
#include <QUuid>

namespace overte::e2e {
// Only original NativeFileBrowser bundle consumers. A hidden/detached item is
// still alive; QObject death and QQmlContext retention are separate originals.
class AssetsUiInventory {
public:
    QJsonObject observe(QQuickItem* root,QQuickWindow* window) {
        if(!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        if(!_clock.isValid()) {_clock.start();}
        if(_sequence>=9007199254740991ULL) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        bool complete=epoch>0 && epoch>=_epoch && root && window && root->window()==window
            && root->thread()==qApp->thread() && window->thread()==qApp->thread();_epoch=epoch;
        QSet<QQuickItem*> seen;int visited=0;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if(!complete || !item) {return;}
            if(++visited>4096 || depth>128 || seen.contains(item) || item->thread()!=qApp->thread()) {complete=false;return;}
            seen.insert(item);
            if(item->objectName()=="nativeFileBrowser" && item->property("caption").toString()=="Select an asset and its companion files") {
                if(assetsBrowser(item)!=item) {complete=false;return;}
                const auto context=originalContext(item);auto model=createVariant(item->property("model")).value<QObject*>();
                if(!context || !model || context->nameForObject(model)!="files" || !qobject_cast<QAbstractListModel*>(model) || !model->inherits("QQuickFolderListModel")
                        || model->thread()!=qApp->thread()) {complete=false;return;}
                Row* found=nullptr;for(auto it=_rows.begin();it!=_rows.end();++it) {if(it->root==item) {found=&it.value();break;}}
                if(!found) {
                    if(_rows.size()>=16) {complete=false;return;}
                    Row row;row.id=nonce();row.root=item;row.model=model;row.context=context;row.window=window;row.born=epoch;
                    row.modelId=nonce();row.contextId=identity(context);row.windowId=identity(window);
                    if(row.contextId.isEmpty() || row.windowId.isEmpty()) {complete=false;return;}
                    row.source=context->baseUrl().toString(QUrl::FullyEncoded);_rows.insert(row.id,row);found=&_rows[row.id];
                }
                if(found->model!=model || found->context!=context || found->window!=window) {complete=false;return;}
            }
            for(auto child:item->childItems()) {walk(child,depth+1);}
        };
        if(complete) {
            walk(root,0);
            if(root->parentItem()==window->contentItem()) {
                for(auto layer:window->contentItem()->childItems()) {if(layer!=root && layer->inherits("QQuickOverlay")) {walk(layer,0);}}
            }
        }
        QJsonArray rows;
        for(auto it=_rows.begin();it!=_rows.end();++it) {
            auto& row=it.value();bool visible=false,inTree=false;
            if(row.root) {
                if(row.root->thread()!=qApp->thread() || assetsBrowser(row.root)!=row.root
                        || originalContext(row.root)!=row.context || row.root->window()!=row.window
                        || createVariant(row.root->property("model")).value<QObject*>()!=row.model) {complete=false;}
                else {
                    const auto pending=row.root->property("requestId"),closing=row.root->property("closing");
                    if(pending.userType()!=QMetaType::QString || closing.userType()!=QMetaType::Bool || pending.toString().size()>4096) {complete=false;}
                    else {row.pending=!pending.toString().isEmpty();row.closing=closing.toBool();}
                    inTree=seen.contains(row.root);visible=true;int depth=0;
                    for(auto item=row.root.data();item;item=item->parentItem()) {
                        if(++depth>128 || item->thread()!=qApp->thread()) {complete=false;break;}
                        visible=visible && item->isVisible() && item->opacity()>.01;
                    }
                }
            }
            if(row.model && row.model->thread()!=qApp->thread() || row.context && row.context->thread()!=qApp->thread()
                    || row.window && row.window->thread()!=qApp->thread()) {complete=false;}
            rows.append(QJsonObject{{"id",row.id},{"modelId",row.modelId},{"contextId",row.contextId},{"windowId",row.windowId},
                {"componentSource",row.source},{"bornEpochMs",static_cast<double>(row.born)},
                {"rootAlive",!row.root.isNull()},{"modelAlive",!row.model.isNull()},{"contextAlive",!row.context.isNull()},
                {"windowAlive",!row.window.isNull()},{"inCurrentTree",inTree},{"visible",visible},
                {"pendingDocuments",row.pending},{"closing",row.closing}});
        }
        return {{"assetsUiInventoryVersion",1},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"elapsedMs",static_cast<double>(_clock.elapsed())},{"capturedEpochMs",static_cast<double>(epoch)},
            {"complete",complete},{"browsers",complete ? rows : QJsonArray()}};
    }
private:
    static QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QQmlContext* originalContext(QQuickItem* root) {
        const auto find=[&](QQmlContext* initial)->QQmlContext* {
            int depth=0;for(auto context=initial;context && ++depth<=128;context=context->parentContext()) {
                if(context->thread()!=qApp->thread()) {return nullptr;}
                if(context->nameForObject(root)=="root" && context->baseUrl()==PathUtils::qmlUrl("dialogs/NativeFileBrowser.qml")) {return context;}
            }return nullptr;
        };
        if(auto context=find(qmlContext(root))) {return context;}
        int visited=0;for(auto child:root->childItems()) {if(++visited>64) {return nullptr;}if(auto context=find(qmlContext(child))) {return context;}}
        return nullptr;
    }
    QString identity(QObject* object) {
        const auto old=_objects.value(object);if(old.object==object) {return old.id;}
        if(_objects.size()>=128) {return {};}
        const auto id=nonce();_objects.insert(object,{object,id});return id;
    }
    struct Identity {QPointer<QObject> object;QString id;};QHash<QObject*,Identity> _objects;
    struct Row {QString id,modelId,contextId,windowId,source;QPointer<QQuickItem> root;QPointer<QObject> model;
        QPointer<QQmlContext> context;QPointer<QQuickWindow> window;qint64 born{0};bool pending{false},closing{false};};
    QMap<QString,Row> _rows;const QString _instance{nonce()};quint64 _sequence{0};qint64 _epoch{0};QElapsedTimer _clock;
};
inline AssetsUiInventory& assetsUiInventory() {static AssetsUiInventory source;return source;}
}
#endif
