// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalLoginControls.h"
#include <QHash>
#include <QUuid>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QUrl>
#include <cmath>

namespace overte::e2e {
inline QVariant createVariant(QVariant value) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (value.userType()==qMetaTypeId<QJSValue>()) { value=value.value<QJSValue>().toVariant(); }
#endif
    return value;
}

inline QString createComponentSource(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!audioGuiItem(item) || !loginQmlId(item,"root")) { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/system/create/qml/NativeCreate.qml")) { return source.toString(); }
    }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline QQuickItem* createPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        const auto tab=parent->property("currentTab");
        if (!createComponentSource(parent).isEmpty() && tab.userType()==QMetaType::Int && tab.toInt()>=0 && tab.toInt()<=4
                && parent->property("statusError").userType()==QMetaType::Bool
                && parent->property("statusText").userType()==QMetaType::QString
                && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) { return parent; }
    }
    return nullptr;
}

inline QString createEntityId(const QString& raw) {
    const QUuid value(raw);
    return value.isNull() ? QString() : value.toString(QUuid::WithoutBraces);
}

inline QQuickItem* createFileBrowser(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    if (!audioGuiItem(item) || !QCoreApplication::arguments().contains("--testScript")) { return nullptr; }
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (parent->objectName()!="nativeFileBrowser") { continue; }
        bool original=false;
        int contextDepth {0};
        for (auto context=qmlContext(parent);context && ++contextDepth<=128;context=context->parentContext()) {
            const auto source=context->baseUrl();
            if (context->nameForObject(parent)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                    && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                    && source.path().endsWith("/dialogs/NativeFileBrowser.qml")) { original=true;break; }
        }
        const auto caption=parent->property("caption").toString();
        const bool save=parent->property("saveDialog").toBool();
        if (original && (save ? caption=="Select Where to Save" : caption=="Select .json to Import")
                && parent->property("saveDialog").userType()==QMetaType::Bool
                && parent->property("filter").toString()=="*.json"
                && !parent->property("bundleMode").toBool() && !parent->property("multiSelect").toBool()
                && !parent->property("selectDirectory").toBool()) { return parent; }
    }
#else
    Q_UNUSED(item)
#endif
    return nullptr;
}

inline QJsonObject createFileObservation(QQuickItem* root) {
    if (!root) { return {}; }
    return {{"caption",root->property("caption").toString()},{"save",root->property("saveDialog").toBool()},
        {"directory",root->property("dir").toUrl().toString()},{"error",root->property("error").toString()},
        {"closing",root->property("closing").toBool()},{"pendingDocuments",!root->property("requestId").toString().isEmpty()}};
}

