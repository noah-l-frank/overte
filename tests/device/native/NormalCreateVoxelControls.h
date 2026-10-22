// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <PathUtils.h>

namespace overte::e2e {
inline QQuickItem* createVoxelPage(QQuickItem* item) {
    auto page=createPage(item);
    const auto expected=PathUtils::defaultScriptsLocation().resolved(QUrl("system/create/qml/NativeCreate.qml"));
    if (!page || page->property("currentTab").toInt()!=3 || QUrl(createComponentSource(page))!=expected) {return nullptr;}
    const auto receipt=page->property("e2eSettingsReceived");
    if (receipt.userType()!=QMetaType::Bool || !receipt.toBool()) {return nullptr;}
    int depth{0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->isValid() && context->baseUrl()==expected && context->nameForObject(page)=="root") {return page;}
    }
    return nullptr;
}
inline int createVoxelCount(const QString& id) {
    return id=="create-voxel.shape" ? 3
        : id=="create-voxel.mode" || id=="create-voxel.dynamics" || id=="create-voxel.pointer" ? 2 : 0;
}
inline bool createVoxelField(const QString& id) {return id=="create-voxel.diameter" || id=="create-voxel.reach";}
inline bool createVoxelText(const QString& id,const QString& text) {
    bool valid{false};const auto value=text.toDouble(&valid);
    return createVoxelField(id) && valid && text.size()<=40 && std::isfinite(value) && value<=100
        && (id=="create-voxel.diameter" ? value>0 : value>=0)
        && QRegularExpression("\\A(?:0|[1-9][0-9]{0,2})(?:\\.[0-9]{1,17})?(?:e[+-]?[0-9]{1,2})?\\z").match(text).hasMatch();
}
inline QString createVoxelControlId(QQuickItem* item) {
    if (!createVoxelPage(item)) {return {};}
    const QHash<QString,QString> fixed{{"NativeCreateEditMode","mode"},{"NativeCreateVoxelShape","shape"},
        {"NativeCreateVoxelDynamics","dynamics"},{"NativeCreateVoxelPointer","pointer"},
        {"NativeCreateVoxelRemove","remove"},{"NativeCreateVoxelDiameter","diameter"},
        {"NativeCreateVoxelReach","reach"},{"NativeCreateVoxelApply","apply"}};
    const auto suffix=fixed.value(item->objectName());if (suffix.isEmpty()) {return {};}
    const auto id="create-voxel."+suffix;
    return (createVoxelCount(id) ? item->inherits("QQuickComboBox") : createVoxelField(id) ? item->inherits("QQuickTextInput")
        : id=="create-voxel.remove" ? item->inherits("QQuickCheckBox") : item->inherits("QQuickButton")) ? id : QString{};
}
inline QVariantMap createVoxelSettings(QQuickItem* item) {
    auto page=createVoxelPage(item);if (!page) {return {};}
    const auto raw=createVariant(page->property("voxelSettings"));if (raw.userType()!=QMetaType::QVariantMap) {return {};}
    const auto value=raw.toMap();QStringList keys{"createAppMode","voxelEditMode","voxelSphereSize","voxelEditDynamics","voxelRemove","voxelPointerMode","voxelBrushLength"};keys.sort();
    if (value.keys()!=keys || value.value("voxelRemove").userType()!=QMetaType::Bool) {return {};}
    const QHash<QString,QStringList> enums{{"createAppMode",{"object","voxel"}},{"voxelEditMode",{"single","sphere","cube"}},
        {"voxelEditDynamics",{"click","continuous"}},{"voxelPointerMode",{"laser","brush"}}};
    for (auto it=enums.cbegin();it!=enums.cend();++it) {
        if (value.value(it.key()).userType()!=QMetaType::QString || !it.value().contains(value.value(it.key()).toString())) {return {};}
    }
    for (const auto& key:{"voxelSphereSize","voxelBrushLength"}) {
        const auto number=value.value(key);const auto v=number.toDouble();
        if ((number.userType()!=QMetaType::Double && number.userType()!=QMetaType::Int) || !std::isfinite(v) || (v==0 && std::signbit(v)) || v>100
                || (QString(key)=="voxelSphereSize" ? v<=0 : v<0)
                || !createVoxelText(QString(key)=="voxelSphereSize" ? "create-voxel.diameter" : "create-voxel.reach",QString::number(v,'g',17))) {return {};}
    }
    return value;
}
inline void appendCreateVoxelObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (createVoxelControlId(item)!=id) {return;}
    bool ready=item->isEnabled();
    if (createVoxelCount(id)) {
        const auto count=item->property("count"),index=item->property("currentIndex");
        const bool valid=count.userType()==QMetaType::Int && count.toInt()==createVoxelCount(id)
            && index.userType()==QMetaType::Int && index.toInt()>=0 && index.toInt()<count.toInt();
        if (valid) {row["count"]=count.toInt();row["currentIndex"]=index.toInt();}ready=ready && valid;
        if (id=="create-voxel.mode") {
            const auto settings=createVoxelSettings(item);if (!settings.isEmpty()) {row["settings"]=QJsonObject::fromVariantMap(settings);}
            ready=ready && !settings.isEmpty();
        }
    } else if (createVoxelField(id)) {
        const auto text=item->property("text"),readOnly=item->property("readOnly");
        const bool valid=text.userType()==QMetaType::QString && createVoxelText(id,text.toString()) && readOnly.userType()==QMetaType::Bool;
        if (valid) {row["text"]=text.toString();}ready=ready && valid && !readOnly.toBool();
    } else if (id=="create-voxel.remove") {
        const auto checked=item->property("checked");if (checked.userType()==QMetaType::Bool) {row["checked"]=checked.toBool();}
        ready=ready && checked.userType()==QMetaType::Bool;
    }
    row["inputReady"]=ready;
}
inline QString createVoxelControlSource(QQuickItem* item,const QString& id) {
    if (createVoxelControlId(item)!=id || !item->window()) {return {};}
    const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(point.x()) || !std::isfinite(point.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) {return {};}
    QJsonObject value;appendCreateVoxelObservation(value,item,id);
    value["component"]=createComponentSource(createVoxelPage(item));value["sceneX"]=point.x();value["sceneY"]=point.y();
    value["width"]=item->width();value["height"]=item->height();value["window"]=QString::number(reinterpret_cast<quintptr>(item->window()),16);
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
#endif
