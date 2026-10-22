// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"
#include <QColor>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QUuid>
#include <QPointer>
#include <QQmlContext>

namespace overte::e2e {
struct CreateExtraObject {
    QPointer<QQuickItem> page;
    QPointer<QQmlContext> context;
    QString name;
    explicit operator bool() const { return page && context && !name.isEmpty(); }
};

class CreateExtraUiLifetimes {
public:
    QString observe(const CreateExtraObject& actual) {
        if (!actual || !actual.page->window() || !_valid || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        for (const auto& row:_pages) {
            if (row.page==actual.page && row.context==actual.context && row.window==actual.page->window()) {return row.id;}
        }
        if (_pages.size()>=32) {_valid=false;return {};}
        const auto context=remember(_contexts,actual.context.data()),window=remember(_windows,actual.page->window());
        if (context.isEmpty() || window.isEmpty()) {_valid=false;return {};}
        const auto id=birth();_pages.append({id,context,window,QDateTime::currentMSecsSinceEpoch(),actual.page,actual.context,actual.page->window()});return id;
    }
    QJsonObject snapshot() {
        if (!_valid || !qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        QJsonArray rows;
        for (const auto& row:_pages) {rows.append(QJsonObject{{"id",row.id},{"contextId",row.contextId},{"windowId",row.windowId},
            {"firstObservedEpochMs",static_cast<double>(row.first)},{"pageAlive",!row.page.isNull()},
            {"contextAlive",!row.context.isNull()},{"windowAlive",!row.window.isNull()}});}
        return {{"createExtraUiInventoryVersion",1},{"instance",_instance},{"sourceSequence",static_cast<double>(++_sequence)},
            {"elapsedMs",static_cast<double>(_clock.elapsed())},{"complete",true},{"pages",rows}};
    }
private:
    static QString birth() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    template<class T> struct Original {QString id;QPointer<T> object;};
    template<class T> static QString remember(QList<Original<T>>& rows,T* actual) {
        for (const auto& row:rows) {if (row.object.data()==actual) {return row.id;}}
        if (!actual || rows.size()>=64) {return {};}
        const auto id=birth();rows.append({id,actual});return id;
    }
    QList<Original<QQmlContext>> _contexts;QList<Original<QQuickWindow>> _windows;
    struct Page {QString id,contextId,windowId;qint64 first;QPointer<QQuickItem> page;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;};
    QElapsedTimer _clock{[] {QElapsedTimer clock;clock.start();return clock;}()};
    QString _instance{birth()};quint64 _sequence{0};bool _valid{true};QList<Page> _pages;
};
inline CreateExtraUiLifetimes& createExtraUiLifetimes() {static CreateExtraUiLifetimes value;return value;}

inline CreateExtraObject createPolyvoxObject(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (!audioGuiItem(item)) { return {}; }
    int contexts{0};
    for (auto context=qmlContext(item);context && ++contexts<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (!context->isValid() || source!=PathUtils::defaultScriptsLocation().resolved(QUrl("system/create/qml/NewPolyVoxDialog.qml"))) { continue; }
        const auto name=context->nameForObject(item);if (name.isEmpty()) { continue; }
        int parents{0};
        for (auto parent=item;parent && ++parents<=128;parent=parent->parentItem()) {
            if (context->nameForObject(parent)=="newPolyVoxDialog" && parent->inherits("QQuickRectangle")
                    && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) { return {parent,context,name}; }
        }
    }
#else
    Q_UNUSED(item)
#endif
    return {};
}

inline CreateExtraObject createPolyvoxControl(QQuickItem* item) {
    auto actual=createPolyvoxObject(item);if (actual) { return actual; }
    // controlsUit.ComboBox is an original FocusScope wrapping a real Qt combo.
    // The actual alias and ancestry establish that association, not its caption.
    if (audioGuiItem(item) && item->inherits("QQuickComboBox")) {
        auto wrapper=item->parentItem();actual=createPolyvoxObject(wrapper);
        if (actual && wrapper->inherits("QQuickFocusScope")
                && wrapper->property("control").value<QObject*>()==item) { return actual; }
    }
    return {};
}

inline QString createExtraControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    if (auto page=createPage(item)) {
        if (page->property("currentTab").toInt()==0) {
            if (item->objectName()=="NativeCreateDetailedType" && item->inherits("QQuickComboBox")) { return "create-extra.detail-kind"; }
            if (item->objectName()=="NativeCreateDetailed" && item->inherits("QQuickButton")) { return "create-extra.detail-open"; }
        }
    }
    const auto actual=createPolyvoxControl(item);if (!actual) { return {}; }
    if (actual.page==item) { return "create-extra.polyvox.page"; }
    const QHash<QString,QString> fields{{"volumeSizeX","x"},{"volumeSizeY","y"},{"volumeSizeZ","z"}};
    if (fields.contains(actual.name) && item->inherits("QQuickTextInput")) { return "create-extra.polyvox."+fields.value(actual.name); }
    const QHash<QString,QString> choices{{"texturePreset","preset"},{"initialShape","shape"},{"surfaceStyle","style"}};
    if (choices.contains(actual.name) && item->inherits("QQuickComboBox")) { return "create-extra.polyvox."+choices.value(actual.name); }
    if (item->inherits("QQuickButton") && item->metaObject()->indexOfSignal("clicked()")>=0) {
        if (actual.name=="button1") { return "create-extra.polyvox.add"; }
        if (actual.name=="button2") { return "create-extra.polyvox.cancel"; }
    }
    return {};
}
inline bool createExtraField(const QString& id) {
    return id=="create-extra.polyvox.x" || id=="create-extra.polyvox.y" || id=="create-extra.polyvox.z";
}
inline int createExtraCount(const QString& id) {
    return id=="create-extra.detail-kind" || id=="create-extra.polyvox.preset" ? 6
        : id=="create-extra.polyvox.shape" || id=="create-extra.polyvox.style" ? 4 : 0;
}
inline bool createExtraText(const QString& id,const QString& text) {
    bool okay{false};const auto value=text.toInt(&okay);
    return createExtraField(id) && okay && value>=8 && value<=64 && QString::number(value)==text;
}
inline void appendCreateExtraObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    bool ready=item->isEnabled() && id!="create-extra.polyvox.page";
    if (createExtraField(id)) {
        const auto text=item->property("text"),readOnly=item->property("readOnly");
        const bool valid=text.userType()==QMetaType::QString && createExtraText(id,text.toString()) && readOnly.userType()==QMetaType::Bool;
        if (valid) { row["text"]=text.toString(); }
        ready=ready && valid && !readOnly.toBool();
    } else if (const auto count=createExtraCount(id)) {
        const auto actual=item->property("count"),index=item->property("currentIndex");
        const bool valid=actual.userType()==QMetaType::Int && actual.toInt()==count && index.userType()==QMetaType::Int
            && index.toInt()>=0 && index.toInt()<count;
        if (valid) { row["currentIndex"]=index.toInt();row["count"]=count; }
        ready=ready && valid;
    } else if (id=="create-extra.polyvox.page") {
        const auto actual=createPolyvoxObject(item);const auto id=createExtraUiLifetimes().observe(actual);
        if (id.isEmpty()) {row["inputReady"]=false;return;}
        row["profile"]="original-new-polyvox-v1";row["pageId"]=id;
    }
    row["inputReady"]=ready;
}
inline QString createExtraControlSource(QQuickItem* item,const QString& id) {
    if (createExtraControlId(item)!=id || !item->window()) { return {}; }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(center.x()) || !std::isfinite(center.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height())) { return {}; }
    QJsonObject value;appendCreateExtraObservation(value,item,id);
    const auto original=createPolyvoxControl(item);
    value["component"]=original ? original.context->baseUrl().toString() : createComponentSource(createPage(item));
    value["sceneX"]=center.x();value["sceneY"]=center.y();value["width"]=item->width();value["height"]=item->height();
    value["window"]=QString::number(reinterpret_cast<quintptr>(item->window()),16);
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}

