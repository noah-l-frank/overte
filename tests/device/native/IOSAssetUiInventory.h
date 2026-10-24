// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "IOSAssetControls.h"
#include <QDateTime>
#include <QPointer>
#include <QSet>
#include <QVector>
#include <functional>

namespace overte::e2e {
// Observation retains weak identity after detachment and destruction. It does
// not own the UI or claim that a finished callback's captures have expired.
class IOSAssetUiInventory {
public:
    static IOSAssetUiInventory& shared() {static IOSAssetUiInventory value;return value;}
    QJsonObject read(const QList<QQuickItem*>& roots) {
        if (!asset_ui::enabled() || roots.isEmpty()) {return {};}
        bool complete=true;QSet<QQuickItem*> seen;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || seen.contains(item) || !complete) {return;}
            if (depth>128 || seen.size()>=8192 || item->thread()!=QThread::currentThread()) {complete=false;return;}
            seen.insert(item);visit(item);for (auto child:item->childItems()) {walk(child,depth+1);}
        };
        for (auto root:roots) {
            if (!root || !root->window()) {complete=false;continue;}
            walk(root->window()->contentItem(),0);
        }
        const auto retainedRoots=retained();for (auto root:retainedRoots) {walk(root,0);}
        return observation(complete);
    }
    void visit(QQuickItem* item) {
        if (!asset_ui::enabled()) {return;}
        const bool file=asset_ui::picker(item)==item,body=asset_ui::page(item)==item;
        if (!file && !body) {return;}
        const auto id=asset_ui::identity(item);
        for (const auto& row:_rows) {if (row.id==id) {return;}}
        if (_rows.size()>=128) {_complete=false;return;}
        _rows.append({item,id,file ? "picker" : "page",asset_ui::component(item,file ? "/dialogs/NativeFileBrowser.qml" : "/hifi/dialogs/TabletAssetServer.qml"),
            asset_ui::identity(asset_ui::page(item)),QDateTime::currentMSecsSinceEpoch()});
    }
    QList<QQuickItem*> retained() const {
        QList<QQuickItem*> result;for (const auto& row:_rows) {if (row.item) {result.append(row.item);}}return result;
    }
    QJsonObject observation(bool complete) {
        if (!asset_ui::enabled()) {return {};}
        QJsonArray rows;
        for (const auto& row:_rows) {
            QJsonObject value{{"rootId",row.id},{"role",row.role},{"componentSource",row.source},{"ownerRootId",row.owner},
                {"firstObservedEpochMs",static_cast<double>(row.observed)},{"alive",!row.item.isNull()}};
            if (row.item) {
                auto item=row.item.data();auto window=item->window();
                value["windowId"]=window ? QJsonValue(asset_ui::identity(window)) : QJsonValue(QJsonValue::Null);
                value["visible"]=item->isVisible();
                if (row.role=="picker") {
                    const auto chosen=property(item,"chosen"),closing=property(item,"closing"),request=property(item,"requestId"),error=property(item,"error");
                    if (chosen.userType()!=QMetaType::QVariantList || closing.userType()!=QMetaType::Bool
                            || request.userType()!=QMetaType::QString || error.userType()!=QMetaType::QString
                            || chosen.toList().size()>32 || !property(item,"dir").canConvert<QUrl>()) {_complete=false;}
                    value["directory"]=item->property("dir").toUrl().toString();
                    value["chosen"]=QJsonArray::fromVariantList(chosen.toList());
                    value["closing"]=closing.toBool();
                    value["requestId"]=request.toString();value["error"]=error.toString();
                    const auto bundle=property(item,"bundle");
                    value["bundleReview"]=!bundle.isNull() && bundle.isValid();
                } else {
                    if (property(item,"busy").userType()!=QMetaType::Bool || property(item,"bundleRequest").userType()!=QMetaType::QString
                            || property(item,"assetWriteAllowed").userType()!=QMetaType::Bool) {_complete=false;}
                    value["busy"]=item->property("busy").toBool();value["bundleRequest"]=item->property("bundleRequest").toString();
                    value["status"]=item->property("status").toString();value["canWrite"]=item->property("assetWriteAllowed").toBool();
                    value["selectedPath"]=item->property("selectedPath").toString();value["selectedUrl"]=item->property("selectedUrl").toString();
                    const auto pending=property(item,"pendingBundle");
                    value["pendingBundle"]=!pending.isNull() && pending.isValid();
                    const auto dialog=item->findChildren<QObject*>("bundleDestinationDialog");
                    if (dialog.size()!=1 || dialog.first()->property("visible").userType()!=QMetaType::Bool) {_complete=false;}
                    value["destinationOpen"]=dialog.size()==1 && dialog.first()->property("visible").toBool();
                    auto raw=item->property("assetProxyModel");
                    auto model=raw.userType()==qMetaTypeId<QJSValue>() ? raw.value<QJSValue>().toQObject() : raw.value<QObject*>();
                    if (!model || model->thread()!=QThread::currentThread()) {_complete=false;}
                    value["modelId"]=model ? QJsonValue(asset_ui::identity(model)) : QJsonValue(QJsonValue::Null);
                    value["modelRevision"]=item->property("updatesCount").toInt();
                }
            }
            rows.append(value);
        }
        return {{"iosAssetUiInventoryVersion",1},{"available",true},{"complete",complete && _complete},
            {"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"roots",rows}};
    }
private:
    static QVariant property(QObject* object,const char* name) {
        const auto value=object->property(name);
        return value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toVariant() : value;
    }
    struct Row {QPointer<QQuickItem> item;QString id,role,source,owner;qint64 observed;};
    QVector<Row> _rows;bool _complete {true};quint64 _sequence {0};
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces);
};
} // namespace overte::e2e
#endif
