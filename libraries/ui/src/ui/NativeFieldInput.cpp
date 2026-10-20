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

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PreparedFieldCommit.h"
#include <PathUtils.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QQmlContext>
#include <QQmlEngine>
#include <QRegularExpression>
#include <QTimer>
#include <QUuid>
#endif

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
    // A TextInput paint bound can be only its cursor or current glyphs.
    // Editing visibility belongs to the real control area, not its text width.
    QRectF visible = field->mapRectToScene(QRectF(0, 0, field->width(), field->height()));
    if (!std::isfinite(visible.x()) || !std::isfinite(visible.y())
            || !std::isfinite(visible.width()) || !std::isfinite(visible.height())) {
        return std::nullopt;
    }
    visible = visible.intersected(QRectF(0, 0, surface->width(), surface->height()));
    for (auto parent = field->parentItem(); parent; parent = parent->parentItem()) {
        if (parent->clip()) { visible = visible.intersected(parent->mapRectToScene(parent->clipRect())); }
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

#if defined(OVERTE_E2E_FEATURE_TESTS)
namespace {
QString commitNonce() {
    return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
}
QString commitSha(const QString& value) {
    return QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(), QCryptographicHash::Sha256).toHex());
}
QQmlContext* scriptFilterContext(QQuickItem* field) {
    if (!QCoreApplication::instance() || !field
            || field->thread() != QCoreApplication::instance()->thread()
            || QThread::currentThread() != field->thread()
            || field->objectName() != QStringLiteral("scriptFilter")) { return nullptr; }
    int depth {0};
    for (auto context = qmlContext(field); context && ++depth <= 128; context = context->parentContext()) {
        if (context->thread() != field->thread()) { return nullptr; }
        const auto source = context->baseUrl();
        if (context->nameForObject(field) == QStringLiteral("filter")
                && (source.scheme() == "file" || source.scheme() == "qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source == PathUtils::qmlUrl(QStringLiteral("hifi/dialogs/TabletRunningScripts.qml"))
                && source.toString().size() <= 4096
                && source.path().endsWith("/hifi/dialogs/TabletRunningScripts.qml")) { return context; }
    }
    return nullptr;
}
}

PreparedFieldCommit::PreparedFieldCommit(QQuickItem* field, QQuickWindow* surface, QQmlContext* context,
        const QString& originalText, int cursor, int anchor, std::unique_ptr<QInputMethodEvent> commit) :
    _field(field), _surface(surface), _context(context), _commit(std::move(commit)), _timer(new QTimer(this)),
    _instance(commitNonce()), _eventId(commitNonce()), _sourceUrl(context->baseUrl().toString(QUrl::FullyEncoded)),
    _initialSha(commitSha(originalText)), _inputSha(commitSha(_commit->commitString())),
    _inputUnits(static_cast<int>(_commit->commitString().size())), _cursor(cursor), _anchor(anchor) {
    _clock.start();
    if (_sourceUrl.size() > 4096) { _valid = false; }
    for (auto parent = field->parentItem(); parent; parent = parent->parentItem()) {
        if (_ancestors.size() >= 128 || parent->thread() != thread()) { _valid = false; break; }
        _ancestors.append(QPointer<QQuickItem>(parent));
    }
    _createdEpoch = epoch();
    record("captured", "none");
    _timer->setSingleShot(true);
    _timer->setTimerType(Qt::PreciseTimer);
    connect(_timer, &QTimer::timeout, this, [this] { expire(); });
    _timer->start(10000);
}

PreparedFieldCommit::~PreparedFieldCommit() = default;

bool PreparedFieldCommit::onNativeThread() const {
    return QCoreApplication::instance() && thread() == QCoreApplication::instance()->thread()
        && QThread::currentThread() == thread()
        && QCoreApplication::arguments().contains("--testScript");
}

qint64 PreparedFieldCommit::epoch() {
    const auto value = QDateTime::currentMSecsSinceEpoch();
    if (value <= 0 || value < _lastEpoch) { _valid = false; return 0; }
    _lastEpoch = value;
    return value;
}

void PreparedFieldCommit::record(const QString& kind, const QString& reason) {
    const auto captured = epoch();
    if (!_valid || !captured || _events.size() >= 2) { _valid = false; return; }
    _events.append(QVariantMap{{"sequence", static_cast<int>(_events.size()) + 1}, {"kind", kind}, {"reason", reason},
        {"capturedEpochMs", captured}, {"elapsedMs", _clock.elapsed()}});
}

void PreparedFieldCommit::finish(const QString& kind, const QString& reason) {
    if (!_commit || _dispatching) { return; }
    _timer->stop();
    _commit.reset(); // Retire the actual event before publishing its original terminal history.
    record(kind, reason);
}

void PreparedFieldCommit::expire() {
    if (!onNativeThread() || !_commit || _dispatching) { return; }
    const auto elapsed = _clock.elapsed();
    if (elapsed < 0) { _valid = false; release(); return; }
    if (elapsed < 10000) {
        // A platform timer cannot redefine the actual original monotonic ceiling.
        _timer->start(static_cast<int>(10000 - elapsed));
        return;
    }
    finish("expired", "hold-deadline");
}

