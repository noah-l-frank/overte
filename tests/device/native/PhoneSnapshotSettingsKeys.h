// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QStringList>
namespace overte::e2e {
inline QStringList snapshotSettingsKeys() {
    QStringList keys{"alsoTakeAnimatedSnapshot","snapshotFormat","previousSnapshotHref","previousSnapshotDomainID",
        "previousStillSnapPath","previousStillSnapStoryID","previousStillSnapBlastingDisabled","previousStillSnapHifiSharingDisabled","previousStillSnapUrl",
        "previousAnimatedSnapPath","previousAnimatedSnapStoryID","previousAnimatedSnapBlastingDisabled","previousAnimatedSnapHifiSharingDisabled"};
    keys.sort();return keys;
}
}
#endif
