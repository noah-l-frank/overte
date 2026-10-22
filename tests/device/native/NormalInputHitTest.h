// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QGuiApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <algorithm>
#include <cmath>
#include <functional>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
// Shared original Avatar/People scene-input algorithm. Traverse actual stacking
// order, ignoring only branches without enabled input at the requested point.
// Callers retain their own original component/field/role and visibility guards.
inline bool normalInputOwnsPoint(QQuickItem* item,QQuickWindow* window,const QPointF& point) {
    if (!item || !window || !qApp || item->window()!=window || item->thread()!=qApp->thread()
            || window->thread()!=qApp->thread() || QThread::currentThread()!=qApp->thread()
            || !std::isfinite(point.x()) || !std::isfinite(point.y())) { return false; }
    int visited=0;bool invalid=false;QQuickItem* recipient{nullptr};
    std::function<bool(QQuickItem*,int)> visit=[&](QQuickItem* node,int depth) {
        if (!node || !node->isVisible() || !node->isEnabled()) { return false; }
        if (++visited>4096 || depth>128 || node->thread()!=qApp->thread()) { invalid=true;return true; }
        const bool inside=node->contains(node->mapFromScene(point));if (node->clip() && !inside) { return false; }
        auto children=node->childItems();std::stable_sort(children.begin(),children.end(),[](QQuickItem* a,QQuickItem* b) { return a->z()<b->z(); });
        for (auto it=children.crbegin();it!=children.crend();++it) { if (visit(*it,depth+1)) { return true; } }
        bool handler=false;for (auto child:node->children()) { if (child->inherits("QQuickPointerHandler") && child->property("enabled").toBool()) { handler=true; } }
        if (inside && (handler || (node->acceptedMouseButtons() & Qt::LeftButton) || node->acceptTouchEvents())) { recipient=node;return true; }
        return false;
    };
    visit(window->contentItem(),0);if (invalid || !recipient) { return false; }
    for (auto parent=recipient;parent;parent=parent->parentItem()) { if (parent==item) { return true; } }return false;
}
#endif
} // namespace overte::e2e
