// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSNormalUiInput.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMouseEvent>
#include <QSet>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVariant>
#include <algorithm>
#include <cmath>
#include <functional>
#include <ui/NativeFieldInput.h>

namespace overte::ios {
namespace {

QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }

QRectF visibleBounds(QQuickItem* item) {
    auto window = item ? item->window() : nullptr;
    if (!window || window->thread() != QThread::currentThread()
            || !item->isVisible() || item->width() <= 0 || item->height() <= 0) { return {}; }
    auto result = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
    const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
    if (!std::isfinite(result.x()) || !std::isfinite(result.y())
            || !std::isfinite(result.width()) || !std::isfinite(result.height())
            || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return {}; }
    result = result.intersected(QRectF(0, 0, window->width(), window->height()));
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) { return {}; }
        if (parent->clip()) {
            if (!parent->clipRect().contains(parent->mapFromScene(center))) { return {}; }
            result = result.intersected(parent->mapRectToScene(parent->clipRect()));
        }
    }
    return result.contains(center) ? result : QRectF();
}

QString identify(QQuickItem* item, bool hud) {
    const auto name = item->objectName();
    if (hud) {
        static const QHash<QString, QString> fields {
            { "PhoneAddressField", "address.field" }, { "PhoneAddressGoButton", "address.go" },
            { "PhoneAddressCancelButton", "address.cancel" }, { "PhoneAddressBackButton", "address.back" },
            { "OverteTabletOpen", "hud.tablet" },
        };
        if (fields.contains(name)) { return fields.value(name); }
        if (item->property("text").toString() == QStringLiteral("GO TO")
                && item->metaObject()->indexOfSignal("clicked()") >= 0) { return QStringLiteral("hud.goto"); }
    } else {
        static const QHash<QString, QString> controls {
            { "nav.home", "tablet.home" }, { "goBack", "places.back" }, { "goForward", "places.forward" },
            { "nav.close", "tablet.close" }, { "OverteTabletClose", "tablet.close" },
        };
        if (controls.contains(name)) { return controls.value(name); }
        if (item->property("text").toString() == QStringLiteral("PLACES")
                && item->metaObject()->indexOfSignal("clicked()") >= 0) { return QStringLiteral("tablet.places"); }
        for (int page = 1; page <= 32; ++page) {
            if (name == QStringLiteral("tabletPage.%1").arg(page)) { return QStringLiteral("tablet.page.%1").arg(page); }
        }
    }
    return {};
}

bool enabled(QQuickItem* item) {
    const auto button = item->property("buttonEnabled");
    return item->isEnabled() && (!button.isValid() || button.toBool());
}

bool integer(const QJsonValue& value, qint64& result) {
    const double number = value.toDouble(-1);
    if (!value.isDouble() || !std::isfinite(number) || number < 0
            || number > 9007199254740991.0 || std::floor(number) != number) { return false; }
    result = static_cast<qint64>(number);
    return true;
}

} // namespace

NormalUiInput::NormalUiInput() : _instance(nonce()) { _clock.start(); }

bool NormalUiInput::guiThread() const { return qApp && QThread::currentThread() == qApp->thread(); }

