// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoAvatarInputHit.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalChatControls.h"
#include <PathUtils.h>
#include <ui/NativeFieldInput.h>
#include <algorithm>
namespace overte::e2e {
// Reused from fixed Phone5527; only the ordinary source-role helper is needed.
inline QVariant avatarPeopleRole(QQuickItem* item,const QString& key) {
    auto context=qmlContext(item);return context ? createVariant(context->contextProperty(key)) : QVariant();
}
inline QQuickItem* avatarPeopleComponent(QQuickItem* item,const QString& path,const QString& id) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth=0;
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->baseUrl()!=PathUtils::qmlUrl(path)) { continue; }
        auto actual=qobject_cast<QQuickItem*>(createVariant(context->contextProperty(id)).value<QObject*>());
        if (actual && context->nameForObject(actual)==id) {
            if ((path=="hifi/AvatarApp.qml" || path=="hifi/Pal.qml" || path.startsWith("hifi/avatarapp/") && path!="hifi/avatarapp/PageIndicator.qml")
                    && !actual->inherits("QQuickRectangle")) {return nullptr;}
            int visualDepth=0;for (auto parent=item;parent && ++visualDepth<=128;parent=parent->parentItem()) {if (parent==actual) {return actual;}}
        }
    }
    return nullptr;
}
inline QQuickItem* avatarApp(QQuickItem* item) { return avatarPeopleComponent(item,"hifi/AvatarApp.qml","root"); }
inline QQuickItem* peopleApp(QQuickItem* item) { return avatarPeopleComponent(item,"hifi/Pal.qml","pal"); }
inline QString avatarPeopleQmlName(QQuickItem* item,const QString& path) {
    int depth=0;for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->baseUrl()==PathUtils::qmlUrl(path)) { const auto name=context->nameForObject(item);if (!name.isEmpty()) { return name; } }
    }
    return {};
}
inline QQuickItem* avatarDialog(QQuickItem* item) {
    if (!avatarApp(item)) { return nullptr; }
    for (const auto& path:QStringList{"hifi/avatarapp/MessageBox.qml","hifi/avatarapp/CreateFavoriteDialog.qml","hifi/avatarapp/Settings.qml","hifi/avatarapp/AdjustWearables.qml"}) {
        if (auto root=avatarPeopleComponent(item,path,"root")) { return root; }
    }
    return nullptr;
}
inline QVariantMap peopleRow(QQuickItem* item) {
    if (!peopleApp(item)) { return {}; }
    for (auto parent=item;parent;parent=parent->parentItem()) {
        if (avatarPeopleQmlName(parent,"hifi/PeopleTable.qml")=="peopleRow") {
            const auto original=createVariant(parent->property("rowData"));auto row=original.toMap();
            if (row.isEmpty()) { if (auto model=original.value<QObject*>()) {
                for (const auto& key:QStringList{"sessionId","userName"}) { const auto value=model->property(key.toUtf8().constData());if (value.userType()==QMetaType::QString) { row.insert(key,value); } }
            } }return row;
        }
    }
    return {};
}
inline QQuickItem* peopleCard(QQuickItem* item) { return peopleApp(item) ? avatarPeopleComponent(item,"hifi/NameCard.qml","thisNameCard") : nullptr; }
inline QVariantMap avatarPeopleSelectedWearable(QQuickItem* item) {
    auto root=avatarPeopleComponent(item,"hifi/avatarapp/AdjustWearables.qml","root");
    if (!root || root->thread()!=qApp->thread()) { return {}; }
    QVariant original;
    if (!QMetaObject::invokeMethod(root,"getCurrentWearable",Qt::DirectConnection,Q_RETURN_ARG(QVariant,original))) { return {}; }
    original=createVariant(original);auto result=original.toMap();
    if (result.isEmpty()) { if (auto object=original.value<QObject*>()) {
        if (object->thread()!=qApp->thread()) { return {}; }
        for (const auto& key:QStringList{"id","modelURL"}) { const auto value=object->property(key.toUtf8().constData());
            if (value.userType()!=QMetaType::QString) { return {}; }result.insert(key,value); }
    } }
    return result;
}
inline bool avatarPeopleFrontDialog(QQuickItem* item,QQuickItem* dialog) {
    auto page=avatarApp(item);if (!page || !dialog) { return false; }
    QQuickItem* front{nullptr};
    for (auto context=qmlContext(page);context;context=context->parentContext()) {
        if (context->baseUrl()!=PathUtils::qmlUrl("hifi/AvatarApp.qml")) { continue; }
        for (const auto& id:QStringList{"popup","createFavorite"}) {
            auto actual=qobject_cast<QQuickItem*>(createVariant(context->contextProperty(id)).value<QObject*>());
            if (!actual || context->nameForObject(actual)!=id) { return false; }
            if (actual->isVisible()) { if (front && front!=actual) { return false; }front=actual; }
        }break;
    }return !front || front==dialog;
}
inline bool avatarPeopleFills(QQuickItem* item,const QString& path,const QString& id) {
    if (!item || !qmlContext(item)) { return false; }
    int depth=0;for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        if (context->baseUrl()!=PathUtils::qmlUrl(path)) { continue; }
        auto target=createVariant(context->contextProperty(id)).value<QObject*>();
        auto anchors=createVariant(item->property("anchors")).value<QObject*>();
        if (target && context->nameForObject(target)==id && anchors && createVariant(anchors->property("fill")).value<QObject*>()==target) { return true; }
    }return false;
}
inline QString avatarPeopleControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto avatar=avatarApp(item),people=peopleApp(item);const auto name=item->objectName();
    if (!avatar && !people) {
        if (avatarPeopleQmlName(item,"hifi/tablet/TabletButton.qml")=="tabletButton") {
            if (item->property("text").toString()=="AVATAR") { return "avatar.entry"; }
            if (item->property("text").toString()=="PEOPLE") { return "people.entry"; }
        }return {};
    }
    if (avatar) {
        if (item==avatar) { return "avatar.page"; }
        const auto own=avatarPeopleQmlName(item,"hifi/AvatarApp.qml");
        if (own=="linkLabel") { return "avatar.url"; }
        if (own=="adjustLabel") { return "avatar.wearables"; }
        if (avatarPeopleQmlName(item,"hifi/avatarapp/PageIndicator.qml")=="pageIndicatorMouseArea") {
            const auto indicator=avatarPeopleComponent(item,"hifi/avatarapp/PageIndicator.qml","indicator");
            if (!indicator) { return {}; }
            return indicator->property("isPrevious").toBool() ? "avatar.bookmark.previous" : "avatar.bookmark.next";
        }
        if (item->inherits("QQuickScrollBar") && item->property("orientation").toInt()==Qt::Vertical && avatarPeopleComponent(item,"hifi/avatarapp/Settings.qml","root")) { return "avatar.settings.scrollbar"; }
        if (item->inherits("QQuickMouseArea")) {
            if (avatarPeopleQmlName(item,"hifi/avatarapp/AvatarAppHeader.qml")=="settingsMouseArea") { return "avatar.settings"; }
            if (avatarPeopleFills(item,"hifi/AvatarApp.qml","star")) { return "avatar.bookmark.add"; }
            if (item->parentItem() && avatarPeopleQmlName(item->parentItem(),"hifi/AvatarApp.qml")=="manageLabel") { return "avatar.bookmark.manage"; }
            if (own=="favoriteAvatarMouseArea") {
                const auto index=avatarPeopleRole(item,"index");bool okay=false;const auto n=index.toInt(&okay);
                if (okay && n>=0 && n<1000) { return "avatar.bookmark.row."+QString::number(n); }
            }
        }
        if (avatarPeopleQmlName(item,"hifi/avatarapp/Settings.qml")=="scaleSlider") { return "avatar.scale"; }
        if (auto dialog=avatarDialog(item)) {
            if (!avatarPeopleFrontDialog(item,dialog)) { return {}; }
            if (item->inherits("QQuickTextInput")) {
                const auto input=createVariant(dialog->property("inputText")).value<QObject*>();
                if (input==item || avatarPeopleQmlName(item,"hifi/avatarapp/CreateFavoriteDialog.qml")=="favoriteName") { return "avatar.dialog.input"; }
            }
            const auto button=avatarPeopleQmlName(item,"hifi/avatarapp/DialogButtons.qml");
            if (button=="yesButton") { return "avatar.dialog.confirm"; }
            if (button=="noButton") { return "avatar.dialog.cancel"; }
        }
        if (avatarPeopleComponent(item,"hifi/avatarapp/AdjustWearables.qml","root") && item->inherits("QQuickText") && item->property("text").toString()=="<a href='#'>Add custom</a>") { return "avatar.wearable.add"; }
        if (avatarPeopleComponent(item,"hifi/avatarapp/AdjustWearables.qml","root") && item->inherits("QQuickAbstractButton")
                && item->property("text").toString()=="TAKE IT OFF" && avatarPeopleFrontDialog(item,avatarDialog(item))) { return "avatar.wearable.remove"; }
    }
    if (people) {
        if (item==people) { return "people.page"; }
        if (QStringList{"peopleConnectionAccept","peopleConnectionDecline","peopleConnectionCancel","peopleRequestConnection"}.contains(name)) {
            return "people."+name.mid(6);
        }
        if (item->inherits("QQuickMouseArea") && item->parentItem()) {
            const auto parentName=avatarPeopleQmlName(item->parentItem(),"hifi/Pal.qml");
            if (parentName=="nearbyTabSelector") { return "people.nearby"; }
            if (parentName=="connectionsTabSelector") { return "people.connections"; }
            if (avatarPeopleQmlName(item->parentItem(),"hifi/PeopleTable.qml")=="peopleRow") {
                bool okay=false;const auto index=item->parentItem()->property("rowIndex").toInt(&okay);
                if (okay && index>=0 && index<1000) { return "people.row."+QString::number(index); }
            }
            if (auto card=peopleCard(item)) {
                if (!card->property("isMyCard").toBool() && !card->property("userName").toString().isEmpty() && people->property("activeTab")=="connectionsTab" && avatarPeopleFills(item,"hifi/NameCard.qml","nameCardRemoveConnectionImage")) { return "people.remove."+card->property("userName").toString(); }
            }
        }
    }
    return {};
}
inline void appendAvatarPeopleControl(QJsonObject& row,QQuickItem* item,const QString& id) {
    bool ready=true;
    if (auto page=avatarApp(item)) {
        const auto current=createVariant(page->property("currentAvatar"));
        auto actual=current.toMap();if (auto object=current.value<QObject*>()) {
            if (object->thread()!=qApp->thread()) {ready=false;}else {for (const auto& key:QStringList{"avatarUrl","avatarScale"}) {actual[key]=object->property(key.toUtf8().constData());}}
        }
        const auto settings=createVariant(page->property("currentAvatarSettings"));
        ready=ready && actual.value("avatarUrl").userType()==QMetaType::QString && !actual.value("avatarUrl").toString().isEmpty()
            && actual.value("avatarScale").canConvert<double>() && std::isfinite(actual.value("avatarScale").toDouble()) && actual.value("avatarScale").toDouble()>0 && !settings.toMap().isEmpty();
    }
    row["inputReady"]=ready && item->isEnabled() && !id.endsWith(".page");
    if (id=="avatar.dialog.input") { row["text"]=item->property("text").toString(); }
    if (auto dialog=avatarDialog(item)) {
        row["dialogTitle"]=dialog->property("titleText").toString();
        row["dialogSource"]=QString::fromLatin1(dialog->metaObject()->className());
    }
    if (auto page=avatarApp(item)) { row["managing"]=page->property("isInManageState").toBool(); }
    if (id=="avatar.scale") { for (const auto& key:QStringList{"value","from","to","stepSize"}) { row[key]=QJsonValue::fromVariant(item->property(key.toUtf8().constData())); } }
    if (id.startsWith("avatar.bookmark.row.")) { row["bookmarkName"]=avatarPeopleRole(item,"name").toString(); }
    if (id=="avatar.wearable.remove") {
        const auto selected=avatarPeopleSelectedWearable(item);
        row["wearableId"]=selected.value("id").toString();
        row["wearableUrlSha256"]=QString::fromLatin1(QCryptographicHash::hash(selected.value("modelURL").toString().toUtf8(),QCryptographicHash::Sha256).toHex());
    }
    if (auto card=peopleCard(item)) { row["peerSession"]=card->property("uuid").toString();row["userName"]=card->property("userName").toString(); }
    const auto original=peopleRow(item);
    if (!original.isEmpty()) { row["peerSession"]=original.value("sessionId").toString();row["userName"]=original.value("userName").toString(); }
    if (auto page=peopleApp(item)) { row["consent"]=QJsonValue::fromVariant(createVariant(page->property("connectionState")));row["tab"]=page->property("activeTab").toString(); }
}
inline QString avatarPeopleControlSource(QQuickItem* item,const QString& id) {
    if (!item || !item->window() || item->thread()!=qApp->thread() || item->window()->thread()!=qApp->thread()) {return {};}
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    if (!std::isfinite(center.x()) || !std::isfinite(center.y()) || !std::isfinite(item->width()) || !std::isfinite(item->height()) || item->width()<=0 || item->height()<=0) {return {};}
    QJsonObject row;appendAvatarPeopleControl(row,item,id);row["id"]=id;
    row["x"]=center.x();row["y"]=center.y();row["width"]=item->width();row["height"]=item->height();
    // Private hash only; the normal surface separately weak-binds the actual
    // window object and changes its generation after destruction/replacement.
    row["window"]=QString::number(reinterpret_cast<quintptr>(item->window()),16);
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
inline bool avatarPeopleOwnsPoint(QQuickItem* item,QQuickWindow* window,const QPointF& point) {
    // QQuickItem::childAt does not sort siblings by z. Follow actual stacking
    // order and skip only branches with no enabled input handler at this point.
    // Any foreign overlay/MouseArea/PointerHandler still blocks dispatch.
    if (!item || !window || (!avatarApp(item) && !peopleApp(item) && avatarPeopleControlId(item)!="avatar.entry" && avatarPeopleControlId(item)!="people.entry")) { return false; }
    return picoAvatarInputOwnsPoint(item,window,point);
}

inline QPointF avatarPeopleActivatePoint(QQuickItem* item,const QString& id) {
    // NameCard action controls cover the row center. Its actual delegate leaves
    // a five-pixel leading gutter for ordinary row selection. Never click a
    // foreign child control and claim that it selected the underlying row.
    const double x=(id.startsWith("people.row.") || id=="people.nearby" || id=="people.connections") ? qMin(2.0,item->width()/2) : item->width()/2;
    return item->mapToScene(QPointF(x,item->height()/2));
}
inline bool avatarPeopleSliderPoint(QQuickItem* item,double value,QPointF& point) {
    if (!item || avatarPeopleControlId(item)!="avatar.scale" || !std::isfinite(value) || value<1 || value>40) { return false; }
    const auto low=item->property("from").toDouble(),high=item->property("to").toDouble();
    if (low!=1 || high!=40 || item->property("orientation").toInt()!=Qt::Horizontal) { return false; }
    auto handle=qobject_cast<QQuickItem*>(item->property("handle").value<QObject*>());
    if (!handle || handle->parentItem()!=item || !handle->isVisible()) { return false; }
    double fraction=(value-low)/(high-low);if (item->property("mirrored").toBool()) { fraction=1-fraction; }
    const auto left=item->property("leftPadding").toDouble(),top=item->property("topPadding").toDouble();
    const auto width=item->property("availableWidth").toDouble(),height=item->property("availableHeight").toDouble();
    if (!std::isfinite(left) || !std::isfinite(top) || !std::isfinite(width) || !std::isfinite(height) || width<=handle->width() || handle->width()<=0 || height<=0) { return false; }
    point=item->mapToScene(QPointF(left+handle->width()/2+fraction*(width-handle->width()),top+height/2));return item->contains(item->mapFromScene(point));
}
inline bool avatarPeopleText(const QString& text) {
    if (QRegularExpression("\\A(?:e2e-|hidden-)[0-9a-f]{32}\\z").match(text).hasMatch()) { return true; }
    const QUrl url(text);return text.size()<=4096 && !text.contains(QRegularExpression("[\\x00-\\x20\\x7f]")) && url.isValid() && url.userInfo().isEmpty() && (url.scheme()=="https" || url.scheme()=="http" || url.scheme()=="qrc") && !url.hasFragment();
}
inline bool applyAvatarPeopleInput(QQuickItem* item,QQuickWindow* window,const QString& id,const QString& action,
        const QJsonObject& command,const std::function<bool(QQuickItem*,const QPointF&)>& pointerAt) {
    if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")
            || avatarPeopleControlId(item)!=id || !item || !item->isVisible() || item->window()!=window) {return false;}
    bool delivered=false;
            QJsonObject row;appendAvatarPeopleControl(row,item,id);
            if (!row.value("inputReady").toBool()) { return false; }
            const auto center=avatarPeopleActivatePoint(item,id);
            if (action=="set-value" && id=="avatar.scale" && command.value("value").isDouble()) {
                QPointF point;if (avatarPeopleSliderPoint(item,command.value("value").toDouble(),point) && avatarPeopleOwnsPoint(item,window,point) && pointerAt) { delivered=pointerAt(item,point); }
            } else if (action=="scroll" && id=="avatar.settings.scrollbar") {
                auto thumb=qobject_cast<QQuickItem*>(item->property("contentItem").value<QObject*>());
                const auto direction=command.value("direction").toString();
                if (thumb && thumb->parentItem()==item && (direction=="up" || direction=="down")) {
                    const auto rect=thumb->mapRectToItem(item,QRectF(0,0,thumb->width(),thumb->height()));
                    const auto low=direction=="up" ? 0.0 : rect.bottom(),high=direction=="up" ? rect.top() : item->height();
                    const auto point=item->mapToScene(QPointF(item->width()/2,(low+high)/2));
                    if (high-low>=2 && avatarPeopleOwnsPoint(item,window,point) && pointerAt) { delivered=pointerAt(item,point); }
                }
            } else if (avatarPeopleOwnsPoint(item,window,center)) {
                if (action=="activate" && !id.endsWith(".page") && pointerAt) { delivered=pointerAt(item,center); }
                else if (action=="replace" && id=="avatar.dialog.input" && command.value("text").isString() && avatarPeopleText(command.value("text").toString())) {
                    delivered=overte::ui::replaceFocusedField(item,window,command.value("text").toString());
                }
            }
    return delivered;
}

}
#endif
