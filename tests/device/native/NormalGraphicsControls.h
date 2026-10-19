// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Read-only identities for actual immediate Graphics controls. The platform
// owner supplies original Render settings; these are not rendered-pass proof.
#include "NormalAudioControls.h"
#include <cmath>

namespace overte::e2e {
struct GraphicsUiContext {
    bool valid {false}, haze {false}, mirrors {false};
    double resolution {0};
    static GraphicsUiContext fromNative(double resolution, bool haze, bool mirrors) {
        GraphicsUiContext result;
#if defined(OVERTE_E2E_FEATURE_TESTS)
        if (qApp && QThread::currentThread() == qApp->thread()
                && QCoreApplication::arguments().contains("--testScript")
                && std::isfinite(resolution) && resolution >= 0.1 && resolution <= 2.0) {
            result.valid = true; result.resolution = resolution; result.haze = haze; result.mirrors = mirrors;
        }
#else
        Q_UNUSED(resolution) Q_UNUSED(haze) Q_UNUSED(mirrors)
#endif
        return result;
    }
};

inline QQuickItem* graphicsPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto node = item; node && ++depth <= 128; node = node->parentItem()) {
        if (node->objectName() == "settings.graphics" && node->inherits("QQuickFlickable")) {
            if (node->property("ready").userType() == QMetaType::Bool && node->property("values").isValid()) { return node; }
            if (node->property("isChangingPreset").userType() == QMetaType::Bool
                    && node->property("hasPresetBeenModified").userType() == QMetaType::Bool) { return node; }
        }
    }
    return nullptr;
}

inline QString graphicsProfile(QQuickItem* item) {
    auto page = graphicsPage(item);
    return !page ? QString() : page->property("ready").userType() == QMetaType::Bool
        ? QStringLiteral("phone-immediate-v1") : QStringLiteral("generic-immediate-v1");
}

inline QString graphicsControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    const auto page = graphicsPage(item);
    if (!page) {
        if (item->objectName() == "settings.graphics" && item->property("semanticId").toString() == "settings.graphics"
                && item->property("pageName").toString() == "Graphics" && item->property("targetPage").toString().isEmpty()) {
            return "graphics.settings-entry";
        }
        return audioControlId(item) == "settings.entry" ? QStringLiteral("settings.entry") : QString();
    }
    if (page == item) { return "graphics.page"; }
    if (item->inherits("QQuickSlider") && item->property("orientation").toInt() == Qt::Horizontal) {
        if (item->objectName() == "settings.graphics.resolutionScale") { return "graphics.resolution"; }
        for (auto parent = item->parentItem(); parent && parent != page; parent = parent->parentItem()) {
            if (parent->property("settingText").toString() == "Resolution scale"
                    && parent->property("sliderStepSize").isValid()) { return "graphics.resolution"; }
        }
    }
    if (item->inherits("QQuickSwitch")) {
        for (auto node = item; node && node != page; node = node->parentItem()) {
            if (node->objectName() == "settings.graphics.haze") { return "graphics.haze"; }
            if (node->objectName() == "settings.graphics.mirrors") { return "graphics.mirrors"; }
        }
    }
    if (item->inherits("QQuickScrollBar") && item->property("orientation").toInt() == Qt::Vertical) { return "graphics.scrollbar"; }
    return {};
}

inline QString graphicsViewport(QQuickItem* item) {
    if (!audioGuiItem(item) || !item->window() || item->width() <= 0 || item->height() <= 0) { return "outside"; }
    auto window = item->window();
    QRectF viewport(0,0,window->width(),window->height());
    if (!item->isVisible() || !std::isfinite(item->opacity()) || item->opacity() <= 0.01) { return "outside"; }
    for (auto parent=graphicsPage(item)==item ? item : item->parentItem();parent;parent=parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) { return "outside"; }
        if (parent->clip()) { viewport=viewport.intersected(parent->mapRectToScene(parent->clipRect())); }
    }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (viewport.isEmpty() || !std::isfinite(center.x()) || !std::isfinite(center.y())
            || center.x()<viewport.left() || center.x()>viewport.right()) { return "outside"; }
    if (center.y()<viewport.top()) { return "above"; }
    if (center.y()>viewport.bottom()) { return "below"; }
    return "visible";
}

inline bool graphicsObservable(QQuickItem* item) {
    return !graphicsControlId(item).isEmpty() && graphicsViewport(item) != "outside";
}

inline bool graphicsSliderRange(QQuickItem* item, double& low, double& high, double& step) {
    if (graphicsControlId(item) != "graphics.resolution") { return false; }
    low = item->property("from").toDouble(); high = item->property("to").toDouble(); step = item->property("stepSize").toDouble();
    return std::isfinite(low) && std::isfinite(high) && std::isfinite(step)
        && low >= 0.1-1e-6 && high <= 2.0+1e-6 && high > low && step > 0 && step <= high-low;
}

