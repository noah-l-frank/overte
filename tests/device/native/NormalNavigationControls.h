// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalChatControls.h"
#include <PathUtils.h>
#include "NavigationModalObservation.h"
namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
inline QQuickItem* navigationPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int contextDepth=0;
    for (auto context=qmlContext(item);context && ++contextDepth<=128;context=context->parentContext()) {
        if (context->baseUrl()!=PathUtils::defaultScriptsLocation().resolved(QUrl("system/places/PicoPlaces.qml"))) { continue; }
        auto root=qobject_cast<QQuickItem*>(createVariant(context->contextProperty("root")).value<QObject*>());
        if (root && context->nameForObject(root)=="root" && root->property("semanticScreenId").toString()=="places.home") { return root; }
    }
    int depth=0;
    for (auto node=item;node && ++depth<=128;node=node->parentItem()) {
        if (node->property("semanticScreenId").toString()!="places.home" || !loginQmlId(node,"root")) { continue; }
        for (auto context=qmlContext(node);context;context=context->parentContext()) {
            if (context->nameForObject(node)=="root" && context->baseUrl()==PathUtils::defaultScriptsLocation().resolved(QUrl("system/places/PicoPlaces.qml"))) { return node; }
        }
    }
    return nullptr;
}
inline QVariant navigationRole(QQuickItem* item,const QString& key) {
    auto context=qmlContext(item);return context ? createVariant(context->contextProperty(key)) : QVariant();
}
inline QObject* navigationDialog(QQuickItem* item) {
    if (!navigationPage(item)) { return nullptr; }
    for (auto context=qmlContext(item);context;context=context->parentContext()) {
        auto dialog=createVariant(context->contextProperty("bookmarkDialog")).value<QObject*>();
        if (!dialog || dialog->objectName()!="bookmarkDialog") { continue; }
        auto content=qobject_cast<QQuickItem*>(createVariant(dialog->property("contentItem")).value<QObject*>());
        auto footer=qobject_cast<QQuickItem*>(createVariant(dialog->property("footer")).value<QObject*>());
        for (auto node=item;node;node=node->parentItem()) { if (node==content || node==footer) { return dialog; } }
    }
    return nullptr;
}
inline QQuickItem* navigationError(QQuickItem* item) {
    for (auto node=item;node;node=node->parentItem()) {
        const auto text=node->property("text");
        if (text.userType()!=QMetaType::QString || text.toString()!="There is no address information for that user or place") { continue; }
        for (auto context=qmlContext(node);context;context=context->parentContext()) {
            if (context->nameForObject(node)=="root" && (context->baseUrl()==PathUtils::qmlUrl("dialogs/TabletMessageBox.qml")
                    || context->baseUrl()==PathUtils::qmlUrl("dialogs/MessageDialog.qml"))) { return node; }
        }
    }
    return nullptr;
}
inline QString navigationControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    if (navigationError(item) && item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="OK") { return "navigation.error.ok"; }
    auto page=navigationPage(item);const auto name=item->objectName();
    if (!page) {
        if (item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="PLACES") {
            for (auto context=qmlContext(item);context;context=context->parentContext()) {
                if (context->baseUrl()==PathUtils::qmlUrl("hifi/tablet/TabletButton.qml") && context->nameForObject(item)=="tabletButton") { return "navigation.entry"; }
            }
        }
        return {};
    }
    if (page==item) { return "navigation.page"; }
    if (name=="placesSearch" || name=="bookmarkName" || name=="newServerUrl") {
        if (!item->inherits("QQuickTextInput")) { return {}; }
        return "navigation."+name;
    }
    if (auto dialog=navigationDialog(item)) {
        if (item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="Cancel") { return "navigation.bookmark.cancel"; }
        if (name=="saveBookmark") { return "navigation.bookmark.save"; }
        return {};
    }
    if (QStringList{"placesTab","bookmarksTab","serversTab","refreshPlaces","addBookmark","maturityFilters","addServer"}.contains(name)
            || QStringList{"rating_everyone","rating_teen","rating_mature","rating_adult","rating_unrated"}.contains(name)) { return "navigation."+name; }
    if (QStringList{"visitPlace","visitBookmark","renameBookmark","deleteBookmark","fetchServer","pinServer"}.contains(name)) {
        bool okay=false;const auto index=navigationRole(item,"index").toInt(&okay);
        if (okay && index>=0 && index<1000) { return "navigation."+name+"."+QString::number(index); }
    }
    return {};
}
inline void appendNavigationControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    row["inputReady"]=item->isEnabled() && id!="navigation.page";
    if (auto dialog=navigationDialog(item)) {
        row["dialogOriginalName"]=dialog->property("originalName").toString();
        row["dialogAddress"]=dialog->property("address").toString();
    }
    if (id=="navigation.placesSearch" || id=="navigation.bookmarkName" || id=="navigation.newServerUrl") { row["text"]=item->property("text").toString(); }
    if (id.startsWith("navigation.rating_") || id.startsWith("navigation.fetchServer.") || id.startsWith("navigation.pinServer.")) { row["checked"]=item->property("checked").toBool(); }
    for (const auto& key:QStringList{"placeId","placeName","placeAddress","bookmarkName","bookmarkAddress","serverUrl","serverIndex"}) {
        const auto value=navigationRole(item,key);
        if (value.isValid() && (id.startsWith("navigation.visit") || id.startsWith("navigation.rename") || id.startsWith("navigation.delete")
                || id.startsWith("navigation.fetchServer.") || id.startsWith("navigation.pinServer."))) { row[key]=QJsonValue::fromVariant(value); }
    }
}
inline QString navigationControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendNavigationControlObservation(row,item,id);
    if (auto page=navigationPage(item)) {
        row["currentAddress"]=page->property("currentAddress").toString();
        row["loading"]=page->property("loading").toBool();
    }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    row["x"]=center.x();row["y"]=center.y();
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
inline bool navigationDecorationPoint(QQuickItem* item,QQuickWindow* window,const QPointF& point) {
    // Quick controls may paint transparent siblings above their input item.
    // Permit the ordinary dispatcher to pass through those decorations only
    // for an original Places control, never an input handler or foreign popup.
    if (!item || !window || !navigationPage(item)) { return false; }
    QSet<QQuickItem*> ancestors;
    for (auto parent=item;parent;parent=parent->parentItem()) { ancestors.insert(parent); }
    auto hit=window->contentItem();bool diverged=false;
    for (int depth=0;hit && depth<128;++depth) {
        if (!ancestors.contains(hit)) { diverged=true;
            if (hit->isEnabled() && ((hit->acceptedMouseButtons() & Qt::LeftButton) || hit->acceptTouchEvents())) { return false; }
            for (auto child:hit->children()) { if (child->inherits("QQuickPointerHandler") && child->property("enabled").toBool()) { return false; } }
        } else if (diverged) { return false; }
        const auto local=hit->mapFromScene(point);auto next=hit->childAt(local.x(),local.y());
        if (!next) { return diverged; }hit=next;
    }
    return false;
}
inline bool navigationText(const QString& text) {
    return text.isEmpty() || QRegularExpression("\\A(?:e2e-|renamed-|hidden-)[0-9a-f]{32}\\z").match(text).hasMatch();
}
#endif
}
