// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QColor>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QPointer>
#include <QQmlProperty>
#include <QQuickItem>
#include <QQuickWindow>
#include <QUuid>
#include <QThread>
#include <cmath>
#include <EntityScriptingInterface.h>
#include <scripting/HMDScriptingInterface.h>

namespace overte::pico::e2e {
// GUI-thread property observation only. This does not assert GPU visibility.
// Original coded world pixels provide the independent visibility observation.
class PicoGraphicsComposition {
public:
    QJsonObject observe(QQuickItem* root,QQuickWindow* window,
            EntityScriptingInterface* entities,HMDScriptingInterface* hmd) {
        const QJsonObject unavailable {{"compositionVersion",1},{"complete",false}};
        if (!qApp || QThread::currentThread()!=qApp->thread() || !root || !window || !entities || !hmd
                || root->window()!=window || root->thread()!=qApp->thread() || window->thread()!=qApp->thread()
                || !root->inherits("QQuickRectangle") || root->objectName()!=QStringLiteral("tabletRoot")) { return unavailable; }
        const auto screenId=hmd->getCurrentTabletScreenID(),frameId=hmd->getCurrentTabletFrameID();
        if (screenId.isNull() || frameId.isNull()) { return unavailable; }
        const auto screen=entities->getEntityProperties(screenId);
        if (screen.getType()!=EntityTypes::Web || screen.getParentID()!=frameId
                || screen.getEntityHostType()!=entity::HostType::LOCAL) { return unavailable; }
        const auto rgba=root->property("color");const auto radius=root->property("radius");
        if (!rgba.canConvert<QColor>() || !radius.isValid() || !std::isfinite(radius.toDouble())) { return unavailable; }
        const auto color=rgba.value<QColor>();
        if (!color.isValid() || !std::isfinite(root->width()) || !std::isfinite(root->height())
                || root->width()<=0 || root->height()<=0 || window->width()<=0 || window->height()<=0) { return unavailable; }
        const auto polygon=[](QQuickItem* item,const QRectF& rect) {
            QJsonArray result;
            for (const auto& point:{rect.topLeft(),rect.topRight(),rect.bottomRight(),rect.bottomLeft()}) {
                const auto original=item->mapToScene(point);
                if (!std::isfinite(original.x()) || !std::isfinite(original.y())) { return QJsonArray(); }
                result.append(QJsonArray{original.x(),original.y()});
            }
            return result;
        };
        QJsonArray ancestors;bool reachedContent {false};
        for (auto node=root;node;node=node->parentItem()) {
            if (ancestors.size()>=128 || node->thread()!=qApp->thread() || node->window()!=window
                    || !std::isfinite(node->opacity())) { return unavailable; }
            // Read the actual public Qt grouped property. No layer setting,
            // mask, opacity, geometry or product input is changed here.
            const auto layer=QQmlProperty::read(node,QStringLiteral("layer.enabled"));
            const auto mask=node->property("containmentMask");
            if (layer.userType()!=QMetaType::Bool || !mask.isValid() || !mask.canConvert<QObject*>()) { return unavailable; }
            const auto clip=node->clip() ? polygon(node,node->clipRect()) : QJsonArray();
            if (node->clip() && clip.size()!=4) { return unavailable; }
            ancestors.append(QJsonObject{{"visible",node->isVisible()},{"opacity",node->opacity()},
                {"layerEnabled",layer.toBool()},{"maskPresent",mask.value<QObject*>()!=nullptr},
                {"clip",node->clip() ? QJsonValue(clip) : QJsonValue(QJsonValue::Null)}});
            if (node==window->contentItem()) { reachedContent=true;break; }
        }
        const auto outline=polygon(root,root->boundingRect());
        if (!reachedContent || outline.size()!=4) { return unavailable; }
        if (_root!=root) {
            _root=root;_birth=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        }
        const auto uuid=[](const QUuid& value) { return value.toString(QUuid::WithoutBraces); };
        return {{"compositionVersion",1},{"complete",true},
            {"screen",QJsonObject{{"id",uuid(screenId)},{"parentId",uuid(frameId)},{"type",QStringLiteral("Web")},
                {"hostType",QStringLiteral("local")},{"visible",screen.getVisible()},{"alpha",screen.getAlpha()},
                {"useBackground",screen.getUseBackground()},{"pulseAlphaMode",static_cast<int>(screen.getPulse().getAlphaMode())}}},
            {"root",QJsonObject{{"id",_birth},{"class",QString::fromLatin1(root->metaObject()->className())},
                {"objectName",root->objectName()},{"color",QJsonArray{color.redF(),color.greenF(),color.blueF(),color.alphaF()}},
                {"radius",radius.toDouble()},{"width",root->width()},{"height",root->height()},{"quad",outline}}},
            {"viewport",QJsonArray{window->width(),window->height()}},{"ancestors",ancestors}};
    }
private:
    QPointer<QQuickItem> _root;
    QString _birth;
};
}
#endif
