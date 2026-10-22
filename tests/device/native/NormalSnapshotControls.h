// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
inline QString snapshotComponentSource(QQuickItem* item) {
    if (!audioGuiItem(item) || item->objectName()!="snapshotReview" || !loginQmlId(item,"root")) { return {}; }
    int depth=0;
    for(auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if(context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
            && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
            && source.path().endsWith("/system/snapshot/NativeSnapshotReview.qml")) { return source.toString(); }
    }
    return {};
}
inline QQuickItem* snapshotPage(QQuickItem* item) {
    if(!audioGuiItem(item)) { return nullptr; }
    int depth=0;
    for(auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if(!snapshotComponentSource(parent).isEmpty() && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0
            && parent->property("capturing").userType()==QMetaType::Bool
            && parent->property("processing").userType()==QMetaType::Bool) { return parent; }
    }
    return nullptr;
}
inline QString snapshotImagePath(QQuickItem* item) {
    if(!snapshotPage(item)) { return {}; }
    const auto context=qmlContext(item);if(!context) { return {}; }
    const auto row=createVariant(context->contextProperty("modelData")).toMap();
    const auto path=row.value("localPath");
    if(path.userType()!=QMetaType::QString || path.toString().isEmpty() || path.toString().size()>2048) { return {}; }
    const auto images=createVariant(snapshotPage(item)->property("images")).toList();
    int matches=0;for(const auto& image:images) { if(createVariant(image).toMap().value("localPath")==path) { ++matches; } }
    return matches==1 ? path.toString() : QString();
}
inline QString snapshotControlId(QQuickItem* item) {
    if(!audioGuiItem(item)) { return {}; }
    const auto page=snapshotPage(item);const auto name=item->objectName();
    if(!page) {
        const auto nav=scriptControlId(item);
        if(nav=="tablet.home" || nav.startsWith("tablet.page.")) { return nav; }
        return item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="SNAP"
            ? QStringLiteral("snapshot.entry") : QString();
    }
    if(page==item) { return "snapshot.page"; }
    if(name=="snapshotName" && item->inherits("QQuickTextInput")) { return "snapshot.name"; }
    if(name=="snapshotMode" && item->inherits("QQuickComboBox")) { return "snapshot.mode"; }
    if(name=="snapshotFormat" && item->inherits("QQuickComboBox")) { return "snapshot.format"; }
    if(item->inherits("QQuickScrollBar") && item->property("orientation").toInt()==Qt::Vertical) { return "snapshot.scrollbar"; }
    if(item->metaObject()->indexOfSignal("clicked()")<0) { return {}; }
    const QHash<QString,QString> fixed{{"snapshotCapture","snapshot.capture"},{"snapshotCancelCapture","snapshot.cancel-capture"},
        {"snapshotCancelUpload","snapshot.cancel-upload"}};
    if(fixed.contains(name)) { return fixed.value(name); }
    const auto label=item->property("text").toString();
    if(label=="Cancel system request") { return "snapshot.cancel-export"; }
    const QHash<QString,QString> actions{{"Save to device","save"},{"System share","share"},{"Upload for URL","upload"}};
    const auto path=snapshotImagePath(item);
    return actions.contains(label) && !path.isEmpty() ? "snapshot."+actions.value(label)+'.'
        +QString::fromLatin1(QCryptographicHash::hash(path.toUtf8(),QCryptographicHash::Sha256).toHex()) : QString();
}
inline bool snapshotChoice(const QString& id) { return id=="snapshot.mode" || id=="snapshot.format"; }
inline void appendSnapshotControl(QJsonObject& row,QQuickItem* item,const QString& id) {
    if(!audioGuiItem(item)) { return; }
    bool ready=item->isEnabled() && id!="snapshot.page";
    const auto page=snapshotPage(item);
    if(id=="snapshot.page") {
        row["profile"]="native-snapshot-review-v1";row["component"]=snapshotComponentSource(page);
        for(const auto& name:QStringList{"capturing","processing","captureSettingsLoaded","statusError"}) {
            const auto value=page->property(name.toLatin1().constData());
            if(value.userType()!=QMetaType::Bool) { ready=false;continue; }row[name]=value.toBool();
        }
        row["statusText"]=page->property("statusText").toString();row["exportTicket"]=page->property("exportTicket").toString();
        row["uploadPath"]=page->property("uploadPath").toString();
    } else if(id=="snapshot.name") {
        row["text"]=item->property("text").toString();
    } else if(snapshotChoice(id)) {
        const auto index=item->property("currentIndex"),count=item->property("count");
        const auto model=createVariant(item->property("model"));QStringList options;
        if(model.userType()==QMetaType::QStringList) { options=model.toStringList(); }
        else { for(const auto& value:model.toList()) { if(value.userType()!=QMetaType::QString) { options.clear();break; }options.append(value.toString()); } }
        const bool valid=index.userType()==QMetaType::Int && count.userType()==QMetaType::Int
            && count.toInt()>0 && count.toInt()<=8 && options.size()==count.toInt() && index.toInt()>=0 && index.toInt()<count.toInt();
        if(valid) { row["currentIndex"]=index.toInt();row["count"]=count.toInt();row["currentText"]=item->property("currentText").toString();row["options"]=QJsonArray::fromStringList(options); }
        ready=ready && valid;
    } else if(id=="snapshot.scrollbar") {
        for(const auto& name:QStringList{"position","size"}) { row[name]=item->property(name.toLatin1().constData()).toDouble(); }
    } else if(id.startsWith("snapshot.save.") || id.startsWith("snapshot.share.") || id.startsWith("snapshot.upload.")) {
        const auto path=snapshotImagePath(item);row["path"]=path;ready=ready && !path.isEmpty();
    }
    row["inputReady"]=ready;
}
inline QString snapshotControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendSnapshotControl(row,item,id);
    if(const auto page=snapshotPage(item)) { row["component"]=snapshotComponentSource(page); }
    if(item && item->window()) { const auto point=item->mapToScene(QPointF(item->width()/2,item->height()/2));row["sceneX"]=point.x();row["sceneY"]=point.y(); }
    return QString::fromUtf8(QJsonDocument(row).toJson(QJsonDocument::Compact));
}
inline bool snapshotText(const QString& text) {
    if(text.size()>48) { return false; }
    for(const auto ch:text) { if(ch.unicode()<32 || ch.unicode()>126) { return false; } }return true;
}
inline bool snapshotScrollPoint(QQuickItem* item,const QString& direction,QPointF& point) {
    if(snapshotControlId(item)!="snapshot.scrollbar" || (direction!="up" && direction!="down")) { return false; }
    auto thumb=qobject_cast<QQuickItem*>(item->property("contentItem").value<QObject*>());
    if(!thumb || thumb->parentItem()!=item || !thumb->isVisible()) { return false; }
    const auto rect=thumb->mapRectToItem(item,QRectF(0,0,thumb->width(),thumb->height()));
    const auto low=direction=="up" ? 0.0 : rect.bottom(),high=direction=="up" ? rect.top() : item->height();
    if(!std::isfinite(low) || !std::isfinite(high) || low<0 || high>item->height() || high-low<2) { return false; }
    point=item->mapToScene(QPointF(item->width()/2,(low+high)/2));return true;
}
#endif
} // namespace overte::e2e
