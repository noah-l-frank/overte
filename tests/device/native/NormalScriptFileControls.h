// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// E2E-only identities/observations for the existing Script file-bundle picker.
// This helper never calls a file helper, sets a model/selection, loads a script
// or emits the browser's selectedFile/selectedBundle signals.
#include <QJsonObject>
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QQuickItem>
#include <QRegularExpression>
#include <QUrl>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QQmlContext>
#include <QQmlEngine>
#include <QJSValue>
#endif

namespace overte::e2e {
inline QQuickItem* scriptFileBrowser(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!QCoreApplication::arguments().contains("--testScript")) { return nullptr; }
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (parent->objectName() == QStringLiteral("nativeFileBrowser")
                && parent->property("caption").toString() == QStringLiteral("Open Script and Companion Files")
                && parent->property("bundleMode").toBool() && !parent->property("saveDialog").toBool()
                && !parent->property("selectDirectory").toBool()
                && parent->property("primaryFilter").toString() == QStringLiteral("\\.js$")) { return parent; }
    }
#else
    Q_UNUSED(item)
#endif
    return nullptr;
}

inline QUrl scriptFileRowUrl(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!scriptFileBrowser(item) || !QRegularExpression("\\AfileRow(0|[1-9][0-9]{0,3})\\z").match(item->objectName()).hasMatch()) { return {}; }
    const auto context = qmlContext(item);
    if (!context) { return {}; }
    auto value = context->contextProperty(QStringLiteral("fileUrl"));
    if (!value.isValid()) { value = context->contextProperty(QStringLiteral("fileURL")); }
    const auto url = value.toUrl();
    return url.isValid() && url.isLocalFile() && url.toString().size() <= 4096 ? url : QUrl();
#else
    Q_UNUSED(item)
    return {};
#endif
}

inline QString scriptFileControlId(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!item || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    const auto name = item->objectName();
    if (name == QStringLiteral("scriptFromFile") && item->metaObject()->indexOfSignal("clicked()") >= 0) {
        return QStringLiteral("scripts.from-file");
    }
    if (!scriptFileBrowser(item)) { return {}; }
    if (item->inherits("QQuickTextInput") && !item->property("readOnly").toBool()) {
        if (name == QStringLiteral("fileFolderPath")) { return QStringLiteral("script-file.folder"); }
    }
    if (name == QStringLiteral("bundlePrimary")) { return QStringLiteral("script-file.primary"); }
    if (item->metaObject()->indexOfSignal("clicked()") < 0) { return {}; }
    const auto row = QRegularExpression("\\AfileRow(0|[1-9][0-9]{0,3})\\z").match(name);
    if (row.hasMatch() && !scriptFileRowUrl(item).isEmpty()) { return "script-file.row." + row.captured(1); }
    if (name == QStringLiteral("fileAccept")) { return QStringLiteral("script-file.select"); }
    if (name == QStringLiteral("fileCancel")) { return QStringLiteral("script-file.cancel"); }
    if (name == QStringLiteral("bundleBack")) { return QStringLiteral("script-file.change-selection"); }
    if (name == QStringLiteral("bundleConfirm")) { return QStringLiteral("script-file.confirm"); }
    if (name == QStringLiteral("bundleCancel")) { return QStringLiteral("script-file.review-cancel"); }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline bool validScriptFolderPath(const QString& text) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    return text.size() <= 4096
        && QRegularExpression("\\A/(?:[^/\\x00-\\x1f]+/)*feature-script-[0-9a-f]{32}(?:/script-bundle)?\\z").match(text).hasMatch()
        && !text.split('/').contains("..") && !text.split('/').contains(".");
#else
    Q_UNUSED(text)
    return false;
#endif
}

inline QString scriptFileControlSource(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto url = scriptFileRowUrl(item);
    if (!url.isEmpty()) { return url.toString(); }
    if (scriptFileControlId(item) == QStringLiteral("script-file.primary")) {
        // Retire a selector token when its actual model/current choice changes.
        // Keyboard selection still targets the original live ComboBox.
        auto bundle = scriptFileBrowser(item)->property("bundle");
        if (bundle.userType() == qMetaTypeId<QJSValue>()) { bundle = bundle.value<QJSValue>().toVariant(); }
        const auto document = bundle.toMap();
        QJsonArray urls, paths;
        for (const auto& url : document.value("urls").toList()) { urls.append(url.toUrl().toString()); }
        for (const auto& path : document.value("relativePaths").toList()) { paths.append(path.toString()); }
        return QString::fromUtf8(QJsonDocument(QJsonObject{{"root", document.value("root").toUrl().toString()},
            {"urls", urls}, {"paths", paths}, {"text", item->property("currentText").toString()},
            {"index", item->property("currentIndex").toInt()}}).toJson(QJsonDocument::Compact));
    }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline void appendScriptFileObservation(QJsonObject& row, QQuickItem* item, const QString& id) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    auto root = scriptFileBrowser(item);
    if (!root) { return; }
    if (id.startsWith(QStringLiteral("script-file.row."))) {
        row["sourceUrl"] = scriptFileRowUrl(item).toString();
        row["rowLabel"] = item->property("text").toString();
        row["selected"] = item->property("highlighted").toBool();
        const auto context = qmlContext(item);
        row["directory"] = context && context->contextProperty(QStringLiteral("fileIsDir")).toBool();
    } else if (id == QStringLiteral("script-file.folder")) {
        row["text"] = item->property("text").toString();
    } else if (id == QStringLiteral("script-file.primary")) {
        row["currentText"] = item->property("currentText").toString();
        row["currentIndex"] = item->property("currentIndex").toInt();
    }
    if (id == QStringLiteral("script-file.cancel") || id == QStringLiteral("script-file.folder") || id == QStringLiteral("script-file.review-cancel")
            || id == QStringLiteral("script-file.confirm")) {
        auto bundle = root->property("bundle");
        if (bundle.userType() == qMetaTypeId<QJSValue>()) { bundle = bundle.value<QJSValue>().toVariant(); }
        const auto document = bundle.toMap();
        QJsonObject picker{{"caption", root->property("caption").toString()},
            {"directory", root->property("dir").toUrl().toString()},
            {"review", !document.isEmpty()}, {"error", root->property("error").toString()}};
        picker["relativePaths"] = QJsonArray::fromVariantList(document.value("relativePaths").toList());
        picker["bundleRoot"] = document.value("root").toUrl().toString();
        QJsonArray urls;
        for (const auto& url : document.value("urls").toList()) { urls.append(url.toUrl().toString()); }
        picker["bundleUrls"] = urls;
        QJsonArray selected;
        auto chosen = root->property("chosen");
        if (chosen.userType() == qMetaTypeId<QJSValue>()) { chosen = chosen.value<QJSValue>().toVariant(); }
        for (const auto& url : chosen.toList()) { selected.append(url.toString()); }
        picker["selectedUrls"] = selected;
        row["picker"] = picker;
    }
#else
    Q_UNUSED(row)
    Q_UNUSED(item)
    Q_UNUSED(id)
#endif
}
} // namespace overte::e2e
