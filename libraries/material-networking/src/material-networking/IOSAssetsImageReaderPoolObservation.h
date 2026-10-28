// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QRunnable>
#include <QString>
#include <QVariantMap>
namespace overte::e2e {
class IOSAssetsImageReaderPoolObservation final {
public:
    // The sole arm attempt occurs before WebView/Application setup and only
    // for actual --testScript arguments in the dedicated native test build.
    static void bootstrap(int argc,const char* const* argv) noexcept;
    static quint64 registration(QRunnable* actual,const QString& allocation,const QString& source1,
        const QString& task,const QString& resource) noexcept;
    static void retiring(quint64 registration) noexcept;
    static QVariantMap snapshot() noexcept;
    static void disarm() noexcept;
};
} // namespace overte::e2e
#endif
