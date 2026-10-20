// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive E2E-only process existence query. Signal zero never sends a signal.
#include <QRegularExpression>
#include <QStringList>
#include <QVariantMap>
#include <cmath>
#if defined(Q_OS_UNIX)
#include <cerrno>
#include <csignal>
// Version 1 is the Linux/Android and Darwin/iOS errno ABI.
static_assert(ESRCH == 3 && EPERM == 1 && EACCES == 13, "Unsupported process-presence errno ABI");
#endif

namespace overte::e2e {
class ProcessPresence {
public:
    static bool integer(const QVariant& value, double low, double high) {
        const auto type = value.userType();
        if (type != QMetaType::Int && type != QMetaType::UInt && type != QMetaType::LongLong
                && type != QMetaType::ULongLong && type != QMetaType::Double) { return false; }
        const auto number = value.toDouble();
        return std::isfinite(number) && number >= low && number <= high && std::floor(number) == number;
    }
    static bool command(const QVariantMap& value) {
        QStringList fields{"schemaVersion", "commandId", "action", "queryProcessId"}; fields.sort();
        const auto id = value.value("commandId");
        return value.keys() == fields && integer(value.value("schemaVersion"), 1, 1)
            && value.value("action") == QVariant(QStringLiteral("feature-process-presence"))
            && id.userType() == QMetaType::QString
            && QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id.toString()).hasMatch()
            && integer(value.value("queryProcessId"), 1, 2147483647);
    }
    static QVariantMap observe(int pid) {
#if defined(Q_OS_UNIX)
        if (pid <= 0) { return {}; }
        const int saved = errno;
        errno = 0;
        const int result = ::kill(pid, 0);
        const int error = result == 0 ? 0 : errno;
        errno = saved;
        if ((result != 0 && result != -1) || (result == -1 && error <= 0)) { return {}; }
        const QString symbol = result == 0 ? "NONE" : error == ESRCH ? "ESRCH"
            : error == EPERM ? "EPERM" : error == EACCES ? "EACCES" : "OTHER";
        return {{"presence", result == 0 ? "present" : error == ESRCH ? "absent" : "unknown"},
            {"nativeResult", result}, {"nativeError", error}, {"errorSymbol", symbol}};
#else
        Q_UNUSED(pid)
        return {}; // An unavailable platform is never an absent process.
#endif
    }
};
} // namespace overte::e2e
