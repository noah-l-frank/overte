// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive identities for the actual selected Places QML. No bookmark, model,
// setting, navigation service or script setter is called by this survey.
#include "NormalAudioControls.h"
#include <QCryptographicHash>
#include <QDir>
#include <QHash>
#include <QMetaProperty>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlProperty>
#include <QPointer>
#include <QUuid>
#include <QVector>

namespace overte::e2e {

inline QString placesRootSource(QQuickItem* item) {
    if (!audioGuiItem(item) || item->property("semanticScreenId").toString() != "places.home") { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/system/places/PicoPlaces.qml")) {
#if defined(Q_OS_IOS)
            if (source.scheme()=="file" && !QDir::cleanPath(source.toLocalFile()).startsWith(
                    QDir::cleanPath(QCoreApplication::applicationDirPath())+"/")) { return {}; }
#endif
            return source.toString();
        }
    }
    return {};
}

inline QQuickItem* placesPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto node=item;node && ++depth<=128;node=node->parentItem()) {
        if (!placesRootSource(node).isEmpty()) { return node; }
    }
    // Popup items can be reparented to the window overlay. Their original QML
    // context, rather than a guessed visual ancestor, still owns the page.
    depth=0;
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        auto root=qobject_cast<QQuickItem*>(context->contextObject());
        if (root && !placesRootSource(root).isEmpty()) { return root; }
    }
    return nullptr;
}

inline QString placesRootId(QQuickItem* root) {
    if (placesRootSource(root).isEmpty()) { return {}; }
    struct Entry { QPointer<QQuickItem> object;QString id; };
    static QVector<Entry> roots;
    for (int index=roots.size()-1;index>=0;--index) { if (roots[index].object.isNull()) { roots.remove(index); } }
    for (const auto& entry:roots) { if (entry.object==root) { return entry.id; } }
    if (roots.size()>=256) { return {}; }
    const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
    roots.append(Entry {root,id});return id;
}

inline QObject* placesBookmarkDialog(QQuickItem* page) {
    if (placesRootSource(page).isEmpty()) { return nullptr; }
    const auto dialogs=page->findChildren<QObject*>(QStringLiteral("bookmarkDialog"),Qt::FindChildrenRecursively);
    if (dialogs.size()!=1 || !dialogs.first()->inherits("QQuickDialog")) { return nullptr; }
    auto dialog=dialogs.first();
    if (dialog->property("visible").userType()!=QMetaType::Bool
            || dialog->property("originalName").userType()!=QMetaType::QString
            || dialog->property("address").userType()!=QMetaType::QString) { return nullptr; }
    return dialog;
}

inline bool placesDescendant(QObject* object,QObject* parent) {
    int depth {0};
    for (auto node=object;node && ++depth<=128;node=node->parent()) { if (node==parent) { return true; } }
    if (auto item=qobject_cast<QQuickItem*>(object)) {
        depth=0;
        for (auto node=item;node && ++depth<=128;node=node->parentItem()) { if (node==parent) { return true; } }
    }
    return false;
}

inline QString placesRowValue(QQuickItem* item,const QString& name) {
    if (!placesPage(item)) { return {}; }
    const auto context=qmlContext(item);
    const auto value=context ? context->contextProperty(name) : QVariant();
    return value.userType()==QMetaType::QString ? value.toString() : QString();
}

inline QString placesRowKey(const QString& value) {
    return value.isEmpty() || value.size()>4096 ? QString() :
        QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(),QCryptographicHash::Sha256).toHex().left(32));
}

