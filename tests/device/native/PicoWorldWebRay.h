// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <functional>
#include <QPointF>
#include <QQuickItem>
#include <QVariantMap>
namespace overte::e2e {
// Passive actual world geometry only. The ordinary OpenXR controller owns
// pointer delivery; this provider cannot click, focus, move or edit a target.
using PicoWorldWebRayProvider = std::function<QVariantMap(QQuickItem*,const QPointF&)>;
inline const char* picoWorldWebRayProperty() { return "_overteE2EPicoWorldWebRayProviderV1"; }
}
Q_DECLARE_METATYPE(overte::e2e::PicoWorldWebRayProvider)
#endif