QJsonObject NormalUiInput::observe(QQuickItem* hud, QQuickItem* tablet, bool tabletShown) {
    if (!guiThread()) { return {}; }
    if (_hud != hud || _tablet != tablet || _tabletShown != tabletShown) { _controls.clear(); }
    _hud = hud; _tablet = tablet; _tabletShown = tabletShown;
    QHash<QString, Control> controls;
    int visited { 0 };
    bool ambiguous { false };
    std::function<void(QQuickItem*, int, bool)> walk = [&](QQuickItem* node, int depth, bool hudTree) {
        if (!node || ambiguous) { return; }
        if (++visited > 4096 || depth > 128 || node->thread() != qApp->thread()) { ambiguous = true; return; }
        if (!visibleBounds(node).isEmpty()) {
            const auto id = identify(node, hudTree);
            if (!id.isEmpty()) {
                if (controls.contains(id)) { ambiguous = true; return; }
                const auto old = _controls.value(id);
                const auto token = old.item == node && old.window == node->window() ? old.token : nonce();
                controls.insert(id, { node, node->window(), token });
            }
        }
        const auto children = node->childItems();
        for (auto child : children) { walk(child, depth + 1, hudTree); }
    };
    if (hud) { walk(hud, 0, true); }
    if (tabletShown && tablet && tablet != hud) { walk(tablet, 0, false); }
    // A modal editor and the tablet cover the underlying world toolbar.
    if (tabletShown || controls.contains(QStringLiteral("address.field"))) {
        controls.remove(QStringLiteral("hud.goto"));
        controls.remove(QStringLiteral("hud.tablet"));
    }
    if (controls.contains(QStringLiteral("address.field"))) {
        for (const auto& id : controls.keys()) {
            if (id.startsWith(QStringLiteral("tablet.")) || id.startsWith(QStringLiteral("places."))) {
                controls.remove(id);
            }
        }
    }
    if (ambiguous) { controls.clear(); }
    _controls = controls;
    auto ids = controls.keys(); std::sort(ids.begin(), ids.end());
    QJsonArray observed;
    for (const auto& id : ids) {
        const auto control = controls.value(id);
        const auto bounds = visibleBounds(control.item);
        observed.append(QJsonObject { { "id", id }, { "token", control.token },
            { "enabled", enabled(control.item) }, { "focused", control.item->hasActiveFocus() },
            { "frame", QJsonObject { { "x", bounds.x() }, { "y", bounds.y() },
                { "width", bounds.width() }, { "height", bounds.height() } } } });
    }
    return { { "schemaVersion", 1 }, { "instance", _instance },
        { "frameSpace", QStringLiteral("qt-window-logical") },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "sampleEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
        { "elapsedMs", static_cast<double>(_clock.elapsed()) }, { "lastSequence", static_cast<double>(_sequence) },
        { "tabletShown", tabletShown }, { "ready", !ambiguous && hud && hud->window() }, { "controls", observed } };
}

QQuickItem* NormalUiInput::item(const QString& controlId, const QString& token) {
    if (!guiThread()) { return nullptr; }
    observe(_hud, _tablet, _tabletShown);
    const auto control = _controls.value(controlId);
    return control.token == token && control.item && control.item->window() == control.window
        && !visibleBounds(control.item).isEmpty() ? control.item.data() : nullptr;
}

QRectF NormalUiInput::projectedFrame(const QString& controlId, const QString& token,
                                   const QRectF& windowBounds, const QRectF& safeBounds) {
    auto control = item(controlId, token);
    const auto finite = [](const QRectF& rect) {
        return std::isfinite(rect.x()) && std::isfinite(rect.y())
            && std::isfinite(rect.width()) && std::isfinite(rect.height());
    };
    if (!control || !finite(windowBounds) || !finite(safeBounds) || windowBounds.isEmpty()
            || safeBounds.isEmpty() || !windowBounds.contains(safeBounds)) { return {}; }
    auto window = control->window();
    if (!window || window->width() <= 0 || window->height() <= 0) { return {}; }
    const auto source = visibleBounds(control);
    const double sx = windowBounds.width() / window->width();
    const double sy = windowBounds.height() / window->height();
    return QRectF(windowBounds.x() + source.x() * sx, windowBounds.y() + source.y() * sy,
                  source.width() * sx, source.height() * sy).intersected(safeBounds);
}

