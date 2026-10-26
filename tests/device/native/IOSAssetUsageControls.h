// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtGlobal>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "IOSAssetTreeControls.h"
#include <EntityScriptingInterface.h>
#include <DependencyManager.h>
#include <NodeList.h>
#include <QMap>
#include <cmath>

namespace overte::e2e::asset_usage_ui {
using asset_bundle_ui::object;
using asset_bundle_ui::property;
inline const QMap<QString,QString>& names() {
    static const QMap<QString,QString> value{{"assets.baking","featureAssetBakingControl"},{"assets.import","featureAssetImportButton"},
        {"assets.import-uploaded","featureAssetUploadedImportButton"},{"assets.model.url","featureAssetModelEditor"},
        {"assets.model.shape","featureAssetModelShape"},{"assets.model.dynamic","featureAssetModelDynamic"},
        {"assets.model.accept","featureAssetModelAccept"},{"assets.model.cancel","featureAssetModelCancel"}};return value;
}
inline QQuickItem* item(QQuickItem* page,const char* name) {
    auto result=qobject_cast<QQuickItem*>(object(page,name));return result && result->window()==page->window() && result->thread()==QThread::currentThread() ? result : nullptr;
}
inline QJsonObject snapshot(QQuickItem* page,bool& complete) {
    if (!asset_ui::enabled() || !asset_tree_ui::tree(page)) {complete=false;return {};}
    auto tree=asset_tree_ui::snapshot(page,complete);if (!complete) {return {};}
    auto baking=item(page,"featureAssetBakingControl"),add=item(page,"featureAssetImportButton"),uploaded=item(page,"featureAssetUploadedImportButton");
    // Hidden popup children may not yet have a scene window. Their actual
    // QObject properties remain readable; visible input requires this window.
    auto editor=qobject_cast<QQuickItem*>(object(page,"featureAssetModelEditor")),shape=qobject_cast<QQuickItem*>(object(page,"featureAssetModelShape")),dynamic=qobject_cast<QQuickItem*>(object(page,"featureAssetModelDynamic"));
    auto dialog=object(page,"featureAssetModelDialog");auto accept=item(page,"featureAssetModelAccept"),cancel=item(page,"featureAssetModelCancel");
    auto entities=qmlContext(page) ? qobject_cast<EntityScriptingInterface*>(qmlContext(page)->contextProperty("Entities").value<QObject*>()) : nullptr;
    const auto nodes=DependencyManager::get<NodeList>();
    if (!baking || !add || !uploaded || !editor || !shape || !dynamic || !dialog || !entities || !nodes
            || entities->thread()!=QThread::currentThread()
            || editor->thread()!=QThread::currentThread() || shape->thread()!=QThread::currentThread() || dynamic->thread()!=QThread::currentThread()
            || entities!=DependencyManager::get<EntityScriptingInterface>().data() || nodes->getSessionUUID().isNull() || nodes->getDomainUUID().isNull()
            || property(baking,"checked").userType()!=QMetaType::Bool || property(dynamic,"checked").userType()!=QMetaType::Bool
            || property(dialog,"visible").userType()!=QMetaType::Bool || property(editor,"text").userType()!=QMetaType::QString
            || property(shape,"currentIndex").userType()!=QMetaType::Int || property(shape,"count").userType()!=QMetaType::Int
            || page->property("importAllowed").userType()!=QMetaType::Bool || page->property("uploadedPrimaryUrl").userType()!=QMetaType::QString
            || page->property("modelName").userType()!=QMetaType::QString) {complete=false;return {};}
    const bool visible=property(dialog,"visible").toBool();QJsonValue position(QJsonValue::Null);
    if (visible && (!accept || !cancel || editor->window()!=page->window() || shape->window()!=page->window() || dynamic->window()!=page->window())) {complete=false;return {};}
    if (visible) {
        const auto actual=property(page,"modelPosition");if (actual.userType()!=QMetaType::QVariantMap) {complete=false;return {};}
        const auto values=actual.toMap();QJsonObject vector;
        if (values.size()!=3) {complete=false;return {};}
        for (const auto key:{"x","y","z"}) {
            const auto value=values.value(key);bool valid=false;const auto number=value.toDouble(&valid);
            if (!valid || value.userType()==QMetaType::Bool || !std::isfinite(number) || std::abs(number)>1e9) {complete=false;return {};}vector[key]=number;
        }
        position=vector;
    }
    QJsonObject selected;
    for (const auto key:{"rootId","windowId","componentSource","treeId","modelId","treeRevision","selectedPaths","currentPath","currentUrl","canWrite","busy"}) {selected[key]=tree.value(key);}
    selected["apiId"]=asset_ui::identity(entities);selected["clientNodeId"]=nodes->getSessionUUID().toString(QUuid::WithoutBraces);
    selected["domainId"]=nodes->getDomainUUID().toString(QUuid::WithoutBraces);
    selected["permissions"]=QJsonObject{{"canWriteAssets",entities->canWriteAssets()},{"canRez",entities->canRez()},{"canRezTmp",entities->canRezTmp()}};
    selected["importAllowed"]=page->property("importAllowed").toBool();selected["uploadedPrimaryUrl"]=page->property("uploadedPrimaryUrl").toString();
    selected["baking"]=QJsonObject{{"id",asset_ui::identity(baking)},{"checked",property(baking,"checked").toBool()},{"enabled",baking->isEnabled()}};
    selected["importButtonId"]=asset_ui::identity(add);selected["importEnabled"]=add->isEnabled();selected["uploadedImportButtonId"]=asset_ui::identity(uploaded);
    selected["uploadedImportVisible"]=uploaded->isVisible();selected["uploadedImportEnabled"]=uploaded->isEnabled();
    selected["model"]=QJsonObject{{"id",asset_ui::identity(dialog)},{"visible",visible},{"urlId",asset_ui::identity(editor)},{"url",property(editor,"text").toString()},
        {"shapeId",asset_ui::identity(shape)},{"shapeIndex",property(shape,"currentIndex").toInt()},{"shapeCount",property(shape,"count").toInt()},
        {"dynamicId",asset_ui::identity(dynamic)},{"dynamicChecked",property(dynamic,"checked").toBool()},{"dynamicEnabled",dynamic->isEnabled()},
        {"name",page->property("modelName").toString()},{"position",position}};return selected;
}
inline QQuickItem* owner(QQuickItem* control) {
    if (!asset_ui::enabled() || !control || !control->window()) {return nullptr;}QQuickItem* result=nullptr;
    for (auto weak:asset_bundle_ui::pages(control->window())) {
        auto page=weak.data();if (!page || !asset_tree_ui::tree(page)) {continue;}
        for (auto it=names().cbegin();it!=names().cend();++it) {
            if (object(page,it.value().toLatin1().constData())!=control) {continue;}if (result && result!=page) {return nullptr;}result=page;
        }
    }
    return result;
}
inline QString control(QQuickItem* target) {
    auto page=owner(target);if (!page) {return {};}
    // An absent new source must not attach an empty v4 row to legacy controls.
    bool complete=true;snapshot(page,complete);if (!complete) {return {};}
    for (auto it=names().cbegin();it!=names().cend();++it) {
        if (object(page,it.value().toLatin1().constData())!=target) {continue;}
        if (it.key()=="assets.model.url") {return target->inherits("QQuickTextInput") && target->property("readOnly")==QVariant(false) ? it.key() : QString();}
        if (it.key()=="assets.model.shape") {return target->inherits("QQuickComboBox") ? it.key() : QString();}
        if (it.key()=="assets.baking" || it.key()=="assets.model.dynamic") {
            return target->metaObject()->indexOfSignal("toggled()")>=0 && target->property("checked").userType()==QMetaType::Bool ? it.key() : QString();
        }
        return target->metaObject()->indexOfSignal("clicked()")>=0 ? it.key() : QString();
    }
    return {};
}
inline bool inputReady(const QJsonObject& value,const QString& id) {
    const auto model=value.value("model").toObject();const bool visible=model.value("visible").toBool();
    if (id=="assets.baking") {return !visible && value.value("baking").toObject().value("enabled").toBool();}
    if (id=="assets.import" || id=="assets.import-uploaded") {return !visible
        && (id=="assets.import" ? value.value("importEnabled").toBool() : value.value("uploadedImportVisible").toBool() && value.value("uploadedImportEnabled").toBool());}
    if (!visible) {return false;}if (id=="assets.model.cancel" || id=="assets.model.url" || id=="assets.model.shape") {return true;}
    if (id=="assets.model.dynamic") {return model.value("dynamicEnabled").toBool();}
    return id=="assets.model.accept";
}
inline QJsonObject metadata(QQuickItem* target) {
    const auto id=control(target);if (id.isEmpty()) {return {};}auto page=owner(target);bool complete=true;const auto actual=snapshot(page,complete);
    if (!complete) {return {};}
    return {{"assetControlVersion",4},{"role","page"},{"rootId",actual.value("rootId")},{"ownerRootId",actual.value("rootId")},
        {"windowId",actual.value("windowId")},{"componentSource",actual.value("componentSource")},{"controlId",id},{"inputReady",inputReady(actual,id)},{"usage",actual}};
}
inline QJsonObject inventory(const QList<QQuickItem*>& roots) {
    static const auto instance=QUuid::createUuid().toString(QUuid::WithoutBraces);static quint64 sequence=0;bool complete=asset_ui::enabled();QJsonArray pages;
    for (auto root:roots) {
        if (asset_ui::page(root)!=root) {continue;}bool valid=true;auto value=snapshot(root,valid);complete=complete && valid;if (valid) {pages.append(value);}
    }
    return {{"iosAssetsUsageUiVersion",1},{"instance",instance},{"sequence",static_cast<double>(++sequence)},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"available",asset_ui::enabled()},{"complete",complete},{"pages",pages}};
}
}
#endif
