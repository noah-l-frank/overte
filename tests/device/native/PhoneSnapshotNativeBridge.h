// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <functional>
#include <QCoreApplication>
#include <QThread>
#include <QVariant>
namespace overte::e2e {
struct PhoneSnapshotNativeProvider {
    std::function<QString()> exportObservation;
    std::function<QString(const QString&)> readbackCommand;
    explicit operator bool() const { return bool(exportObservation) && bool(readbackCommand); }
};
inline const char* phoneSnapshotNativeProviderProperty() { return "_overteE2EPhoneSnapshotNativeProviderV1"; }
}
Q_DECLARE_METATYPE(overte::e2e::PhoneSnapshotNativeProvider)
namespace overte::e2e {
inline PhoneSnapshotNativeProvider phoneSnapshotNativeProvider() {
    auto* app=QCoreApplication::instance();
    if (!app || QThread::currentThread()!=app->thread() || !app->arguments().contains("--testScript")) { return {}; }
    const auto original=app->property(phoneSnapshotNativeProviderProperty());
    if (original.userType()!=qMetaTypeId<PhoneSnapshotNativeProvider>()) { return {}; }
    const auto provider=original.value<PhoneSnapshotNativeProvider>();
    return provider ? provider : PhoneSnapshotNativeProvider();
}
// Preserve original JNI QString code units and unavailable/invalid responses.
// The core caller retains its original command, JSON and clock validation.
inline QString phoneSnapshotExportObservation() {
    const auto provider=phoneSnapshotNativeProvider();
    return provider ? provider.exportObservation() : QString();
}
inline QString phoneSnapshotReadbackCommand(const QString& command) {
    const auto provider=phoneSnapshotNativeProvider();
    return provider ? provider.readbackCommand(command) : QString();
}
}
#endif
