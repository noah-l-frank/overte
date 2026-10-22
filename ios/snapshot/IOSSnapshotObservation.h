// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QVariantMap>
namespace overte::ios {
// Passive originals only. This never authorizes Photos access, captures an
// image, dismisses a controller or changes a native export operation.
QVariantMap featureSnapshotExportObservation();
}
#endif
