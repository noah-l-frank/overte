// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "NormalControlUi.h"
#include <PathUtils.h>
#include <QJsonObject>
#include <QQmlContext>
#include <QQmlEngine>
#include <QVector>

namespace overte::e2e {
// Original page/field/context identities, not an input-order generation counter.
// Reading this source never opens a page, changes a draft or assigns focus.
class PhoneLifecycleEditor {
public:
    static QMap<QString,QUrl> sources() {
        const auto root=PathUtils::defaultScriptsLocation();
        if(!root.isLocalFile() || root.hasQuery() || root.hasFragment())return {};
        const QDir directory(root.toLocalFile());
        return {{"create",QUrl::fromLocalFile(directory.filePath("system/create/qml/NativeCreate.qml"))},
            {"chat",QUrl::fromLocalFile(directory.filePath("communityScripts/armored-chat/armored_chat.qml"))},
            {"scripts",PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml")}};
    }
    QVariantMap observe(QQuickItem* root,QQuickWindow* window,const QString& run,bool osKeyboard) {
        if(!gui() || !hex(run) || _busy || !_valid || !root || !window || root->window()!=window
                || root->thread()!=qApp->thread() || window->thread()!=qApp->thread())return {};
        const auto epoch=now();if(!epoch)return {};
        const auto canonical=sources();if(canonical.size()!=3)return {};
        QSet<QQuickItem*> visited;Field selected;int matches=0;bool invalid=false;
        std::function<void(QQuickItem*,int)> walk=[&](QQuickItem* item,int depth) {
            if(!item || invalid)return;
            if(depth>128 || visited.size()>=4096 || visited.contains(item) || item->thread()!=qApp->thread()) { invalid=true;return; }
            visited.insert(item);
            const auto name=item->objectName();
            const QString editor=name=="NativeCreateText" ? "create" : name=="chatMessageInput" ? "chat" : name=="scriptFilter" ? "scripts" : "";
            if(!editor.isEmpty()) {
                const QString id=editor=="create" ? "newText" : editor=="chat" ? "textArea" : "filter";
                QQmlContext* original=nullptr;int contexts=0;
                for(auto context=qmlContext(item);context && ++contexts<=128;context=context->parentContext()) {
                    if(context->thread()!=qApp->thread()) { invalid=true;return; }
                    if(context->nameForObject(item)==id && context->baseUrl()==canonical.value(editor)) { original=context;break; }
                }
                const auto visible=NormalControlUi::visibleRect(item,window);
                if(!visible.isEmpty()) {
                    if(!original || !item->isEnabled() || item->property("readOnly").toBool() || ++matches>1) { invalid=true;return; }
                    const auto text=item->property("text");
                    if(text.userType()!=QMetaType::QString || !ownedText(editor,run,text.toString())) { invalid=true;return; }
                    auto page=original->contextObject();
                    if(!page || page->thread()!=qApp->thread()) { invalid=true;return; }
                    selected={editor,item,window,original,page,text.toString(),visible};
                }
            }
            for(auto child:item->childItems())walk(child,depth+1);
        };
        walk(root,0);if(invalid)return {};
        int current=-1;
        if(matches) {
            for(int index=0;index<_seen.size();++index) {
                const auto& old=_seen[index];
                if(old.field && old.field==selected.field && old.window==selected.window && old.context==selected.context && old.page==selected.page) { current=index;break; }
            }
            if(current<0) {
                if(_seen.size()>=64)return {};
                _seen.append({selected.editor,selected.field,selected.window,selected.context,selected.page,nonce(),nonce(),epoch,0});current=_seen.size()-1;
            }
        }
        QVariantList identities;
        for(int index=0;index<_seen.size();++index) {
            auto& old=_seen[index];const bool attached=old.field && old.field->window()==window && visited.contains(old.field);
            const bool alive=old.field && old.window && old.context && old.page;
            const bool active=index==current;
            if(!active && !old.retired && (!alive || !attached || current>=0))old.retired=epoch;
            // An actual old source returning after retirement is not a newly
            // created editor. Preserve its identity and reject its reuse.
            if(active && old.retired)return {};
            identities.append(QVariantMap{{"editor",old.editor},{"token",old.token},{"fieldToken",old.fieldToken},
                {"sourceUrl",canonical.value(old.editor).toString(QUrl::FullyEncoded)},{"createdEpochMs",old.created},
                {"retiredEpochMs",old.retired},{"alive",alive},{"attached",attached},{"active",active}});
        }
        QVariantMap currentField{{"status","none"}};
        if(current>=0) {
            const auto& old=_seen[current];
            currentField={{"status","ready"},{"editor",old.editor},{"token",old.token},{"fieldToken",old.fieldToken},
                {"sourceUrl",canonical.value(old.editor).toString(QUrl::FullyEncoded)},{"text",selected.text},
                {"focused",selected.field->hasActiveFocus()},{"frame",QVariantList{selected.frame.x(),selected.frame.y(),selected.frame.width(),selected.frame.height()}}};
            _issued.insert(_sequence+1,{run,old.fieldToken,epoch});
        }
        for(auto it=_issued.begin();it!=_issued.end();)if(epoch-it->epoch>5000)it=_issued.erase(it);else ++it;
        if(_issued.size()>256)return {};
        _current=selected;_currentToken=current<0 ? QString() : _seen[current].fieldToken;
        QVariantMap urls;for(auto it=canonical.cbegin();it!=canonical.cend();++it)urls.insert(it.key(),it->toString(QUrl::FullyEncoded));
        return {{"phoneLifecycleEditorVersion",1},{"instance",_instance},{"sequence",++_sequence},{"capturedEpochMs",epoch},
            {"canonicalSources",urls},{"current",currentField},{"contexts",identities},{"osKeyboardVisible",osKeyboard}};
    }
    bool input(const QVariantMap& command,QQuickItem* root,QQuickWindow* window,bool keyboard) {
        if(!gui() || _busy)return false;
        const auto run=command.value("runId").toString(),id=command.value("commandId").toString();
        const auto operation=command.value("operation").toString();
        const auto json=QJsonObject::fromVariantMap(command);const auto sequence=json.value("observationSequence").toDouble(-1);
        if(!hex(run) || !hex(id) || _commands.contains(id) || _commands.size()>=256
                || command.keys()!=QStringList{"action","commandId","fieldToken","observationSequence","operation","runId","schemaVersion"}
                || command.value("action")!="phone-lifecycle-editor-input"
                || json.value("schemaVersion")!=QJsonValue(1) || !json.value("observationSequence").isDouble()
                || !std::isfinite(sequence) || sequence<1 || sequence>9007199254740991.0 || std::floor(sequence)!=sequence
                || !QStringList{"focus","type"}.contains(operation))return false;
        _commands.insert(id); // A rejected/uncertain admitted input is never replayed.
        const auto issued=_issued.value(command.value("observationSequence").toULongLong());
        const auto actual=observe(root,window,run,keyboard);
        if(actual.isEmpty() || issued.run!=run || issued.token!=command.value("fieldToken").toString()
                || issued.token!=_currentToken || now()-issued.epoch>5000 || !_current.field || !_current.window)return false;
        _busy=true;bool delivered=false;
        QPointer<QQuickItem> field=_current.field;QPointer<QQuickWindow> surface=_current.window;
        if(operation=="focus")delivered=NormalControlUi::pointerEvent(field,surface,_current.frame.center(),false);
        else if(field->hasActiveFocus()) {
            const QString text=_current.editor=="create" ? "Overte ä Ω 東京 "+run : (_current.editor=="chat" ? "reply-" : "retry-")+run;
            delivered=overte::ui::replaceFocusedField(field,surface,text);
        }
        _busy=false;return delivered;
    }
private:
    struct Field { QString editor;QPointer<QQuickItem> field;QPointer<QQuickWindow> window;QPointer<QQmlContext> context;QPointer<QObject> page;QString text;QRectF frame; };
    struct Seen { QString editor;QPointer<QQuickItem> field;QPointer<QQuickWindow> window;QPointer<QQmlContext> context;QPointer<QObject> page;QString token,fieldToken;qint64 created,retired; };
    struct Issued { QString run,token;qint64 epoch{0}; };
    static bool gui() { return qApp && QThread::currentThread()==qApp->thread() && QCoreApplication::arguments().contains("--testScript"); }
    static bool hex(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool ownedText(const QString& editor,const QString& run,const QString& text) {
        return text.isEmpty() || text==(editor=="create" ? "Overte ä Ω 東京 "+run : (editor=="chat" ? "reply-" : "retry-")+run);
    }
    qint64 now() { const auto epoch=QDateTime::currentMSecsSinceEpoch();if(epoch<=0 || epoch<_epoch) { _valid=false;return 0; }_epoch=epoch;return epoch; }
    QString _instance{nonce()},_currentToken;quint64 _sequence{0};qint64 _epoch{0};bool _valid{true},_busy{false};
    QVector<Seen> _seen;QMap<quint64,Issued> _issued;QSet<QString> _commands;Field _current;
};
} // namespace overte::e2e
#endif