inline bool graphicsSliderPoint(QQuickItem* item, double value, QPointF& point) {
    double low {0}, high {0}, step {0};
    if (!std::isfinite(value) || !graphicsSliderRange(item, low, high, step)
            || value < low-1e-6 || value > high+1e-6 || std::abs((value-low)/step-std::round((value-low)/step)) > 1e-4) { return false; }
    auto handle = qobject_cast<QQuickItem*>(item->property("handle").value<QObject*>());
    if (!handle || handle->parentItem() != item || !handle->isVisible()) { return false; }
    double fraction = (value-low)/(high-low);
    if (item->property("mirrored").toBool()) { fraction = 1-fraction; }
    const double left = item->property("leftPadding").toDouble(), top = item->property("topPadding").toDouble();
    const double width = item->property("availableWidth").toDouble(), height = item->property("availableHeight").toDouble();
    if (!std::isfinite(left) || !std::isfinite(top) || !std::isfinite(width) || !std::isfinite(height)
            || width <= handle->width() || handle->width() <= 0 || height <= 0) { return false; }
    point = item->mapToScene(QPointF(left+handle->width()/2+fraction*(width-handle->width()), top+height/2));
    return std::isfinite(point.x()) && std::isfinite(point.y()) && item->contains(item->mapFromScene(point));
}

inline bool graphicsScrollPoint(QQuickItem* item, const QString& direction, QPointF& point) {
    if (graphicsControlId(item) != "graphics.scrollbar" || (direction != "up" && direction != "down")) { return false; }
    auto thumb = qobject_cast<QQuickItem*>(item->property("contentItem").value<QObject*>());
    if (!thumb || thumb->parentItem() != item || !thumb->isVisible() || !item->isEnabled()) { return false; }
    const auto rect = thumb->mapRectToItem(item, QRectF(0, 0, thumb->width(), thumb->height()));
    if (!std::isfinite(rect.top()) || !std::isfinite(rect.bottom()) || rect.top() < 0 || rect.bottom() > item->height()) { return false; }
    const double low = direction == "up" ? 0 : rect.bottom(), high = direction == "up" ? rect.top() : item->height();
    if (high-low < 2) { return false; }
    point = item->mapToScene(QPointF(item->width()/2,(low+high)/2));
    return std::isfinite(point.x()) && std::isfinite(point.y());
}

inline void appendGraphicsControlObservation(QJsonObject& row, QQuickItem* item, const QString& id, const GraphicsUiContext& context) {
    if (!audioGuiItem(item)) { return; }
    const auto page = graphicsPage(item);
    const auto profile = graphicsProfile(item);
    const auto viewport = graphicsViewport(item);
    row["viewport"] = viewport;
    bool ready = context.valid && item->isEnabled() && id != "graphics.page" && viewport == "visible";
    if (page) {
        const auto moving = page->property("moving"), dragging = page->property("dragging");
        ready = ready && moving.userType() == QMetaType::Bool && dragging.userType() == QMetaType::Bool
            && !moving.toBool() && !dragging.toBool()
            && (profile == "phone-immediate-v1" ? page->property("ready").toBool() : !page->property("isChangingPreset").toBool());
    }
    if (id == "graphics.page") { row["profile"] = profile; }
    else if (id == "graphics.resolution") {
        double low {0}, high {0}, step {0};
        const bool range = graphicsSliderRange(item, low, high, step);
        const auto value = item->property("value").toDouble();
        row["value"] = value; row["nativeValue"] = context.resolution;
        row["minimum"] = low; row["maximum"] = high; row["step"] = step;
        ready = ready && range && std::isfinite(value) && std::abs(value-context.resolution)<1e-4
            && std::abs((value-low)/step-std::round((value-low)/step))<1e-4;
    } else if (id == "graphics.haze" || id == "graphics.mirrors") {
        const bool checked = item->property("checked").toBool(), native = id == "graphics.haze" ? context.haze : context.mirrors;
        row["checked"] = checked; row["nativeChecked"] = native;
        ready = ready && checked == native;
    } else if (id == "graphics.scrollbar") {
        row["position"] = item->property("position").toDouble(); row["size"] = item->property("size").toDouble();
    }
    row["inputReady"] = ready;
}

inline QString graphicsControlSource(QQuickItem* item, const QString& id, const GraphicsUiContext& context) {
    QJsonObject value;
    appendGraphicsControlObservation(value,item,id,context);
    if (value.isEmpty()) { return {}; }
    value["profile"] = graphicsProfile(item);
    if (id == "graphics.resolution" || id == "graphics.scrollbar") {
        value["width"] = item->width(); value["height"] = item->height();
        if (id == "graphics.resolution") {
            for (const auto& key : {"leftPadding","topPadding","availableWidth","availableHeight","mirrored"}) {
                value[key] = QJsonValue::fromVariant(item->property(key));
            }
            auto handle = qobject_cast<QQuickItem*>(item->property("handle").value<QObject*>());
            value["handleWidth"] = handle ? handle->width() : 0;
        }
    }
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
