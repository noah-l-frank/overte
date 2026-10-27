// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(Q_OS_IOS) && defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QVariantMap>
#include <image/IOSImageProcessingObservation.h>
#include <cstddef>
#include <memory>

namespace overte::e2e {
// Tokens pin diagnostic State only. No object address or product owner escapes.
class IOSAssetsImageReaderStorageObservation final {
public:
    class Token final {
    public:
        Token()=default;
    private:
        friend class IOSAssetsImageReaderStorageObservation;
        std::shared_ptr<void> _state;quint64 _row{0};
    };
    static Token allocationEntering(std::size_t bytes) noexcept;
    static void allocationReturned(const Token& attempt,void* actual) noexcept;
    static void allocationThrew(const Token& attempt) noexcept;
    static void attach(void* actual,const image::e2e::IOSImageProcessingObservation::Task& task) noexcept;
    static void destructorEntering(void* actual) noexcept;
    static Token deleteEntering(void* actual,std::size_t bytes,bool sized) noexcept;
    static void deleteReturned(const Token& captured) noexcept;
    static QVariantMap snapshot() noexcept;
    static void disarm() noexcept;
};
} // namespace overte::e2e
#endif
