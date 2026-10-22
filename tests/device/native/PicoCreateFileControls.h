// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QGuiApplication>
#include <QHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QPointer>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <algorithm>
#include <cmath>
#include <functional>

namespace overte::e2e {
inline QString createOriginalComponent(QQuickItem* item, const QString& suffix) {
    if (!qApp || QThread::currentThread()!=qApp->thread() || !item || item->thread()!=qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment() && source.path().endsWith(suffix)) {
            return source.toString(QUrl::FullyEncoded);
        }
    }
    return {};
}
inline QString createFileRole(QQuickItem* root) {
    if (!root || root->objectName()!="nativeFileBrowser"
            || createOriginalComponent(root,"/dialogs/NativeFileBrowser.qml").isEmpty()) { return {}; }
    for (const auto& key:QStringList{"bundleMode","saveDialog","selectDirectory","multiSelect","closing"}) {
        if (root->property(key.toLatin1()).userType()!=QMetaType::Bool) { return {}; }
    }
    if (root->property("bundleMode").toBool() || root->property("selectDirectory").toBool()
            || root->property("multiSelect").toBool() || root->property("filter").toString()!="*.json") { return {}; }
    if (!root->property("saveDialog").toBool() && root->property("caption").toString()=="Select .json to Import") { return "import"; }
    if (root->property("saveDialog").toBool() && root->property("caption").toString()=="Select Where to Save") { return "export"; }
    return {};
}
inline QQuickItem* createFileBrowser(QQuickItem* item) {
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (!createFileRole(parent).isEmpty()) { return parent; }
    }
    return nullptr;
}

// Weak original roots include hidden and detached browsers. Closing, absence
// and QObject retirement are separate facts; no callback lease is inferred.
class CreateUiInventory {
public:
    QJsonObject observe(QQuickItem* root,QQuickWindow* window) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        bool complete=root && window && root->window()==window && root->thread()==qApp->thread() && window->thread()==qApp->thread();
        for (auto iterator=_known.begin();iterator!=_known.end();) {
            if (!iterator.value().item) { _retired.insert(iterator.value().id);iterator=_known.erase(iterator); }
            else { ++iterator; }
        }
        QSet<QQuickItem*> seen;int count {0};
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || !complete) { return; }
            if (++count>4096 || depth>128 || seen.contains(item) || item->thread()!=qApp->thread()) { complete=false;return; }
            seen.insert(item);
            const bool editor=!createOriginalComponent(item,"/system/create/qml/NativeCreate.qml").isEmpty();
            const auto caption=item->property("caption").toString();
            const bool candidate=item->objectName()=="nativeFileBrowser" && (caption=="Select .json to Import" || caption=="Select Where to Save");
            const auto role=candidate ? createFileRole(item) : QString();
            if (candidate && role.isEmpty()) { complete=false;return; }
            if (editor || !role.isEmpty()) {
                const auto profile=editor ? QStringLiteral("create-editor-v1") : "create-"+role+"-json-v1";
                if (!_known.contains(item)) {
                    if (_known.size()>=16) { complete=false;return; }
                    _known.insert(item,{item,QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),profile});
                } else if (_known.value(item).profile!=profile) { complete=false;return; }
            }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        if (complete) {
            walk(root,0);
            if (root->parentItem()==window->contentItem()) {
                for (auto layer:window->contentItem()->childItems()) {
                    if (layer!=root && layer->inherits("QQuickOverlay")) { walk(layer,0); }
                }
            }
        }
        complete=complete && _retired.size()<=256;
        QJsonArray roots,retired;
        auto keys=_retired.values();std::sort(keys.begin(),keys.end());
        for (const auto& id:keys) { retired.append(id); }
        auto tracked=_known.values();std::sort(tracked.begin(),tracked.end(),[](const Tracked& a,const Tracked& b){return a.id<b.id;});
        for (const auto& row:tracked) {
            if (!row.item || row.item->thread()!=qApp->thread()) { complete=false;break; }
            bool visible {true};int depth {0};
            for (auto parent=row.item.data();parent;parent=parent->parentItem()) {
                if (++depth>128) { complete=false;break; }
                visible=visible && parent->isVisible() && parent->opacity()>.01;
            }
            QJsonObject value{{"id",row.id},{"profile",row.profile},{"visible",visible},{"inCurrentTree",seen.contains(row.item)}};
            if (row.profile=="create-editor-v1") {
                value["componentSource"]=createOriginalComponent(row.item,"/system/create/qml/NativeCreate.qml");
                if (value.value("componentSource").toString().isEmpty()) { complete=false;break; }
            } else {
                const auto request=row.item->property("requestId"),closing=row.item->property("closing");
                const auto role=createFileRole(row.item);
                if (role.isEmpty() || row.profile!="create-"+role+"-json-v1" || request.userType()!=QMetaType::QString || closing.userType()!=QMetaType::Bool
                        || request.toString().size()>4096) { complete=false;break; }
                value["componentSource"]=createOriginalComponent(row.item,"/dialogs/NativeFileBrowser.qml");
                value["closing"]=closing.toBool();value["requestId"]=request.toString();
            }
            roots.append(value);
        }
        return {{"inventoryVersion",1},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"complete",complete},{"roots",complete ? roots : QJsonArray()},{"retiredRoots",complete ? retired : QJsonArray()}};
    }
    QString identity(QQuickItem* item) const {
        const auto row=_known.value(item);return row.item==item ? row.id : QString();
    }
    QString windowIdentity(QQuickWindow* window) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !window || window->thread()!=qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const auto row=_windows.value(window);
        if (row.window==window) { return row.id; }
        // Never borrow a prior native-window identity when Qt reuses an address.
        if (_windowGenerations>=16) { return {}; }
        ++_windowGenerations;const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _windows.insert(window,{window,id});return id;
    }
