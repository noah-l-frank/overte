// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QString>

class QQuickItem;
class QQuickWindow;

namespace overte::ui {

// Native input for an already focused, visible editable Qt Quick control.
// The caller owns surface/process/source binding and must obtain the actual
// field through its live UI observation. No editor property assignment or
// feature mutation API is used. A submit result acknowledges delivery only.
bool replaceFocusedField(QQuickItem* field, QQuickWindow* surface, const QString& text);
bool submitFocusedField(QQuickItem* field, QQuickWindow* surface);

} // namespace overte::ui
