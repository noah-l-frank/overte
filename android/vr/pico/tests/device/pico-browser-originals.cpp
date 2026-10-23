// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual selected native backend and Pico pointer/provider bodies. Android DOM,
// Tablet singleton and Java scheduling are explicit host boundaries, not devices.
#include "NativeWebViewItem.h"
#include "tests/device/native/PicoBrowserFeatureBridge.h"
#include "tests/device/native/PicoWorldWebRay.h"
#include "tests/device/native/PicoWorldWebText.h"
#include "tests/device/native/NormalControlUi.h"
#include <PointerEvent.h>
#include <QTouchDevice>
#include <QGuiApplication>
#include <QQuickWindow>
#include <QEventLoop>
#include <QTimer>
#include <QThread>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <jni.h>
#include <cassert>
#include <cstdio>
#include <memory>
#undef assert
#define assert(condition) do { if (!(condition)) { fprintf(stderr,"Host assertion at line %d: %s\n",__LINE__,#condition);fflush(stderr);abort();} } while(false)
using namespace overte::e2e;
#include "actual-pointer-route.inc"
struct TabletBoundary:QObject {
    QQuickItem* root{};OffscreenQmlSurface* surface{};
    QQuickItem* getTabletRoot(){return root;}OffscreenQmlSurface* getTabletSurface(){return surface;}
};
struct TabletScriptingInterface {
    std::shared_ptr<TabletBoundary> tablet=std::make_shared<TabletBoundary>();
    auto getTablet(const QString&){return tablet;}
};
TabletScriptingInterface tabletBoundary;bool admittedBridge=true;
struct DependencyManager {
    template<class T>static bool isSet(){return true;}
    template<class T>static T* get(){return &tabletBoundary;}
};
const QString SYSTEM_TABLET="com.highfidelity.interface.tablet.system",BRIDGE_DIRECTORY="host-private-boundary";
bool bridgeEnabled(){return admittedBridge;}bool previewDirectory(const QString&){return true;}
#include "actual-browser-provider.inc"
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeInitialize(JNIEnv*,jclass);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeForeground(JNIEnv*,jclass,jboolean);
extern "C" void Java_org_overte_web_EmbeddedWebView_nativeInputFocus(JNIEnv*,jclass,jlong,jlong,jlong,jboolean);
struct BrowserItem:NativeWebViewItem {using NativeWebViewItem::NativeWebViewItem;using NativeWebViewItem::inputMethodQuery;};
QString nonce(){return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
void events(int duration=1){QEventLoop loop;QTimer::singleShot(duration,&loop,&QEventLoop::quit);loop.exec();}
QByteArray quoted(const QVariantMap& map){auto bytes=QJsonDocument(QJsonArray{QString::fromUtf8(QJsonDocument::fromVariant(map).toJson(QJsonDocument::Compact))}).toJson(QJsonDocument::Compact);return bytes.mid(1,bytes.size()-2);}
int main(int argc,char**argv){
    QGuiApplication app(argc,argv);assert(argc>=2);
    const std::string path=std::string("-Djava.class.path=")+argv[1];JavaVMOption option{const_cast<char*>(path.c_str()),nullptr};
    JavaVMInitArgs config{JNI_VERSION_1_8,1,&option,JNI_FALSE};JavaVM* machine=nullptr;JNIEnv* env=nullptr;
    assert(JNI_CreateJavaVM(&machine,reinterpret_cast<void**>(&env),&config)==JNI_OK);
    auto java=env->FindClass("org/overte/web/EmbeddedWebView");assert(java);
    Java_org_overte_web_EmbeddedWebView_nativeInitialize(env,java);Java_org_overte_web_EmbeddedWebView_nativeForeground(env,java,true);
    const auto count=[&](const char*name){auto field=env->GetStaticFieldID(java,name,"I");assert(field);return env->GetStaticIntField(java,field);};
    const auto field=[&](const char*name){auto id=env->GetStaticFieldID(java,name,"J");assert(id);return env->GetStaticLongField(java,id);};
    {
        QQuickWindow window;window.resize(640,480);window.show();window.requestActivate();events();
        QQuickItem root(window.contentItem());root.setSize(QSizeF(640,480));OffscreenQmlSurface surface(&root,&window);
        tabletBoundary.tablet->root=&root;tabletBoundary.tablet->surface=&surface;tabletBoundary.tablet->setProperty("tabletShown",true);
        installBrowserInputProvider();const auto input=app.property(picoBrowserInputProperty()).value<PicoBrowserInputProvider>();assert(input.pointer && input.text && input.scroll);
        const QString run(32,'a'),owner(32,'b'),fixture="http://127.0.0.1/feature-fixture/v1/runs/"+run+"/",url=fixture+"tickets/"+QString(32,'c')+"/index.html";
        auto cmd=[&](const QString&op){return QVariantMap{{"schemaVersion",1},{"commandId",nonce()},{"action","pico-tablet-web"},{"runId",run},{"fixtureUrl",fixture},{"operation",op},{"ownerToken",owner}};};
        auto reserve=cmd("reserve");assert(picoBrowserCommand(reserve));assert(NativeWebViewItem::featurePicoBrowser(reserve).value("status")=="ready");
        auto item=std::make_unique<BrowserItem>(&root);item->setSize(QSizeF(640,480));item->setSurface(NativeWebViewItem::Tablet);
        item->setSourceIdentity("tablet:actual-host-boundary");item->setUrl(url);item->componentComplete();events();
        const auto handle=field("handle"),birth=field("birth");const auto grant=item->generation();assert(handle>0 && birth>0 && grant>0);
        item->acceptCreated(true,birth);events();item->acceptPage(grant,1,QUrl(url));events();
        const unsigned char pixels[4*4*3]={};item->acceptFrame(grant,1,pixels,sizeof(pixels),4,3);events();
        item->acceptFeatureWebFinished(grant,1,QUrl(url));events();
        auto observe=cmd("observe");auto pending=NativeWebViewItem::featurePicoBrowser(observe);assert(pending.value("status")=="pending");assert(count("ownedReads")==1);
        const auto dom=[&](const QVariantMap&command,int sequence){return QVariantMap{{"webDOMVersion",1},{"requestId",command.value("commandId")},{"instance",QString(32,'d')},{"sequence",sequence},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"document",QVariantMap{{"runId",run},{"href",url},{"responseId",QString(32,'e')},{"readyState","complete"},{"title","Actual fixture title"}}},
            {"editor",QVariantMap{{"text","old"},{"focused",false}}},{"attempts",QVariantList{}},{"echoes",QVariantList{}}};};
        item->acceptFeatureWebDOM(grant,1,QUrl(url),observe.value("commandId").toString(),quoted(dom(observe,1)));events();
        auto source=NativeWebViewItem::featurePicoBrowser(observe);assert(source.value("status")=="ready");
        auto original=source.value("source").toMap();assert(original.value("documents").toList().size()==1 && original.value("domHistory").toMap().size()==1);
        assert(original.value("current").toMap().value("source").toMap().value("dom").toMap().value("document").toMap().value("title")=="Actual fixture title");
        const auto action=[&](const QString&control,const QString&text){auto value=cmd("input");value.insert("handle",QString::number(handle));value.insert("creation",qulonglong(birth));value.insert("grant",qulonglong(grant));value.insert("page",1);value.insert("control",control);value.insert("text",text);return value;};
        const auto geometry=[&](const QVariantMap&command,int sequence,bool focused){return QVariantMap{{"webGeometryVersion",1},{"requestId",command.value("commandId")},{"instance",QString(32,'d')},{"sequence",sequence},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"document",QVariantMap{{"runId",run},{"href",url},{"responseId",QString(32,'e')},{"readyState","complete"}}},{"control",command.value("control")},
            {"editor",QVariantMap{{"focused",focused},{"text","old"},{"cursor",1},{"anchor",1}}},
            {"viewport",QVariantMap{{"width",640},{"height",480},{"scale",1},{"offsetLeft",0},{"offsetTop",0}}},
            {"rect",QVariantMap{{"x",80},{"y",60},{"width",160},{"height",80}}},{"center",QVariantMap{{"x",160},{"y",100}}},
            {"hit",true},{"enabled",true},{"connected",true}};};
        auto probe=action("text","input");const auto sample=geometry(probe,2,false);
        assert(picoBrowserPoint(sample,probe.value("commandId").toString(),run,url,"text",sample.value("capturedEpochMs").toLongLong(),QSizeF(640,480)));
        for (int mutation=0;mutation<11;++mutation) {
            auto bad=sample;
            if(mutation==0)bad["hit"]=false;if(mutation==1)bad["enabled"]=false;if(mutation==2)bad["connected"]=false;
            if(mutation==3)bad["capturedEpochMs"]=bad.value("capturedEpochMs").toLongLong()-1501;
            if(mutation==4)bad["requestId"]=nonce();if(mutation==5)bad["extra"]=1;
            if(mutation==6){auto v=bad.value("viewport").toMap();v["scale"]=2;bad["viewport"]=v;}
            if(mutation==7){auto v=bad.value("center").toMap();v["x"]=640;bad["center"]=v;}
            if(mutation==8){auto v=bad.value("document").toMap();v["runId"]=nonce();bad["document"]=v;}
            if(mutation==9){auto v=bad.value("editor").toMap();v["cursor"]=1.5;bad["editor"]=v;}
            if(mutation==10)bad["sequence"]=true;
            assert(!picoBrowserPoint(bad,probe.value("commandId").toString(),run,url,"text",sample.value("capturedEpochMs").toLongLong(),QSizeF(640,480)));
        }
        auto type=action("text",QString::fromUtf8("Grüße 🌍"));assert(picoBrowserCommand(type));
        pending=NativeWebViewItem::featurePicoBrowser(type);assert(pending.value("status")=="pending");assert(count("geometryReads")==1);
        assert(NativeWebViewItem::featurePicoBrowser(type)==pending && count("geometryReads")==1);
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,type.value("commandId").toString(),quoted(geometry(type,2,false)));events();
        assert(count("pointers")==2 && count("focusReads")==1 && count("edits")==0);
        Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,java,handle,grant,1,true);events();
        assert(item->acceptMessage(grant,1,QUrl(url),QUrl("http://127.0.0.1"),true,"editor",R"({"active":true,"text":"old","cursor":1,"anchor":1,"absoluteCursor":1,"kind":"text"})"));events();
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,type.value("commandId").toString(),quoted(geometry(type,3,true)),true);events(50);
        auto receipt=NativeWebViewItem::featurePicoBrowser(type);assert(receipt.value("status")=="ready");assert(count("edits")==1);
        auto editId=env->GetStaticFieldID(java,"lastEdit","Ljava/lang/String;");auto text=static_cast<jstring>(env->GetStaticObjectField(java,editId));
        const auto* bytes=env->GetStringChars(text,nullptr);auto edit=QJsonDocument::fromJson(QString::fromUtf16(bytes,env->GetStringLength(text)).toUtf8()).object();env->ReleaseStringChars(text,bytes);
        assert(edit.value("action")=="ime" && edit.value("commit")==QString::fromUtf8("Grüße 🌍") && edit.value("replaceStart")==-1 && edit.value("replaceLength")==3);
        // The real native model remains old at this Android editor seam. The
        // delivery receipt must not synthesize its desired DOM/model effect.
        assert(item->inputMethodQuery(Qt::ImSurroundingText)=="old");assert(NativeWebViewItem::featurePicoBrowser(type)==receipt && count("edits")==1);
        auto collision=type;collision["text"]="other";assert(NativeWebViewItem::featurePicoBrowser(collision).isEmpty());
        auto second=action("text","new");assert(NativeWebViewItem::featurePicoBrowser(second).value("status")=="pending");
        QQuickItem overlay(&root);overlay.setSize(QSizeF(640,480));overlay.setZ(100);
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,second.value("commandId").toString(),quoted(geometry(second,4,false)));events();
        assert(NativeWebViewItem::featurePicoBrowser(second).value("status")=="unavailable" && count("pointers")==2 && count("edits")==1);
        overlay.setVisible(false);assert(NativeWebViewItem::featurePicoBrowser(type)==receipt && count("edits")==1);
        auto stale=action("text","late");NativeWebViewItem::featurePicoBrowser(stale);auto old=geometry(stale,5,false);old["capturedEpochMs"]=QDateTime::currentMSecsSinceEpoch()-1501;
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,stale.value("commandId").toString(),quoted(old));events();
        assert(NativeWebViewItem::featurePicoBrowser(stale).value("status")=="unavailable" && count("pointers")==2);
        // A passive offscreen measurement performs no pointer, wheel or IME.
        auto measure=action("text","");measure.remove("text");measure["operation"]="measure";
        assert(picoBrowserCommand(measure));assert(NativeWebViewItem::featurePicoBrowser(measure).value("status")=="pending");
        auto offscreen=geometry(measure,6,false);offscreen["rect"]=QVariantMap{{"x",80},{"y",600},{"width",160},{"height",80}};
        offscreen["center"]=QVariantMap{{"x",160},{"y",640}};offscreen["hit"]=false;
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,measure.value("commandId").toString(),quoted(offscreen));events();
        const auto measured=NativeWebViewItem::featurePicoBrowser(measure);
        assert(measured.value("status")=="ready" && measured.value("source").toMap().value("geometryRaw")==QString::fromUtf8(quoted(offscreen)));
        assert(count("pointers")==2 && count("edits")==1 && count("wheels")==0);
        assert(NativeWebViewItem::featurePicoBrowser(measure)==measured);
        auto wheel=action("scroll-down","");assert(picoBrowserCommand(wheel));NativeWebViewItem::featurePicoBrowser(wheel);
        auto wheelGeometry=geometry(wheel,7,false);wheelGeometry["editor"]=QVariantMap{{"focused",false},{"text",QVariant()},{"cursor",QVariant()},{"anchor",QVariant()}};
        wheelGeometry["rect"]=QVariantMap{{"x",0},{"y",0},{"width",640},{"height",480}};wheelGeometry["center"]=QVariantMap{{"x",320},{"y",240}};
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,wheel.value("commandId").toString(),quoted(wheelGeometry));events();
        const auto wheelReceipt=NativeWebViewItem::featurePicoBrowser(wheel);
        assert(wheelReceipt.value("status")=="ready" && count("wheels")==1 && count("pointers")==2 && count("edits")==1);
        assert(NativeWebViewItem::featurePicoBrowser(wheel)==wheelReceipt && count("wheels")==1);
        // An overlay cannot receive a replayed wheel under a replacement nonce.
        auto blockedWheel=action("scroll-up","");NativeWebViewItem::featurePicoBrowser(blockedWheel);overlay.setVisible(true);
        auto blockedGeometry=wheelGeometry;blockedGeometry["requestId"]=blockedWheel.value("commandId");blockedGeometry["sequence"]=8;blockedGeometry["control"]="scroll-up";
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,blockedWheel.value("commandId").toString(),quoted(blockedGeometry));events();
        assert(NativeWebViewItem::featurePicoBrowser(blockedWheel).value("status")=="unavailable" && count("wheels")==1);
        overlay.setVisible(false);
        auto finalObserve=cmd("observe");NativeWebViewItem::featurePicoBrowser(finalObserve);
        item->acceptFeatureWebDOM(grant,1,QUrl(url),finalObserve.value("commandId").toString(),quoted(dom(finalObserve,2)));events();
        auto finalPacket=NativeWebViewItem::featurePicoBrowser(finalObserve);assert(finalPacket.value("status")=="ready");
        const auto history=finalPacket.value("source").toMap().value("inputs").toList();assert(history.size()==5);
        assert(!history[0].toMap().value("geometryRaw").isNull() && !history[0].toMap().value("focusRaw").isNull()
            && history[0].toMap().value("nativeBeforeIME").toMap().value("text")=="old");
        QFile originalFile(QString::fromLocal8Bit(argv[1])+"/native-originals.json");assert(originalFile.open(QFile::WriteOnly));
        originalFile.write(QJsonDocument::fromVariant(QVariantMap{{"request",finalObserve},{"packet",finalPacket},{"measureRequest",measure},{"measurePacket",measured}}).toJson(QJsonDocument::Compact));originalFile.close();
        auto retire=cmd("retire");assert(NativeWebViewItem::featurePicoBrowser(retire).isEmpty());
        item.reset();events();QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);events();
        assert(NativeWebViewItem::featurePicoBrowser(retire).value("status")=="ready");
        assert(NativeWebViewItem::featurePicoBrowser(type).isEmpty() && count("edits")==1);
        // A stale retained native item outside the actual tablet cannot get input.
        NativeWebViewItem foreign;foreign.setSize(QSizeF(640,480));assert(!input.pointer(&foreign,QPointF(160,100),QDateTime::currentMSecsSinceEpoch()));
        tabletBoundary.tablet->root=nullptr;tabletBoundary.tablet->surface=nullptr;
    }
    {
        // Entity/HMD resolution is a declared boundary here. The unchanged
        // original world provider is separately compiled against actual Qt
        // scene transforms in world-web-ray-native.cpp. This path joins its
        // original IME provider to the complete selected native backend/JNI.
        QQuickWindow window;window.resize(640,480);window.show();window.requestActivate();events();
        QQuickItem root(window.contentItem());root.setSize(QSizeF(640,480));
        const QString run(32,'7'),owner(32,'8'),fixture="http://127.0.0.1/feature-fixture/v1/runs/"+run+"/",url=fixture+"tickets/"+QString(32,'9')+"/index.html";
        auto cmd=[&](const QString&op){return QVariantMap{{"schemaVersion",1},{"commandId",nonce()},{"action","pico-world-web"},{"runId",run},{"fixtureUrl",fixture},{"operation",op},{"ownerToken",owner}};};
        assert(NativeWebViewItem::featurePicoBrowser(cmd("reserve")).value("status")=="ready");
        auto item=std::make_unique<BrowserItem>(&root);item->setSize(QSizeF(640,480));item->setSurface(NativeWebViewItem::WorldEntity);
        item->setSourceIdentity("web-entity:12345678-1234-1234-1234-123456789abc");item->setUrl(url);item->componentComplete();events();
        const auto handle=field("handle"),birth=field("birth");const auto grant=item->generation();
        item->acceptCreated(true,birth);events();item->acceptPage(grant,1,QUrl(url));events();
        const unsigned char pixels[4*4*3]={};item->acceptFrame(grant,1,pixels,sizeof(pixels),4,3);events();
        item->acceptFeatureWebFinished(grant,1,QUrl(url));events();
        PicoWorldWebRayProvider entityBoundary=[](QQuickItem* item,const QPointF& point){
            return item && item->property("sourceIdentity").toString().startsWith("web-entity:")
                && NormalControlUi::ownsPoint(item,item->window(),item->mapToScene(point)) ? QVariantMap{{"explicitEntityBoundary",true}} : QVariantMap();
        };
        app.setProperty(picoWorldWebRayProperty(),QVariant::fromValue(entityBoundary));installWorldWebTextProvider();
        const auto action=[&](const QString&text){auto value=cmd("commit-text");value.insert("handle",QString::number(handle));value.insert("creation",qulonglong(birth));
            value.insert("grant",qulonglong(grant));value.insert("page",1);value.insert("control","text");value.insert("text",text);return value;};
        const auto geometry=[&](const QVariantMap& command,bool focused){return QVariantMap{{"webGeometryVersion",1},{"requestId",command.value("commandId")},{"instance",QString(32,'d')},{"sequence",1},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"document",QVariantMap{{"runId",run},{"href",url},{"responseId",QString(32,'e')},{"readyState","complete"}}},{"control","text"},
            {"editor",QVariantMap{{"focused",focused},{"text","old"},{"cursor",1},{"anchor",1}}},
            {"viewport",QVariantMap{{"width",640},{"height",480},{"scale",1},{"offsetLeft",0},{"offsetTop",0}}},
            {"rect",QVariantMap{{"x",80},{"y",60},{"width",160},{"height",80}}},{"center",QVariantMap{{"x",160},{"y",100}}},{"hit",true},{"enabled",true},{"connected",true}};};
        const int beforePointers=count("pointers"),beforeEdits=count("edits");
        auto unfocused=action("unfocused");assert(picoBrowserCommand(unfocused));NativeWebViewItem::featurePicoBrowser(unfocused);
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,unfocused.value("commandId").toString(),quoted(geometry(unfocused,false)),true);events();
        assert(NativeWebViewItem::featurePicoBrowser(unfocused).value("status")=="unavailable" && count("edits")==beforeEdits);
        // Explicit substitute for the independently delivered normal ray and
        // Android editor callbacks; the provider itself never focuses an item.
        item->forceActiveFocus(Qt::MouseFocusReason);Java_org_overte_web_EmbeddedWebView_nativeInputFocus(env,java,handle,birth,grant,true);events();
        assert(item->acceptMessage(grant,1,QUrl(url),QUrl("http://127.0.0.1"),true,"editor",R"({"active":true,"text":"old","cursor":1,"anchor":1,"absoluteCursor":1,"kind":"text"})"));events();
        auto mismatched=action("wrong-viewport");NativeWebViewItem::featurePicoBrowser(mismatched);
        auto wrongViewport=geometry(mismatched,true);auto viewport=wrongViewport.value("viewport").toMap();viewport["height"]=300;wrongViewport["viewport"]=viewport;
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,mismatched.value("commandId").toString(),quoted(wrongViewport),true);events();
        assert(NativeWebViewItem::featurePicoBrowser(mismatched).value("status")=="unavailable" && count("edits")==beforeEdits && count("pointers")==beforePointers);
        auto commit=action(QString::fromUtf8("Grüße 🌍"));NativeWebViewItem::featurePicoBrowser(commit);
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,commit.value("commandId").toString(),quoted(geometry(commit,true)),true);events();
        const auto packet=NativeWebViewItem::featurePicoBrowser(commit);assert(packet.value("status")=="ready" && packet.value("picoBrowserVersion")==4);
        assert(packet.value("source").toMap().value("delivered")==true && count("edits")==beforeEdits+1 && count("pointers")==beforePointers);
        assert(item->inputMethodQuery(Qt::ImSurroundingText)=="old");assert(NativeWebViewItem::featurePicoBrowser(commit)==packet && count("edits")==beforeEdits+1);
        QQuickItem overlay(&root);overlay.setSize(QSizeF(640,480));overlay.setZ(100);
        auto blocked=action("blocked");NativeWebViewItem::featurePicoBrowser(blocked);
        NativeWebViewItem::acceptFeaturePicoBrowserGeometry(handle,grant,1,url,blocked.value("commandId").toString(),quoted(geometry(blocked,true)),true);events();
        const auto refused=NativeWebViewItem::featurePicoBrowser(blocked);assert(refused.value("status")=="ready" && refused.value("source").toMap().value("delivered")==false);
        assert(count("edits")==beforeEdits+1 && count("pointers")==beforePointers);
        QFile file(QString::fromLocal8Bit(argv[1])+"/world-text-native-originals.json");assert(file.open(QFile::WriteOnly));
        file.write(QJsonDocument::fromVariant(QVariantMap{{"request",commit},{"packet",packet},{"blockedRequest",blocked},{"blockedPacket",refused},
            {"actualNativeTextAfter",item->inputMethodQuery(Qt::ImSurroundingText)},{"worldPointerAttempts",count("pointers")-beforePointers}}).toJson(QJsonDocument::Compact));file.close();
        auto retire=cmd("retire");assert(NativeWebViewItem::featurePicoBrowser(retire).isEmpty());item.reset();events();QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);events();
        assert(NativeWebViewItem::featurePicoBrowser(retire).value("status")=="ready");assert(NativeWebViewItem::featurePicoBrowser(commit).isEmpty());
    }
    machine->DestroyJavaVM();puts("PASS actual selected native browser, retained originals, original Pico surface pointer/provider and normal Qt IME; Android DOM/Java scheduling/Tablet boundary substituted");
}
