// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(OVERTE_IOS_E2E_TEST_BUILD) && defined(Q_OS_IOS)
#include "IOSSnapshotExportControls.h"
#include <QCoreApplication>
#include <QJsonArray>
#include <QPointer>
#include <QQuickWindow>
#include <QSet>
#include <QThread>
#include <cmath>

namespace overte::e2e::snapshot_review {
// Passive GUI-thread properties, not an image decode/render/GPU verdict.
// No observer retains a product QObject or schedules a callback.
inline QString identity(QObject* object, const char* key) {
    auto value=object->property(key).toString();
    if (value.isEmpty()) {
        value=QUuid::createUuid().toString(QUuid::WithoutBraces);
        object->setProperty(key,value);
    }
    return QRegularExpression("\\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\z").match(value).hasMatch() ? value : QString();
}

inline QJsonObject image(QQuickItem* item,QQuickItem* root) {
    QPointer<QQuickItem> heldItem=item,heldRoot=root;
    auto row=snapshotExportRow(item,root);
    if (!row || !item->inherits("QQuickImage") || item->thread()!=QThread::currentThread()) {return {};}
    QPointer<QQuickItem> heldRow=row;
    const auto sourceValue=item->property("source");
    const auto source=sourceValue.toUrl();
    const QFileInfo rowFile(row->property("featureSnapshotPath").toString());
    const QFileInfo sourceFile(source.toLocalFile());
    const auto actualName=rowFile.fileName();
    const bool owned=QRegularExpression("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)\\z").match(actualName).hasMatch()
        && source.isLocalFile() && !source.hasQuery() && !source.hasFragment()
        && rowFile.isAbsolute() && rowFile.isFile() && !rowFile.isSymLink()
        && sourceFile.isAbsolute() && sourceFile.isFile() && !sourceFile.isSymLink()
        && !rowFile.canonicalFilePath().isEmpty()
        && sourceFile.canonicalFilePath()==rowFile.canonicalFilePath();
    const auto window=item->window();
    if (!window || window!=root->window()) {return {};}
    const auto size=item->property("sourceSize").toSize();
    bool statusValid=false;
    const auto status=item->property("status").toInt(&statusValid);
    if (!statusValid || status<0 || status>3) {return {};}
    bool widthValid=false,heightValid=false;
    const auto width=item->property("paintedWidth").toDouble(&widthValid);
    const auto height=item->property("paintedHeight").toDouble(&heightValid);
    if (!widthValid || !heightValid || !std::isfinite(width) || !std::isfinite(height)
            || width<0 || height<0 || size.width()<0 || size.height()<0) {return {};}
    const auto bounds=item->mapRectToScene(QRectF((item->width()-width)/2,(item->height()-height)/2,width,height));
    const auto origin=item->mapToScene(QPointF(0,0)),horizontal=item->mapToScene(QPointF(1,0)),vertical=item->mapToScene(QPointF(0,1));
    const bool axisAligned=std::abs(horizontal.y()-origin.y())<0.000001
        && std::abs(vertical.x()-origin.x())<0.000001 && horizontal.x()>origin.x() && vertical.y()>origin.y();
    bool unclipped=true;
    for (auto parent=item;parent;parent=parent->parentItem()) {
        if (parent->rotation()!=0 || parent->scale()<=0) {unclipped=false;}
        if (parent->clip() && !parent->mapRectToScene(QRectF(0,0,parent->width(),parent->height())).contains(bounds)) {unclipped=false;}
    }
    const auto ratio=window->devicePixelRatio();
    if (!std::isfinite(ratio) || ratio<=0 || window->width()<=0 || window->height()<=0
            || !std::isfinite(bounds.x()) || !std::isfinite(bounds.y())
            || !std::isfinite(bounds.width()) || !std::isfinite(bounds.height())) {return {};}
    const auto object=identity(item,"_overteE2ESnapshotPreviewId");
    if (object.isEmpty() || !heldItem || !heldRoot || !heldRow || item->window()!=window
            || snapshotExportRoot(item)!=root || snapshotExportRow(item,root)!=row) {return {};}
    return {{"objectIdentity",object},{"row",row->property("featureSnapshotIndex").toInt()},
        {"fileOwned",owned},{"fileName",owned ? actualName : QString()},
        {"status",status},{"visible",item->isVisible()},{"sourceSize",QJsonArray{size.width(),size.height()}},
        {"paintedBounds",QJsonArray{bounds.x(),bounds.y(),bounds.width(),bounds.height()}},
        {"centerAligned",item->property("horizontalAlignment").toInt()==Qt::AlignHCenter
            && item->property("verticalAlignment").toInt()==Qt::AlignVCenter},
        {"preserveAspectFit",item->property("fillMode").toInt()==1},
        {"unclipped",unclipped},{"axisAligned",axisAligned},{"systemBlocked",overte::ios::featureSnapshotQtInputBlocked()},
        {"window",QJsonObject{{"width",window->width()},{"height",window->height()},
            {"x",window->x()},{"y",window->y()},{"devicePixelRatio",ratio}}}};
}

inline QJsonObject inventory(const QList<QQuickItem*>& tops,bool complete) {
    const auto application=QCoreApplication::instance();QJsonArray roots;
    if (!application || application->thread()!=QThread::currentThread()
            || !QCoreApplication::arguments().contains("--testScript")) {complete=false;}
    else {
        QList<QQuickItem*> pending=tops;QSet<QQuickItem*> seen;QList<QQuickItem*> reviews;
        while (!pending.isEmpty()) {
            auto item=pending.takeLast();if (!item || seen.contains(item)) {continue;}
            if (seen.size()>=8192 || item->thread()!=QThread::currentThread()) {complete=false;break;}
            seen.insert(item);pending.append(item->childItems());
            if (item->objectName()=="snapshotReview") {
                if (snapshotExportRoot(item)!=item) {complete=false;continue;}
                reviews.append(item);
            }
        }
        if (reviews.size()>8) {complete=false;}
        else for (auto root:reviews) {
            QJsonArray images;QSet<int> indices;const auto rootId=identity(root,"_overteE2ESnapshotExportRootId");
            const auto count=root->property("featureImageCount");
            if (rootId.isEmpty() || count.userType()!=QMetaType::Int || count.toInt()<0 || count.toInt()>8) {complete=false;continue;}
            for (auto item:seen) {
                if (item->objectName()!="snapshotStillPreview" || snapshotExportRoot(item)!=root) {continue;}
                const auto observed=image(item,root);const auto index=observed.value("row").toInt(-1);
                if (observed.isEmpty() || index<0 || index>=8 || indices.contains(index)) {complete=false;continue;}
                indices.insert(index);images.append(observed);
            }
            if (images.size()!=count.toInt()) {complete=false;}
            roots.append(QJsonObject{{"rootIdentity",rootId},{"qmlSource",qmlContext(root)->baseUrl().toString()},
                {"visible",root->isVisible()},{"capturing",root->property("capturing").toBool()},
                {"processing",root->property("processing").toBool()},{"statusError",root->property("statusError").toBool()},
                {"imageCount",count.toInt()},{"images",images}});
        }
    }
    return {{"iosSnapshotReviewInventoryVersion",1},{"complete",complete},{"roots",roots}};
}
}
#endif