inline QString createControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto page=createPage(item);const auto name=item->objectName();
    if (auto browser=createFileBrowser(item)) {
        if (name=="fileNameInput" && item->inherits("QQuickTextInput")) { return "create-file.name"; }
        if (item->metaObject()->indexOfSignal("clicked()")>=0) {
            if (name=="fileAccept") { return "create-file.accept"; }
            if (name=="fileCancel") { return "create-file.cancel"; }
        }
        return {};
    }
    if (!page) {
        const auto nav=scriptControlId(item);
        if (nav=="tablet.home" || nav.startsWith("tablet.page.")) { return nav; }
        return item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="CREATE"
            ? QStringLiteral("create.entry") : QString();
    }
    if (page==item) { return "create.page"; }
    if (item->inherits("QQuickScrollBar") && item->property("orientation").toInt()==Qt::Vertical) {
        // An attached ScrollBar belongs to the actual visible ScrollView (or
        // its content Flickable), never an arbitrary similarly named item.
        auto owner=item->parentItem();
        for (int depth=0;owner && depth<3;++depth,owner=owner->parentItem()) {
            if (owner->inherits("QQuickScrollView") && createPage(owner)==page) { return "create.scrollbar"; }
        }
    }
    const QHash<QString,QString> fixed{{"NativeCreateHost","create.host"},{"NativeCreateImportHost","create.import-host"},
        {"NativeCreateResourceUrl","create.resource"},{"NativeCreateNew_Shape","create.new-shape"},
        {"NativeCreateNew_Model","create.new-model"},{"NativeCreateNew_PolyVox","create.new-voxel"},
        {"NativeCreateRefresh","create.refresh"},{"NativeCreateName","create.name"},
        {"NativeCreateApply","create.apply"},{"NativeCreateDelete","create.delete"},
        {"NativeCreateUndo","create.undo"},{"NativeCreateRedo","create.redo"},
        {"NativeCreateImportUrl","create.import-url"},{"NativeCreateImport","create.import-submit"},
        {"NativeCreateBrowse","create.import-browse"},{"NativeCreateApplyTyped","create.apply-typed"},
        {"NativeCreateTool_export","create.export"},
        {"NativeCreateEditMode","create.edit-mode"},{"NativeCreateVoxelShape","create.voxel-shape"},
        {"NativeCreateVoxelRemove","create.voxel-remove"},{"NativeCreateVoxelDynamics","create.voxel-dynamics"},
        {"NativeCreateVoxelPointer","create.voxel-pointer"},{"NativeCreateVoxelDiameter","create.voxel-diameter"},
        {"NativeCreateVoxelReach","create.voxel-reach"},{"NativeCreateVoxelApply","create.voxel-apply"},
        {"NativeCreatePropertySearch","create.property-filter"}};
    if (fixed.contains(name)) { return fixed.value(name); }
    const auto tab=QRegularExpression("\\ANativeCreateTab_([0-4])\\z").match(name);
    if (tab.hasMatch()) { return "create.tab."+tab.captured(1); }
    const auto field=QRegularExpression("\\ANativeCreateField_(position|rotation|dimensions|color)_(x|y|z|red|green|blue)\\z").match(name);
    if (field.hasMatch() && ((field.captured(1)=="color")==QStringList{"red","green","blue"}.contains(field.captured(2)))) {
        return "create.field."+field.captured(1)+'.'+field.captured(2);
    }
    if (name=="NativeCreateProperty_textures") { return "create.textures"; }
    if (name.startsWith("NativeCreateEntity_")) {
        const auto id=createEntityId(name.mid(QStringLiteral("NativeCreateEntity_").size()));
        if (!id.isEmpty()) { return "create.entity."+id; }
    }
    if (loginQmlId(item,"shapeChoice") && item->inherits("QQuickComboBox")) { return "create.shape"; }
    if (loginQmlId(item,"listSearch") && item->inherits("QQuickTextInput")) { return "create.filter"; }
    return {};
}

inline bool createField(const QString& id) {
    return id=="create.name" || id=="create.resource" || id=="create.import-url" || id=="create.filter"
        || id=="create.textures" || id=="create.voxel-diameter" || id=="create.voxel-reach"
        || id=="create-file.name" || id=="create.property-filter" || id.startsWith("create.field.");
}
inline bool createChoice(const QString& id) {
    return id=="create.host" || id=="create.import-host" || id=="create.shape" || id=="create.edit-mode"
        || id=="create.voxel-shape" || id=="create.voxel-dynamics" || id=="create.voxel-pointer";
}
inline bool createText(const QString& text) {
    if (text.size()>4096) { return false; }
    for (auto ch:text) { if (ch.unicode()<32 || ch.unicode()>126) { return false; } }
    return true;
}

