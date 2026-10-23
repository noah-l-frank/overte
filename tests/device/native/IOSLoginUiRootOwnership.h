// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive actual Login root operands from the original UI walk, never fields.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "GenericLoginControls.h"
#include "IOSScriptUiRootOwnership.h"
#include <PathUtils.h>
#include <QSet>
#include <QPair>

namespace overte::e2e::login_ui_roots {
inline script_ui_roots::Ledger& ledger() {
    static script_ui_roots::Ledger value(script_ui_roots::Profile::Login);return value;
}
inline QQuickItem* operand(QQuickItem* item) {return genericLoginRoot(item);}
inline QPair<QString,QString> component(QQuickItem* root) {
    if (!root || operand(root)!=root) {return {};}
    const bool tablet=root->property("isTablet").toBool(),overlay=root->property("isOverlay").toBool();
    if (tablet && overlay) {return {};}
    const QString kind=tablet ? "tablet" : overlay ? "overlay" : "dialog";
    const QString suffix=tablet ? "dialogs/TabletLoginDialog.qml" : overlay ? "OverlayLoginDialog.qml" : "LoginDialog.qml";
    int depth {0};
    for (auto context=qmlContext(root);context && ++depth<=128;context=context->parentContext()) {
        if (context->thread()==root->thread() && context->nameForObject(root)=="root"
                && context->baseUrl()==PathUtils::qmlUrl(suffix)) {
            return {kind,context->baseUrl().toString(QUrl::FullyEncoded)};
        }
    }
    return {};
}
class Inventory {
    bool _complete {true};
    QSet<QQuickItem*> _seen;
    QJsonArray _controls;
public:
    void visit(QQuickItem* item) {
        if (!script_ui_roots::enabled()) {return;}
        auto root=operand(item);if (!root || _seen.contains(root)) {return;}
        _seen.insert(root);const auto source=component(root);
        if (source.first.isEmpty() || ledger().observe(root,source.first,source.second).isEmpty()) {_complete=false;}
    }
    void control(QQuickItem* item,const QString& id,const QString& token) {
        if (!script_ui_roots::enabled() || !id.startsWith("login.") || id=="login.entry") {return;}
        auto root=operand(item);const auto source=component(root);
        if (!root || !_seen.contains(root) || source.first.isEmpty()) {_complete=false;return;}
        const auto identity=ledger().observe(root,source.first,source.second);
        if (identity.isEmpty() || _controls.size()>=16) {_complete=false;return;}
        _controls.append(QJsonObject{{"id",id},{"token",token},{"observedIdentity",identity}});
    }
    QJsonObject observation(bool wholeTreeReady) {
        if (!script_ui_roots::enabled()) {
            return {{"iosLoginUiRootsVersion",1},{"complete",false},{"ownership",QJsonObject{{"iosLoginUiRootOwnershipVersion",1},{"available",false}}},{"controls",QJsonArray()}};
        }
        const auto ownership=ledger().read(wholeTreeReady && _complete);
        const bool complete=wholeTreeReady && _complete && ownership.value("available").toBool() && ownership.value("complete").toBool();
        return {{"iosLoginUiRootsVersion",1},{"complete",complete},{"ownership",ownership},
            {"controls",complete ? _controls : QJsonArray()}};
    }
};
} // namespace overte::e2e::login_ui_roots
#endif
