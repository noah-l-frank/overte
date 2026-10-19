// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QQuickItem>
#include <QVariant>
#include <QStringList>
#include <functional>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QQmlContext>
#include <QQmlEngine>
#endif

namespace overte::e2e {
inline bool loginQmlId(QQuickItem* item,const QString& id) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->nameForObject(item)==id) { return true; }
    }
#else
    Q_UNUSED(item) Q_UNUSED(id)
#endif
    return false;
}

// IDs belong to the actual reviewed QML component context, including inherited
// Controls contexts. Ambiguous/missing trees are unavailable, never fabricated.
inline QQuickItem* uniqueLoginItem(QQuickItem* root,const QStringList& ids) {
    QQuickItem* found {nullptr};bool invalid {false};int count {0};
    std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
        if (!item || invalid) { return; }
        if (++count>4096 || depth>128) { invalid=true;return; }
        for (const auto& id:ids) {
            if (loginQmlId(item,id)) {
                if (found && found!=item) { invalid=true;return; }
                found=item;
            }
        }
        for (auto child:item->childItems()) { walk(child,depth+1); }
    };
    walk(root,0);return invalid ? nullptr : found;
}

inline QQuickItem* genericLoginRoot(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && !defined(ANDROID_APP_PHONE_INTERFACE)
    int depth {0};
    for (auto node=item;node && ++depth<=128;node=node->parentItem()) {
        if (node->objectName()=="LoginDialog"
                && node->property("isTablet").userType()==QMetaType::Bool
                && node->property("isOverlay").userType()==QMetaType::Bool) { return node; }
    }
#else
    Q_UNUSED(item)
#endif
    return nullptr;
}

inline QString genericLoginStage(QQuickItem* root) {
    auto body=uniqueLoginItem(root,{"linkAccountBody","loggingInBody"});
    if (!body) { return "unavailable"; }
    for (const auto& key:{"linkSteam","linkOculus","withSteam","withOculus"}) {
        if (body->property(key).userType()!=QMetaType::Bool || body->property(key).toBool()) { return "unavailable"; }
    }
    if (body->property("isLoggingInToDomain").userType()!=QMetaType::Bool) { return "unavailable"; }
    if (loginQmlId(body,"linkAccountBody")) { return "credentials"; }
    auto spinner=uniqueLoginItem(body,{"loggingInSpinner"});
    if (!spinner) { return "unavailable"; }
    return spinner->isVisible() ? "pending" : "completion";
}

inline QString genericLoginError(QQuickItem* root) {
    const auto stage=genericLoginStage(root);
    if (stage=="pending" || stage=="completion") { return "none"; }
    if (stage!="credentials") { return "unavailable"; }
    auto label=uniqueLoginItem(root,{"loginErrorMessage"});
    if (!label || label->property("text").userType()!=QMetaType::QString) { return "unavailable"; }
    const auto text=label->property("text").toString();
    if (!label->isVisible() || text.isEmpty()) { return "none"; }
    return text=="Username or password is incorrect." ? "invalid-credentials" : "other";
}

inline QString genericSubmissionText(QQuickItem* root) {
    auto field=uniqueLoginItem(root,{"metaverseServerField"});
    return field && field->property("text").userType()==QMetaType::QString
        ? field->property("text").toString() : QString();
}

inline QString loginEndpointDigest(const QString& text) {
    return QString::fromLatin1(QCryptographicHash::hash(text.toUtf8(),QCryptographicHash::Sha256).toHex());
}

inline QString genericLoginControlId(QQuickItem* item) {
    auto root=genericLoginRoot(item);
    if (!root) { return {}; }
    if (root==item) { return "login.page"; }
    if (genericLoginStage(root)!="credentials") { return {}; }
    if (loginQmlId(item,"emailField")) { return "login.username"; }
    if (loginQmlId(item,"passwordField") && item->property("echoMode").toInt()==2) { return "login.password"; }
    if (loginQmlId(item,"metaverseServerField")) { return "login.server"; }
    if (item->metaObject()->indexOfSignal("clicked()")>=0) {
        if (loginQmlId(item,"loginButton")) { return "login.submit"; }
        if (loginQmlId(item,"dismissButton")) { return "login.cancel"; }
    }
    return {};
}
} // namespace overte::e2e
