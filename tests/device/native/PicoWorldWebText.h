// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <functional>
#include <QPointF>
#include <QQuickItem>
#include <QString>
namespace overte::e2e {
// Ordinary IME only after independently observed world-item/editor focus.
// This provider cannot focus an item, click, navigate or assign DOM state.
using PicoWorldWebTextProvider=std::function<bool(QQuickItem*,const QPointF&,const QString&,qint64)>;
inline const char* picoWorldWebTextProperty(){return "_overteE2EPicoWorldWebTextProviderV1";}
}
Q_DECLARE_METATYPE(overte::e2e::PicoWorldWebTextProvider)
#endif