bool NormalUiInput::press(const QString& controlId, const QString& token) {
    auto control = item(controlId, token);
    if (!control || !enabled(control)) { return false; }
    QPointer<QQuickWindow> window(control->window());
    const auto position = control->mapToScene(QPointF(control->width() / 2, control->height() / 2));
    QMouseEvent down(QEvent::MouseButtonPress, position, position, position,
        Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    const bool delivered = QCoreApplication::sendEvent(window, &down);
    if (window) {
        QMouseEvent up(QEvent::MouseButtonRelease, position, position, position,
            Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
        QCoreApplication::sendEvent(window, &up);
    }
    return delivered;
}

QJsonObject NormalUiInput::edit(const QJsonObject& command) {
    if (!guiThread()) { return {}; }
    const auto action = command.value("operation").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "instance", "sequence", "observedElapsedMs", "fieldToken", "operation" };
    if (action == QStringLiteral("replace")) { expected.insert(QStringLiteral("text")); }
    const auto keys = command.keys();
    qint64 sequence { 0 }, observed { 0 };
    const auto id = command.value("commandId").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "commandId", id }, { "instance", _instance },
        { "sequence", command.value("sequence") }, { "performed", false },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "sampleEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) } };
    if (QSet<QString>(keys.begin(), keys.end()) != expected || command.value("schemaVersion") != QJsonValue(1)
            || QUuid(id).isNull() || QUuid(id).toString(QUuid::WithoutBraces) != id
            || command.value("instance") != QJsonValue(_instance)
            || !integer(command.value("sequence"), sequence) || sequence != _sequence + 1
            || !integer(command.value("observedElapsedMs"), observed) || observed > _clock.elapsed()
            || _clock.elapsed() - observed > 5000 || (action != "replace" && action != "submit")) { return result; }
    _sequence = sequence;
    auto field = item(QStringLiteral("address.field"), command.value("fieldToken").toString());
    if (!field || !enabled(field)) { return result; }
    if (action == QStringLiteral("replace") && command.value("text").isString()) {
        result["performed"] = overte::ui::replaceFocusedField(field, field->window(), command.value("text").toString());
    } else if (action == QStringLiteral("submit")) {
        result["performed"] = overte::ui::submitFocusedField(field, field->window());
    }
    return result;
}

bool NormalUiInput::validRequest(const QJsonObject& command) {
    const auto operation = command.value("operation").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "action", "operation" };
    if (operation == QStringLiteral("edit")) { expected.insert(QStringLiteral("input")); }
    const auto keys = command.keys();
    if (QSet<QString>(keys.begin(), keys.end()) != expected
            || command.value("schemaVersion") != QJsonValue(1)
            || command.value("action") != QJsonValue(QStringLiteral("normal-ui-input"))
            || !QRegularExpression(QStringLiteral("^ios-[0-9a-f]{32}$"))
                .match(command.value("commandId").toString()).hasMatch()
            || QJsonDocument(command).toJson(QJsonDocument::Compact).size() > 32768) { return false; }
    if (operation == QStringLiteral("observe")) { return true; }
    if (operation != QStringLiteral("edit") || !command.value("input").isObject()) { return false; }
    const auto input = command.value("input").toObject();
    const auto action = input.value("operation").toString();
    QSet<QString> inputKeys { "schemaVersion", "commandId", "instance", "sequence",
        "observedElapsedMs", "fieldToken", "operation" };
    if (action == QStringLiteral("replace")) { inputKeys.insert(QStringLiteral("text")); }
    const auto actual = input.keys();
    qint64 sequence { 0 }, observed { 0 };
    const auto uuid = [](const QJsonValue& value) {
        const auto id = value.toString();
        return !QUuid(id).isNull() && QUuid(id).toString(QUuid::WithoutBraces) == id;
    };
    if (QSet<QString>(actual.begin(), actual.end()) != inputKeys
            || input.value("schemaVersion") != QJsonValue(1)
            || !uuid(input.value("commandId")) || !uuid(input.value("instance"))
            || !uuid(input.value("fieldToken"))
            || !integer(input.value("sequence"), sequence) || sequence < 1
            || !integer(input.value("observedElapsedMs"), observed)) { return false; }
    if (action == QStringLiteral("submit")) { return true; }
    if (action != QStringLiteral("replace") || !input.value("text").isString()) { return false; }
    const auto text = input.value("text").toString();
    if (text.size() > 4096) { return false; }
    for (int index = 0; index < text.size(); ++index) {
        const auto character = text.at(index);
        if (character.unicode() < 32 || character.unicode() == 127 || character.isLowSurrogate()) { return false; }
        if (character.isHighSurrogate() && (++index >= text.size() || !text.at(index).isLowSurrogate())) { return false; }
    }
    return true;
}

QJsonObject NormalUiInput::request(const QJsonObject& command) {
    if (!guiThread() || !validRequest(command)) { return {}; }
    const auto operation = command.value("operation").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "commandId", command.value("commandId") } };
    if (operation == QStringLiteral("observe")) { result["observation"] = observe(_hud, _tablet, _tabletShown); }
    else { result["status"] = edit(command.value("input").toObject()); }
    return result;
}

} // namespace overte::ios
