// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PicoE2eNavigationUi.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <algorithm>
#include <cmath>
#include <ui/NativeFieldInput.h>

namespace overte::pico::e2e {
namespace {

QString token() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }

bool visible(QQuickItem* item, QQuickWindow* window) {
    if (!item || !window || item->window() != window || !item->isVisible()
            || item->width() <= 0 || item->height() <= 0) { return false; }
    // TextInput's painted boundingRect can be just its empty cursor or glyphs.
    // Native pointer hit targets use the actual control width and height.
    auto rect = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
    const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
    if (!std::isfinite(rect.x()) || !std::isfinite(rect.y())
            || !std::isfinite(rect.width()) || !std::isfinite(rect.height())
            || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return false; }
    rect = rect.intersected(QRectF(0, 0, window->width(), window->height()));
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) {
            return false;
        }
        if (parent->clip()) {
            if (!parent->clipRect().contains(parent->mapFromScene(center))) { return false; }
            rect = rect.intersected(parent->mapRectToScene(parent->clipRect()));
        }
    }
    return !rect.isEmpty() && rect.contains(center);
}

bool enabled(QQuickItem* item) {
    const auto explicitEnabled = item->property("buttonEnabled");
    return item->isEnabled() && (!explicitEnabled.isValid() || explicitEnabled.toBool());
}

QString controlId(QQuickItem* item) {
    static const QHash<QString, QString> names {
        { "tabletAddressLine", "navigation.address" },
        { "tabletAddressBack", "navigation.back" },
        { "tabletAddressForward", "navigation.forward" },
        { "nav.home", "tablet.home" },
        { "snapshotName", "snapshot.name" },
        { "snapshotMode", "snapshot.mode" },
        { "snapshotFormat", "snapshot.format" },
        { "snapshotCapture", "snapshot.capture" },
        { "snapshotCancelCapture", "snapshot.cancel" },
    };
    const auto name = item->objectName();
    if (names.contains(name)) { return names.value(name); }
    for (const auto& mode : {"still", "animated", "panorama", "cubemap"}) {
        if (name == QStringLiteral("snapshotMode.option.") + mode) {
            return QStringLiteral("snapshot.mode.") + mode;
        }
    }
    for (const auto& format : {"png", "jpg", "webp"}) {
        if (name == QStringLiteral("snapshotFormat.option.") + format) {
            return QStringLiteral("snapshot.format.") + format;
        }
    }
    for (int page = 1; page <= 32; ++page) {
        if (name == QStringLiteral("tabletPage.%1").arg(page)) {
            return QStringLiteral("tablet.page.%1").arg(page);
        }
    }
    // Match the actual TabletButton, never its child caption Text item.
    if (item->metaObject()->indexOfSignal("clicked()") >= 0) {
        const auto caption = item->property("text").toString();
        if (caption == QStringLiteral("GOTO")) { return QStringLiteral("navigation.goto"); }
        if (caption == QStringLiteral("SNAP")) { return QStringLiteral("snapshot.entry"); }
    }
    return {};
}

bool integer(const QJsonValue& value, qint64& output) {
    if (!value.isDouble()) { return false; }
    const double number = value.toDouble();
    if (!std::isfinite(number) || number < 0 || number > 9007199254740991.0
            || std::floor(number) != number) { return false; }
    output = static_cast<qint64>(number);
    return true;
}

bool exactKeys(const QJsonObject& object, const QSet<QString>& expected) {
    const auto keys = object.keys();
    return QSet<QString>(keys.begin(), keys.end()) == expected;
}

} // namespace

NavigationUi::NavigationUi() : _bridgeId(token()), _generation(token()) { _clock.start(); }

