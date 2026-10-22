// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalControlUi.h"
#include "ChatEmptyHistoryLease.h"
#include <SettingManager.h>
#include <DependencyManager.h>
#include <QDataStream>
#include <QDateTime>
#include <QPointer>
#include <QSet>
#include <QMap>
#include <memory>

namespace overte::e2e {
// Passive original QML/ListModel and live Setting::Manager reads. No requested
// state, message input, setting write, cached message list or keyboard request
// may be substituted for these sources.
class ChatViewObservation {
public:
    QVariantMap request(const QVariantMap& input,const QList<QQuickItem*>& roots,bool tabletShown,const QVariantMap& nativeKeyboard) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || roots.isEmpty()
                || !QCoreApplication::arguments().contains("--testScript") || !_available
                || !DependencyManager::isSet<Setting::Manager>()) { return {}; }
        const auto command=QJsonObject::fromVariantMap(input);const auto keys=command.keys();
        const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue("feature-chat-view-observe")
                || !QRegularExpression("\\A(?:ios-)?[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) { return {}; }
        const auto started=tick();if (!started) { return {}; }
        QQuickItem* page {nullptr};bool invalid {false},focused {false},hasDraft {false},anyRoot {false};QSet<QQuickItem*> visited;
        std::function<void(QQuickItem*,int)> visit=[&](QQuickItem* item,int depth) {
            if (!item || invalid || visited.contains(item)) { return; }
            if (depth>128 || visited.size()>=4096 || item->thread()!=qApp->thread()) { invalid=true;return; }
            visited.insert(item);
            if (!chatComponentSource(item).isEmpty()) {
                auto actual=chatPage(item);
                auto editor=qobject_cast<QQuickItem*>(createVariant(item->property("messageInput")).value<QObject*>());
                if (actual!=item || !editor || chatPage(editor)!=item) { invalid=true;return; }
                const auto text=editor->property("text");
                if (text.userType()!=QMetaType::QString) { invalid=true;return; }
                hasDraft=hasDraft || !text.toString().isEmpty();
                focused=focused || editor->hasActiveFocus();
                if (tabletShown && !NormalControlUi::visibleRect(item,item->window()).isEmpty()) {
                    if (page && page!=item) { invalid=true;return; }page=item;
                }
            }
            for (auto child:item->childItems()) { visit(child,depth+1); }
        };
        for (auto root:roots) { if (root && root->window()) { anyRoot=true;visit(root,0); } }
        if (!anyRoot || invalid) { return {}; }
        QVariantMap ui{{"present",page!=nullptr}};
        if (page) {
            if (_page!=page || !_present || _window!=page->window()) { _generation=nonce(); }
            const auto histories=chatOriginalHistory(page,run);
            auto editor=qobject_cast<QQuickItem*>(createVariant(page->property("messageInput")).value<QObject*>());
            if (histories.isEmpty() || !editor) { return {}; }
            const auto draft=editor->property("text");
            if (draft.userType()!=QMetaType::QString || !chatText(draft.toString())
                    || (!draft.toString().isEmpty() && !draft.toString().endsWith(run))) { return {}; }
            ui=histories;ui.insert("present",true);ui.insert("generation",_generation);
            ui.insert("channel",page->property("pageVal"));ui.insert("draft",editor->property("text"));
            ui.insert("keyboardRequested",page->property("keyboardRaised"));
            // Read the actual visible ListView model too. The selected alias is
            // not evidence that the view really uses that model.
            QQuickItem* list {nullptr};int count {0};bool bad {false};
            std::function<void(QQuickItem*,int)> find=[&](QQuickItem* item,int depth) {
                if (!item || bad) { return; }
                if (++count>4096 || depth>128) { bad=true;return; }
                if (item->inherits("QQuickListView") && loginQmlId(item,"listview") && chatPage(item)==page) {
                    if (list && list!=item) { bad=true;return; }list=item;
                }
                for (auto child:item->childItems()) { find(child,depth+1); }
            };
            find(page,0);if (bad || !list) { return {}; }
            QVariantList visible;int visibleCount {0};
            if (!NormalControlUi::visibleRect(list,list->window()).isEmpty()) {
                auto model=qobject_cast<QAbstractItemModel*>(createVariant(list->property("model")).value<QObject*>());
                if (!model || model->thread()!=qApp->thread() || !rows(model,run,visible)) { return {}; }
                visibleCount=model->rowCount();
            }
            ui.insert("visibleMessages",visible);ui.insert("visibleRowCount",visibleCount);
        } else if (_present) { _generation=nonce(); }
        _page=page;_window=page?page->window():nullptr;_present=page!=nullptr;
        const auto stored=storage(run);if (stored.isEmpty()) { return {}; }
        // OS-derived host metrics may be unavailable (e.g. a VR entity
        // keyboard). Never label QML keyboardRaised as measured visibility.
        QVariantMap keyboard{{"available",false}};
        if (nativeKeyboard.value("valid").userType()==QMetaType::Bool && nativeKeyboard.value("valid").toBool()
                && nativeKeyboard.value("keyboardVisible").userType()==QMetaType::Bool) {
            keyboard={{"available",true},{"backend","native-touch-metrics"},{"visible",nativeKeyboard.value("keyboardVisible")}};
        }
        const auto captured=tick();if (!captured || captured-started>1500 || _sequence>=9007199254740991ULL) { return {}; }
        return {{"chatViewVersion",1},{"commandId",id},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",captured},{"source",QVariantMap{{"tabletShown",tabletShown},{"editorFocused",focused},{"editorHasDraft",hasDraft},
                {"keyboard",keyboard},{"ui",ui},{"storage",stored}}}};
    }
    QVariantMap historyRequest(const QVariantMap& command,const QList<QQuickItem*>& roots,bool tabletShown,const QVariantMap& nativeKeyboard) {
        auto query=command;query.remove("operation");query["action"]="feature-chat-view-observe";
        const auto packet=request(query,roots,tabletShown,nativeKeyboard);if (packet.isEmpty()) { return {}; }
        const auto source=packet.value("source").toMap(),keyboard=source.value("keyboard").toMap();
        const bool closed=!source.value("ui").toMap().value("present").toBool() && !source.value("editorFocused").toBool()
            && !source.value("editorHasDraft").toBool() && keyboard.value("available").toBool() && !keyboard.value("visible").toBool();
        const auto run=command.value("runId").toString(),operation=command.value("operation").toString();
        if (operation=="capture" && !_historyOwner.isEmpty() && _historyOwner!=run) { return {}; }
        if (!_histories.contains(run)) {
            if (_histories.size()>=128 || (operation!="inspect" && operation!="capture")) { return {}; }
            _histories.insert(run,std::make_shared<ChatEmptyHistoryLease>());
        }
        auto manager=DependencyManager::get<Setting::Manager>();
        const auto result=_histories.value(run)->request(command,closed,[manager] {
            QVariantMap actual;
            manager->withReadLock([&] { actual={{"historyPresent",manager->contains("ArmoredChat-Messages")},{"history",manager->value("ArmoredChat-Messages")},
                {"configPresent",manager->contains("ArmoredChat-Config")},{"config",manager->value("ArmoredChat-Config")}}; });
            return actual;
        },[manager](const QVariantMap& expected,const QVariantMap& original) { return manager->featureRestoreEmptyChat(expected,original); });
        if (!result.isEmpty()) {
            const auto actual=result.value("source").toMap();
            if (actual.value("scopePresent").toBool()) { _historyOwner=run; }
            if (actual.value("retired").toBool() && _historyOwner==run) { _historyOwner.clear(); }
        }
        return result;
    }
