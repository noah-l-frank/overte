// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "IOSAssetBundleControls.h"
#include <QAbstractItemModel>
#include <QModelIndex>

namespace overte::e2e::asset_tree_ui {
using asset_bundle_ui::object;
using asset_bundle_ui::property;
constexpr int LIMIT=64;
inline QQuickItem* tree(QQuickItem* page) {
    if (!asset_ui::enabled() || !asset_bundle_ui::canonical(page,"hifi/dialogs/TabletAssetServer.qml")
            || page->property("featureAssetBundleObservation")!=QVariant(true)) {return nullptr;}
    auto item=qobject_cast<QQuickItem*>(object(page,"featureAssetTree"));
    return item && asset_bundle_ui::canonical(item,"hifi/dialogs/NativeModelTree.qml") && item->window()==page->window() ? item : nullptr;
}
inline QAbstractItemModel* model(QQuickItem* page) {
    auto item=tree(page);auto value=qobject_cast<QAbstractItemModel*>(object(page,"assetProxyModel"));
    return item && value && value->thread()==QThread::currentThread() && object(item,"sourceModel")==value ? value : nullptr;
}
inline QJsonArray lineage(QModelIndex index,bool& complete) {
    QList<int> path;int depth=0;
    while (index.isValid()) {
        if (++depth>16 || index.column()!=0 || index.row()<0 || index.row()>=LIMIT) {complete=false;return {};}
        path.prepend(index.row());index=index.parent();
    }
    QJsonArray result;for (auto row:path) {result.append(row);}return result;
}
inline QJsonObject modelRow(QAbstractItemModel* model,const QModelIndex& index,bool& complete) {
    if (!model || !index.isValid() || index.model()!=model || index.column()!=0) {complete=false;return {};}
    const auto name=model->data(index,Qt::DisplayRole),path=model->data(index,Qt::UserRole),folder=model->data(index,Qt::UserRole+1);
    const auto url=model->data(index,Qt::UserRole+3),full=model->data(index,Qt::UserRole+4),status=model->data(index,Qt::UserRole+5),errors=model->data(index,Qt::UserRole+6);
    if (name.userType()!=QMetaType::QString || path.userType()!=QMetaType::QString || folder.userType()!=QMetaType::Bool
            || url.userType()!=QMetaType::QString || full.userType()!=QMetaType::QString || status.userType()!=QMetaType::QString
            || errors.userType()!=QMetaType::QString) {complete=false;return {};}
    return {{"modelIndex",lineage(index,complete)},{"name",name.toString()},{"path",path.toString()},{"folder",folder.toBool()},
        {"url",url.toString()},{"fullPath",full.toString()},{"status",status.toString()},{"bakingErrors",errors.toString()}};
}
inline QJsonObject snapshot(QQuickItem* page,bool& complete) {
    auto root=tree(page);auto original=model(page);if (!root || !original || !page->window()) {complete=false;return {};}
    const auto rows=property(root,"rows"),keys=property(root,"selectedKeys"),expanded=property(root,"expanded"),revision=property(root,"revision");
    const auto selected=property(root,"selectedIndexes"),current=property(root,"currentIndex");
    if (rows.userType()!=QMetaType::QVariantList || keys.userType()!=QMetaType::QVariantList
            || expanded.userType()!=QMetaType::QVariantMap || revision.userType()!=QMetaType::Int
            || selected.userType()!=QMetaType::QVariantList || rows.toList().size()>LIMIT || selected.toList().size()>LIMIT) {complete=false;return {};}
    QJsonArray modelRows,visible,paths;QSet<QString> selectedKeys;
    for (const auto& key:keys.toList()) {if (key.userType()!=QMetaType::QString || selectedKeys.contains(key.toString())) {complete=false;}selectedKeys.insert(key.toString());}
    std::function<void(const QModelIndex&,int)> walk=[&](const QModelIndex& parent,int depth) {
        if (!complete) {return;}if (depth>16 || original->rowCount(parent)>LIMIT) {complete=false;return;}
        for (int row=0;row<original->rowCount(parent);++row) {
            if (modelRows.size()>=LIMIT) {complete=false;return;}const auto index=original->index(row,0,parent);
            modelRows.append(modelRow(original,index,complete));if (original->hasChildren(index)) {walk(index,depth+1);}
        }
    };
    walk(QModelIndex(),0);
    for (const auto& value:selected.toList()) {
        if (!value.canConvert<QModelIndex>()) {complete=false;continue;}const auto index=value.value<QModelIndex>();
        const auto actual=modelRow(original,index,complete);const auto path=actual.value("path").toString();
        if (!selectedKeys.contains(path)) {complete=false;}paths.append(path);
    }
    if (paths.size()!=selectedKeys.size()) {complete=false;}
    const auto actualRows=rows.toList();
    for (int number=0;number<actualRows.size();++number) {
        if (actualRows[number].userType()!=QMetaType::QVariantMap) {complete=false;continue;}const auto row=actualRows[number].toMap();
        if (!row.value("index").canConvert<QModelIndex>()) {complete=false;continue;}
        const auto actual=modelRow(original,row.value("index").value<QModelIndex>(),complete);
        if (row.value("key").toString()!=actual.value("path").toString() || row.value("path").toString()!=actual.value("path").toString()
                || row.value("name").toString()!=actual.value("name").toString() || row.value("folder")!=actual.value("folder").toVariant()
                || row.value("status").toString()!=actual.value("status").toString()) {complete=false;}
        const auto key=actual.value("path").toString();visible.append(QJsonObject{{"index",number},{"model",actual},{"depth",row.value("depth").toInt()},
            {"selected",selectedKeys.contains(key)},{"expanded",actual.value("folder").toBool() && expanded.toMap().value(key).toBool()}});
    }
    QString currentPath,currentUrl;
    if (current.isValid() && !current.isNull()) {
        if (!current.canConvert<QModelIndex>()) {complete=false;}else {
            const auto actual=modelRow(original,current.value<QModelIndex>(),complete);currentPath=actual.value("path").toString();currentUrl=actual.value("url").toString();
        }
    }
    auto rename=object(page,"featureAssetRenameDialog");auto editor=object(page,"featureAssetRenameEditor");auto remove=object(page,"featureAssetDeleteDialog");
    if (!rename || !editor || !remove || property(rename,"visible").userType()!=QMetaType::Bool || property(remove,"visible").userType()!=QMetaType::Bool
            || property(editor,"text").userType()!=QMetaType::QString || page->property("assetWriteAllowed").userType()!=QMetaType::Bool
            || page->property("busy").userType()!=QMetaType::Bool) {complete=false;}
    return {{"rootId",asset_ui::identity(page)},{"windowId",asset_ui::identity(page->window())},{"treeId",asset_ui::identity(root)},
        {"modelId",asset_ui::identity(original)},{"componentSource",qmlContext(page)->baseUrl().toString()},{"treeRevision",revision.toInt()},
        {"filterText",property(root,"filterText").toString()},{"selectedPaths",paths},{"currentPath",currentPath},{"currentUrl",currentUrl},
        {"modelRows",modelRows},{"rows",visible},{"renameId",asset_ui::identity(rename)},{"renameVisible",property(rename,"visible").toBool()},
        {"renameText",property(editor,"text").toString()},{"deleteId",asset_ui::identity(remove)},{"deleteVisible",property(remove,"visible").toBool()},
        {"canWrite",page->property("assetWriteAllowed").toBool()},{"busy",page->property("busy").toBool()}};
}
inline QQuickItem* owner(QQuickItem* item) {
    if (!asset_ui::enabled() || !item || !item->window()) {return nullptr;}
    if (auto page=asset_ui::page(item)) {return tree(page) ? page : nullptr;}
    QQuickItem* found=nullptr;
    for (auto weak:asset_bundle_ui::pages(item->window())) {
        auto page=weak.data();if (!page || !tree(page)) {continue;}
        for (const auto name:{"featureAssetRenameEditor","featureAssetRenameAccept","featureAssetRenameCancel","featureAssetDeleteAccept","featureAssetDeleteCancel"}) {
            if (object(page,name)!=item) {continue;}if (found && found!=page) {return nullptr;}found=page;
        }
    }
    return found;
}
inline QString control(QQuickItem* item) {
    auto page=owner(item);if (!page || !item) {return {};}
    const auto name=item->objectName();
    const auto match=QRegularExpression("\\AnativeTreeRow(0|[1-9][0-9]?)\\z").match(name);
    if (match.hasMatch() && item->inherits("QQuickMouseArea") && asset_bundle_ui::canonical(tree(page),"hifi/dialogs/NativeModelTree.qml")) {
        bool child=false;for (auto parent=item;parent;parent=parent->parentItem()) {if (parent==tree(page)) {child=true;break;}}
        const auto context=qmlContext(item);if (child && context && context->baseUrl()==PathUtils::qmlUrl("hifi/dialogs/NativeModelTree.qml")) {return "assets.tree.row."+match.captured(1);}
    }
    if (object(page,"featureAssetRenameEditor")==item && item->inherits("QQuickTextInput") && item->property("readOnly")==QVariant(false)) {return "assets.rename.path";}
    if (item->metaObject()->indexOfSignal("clicked()")<0) {return {};}
    if (object(page,"featureAssetRenameAccept")==item) {return "assets.rename.accept";}
    if (object(page,"featureAssetRenameCancel")==item) {return "assets.rename.cancel";}
    if (object(page,"featureAssetDeleteAccept")==item) {return "assets.delete.accept";}
    if (object(page,"featureAssetDeleteCancel")==item) {return "assets.delete.cancel";}
    if (object(page,"featureAssetRefreshButton")==item) {return "assets.refresh";}
    if (object(page,"featureAssetRenameButton")==item) {return "assets.rename";}
    if (object(page,"featureAssetDeleteButton")==item) {return "assets.delete";}return {};
}
inline QJsonObject metadata(QQuickItem* item) {
    const auto id=control(item);if (id.isEmpty()) {return {};}
    auto page=owner(item);bool complete=true;auto actual=snapshot(page,complete);if (!complete) {return {};}
    QJsonValue row(QJsonValue::Null);
    if (id.startsWith("assets.tree.row.")) {
        const auto number=id.mid(QString("assets.tree.row.").size()).toInt();const auto rows=actual.value("rows").toArray();
        if (number<0 || number>=rows.size() || !qmlContext(item)) {return {};}
        const auto value=qmlContext(item)->contextProperty("modelData");const auto variant=value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toVariant() : value;
        if (variant.userType()!=QMetaType::QVariantMap) {return {};}
        const auto index=variant.toMap().value("index");if (!index.canConvert<QModelIndex>()) {return {};}
        if (modelRow(model(page),index.value<QModelIndex>(),complete)!=rows[number].toObject().value("model").toObject() || !complete) {return {};}
        row=rows[number];
    }
    for (const auto key:{"modelRows","rows","filterText"}) {actual.remove(key);}
    actual["assetControlVersion"]=3;actual["role"]="page";actual["ownerRootId"]=actual.value("rootId");actual["controlId"]=id;actual["row"]=row;
    return actual;
}
inline QPointF point(QQuickItem* item) {
    // The original MouseArea uses its existing left folder affordance to
    // select and expand/collapse. Deliver a normal hit there, never invoke
    // selectRow/toggle or assign model selection from the adapter.
    return QPointF(control(item).startsWith("assets.tree.row.") ? qMin(8.0,item->width()/2) : item->width()/2,item->height()/2);
}
inline QJsonObject inventory(const QList<QQuickItem*>& roots) {
    static const auto instance=QUuid::createUuid().toString(QUuid::WithoutBraces);static quint64 sequence=0;bool complete=asset_ui::enabled();QJsonArray pages;
    for (auto root:roots) {
        if (asset_ui::page(root)!=root) {continue;}bool valid=true;pages.append(snapshot(root,valid));complete=complete && valid;
    }
    return {{"iosAssetsTreeUiVersion",1},{"instance",instance},{"sequence",static_cast<double>(++sequence)},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"available",asset_ui::enabled()},{"complete",complete},{"pages",pages}};
}
}
#endif