inline void appendCreateControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    auto page=createPage(item);
    bool ready=item->isEnabled() && id!="create.page";
    QJsonArray selected;
    if (page) {
        const auto ids=createVariant(page->property("selectedIDs"));
        bool validSelection=ids.userType()==QMetaType::QVariantList && ids.toList().size()<=256;
        for (const auto& raw:ids.toList()) {
            const auto value=createEntityId(raw.toString());
            if (value.isEmpty() || selected.contains(value)) { validSelection=false;break; }
            selected.append(value);
        }
        if (!validSelection) { row["inputReady"]=false;return; }
        if (id=="create.page") {
            row["profile"]="native-create-v1";
            row["tab"]=page->property("currentTab").toInt();row["selectedIds"]=selected;
            const auto status=page->property("statusText").toString();
            if (status.size()>256) { row.remove("profile");row["inputReady"]=false;return; }
            for (auto ch:status) { if (ch.unicode()<32 || ch.unicode()==127) { row.remove("profile");row["inputReady"]=false;return; } }
            row["statusError"]=page->property("statusError").toBool();row["statusText"]=status;
            row["toolSettings"]=QJsonObject::fromVariantMap(createVariant(page->property("voxelSettings")).toMap());
            row["componentSourceSha256"]=QString::fromLatin1(QCryptographicHash::hash(createComponentSource(page).toUtf8(),QCryptographicHash::Sha256).toHex());
        }
    } else if (auto browser=createFileBrowser(item)) {
        row["picker"]=createFileObservation(browser);
        ready=ready && !browser->property("closing").toBool() && browser->property("requestId").toString().isEmpty();
    } else { ready=ready && (id=="create.entry" || id=="tablet.home" || id.startsWith("tablet.page.")); }
    if (id=="create.voxel-remove") {
        const auto checked=item->property("checked");
        if (checked.userType()!=QMetaType::Bool) { row["inputReady"]=false;return; }
        row["checked"]=checked.toBool();
    } else if (id=="create.scrollbar") {
        const auto position=item->property("position"),size=item->property("size");
        bool positionOkay {false},sizeOkay {false};
        const auto p=position.toDouble(&positionOkay),s=size.toDouble(&sizeOkay);
        const bool valid=positionOkay && sizeOkay && position.userType()!=QMetaType::Bool && size.userType()!=QMetaType::Bool
            && std::isfinite(p) && std::isfinite(s) && p>=0 && s>0 && s<=1 && p+s<=1.000001;
        if (valid) { row["position"]=p;row["size"]=s; }
        ready=ready && valid && s<1;
    } else if (createField(id)) {
        const auto text=item->property("text");const auto readOnly=item->property("readOnly");
        const bool valid=text.userType()==QMetaType::QString && createText(text.toString()) && readOnly.userType()==QMetaType::Bool;
        if (valid) { row["text"]=text.toString(); }
        ready=ready && valid && !readOnly.toBool();
    } else if (createChoice(id)) {
        const auto index=item->property("currentIndex"),count=item->property("count");
        const bool valid=index.userType()==QMetaType::Int && count.userType()==QMetaType::Int
            && index.toInt()>=0 && index.toInt()<count.toInt() && count.toInt()==(id=="create.shape" ? 6 : id=="create.voxel-shape" ? 3 : 2);
        if (valid) { row["currentIndex"]=index.toInt();row["count"]=count.toInt(); }
        ready=ready && valid;
    } else if (id.startsWith("create.entity.")) {
        row["entityId"]=id.mid(QStringLiteral("create.entity.").size());
    }
    row["inputReady"]=ready;
}

inline bool createScrollPoint(QQuickItem* item,const QString& direction,QPointF& point) {
    if (createControlId(item)!="create.scrollbar" || (direction!="up" && direction!="down")) { return false; }
    auto thumb=qobject_cast<QQuickItem*>(item->property("contentItem").value<QObject*>());
    if (!thumb || thumb->parentItem()!=item || !thumb->isVisible() || !item->isEnabled()) { return false; }
    const auto rect=thumb->mapRectToItem(item,QRectF(0,0,thumb->width(),thumb->height()));
    if (!std::isfinite(rect.top()) || !std::isfinite(rect.bottom()) || rect.top()<0 || rect.bottom()>item->height()) { return false; }
    const double low=direction=="up" ? 0 : rect.bottom(),high=direction=="up" ? rect.top() : item->height();
    if (high-low<2) { return false; }
    point=item->mapToScene(QPointF(item->width()/2,(low+high)/2));
    return std::isfinite(point.x()) && std::isfinite(point.y());
}

inline QString createControlSource(QQuickItem* item,const QString& id) {
    QJsonObject value;appendCreateControlObservation(value,item,id);
    auto page=createPage(item);
    if (page) {
        QJsonObject actualPage;appendCreateControlObservation(actualPage,page,"create.page");
        if (!actualPage.contains("profile")) { return {}; }
        value["tab"]=actualPage.value("tab");
        value["selection"]=actualPage.value("selectedIds");
        value["component"]=createComponentSource(page);
    }
    if (auto browser=createFileBrowser(item)) { value["picker"]=createFileObservation(browser); }
    if (item && item->window()) {
        const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
        value["sceneX"]=center.x();value["sceneY"]=center.y();
    }
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}
} // namespace overte::e2e