QJsonObject NavigationUi::observe(QQuickItem* root, QQuickWindow* window, bool open) {
    // This object belongs to the GUI timer. Reject foreign-thread calls before
    // reading the scene graph, including otherwise valid stale pointers.
    const bool gui = qApp && QThread::currentThread() == qApp->thread();
    if (!gui) { return {}; }
    if (_root != root || _window != window || _open != open) {
        _generation = token();
        _controls.clear();
        _root = root;
        _window = window;
        _open = open;
    }
    bool ready = open && root && window && root->thread() == qApp->thread()
        && window->thread() == qApp->thread() && root->window() == window;
    QHash<QString, Control> controls;
    bool ambiguous { false };
    int count { 0 };
    std::function<void(QQuickItem*, int)> walk = [&](QQuickItem* item, int depth) {
        if (!item || ambiguous) { return; }
        if (++count > 4096 || depth > 128) { ambiguous = true; return; }
        if (visible(item, window)) {
            const auto id = controlId(item);
            if (!id.isEmpty()) {
                if (controls.contains(id)) { ambiguous = true; return; }
                const auto previous = _controls.value(id);
                controls.insert(id, { item, previous.item == item ? previous.token : token() });
            }
        }
        const auto children = item->childItems();
        for (auto child : children) { walk(child, depth + 1); }
    };
    if (ready) {
        walk(root, 0);
        // Controls popups are rendered in this window's Qt overlay beside the
        // complete tablet root. Never discover arbitrary or foreign siblings.
        if (root->parentItem() == window->contentItem()) {
            for (auto layer : window->contentItem()->childItems()) {
                if (layer != root && layer->inherits("QQuickOverlay")) { walk(layer, 0); }
            }
        }
    }
    if (ambiguous || !ready) { controls.clear(); ready = false; }
    _controls = controls;
    auto ids = controls.keys();
    std::sort(ids.begin(), ids.end());
    QJsonArray observed;
    for (const auto& id : ids) {
        const auto control = controls.value(id);
        QJsonObject row { { "id", id }, { "token", control.token },
            { "enabled", enabled(control.item) }, { "focused", control.item->hasActiveFocus() } };
        if (id.startsWith(QStringLiteral("snapshot.mode.")) || id.startsWith(QStringLiteral("snapshot.format."))) {
            row["checked"] = control.item->property("checked").toBool();
        }
        observed.append(row);
    }
    return { { "schemaVersion", 1 }, { "bridgeId", _bridgeId }, { "generation", _generation },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "elapsedMs", static_cast<double>(_clock.elapsed()) },
        { "updatedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
        { "lastCommandSequence", static_cast<double>(_lastCommandSequence) },
        { "open", open }, { "ready", ready }, { "controls", observed } };
}

QJsonObject NavigationUi::apply(QQuickItem* root, QQuickWindow* window, bool open,
                               const QJsonObject& command,
                               const std::function<bool(QQuickItem*)>& pointerClick) {
    if (!qApp || QThread::currentThread() != qApp->thread()) { return {}; }
    const auto current = observe(root, window, open);
    const auto id = command.value("commandId").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "bridgeId", _bridgeId },
        { "commandId", id }, { "sequence", command.value("sequence") },
        { "performed", false }, { "error", QStringLiteral("invalid-command") },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "updatedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) } };
    const auto action = command.value("action").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "bridgeId", "generation",
        "sequence", "observedElapsedMs", "controlId", "controlToken", "action" };
    if (action == "replace") { expected.insert("text"); }
    qint64 sequence { 0 }, observedAt { 0 };
    const auto uuid = QUuid(id);
    if (!exactKeys(command, expected) || command.value("schemaVersion") != QJsonValue(1)
            || uuid.isNull() || uuid.toString(QUuid::WithoutBraces) != id
            || !integer(command.value("sequence"), sequence)
            || sequence != _lastCommandSequence + 1
            || command.value("bridgeId") != QJsonValue(_bridgeId)
            || command.value("generation") != QJsonValue(_generation)
            || !integer(command.value("observedElapsedMs"), observedAt)
            || observedAt > _clock.elapsed() || _clock.elapsed() - observedAt > 5000
            || (action != "activate" && action != "replace" && action != "submit")) { return result; }
    // Consume an admitted sequence before any input. An uncertain result may
    // be read again but can never replay a pointer/key/IME mutation.
    _lastCommandSequence = sequence;
    const auto controlId = command.value("controlId").toString();
    const auto control = _controls.value(controlId);
    if (!current.value("ready").toBool() || !control.item
            || command.value("controlToken") != QJsonValue(control.token)
            || !enabled(control.item) || !visible(control.item, window)) {
        result["error"] = QStringLiteral("control-unavailable");
        return result;
    }
    bool delivered { false };
    if (action == "activate") {
        delivered = pointerClick && pointerClick(control.item);
    } else if (controlId == QStringLiteral("navigation.address")) {
        if (action == "replace" && command.value("text").isString()) {
            delivered = overte::ui::replaceFocusedField(control.item, window, command.value("text").toString());
        } else if (action == "submit") {
            delivered = overte::ui::submitFocusedField(control.item, window);
        }
    } else if (controlId == QStringLiteral("snapshot.name") && action == "replace"
            && command.value("text").isString()) {
        const auto text = command.value("text").toString();
        static const QRegularExpression ownedName {
            QStringLiteral("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\\z") };
        if (text.size() <= 48 && ownedName.match(text).hasMatch()) {
            delivered = overte::ui::replaceFocusedField(control.item, window, text);
        }
    }
    result["performed"] = delivered;
    result["error"] = delivered ? QString() : QStringLiteral("input-delivery-failed");
    return result;
}

} // namespace overte::pico::e2e
