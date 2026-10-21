// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalLoginControls.h"
#include <QJSValue>
#include <Menu.h>

namespace overte::e2e {
struct AccountMenuUiContext {
    LoginUiContext login;
    QString principal, actionText;
    bool ready {false};
    static AccountMenuUiContext fromNative(const QVariantMap& account) {
        AccountMenuUiContext result;result.login=LoginUiContext::fromNative(account);
        if (!result.login.valid) { return result; }
        result.principal=account.value("principalSha256").toString();
        const auto native=account.value("observation").toMap();
        const auto menu=Menu::getInstance();
        const auto action=menu ? menu->getActionForOption(MenuOption::Login) : nullptr;
        if (action) { result.actionText=action->text(); }
        result.ready=result.login.valid && account.value("loggedIn").toBool()
            && native.value("credentialActive").toBool() && native.value("tokenPresent").toBool()
            && native.value("tokenValid").toBool() && !native.value("loginPending").toBool()
            && !native.value("refreshPending").toBool()
            && result.actionText.startsWith("Directory Service: Logout ")
            && loginEndpointDigest(result.actionText.mid(QStringLiteral("Directory Service: Logout ").size()))==result.principal;
        return result;
    }
};

inline QString accountMenuControlId(QQuickItem* item) {
    if (!loginGuiItem(item) || !QString::fromLatin1(item->metaObject()->className()).startsWith("TabletMenuItem_QMLTYPE_")) { return {}; }
    auto source=item->property("source").value<QObject*>();
    if (!source && item->property("source").userType()==qMetaTypeId<QJSValue>()) {
        source=item->property("source").value<QJSValue>().toQObject();
    }
    if (!source || source->thread()!=qApp->thread()) { return {}; }
    // Match the existing TabletMenuAdapter for Controls 1 and Controls 2.
    // An absent wrapper-only tabletVisible property is not observed false.
    const auto tabletVisible=source->property("tabletVisible");
    const auto visible=tabletVisible.isValid() ? tabletVisible : source->property("visible");
    if (visible.userType()!=QMetaType::Bool || !visible.toBool()
            || !source->property("enabled").toBool() || !item->property("platformEnabled").toBool()) { return {}; }
    const auto text=item->property("text").toString();
    if (source->property("type").toInt()==2 && text=="File" && source->property("title").toString()==text) { return "account-menu.file"; }
    if (source->property("type").toInt()==1 && text.startsWith("Directory Service: Logout ")
            && source->property("text").toString()==text) { return "account-menu.logout"; }
    return {};
}

inline void appendAccountMenuObservation(QJsonObject& row,QQuickItem* item,const QString& id,const AccountMenuUiContext& context) {
    row["accountInstance"]=context.login.instance;row["credentialGeneration"]=static_cast<double>(context.login.generation);
    row["endpointSha256"]=context.login.endpoint;row["principalSha256"]=context.principal;
    row["inputReady"]=context.ready && item && item->isEnabled() && accountMenuControlId(item)==id
        && (id!="account-menu.logout" || item->property("text").toString()==context.actionText);
}

inline QString accountMenuSource(QQuickItem* item,const QString& id,const AccountMenuUiContext& context) {
    QJsonObject value;appendAccountMenuObservation(value,item,id,context);
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
