// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"
#include <QQuickWindow>
#include <algorithm>
#include <cmath>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
inline QStringList emoteNames() {
    return {"Crying","Surprised","Dancing","Cheering","Waving","Fall","Pointing","Clapping","Sit","Love"};
}
inline QString emoteComponentSource(QQuickItem* item) {
    if (!audioGuiItem(item) || !loginQmlId(item,"root")) { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/system/+android_phoneInterface/PhoneEmote.qml")) { return source.toString(); }
    }
    return {};
}
inline QStringList emoteModel(QQuickItem* page) {
    if (!page) { return {}; }
    const auto original=createVariant(page->property("emotes"));
    if (original.userType()==QMetaType::QStringList) { return original.toStringList(); }
    if (original.userType()!=QMetaType::QVariantList) { return {}; }
    QStringList names;
    for (const auto& value:original.toList()) {
        if (value.userType()!=QMetaType::QString) { return {}; }
        names.append(value.toString());
    }
    return names;
}
inline QQuickItem* emotePage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (emoteComponentSource(parent).isEmpty()) { continue; }
        const auto active=parent->property("activeEmote"),status=parent->property("statusText");
        const auto names=emoteModel(parent);auto sorted=names;auto known=emoteNames();
        std::sort(sorted.begin(),sorted.end());std::sort(known.begin(),known.end());
        if (names.size()==10 && sorted==known && active.userType()==QMetaType::QString
                && (active.toString().isEmpty() || names.contains(active.toString()))
                && status.userType()==QMetaType::QString && status.toString().size()<=256
                && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) { return parent; }
    }
    return nullptr;
}
inline QRectF emoteVisibleRect(QQuickItem* item) {
    if (!audioGuiItem(item) || !item->window()) { return {}; }
    auto window=item->window();QRectF result(0,0,window->width(),window->height());
    int depth {0};
    for (auto parent=item;parent;parent=parent->parentItem()) {
        if (++depth>128) { return {}; }
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity()<=.01) { return {}; }
        if (parent==item || parent->clip()) {
            result=result.intersected(parent->mapRectToScene(QRectF(0,0,parent->width(),parent->height())));
        }
    }
    return std::isfinite(result.x()) && std::isfinite(result.y()) && std::isfinite(result.width())
        && std::isfinite(result.height()) ? result : QRectF();
}
inline QString emoteControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto page=emotePage(item);
    if (!page) {
        const auto nav=scriptControlId(item);
        if (nav=="tablet.home" || nav.startsWith("tablet.page.")) { return nav; }
        return item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="EMOTE"
            ? QStringLiteral("emote.entry") : QString();
    }
    if (page==item) { return "emote.page"; }
    if (loginQmlId(item,"emoteGrid") && item->inherits("QQuickGridView")) { return "emote.grid"; }
    const auto name=item->property("text").toString();
    if (emoteModel(page).contains(name) && item->objectName()=="PhoneEmoteButton_"+name
            && item->metaObject()->indexOfSignal("clicked()")>=0) { return "emote.play."+name; }
    return {};
}
inline QQuickItem* emoteGrid(QQuickItem* item) {
    auto page=emotePage(item);
    for (auto node=item;page && node && node!=page;node=node->parentItem()) {
        if (emoteControlId(node)=="emote.grid") { return node; }
    }
    return nullptr;
}
inline void appendEmoteControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    auto page=emotePage(item);auto grid=emoteGrid(item);
    bool ready=item->isEnabled() && !emoteVisibleRect(item).isEmpty() && id!="emote.page";
    if (grid) {
        ready=ready && grid->property("moving").userType()==QMetaType::Bool && !grid->property("moving").toBool()
            && grid->property("dragging").userType()==QMetaType::Bool && !grid->property("dragging").toBool();
    }
    if (id=="emote.page") {
        row["profile"]="phone-native-chooser-v1";row["activeName"]=page->property("activeEmote").toString();
        row["names"]=QJsonArray::fromStringList(emoteModel(page));
        row["componentSourceSha256"]=QString::fromLatin1(QCryptographicHash::hash(emoteComponentSource(page).toUtf8(),QCryptographicHash::Sha256).toHex());
    } else if (id=="emote.grid") {
        const auto y=item->property("contentY"),origin=item->property("originY"),height=item->property("contentHeight");
        const double current=y.toDouble(),start=origin.toDouble(),extent=height.toDouble();
        ready=ready && std::isfinite(current) && std::isfinite(start) && std::isfinite(extent) && extent>0
            && std::isfinite(item->height()) && item->height()>0;
        row["contentY"]=current;row["originY"]=start;row["contentHeight"]=extent;row["viewportHeight"]=item->height();
        row["moving"]=item->property("moving").toBool();row["dragging"]=item->property("dragging").toBool();
    } else if (id.startsWith("emote.play.")) {
        const auto name=id.mid(QStringLiteral("emote.play.").size());
        row["name"]=name;row["index"]=emoteModel(page).indexOf(name);
        row["highlighted"]=item->property("highlighted").toBool();
        ready=ready && grid && item->property("highlighted").userType()==QMetaType::Bool
            && emoteVisibleRect(item).contains(item->mapToScene(QPointF(item->width()/2,item->height()/2)));
    }
    row["inputReady"]=ready;
}
inline QString emoteControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendEmoteControlObservation(row,item,id);
    if (auto page=emotePage(item)) { row["sourceActiveName"]=page->property("activeEmote").toString(); }
    if (!item || !item->window()) { return {}; }
    const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(point.x()) || !std::isfinite(point.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) { return {}; }
    row["sceneX"]=point.x();row["sceneY"]=point.y();row["width"]=item->width();row["height"]=item->height();
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
#endif
} // namespace overte::e2e
