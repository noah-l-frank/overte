// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QGuiApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QThread>
#include <algorithm>
#include <cmath>
#include <functional>
namespace overte::e2e {
// Fixed Phone5527 handler traversal adapted to the actual Pico scene. Opaque
// foreign drawn items and unproven negative-z branches conservatively refuse.
inline bool picoAvatarInputOwnsPoint(QQuickItem* item,QQuickWindow* window,const QPointF& point) {
    if (!item || !window || !qApp || item->window()!=window || item->thread()!=qApp->thread()
            || window->thread()!=qApp->thread() || QThread::currentThread()!=qApp->thread()
            || !std::isfinite(point.x()) || !std::isfinite(point.y())) {return false;}
    int visited=0;bool invalid=false;QQuickItem* recipient=nullptr;
    std::function<bool(QQuickItem*,int)> visit=[&](QQuickItem* node,int depth) {
        if (!node || !node->isVisible()) {return false;}
        if (++visited>4096 || depth>128 || node->thread()!=qApp->thread() || !std::isfinite(node->z()) || !std::isfinite(node->x()) || !std::isfinite(node->y()) || !std::isfinite(node->width()) || !std::isfinite(node->height())) {invalid=true;return true;}
        const bool inside=node->contains(node->mapFromScene(point));if (node->clip() && !inside) {return false;}
        auto children=node->childItems();for (auto child:children) {if (child->thread()!=qApp->thread() || !std::isfinite(child->z())) {invalid=true;return true;}}
        std::stable_sort(children.begin(),children.end(),[](QQuickItem* a,QQuickItem* b){return a->z()<b->z();});
        for (auto it=children.crbegin();it!=children.crend();++it) {if ((*it)->z()>=0 && visit(*it,depth+1)) {return true;}}
        bool handler=false;
        if (node->isEnabled()) {for (auto child:node->children()) {if (child->inherits("QQuickPointerHandler") && child->property("enabled").toBool()) {handler=true;}}}
        if (inside && ((node->isEnabled() && (handler || (node->acceptedMouseButtons() & Qt::LeftButton) || node->acceptTouchEvents()))
                || node->flags().testFlag(QQuickItem::ItemHasContents))) {recipient=node;return true;}
        if (inside && std::any_of(children.begin(),children.end(),[](QQuickItem* child){return child->z()<0;})) {invalid=true;return true;}
        for (auto it=children.crbegin();it!=children.crend();++it) {if ((*it)->z()<0 && visit(*it,depth+1)) {return true;}}
        return false;
    };
    visit(window->contentItem(),0);if (invalid || !recipient || !item->isEnabled()) {return false;}
    for (auto parent=recipient;parent;parent=parent->parentItem()) {if (parent==item) {return true;}}return false;
}
}
#endif
