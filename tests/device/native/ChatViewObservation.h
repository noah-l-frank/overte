// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "NormalControlUi.h"
#if defined(Q_OS_IOS)
#include "IOSChatRootOwnership.h"
#endif
#include <SettingManager.h>
#include <DependencyManager.h>
#include <QDataStream>
#include <QBuffer>
#include <QDateTime>
#include <QPointer>
#include <QSet>

namespace overte::e2e {
// Passive original QML/ListModel and live Setting::Manager reads. No requested
// state, message input, setting write, cached message list or keyboard request
// may be substituted for these sources.
class ChatViewObservation {
public:
    QVariantMap request(const QVariantMap& input,const QList<QQuickItem*>& roots,bool tabletShown,const QVariantMap& nativeKeyboard) {
        return requestOriginal(input,roots,tabletShown,nativeKeyboard,false);
    }
#if defined(Q_OS_IOS)
    // Explicit diagnostic identity cut. request() keeps its literal DTO;
    // the iOS test bridge marshals this cut only for the selected View-4 profile.
    QVariantMap requestWithLoadedObjectIdentities(const QVariantMap& input,const QList<QQuickItem*>& roots,
            bool tabletShown,const QVariantMap& nativeKeyboard) {
        return requestOriginal(input,roots,tabletShown,nativeKeyboard,true);
    }
#endif
private:
    QVariantMap requestOriginal(const QVariantMap& input,const QList<QQuickItem*>& roots,bool tabletShown,
            const QVariantMap& nativeKeyboard,bool loadedObjectIdentities) {
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
#if defined(Q_OS_IOS)
        _roots.begin(loadedObjectIdentities);const auto rootCensus=_roots.census();
#endif
        QQuickItem* page {nullptr};bool invalid {false},focused {false},hasDraft {false},anyRoot {false};QSet<QQuickItem*> visited;
        std::function<void(QQuickItem*,int)> visit=[&](QQuickItem* item,int depth) {
            if (!item || invalid || visited.contains(item)) { return; }
            if (depth>128 || visited.size()>=4096 || item->thread()!=qApp->thread()) { invalid=true;return; }
            visited.insert(item);
            const auto component=chatComponentSource(item);
            if (!component.isEmpty()) {
                auto actual=chatPage(item);
                auto editor=qobject_cast<QQuickItem*>(createVariant(item->property("messageInput")).value<QObject*>());
                if (actual!=item || !editor || chatPage(editor)!=item) { invalid=true;return; }
                const auto text=editor->property("text");
                if (text.userType()!=QMetaType::QString) { invalid=true;return; }
                hasDraft=hasDraft || !text.toString().isEmpty();
                focused=focused || editor->hasActiveFocus();
                const bool visible=tabletShown && !NormalControlUi::visibleRect(item,item->window()).isEmpty();
#if defined(Q_OS_IOS)
                _roots.page(item,editor,chatModel(item,"localHistory"),chatModel(item,"domainHistory"),component,visible);
#endif
                if (visible) {
                    if (page && page!=item) { invalid=true;return; }page=item;
                }
            }
#if defined(Q_OS_IOS)
            if (item->inherits("QQuickListView") && loginQmlId(item,"listview")) {
                if (auto actual=chatPage(item)) {
                    auto model=qobject_cast<QAbstractItemModel*>(createVariant(item->property("model")).value<QObject*>());
                    _roots.list(actual,item,model);
                }
            }
#endif
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
#if defined(Q_OS_IOS)
            ui.insert("rootIdentity",_roots.identity(page));
#endif
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
        QVariantMap source{{"tabletShown",tabletShown},{"editorFocused",focused},{"editorHasDraft",hasDraft},
            {"keyboard",keyboard},{"ui",ui},{"storage",stored}};
#if defined(Q_OS_IOS)
        source.insert("rootOwnership",_roots.read(true));
        const int version=3;
#else
        const int version=2;
#endif
        const auto captured=tick();if (!captured || captured-started>1500 || _sequence>=9007199254740991ULL) { return {}; }
        QVariantMap original{{"chatViewVersion",version},{"commandId",id},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",captured},{"source",source}};
#if defined(Q_OS_IOS)
        if (loadedObjectIdentities) {
            const auto rootSource=source.value("rootOwnership").toMap();
            if (!rootSource.value("available").toBool() || !rootSource.value("complete").toBool()
                    || !rootSource.value("wholeTreeReady").toBool()) return {};
            auto links=_roots.loadedObjectLinks(rootCensus);if (links.isEmpty()) return {};
            links.insert("rootSourceInstance",rootSource.value("instance"));
            links.insert("rootObservationSequence",rootSource.value("sequence"));
            const auto completed=tick();if (!completed || completed-started>1500) return {};
            const QVariantMap cut{{"chatViewLoadedObjectIdentityCutVersion",1},{"view",original},{"objectLinks",links},
                {"cutCompletedEpochMs",completed}};
            return QJsonDocument::fromVariant(cut).toJson(QJsonDocument::Compact).size()<=131072 ? cut : QVariantMap();
        }
#else
        Q_UNUSED(loadedObjectIdentities);
#endif
        return original;
    }
private:
    class HistoryBuffer final : public QBuffer {
    public:
        using QBuffer::QBuffer;
    protected:
        qint64 writeData(const char* data,qint64 size) override {
            // Private stored entries can have arbitrary extra fields. Bound
            // the actual serialization while writing, before allocating or
            // hashing an unbounded QByteArray. This never changes the value.
            if (size<0 || size>256*1024-buffer().size()) { return -1; }
            return QBuffer::writeData(data,size);
        }
    };
    static bool historyValue(const QVariant& value,int depth,int& nodes,int& characters) {
        if (depth>8 || ++nodes>8192) { return false; }
        if (!value.isValid()) { return true; }
        const auto type=value.userType();
        if (type==QMetaType::Bool || type==QMetaType::Int || type==QMetaType::UInt
                || type==QMetaType::LongLong || type==QMetaType::ULongLong
                || type==QMetaType::Double || type==QMetaType::Float) { return true; }
        if (type==QMetaType::QString) {
            const auto text=value.toString();
            if (text.size()>65536-characters) { return false; }
            characters+=static_cast<int>(text.size());return true;
        }
        if (type==QMetaType::QVariantMap) {
            const auto object=value.toMap();if (object.size()>64) { return false; }
            for (auto it=object.cbegin();it!=object.cend();++it) {
                if (it.key().size()>128 || it.key().size()>65536-characters) { return false; }
                characters+=static_cast<int>(it.key().size());if (!historyValue(it.value(),depth+1,nodes,characters)) { return false; }
            }
            return true;
        }
        if (type==QMetaType::QVariantList || type==QMetaType::QStringList) {
            QVariantList rows;
            if (type==QMetaType::QVariantList) { rows=value.toList(); }
            else {
                const auto texts=value.toStringList();if (texts.size()>1000) { return false; }
                for (const auto& text:texts) { rows.append(text); }
            }
            if (rows.size()>1000) { return false; }
            for (const auto& row:rows) { if (!historyValue(row,depth+1,nodes,characters)) { return false; } }
            return true;
        }
        // Never invoke a custom QVariant stream operator from a passive read.
        return false;
    }
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
        if (!value.isValid() || value.userType()==QMetaType::Bool) { return true; }
        const auto type=value.userType();
        if (type==QMetaType::QString) { return value.toString().size()<=textLimit; }
        if (type!=QMetaType::Int && type!=QMetaType::UInt && type!=QMetaType::LongLong
                && type!=QMetaType::ULongLong && type!=QMetaType::Double && type!=QMetaType::Float) { return false; }
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
        else if (history.userType()==QMetaType::QStringList) {
            kind="string-list";const auto texts=history.toStringList();if (texts.size()>1000) { return {}; }
            for (const auto& value:texts) { original.append(value); }
        }
        else { return {}; }
        if (original.size()>1000) { return {}; }
        int nodes{0},characters{0};if (!historyValue(history,0,nodes,characters)) { return {}; }
        QByteArray historyBytes;HistoryBuffer historyDevice(&historyBytes);
        if (!historyDevice.open(QIODevice::WriteOnly)) { return {}; }
        QDataStream historyStream(&historyDevice);historyStream<<historyPresent<<history;
        if (historyStream.status()!=QDataStream::Ok || historyBytes.size()>256*1024) { return {}; }
        const auto historySha=QString::fromLatin1(QCryptographicHash::hash(historyBytes,QCryptographicHash::Sha256).toHex());
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
        return {{"kind",kind},{"count",original.size()},{"unowned",unowned},{"events",events},
            {"configSha256",configSha},{"valueSha256",historySha}};
    }
    qint64 tick() {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch) { _available=false;return 0; }_epoch=now;return now;
    }
#if defined(Q_OS_IOS)
    IOSChatRootOwnership _roots;
#endif
    const QString _instance{nonce()};QString _generation{nonce()};QPointer<QQuickItem> _page;QPointer<QQuickWindow> _window;
    bool _available{true},_present{false};qint64 _epoch{0};quint64 _sequence{0};
};
} // namespace overte::e2e
#endif
