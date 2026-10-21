// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCryptographicHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickItem>
#include <QThread>
#include <QCoreApplication>
namespace overte::e2e {
inline QJsonObject navigationAddressObservation(QQuickItem* item) {
    if (!item || !QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || item->thread()!=QCoreApplication::instance()->thread()) { return {}; }
    const auto original=item->property("text");
    if (original.userType()!=QMetaType::QString) { return {}; }
    const auto text=original.toString();
    return {{"textSha256",QString::fromLatin1(QCryptographicHash::hash(text.toUtf8(),QCryptographicHash::Sha256).toHex())},
        {"textLength",text.size()},{"inputReady",item->isEnabled() && item->hasActiveFocus() && text.size()<=2048}};
}
inline QString navigationAddressSource(QQuickItem* item) {
    const auto value=navigationAddressObservation(item);
    return value.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
}
#endif
