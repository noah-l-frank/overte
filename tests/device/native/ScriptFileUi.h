// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include "NormalScriptFileControls.h"
#include <ui/NativeFieldInput.h>
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QHash>
#include <QKeyEvent>
#include <QPointer>
#include <QQuickWindow>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <algorithm>
#include <cmath>
#include <functional>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
class ScriptFileUi {
public:
    ScriptFileUi() : _instance(nonce()), _generation(nonce()) { _clock.start(); }

    QJsonObject observe(QQuickItem* root, QQuickWindow* window) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        if (_root != root || _window != window) {
            _root = root; _window = window; _generation = nonce(); _controls.clear();
        }
        bool ready = root && window && root->window() == window
            && root->thread() == qApp->thread() && window->thread() == qApp->thread();
        QHash<QString, Control> controls;
        int visited {0};
        bool ambiguous {false};
        std::function<void(QQuickItem*, int)> walk = [&](QQuickItem* item, int depth) {
            if (!item || ambiguous) { return; }
            if (++visited > 4096 || depth > 128 || item->thread() != qApp->thread()) { ambiguous = true; return; }
            if (!visibleRect(item, window).isEmpty()) {
                const auto id = scriptFileControlId(item);
                if (!id.isEmpty()) {
                    if (controls.contains(id)) { ambiguous = true; return; }
                    const auto previous = _controls.value(id);
                    const auto source = scriptFileControlSource(item);
                    controls.insert(id, {item, previous.item == item && previous.source == source ? previous.token : nonce(), source});
                }
            }
            for (auto child : item->childItems()) { walk(child, depth + 1); }
        };
        if (ready) {
            walk(root, 0);
            if (root->parentItem() == window->contentItem()) {
                for (auto layer : window->contentItem()->childItems()) {
                    if (layer != root && layer->inherits("QQuickOverlay")) { walk(layer, 0); }
                }
            }
        }
        bool picker {false};
        for (const auto& id : controls.keys()) { picker = picker || id.startsWith(QStringLiteral("script-file.")); }
        if (picker) { controls.remove(QStringLiteral("scripts.from-file")); }
        if (ambiguous || controls.size() > 384) { ready = false; controls.clear(); }
        _controls = controls;
        auto ids = controls.keys(); std::sort(ids.begin(), ids.end());
        QJsonArray rows;
        for (const auto& id : ids) {
            const auto control = controls.value(id);
            QJsonObject row{{"id", id}, {"token", control.token}, {"enabled", control.item->isEnabled()},
                {"focused", control.item->hasActiveFocus()}};
            appendScriptFileObservation(row, control.item, id);
            rows.append(row);
        }
        return {{"schemaVersion", 1}, {"instance", _instance}, {"generation", _generation},
            {"sourceSequence", static_cast<double>(++_sourceSequence)},
            {"lastCommandSequence", static_cast<double>(_lastCommandSequence)}, {"elapsedMs", static_cast<double>(_clock.elapsed())},
            {"capturedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"processId", static_cast<double>(QCoreApplication::applicationPid())},
            {"fileControlsVersion", 1}, {"ready", ready}, {"controls", rows}};
    }

