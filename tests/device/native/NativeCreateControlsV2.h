// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalLoginControls.h"
#include <QCryptographicHash>
#include <QJsonDocument>

namespace overte::e2e {
// Source-role admission is deliberately separate from Script bundle admission.
inline QQuickItem* createFileBrowser(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    if (!audioGuiItem(item) || !QCoreApplication::arguments().contains("--testScript")) { return nullptr; }
    for (auto root=item;root;root=root->parentItem()) {
        if (root->objectName()!="nativeFileBrowser") { continue; }
        bool source=false;
        int depth=0;
        for (auto context=qmlContext(root);context && ++depth<=128;context=context->parentContext()) {
            const auto url=context->baseUrl();
            if (context->nameForObject(root)=="root" && (url.scheme()=="file" || url.scheme()=="qrc")
                    && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                    && url.path().endsWith("/dialogs/NativeFileBrowser.qml")) { source=true;break; }
        }
        const auto caption=root->property("caption"),filter=root->property("filter"),save=root->property("saveDialog");
        if (!source || caption.userType()!=QMetaType::QString || filter.userType()!=QMetaType::QString
                || save.userType()!=QMetaType::Bool || filter.toString()!="*.json"
                || root->property("bundleMode").userType()!=QMetaType::Bool || root->property("bundleMode").toBool()
                || root->property("selectDirectory").userType()!=QMetaType::Bool || root->property("selectDirectory").toBool()
                || root->property("multiSelect").userType()!=QMetaType::Bool || root->property("multiSelect").toBool()
                || !root->property("primaryFilter").toString().isEmpty()) { return nullptr; }
        if ((!save.toBool() && caption.toString()=="Select .json to Import")
                || (save.toBool() && caption.toString()=="Select Where to Save")) { return root; }
        return nullptr;
    }
#else
    Q_UNUSED(item)
#endif
    return nullptr;
}

inline QString createFileRole(QQuickItem* root) {
    return createFileBrowser(root) ? (root->property("saveDialog").toBool() ? "export" : "import") : QString();
}

inline QJsonObject createFileObservation(QQuickItem* root) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    const auto role=createFileRole(root);if (role.isEmpty()) { return {}; }
    QString source;
    for (auto context=qmlContext(root);context;context=context->parentContext()) {
        if (context->nameForObject(root)=="root" && context->baseUrl().path().endsWith("/dialogs/NativeFileBrowser.qml")) {
            source=context->baseUrl().toString();break;
        }
    }
    auto id=root->property("_overteE2ECreateRootId").toString();
    if (id.isEmpty()) {
        // Instrumentation-only identity; no user selection, dialog or entity
        // property is written. Identity lives exactly as long as this QObject.
        id=QUuid::createUuid().toString(QUuid::WithoutBraces);
        root->setProperty("_overteE2ECreateRootId",id);
    }
    return {{"role",role},{"rootId",id},{"componentSource",source},{"caption",root->property("caption").toString()},
        {"filter",root->property("filter").toString()},{"saveDialog",root->property("saveDialog").toBool()},
        {"bundleMode",root->property("bundleMode").toBool()},{"selectDirectory",root->property("selectDirectory").toBool()},
        {"directory",root->property("dir").toUrl().toString()},{"closing",root->property("closing").toBool()},
        {"requestId",root->property("requestId").toString()},{"error",root->property("error").toString()}};
#else
    Q_UNUSED(root);return {};
#endif
}

inline QString createExtraControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto root=createFileBrowser(item);
    if (!root) { return {}; }
    const auto prefix="create."+createFileRole(root)+'.',name=item->objectName();
    if (item->inherits("QQuickTextInput") && !item->property("readOnly").toBool()) {
        if (name=="fileNameInput") { return prefix+"filename"; }
        if (name=="fileFolderPath") { return prefix+"folder"; }
    }
    if (item->metaObject()->indexOfSignal("clicked()")>=0) {
        if (name=="fileCancel") { return prefix+"cancel"; }
        if (name=="fileAccept") { return prefix+"accept"; }
    }
    return {};
}

inline int createExtraChoiceCount(const QString& id) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    if (id=="create.voxel.shape") { return 3; }
    if (id=="create.voxel.mode" || id=="create.voxel.dynamics" || id=="create.voxel.pointer") { return 2; }
#else
    Q_UNUSED(id)
#endif
    return 0;
}
inline bool createExtraField(const QString& id) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
    return id=="create.voxel.diameter" || id=="create.voxel.reach"
        || id=="create.import.folder" || id=="create.import.filename"
        || id=="create.export.folder" || id=="create.export.filename";
#else
    Q_UNUSED(id);return false;
#endif
}
} // namespace overte::e2e
