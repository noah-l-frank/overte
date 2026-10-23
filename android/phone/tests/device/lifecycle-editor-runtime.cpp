// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual original QML, Qt input and weak context retirement. Backend services
// and measured OS-IME metrics are explicit host seams, not Android acceptance.
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QTest>
#include <QJsonDocument>
#include <cstdio>
#include "tests/device/native/PhoneLifecycleEditor.h"
#include "tests/device/native/PendingFieldCommitOwner.h"
#include "tests/device/native/WebDOMObservationBridge.h"
static QString stage;
static QString activeEditor;
QUrl PathUtils::defaultScriptsLocation(const QString&) { return QUrl::fromLocalFile(stage+"/scripts/"); }
QUrl PathUtils::qmlUrl(const QString& relative) { return QUrl::fromLocalFile(stage+"/qml/"+relative); }
class Services:public QObject {
    Q_OBJECT
    Q_PROPERTY(bool active READ active CONSTANT)
    Q_PROPERTY(QVariant scriptsModelFilter READ model CONSTANT)
public:
    bool active() const { return false; }QVariant model() const { return {}; }
    Q_INVOKABLE QVariantList getRunning() { return {}; }
    Q_INVOKABLE bool isOptionChecked(const QString&) { return false; }
signals:void scriptCountChanged();void scriptLoadError(const QString&,const QString&);
};
// ORIGINAL_TEST_BINDING
static void needAt(bool value,int line) {
    if(!value)throw std::runtime_error("Original lifecycle editor source contract for "+activeEditor.toStdString()+" at line "+std::to_string(line));
}
#define need(value) needAt((value),__LINE__)
static QVariantMap originalPendingProviderDispatch(const QVariantMap& command) {
    // ORIGINAL_PENDING_PROVIDER_DISPATCH
}
int main(int argc,char**argv) {
    QGuiApplication app(argc,argv);stage=QString::fromLocal8Bit(argv[1]);const QString mode=argv[2],run(32,'a');
    if(mode=="provider-types") {
        using overte::e2e::PendingCommitProvider;
        using overte::e2e::WebDOMProvider;
        need(qMetaTypeId<PendingCommitProvider>()!=qMetaTypeId<WebDOMProvider>());
        const QVariantMap command{{"actual-host-command",true}};
        PendingCommitProvider empty;need(!empty && empty(command).isEmpty());
        int pendingCalls=0,foreignCalls=0;
        WebDOMProvider foreign=[&](const QVariantMap& value){++foreignCalls;return value;};
        qApp->setProperty(overte::e2e::pendingCommitProviderProperty(),QVariant::fromValue(foreign));
        need(originalPendingProviderDispatch(command).isEmpty() && foreignCalls==0);
        PendingCommitProvider provider{[&](const QVariantMap& value){++pendingCalls;return value;}};
        const auto copied=provider;
        qApp->setProperty(overte::e2e::pendingCommitProviderProperty(),QVariant::fromValue(copied));
        need(originalPendingProviderDispatch(command)==command && pendingCalls==1 && foreignCalls==0);
        qApp->setProperty(overte::e2e::pendingCommitProviderProperty(),QVariant::fromValue(empty));
        need(originalPendingProviderDispatch(command).isEmpty() && pendingCalls==1 && foreignCalls==0);
        qApp->setProperty(overte::e2e::pendingCommitProviderProperty(),QVariant());
        need(originalPendingProviderDispatch(command).isEmpty() && pendingCalls==1 && foreignCalls==0);
        return 0;
    }
    QQmlEngine engine;engine.addImportPath(stage);Services services;
    for(const auto& name:QStringList{"ScriptDiscoveryService","MenuInterface","HMD"})engine.rootContext()->setContextProperty(name,&services);
    QQuickWindow window;window.resize(640,1100);QQuickItem root(window.contentItem());root.setSize(QSizeF(640,1100));window.show();window.requestActivate();QTest::qWait(50);
    auto& dependencyUi=LifecycleDependencies::service<OffscreenUi>();dependencyUi=QSharedPointer<OffscreenUi>::create();dependencyUi->root=&root;dependencyUi->window=&window;
    LifecycleDependencies::service<TabletScriptingInterface>()=QSharedPointer<TabletScriptingInterface>::create();
    TestScriptingInterface test;
    auto observe=[&] {return test.phoneLifecycleEditor({{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
        {"action","phone-lifecycle-editor-observe"},{"runId",run}});};
    auto body=[&] { auto value=observe();need(!value.isEmpty());return value.value("source").toMap(); };
    auto current=[&] {return body().value("current").toMap();};
    QVariantMap lastInputCommand;
    auto input=[&](const QString& operation,const QVariantMap& source) {
        const auto field=source.value("current").toMap();lastInputCommand={{"schemaVersion",1},
            {"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"runId",run},{"action","phone-lifecycle-editor-input"},
            {"operation",operation},{"fieldToken",field.value("fieldToken")},{"observationSequence",source.value("sequence")}};
        return test.phoneLifecycleEditor(lastInputCommand);
    };
    auto create=[&](const QString& editor) {
        const auto url=overte::e2e::PhoneLifecycleEditor::sources().value(editor);QQmlComponent component(&engine,url);
        auto page=qobject_cast<QQuickItem*>(component.create());if(!page)qWarning()<<component.errors();need(page);
        page->setParentItem(&root);page->setSize(QSizeF(640,1100));QTest::qWait(40);return page;
    };
    need(current().value("status")=="none");QStringList tokens;
    if(mode=="foreign-source") {
        const auto path=stage+"/foreign/NativeCreate.qml";need(QDir().mkpath(stage+"/foreign"));
        need(QFile::copy(overte::e2e::PhoneLifecycleEditor::sources().value("create").toLocalFile(),path));
        QQmlComponent component(&engine,QUrl::fromLocalFile(path));QScopedPointer<QObject> value(component.create());auto page=qobject_cast<QQuickItem*>(value.data());need(page);
        page->setParentItem(&root);page->setSize(QSizeF(640,1100));QTest::qWait(30);need(observe().isEmpty());return 0;
    }
    for(const auto& editor:QStringList{"create","chat","scripts"}) {
        activeEditor=editor;
        auto page=create(editor);auto source=body();auto field=source.value("current").toMap();need(field.value("editor")==editor && field.value("text")=="");
        tokens.append(field.value("token").toString());
        if(mode=="foreign-token") {auto wrong=source;auto fields=field;fields["fieldToken"]=QString(32,'f');wrong["current"]=fields;need(input("focus",wrong).value("performed")==false);
            lastInputCommand["fieldToken"]=field.value("fieldToken");need(test.phoneLifecycleEditor(lastInputCommand).value("performed")==false);delete page;return 0;}
        if(mode=="ambiguous") {auto duplicate=create(editor);need(observe().isEmpty());delete duplicate;delete page;return 0;}
        need(input("focus",source).value("performed")==true);QTest::qWait(20);need(current().value("focused")==true);
        if(mode=="private-text") { auto fieldItem=page->findChild<QQuickItem*>(editor=="create" ? "NativeCreateText" : "chatMessageInput");need(fieldItem);fieldItem->setProperty("text","private external draft");need(observe().isEmpty());delete page;return 0; }
        source=body();need(input("type",source).value("performed")==true);QTest::qWait(20);
        const auto expected=editor=="create" ? "Overte ä Ω 東京 "+run : (editor=="chat" ? "reply-" : "retry-")+run;
        need(current().value("text")==expected);
        if(editor=="chat") {
            page->setVisible(false);QTest::qWait(10);need(current().value("status")=="none");page->setVisible(true);QTest::qWait(10);
            need(current().value("text")==expected && current().value("token")==tokens.last());
        }
        if(editor=="scripts") {
            overte::e2e::PendingFieldCommitOwner owner([&] {return overte::e2e::PendingFieldCommitOwner::Roots{true,{&root}};},
                [&](QQuickItem* item,QQuickWindow* surface,const QPointF& point){return overte::e2e::NormalControlUi::pointerEvent(item,surface,point);});
            auto request=[&](const QString& operation,const QVariantMap& previous) {
                QVariantMap command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
                    {"action","feature-pending-commit-owner"},{"operation",operation},{"runId",run},{"eventId",""}};
                if(operation!="observe") {command["ownerInstance"]=previous.value("instance");command["intentSequence"]=previous.value("lastIntentSequence").toULongLong()+1;
                    command["fieldToken"]=previous.value("current").toMap().value("token");command["observationSequence"]=previous.value("sequence");}
                if(operation=="attempt")command["eventId"]=previous.value("commit").toMap().value("observation").toMap().value("eventId");
                return owner.request(command);
            };
            auto prepared=request("hold",request("observe",{}));need(prepared.value("performed")==true);
            need(prepared.value("commit").toMap().value("fieldToken")==current().value("fieldToken"));
            const auto old=current();delete page;page=nullptr;need(current().value("status")=="none");
            auto replacement=create("scripts");const auto newer=current();need(newer.value("token")!=old.value("token") && newer.value("text")=="" && newer.value("focused")==false);
            auto pending=request("observe",{});need(pending.value("current").toMap().value("token")==newer.value("fieldToken"));
            const auto attempted=request("attempt",pending);const auto event=attempted.value("commit").toMap().value("observation").toMap().value("events").toList().last().toMap();
            need(event.value("kind")=="rejected" && event.value("reason")=="context-retired");need(current().value("text")=="" && current().value("focused")==false);
            delete replacement;
        }
        delete page;need(current().value("status")=="none");
    }
    need(QSet<QString>(tokens.begin(),tokens.end()).size()==3);const auto original=observe();std::puts(QJsonDocument::fromVariant(original).toJson(QJsonDocument::Compact).constData());return 0;
}
#include "lifecycle-editor-runtime.moc"
