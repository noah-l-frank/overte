// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Source-owned IDs for normal Qt controls. This helper cannot load/stop a
// script, invoke a QML handler or choose a desired script-service observation.
#include <QJsonObject>
#include <QQuickItem>
#include <QRegularExpression>
#include <QUrl>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#endif

namespace overte::e2e {

inline QString scriptRowLabel(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto match = QRegularExpression("\\Ascript(?:Restart|Stop)([0-9]{1,3})\\z").match(item->objectName());
    if (!match.hasMatch() || match.captured(1).toInt() > 127 || !item->parentItem()) { return {}; }
    const auto index = match.captured(1);
    const auto siblings = item->parentItem()->childItems();
    for (int pos = 2; pos < siblings.size(); ++pos) {
        const auto stop = siblings[pos];
        const auto restart = siblings[pos - 1];
        const auto label = siblings[pos - 2];
        if (stop->objectName() == "scriptStop" + index && restart->objectName() == "scriptRestart" + index
                && (stop == item || restart == item) && label->inherits("QQuickText")
                && stop->metaObject()->indexOfSignal("clicked()") >= 0
                && restart->metaObject()->indexOfSignal("clicked()") >= 0) {
            const auto text = label->property("text");
            return text.userType() == QMetaType::QString && text.toString().size() <= 4096 ? text.toString() : QString();
        }
    }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline bool scriptUrlDialog(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (parent->property("title").toString() == QStringLiteral("Open and Run Script")
                && parent->property("label").toString() == QStringLiteral("Script URL")) { return true; }
    }
#else
    Q_UNUSED(item)
#endif
    return false;
}

inline QString scriptRowSource(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (scriptRowLabel(item).isEmpty()) { return {}; }
    const auto context = qmlContext(item);
    if (!context) { return {}; }
    auto value = context->contextProperty(QStringLiteral("modelData"));
    if (value.userType() == qMetaTypeId<QJSValue>()) { value = value.value<QJSValue>().toVariant(); }
    if (value.userType() != QMetaType::QVariantMap) { return {}; }
    const auto row = value.toMap();
    const auto url = row.value("url");
    const auto path = row.value("path");
    if (url.userType() != QMetaType::QString || path.userType() != QMetaType::QString) { return {}; }
    const auto source = url.toString().isEmpty() ? path.toString() : url.toString();
    return source.size() <= 4096 ? source : QString();
#else
    Q_UNUSED(item)
    return {};
#endif
}

inline QString scriptControlId(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto name = item->objectName();
    if (name == "scriptFromUrl") { return QStringLiteral("scripts.from-url"); }
    if (name == "runningScriptList") { return QStringLiteral("scripts.list"); }
    const auto row = QRegularExpression("\\Ascript(Restart|Stop)(0|[1-9][0-9]{0,2})\\z").match(name);
    if (row.hasMatch() && row.captured(2).toInt() <= 127 && !scriptRowSource(item).isEmpty()) {
        return "scripts." + row.captured(1).toLower() + "." + row.captured(2);
    }
    if (scriptUrlDialog(item)) {
        // Bind the actual editor, not both a custom TextField wrapper and its
        // child. A duplicate actual editor will invalidate the caller's tree.
        if (item->inherits("QQuickTextInput") && !item->property("readOnly").toBool()) {
            return QStringLiteral("scripts.url.field");
        }
        if (item->metaObject()->indexOfSignal("clicked()") >= 0) {
            const auto text = item->property("text").toString();
            if (text == "OK") { return QStringLiteral("scripts.url.submit"); }
            if (text == "Cancel") { return QStringLiteral("scripts.url.cancel"); }
        }
    }
    if (item->metaObject()->indexOfSignal("clicked()") >= 0) {
        const auto text = item->property("text").toString();
        if (text == "SCRIPTS") { return QStringLiteral("scripts.entry"); }
        if (text == "MENU") { return QStringLiteral("scripts.menu"); }
    }
    // The VR menu uses real TabletMenuItem delegates rather than Buttons.
    if (QString::fromLatin1(item->metaObject()->className()).startsWith("TabletMenuItem_QMLTYPE_")) {
        const auto text = item->property("text").toString();
        if (text == "Edit") { return QStringLiteral("scripts.menu-edit"); }
        if (text == "Running Scripts") { return QStringLiteral("scripts.menu-running"); }
    }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline void appendScriptControlObservation(QJsonObject& row, QQuickItem* item, const QString& id) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (id.startsWith("scripts.restart.") || id.startsWith("scripts.stop.")) {
        row["rowLabel"] = scriptRowLabel(item);
        row["sourceUrl"] = scriptRowSource(item);
    } else if (id == "scripts.url.field") {
        row["text"] = item->property("text").toString();
    }
#else
    Q_UNUSED(row)
    Q_UNUSED(item)
    Q_UNUSED(id)
#endif
}

inline bool validScriptUrlText(const QString& text) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const QUrl url(text);
    return text.size() <= 4096 && url.isValid() && (url.scheme() == "http" || url.scheme() == "https")
        && !url.host().isEmpty() && url.userInfo().isEmpty() && !url.hasQuery() && !url.hasFragment()
        && QRegularExpression("\\A(?:/script-management/[0-9a-f]{32}/(?:client|missing)\\.js|/feature-fixture/v1/runs/[0-9a-f]{32}/tickets/[0-9a-f]{32}/missing\\.js|/create/[0-9a-f]{32}/observer\\.js)\\z")
            .match(url.path()).hasMatch();
#else
    Q_UNUSED(text)
    return false;
#endif
}

} // namespace overte::e2e