QVariantMap PreparedFieldCommit::observation(const QString& requestId) {
    if (!onNativeThread() || _dispatching
            || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(requestId).hasMatch()) { return {}; }
    if (_commit && _clock.elapsed() >= 10000) { expire(); }
    const auto captured = epoch();
    if (!_valid || !captured || _events.isEmpty()) { return {}; }
    return {{"pendingFieldCommitVersion", 1}, {"requestId", requestId}, {"instance", _instance},
        {"eventId", _eventId}, {"sequence", static_cast<qulonglong>(++_sequence)},
        {"processId", QCoreApplication::applicationPid()}, {"createdEpochMs", _createdEpoch},
        {"capturedEpochMs", captured}, {"elapsedMs", _clock.elapsed()}, {"pending", static_cast<bool>(_commit)},
        {"source", QVariantMap{{"componentUrl", _sourceUrl}, {"fieldName", "scriptFilter"},
            {"initialTextSha256", _initialSha}, {"inputSha256", _inputSha}, {"inputCodeUnits", _inputUnits}}},
        {"events", _events}};
}

bool PreparedFieldCommit::dispatch(QQuickItem* currentField, QQuickWindow* currentSurface) {
    if (!onNativeThread() || !_valid || _dispatching || !_commit) { return false; }
    if (!epoch()) { return false; }
    if (_clock.elapsed() >= 10000) { expire(); return false; }
    // The caller must supply a genuinely observed current Scripts control.
    // An absent/foreign source cannot manufacture a retired-context attempt.
    if (!currentField || !currentSurface || currentField->thread() != thread()
            || currentSurface->thread() != thread() || currentField->window() != currentSurface
            || !currentField->isVisible() || !currentField->isEnabled()
            || !scriptFilterContext(currentField)) { return false; }
    bool same = currentField == _field && currentSurface == _surface && _context
        && scriptFilterContext(currentField) == _context
        && _context->baseUrl().toString(QUrl::FullyEncoded) == _sourceUrl;
    auto parent = currentField->parentItem();
    for (const auto& original : _ancestors) {
        if (!original || parent != original) { same = false; break; }
        parent = parent->parentItem();
    }
    if (parent) { same = false; }
    if (!same) { finish("rejected", "context-retired"); return true; }
    const auto actual = focusedText(_field, _surface);
    if (!actual) { finish("rejected", "focus-lost"); return true; }
    if (commitSha(actual->text) != _initialSha || actual->cursor != _cursor || actual->anchor != _anchor) {
        finish("rejected", "editor-changed"); return true;
    }
    if (_clock.elapsed() >= 10000) { expire(); return false; }
    _timer->stop();
    auto commit = std::move(_commit);
    _dispatching = true;
    QPointer<PreparedFieldCommit> self(this);
    QCoreApplication::sendEvent(_surface, commit.get());
    if (!self) { return false; }
    _dispatching = false;
    // Record only after the original native send returned, never as an intent
    // or a claim that the editor/product consumed the input successfully.
    record("sent", "none");
    return true;
}

bool PreparedFieldCommit::release() {
    if (!onNativeThread() || _dispatching) { return false; }
    if (_commit) {
        if (_clock.elapsed() >= 10000) { finish("expired", "hold-deadline"); }
        else { finish("released", "none"); }
    }
    return !_commit;
}

std::unique_ptr<PreparedFieldCommit> prepareFocusedScriptFilterCommit(
        QQuickItem* field, QQuickWindow* surface, const QString& text) {
    if (!QCoreApplication::instance() || QThread::currentThread() != QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !literalText(text)
            || !QRegularExpression("\\AOverte ä Ω 東京 [0-9a-f]{32}\\z").match(text).hasMatch()) { return {}; }
    QPointer<QQuickItem> guardedField(field);
    QPointer<QQuickWindow> guardedSurface(surface);
    QPointer<QQmlContext> context(scriptFilterContext(field));
    auto original = focusedText(field, surface);
    if (!context || !original || original->text != "retry-" + text.right(32)) { return {}; }
    if (std::min(original->cursor, original->anchor) != 0
            || std::max(original->cursor, original->anchor) != original->text.size()) {
        key(guardedSurface, Qt::Key_A, Qt::ControlModifier);
    }
    const auto selected = focusedText(guardedField, guardedSurface);
    if (!selected || !context || scriptFilterContext(guardedField) != context || selected->text != original->text
            || std::min(selected->cursor, selected->anchor) != 0
            || std::max(selected->cursor, selected->anchor) != selected->text.size()) { return {}; }
    auto commit = std::make_unique<QInputMethodEvent>();
    commit->setCommitString(text);
    auto prepared = std::unique_ptr<PreparedFieldCommit>(new PreparedFieldCommit(guardedField, guardedSurface, context,
        selected->text, selected->cursor, selected->anchor, std::move(commit)));
    if (!prepared->_valid) { return {}; }
    return prepared;
}
#endif

} // namespace overte::ui
