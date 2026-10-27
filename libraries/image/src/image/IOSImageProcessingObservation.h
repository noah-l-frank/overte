// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QIODevice>
#include <QString>
#include <QVariantMap>
#include <memory>

namespace image::e2e {
// Diagnostic metadata only. No product object/owner or raw URL/pointer escapes.
class IOSImageProcessingObservation final {
public:
    struct Task {
        QString source1Instance,taskId,resourceId;
        std::weak_ptr<void> marker;
        quint64 token{0};
    };
    static Task prepare(Task actual) noexcept; // Actual constructor/main thread only.
    static QVariantMap snapshot() noexcept;   // Metadata + weak owner reads only.
    static void disarm() noexcept;
    class Body;
    class Binding final {
    public:
        Binding(const Task& task,const std::shared_ptr<QIODevice>& actual) noexcept;
        ~Binding();
        Binding(const Binding&)=delete;Binding& operator=(const Binding&)=delete;
    private:
        friend class Body;
        Binding* _previous{nullptr};quint64 _row{0};bool _pushed{false},_claimed{false},_ready{false};
    };
    enum class Kind {Processing,Raw};
    class Body final {
    public:
        explicit Body(Kind kind) noexcept;
        ~Body();
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:
        Kind _kind;quint64 _row{0},_previous{0};int _exceptions{0};
    };
    static void contentResetEntering() noexcept;
    static void contentResetReturned() noexcept;
};
} // namespace image::e2e
#endif
