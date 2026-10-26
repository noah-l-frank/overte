// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "IOSAssetControls.h"
#include "NormalControlUi.h"
#include <PathUtils.h>
#include <QJSValue>
#include <QKeyEvent>
#include <QHash>

namespace overte::e2e::asset_bundle_ui {
inline QVariant property(QObject* object,const char* name) {
    if (!object) {return {};}
    const auto value=object->property(name);
    return value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toVariant() : value;
}
inline QObject* object(QObject* owner,const char* name) {
    if (!owner) {return nullptr;}const auto value=owner->property(name);
    return value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toQObject() : value.value<QObject*>();
}
inline bool canonical(QQuickItem* root,const QString& relative) {
    return root && qmlContext(root) && qmlContext(root)->baseUrl()==PathUtils::qmlUrl(relative);
}
inline QObject* dialog(QQuickItem* page) {
    if (!canonical(page,"hifi/dialogs/TabletAssetServer.qml") || page->property("featureAssetBundleObservation")!=QVariant(true)) {return nullptr;}
    const auto rows=page->findChildren<QObject*>("bundleDestinationDialog");
    return rows.size()==1 && rows.first()->thread()==QThread::currentThread() ? rows.first() : nullptr;
}
struct ReadState {int depth{0};QHash<QQuickWindow*,QList<QPointer<QQuickItem>>> pages;};
inline ReadState& readState() {static thread_local ReadState state;return state;}
class ReadScope {
public:
    ReadScope() {if (!readState().depth++) {readState().pages.clear();}}
    ~ReadScope() {if (!--readState().depth) {readState().pages.clear();}}
    ReadScope(const ReadScope&)=delete;ReadScope& operator=(const ReadScope&)=delete;
};
inline QList<QPointer<QQuickItem>> pages(QQuickWindow* window) {
    auto& state=readState();
    if (state.depth && state.pages.contains(window)) {return state.pages.value(window);}
    QList<QPointer<QQuickItem>> result;int visited=0;bool complete=true;
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* node,int depth) {
        if (!node || !complete) {return;}if (++visited>8192 || depth>128) {complete=false;return;}
        if (node->objectName()=="AssetServer" && asset_ui::page(node)==node) {result.append(node);}
        for (auto child:node->childItems()) {walk(child,depth+1);}
    };
    walk(window ? window->contentItem() : nullptr,0);if (!complete) {result.clear();}
    // Only weak root membership within one synchronous GUI survey is reused.
    // Every metadata read still observes current objects, source, window,
    // visibility, Dialog state, actual control pointers and bundle values.
    if (state.depth) {state.pages.insert(window,result);}return result;
}
inline QQuickItem* destinationPage(QQuickItem* item) {
    if (!asset_ui::enabled() || !item || !item->window()) {return nullptr;}
    if (item->objectName()!="assetBundleDestination" && item->metaObject()->indexOfSignal("clicked()")<0) {return nullptr;}
    QQuickItem* found=nullptr;
    for (auto weak:pages(item->window())) {
        auto node=weak.data();
        if (node && dialog(node) && node->window()==item->window()
                && node->isVisible() && property(dialog(node),"visible")==QVariant(true)
                && (object(node,"featureAssetDestinationEditor")==item || object(node,"featureAssetDestinationAccept")==item
                    || object(node,"featureAssetDestinationCancel")==item)) {
            if (found) {return nullptr;}found=node;
        }
    }
    return found;
}
inline QString control(QQuickItem* item) {
    if (!asset_ui::enabled() || !item) {return {};}
    auto picker=asset_ui::picker(item);const auto name=item->objectName();
    if (picker && canonical(picker,"dialogs/NativeFileBrowser.qml")) {
        if (name=="bundlePrimary" && item->inherits("QQuickComboBox")) {return "asset-file.bundle-primary";}
        if (item->metaObject()->indexOfSignal("clicked()")>=0) {
            if (name=="bundleConfirm") {return "asset-file.bundle-use";}
            if (name=="bundleBack") {return "asset-file.bundle-back";}
        }
    }
    auto page=destinationPage(item);if (!page) {return {};}
    if (object(page,"featureAssetDestinationEditor")==item && item->inherits("QQuickTextInput")
            && item->property("readOnly")==QVariant(false)) {return "assets.destination";}
    if (item->metaObject()->indexOfSignal("clicked()")<0) {return {};}
    if (object(page,"featureAssetDestinationAccept")==item) {return "assets.destination.accept";}
    if (object(page,"featureAssetDestinationCancel")==item) {return "assets.destination.cancel";}
    return {};
}
inline QJsonValue manifest(const QVariant& value,int selected,bool& complete) {
    if (!value.isValid() || value.isNull()) {return QJsonValue(QJsonValue::Null);}
    if (value.userType()!=QMetaType::QVariantMap) {complete=false;return QJsonValue(QJsonValue::Null);}
    const auto raw=value.toMap();const auto paths=raw.value("relativePaths").toList(),urls=raw.value("urls").toList();
    const auto root=raw.value("root").toUrl();
    if (!root.isLocalFile() || root.hasQuery() || root.hasFragment() || paths.isEmpty() || paths.size()>32 || paths.size()!=urls.size()
            || raw.value("error")!=QVariant(QString())) {complete=false;return QJsonValue(QJsonValue::Null);}
    QJsonArray relative,files;QSet<QString> seen;
    for (int index=0;index<paths.size();++index) {
        const auto path=paths[index].toString();const auto url=urls[index].toUrl();
        if (paths[index].userType()!=QMetaType::QString || path.isEmpty() || path.size()>256 || path.startsWith('/')
                || path.split('/').contains("..") || path.split('/').contains(".") || path.split('/').contains("") || seen.contains(path)
                || !url.isLocalFile() || url.hasQuery() || url.hasFragment() || QDir(root.toLocalFile()).filePath(path)!=url.toLocalFile()) {
            complete=false;return QJsonValue(QJsonValue::Null);
        }
        seen.insert(path);relative.append(path);files.append(url.toString());
    }
    if (selected==-2) {
        const auto primary=raw.value("primaryPath");selected=paths.indexOf(primary);
        if (primary.userType()!=QMetaType::QString || selected<0 || raw.value("primary").toUrl()!=urls[selected].toUrl()) {complete=false;}
    }
    if (selected< -1 || selected>=paths.size()) {complete=false;return QJsonValue(QJsonValue::Null);}
    return QJsonObject{{"root",root.toString()},{"urls",files},{"relativePaths",relative},{"primaryIndex",selected},
        {"primaryPath",selected<0 ? QString() : paths[selected].toString()}};
}
inline QJsonValue pickerBundle(QQuickItem* picker,bool& complete) {
    const auto choices=picker->findChildren<QQuickItem*>("bundlePrimary");
    if (choices.size()!=1 || choices.first()->property("currentIndex").userType()!=QMetaType::Int) {complete=false;return QJsonValue(QJsonValue::Null);}
    return manifest(property(picker,"bundle"),choices.first()->property("currentIndex").toInt(),complete);
}
inline QJsonObject metadata(QQuickItem* item) {
    const auto id=control(item);if (id.isEmpty() || !item->window()) {return {};}
    auto picker=asset_ui::picker(item);auto page=picker ? asset_ui::page(picker) : destinationPage(item);
    auto root=picker ? picker : page;bool complete=true;
    const auto bundle=picker ? pickerBundle(picker,complete) : manifest(property(page,"pendingBundle"),-2,complete);
    if (!complete || bundle.isNull()) {return {};}
    const auto original=bundle.toObject();
    return {{"assetControlVersion",2},{"role",picker ? "picker" : "page"},{"rootId",asset_ui::identity(root)},
        {"windowId",asset_ui::identity(item->window())},{"componentSource",qmlContext(root)->baseUrl().toString()},
        {"controlId",id},{"ownerRootId",asset_ui::identity(page)},{"bundle",bundle},
        {"fieldText",id=="assets.destination" ? item->property("text").toString() : QString()},
        {"destinationText",picker ? QString() : property(object(page,"featureAssetDestinationEditor"),"text").toString()},
        {"choiceIndex",picker ? original.value("primaryIndex").toInt() : -1},
        {"choiceCount",picker ? original.value("relativePaths").toArray().size() : 0},
        {"destinationId",picker ? QJsonValue(QJsonValue::Null) : QJsonValue(asset_ui::identity(dialog(page)))}};
}
inline QString source(QQuickItem* item) {
    const auto value=metadata(item);return value.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
inline QJsonObject inventory(const QList<QQuickItem*>& roots) {
    static const auto instance=QUuid::createUuid().toString(QUuid::WithoutBraces);static quint64 sequence=0;
    bool complete=asset_ui::enabled();QJsonArray rows;
    for (auto root:roots) {
        const bool picker=asset_ui::picker(root)==root;bool valid=true;
        if (!(picker ? canonical(root,"dialogs/NativeFileBrowser.qml") : canonical(root,"hifi/dialogs/TabletAssetServer.qml"))) {complete=false;continue;}
        auto page=picker ? asset_ui::page(root) : root;
        QJsonObject row{{"rootId",asset_ui::identity(root)},{"ownerRootId",asset_ui::identity(page)},{"role",picker ? "picker" : "page"},
            {"bundle",picker ? pickerBundle(root,valid) : manifest(property(root,"pendingBundle"),-2,valid)}};
        if (!picker) {
            const auto destination=dialog(root);const auto editor=object(root,"featureAssetDestinationEditor");
            if (!destination || !editor || property(destination,"visible").userType()!=QMetaType::Bool) {valid=false;}
            row["destinationId"]=asset_ui::identity(destination);row["destinationVisible"]=property(destination,"visible").toBool();
            row["destinationText"]=property(editor,"text").toString();row["uploadedPrimaryUrl"]=root->property("uploadedPrimaryUrl").toString();
        }
        complete=complete && valid;rows.append(row);
    }
    return {{"iosAssetsBundleUiVersion",1},{"instance",instance},{"sequence",static_cast<double>(++sequence)},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"available",asset_ui::enabled()},{"complete",complete},{"rows",rows}};
}
inline bool selectPrimary(QQuickItem* item,QQuickWindow* window,int index) {
    if (!asset_ui::enabled() || control(item)!="asset-file.bundle-primary" || !window || item->window()!=window
            || index<0 || index>=32 || index>=item->property("count").toInt() || !item->isEnabled()) {return false;}
    const auto focused=[&] {
        for (auto focus=window->activeFocusItem();focus;focus=focus->parentItem()) {if (focus==item) {return true;}}
        const auto popup=object(item,"popup");const auto content=popup ? qobject_cast<QQuickItem*>(object(popup,"contentItem")) : nullptr;
        if (!popup || property(popup,"visible")!=QVariant(true) || !content || content->window()!=window) {return false;}
        for (auto focus=window->activeFocusItem();focus;focus=focus->parentItem()) {if (focus==content) {return true;}}
        return false;
    };
    const auto key=[&](int code) {
        QPointer<QQuickWindow> held=window;QKeyEvent down(QEvent::KeyPress,code,Qt::NoModifier),up(QEvent::KeyRelease,code,Qt::NoModifier);
        const auto pressed=QCoreApplication::sendEvent(window,&down);return held && QCoreApplication::sendEvent(held,&up) && pressed;
    };
    QPointer<QQuickItem> held=item;QPointer<QQuickWindow> surface=window;
    if (!focused() || !key(Qt::Key_Home)) {return false;}
    for (int count=0;held && surface && count<index;++count) {if (!focused() || !key(Qt::Key_Down)) {return false;}}
    return held && surface && focused() && key(Qt::Key_Return);
}
}
#endif
