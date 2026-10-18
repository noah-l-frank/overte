// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeFieldInput.h"

#include <QCoreApplication>
#include <QInputMethodEvent>
#include <QKeyEvent>
#include <QKeySequence>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <QVariant>
#include <algorithm>
#include <cmath>
#include <optional>

namespace overte::ui {
namespace {

struct Editor {
    QString text;
    int cursor;
    int anchor;
};

std::optional<Editor> focusedText(QQuickItem* field, QQuickWindow* surface) {
    if (!field || !surface || QThread::currentThread() != surface->thread()
            || field->thread() != surface->thread() || field->window() != surface
            || !field->isEnabled() || !field->isVisible()
            || field->width() <= 0.0 || field->height() <= 0.0
            || field->property("readOnly").toBool()) {
        return std::nullopt;
    }
    for (auto parent = field; parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) {
            return std::nullopt;
        }
    }
    QRectF visible = field->mapRectToScene(field->boundingRect());
    if (!std::isfinite(visible.x()) || !std::isfinite(visible.y())
            || !std::isfinite(visible.width()) || !std::isfinite(visible.height())) {
        return std::nullopt;
    }
    visible = visible.intersected(QRectF(0, 0, surface->width(), surface->height()));
    for (auto parent = field->parentItem(); parent; parent = parent->parentItem()) {
        if (parent->clip()) { visible = visible.intersected(parent->mapRectToScene(parent->boundingRect())); }
    }
    if (visible.isEmpty()) { return std::nullopt; }
    auto focus = surface->activeFocusItem();
    bool ownsFocus { false };
    for (auto item = focus; item; item = item->parentItem()) {
        if (item == field) { ownsFocus = true; break; }
    }
    if (!ownsFocus || !focus->flags().testFlag(QQuickItem::ItemAcceptsInputMethod)
            || !focus->inputMethodQuery(Qt::ImEnabled).toBool()) {
        return std::nullopt;
    }
    // Query the actual focused editor using the platform input-method API.
    // Accessibility factories are optional on headless and native Qt builds.
    const auto text = focus->inputMethodQuery(Qt::ImSurroundingText);
    const auto cursor = focus->inputMethodQuery(Qt::ImCursorPosition);
    const auto anchor = focus->inputMethodQuery(Qt::ImAnchorPosition);
    bool cursorValid { false }, anchorValid { false };
    Editor result { text.toString(), cursor.toInt(&cursorValid), anchor.toInt(&anchorValid) };
    if (text.userType() != QMetaType::QString || result.text.size() > 4096
            || !cursorValid || !anchorValid || result.cursor < 0 || result.anchor < 0
            || result.cursor > result.text.size() || result.anchor > result.text.size()) {
        return std::nullopt;
    }
    return result;
}

bool literalText(const QString& text) {
    if (text.size() > 4096) { return false; }
    for (int index = 0; index < text.size(); ++index) {
        const QChar character = text.at(index);
        if (character.unicode() < 32 || character.unicode() == 127) { return false; }
        if (character.isHighSurrogate()) {
            if (++index >= text.size() || !text.at(index).isLowSurrogate()) { return false; }
        } else if (character.isLowSurrogate()) {
            return false;
        }
    }
    return true;
}

bool key(QQuickWindow* surface, int code, Qt::KeyboardModifiers modifiers = Qt::NoModifier) {
    QPointer<QQuickWindow> guarded(surface);
    QKeyEvent press(QEvent::KeyPress, code, modifiers);
    const bool delivered = QCoreApplication::sendEvent(surface, &press);
    // A legitimate submit may dismiss its field. Release the owned window's
    // key anyway; never retry an uncertain keyDown or direct-call a handler.
    if (guarded) {
        QKeyEvent release(QEvent::KeyRelease, code, modifiers);
        QCoreApplication::sendEvent(guarded, &release);
    }
    // This reports event delivery, never that a feature succeeded. Qt Quick
    // may consume a key without propagating its accepted flag to the window.
    return delivered;
}

} // namespace

bool replaceFocusedField(QQuickItem* field, QQuickWindow* surface, const QString& text) {
    if (!literalText(text)) { return false; }
    auto content = focusedText(field, surface);
    if (!content) { return false; }
    QPointer<QQuickItem> guardedField(field);
    QPointer<QQuickWindow> guardedSurface(surface);
    if (!content->text.isEmpty()) {
        const QKeySequence selectAll(QKeySequence::SelectAll);
        if (selectAll.isEmpty()) { return false; }
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
        const int combined = selectAll[0].toCombined();
#else
        const int combined = selectAll[0];
#endif
        if (!key(surface, combined & ~int(Qt::KeyboardModifierMask),
                 Qt::KeyboardModifiers(combined & int(Qt::KeyboardModifierMask)))) {
            return false;
        }
        // Focus/selection handlers may replace their control. Never commit
        // private input into the new owner or append after ignored Select All.
        content = focusedText(guardedField, guardedSurface);
        if (!content || std::min(content->cursor, content->anchor) != 0
                || std::max(content->cursor, content->anchor) != content->text.size()) { return false; }
    }
    if (!focusedText(guardedField, guardedSurface)) { return false; }
    if (text.isEmpty()) {
        if (content->text.isEmpty()) { return true; }
        key(guardedSurface, Qt::Key_Backspace);
        const auto observed = focusedText(guardedField, guardedSurface);
        return observed && observed->text.isEmpty();
    }
    QInputMethodEvent commit;
    commit.setCommitString(text);
    QCoreApplication::sendEvent(guardedSurface, &commit);
    // QQuickWindow forwards an IME event without propagating its accepted
    // flag. Observe the actual editor instead of inferring delivery from it.
    const auto observed = focusedText(guardedField, guardedSurface);
    return observed && observed->text == text;
}

bool submitFocusedField(QQuickItem* field, QQuickWindow* surface) {
    return focusedText(field, surface) && key(surface, Qt::Key_Return);
}

} // namespace overte::ui
