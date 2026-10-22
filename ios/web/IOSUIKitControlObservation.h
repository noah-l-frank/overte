// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(__OBJC__)
#include <QVariantMap>
@class UIButton;
class QQuickItem;
namespace overte::ios::uikit_input {
// Called only for a real existing source-token UIButton, with the just-read
// actual Qt control. No UI object is retained across the call or serialized.
void bindTabletButton(UIButton*,QQuickItem*,const QString&,const QVariantMap&) noexcept;
}
#endif
