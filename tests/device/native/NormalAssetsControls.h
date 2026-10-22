// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
inline bool assetsComponent(QObject* object,const QString& suffix,const QString& id="root") {
    const auto contextOwns=[&](QQmlContext* initial) {
        int depth=0;
        for (auto context=initial;context && ++depth<=128;context=context->parentContext()) {
            const auto source=context->baseUrl();
            if (context->nameForObject(object)==id && (source.scheme()=="file" || source.scheme()=="qrc")
                    && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                    && source.path().endsWith(suffix)) { return true; }
        }
        return false;
    };
    if (contextOwns(qmlContext(object))) { return true; }
    // An instantiated composite root can expose its outer creation context.
    // Its actual immediate children retain the inner component context. That
    // context must still name THIS exact object as the component's original ID.
    if (auto item=qobject_cast<QQuickItem*>(object)) {
        int visited=0;
        for (auto child:item->childItems()) {
            if (++visited>64) { return false; }
            if (contextOwns(qmlContext(child))) { return true; }
        }
    }
    return false;
}

inline QQuickItem* assetsPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth=0;
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        auto root=qobject_cast<QQuickItem*>(createVariant(context->contextProperty("root")).value<QObject*>());
        if (root && root->objectName()=="AssetServer" && assetsComponent(root,"/hifi/dialogs/TabletAssetServer.qml")
                && root->property("assetWriteAllowed").userType()==QMetaType::Bool
                && root->property("busy").userType()==QMetaType::Bool) { return root; }
    }
    return nullptr;
}
inline QQuickItem* assetsBrowser(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth=0;
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (parent->objectName()=="nativeFileBrowser" && assetsComponent(parent,"/dialogs/NativeFileBrowser.qml")
                && parent->property("caption").toString()=="Select an asset and its companion files"
                && parent->property("bundleMode").toBool() && parent->property("multiSelect").toBool()
                && !parent->property("saveDialog").toBool() && !parent->property("selectDirectory").toBool()
                && parent->property("primaryFilter").toString().isEmpty()) { return parent; }
    }
    return nullptr;
}
inline QObject* assetsDialog(QQuickItem* item,QString* name=nullptr) {
    if (!assetsPage(item)) { return nullptr; }
    for (auto context=qmlContext(item);context;context=context->parentContext()) {
        for (const auto& id:QStringList{"renameDialog","deleteDialog","bundleDialog","modelDialog"}) {
            auto dialog=createVariant(context->contextProperty(id)).value<QObject*>();
            if (!dialog || !assetsComponent(dialog,"/hifi/dialogs/TabletAssetServer.qml",id) || !dialog->property("visible").toBool()) { continue; }
            auto content=qobject_cast<QQuickItem*>(createVariant(dialog->property("contentItem")).value<QObject*>());
            auto footer=qobject_cast<QQuickItem*>(createVariant(dialog->property("footer")).value<QObject*>());
            for (auto node=item;node;node=node->parentItem()) {
                if (node==content || node==footer) { if (name) { *name=id; }return dialog; }
            }
        }
    }
    return nullptr;
}
inline QQuickItem* assetsClosingWindow(QQuickItem* item) {
    if (!audioGuiItem(item) || !assetsComponent(item,"/windows/DefaultFrameDecoration.qml","closeClickArea")) { return nullptr; }
    for (auto node=item;node;node=node->parentItem()) {
        if (node->objectName()=="AssetServer" && assetsComponent(node,"/hifi/AssetServer.qml")
                && node->property("shown").userType()==QMetaType::Bool && node->property("title").toString()=="Asset Browser") { return node; }
    }
    return nullptr;
}
inline QQuickItem* assetsTree(QQuickItem* item) {
    if (!assetsPage(item)) { return nullptr; }
    for (auto node=item;node;node=node->parentItem()) {
        if (node->objectName()=="assetTree" && assetsComponent(node,"/hifi/dialogs/NativeModelTree.qml")
                && node->property("pathRole").toInt()==256 && node->property("folderRole").toInt()==257
                && node->property("statusRole").toInt()==261) { return node; }
    }
    return nullptr;
}
inline QVariantMap assetsTreeRow(QQuickItem* item) {
    if (!assetsTree(item) || !QRegularExpression("\\AnativeTreeRow(0|[1-9][0-9]{0,3})\\z").match(item->objectName()).hasMatch()) { return {}; }
    auto context=qmlContext(item);const auto data=context ? createVariant(context->contextProperty("modelData")).toMap() : QVariantMap();
    if (data.value("path").userType()!=QMetaType::QString || data.value("folder").userType()!=QMetaType::Bool
            || data.value("status").userType()!=QMetaType::QString || data.value("name").userType()!=QMetaType::QString) { return {}; }
    return {{"path",data.value("path")},{"folder",data.value("folder")},{"status",data.value("status")},{"name",data.value("name")}};
}
inline QString assetsControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    const auto name=item->objectName();
    if (assetsClosingWindow(item)) { return "assets.close"; }
    if (auto browser=assetsBrowser(item)) {
        if ((name=="fileNameInput" || name=="fileFolderPath") && item->inherits("QQuickTextInput")) { return name=="fileNameInput" ? "assets-file.name" : "assets-file.folder"; }
        if (name=="fileList" && item->inherits("QQuickListView")) { return "assets-file.list"; }
        if (name=="bundlePrimary" && item->inherits("QQuickComboBox")) { return "assets-file.primary"; }
        if (item->metaObject()->indexOfSignal("clicked()")>=0) {
            const QHash<QString,QString> names{{"fileAccept","accept"},{"fileCancel","cancel"},
                {"bundleConfirm","confirm"},{"bundleBack","back"},{"bundleCancel","review-cancel"}};
            if (names.contains(name)) { return "assets-file."+names.value(name); }
            const auto row=QRegularExpression("\\AfileRow(0|[1-9][0-9]{0,3})\\z").match(name);
            if (row.hasMatch()) { return "assets-file.row."+row.captured(1); }
        }
        return {};
    }
    const auto page=assetsPage(item);
    if (!page) { const auto nav=scriptControlId(item);return nav=="tablet.home" ? nav : QString(); }
    if (page==item) { return "assets.page"; }
    QString dialog;
    if (auto popup=assetsDialog(item,&dialog)) {
        const QHash<QString,QString> fields{{"assetRenamePath","assets.rename.path"},{"assetBundleDestination","assets.destination.path"},
            {"assetModelUrl","assets.model.url"}};
        if (fields.contains(name) && item->inherits("QQuickTextInput")) { return fields.value(name); }
        if (item->metaObject()->indexOfSignal("clicked()")>=0) {
            // Resolve the actual DialogButtonBox role, rather than translated
            // text or a similarly named button in an unrelated popup.
            const auto role=QQmlProperty(item,"DialogButtonBox.buttonRole",qmlContext(item)).read();
            if ((role.userType()==QMetaType::Int ||
#if QT_VERSION >= QT_VERSION_CHECK(6,0,0)
                    role.metaType().flags().testFlag(QMetaType::IsEnumeration)
#else
                    QMetaType::typeFlags(role.userType()).testFlag(QMetaType::IsEnumeration)
#endif
                    ) && (role.toInt()==0 || role.toInt()==1 || role.toInt()==5 || role.toInt()==6)) {
                const QString prefix=dialog=="renameDialog" ? "rename" : dialog=="deleteDialog" ? "delete" : dialog=="bundleDialog" ? "destination" : "model";
                return "assets."+prefix+((role.toInt()==0 || role.toInt()==5) ? ".accept" : ".cancel");
            }
        }
        return {};
    }
    if (name=="assetFilter" && item->inherits("QQuickTextInput")) { return "assets.filter"; }
    if (name=="assetTree" && assetsTree(item)==item) { return "assets.tree"; }
    if (!assetsTreeRow(item).isEmpty()) { return "assets.row."+name.mid(QStringLiteral("nativeTreeRow").size()); }
    const QHash<QString,QString> buttons{{"assetRefresh","assets.refresh"},{"assetImport","assets.import"},
        {"assetUpload","assets.upload"},{"assetRename","assets.rename"},{"assetDelete","assets.delete"},{"assetBaking","assets.baking"}};
    return buttons.contains(name) && item->metaObject()->indexOfSignal("clicked()")>=0 ? buttons.value(name) : QString();
}
inline bool assetsField(const QString& id) {
    return id=="assets.filter" || id=="assets.rename.path" || id=="assets.destination.path" || id=="assets.model.url" || id=="assets-file.name" || id=="assets-file.folder";
}
inline bool assetsChoice(const QString& id) { return id=="assets-file.primary"; }
inline QJsonObject assetsPickerOriginal(QQuickItem* root) {
    const auto bundle=createVariant(root->property("bundle")).toMap();
    QJsonArray chosen,urls;
    for (const auto& url:createVariant(root->property("chosen")).toList()) { chosen.append(url.toString()); }
    for (const auto& url:bundle.value("urls").toList()) { urls.append(url.toUrl().toString()); }
    return {{"caption",root->property("caption").toString()},{"directory",root->property("dir").toUrl().toString()},
        {"error",root->property("error").toString()},{"closing",root->property("closing").toBool()},
        {"pendingDocuments",!root->property("requestId").toString().isEmpty()},
        {"selectedUrls",chosen},{"review",!bundle.isEmpty()},{"bundleRoot",bundle.value("root").toUrl().toString()},
        {"bundleUrls",urls},{"relativePaths",QJsonArray::fromVariantList(bundle.value("relativePaths").toList())}};
}
inline QJsonObject assetsPageOriginal(QQuickItem* page) {
    for (const auto& name:QStringList{"assetWriteAllowed","importAllowed","busy"}) {
        if (page->property(name.toUtf8()).userType()!=QMetaType::Bool) { return {}; }
    }
    for (const auto& name:QStringList{"status","selectedPath","selectedUrl","uploadedPrimaryUrl","bundleRequest"}) {
        if (page->property(name.toUtf8()).userType()!=QMetaType::QString) { return {}; }
    }
    auto tree=page->findChild<QQuickItem*>("assetTree");
    if (!tree || assetsTree(tree)!=tree) { return {}; }
    const auto rows=createVariant(tree->property("rows")).toList();
    const auto current=tree->property("currentRow");
    if (current.userType()!=QMetaType::Int || current.toInt()<-1 || current.toInt()>=rows.size() || rows.size()>4096) { return {}; }
    const auto selected=current.toInt()<0 ? QVariantMap() : rows[current.toInt()].toMap();
    QJsonArray selection;
    for (const auto& row:rows) {
        const auto actual=row.toMap();
        if (createVariant(tree->property("selectedKeys")).toList().contains(actual.value("key"))) {
            selection.append(QJsonObject{{"path",actual.value("path").toString()},{"folder",actual.value("folder").toBool()},
                {"status",actual.value("status").toString()}});
        }
    }
    return {{"profile","native-assets-v1"},{"canWrite",page->property("assetWriteAllowed").toBool()},
        {"canImport",page->property("importAllowed").toBool()},{"busy",page->property("busy").toBool()},
        {"status",page->property("status").toString()},{"selectedPath",page->property("selectedPath").toString()},
        {"selectedUrl",page->property("selectedUrl").toString()},{"selection",selection},
        {"selectedStatus",selected.value("status").toString()},{"treeRevision",tree->property("revision").toInt()},
        {"uploadedPrimaryUrl",page->property("uploadedPrimaryUrl").toString()},
        {"uploadActive",!page->property("bundleRequest").toString().isEmpty()},
        {"pendingBundle",!createVariant(page->property("pendingBundle")).toMap().isEmpty()}};
}
inline void appendAssetsControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    bool ready=item->isEnabled() && id!="assets.page";
    if (auto page=assetsPage(item)) {
        const auto original=assetsPageOriginal(page);
        if (original.isEmpty()) { row["inputReady"]=false;return; }
        if (id=="assets.page") { for (auto it=original.begin();it!=original.end();++it) { row[it.key()]=it.value(); } }
    }
    if (auto browser=assetsBrowser(item)) {
        row["picker"]=assetsPickerOriginal(browser);
        ready=ready && !browser->property("closing").toBool() && browser->property("requestId").toString().isEmpty();
        if (id.startsWith("assets-file.row.")) {
            auto context=qmlContext(item);const auto url=context->contextProperty("fileUrl").toUrl();
            row["sourceUrl"]=url.toString();row["directory"]=context->contextProperty("fileIsDir").toBool();
            row["selected"]=item->property("highlighted").toBool();ready=ready && url.isLocalFile();
        }
    }
    if (assetsField(id)) { row["text"]=item->property("text").toString();ready=ready && !item->property("readOnly").toBool() && createText(item->property("text").toString()); }
    if (assetsChoice(id)) { row["currentIndex"]=item->property("currentIndex").toInt();row["count"]=item->property("count").toInt();
        row["currentText"]=item->property("currentText").toString();ready=ready && item->property("count").toInt()>0 && item->property("count").toInt()<=32; }
    if (id.startsWith("assets.row.")) { row["mapping"]=QJsonObject::fromVariantMap(assetsTreeRow(item)); }
    if (id=="assets.baking") { row["checked"]=item->property("checked").toBool(); }
    row["inputReady"]=ready;
}
inline QString assetsControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendAssetsControlObservation(row,item,id);
    if (auto page=assetsPage(item)) { row["page"]=assetsPageOriginal(page); }
    if (item && item->window()) { const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));row["x"]=center.x();row["y"]=center.y(); }
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
#endif
} // namespace overte::e2e
