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
    return {{"accountPreferenceVersion",1},{"present",present},{"valueType",kind},
        {"valueSha256",readable ? QJsonValue(digest(text)) : QJsonValue(QJsonValue::Null)},
        {"canonicalOrigin",readable && accountOriginText(text)},
        {"processOverridePresent",overridePresent},
        {"processOverrideSha256",overridePresent ? QJsonValue(digest(overrideValue)) : QJsonValue(QJsonValue::Null)},
        {"processOverrideCanonical",overridePresent && accountOriginText(overrideValue)}};
#else
    return {};
#endif
}
} // namespace overte::e2e
