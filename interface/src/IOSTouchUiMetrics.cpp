// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0

#include "IOSTouchUiMetrics.h"

#if !defined(Q_OS_IOS)
// Desktop MOC emits this class's vtable without the UIKit implementation.
// The native iOS destructor retains its notification-observer cleanup.
IOSTouchUiMetrics::~IOSTouchUiMetrics() = default;
#endif