private:
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool rows(QAbstractItemModel* model,const QString& run,QVariantList& result) {
        if (!model || model->rowCount()<0 || model->rowCount()>1000) { return false; }
        const auto role=model->roleNames().key(QByteArray("text"),-1);
        if (role<0 && model->rowCount()) { return false; }
        for (int index=0;index<model->rowCount();++index) {
            const auto actual=model->data(model->index(index,0),role);
            if (actual.userType()!=QMetaType::QString) { return false; }
            const auto text=actual.toString();
            if (chatText(text) && !text.isEmpty() && text.endsWith(run)) { result.append(actual); }
        }
        return true;
    }
    static bool scalar(const QVariant& value,int textLimit) {
        if (!value.isValid() || value.isNull() || value.userType()==QMetaType::Bool) { return true; }
        if (value.userType()==QMetaType::QString) { return value.toString().size()<=textLimit; }
        bool okay {false};const auto number=value.toDouble(&okay);
        return okay && std::isfinite(number) && std::abs(number)<=9007199254740991.0;
    }
    static QVariantMap storage(const QString& run) {
        auto manager=DependencyManager::get<Setting::Manager>();bool historyPresent {false},configPresent {false};QVariant history,config;
        // The existing manager uses a recursive read lock. Keep presence and
        // both original values atomic across the public, thread-safe reads.
        manager->withReadLock([&] {
            historyPresent=manager->contains("ArmoredChat-Messages");history=manager->value("ArmoredChat-Messages");
            configPresent=manager->contains("ArmoredChat-Config");config=manager->value("ArmoredChat-Config");
        });
        if (config.userType()==QMetaType::QVariantMap) {
            const auto object=config.toMap();if (object.size()>32) { return {}; }
            for (auto it=object.cbegin();it!=object.cend();++it) {
                if (it.key().size()>128 || !scalar(it.value(),256)) { return {}; }
            }
        } else if (!scalar(config,256)) { return {}; }
        QByteArray configBytes;QDataStream stream(&configBytes,QIODevice::WriteOnly);stream<<configPresent<<config;
        if (stream.status()!=QDataStream::Ok || configBytes.size()>16384) { return {}; }
        const auto configSha=QString::fromLatin1(QCryptographicHash::hash(configBytes,QCryptographicHash::Sha256).toHex());
        QString kind;QVariantList original;
        if (!historyPresent) { kind="unset"; }
        else if (!history.isValid() || history.isNull()) { kind="null"; }
        else if (history.userType()==QMetaType::QString && history.toString().isEmpty()) { kind="empty-string"; }
        else if (history.userType()==QMetaType::QVariantList) { kind="array";original=history.toList(); }
        else if (history.userType()==QMetaType::QStringList) { kind="string-list";for (const auto& value:history.toStringList()) { original.append(value); } }
        else { return {}; }
        if (original.size()>1000) { return {}; }
        QVariantList events;int unowned {0};
        for (const auto& entry:original) {
            if (entry.userType()!=QMetaType::QVariantMap) { ++unowned;continue; }
            const auto value=entry.toMap();const auto raw=value.value("message");const auto channel=value.value("channel");
            if (raw.userType()!=QMetaType::QString || !chatText(raw.toString()) || raw.toString().isEmpty() || !raw.toString().endsWith(run)) {
                ++unowned;continue;
            }
            if (channel.userType()!=QMetaType::QString || (channel.toString()!="local" && channel.toString()!="domain")) { return {}; }
            const auto stamp=value.value("timestamp");bool okay {false};const auto epoch=stamp.toDouble(&okay);
            if (!okay || stamp.userType()==QMetaType::Bool || stamp.userType()==QMetaType::QString || !std::isfinite(epoch)
                    || epoch<=0 || epoch>9007199254740991.0 || std::floor(epoch)!=epoch) { return {}; }
            // Display names and arbitrary extra/private fields are never kept.
            events.append(QVariantMap{{"channel",channel},{"text",raw},{"timestamp",stamp}});
        }
        return {{"kind",kind},{"count",original.size()},{"unowned",unowned},{"events",events},{"configSha256",configSha}};
    }
    qint64 tick() {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch) { _available=false;return 0; }_epoch=now;return now;
    }
    QMap<QString,std::shared_ptr<ChatEmptyHistoryLease>> _histories;QString _historyOwner;
    const QString _instance{nonce()};QString _generation{nonce()};QPointer<QQuickItem> _page;QPointer<QQuickWindow> _window;
    bool _available{true},_present{false};qint64 _epoch{0};quint64 _sequence{0};
};
} // namespace overte::e2e
#endif
