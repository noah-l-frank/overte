// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QObject>
#include <QPointer>
#include <QString>
#include <QVariantMap>

namespace overte::e2e {
// Separate optional source. Existing ImageReader Source1/History5 wires do not change.
class IOSAssetsImageReaderQueueObservation {
public:
    struct Context {
        QString ownerInstance, taskId, dispatchId, receiverId, resourceId;
        QPointer<QObject> receiver;
    };
    // Prepare on the original main-thread ImageReader construction path, after
    // Source1's mutex has been released. No existing SDK is modified here.
    static void prepare() noexcept;
    static void disarm() noexcept;
    static QVariantMap snapshot() noexcept;
    class Binding {
    public:
        Binding() = default;
        void begin(const Context &, QObject *) noexcept;
        void returned(bool accepted) noexcept;
        ~Binding() noexcept;
        Binding(const Binding &) = delete;
        Binding &operator=(const Binding &) = delete;
    private:
        quint64 _row { 0 }, _qtScope { 0 };
        bool _returned { false };
    };
    class Receiver {
    public:
        Receiver() = default;
        void begin(const Context &) noexcept;
        ~Receiver() noexcept;
        Receiver(const Receiver &) = delete;
        Receiver &operator=(const Receiver &) = delete;
    private:
        quint64 _row { 0 };
        int _exceptions { 0 };
    };
};
}
#endif
