// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Fixed Phone5527 Assets QML/filesystem journey, actual Pico observer/input and
// original Offscreen pointer bodies; network/entity/keyboard endpoints are host seams.

#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QQuickWindow>
#include <QQuickItem>
#include <QStandardItemModel>
#include <QLoggingCategory>
#include <QtTest/QTest>
#include <iostream>
#include <PointerEvent.h>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <map>
#include "actual-pointer-route.inc"
#include "tests/device/native/NormalControlUi.h"
#include "avatar-navigation-observation-seams.h"
namespace overte::e2e {
inline bool placesField(const QString&){return false;}
inline bool placesText(const QString&){return false;}
inline bool placesScrollPoint(QQuickItem*,const QString&,QPointF&){return false;}
}
#define ANDROID_APP_PICO_INTERFACE
#include "actual-assets-navigation.inc"
#undef ANDROID_APP_PICO_INTERFACE
#include "libraries/ui/src/FileDialogHelper.h"
Q_LOGGING_CATEGORY(uiLogging,"ui")
using namespace overte::e2e;
static QQuickItem* find(QQuickItem* node,const QString& name) {
 if(node->objectName()==name)return node;for(auto child:node->childItems())if(auto found=find(child,name))return found;return nullptr;
}
int main(int argc,char**argv){
 HostApplication app(argc,argv);PathUtils::qml=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[5])+"/interface/resources/qml/");
 if(!app.arguments().contains("--testScript")){AssetsUi gated;if(!gated.observe(nullptr,nullptr).isEmpty())return 44;return 0;}
 QQmlEngine engine;engine.addImportPath(argv[1]);FileDialogHelper files;
 engine.rootContext()->setContextProperty("fileDialogHelper",&files);
 QStandardItemModel model;auto folder=new QStandardItem("e2e-root");folder->setData("/e2e-root/",256);folder->setData(true,257);
 auto main=new QStandardItem("main.gltf");main->setData("/e2e-root/main.gltf",256);main->setData(false,257);main->setData("atp:/e2e-root/main.gltf",259);main->setData("--",261);
 folder->appendRow(main);model.appendRow(folder);engine.rootContext()->setContextProperty("assetModel",&model);
 QQmlComponent helper(&engine);helper.setData(R"(import QtQml 2.7
QtObject {
 property var proxyModel: assetModel
 property var mappingModel: QtObject { property bool autoRefreshEnabled: false; signal errorGettingMappings(string message); function refresh() {} }
 property bool allowed: true
 property int deletes: 0
 property int uploads: 0
 property int imports: 0
 property var bundleOriginal: null
 signal canWriteAssetsChanged(bool allowed)
 signal canRezChanged()
 signal canRezTmpChanged()
 signal uploadRequest(var url)
 function canWriteAssets() { return allowed }
 function canRez() { return true }
 function canRezTmp() { return true }
 function isOptionChecked(name) { return false }
 function getForward(value) { return ({x:0,y:0,z:-1}) }
 function sum(a,b) { return ({x:0,y:0,z:2}) }
 function multiply(a,b) { return ({x:0,y:0,z:0}) }
 function fromPolar(a,b) { return ({x:0,y:0,z:0}) }
 property var position: ({x:0,y:0,z:4})
 property var orientation: ({x:0,y:0,z:0,w:1})
 function deleteMappings(paths,done) { ++deletes; done(null) }
 function renameMapping(a,b,done) { done(null) }
 function isKnownFolder(path) { return false }
 function isKnownMapping(path) { return false }
 function addModelEntity() { ++imports; return "12345678-1234-4234-8234-123456789abc" }
 function uploadBundle(paths,relative,destination,primary,progress,done) {
   var manifest=fileDialogHelper.documentBundle(paths.map(function(path){return fileDialogHelper.pathToUrl(path)}));
   bundleOriginal=({files:paths,relative:relative,destination:destination,primary:primary,actual:manifest});
   ++uploads;Qt.callLater(function(){done(null,JSON.stringify(relative),destination+primary)});return "synthetic-upload-request";
 }
})",QUrl("file:///explicit-assets-endpoints.qml"));
 QScopedPointer<QObject> service(helper.create());if(!service){qWarning()<<helper.errors();return 1;}
 for(const auto& name:QStringList{"Assets","Entities","MenuInterface","MyAvatar","Vec3","Quat","ApplicationInterface"})engine.rootContext()->setContextProperty(name,service.data());
 QQmlComponent component(&engine,QUrl::fromLocalFile(argv[2]));QScopedPointer<QObject> object(component.create());
 if(!object){qWarning()<<component.errors();return 2;}auto root=qobject_cast<QQuickItem*>(object.data());if(!root)return 3;
 QQuickWindow window;window.resize(900,1200);root->setParentItem(window.contentItem());root->setSize(QSizeF(900,1200));window.show();window.requestActivate();QTest::qWait(120);
 overte::pico::e2e::NavigationUi ui;OffscreenQmlSurface surface(root,&window);int pointers=0;
 QJsonArray observations;auto capture=[&]{auto value=ui.observe(root,&window,true);observations.append(value);return value;};
 auto row=[&](const QString& id){for(const auto& item:capture().value("controls").toArray()){auto value=item.toObject();if(value.value("id")==id)return value;}return QJsonObject();};
 auto command=[&](const QString& id,const QString& action,const QJsonValue& value=QJsonValue()){
  auto original=capture();auto control=row(id);
  QJsonObject request{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces)},{"action",action},
   {"bridgeId",original.value("bridgeId")},{"generation",original.value("generation")},{"sequence",original.value("lastCommandSequence").toDouble()+1},
   {"observedElapsedMs",original.value("elapsedMs")},{"controlId",id},{"controlToken",control.value("token")}};
  if(action=="replace")request["text"]=value;if(action=="select-index")request["index"]=value;return request;
 };
 auto apply=[&](const QJsonObject& request){
  auto pointerAt=[&](QQuickItem* item,const QPointF& point){++pointers;return sendPointerAt(item,&surface,point);};
  auto click=[&](QQuickItem* item){return pointerAt(item,item->mapToScene(QPointF(item->width()/2,item->height()/2)));};
  auto result=ui.apply(root,&window,true,request,click,pointerAt);QTest::qWait(80);return result.value("performed").toBool();
 };
 auto input=[&](const QString&id,const QString&action,const QJsonValue&value=QJsonValue()){
  if(row(id).isEmpty()){
   std::cerr<<"missing "<<id.toStdString()<<" ready "<<capture().value("ready").toBool()<<'\n';
   std::function<void(QQuickItem*,int)> debug=[&](QQuickItem* node,int depth){if(depth>32)return;
    if(node->metaObject()->indexOfSignal("clicked()")>=0 && node->isVisible()) {
     const auto context=qmlContext(node);auto role=QQmlProperty(node,"DialogButtonBox.buttonRole",context).read();QString dialog;
     std::cerr<<node->metaObject()->className()<<" name "<<node->objectName().toStdString()<<" page "<<bool(assetsPage(node))<<" dialog "<<bool(assetsDialog(node,&dialog))<<" role "<<role.toString().toStdString()<<" type "<<role.userType()<<'\n';
    }for(auto child:node->childItems())debug(child,depth+1);};debug(window.contentItem(),0);return false;}
  if(!apply(command(id,action,value))){std::cerr<<"refused "<<id.toStdString()<<" "<<QJsonDocument(row(id)).toJson().toStdString()<<'\n';return false;}return true;
 };
 auto replace=[&](const QString&id,const QString&value){return input(id,"activate")&&input(id,"replace",value)&&row(id).value("text")==value;};
 auto page=row("assets.page");if(page.value("profile")!="native-assets-v1"||page.value("canWrite")!=true){std::cerr<<"page "<<QJsonDocument(page).toJson().toStdString()<<" root "<<assetsPage(root)<<" original "<<assetsComponent(root,"/hifi/dialogs/TabletAssetServer.qml")<<"\n";auto tree=find(root,"assetTree");std::cerr<<"tree "<<tree<<" resolved "<<assetsTree(tree)<<" original "<<assetsComponent(tree,"/hifi/dialogs/NativeModelTree.qml")<<"\n"<<QJsonDocument(capture()).toJson().toStdString();return 4;}
 if(!replace("assets.filter","main.gltf"))return 5;
 QString selected;for(const auto& value:capture().value("controls").toArray()){auto r=value.toObject();if(r.value("mapping").toObject().value("path")=="/e2e-root/main.gltf")selected=r.value("id").toString();}
 if(selected.isEmpty()||!input(selected,"activate")||row("assets.page").value("selectedPath")!="/e2e-root/main.gltf")return 6;
 // A row's original mapping identity changes its token, even at the same index.
 auto stale=command(selected,"activate");main->setData("/foreign/main.gltf",256);QTest::qWait(100);
 if(apply(stale))return 7;main->setData("/e2e-root/main.gltf",256);QTest::qWait(100);
 if(!input(selected,"activate"))return 23;
 if(!input("assets.import","activate")||!input("assets.model.accept","activate")||service->property("imports").toInt()!=1)return 8;
 if(!input("assets.rename","activate")||!replace("assets.rename.path","/renamed-test/")||!input("assets.rename.cancel","activate"))return 9;
 if(!input("assets.delete","activate")||!input("assets.delete.accept","activate")||service->property("deletes").toInt()!=1)return 10;
 // Permission changes enter via the actual existing Entities signal, then the
 // real binding disables Delete. An ACK cannot invent a permission error.
 service->setProperty("allowed",false);QMetaObject::invokeMethod(service.data(),"canWriteAssetsChanged",Q_ARG(bool,false));QTest::qWait(60);
 if(row("assets.page").value("canWrite")!=false||row("assets.delete").value("enabled")!=false||apply(command("assets.delete","activate"))||service->property("deletes").toInt()!=1)return 11;
 auto disabled=find(root,"assetDelete");auto upload=find(root,"assetUpload");if(!disabled||!upload)return 46;
 const auto disabledCenter=disabled->mapToScene(QPointF(disabled->width()/2,disabled->height()/2));
 const auto wrongPoint=upload->mapToScene(QPointF(upload->width()/2,upload->height()/2));
 if(!NormalControlUi::ownsPoint(disabled,&window,disabledCenter,{},true)
    ||NormalControlUi::ownsPoint(disabled,&window,wrongPoint,{},true))return 47;
 const int beforeWrongPoint=pointers;auto moved=command("assets.delete","probe-disabled");const auto x=disabled->x();disabled->setX(x+3);
 if(apply(moved)||pointers!=beforeWrongPoint)return 48;disabled->setX(x);
 if(!apply(command("assets.delete","probe-disabled"))||service->property("deletes").toInt()!=1||row("assets.delete").value("enabled")!=false||row("assets.delete").value("inputReady")!=false||!row("assets.delete.accept").isEmpty())return 31;
 {QQuickItem cover(window.contentItem());cover.setSize(QSizeF(900,1200));cover.setZ(100000);cover.setAcceptedMouseButtons(Qt::LeftButton);
  if(apply(command("assets.delete","probe-disabled")))return 32;}
 service->setProperty("allowed",true);QMetaObject::invokeMethod(service.data(),"canWriteAssetsChanged",Q_ARG(bool,true));QTest::qWait(60);
 if(apply(command("assets.delete","probe-disabled"))||apply(command("assets.upload","probe-disabled")))return 33;
 // Foreign modal obstruction must reject the real reference before delivery.
 QQuickItem blocker(window.contentItem());blocker.setSize(QSizeF(900,1200));blocker.setZ(100000);blocker.setAcceptedMouseButtons(Qt::LeftButton);
 if(apply(command("assets.upload","activate")))return 12;blocker.setVisible(false);
 if(!input("assets.upload","activate"))return 13;
 const QString directory=QString::fromLocal8Bit(argv[3]);
 auto navigate=[&](const QString& path){return replace("assets-file.folder",path)&&input("assets-file.folder","submit");};
 auto pick=[&](const QString& path){
  for(int wait=0;wait<20;++wait){for(const auto&value:capture().value("controls").toArray()){auto r=value.toObject();if(r.value("sourceUrl")==QUrl::fromLocalFile(path).toString())return input(r.value("id").toString(),"activate");}QTest::qWait(30);}
  std::cerr<<"missing actual file "<<path.toStdString()<<'\n';return false;
 };
 if(!navigate(directory)||!pick(directory+"/main.gltf")||!navigate(directory+"/mesh")||!pick(directory+"/mesh/triangle.bin")
    ||!navigate(directory+"/textures")||!pick(directory+"/textures/checker.png")||!input("assets-file.accept","activate"))return 14;
 if(row("assets-file.primary").value("count")!=3||!input("assets-file.primary","activate")||!input("assets-file.primary","select-index",0)
   ||!input("assets-file.confirm","activate"))return 15;
 if(!replace("assets.destination.path","/e2e-test/gltf-bundle/")||!input("assets.destination.accept","activate"))return 16;
 auto receipt=createVariant(service->property("bundleOriginal")).toMap();
 if(service->property("uploads").toInt()!=1||receipt.value("relative").toList().size()!=3||receipt.value("primary")!="main.gltf"
   ||!receipt.value("actual").toMap().value("error").toString().isEmpty()||receipt.value("destination")!="/e2e-test/gltf-bundle/"){std::cerr<<"upload "<<service->property("uploads").toInt()<<" "<<QJsonDocument::fromVariant(receipt).toJson().toStdString();return 17;}
 // Retire the actual selected main file while the original picker remains open.
 if(!input("assets.upload","activate")||!navigate(directory)||!pick(directory+"/main.gltf"))return 18;
 if(!QFile::remove(directory+"/main.gltf")||!input("assets-file.accept","activate"))return 19;
 if(row("assets-file.cancel").value("picker").toObject().value("error")!="A selected file is no longer available."||service->property("uploads").toInt()!=1)return 20;
 if(!input("assets-file.cancel","activate")||!row("assets-file.cancel").isEmpty())return 21;
 // A similarly named foreign object/context is never an Assets page/control.
 QQmlComponent foreign(&engine);foreign.setData("import QtQuick 2.7; Item { objectName: \"assetUpload\"; signal clicked() }",QUrl("file:///foreign.qml"));QScopedPointer<QObject> bad(foreign.create());
 if(!assetsControlId(qobject_cast<QQuickItem*>(bad.data())).isEmpty())return 22;
 QFile originals(argv[4]);if(!originals.open(QIODevice::WriteOnly)||originals.write(QJsonDocument(observations).toJson(QJsonDocument::Compact))<0)return 24;originals.close();
 if(pointers<20)return 45;
 std::cout<<"Original Pico Assets observer, pointer route, actual QML/files and counterexamples passed\n";return 0;
}