    QJsonObject apply(QQuickItem* root, QQuickWindow* window, const QJsonObject& command,
                      const std::function<bool(QQuickItem*)>& pointerClick) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const auto current = observe(root, window);
        const auto request = command.value("commandId").toString();
        QJsonObject result{{"schemaVersion", 1}, {"commandId", request}, {"performed", false},
            {"instance", _instance}, {"generation", _generation}, {"sequence", command.value("sequence")},
            {"processId", static_cast<double>(QCoreApplication::applicationPid())}};
        const auto action = command.value("action").toString();
        QSet<QString> fields{"schemaVersion", "commandId", "instance", "generation", "sequence", "observedElapsedMs",
            "controlId", "controlToken", "action"};
        if (action == "replace") { fields.insert("text"); }
        if (action == "select-index") { fields.insert("index"); }
        const auto keys = command.keys();
        qint64 sequence {0}, observed {0};
        if (!current.value("ready").toBool() || QSet<QString>(keys.begin(), keys.end()) != fields
                || command.value("schemaVersion") != QJsonValue(1)
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request).hasMatch()
                || command.value("instance") != QJsonValue(_instance) || command.value("generation") != QJsonValue(_generation)
                || !integer(command.value("sequence"), sequence) || sequence != _lastCommandSequence + 1
                || !integer(command.value("observedElapsedMs"), observed) || observed > _clock.elapsed()
                || _clock.elapsed() - observed > 5000
                || (action != "activate" && action != "replace" && action != "submit" && action != "select-index")) { return result; }
        // Consume intent before dispatch; never replay uncertain native input.
        _lastCommandSequence = sequence;
        const auto id = command.value("controlId").toString();
        const auto control = _controls.value(id);
        if (!control.item || !control.item->isEnabled() || command.value("controlToken") != QJsonValue(control.token)
                || visibleRect(control.item, window).isEmpty()) { return result; }
        bool delivered {false};
        if (action == "activate") {
            delivered = pointerClick && pointerClick(control.item);
        } else if (id == QStringLiteral("script-file.folder")) {
            if (action == "replace" && command.value("text").isString()) {
                const auto text = command.value("text").toString();
                if (validScriptFolderPath(text)) {
                    delivered = overte::ui::replaceFocusedField(control.item, window, text);
                }
            } else if (action == "submit") { delivered = overte::ui::submitFocusedField(control.item, window); }
        } else if (id == QStringLiteral("script-file.primary") && action == "select-index") {
            qint64 index {0};
            if (integer(command.value("index"), index)) { delivered = selectFocusedPrimary(control.item, window, index); }
        }
        result["performed"] = delivered; // Input delivery only; read real state separately.
        return result;
    }

    static QRectF visibleRect(QQuickItem* item, QQuickWindow* window) {
        if (!item || !window || window->thread() != QThread::currentThread()
                || item->thread() != QThread::currentThread()
                || item->window() != window || item->width() <= 0 || item->height() <= 0) { return {}; }
        auto rect = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
        const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width())
                || !std::isfinite(rect.height()) || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return {}; }
        rect = rect.intersected(QRectF(0, 0, window->width(), window->height()));
        for (auto parent = item; parent; parent = parent->parentItem()) {
            if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) { return {}; }
            if (parent->clip()) { rect = rect.intersected(parent->mapRectToScene(parent->clipRect())); }
        }
        return rect.contains(center) ? rect : QRectF();
    }

    static bool selectFocusedPrimary(QQuickItem* item, QQuickWindow* window, qint64 index) {
        if (!item || !window || !qApp || QThread::currentThread() != qApp->thread()
                || item->thread() != QThread::currentThread() || window->thread() != QThread::currentThread()
                || !QCoreApplication::arguments().contains("--testScript")
                || scriptFileControlId(item) != QStringLiteral("script-file.primary")
                || visibleRect(item, window).isEmpty() || !item->isEnabled()
                || index < 0 || index >= 32 || index >= item->property("count").toInt() || !ownsFocus(item, window)) { return false; }
        QPointer<QQuickItem> original = item;
        QPointer<QQuickWindow> surface = window;
        bool delivered = key(surface, Qt::Key_Home);
        for (int step = 0; delivered && original && surface && step < index; ++step) {
            delivered = ownsFocus(original, surface) && key(surface, Qt::Key_Down);
        }
        return delivered && original && surface && ownsFocus(original, surface) && key(surface, Qt::Key_Return);
    }

private:
    struct Control { QPointer<QQuickItem> item; QString token, source; };
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool integer(const QJsonValue& value, qint64& number) {
        const auto candidate = value.toDouble(-1);
        if (!value.isDouble() || !std::isfinite(candidate) || candidate < 0 || candidate > 9007199254740991.0
                || std::floor(candidate) != candidate) { return false; }
        number = static_cast<qint64>(candidate); return true;
    }
    static bool ownsFocus(QQuickItem* item, QQuickWindow* window) {
        if (!item || !window || !window->activeFocusItem()) { return false; }
        for (auto focus = static_cast<QObject*>(window->activeFocusItem()); focus; focus = focus->parent()) {
            if (focus == item) { return true; }
        }
        return false;
    }
    static bool key(QQuickWindow* window, int code) {
        if (!window) { return false; }
        QPointer<QQuickWindow> guarded = window;
        QKeyEvent press(QEvent::KeyPress, code, Qt::NoModifier);
        const bool delivered = QCoreApplication::sendEvent(window, &press);
        if (guarded) {
            QKeyEvent release(QEvent::KeyRelease, code, Qt::NoModifier);
            QCoreApplication::sendEvent(guarded, &release);
        }
        return delivered;
    }
    QPointer<QQuickItem> _root;
    QPointer<QQuickWindow> _window;
    QHash<QString, Control> _controls;
    QString _instance, _generation;
    QElapsedTimer _clock;
    quint64 _sourceSequence {0};
    qint64 _lastCommandSequence {0};
};
#endif
} // namespace overte::e2e
