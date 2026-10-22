// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NormalPlacesControls.h"
#include "NormalNavigationAddress.h"

namespace overte::e2e {
inline QString navigationLookupComponent(QQuickItem* root,bool home) {
    if (!loginGuiItem(root) || !QString(root->metaObject()->className()).startsWith(home ? "TabletHome_QMLTYPE_" : "TabletAddressDialog_QMLTYPE_")
            || (home ? root->property("semanticScreenId").toString()!="tablet.home" : root->objectName()!="tabletAddressDialog")) { return {}; }
    int depth{0};
    for (auto c=qmlContext(root);c && ++depth<=128;c=c->parentContext()) {
        const auto url=c->baseUrl();
        if (c->nameForObject(root)==(home ? "tablet" : "root") && (url.scheme()=="file" || url.scheme()=="qrc")
                && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                && url.path().endsWith(home ? "/hifi/tablet/TabletHome.qml" : "/hifi/tablet/TabletAddressDialog.qml")) { return url.toString(); }
    }
    return {};
}
inline QString navigationLookupRootId(QQuickItem* root) {
    if (navigationLookupComponent(root,true).isEmpty() && navigationLookupComponent(root,false).isEmpty()) { return {}; }
    static QHash<QQuickItem*,QPair<QPointer<QQuickItem>,QString>> rows;static QSet<QString> retired;
    for (auto i=rows.begin();i!=rows.end();) {
        if (!i.value().first) { retired.insert(i.value().second);i=rows.erase(i); }else { ++i; }
    }
    if (retired.size()>256 || (!rows.contains(root) && rows.size()>=128)) { return {}; }
    if (!rows.contains(root)) {
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        if (retired.contains(id)) { return {}; }rows.insert(root,qMakePair(QPointer<QQuickItem>(root),id));
    }
    return rows.value(root).second;
}
inline QQuickItem* navigationLookupRoot(QQuickItem* item,bool home) {
    if (!loginGuiItem(item)) { return nullptr; }int depth{0};
    for (auto p=item;p && ++depth<=128;p=p->parentItem()) { if (!navigationLookupComponent(p,home).isEmpty()) { return p; } }
    return nullptr;
}
inline QQuickItem* navigationLookupNamed(QQuickItem* root,bool home,const QString& name) {
    const auto source=navigationLookupComponent(root,home);if (source.isEmpty()) { return nullptr; }
    QQuickItem* result{nullptr};int depth{0};
    for (auto c=qmlContext(root);c && ++depth<=128;c=c->parentContext()) {
        if (c->nameForObject(root)!=(home ? "tablet" : "root") || c->baseUrl().toString()!=source) { continue; }
        auto item=qobject_cast<QQuickItem*>(placesObject(c->contextProperty(name)));
        if (!loginGuiItem(item) || c->nameForObject(item)!=name || (result && result!=item)) { return nullptr; }result=item;
    }
    return result;
}
inline bool navigationLookupVisible(QQuickItem* item) {
    if (!loginGuiItem(item) || !item->window() || item->width()<=0 || item->height()<=0) { return false; }
    int depth{0};for (auto p=item;p && ++depth<=128;p=p->parentItem()) {
        if (!p->isVisible() || !std::isfinite(p->opacity()) || p->opacity()<=.01) { return false; }
    }
    return depth<=128;
}
inline QJsonObject navigationLookupHome(QQuickItem* root) {
    const auto source=navigationLookupComponent(root,true),id=navigationLookupRootId(root);
    auto swipe=navigationLookupNamed(root,true,"swipeView");
    if (source.isEmpty() || id.isEmpty() || !swipe || swipe->property("count").userType()!=QMetaType::Int
            || swipe->property("currentIndex").userType()!=QMetaType::Int) { return {}; }
    const auto count=swipe->property("count").toInt(),index=swipe->property("currentIndex").toInt();
    if (count<0 || count>32 || index< -1 || index>=count) { return {}; }
    return {{"rootId",id},{"sourceSha256",placesHash(source)},{"pageIndex",index},{"pageCount",count},{"visible",navigationLookupVisible(root)}};
}
inline QJsonObject navigationLookupAddress(QQuickItem* root) {
    const auto source=navigationLookupComponent(root,false),id=navigationLookupRootId(root);
    auto field=navigationLookupNamed(root,false,"addressLine");
    if (source.isEmpty() || id.isEmpty() || !field || field->objectName()!="tabletAddressLine") { return {}; }
    auto value=navigationAddressObservation(field);if (value.isEmpty()) { return {}; }
    value["rootId"]=id;value["sourceSha256"]=placesHash(source);value["focused"]=field->hasActiveFocus();
    value["visible"]=navigationLookupVisible(root);return value;
}
inline QString navigationLookupControlSource(QQuickItem* item,const QString& control) {
    if (!loginGuiItem(item)) { return {}; }QJsonObject value;
    if (control=="navigation.address") {
        auto root=navigationLookupRoot(item,false);
        if (!root || navigationLookupNamed(root,false,"addressLine")!=item) { return {}; }value=navigationLookupAddress(root);
    } else {
        auto root=navigationLookupRoot(item,true);value=navigationLookupHome(root);
        if (value.isEmpty()) { return {}; }
        if (control=="navigation.goto") {
            if (!QString(item->metaObject()->className()).startsWith("TabletButton_QMLTYPE_") || item->property("text").toString()!="GOTO"
                    || item->property("icon").toString()!="icons/tablet-icons/goto-i.svg"
                    || item->property("activeIcon").toString()!="icons/tablet-icons/goto-a.svg") { return {}; }
            const auto uuid=QUuid(placesVariant(item->property("uuid")).toString());if (uuid.isNull()) { return {}; }
            bool original{false};int depth{0};
            for (auto c=qmlContext(item);c && ++depth<=128;c=c->parentContext()) {
                const auto url=c->baseUrl();
                original=original || (c->nameForObject(item)=="tabletButton" && (url.scheme()=="file" || url.scheme()=="qrc")
                    && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment() && url.path().endsWith("/hifi/tablet/TabletButton.qml"));
            }
            if (!original) { return {}; }value["buttonId"]=uuid.toString(QUuid::WithoutBraces);
        } else if (control.startsWith("tablet.page.")) {
            if (!item->inherits("QQuickMouseArea") || item->objectName()!=control) { return {}; }
            bool okay{false};const auto page=control.mid(12).toInt(&okay);
            const auto context=qmlContext(item);const auto originalIndex=context ? placesVariant(context->contextProperty("index")) : QVariant();
            bool indexOkay{false};const auto index=originalIndex.toInt(&indexOkay);
            if (!okay || page<1 || page>value.value("pageCount").toInt() || !indexOkay || (originalIndex.userType()!=QMetaType::Int && originalIndex.userType()!=QMetaType::Double)
                    || originalIndex.toDouble()!=index || index!=page-1 || !context || context->baseUrl().toString()!=navigationLookupComponent(root,true)) { return {}; }
            value["page"]=page;
        } else { return {}; }
    }
    if (value.isEmpty()) { return {}; }
    const auto rect=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
    if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width()) || !std::isfinite(rect.height())
            || rect.width()<=0 || rect.height()<=0) { return {}; }
    value["sceneX"]=rect.x();value["sceneY"]=rect.y();value["width"]=rect.width();value["height"]=rect.height();value["controlId"]=control;
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
