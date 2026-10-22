// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <DependencyManager.h>
#include <SettingManager.h>
#include <MetaverseAPI.h>
#include <udt/PacketHeaders.h>
#include <QCryptographicHash>
#include <QDataStream>
#include <QCoreApplication>
#include <QThread>
#include <QVariantMap>

namespace overte::e2e {
// Actual loaded presence, Qt type and value. No default coercion, setting write,
// settings-file timestamp or claim about disk persistence.
inline QVariantMap placesPreferenceObservation() {
    if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !DependencyManager::isSet<Setting::Manager>()) { return {}; }
    const auto manager=DependencyManager::get<Setting::Manager>();
    QVariantMap settings;bool valid {true};
    manager->withReadLock([&] {
        for (const auto& name:QStringList{"placesAppPinnedMetaverse","placesAppMetaverseToFetch","placesAppMaturityFilter"}) {
            const bool present=manager->contains(name);const auto original=manager->value(name);
            QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream<<present<<original;
            if (stream.status()!=QDataStream::Ok || bytes.size()>65536) { valid=false;return; }
            QString kind="unsupported";QVariantList entries;QVariant value;
            if (!present) { kind="absent"; }
            else if (!original.isValid() || original.isNull()) { kind="null"; }
            else if (original.userType()==QMetaType::QVariantList) { kind="list";entries=original.toList(); }
            else if (original.userType()==QMetaType::QStringList) {
                kind="string-list";for (const auto& entry:original.toStringList()) { entries.append(entry); }
            }
            bool strings=entries.size()<=1024;
            for (const auto& entry:entries) { if (entry.userType()!=QMetaType::QString || entry.toString().size()>4096) { strings=false;break; } }
            if ((kind=="list" || kind=="string-list") && strings) { value=entries; }
            else if (kind=="list" || kind=="string-list") { kind="unsupported"; }
            settings.insert(name,QVariantMap {{"present",present},{"kind",kind},{"value",value},
                {"valueSha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}});
        }
    });
    if (!valid) { return {}; }
    return {{"placesPreferenceVersion",1},{"values",settings},
        {"metaverseOrigin",MetaverseAPI::getCurrentMetaverseServerURL().toString(QUrl::FullyEncoded)},
        {"protocolSignature",protocolVersionsSignatureBase64()}};
}
} // namespace overte::e2e
#endif
