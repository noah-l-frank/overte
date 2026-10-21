// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Original read-only preference/process-origin facts. No setting mutation,
// account endpoint assignment, credential access or restoration setter.
#include <QCoreApplication>
#include <QThread>
#include <QCryptographicHash>
#include <QJsonObject>
#include <QJsonValue>
#include <QUrl>
#include <SettingHandle.h>
#include "PrivateAccountOrigin.h"
#include "NormalLoginControls.h"

namespace overte::e2e {
inline QJsonObject accountPreferenceObservation() {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!qApp || QThread::currentThread()!=qApp->thread()
            || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    Setting::Handle<QVariant> setting("private/selectedMetaverseURL");
    const auto value=setting.get();
    const bool present=setting.isSet();
    const auto kind=!present ? QStringLiteral("absent") : value.userType()==QMetaType::QString ? QStringLiteral("string")
        : value.userType()==QMetaType::QUrl ? QStringLiteral("url") : QStringLiteral("unsupported");
    QString text;
    if (kind=="string") { text=value.toString(); }
    else if (kind=="url") { text=QString::fromLatin1(value.toUrl().toEncoded()); }
    const auto digest=[](const QString& text) { return QString::fromLatin1(
        QCryptographicHash::hash(text.toUtf8(),QCryptographicHash::Sha256).toHex()); };
    const bool readable=kind=="string" || kind=="url";
    const bool overridePresent=qEnvironmentVariableIsSet("HIFI_METAVERSE_URL");
    const auto overrideValue=qEnvironmentVariable("HIFI_METAVERSE_URL");
    Setting::Handle<QVariant> rememberSetting("keepMeLoggedIn");
    const auto remember=rememberSetting.get();const bool rememberPresent=rememberSetting.isSet();
    Setting::Handle<QVariant> usernameSetting("keepMeLoggedIn/savedUsername");
    const auto username=usernameSetting.get();const bool usernamePresent=usernameSetting.isSet();
    const bool rememberReadable=rememberPresent && remember.userType()==QMetaType::Bool;
    const bool usernameReadable=usernamePresent && username.userType()==QMetaType::QString;
    return {{"accountPreferenceVersion",2},{"present",present},{"valueType",kind},
        {"rememberPresent",rememberPresent},{"rememberType",!rememberPresent ? "absent" : rememberReadable ? "bool" : "unsupported"},
        {"rememberValue",rememberReadable ? QJsonValue(remember.toBool()) : QJsonValue(QJsonValue::Null)},
        {"savedUsernamePresent",usernamePresent},{"savedUsernameType",!usernamePresent ? "absent" : usernameReadable ? "string" : "unsupported"},
        {"savedUsernameSha256",usernameReadable ? QJsonValue(digest(username.toString())) : QJsonValue(QJsonValue::Null)},
        {"valueSha256",readable ? QJsonValue(digest(text)) : QJsonValue(QJsonValue::Null)},
        {"canonicalOrigin",readable && accountOriginText(text)},
        {"processOverridePresent",overridePresent},
        {"processOverrideSha256",overridePresent ? QJsonValue(digest(overrideValue)) : QJsonValue(QJsonValue::Null)},
        {"processOverrideCanonical",overridePresent && accountOriginText(overrideValue)}};
#else
    return {};
#endif
}
inline QString accountPreferenceControlId(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto root=genericLoginRoot(item);
    if (root && genericLoginStage(root)=="credentials" && loginQmlId(item,"keepMeLoggedInCheckbox")
            && item->property("checked").userType()==QMetaType::Bool
            && item->metaObject()->indexOfSignal("clicked()")>=0) { return "account.remember"; }
#else
    Q_UNUSED(item)
#endif
    return {};
}
inline QJsonObject accountPreferenceControlObservation(QQuickItem* item,const LoginUiContext& context) {
    if (!context.valid || accountPreferenceControlId(item).isEmpty()) { return {}; }
    return {{"preferenceControlVersion",1},{"checked",item->property("checked").toBool()}};
}
inline QString accountPreferenceControlSource(QQuickItem* item,const LoginUiContext& context) {
    auto row=accountPreferenceControlObservation(item,context);
    auto root=genericLoginRoot(item);
    if (row.isEmpty() || !root) { return {}; }
    QJsonObject page;appendLoginControlObservation(page,root,"login.page",context);
    if (page.value("domain").toBool() || page.value("closing").toBool()) { return {}; }
    row["page"]=page;
    return QString::fromUtf8(QJsonDocument(row).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