private:
    struct Tracked {QPointer<QQuickItem> item;QString id,profile;};
    QHash<QQuickItem*,Tracked> _known;
    QSet<QString> _retired;
    struct TrackedWindow {QPointer<QQuickWindow> window;QString id;};
    QHash<QQuickWindow*,TrackedWindow> _windows;
    int _windowGenerations {0};
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _sequence {0};
};
inline CreateUiInventory& createUiInventory() { static CreateUiInventory source;return source; }

inline QString createFileControlId(QQuickItem* item) {
    const auto root=createFileBrowser(item);
    if (!root) { return {}; }
    if (root==item) { return "create-file.page"; }
    const auto name=item->objectName();
    if (item->inherits("QQuickTextInput") && item->property("readOnly").userType()==QMetaType::Bool && !item->property("readOnly").toBool()) {
        if (name=="fileFolderPath") { return "create-file.folder"; }
        if (name=="fileNameInput") { return "create-file.name"; }
    }
    if (item->metaObject()->indexOfSignal("clicked()")>=0) {
        if (name=="fileAccept") { return "create-file.accept"; }
        if (name=="fileCancel") { return "create-file.cancel"; }
    }
    return {};
}
inline bool createFilePath(const QString& text,const QString& identifier,const QString& role) {
    if (text.size()>4096 || text.contains("\\") || text.split('/').contains(".") || text.split('/').contains("..")) { return false; }
    const QString suffix=identifier=="create-file.folder" ? QString() : role=="import" ? "/entity-import.json" : "/export.json";
    return QRegularExpression("\\A/(?:[^/\\x00-\\x20]+/)*feature-create-[0-9a-f]{32}-[0-9a-f]{32}"+QRegularExpression::escape(suffix)+"\\z").match(text).hasMatch();
}
inline void appendCreateFileObservation(QJsonObject& value,QQuickItem* item,const QString& identifier) {
    const auto root=createFileBrowser(item);if (!root) { return; }
    const auto role=createFileRole(root),rootId=createUiInventory().identity(root);
    bool ready=item->isEnabled() && !rootId.isEmpty() && !root->property("closing").toBool() && root->property("requestId").toString().isEmpty();
    value["rootId"]=rootId;value["role"]=role;
    if (identifier=="create-file.page") {
        ready=false;
        value["caption"]=root->property("caption").toString();value["filter"]=root->property("filter").toString();
        value["directory"]=root->property("dir").toUrl().toString(QUrl::FullyEncoded);
        value["closing"]=root->property("closing").toBool();value["requestId"]=root->property("requestId").toString();
        value["errorText"]=root->property("error").toString();
        value["componentSource"]=createOriginalComponent(root,"/dialogs/NativeFileBrowser.qml");
    } else if (identifier=="create-file.folder" || identifier=="create-file.name") {
        value["text"]=item->property("text").toString();
    }
    value["inputReady"]=ready;
}
inline QString createFileControlSource(QQuickItem* item,const QString& identifier) {
    QJsonObject value;appendCreateFileObservation(value,item,identifier);
    const auto root=createFileBrowser(item);
    if (!root || value.value("rootId").toString().isEmpty()) { return {}; }
    const auto window=item->window();const auto windowId=createUiInventory().windowIdentity(window);
    if (windowId.isEmpty() || !window || item->thread()!=qApp->thread()) { return {}; }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    const auto rect=item->mapRectToScene(item->boundingRect());
    const auto finite=[](qreal number,qreal limit) {return std::isfinite(number) && std::abs(number)<=limit;};
    if (!finite(item->width(),1000000) || !finite(item->height(),1000000) || item->width()<=0 || item->height()<=0
            || !finite(center.x(),1000000000) || !finite(center.y(),1000000000)
            || !finite(rect.x(),1000000000) || !finite(rect.y(),1000000000)
            || !finite(rect.width(),1000000) || !finite(rect.height(),1000000) || rect.width()<=0 || rect.height()<=0
            || window->width()<=0 || window->height()<=0 || window->width()>1000000 || window->height()>1000000
            || !finite(window->devicePixelRatio(),16) || window->devicePixelRatio()<=0) { return {}; }
    value["geometry"]=QJsonObject{{"sceneCenterX",center.x()},{"sceneCenterY",center.y()},
        {"width",item->width()},{"height",item->height()},{"sceneX",rect.x()},{"sceneY",rect.y()},
        {"sceneWidth",rect.width()},{"sceneHeight",rect.height()}};
    value["nativeWindow"]=QJsonObject{{"id",windowId},{"width",window->width()},{"height",window->height()},
        {"devicePixelRatio",window->devicePixelRatio()}};
    value["directory"]=root->property("dir").toUrl().toString(QUrl::FullyEncoded);
    value["closing"]=root->property("closing").toBool();value["requestId"]=root->property("requestId").toString();
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
#endif
