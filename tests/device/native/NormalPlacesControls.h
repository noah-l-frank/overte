// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NormalLoginControls.h"
#include <QAbstractItemModel>
#include <QHash>
#include <QJsonArray>
#include <QJSValue>
#include <QPair>
#include <QPointer>
#include <QQmlProperty>
#include <QSet>
#include <QUuid>
#include <QUrl>
#include <cmath>

namespace overte::e2e {
inline QObject* placesObject(const QVariant& value) {
    const auto object = value.value<QObject*>();
    return object ? object : value.userType() == qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toQObject() : nullptr;
}
inline QVariant placesVariant(QVariant value) {
    return value.userType() == qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toVariant() : value;
}
inline QString placesHash(const QString& text) { return loginEndpointDigest(text); }

inline QString placesComponent(QQuickItem* root) {
    if (!loginGuiItem(root) || root->property("semanticScreenId").toString() != "places.home"
            || root->property("channel").toString() != "com.overte.places") { return {}; }
    int depth {0};
    for (auto context = qmlContext(root); context && ++depth <= 128; context = context->parentContext()) {
        const auto url = context->baseUrl();
        if (context->nameForObject(root) == "root" && (url.scheme() == "qrc" || url.scheme() == "file")
                && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                && url.path().endsWith("/system/places/PicoPlaces.qml")) { return url.toString(); }
    }
    return {};
}

inline QString placesRootInstance(QQuickItem* root) {
    if (placesComponent(root).isEmpty()) { return {}; }
    // Weak original QObject identity survives independent readers without
    // retaining a closed page or confusing a reused pointer with its old root.
    static QHash<QQuickItem*, QPair<QPointer<QQuickItem>, QString>> roots;
    static QSet<QString> retired;
    for (auto i = roots.begin(); i != roots.end();) {
        if (!i.value().first) { retired.insert(i.value().second);i = roots.erase(i); }
        else { ++i; }
    }
    if (retired.size() > 256 || (!roots.contains(root) && roots.size() >= 16)) { return {}; }
    if (!roots.contains(root)) {
        const auto id = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        if (retired.contains(id)) { return {}; }
        roots.insert(root, qMakePair(QPointer<QQuickItem>(root), id));
    }
    return roots.value(root).second;
}

inline QQuickItem* placesRoot(QQuickItem* item) {
    if (!loginGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto node = item; node && ++depth <= 128; node = node->parentItem()) {
        if (!placesComponent(node).isEmpty()) { return node; }
    }
    // Controls 2 renders the original Dialog in its window overlay. Resolve its
    // lexical original root, never an arbitrary similarly named sibling item.
    depth = 0;
    for (auto context = qmlContext(item); context && ++depth <= 128; context = context->parentContext()) {
        auto root = qobject_cast<QQuickItem*>(placesObject(context->contextProperty("root")));
        if (root && root->window() == item->window() && !placesComponent(root).isEmpty()) { return root; }
    }
    return nullptr;
}

inline QObject* placesNamedObject(QQuickItem* root, const QString& id) {
    const auto source = placesComponent(root);QObject* result {nullptr};int depth {0};
    if (source.isEmpty()) { return nullptr; }
    for (auto context = qmlContext(root); context && ++depth <= 128; context = context->parentContext()) {
        if (context->nameForObject(root) != "root" || context->baseUrl().toString() != source) { continue; }
        auto object = placesObject(context->contextProperty(id));
        if (!object || object->thread() != qApp->thread() || context->nameForObject(object) != id
                || (result && result != object)) { return nullptr; }
        result = object;
    }
    return result;
}

inline QJsonObject placesModel(QQuickItem* root, const QString& id, const QStringList& fields) {
    auto model = qobject_cast<QAbstractItemModel*>(placesNamedObject(root, id));
    if (!model || model->rowCount() < 0 || model->rowCount() > 256) { return {}; }
    const auto roles = model->roleNames();QHash<QString, int> selected;
    for (auto role = roles.cbegin(); role != roles.cend(); ++role) {
        const auto name = QString::fromUtf8(role.value());
        if (fields.contains(name)) {
            if (selected.contains(name)) { return {}; }selected.insert(name, role.key());
        }
    }
    // A genuine empty QML ListModel has no inferred dynamic roles yet.
    if (model->rowCount() && selected.size() != fields.size()) { return {}; }
    QJsonArray rows;
    for (int index = 0; index < model->rowCount(); ++index) {
        QJsonObject row;
        for (const auto& field : fields) {
            const auto value = model->data(model->index(index, 0), selected.value(field));
            if (field == "serverIndex") {
                bool okay {false};const auto number = value.toDouble(&okay);
                const bool numeric = value.userType() == QMetaType::Int || value.userType() == QMetaType::Double
                    || value.userType() == QMetaType::UInt || value.userType() == QMetaType::LongLong || value.userType() == QMetaType::ULongLong;
                if (!okay || !numeric || !std::isfinite(number)
                        || number < 0 || number > 255 || number != std::floor(number)) { return {}; }
                row[field] = static_cast<int>(number);
            } else if (field == "fetched" || field == "pinned" || field == "failed") {
                if (value.userType() != QMetaType::Bool) { return {}; }row[field] = value.toBool();
            } else {
                if (value.userType() != QMetaType::QString || value.toString().size() > 8192) { return {}; }
                row[field + "Sha256"] = placesHash(value.toString());
            }
        }
        rows.append(row);
    }
    return {{"rows", rows}, {"count", model->rowCount()}};
}

inline QJsonObject placesPageObservation(QQuickItem* root) {
    const auto source = placesComponent(root);
    auto search = placesNamedObject(root, "search"), tabs = placesNamedObject(root, "tabs");
    auto timer = placesNamedObject(root, "commandInterval"), dialog = placesNamedObject(root, "bookmarkDialog");
    auto draft = placesNamedObject(root, "bookmarkName");
    if (source.isEmpty() || !search || !tabs || !timer || !dialog || !draft
            || root->property("loading").userType() != QMetaType::Bool
            || root->property("currentAddress").userType() != QMetaType::QString
            || search->property("text").userType() != QMetaType::QString
            || tabs->property("currentIndex").userType() != QMetaType::Int
            || tabs->property("currentIndex").toInt() < 0 || tabs->property("currentIndex").toInt() > 2
            || timer->property("running").userType() != QMetaType::Bool
            || dialog->objectName() != "bookmarkDialog" || !dialog->inherits("QQuickDialog")
            || dialog->property("visible").userType() != QMetaType::Bool
            || dialog->property("originalName").userType() != QMetaType::QString
            || dialog->property("address").userType() != QMetaType::QString
            || draft->property("text").userType() != QMetaType::QString) { return {}; }
    const auto commands = placesVariant(root->property("pendingCommands"));
    const auto ratings = placesVariant(root->property("maturityFilter"));
    if (commands.userType() != QMetaType::QVariantList || commands.toList().size() > 64
            || ratings.userType() != QMetaType::QVariantList || ratings.toList().size() > 5) { return {}; }
    QJsonArray maturity;
    for (const auto& value : ratings.toList()) {
        if (value.userType() != QMetaType::QString || maturity.contains(value.toString())
                || !QStringList{"everyone", "teen", "mature", "adult", "unrated"}.contains(value.toString())) { return {}; }
        maturity.append(value.toString());
    }
    const auto directory = placesModel(root, "placesModel", {"placeName", "placeAddress", "placeId"});
    const auto bookmarks = placesModel(root, "bookmarksModel", {"bookmarkName", "bookmarkAddress"});
    const auto servers = placesModel(root, "serversModel", {"serverUrl", "serverIndex", "fetched", "pinned", "failed"});
    const auto query = search->property("text").toString(), text = draft->property("text").toString();
    if (directory.isEmpty() || bookmarks.isEmpty() || servers.isEmpty() || query.size() > 8192 || text.size() > 8192) { return {}; }
    const auto rootId=placesRootInstance(root);if (rootId.isEmpty()) { return {}; }
    return {{"profile", "pico-places-v1"}, {"rootInstance", rootId}, {"componentSourceSha256", placesHash(source)},
        {"tab", tabs->property("currentIndex").toInt()}, {"loading", root->property("loading").toBool()},
        {"querySha256", placesHash(query)}, {"queryLength", query.size()},
        {"currentAddressSha256", placesHash(root->property("currentAddress").toString())},
        {"directory", directory}, {"bookmarks", bookmarks}, {"servers", servers}, {"maturity", maturity},
        {"queueCount", commands.toList().size()}, {"dispatchTimerRunning", timer->property("running").toBool()},
        {"dialog", QJsonObject{{"visible", dialog->property("visible").toBool()},
            {"originalNameSha256", placesHash(dialog->property("originalName").toString())},
            {"addressSha256", placesHash(dialog->property("address").toString())},
            {"draftSha256", placesHash(text)}, {"draftLength", text.size()}}}};
}

inline QString placesControlId(QQuickItem* item) {
    if (!loginGuiItem(item)) { return {}; }
    const auto root = placesRoot(item);
    if (!root) {
        return item->metaObject()->indexOfSignal("clicked()") >= 0 && item->property("text").toString() == "PLACES"
            ? QStringLiteral("places.entry") : QString();
    }
    if (root == item) { return "places.page"; }
    const QHash<QString, QString> fixed{{"refreshPlaces", "places.refresh"}, {"placesSearch", "places.search"},
        {"placesTab", "places.tab.0"}, {"bookmarksTab", "places.tab.1"}, {"serversTab", "places.tab.2"},
        {"maturityFilters", "places.ratings"}, {"addBookmark", "places.bookmark.add"},
        {"bookmarkName", "places.bookmark.name"}, {"saveBookmark", "places.bookmark.save"},
        {"newServerUrl", "places.server.url"}, {"addServer", "places.server.add"}};
    const auto name = item->objectName();
    if (fixed.contains(name)) { return fixed.value(name); }
    if (QRegularExpression("\\Arating_(everyone|teen|mature|adult|unrated)\\z").match(name).hasMatch()) {
        return "places.rating." + name.mid(7);
    }
    const auto context = qmlContext(item);
    if (context && item->metaObject()->indexOfSignal("clicked()") >= 0) {
        if (name == "visitPlace" && context->contextProperty("placeName").userType() == QMetaType::QString) {
            return "places.visit." + placesHash(context->contextProperty("placeName").toString());
        }
        if (QStringList{"visitBookmark", "renameBookmark", "deleteBookmark"}.contains(name)
                && context->contextProperty("bookmarkName").userType() == QMetaType::QString) {
            return "places.bookmark." + (name == "visitBookmark" ? QString("visit.")
                : name == "renameBookmark" ? QString("rename.") : QString("delete."))
                + placesHash(context->contextProperty("bookmarkName").toString());
        }
        if (name == "fetchServer" || name == "pinServer") {
            const auto url = context->contextProperty("serverUrl");
            if (url.userType() == QMetaType::QString) {
                return "places.server." + (name == "fetchServer" ? QString("fetch.") : QString("pin.")) + placesHash(url.toString());
            }
        }
        // The original anonymous Cancel button is identified by its attached
        // RejectRole inside the actual bookmark dialog's footer, not its text.
        auto dialog = placesNamedObject(root, "bookmarkDialog");
        auto footer = dialog ? placesObject(dialog->property("footer")) : nullptr;
        QVariant role;int contextDepth {0};
        for (auto lexical = qmlContext(root); lexical && ++contextDepth <= 128; lexical = lexical->parentContext()) {
            if (lexical->nameForObject(root) == "root" && lexical->baseUrl().toString() == placesComponent(root)) {
                // Resolve the attached Controls 2 type in the original page's
                // import context, not an inherited style's private context.
                role = QQmlProperty(item, "DialogButtonBox.buttonRole", lexical).read();break;
            }
        }
        int depth {0};bool roleOkay {false};const auto buttonRole = role.toInt(&roleOkay);
        for (auto owner = item->parent(); footer && owner && ++depth <= 128; owner = owner->parent()) {
            if (owner == footer && roleOkay && role.userType() != QMetaType::Bool && buttonRole == 1) { return "places.bookmark.cancel"; }
        }
    }
    if (item->inherits("QQuickScrollBar") && item->property("orientation").toInt() == Qt::Vertical) {
        for (auto owner = item->parentItem(); owner && owner != root; owner = owner->parentItem()) {
            if (loginQmlId(owner, "placesList")) { return "places.scroll.directory"; }
            if (loginQmlId(owner, "bookmarksList")) { return "places.scroll.bookmarks"; }
            if (loginQmlId(owner, "serversList")) { return "places.scroll.servers"; }
        }
    }
    return {};
}

inline bool placesField(const QString& id) {
    return id == "places.search" || id == "places.bookmark.name" || id == "places.server.url";
}
inline bool placesText(const QString& text) {
    if (text.size() > 4096) { return false; }
    for (const auto c : text) { if (c.unicode() < 32 || c.unicode() > 126) { return false; } }
    return true;
}

inline void appendPlacesObservation(QJsonObject& row, QQuickItem* item, const QString& id) {
    if (!loginGuiItem(item)) { return; }
    auto root = placesRoot(item);
    if (!root) { row["inputReady"] = id == "places.entry" && item->isEnabled();return; }
    const auto page = placesPageObservation(root);
    if (page.isEmpty()) { row["inputReady"] = false;return; }
    const auto dialog = page.value("dialog").toObject();
    const bool inDialog = id == "places.bookmark.name" || id == "places.bookmark.save" || id == "places.bookmark.cancel";
    bool ready = root->isVisible() && item->isEnabled() && !page.value("loading").toBool()
        && page.value("queueCount").toInt() == 0 && !page.value("dispatchTimerRunning").toBool()
        && dialog.value("visible").toBool() == inDialog;
    if (id == "places.page") {
        for (auto i = page.begin(); i != page.end(); ++i) { row[i.key()] = i.value(); }ready = false;
    } else if (placesField(id)) {
        const auto text = item->property("text"), readOnly = item->property("readOnly");
        if (text.userType() != QMetaType::QString || text.toString().size() > 8192 || readOnly.userType() != QMetaType::Bool) { ready = false; }
        else { row["textSha256"] = placesHash(text.toString());row["textLength"] = text.toString().size();ready = ready && !readOnly.toBool(); }
    } else if (id.startsWith("places.visit.") || id.startsWith("places.bookmark.visit.")
            || id.startsWith("places.bookmark.rename.") || id.startsWith("places.bookmark.delete.")) {
        const auto context = qmlContext(item);const bool directory = id.startsWith("places.visit.");
        const auto field = directory ? QString("placeAddress") : QString("bookmarkAddress");
        const auto address = context ? context->contextProperty(field) : QVariant();
        if (address.userType() != QMetaType::QString || address.toString().size() > 8192) { ready = false; }
        else { row["addressSha256"] = placesHash(address.toString()); }
    } else if (id.startsWith("places.rating.") || id.startsWith("places.server.fetch.") || id.startsWith("places.server.pin.")) {
        if (item->property("checked").userType() != QMetaType::Bool) { ready = false; }
        else { row["checked"] = item->property("checked").toBool(); }
    } else if (id.startsWith("places.scroll.")) {
        bool pOkay {false}, sOkay {false};
        const auto p = item->property("position").toDouble(&pOkay), s = item->property("size").toDouble(&sOkay);
        if (!pOkay || !sOkay || !std::isfinite(p) || !std::isfinite(s) || p < 0 || s <= 0 || p + s > 1.000001) { ready = false; }
        else { row["position"] = p;row["size"] = s;ready = ready && s < 1; }
    }
    row["inputReady"] = ready;
}

inline QString placesControlSource(QQuickItem* item, const QString& id) {
    QJsonObject value;appendPlacesObservation(value, item, id);
    const auto root = placesRoot(item);
    if (root) {
        const auto page = placesPageObservation(root);
        if (page.isEmpty()) { return {}; }value["page"] = page;
    }
    if (item && item->window()) {
        const auto rect = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width()) || !std::isfinite(rect.height())) { return {}; }
        value["sceneX"] = rect.x();value["sceneY"] = rect.y();value["width"] = rect.width();value["height"] = rect.height();
    }
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}

inline bool placesScrollPoint(QQuickItem* item, const QString& direction, QPointF& point) {
    if (!placesControlId(item).startsWith("places.scroll.") || (direction != "up" && direction != "down")) { return false; }
    auto thumb = qobject_cast<QQuickItem*>(placesObject(item->property("contentItem")));
    if (!thumb || thumb->parentItem() != item || !thumb->isVisible() || !item->isEnabled()) { return false; }
    const auto rect = thumb->mapRectToItem(item, QRectF(0, 0, thumb->width(), thumb->height()));
    if (!std::isfinite(rect.top()) || !std::isfinite(rect.bottom()) || rect.top() < 0 || rect.bottom() > item->height()) { return false; }
    const auto low = direction == "up" ? 0 : rect.bottom(), high = direction == "up" ? rect.top() : item->height();
    if (high - low < 2) { return false; }
    point = item->mapToScene(QPointF(item->width() / 2, (low + high) / 2));
    return std::isfinite(point.x()) && std::isfinite(point.y());
}
}
#endif