// Narrow visual ownership exceptions for the original dialog only. The caller
// still traverses all siblings/z/clip paths; a foreign overlay is never skipped.
inline bool createExtraDecoration(QQuickItem* node,QQuickItem* target) {
    const auto actual=createPolyvoxControl(target),candidate=createPolyvoxObject(node);
    if (!actual || !candidate || actual.page!=candidate.page || actual.context!=candidate.context
            || node->acceptedMouseButtons()!=Qt::NoButton || node->filtersChildMouseEvents()) { return false; }
    if (!node->flags().testFlag(QQuickItem::ItemHasContents)) {
        // Original QQuick positioners accept touch for child delivery. Only
        // these source-qualified paintless containers are transparent here;
        // their actual touch route is tested with the unchanged surface body.
        return (node->inherits("QQuickRow") || node->inherits("QQuickColumn") || node->metaObject()==&QQuickItem::staticMetaObject);
    }
    if (node->acceptTouchEvents() || !createExtraField(createExtraControlId(target)) || !node->inherits("QQuickRectangle") || !node->childItems().isEmpty()) { return false; }
    const QHash<QString,QString> frames{{"volumeSizeX","textInputBoxVolumeSizeX"},{"volumeSizeY","textInputBoxVolumeSizeY"},{"volumeSizeZ","textInputBoxVolumeSizeZ"}};
    return frames.value(actual.name)==candidate.name && target->parentItem()==node->parentItem()
        && node->z()==target->z() && node->opacity()==.1 && node->property("color").value<QColor>()==QColor("white")
        && node->mapRectToScene(QRectF(0,0,node->width(),node->height()))==target->mapRectToScene(QRectF(0,0,target->width(),target->height()));
}
} // namespace overte::e2e
