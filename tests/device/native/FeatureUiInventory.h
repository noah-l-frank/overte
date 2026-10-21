// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalLoginControls.h"
#include "NormalGraphicsControls.h"
#include <QHash>
#include <QJsonArray>
#include <QPointer>
#include <QQuickWindow>
#include <QJSValue>
#include <QSet>
#include <QUuid>
#include <algorithm>
#include <functional>

namespace overte::e2e {
// Weak tracking never extends a product dialog's lifetime. Detached/hidden
// objects remain resources until their actual QObject destruction is observed.
class FeatureUiInventory {
public:
    enum class Kind { Login, Graphics };
    explicit FeatureUiInventory(Kind kind=Kind::Login) : _kind(kind) {}
private:
    Kind _kind;

public:
    QJsonObject observe(QQuickItem* root,QQuickWindow* window) {
        if (!qApp || QThread::currentThread()!=qApp->thread()) { return {}; }
        bool complete=root && window && root->window()==window && root->thread()==qApp->thread()
            && window->thread()==qApp->thread();
        for (auto i=_known.begin();i!=_known.end();) {
            if (!i.value().item) { _retired.insert(i.value().id);i=_known.erase(i); }
            else { ++i; }
        }
        QSet<QQuickItem*> seen;int count {0};
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if (!item || !complete) { return; }
            if (++count>4096 || depth>128 || seen.contains(item) || item->thread()!=qApp->thread()) { complete=false;return; }
            seen.insert(item);
            const bool menu=item->objectName()=="tabletMenuHandlerItem"
                && QString::fromLatin1(item->metaObject()->className()).startsWith("TabletMenuStack_QMLTYPE_");
            const bool login=_kind==Kind::Login && (genericLoginRoot(item)==item || phoneLoginPage(item)==item);
            const bool graphics=_kind==Kind::Graphics && graphicsPage(item)==item;
            if (login || graphics || menu) {
                if (!_known.contains(item)) {
                    if (_known.size()>=16) { complete=false;return; }
                    _known.insert(item,{item,QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),
                        menu ? QStringLiteral("tablet-menu-v1") : graphics
                            ? graphicsProfile(item)=="generic-immediate-v1" ? QStringLiteral("graphics-generic-v1") : QStringLiteral("graphics-phone-v1")
                            : genericLoginRoot(item)==item ? QStringLiteral("qml-login-v1") : QStringLiteral("phone-login-v1")});
                }
            }
            for (auto child:item->childItems()) { walk(child,depth+1); }
        };
        if (complete) {
            walk(root,0);
            if (root->parentItem()==window->contentItem()) {
                for (auto layer:window->contentItem()->childItems()) {
                    if (layer!=root && layer->inherits("QQuickOverlay")) { walk(layer,0); }
                }
            }
        }
        complete=complete && _retired.size()<=256;
        for (const auto& row:_known) {
            if (!row.item || row.item->thread()!=qApp->thread()) { complete=false; }
        }
        QJsonArray roots,retired;
        auto ids=_retired.values();std::sort(ids.begin(),ids.end());
        if (complete) {
            for (const auto& id:ids) { retired.append(id); }
            QList<Tracked> tracked=_known.values();
            std::sort(tracked.begin(),tracked.end(),[](const Tracked& a,const Tracked& b) { return a.id<b.id; });
            for (const auto& row:tracked) {
                bool visible=row.item && row.item->isVisible();int depth {0};
                for (auto node=row.item.data();node && visible;node=node->parentItem()) {
                    if (++depth>128 || !node->isVisible() || node->opacity()<=0.01) { visible=false; }
                }
                bool running {false},pending {false};
                if (row.profile=="tablet-menu-v1" && !menuCallback(row.item,running,pending)) { complete=false;break; }
                if (row.profile=="graphics-generic-v1" && !graphicsCallback(row.item,running,pending)) { complete=false;break; }
                roots.append(QJsonObject {{"id",row.id},{"profile",row.profile},{"visible",visible},
                    {"inCurrentTree",seen.contains(row.item.data())},{"callbackRunning",running},{"callbackItemPresent",pending}});
            }
        }
        return {{"inventoryVersion",1},{"complete",complete},{"roots",complete ? roots : QJsonArray()},
            {"retiredRoots",complete ? retired : QJsonArray()}};
    }
private:
    struct Tracked { QPointer<QQuickItem> item;QString id,profile; };
    static QObject* object(const QVariant& value) {
        auto result=value.value<QObject*>();
        return result ? result : value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toQObject() : nullptr;
    }
    static bool graphicsCallback(QQuickItem* root,bool& running,bool& pending) {
        QObject* timer {nullptr};int visited {0};bool complete {true};
        std::function<void(QObject*,int)> walk=[&](QObject* node,int depth) {
            if (!node || !complete) { return; }
            if (++visited>4096 || depth>128 || node->thread()!=qApp->thread()) { complete=false;return; }
            int contextDepth {0};
            for (auto context=qmlContext(node);context;context=context->parentContext()) {
                if (++contextDepth>128) { complete=false;return; }
                if (context->nameForObject(node)=="verticalScrollBarInitialVisibilityTimer") {
                    if (timer && timer!=node) { complete=false;return; }timer=node;break;
                }
            }
            for (auto child:node->children()) { walk(child,depth+1); }
        };
        walk(root,0);
        if (!complete || !timer || timer->property("running").userType()!=QMetaType::Bool) { return false; }
        bool parented {false};int depth {0};
        for (auto parent=timer->parent();parent && ++depth<=128;parent=parent->parent()) {
            if (parent==root) { parented=true;break; }
        }
        if (!parented) { return false; }
        running=timer->property("running").toBool();
        // This original timer has no retained menuItem target. The complete
        // Graphics root remains a resource until its actual QObject deletion.
        pending=object(timer->property("menuItem"))!=nullptr;
        return true;
    }
    static bool menuCallback(QQuickItem* root,bool& running,bool& pending) {
        QQuickItem* stack {nullptr};
        for (auto child:root->childItems()) {
            if (child->objectName()=="stack" && loginQmlId(child,"d")) {
                if (stack) { return false; }stack=child;
            }
        }
        const auto timer=stack ? object(stack->property("delay")) : nullptr;
        if (!timer || timer->thread()!=qApp->thread() || timer->property("running").userType()!=QMetaType::Bool
                || timer->metaObject()->indexOfProperty("menuItem")<0) { return false; }
        bool parented {false};int depth {0};
        for (auto parent=timer->parent();parent && ++depth<=128;parent=parent->parent()) {
            if (parent==stack) { parented=true;break; }
        }
        if (!parented) { return false; } // Root destruction must also destroy its retained timer.
        running=timer->property("running").toBool();
        const auto value=timer->property("menuItem");
        pending=object(value)!=nullptr;
        if (!pending && value.userType()==qMetaTypeId<QJSValue>()) {
            const auto script=value.value<QJSValue>();
            if (!script.isNull() && !script.isUndefined()) { return false; }
        } else if (!pending && !value.isNull()) { return false; }
        return true;
    }
    QHash<QQuickItem*,Tracked> _known;
    QSet<QString> _retired;
};
inline FeatureUiInventory& graphicsUiInventory() {
    static FeatureUiInventory source {FeatureUiInventory::Kind::Graphics};
    return source;
}
}
#endif
