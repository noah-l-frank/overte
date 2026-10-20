// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "NormalCreateControls.h"
#include <QAbstractItemModel>

namespace overte::e2e {
#if defined(OVERTE_E2E_FEATURE_TESTS)
// These reads inspect the actual original QML/model. No QML handler is invoked
// and neither a send acknowledgement nor an expected message becomes a row.
inline QString chatComponentSource(QQuickItem* item) {
    if (!audioGuiItem(item) || !loginQmlId(item,"root")) { return {}; }
    int depth {0};
    for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
        const auto source=context->baseUrl();
        if (context->nameForObject(item)=="root" && (source.scheme()=="file" || source.scheme()=="qrc")
                && source.authority().isEmpty() && !source.hasQuery() && !source.hasFragment()
                && source.path().endsWith("/armored-chat/armored_chat.qml")) { return source.toString(); }
    }
    return {};
}
inline QQuickItem* chatPage(QQuickItem* item) {
    if (!audioGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
        const auto channel=parent->property("pageVal"),tablet=parent->property("tabletMode");
        if (!chatComponentSource(parent).isEmpty() && channel.userType()==QMetaType::QString
                && QStringList{"local","domain","settings"}.contains(channel.toString())
                && tablet.userType()==QMetaType::Bool && tablet.toBool()
                && parent->property("keyboardRaised").userType()==QMetaType::Bool
                && parent->metaObject()->indexOfSignal("sendToScript(QVariant)")>=0) { return parent; }
    }
    return nullptr;
}
inline bool chatText(const QString& value) {
    return value.isEmpty() || QRegularExpression(QStringLiteral("\\A(?:Overte ä Ω 東京 |(?:reply|hidden|retry)-)[0-9a-f]{32}\\z")).match(value).hasMatch();
}
inline QAbstractItemModel* chatModel(QQuickItem* page,const char* name) {
    if (!page || chatPage(page)!=page) { return nullptr; }
    const auto original=createVariant(page->property(name));
    auto model=qobject_cast<QAbstractItemModel*>(original.value<QObject*>());
    return model && model->thread()==page->thread() && model->rowCount()>=0 && model->rowCount()<=1000 ? model : nullptr;
}
inline QVariantMap chatOriginalHistory(QQuickItem* page,const QString& run) {
    if (!page || chatPage(page)!=page || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
    QVariantMap result;
    for (const auto& channel:QStringList{"local","domain"}) {
        const auto name=(channel+"History").toLatin1();auto model=chatModel(page,name.constData());
        if (!model) { return {}; }
        const auto roles=model->roleNames();const auto role=roles.key(QByteArray("text"),-1);
        if (role<0 && model->rowCount()) { return {}; }
        QVariantList rows;
        for (int index=0;index<model->rowCount();++index) {
            const auto actual=model->data(model->index(index,0),role);
            if (actual.userType()!=QMetaType::QString) { return {}; }
            const auto text=actual.toString();
            // Filter, never manufacture, original model text. Preserve order
            // and multiplicity. Do not retain other runs or private messages.
            if (chatText(text) && !text.isEmpty() && text.endsWith(run)) { rows.append(actual); }
        }
        result.insert(channel+"Messages",rows);result.insert(channel+"RowCount",model->rowCount());
    }
    return result;
}
inline QString chatControlId(QQuickItem* item) {
    if (!audioGuiItem(item)) { return {}; }
    auto page=chatPage(item);
    if (!page) {
        const auto nav=scriptControlId(item);
        if (nav=="tablet.home" || nav.startsWith("tablet.page.")) { return nav; }
        return item->metaObject()->indexOfSignal("clicked()")>=0 && item->property("text").toString()=="CHAT"
            ? QStringLiteral("chat.entry") : QString();
    }
    if (page==item) { return "chat.page"; }
    const auto name=item->objectName();
    if (name=="chatMessageInput" && item->inherits("QQuickTextEdit")) { return "chat.input"; }
    if (name=="chatSend" && item->metaObject()->indexOfSignal("clicked()")>=0) { return "chat.send"; }
    if (name=="chatClose" && item->metaObject()->indexOfSignal("clicked()")>=0) { return "chat.close"; }
    if (item->inherits("QQuickMouseArea") && item->parentItem()) {
        if (loginQmlId(item->parentItem(),"local_page")) { return "chat.local"; }
        if (loginQmlId(item->parentItem(),"domain_page")) { return "chat.domain"; }
    }
    return {};
}
inline void appendChatControlObservation(QJsonObject& row,QQuickItem* item,const QString& id) {
    if (!audioGuiItem(item)) { return; }
    bool ready=item->isEnabled() && id!="chat.page";
    auto page=chatPage(item);
    if (id=="chat.page") {
        auto local=chatModel(page,"localHistory"),domain=chatModel(page,"domainHistory");
        if (!local || !domain) { row["inputReady"]=false;return; }
        row["profile"]="armored-chat-native-v1";row["channel"]=page->property("pageVal").toString();
        // This is the original QML request, not proof of a visible OS/VR
        // keyboard. The complete adapter must independently inspect that UI.
        row["keyboardRequested"]=page->property("keyboardRaised").toBool();
        row["localRowCount"]=local->rowCount();row["domainRowCount"]=domain->rowCount();
        row["componentSourceSha256"]=QString::fromLatin1(QCryptographicHash::hash(chatComponentSource(page).toUtf8(),QCryptographicHash::Sha256).toHex());
    } else if (id=="chat.input") {
        const auto actual=item->property("text");
        if (actual.userType()!=QMetaType::QString || !chatText(actual.toString())) { row["inputReady"]=false;return; }
        row["text"]=actual.toString();
    } else if (!page) { ready=ready && (id=="chat.entry" || id=="tablet.home" || id.startsWith("tablet.page.")); }
    row["inputReady"]=ready;
}
inline QString chatControlSource(QQuickItem* item,const QString& id) {
    QJsonObject row;appendChatControlObservation(row,item,id);
    if (auto page=chatPage(item)) {
        row["sourceChannel"]=page->property("pageVal").toString();
        row["sourceKeyboardRequest"]=page->property("keyboardRaised").toBool();
        auto editor=qobject_cast<QQuickItem*>(createVariant(page->property("messageInput")).value<QObject*>());
        if (!editor || chatPage(editor)!=page) { return {}; }
        const auto actual=editor->property("text");
        if (actual.userType()!=QMetaType::QString || !chatText(actual.toString())) { return {}; }
        row["sourceDraftSha256"]=QString::fromLatin1(QCryptographicHash::hash(actual.toString().toUtf8(),QCryptographicHash::Sha256).toHex());
        row["sourceEditorFocus"]=editor->hasActiveFocus();
    }
    return QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(row).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
}
#endif
} // namespace overte::e2e
