// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QtGlobal>
class QImage;
namespace gpu {
// Test-only original GPU copy, retained through the real frame fence. The
// owner must never call complete() before that original fence succeeds.
class FeatureFramebufferReadback {
public:
    virtual ~FeatureFramebufferReadback() = default;
    virtual bool complete(QImage&) = 0;
    virtual quint64 bytes() const = 0;
};
}
#endif
