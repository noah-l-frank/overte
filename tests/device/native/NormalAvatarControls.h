// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalPlacesControls.h"
#include "NormalCreateControls.h"
#include <QAbstractItemModel>
#include <QKeyEvent>
#include <QQuickWindow>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
namespace overte::e2e {
inline QString avatarComponentSource(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (source.scheme()=="file" && !QDir::cleanPath(source.toLocalFile()).startsWith(
                QDir::cleanPath(QCoreApplication::applicationDirPath())+"/")) { continue; }
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/hifi/AvatarApp.qml")) { return source.toString(); }
        if (context->nameForObject(item)=="pal" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/hifi/Pal.qml")) { return source.toString(); }
    }
    return {};
}
inline QQuickItem* avatarPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (!avatarComponentSource(parent).isEmpty()
                && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) { return parent; }
    }
    return nullptr;
}
inline QObject* avatarNamed(QQuickItem* root,const QString& name) {
    if (avatarComponentSource(root).isEmpty()) { return nullptr; }
    const auto objects=root->findChildren<QObject*>();if (objects.size()>4096) { return nullptr; }
    QObject* result {nullptr};
    for (auto object:objects) {
        int depth {0};bool matches {false};
        for (auto context=qmlContext(object);context && ++depth<=128;context=context->parentContext()) {
            if (context->nameForObject(object)==name) { matches=true;break; }
        }
        if (matches) { if (result && result!=object) { return nullptr; }result=object; }
    }
    return result;
}
inline QString avatarRootId(QQuickItem* root) {
    if (avatarComponentSource(root).isEmpty()) { return {}; }
    struct Entry { QPointer<QQuickItem> object;QString id; };static QVector<Entry> roots;
    for (int index=roots.size()-1;index>=0;--index) { if (!roots[index].object) { roots.remove(index); } }
    for (const auto& row:roots) { if (row.object==root) { return row.id; } }
    if (roots.size()>=256) { return {}; }
    const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);roots.append({root,id});return id;
}
inline QString avatarDialog(QQuickItem* page) {
    const auto source=avatarComponentSource(page);
    if (source.endsWith("/Pal.qml")) {
        const auto prompt=avatarNamed(page,"connectionPrompt");
        if (!prompt || prompt->property("visible").userType()!=QMetaType::Bool) { return {}; }
        return prompt->property("visible").toBool() ? "connection" : "none";
    }
    QString result="none";
    for (const auto& entry:QList<QPair<QString,QString>>{{"popup","popup"},{"createFavorite","favorite"},
            {"settings","settings"},{"adjustWearables","wearables"}}) {
        const auto object=avatarNamed(page,entry.first);
        if (!object || object->property("visible").userType()!=QMetaType::Bool) { return {}; }
        if (object->property("visible").toBool()) {
            // The wearable URL popup can cover the existing AdjustWearables
            // surface. Retain the actual topmost popup, without opening it.
            if (result=="none" || entry.second=="popup") { result=entry.second; }
            else if (result!="popup" || entry.second!="wearables") { return {}; }
        }
    }
    return result;
}
inline QString avatarKey(const QString& value) {
    return value.isEmpty() || value.size()>4096 ? QString() :
        QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(),QCryptographicHash::Sha256).toHex().left(32));
}
inline QQuickItem* avatarNameCard(QQuickItem* item) {
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        if (loginQmlId(parent,"thisNameCard") && parent->property("uuid").userType()==QMetaType::QString
                && parent->property("userName").userType()==QMetaType::QString) { return parent; }
    }
    return nullptr;
}
inline QString avatarControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto page=avatarPage(item);
    if (!page) {
        const auto nav=scriptControlId(item);
        if (nav=="tablet.home" || nav.startsWith("tablet.page.")) { return nav; }
        if (item->metaObject()->indexOfSignal("clicked()")>=0) {
            if (item->property("text").toString()=="AVATAR") { return "avatar.entry"; }
            if (item->property("text").toString()=="PEOPLE") { return "people.entry"; }
        }
        return {};
    }
    const bool people=avatarComponentSource(page).endsWith("/Pal.qml");
    if (page==item) { return people ? "people.page" : "avatar.page"; }
    if (people) {
        const QHash<QString,QString> fixed {{"peopleConnectionAccept","people.accept"},
            {"peopleConnectionDecline","people.decline"},{"peopleConnectionCancel","people.cancel"}};
        if (fixed.contains(item->objectName())) { return fixed.value(item->objectName()); }
        if (auto card=avatarNameCard(item)) {
            const auto id=QUuid(card->property("uuid").toString()).toString(QUuid::WithoutBraces);
            if (card==item && !QUuid(id).isNull()) { return "people.select."+id; }
            if (card==item && QUuid(id).isNull() && page->property("activeTab").toString()=="connectionsTab") {
                const auto key=avatarKey(card->property("userName").toString());
                if (!key.isEmpty()) { return "people.connection-select."+key; }
            }
            if (!QUuid(id).isNull() && item->objectName()=="peopleRequestConnection") { return "people.request."+id; }
            if (item->inherits("QQuickMouseArea")) {
                const auto target=QQmlProperty(item,"anchors.fill",qmlContext(item)).read().value<QObject*>();
                if (target && loginQmlId(target,"nameCardRemoveConnectionImage")) {
                    const auto key=avatarKey(card->property("userName").toString());
                    if (!key.isEmpty()) { return "people.remove."+key; }
                }
            }
        }
        if (item->inherits("QQuickMouseArea")) {
            const auto parent=item->parentItem();
            if (parent && loginQmlId(parent,"nearbyTabSelector")) { return "people.nearby"; }
            if (parent && loginQmlId(parent,"connectionsTabSelector")) { return "people.connections"; }
        }
        return {};
    }
    if (loginQmlId(item,"linkLabel")) { return "avatar.url-open"; }
    if (loginQmlId(item,"adjustLabel")) { return "avatar.wearables-open"; }
    if (loginQmlId(item,"settingsMouseArea")) { return "avatar.settings-open"; }
    if (loginQmlId(item,"scaleSlider") && item->inherits("QQuickSlider")) { return "avatar.scale"; }
    if (item->inherits("QQuickComboBox") && item->parentItem()
            && loginQmlId(item->parentItem(),"wearablesCombobox")) { return "avatar.wearable-choice"; }
    const auto popup=avatarNamed(page,"popup"),favorite=avatarNamed(page,"createFavorite"),
        settings=avatarNamed(page,"settings"),wearables=avatarNamed(page,"adjustWearables");
    if (item->inherits("QQuickTextInput")) {
        if (popup && placesDescendant(item,popup) && loginQmlId(item,"input")) { return "avatar.url"; }
        if (favorite && placesDescendant(item,favorite) && loginQmlId(item,"favoriteName")) { return "avatar.favorite-name"; }
    }
    if (item->inherits("QQuickMouseArea")) {
        const auto target=QQmlProperty(item,"anchors.fill",qmlContext(item)).read().value<QObject*>();
        if (target && loginQmlId(target,"star")) { return "avatar.favorite-add"; }
        if (item->parentItem() && item->parentItem()->property("text").toString()==
                (page->property("isInManageState").toBool() ? "Back" : "Manage")) { return "avatar.manage"; }
        if (loginQmlId(item,"favoriteAvatarMouseArea")) {
            const auto context=qmlContext(item);const auto name=context ? context->contextProperty("name") : QVariant();
            if (name.userType()==QMetaType::QString) {
                const auto key=avatarKey(name.toString());if (!key.isEmpty()) { return "avatar.favorite."+key; }
            }
        }
    }
    if (item->metaObject()->indexOfSignal("clicked()")>=0) {
        const bool yes=loginQmlId(item,"yesButton"),no=loginQmlId(item,"noButton");
        if (yes || no) {
            for (const auto& entry:QList<QPair<QObject*,QString>>{{popup,"avatar.popup."},{favorite,"avatar.favorite."},
                    {settings,"avatar.settings."},{wearables,"avatar.wearables."}}) {
                if (entry.first && placesDescendant(item,entry.first)) { return entry.second+(yes ? "confirm" : "cancel"); }
            }
        }
        if (wearables && placesDescendant(item,wearables) && item->property("text").toString()=="TAKE IT OFF") {
            return "avatar.wearable-remove";
        }
    }
    if (wearables && placesDescendant(item,wearables) && item->inherits("QQuickText")
            && item->property("text").toString()=="<a href='#'>Add custom</a>") { return "avatar.wearable-add"; }
    return {};
}
inline bool avatarField(const QString& id) { return id=="avatar.url" || id=="avatar.favorite-name"; }
inline QVariantList avatarWearableChoices(QQuickItem* page) {
    const auto owner=avatarNamed(page,"wearablesCombobox");
    const auto inner=owner ? createVariant(owner->property("comboBox")).value<QObject*>() : nullptr;
    const auto original=inner ? createVariant(inner->property("model")) : QVariant();
    auto model=qobject_cast<QAbstractItemModel*>(original.value<QObject*>());
    if (!model || model->thread()!=QThread::currentThread() || model->rowCount()>64) { return {}; }
    const auto roles=model->roleNames();const auto idRole=roles.key(QByteArray("id"),-1);
    if (idRole<0 && model->rowCount()) { return {}; }
    QVariantList result;
    for (int index=0;index<model->rowCount();++index) {
        const auto originalId=model->data(model->index(index,0),idRole);const auto id=QUuid(originalId.toString());
        if (id.isNull()) { return {}; }result.append(id.toString(QUuid::WithoutBraces));
    }
    return result;
}
inline QString avatarSelectedWearable(QQuickItem* page) {
    const auto owner=avatarNamed(page,"wearablesCombobox");
    if (!owner || owner->property("currentIndex").userType()!=QMetaType::Int) { return {}; }
    const auto choices=avatarWearableChoices(page);const auto index=owner->property("currentIndex").toInt();
    return index>=0 && index<choices.size() ? choices[index].toString() : QString();
}
inline bool avatarText(const QString& value) {
    if (value.size()>4096) { return false; }
    for (auto character:value) { if (character.unicode()<32 || character.unicode()==127) { return false; } }
    return true;
}
inline void appendAvatarControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    auto page=avatarPage(item);bool ready=item->isEnabled() && id!="avatar.page" && id!="people.page";
    row["inputReady"]=ready;
    if (!page) { return; }
    const auto dialog=avatarDialog(page),root=avatarRootId(page),source=avatarComponentSource(page);
    if (dialog.isEmpty() || root.isEmpty()) { row["inputReady"]=false;return; }
    row["rootId"]=root;row["qmlSource"]=source;
    if (id=="avatar.page") {
        const auto popup=avatarNamed(page,"popup");
        row["profile"]="ios-avatar-people-native-v1";row["dialog"]=dialog;
        row["popupTitle"]=popup ? popup->property("titleText").toString() : QString();
        row["manage"]=page->property("isInManageState").toBool();
        row["favoriteName"]=page->property("avatarName").toString();
        row["favoritePresent"]=page->property("isAvatarInFavorites").toBool();
    } else if (id=="people.page") {
        const auto state=createVariant(page->property("connectionState"));
        if (state.userType()!=QMetaType::QVariantMap) { row["inputReady"]=false;return; }
        row["profile"]="ios-avatar-people-native-v1";row["dialog"]=dialog;
        row["connectionState"]=QJsonObject::fromVariantMap(state.toMap());
        row["activeTab"]=page->property("activeTab").toString();
    } else if (avatarField(id)) {
        const auto actual=item->property("text");
        if (actual.userType()!=QMetaType::QString || !avatarText(actual.toString())) { row["inputReady"]=false;return; }
        row["text"]=actual.toString();
    } else if (id=="avatar.scale") {
        row["value"]=item->property("value").toDouble()/10;
        row["minimum"]=item->property("from").toDouble()/10;row["maximum"]=item->property("to").toDouble()/10;
    } else if (id=="avatar.wearable-choice") {
        row["choices"]=QJsonArray::fromVariantList(avatarWearableChoices(page));
        row["index"]=item->property("currentIndex").toInt();
    } else if (id=="avatar.wearable-remove") {
        row["selectedId"]=avatarSelectedWearable(page);
        if (row["selectedId"].toString().isEmpty()) { row["inputReady"]=false; }
    } else if (id=="avatar.favorite.confirm") {
        const auto conflict=avatarNamed(page,"wrongName");
        if (!conflict || conflict->property("visible").userType()!=QMetaType::Bool) { row["inputReady"]=false;return; }
        row["nameConflict"]=conflict->property("visible").toBool();
    } else if (id.startsWith("avatar.favorite.") && id.size()==QString("avatar.favorite.").size()+32) {
        const auto context=qmlContext(item);row["name"]=context ? context->contextProperty("name").toString() : QString();
    } else if (id.startsWith("people.request.") || id.startsWith("people.remove.") || id.startsWith("people.select.")
            || id.startsWith("people.connection-select.")) {
        const auto card=avatarNameCard(item);
        if (!card) { row["inputReady"]=false;return; }
        row["peerSession"]=QUuid(card->property("uuid").toString()).toString(QUuid::WithoutBraces);
        row["username"]=card->property("userName").toString();
        row["selected"]=card->property("selected").toBool();row["present"]=card->property("isPresent").toBool();
        row["replicated"]=card->property("isReplicated").toBool();
        ready=ready && (id.startsWith("people.select.") || id.startsWith("people.connection-select.")
            || card->property("selected").toBool()) && !card->property("isMyCard").toBool()
            && card->property("isPresent").toBool() && !card->property("isReplicated").toBool();row["inputReady"]=ready;
    }
}
inline QString avatarControlSource(QQuickItem* item,const QString& id) {
    if (!item || !item->window() || avatarControlId(item)!=id) { return {}; }
    QJsonObject row;appendAvatarControlObservation(row,item,id);
    if (auto page=avatarPage(item)) {
        row["sourceDialog"]=avatarDialog(page);row["sourceManage"]=page->property("isInManageState").toBool();
        const auto popup=avatarNamed(page,"popup");
        if (popup) {
            row["sourcePopupTitle"]=popup->property("titleText").toString();
            const auto editor=createVariant(popup->property("inputText")).value<QObject*>();
            if (editor) { row["sourceDraft"]=editor->property("text").toString(); }
        }
        row["sourceConnection"]=QJsonValue::fromVariant(createVariant(page->property("connectionState")));
        row["sourceSelectedWearable"]=avatarSelectedWearable(page);
    }
    const auto center=item->mapToScene(QPointF(item->width()/2,item->height()/2));
    row["sceneX"]=center.x();row["sceneY"]=center.y();row["width"]=item->width();row["height"]=item->height();
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
inline bool avatarSliderPoint(QQuickItem* item,double scale,QPointF& point) {
    if (avatarControlId(item)!="avatar.scale" || !std::isfinite(scale) || scale<.1 || scale>4
            || std::abs(scale*10-std::round(scale*10))>.0001) { return false; }
    const auto low=item->property("from").toDouble(),high=item->property("to").toDouble();
    auto handle=qobject_cast<QQuickItem*>(item->property("handle").value<QObject*>());
    if (low!=1 || high!=40 || !handle || handle->parentItem()!=item || !handle->isVisible()) { return false; }
    double fraction=(scale*10-low)/(high-low);if (item->property("mirrored").toBool()) { fraction=1-fraction; }
    const auto left=item->property("leftPadding").toDouble(),top=item->property("topPadding").toDouble(),
        width=item->property("availableWidth").toDouble(),height=item->property("availableHeight").toDouble();
    if (!std::isfinite(left) || !std::isfinite(top) || !std::isfinite(width) || !std::isfinite(height)
            || width<=handle->width() || handle->width()<=0 || height<=0) { return false; }
    point=item->mapToScene(QPointF(left+handle->width()/2+fraction*(width-handle->width()),top+height/2));
    return std::isfinite(point.x()) && std::isfinite(point.y()) && item->contains(item->mapFromScene(point));
}
inline bool avatarSelectChoice(QQuickItem* item,QQuickWindow* window,qint64 index) {
    if (!item || !window || avatarControlId(item)!="avatar.wearable-choice" || !item->isEnabled()
            || !item->inherits("QQuickComboBox") || index<0 || index>=64 || index>=item->property("count").toInt()) { return false; }
    const auto ownsFocus=[&]() {
        for (auto focus=window->activeFocusItem();focus;focus=focus->parentItem()) { if (focus==item) { return true; } }
        auto popup=item->property("popup").value<QObject*>();
        auto content=popup ? qobject_cast<QQuickItem*>(popup->property("contentItem").value<QObject*>()) : nullptr;
        if (!popup || !popup->property("visible").toBool() || !content || content->window()!=window) { return false; }
        for (auto focus=window->activeFocusItem();focus;focus=focus->parentItem()) { if (focus==content) { return true; } }
        return false;
    };
    if (!ownsFocus()) { return false; }
    QPointer<QQuickItem> original=item;QPointer<QQuickWindow> surface=window;
    auto key=[&](int code) {
        if (!original || !surface || !ownsFocus()) { return false; }
        QKeyEvent down(QEvent::KeyPress,code,Qt::NoModifier);const bool delivered=QCoreApplication::sendEvent(surface,&down);
        if (!surface) { return false; }QKeyEvent up(QEvent::KeyRelease,code,Qt::NoModifier);
        return QCoreApplication::sendEvent(surface,&up) && delivered;
    };
    bool delivered=key(Qt::Key_Home);
    for (qint64 offset=0;delivered && offset<index;++offset) { delivered=key(Qt::Key_Down); }
    return delivered && key(Qt::Key_Return);
}
} // namespace overte::e2e
#endif