inline QString placesControlId(QQuickItem* item) {
    auto page=placesPage(item);
    if (!page) { return {}; }
    if (page==item) { return "places.page"; }
    const auto name=item->objectName();
    if (item->inherits("QQuickTextInput")) {
        if (name=="placesSearch") { return "places.search"; }
        if (name=="bookmarkName") { return "places.bookmark-name"; }
        return {};
    }
    if (item->metaObject()->indexOfSignal("clicked()")<0) { return {}; }
    static const QHash<QString,QString> buttons {
        {"refreshPlaces","places.refresh"},{"goBack","places.back"},{"goForward","places.forward"},
        {"goHome","places.home"},{"placesTab","places.tab.places"},{"bookmarksTab","places.tab.bookmarks"},
        {"serversTab","places.tab.servers"},{"addBookmark","places.bookmark-add"},{"saveBookmark","places.bookmark-save"}
    };
    if (buttons.contains(name)) { return buttons.value(name); }
    if (name=="visitPlace") {
        const auto key=placesRowKey(placesRowValue(item,"placeId"));
        return key.isEmpty() ? QString() : "places.visit."+key;
    }
    static const QHash<QString,QString> bookmarks {
        {"visitBookmark","places.bookmark-visit."},{"renameBookmark","places.bookmark-rename."},
        {"deleteBookmark","places.bookmark-delete."}
    };
    if (bookmarks.contains(name)) {
        const auto key=placesRowKey(placesRowValue(item,"bookmarkName"));
        return key.isEmpty() ? QString() : bookmarks.value(name)+key;
    }
    auto dialog=placesBookmarkDialog(page);
    auto footer=dialog ? dialog->property("footer").value<QObject*>() : nullptr;
    const auto roleProperty=QQmlProperty(item,"DialogButtonBox.buttonRole",qmlContext(item));
    const auto descriptor=roleProperty.property();
    bool knownRole {false}, knownValue {false};
    const auto rejected=descriptor.isEnumType() ? descriptor.enumerator().keyToValue("RejectRole",&knownRole) : -1;
    const auto role=roleProperty.read().toInt(&knownValue);
    // Resolve the actual attached enum, including this build's numeric value.
    // No translated label or synthetic objectName selects this anonymous input.
    if (name.isEmpty() && footer && placesDescendant(item,footer)
            && knownRole && knownValue && role==rejected) { return "places.bookmark-cancel"; }
    return {};
}

inline QJsonObject placesControlSource(QQuickItem* item,const QString& id) {
    auto page=placesPage(item);auto dialog=placesBookmarkDialog(page);
    if (!page || !dialog || placesControlId(item)!=id) { return {}; }
    if ((id=="places.search" || id=="places.bookmark-name")
            && item->property("text").userType()!=QMetaType::QString) { return {}; }
    const auto root=placesRootId(page);
    if (root.isEmpty()) { return {}; }
    const bool place=id.startsWith("places.visit.");
    const bool bookmark=id.startsWith("places.bookmark-visit.") || id.startsWith("places.bookmark-rename.")
        || id.startsWith("places.bookmark-delete.");
    const auto name=placesRowValue(item,place ? "placeId" : "bookmarkName");
    const auto address=placesRowValue(item,place ? "placeAddress" : "bookmarkAddress");
    if ((place || bookmark) && (name.isEmpty() || address.isEmpty() || address.size()>4096)) { return {}; }
    return QJsonObject {{"profile","qt-places-qml-v1"},{"rootId",root},{"qmlSource",placesRootSource(page)},
        {"rowName",place || bookmark ? name : QString()},{"rowAddress",place || bookmark ? address : QString()}};
}

inline void appendPlacesControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    const auto source=placesControlSource(item,id);
    if (source.isEmpty()) { return; }
    for (auto iterator=source.begin();iterator!=source.end();++iterator) { row[iterator.key()]=iterator.value(); }
    auto dialog=placesBookmarkDialog(placesPage(item));
    const bool modal=dialog->property("visible").toBool();
    const bool field=id=="places.search" || id=="places.bookmark-name";
    const bool modalControl=id=="places.bookmark-name" || id=="places.bookmark-save" || id=="places.bookmark-cancel";
    const auto text=item->property("text");
    row["value"]=field && text.userType()==QMetaType::QString ? text.toString() : QString();
    row["modal"]=modal;
    row["inputReady"]=item->isEnabled() && id!="places.page" && modal==modalControl
        && (!field || text.userType()==QMetaType::QString);
}

} // namespace overte::e2e
