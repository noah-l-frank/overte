// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NormalAccountMenuControls.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRegularExpression>
#include <QUuid>
#include <functional>

namespace overte::e2e::asset_ui {
inline bool enabled() {
    return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")
        && QThread::currentThread()==QCoreApplication::instance()->thread();
}
inline QString component(QQuickItem* item,const QString& suffix) {
    if (!enabled() || !item || item->thread()!=QThread::currentThread()) {return {};}
    int depth=0;
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto url=context->baseUrl();
        if (context->nameForObject(item)=="root" && (url.scheme()=="file" || url.scheme()=="qrc")
                && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                && url.path().endsWith(suffix)) {return url.toString();}
    }
    return {};
}
inline QQuickItem* page(QQuickItem* item) {
    int depth=0;
    for (auto root=item;root && ++depth<=128;root=root->parentItem()) {
        if (root->objectName()=="AssetServer" && !component(root,"/hifi/dialogs/TabletAssetServer.qml").isEmpty()) {return root;}
    }
    return nullptr;
}
inline QQuickItem* picker(QQuickItem* item) {
    int depth=0;
    for (auto root=item;root && ++depth<=128;root=root->parentItem()) {
        if (root->objectName()!="nativeFileBrowser") {continue;}
        if (component(root,"/dialogs/NativeFileBrowser.qml").isEmpty() || !page(root)
                || root->property("caption")!=QVariant("Select an asset and its companion files")
                || root->property("bundleMode")!=QVariant(true) || root->property("multiSelect")!=QVariant(true)
                || root->property("saveDialog")!=QVariant(false) || root->property("selectDirectory")!=QVariant(false)
                || !root->property("primaryFilter").toString().isEmpty()) {return nullptr;}
        return root;
    }
    return nullptr;
}
inline QString identity(QObject* object) {
    if (!enabled() || !object || object->thread()!=QThread::currentThread()) {return {};}
    auto value=object->property("_overteE2EAssetIdentity").toString();
    if (value.isEmpty()) {
        value=QUuid::createUuid().toString(QUuid::WithoutBraces);
        object->setProperty("_overteE2EAssetIdentity",value);
    }
    return value;
}
inline QString menu(QQuickItem* item) {
    if (!enabled()) {return {};}
    const auto source=accountMenuSource(item);if (!source) {return {};}
    const auto context=qmlContext(item);if (!context) {return {};}
    const auto url=context->baseUrl();
    if ((url.scheme()!="file" && url.scheme()!="qrc") || !url.authority().isEmpty()
            || url.hasQuery() || url.hasFragment() || !url.path().endsWith("/hifi/tablet/TabletMenuItem.qml")) {return {};}
    const auto text=item->property("text").toString();
    if (source->property("type").toInt()==2 && text=="Edit") {return "assets.menu";}
    if (source->property("type").toInt()==1 && text=="Asset Browser") {return "assets.open";}
    return {};
}
inline QQuickItem* navigationPage(QQuickItem* item) {
    if (!enabled() || !item || !item->window() || item->objectName()!="nav.home"
            || item->metaObject()->indexOfSignal("clicked()")<0) {return nullptr;}
    const auto context=qmlContext(item);if (!context) {return nullptr;}
    const auto url=context->baseUrl();
    if ((url.scheme()!="file" && url.scheme()!="qrc") || !url.authority().isEmpty() || url.hasQuery() || url.hasFragment()
            || !url.path().endsWith("/hifi/tablet/TabletNavigation.qml")) {return nullptr;}
    QQuickItem* found=nullptr;int visited=0;bool complete=true;
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* node,int depth) {
        if (!node || !complete) {return;}if (++visited>8192 || depth>128) {complete=false;return;}
        if (page(node)==node && node->isVisible() && node->window()==item->window()) {if (found) {complete=false;return;}found=node;}
        for (auto child:node->childItems()) {walk(child,depth+1);}
    };
    walk(item->window()->contentItem(),0);return complete ? found : nullptr;
}
inline QString control(QQuickItem* item) {
    const auto entry=menu(item);if (!entry.isEmpty()) {return entry;}
    if (navigationPage(item)) {return "assets.home";}
    auto root=picker(item);const auto name=item ? item->objectName() : QString();
    if (root) {
        if (item->inherits("QQuickTextInput") && name=="fileFolderPath" && !item->property("readOnly").toBool()) {return "asset-file.folder";}
        if (item->metaObject()->indexOfSignal("clicked()")<0) {return {};}
        const auto row=QRegularExpression("\\AfileRow(0|[1-9][0-9]{0,3})\\z").match(name);
        if (row.hasMatch()) {return "asset-file.row."+row.captured(1);}
        if (name=="fileAccept") {return "asset-file.select";}
        if (name=="fileCancel" || name=="bundleCancel") {return "asset-file.cancel";}
        return {};
    }
    root=page(item);if (!root || picker(root)) {return {};}
    if (name=="assetUpload" && item->metaObject()->indexOfSignal("clicked()")>=0) {return "assets.upload";}
    return {};
}
inline QJsonObject metadata(QQuickItem* item) {
    const auto id=control(item);if (id.isEmpty()) {return {};}
    const auto entry=menu(item);
    if (!entry.isEmpty()) {
        auto source=accountMenuSource(item);
        return {{"assetControlVersion",1},{"role","menu"},{"rootId",identity(source)},
            {"windowId",identity(item->window())},{"componentSource",qmlContext(item)->baseUrl().toString()},
            {"controlId",id},{"sourceType",source->property("type").toInt()},
            {"labelSha256",QString::fromLatin1(QCryptographicHash::hash(item->property("text").toString().toUtf8(),QCryptographicHash::Sha256).toHex())}};
    }
    auto root=picker(item);if (!root) {root=page(item);}if (!root) {root=navigationPage(item);}
    const bool file=picker(item)!=nullptr;
    QString rowUrl;
    if (id.startsWith("asset-file.row.")) {
        const auto context=qmlContext(item);if (!context) {return {};}
        auto value=context->contextProperty("fileUrl");if (!value.isValid()) {value=context->contextProperty("fileURL");}
        const auto url=value.toUrl();if (!url.isLocalFile() || url.hasQuery() || url.hasFragment()) {return {};}
        rowUrl=url.toString();
    }
    return {{"assetControlVersion",1},{"role",file ? "picker" : "page"},{"rootId",identity(root)},
        {"windowId",identity(item->window())},{"componentSource",component(root,file ? "/dialogs/NativeFileBrowser.qml" : "/hifi/dialogs/TabletAssetServer.qml")},
        {"controlId",id},{"ownerRootId",identity(page(root))},{"rowUrl",rowUrl},
        {"fieldText",id=="asset-file.folder" ? item->property("text").toString() : QString()},
        {"navigationSource",id=="assets.home" ? qmlContext(item)->baseUrl().toString() : QString()}};
}
inline QString source(QQuickItem* item) {
    const auto value=metadata(item);return value.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e::asset_ui
#endif
