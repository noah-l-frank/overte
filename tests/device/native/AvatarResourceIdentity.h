// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QUrl>
#include <QVariantMap>

namespace overte { namespace e2e {

// Only immutable, known APK resources may be opened. A configured URL or a
// loaded HFM URL is not a claim about delivered bytes. Never fetch URLs here.
inline QVariant avatarBundledResource(const QUrl& actual, const QString& allowed) {
    if (!actual.isValid() || actual.scheme() != "qrc" || !actual.authority().isEmpty()
            || actual.hasQuery() || actual.hasFragment()
            || QDir::cleanPath(actual.path()) != "/" + allowed) { return {}; }
    QFile file(":" + QDir::cleanPath(actual.path()));
    constexpr qint64 MAX_BYTES = 4 * 1024 * 1024;
    if (!file.open(QIODevice::ReadOnly) || file.size() < 1 || file.size() > MAX_BYTES) { return {}; }
    const auto size = file.size();
    const auto bytes = file.read(MAX_BYTES + 1);
    if (file.error() != QFile::NoError || bytes.size() != size || !file.atEnd()) { return {}; }
    return QVariantMap{{"resourcePath",allowed},{"bytes",size},
        {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}};
}

inline QVariantMap avatarUrlSource(const QString& actual, const QString& allowed) {
    // Preserve the exact loaded HFM string before parsing for resource lookup.
    const auto text = actual.toUtf8();
    return {{"present",!text.isEmpty()},
        {"urlSha256",QString::fromLatin1(QCryptographicHash::hash(text,QCryptographicHash::Sha256).toHex())},
        {"bundledResource",avatarBundledResource(QUrl(actual),allowed)}};
}
inline QVariantMap avatarUrlSource(const QUrl& actual, const QString& allowed) {
    // Configured skeleton URL is itself a QUrl; measure that API representation.
    return avatarUrlSource(actual.toString(),allowed);
}
} }
#endif
