// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QtGlobal>
#include "IOSAssetReplyTrace.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
namespace overte::e2e {
IOSAssetReplyTrace& IOSAssetReplyTrace::instance() {static IOSAssetReplyTrace actual;return actual;}
QString& IOSAssetReplyTrace::current() {static thread_local QString owner;return owner;}
}
#endif
