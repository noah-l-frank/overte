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
#include <QTemporaryDir>
#include "actual-pointer-route.inc"
#include "tests/device/native/NormalControlUi.h"
#include "tests/device/native/AssetsUiInventory.h"
#define ASSETS_ORIGINAL_ENDPOINTS
#include "avatar-navigation-observation-seams.h"
namespace overte::e2e {
inline bool placesField(const QString&){return false;}
inline bool placesText(const QString&){return false;}
inline bool placesScrollPoint(QQuickItem*,const QString&,QPointF&){return false;}
}
#if !defined(ANDROID_APP_PICO_INTERFACE)
#define ANDROID_APP_PICO_INTERFACE
#endif
#include "PicoAssetsReadJob.h"
#include "assets-read-endpoints-host.h"
#include "MappingRequest.h"
#include "AssetRequest.h"
#include "assets-upload-mappings-host.h"
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
#include "AssetUpload.h"
#endif
#include "AssetsBundleOriginals.inc"
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
#include "AssetsUploadOriginalFactories.inc"
#else
void AssetMappingsScriptingInterface::advanceBundle(const std::shared_ptr<BundleUpload>& state) {
 ++backendDispatches;finishBundle(state,"Explicit host backend is unavailable.");
}
#endif
#include "assets-files-getter-host.h"
#include "actual-assets-navigation.inc"
#undef ANDROID_APP_PICO_INTERFACE
#include "libraries/ui/src/FileDialogHelper.h"
Q_LOGGING_CATEGORY(uiLogging,"ui")
Q_LOGGING_CATEGORY(asset_client,"assets-client-host")
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
#include "assets-tablet-host.h"
#include "tests/device/native/AssetsPageObservation.h"
Q_LOGGING_CATEGORY(qmlLogging,"qml-original-loader-host")
#include "AssetsTabletOriginals.inc"
#endif
#include "AssetsReadOriginals.inc"
#if defined(ASSETS_ORIGINAL_SERVER_QUERY)
#include "assets-server-status-host.h"
Q_LOGGING_CATEGORY(asset_server,"assets-normal-server-read-host")
#endif
namespace AssetUtils {
QByteArray loadFromCache(const QUrl&){return {};}
bool saveToCache(const QUrl&,const QByteArray&){return true;}
}
struct AssetsNativeClient {
 QSharedPointer<AssetClient> client{new AssetClient,[](AssetClient* value){value->deleteLater();}};QThread worker;
 explicit AssetsNativeClient(std::function<QByteArray()> serverWire={}){DependencyManager::slot<AssetClient>()=client;client->content="independent original mapping bytes";
  client->originalServerAll=std::move(serverWire);
  const auto hash=QCryptographicHash::hash(client->content,QCryptographicHash::Sha256);
  auto primitive=[](QByteArray& raw,const auto& value){raw.append(reinterpret_cast<const char*>(&value),sizeof(value));};
  const QByteArray path="/foreign/original.bin";primitive(client->allReply,quint32(1));primitive(client->allReply,quint32(path.size()));
  client->allReply+=path;client->allReply+=hash;primitive(client->allReply,AssetUtils::Irrelevant);
#if defined(ASSETS_ORIGINAL_BUNDLE_UPLOADS)
  client->mappings.insert(QString::fromUtf8(path),QString::fromLatin1(hash.toHex()));
#endif
  client->moveToThread(&worker);worker.start();
 }
 ~AssetsNativeClient(){DependencyManager::slot<AssetClient>().clear();client.clear();worker.quit();if(!worker.wait(1000)) {qFatal("Original host AssetClient did not retire");}}
};
using namespace overte::e2e;
static QQuickItem* find(QQuickItem* node,const QString& name) {
 if(node->objectName()==name)return node;for(auto child:node->childItems())if(auto found=find(child,name))return found;return nullptr;
}
int main(int argc,char**argv){
 HostApplication app(argc,argv);PathUtils::qml=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[5])+"/interface/resources/qml/");
 if(!app.arguments().contains("--testScript")){AssetsUi gated;if(!gated.observe(nullptr,nullptr).isEmpty())return 44;return 0;}
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
 std::unique_ptr<HostUnrelatedQml> unrelated;
#endif
 QQmlEngine engine;engine.addImportPath(argv[1]);FileDialogHelper files;
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
 const bool persistent=app.arguments().contains("--persistent-tablet");
 std::unique_ptr<HostSurfaceLoader> loader;std::unique_ptr<TabletProxy> tablet;std::unique_ptr<HostPicoStandardChannel> standard;
 if(persistent) {
  engine.rootContext()->setBaseUrl(PathUtils::qml);
  unrelated=std::make_unique<HostUnrelatedQml>(QUrl::fromLocalFile(QFileInfo(argv[1]).absolutePath()+"/unrelated-tablet-content.qml"));
  engine.setUrlInterceptor(unrelated.get());loader=std::make_unique<HostSurfaceLoader>(&engine);
  engine.rootContext()->setContextProperty("QmlSurface",loader.get());
 }
#endif
 const auto originalUploads=QSharedPointer<AssetMappingsScriptingInterface>::create();
 DependencyManager::slot<AssetMappingsScriptingInterface>()=originalUploads;
 const auto originalNodes=QSharedPointer<NodeList>::create();DependencyManager::slot<NodeList>()=originalNodes;
 engine.rootContext()->setContextProperty("originalBundleService",originalUploads.data());
#if defined(ASSETS_ORIGINAL_SERVER_QUERY)
 QTemporaryDir serverFiles;AssetServer server;server._filesDirectory=QDir(serverFiles.path());
 assert(serverFiles.isValid());
 AssetsNativeClient originalReadClient([&]{
  QByteArray wire;assert(QMetaObject::invokeMethod(&server,[&]{wire=server.originalWire();},Qt::BlockingQueuedConnection));return wire;
 });
 const auto foreignHash=putOriginal(server,originalReadClient.client->content);server._fileMappings["/foreign/original.bin"]=foreignHash;
#else
 AssetsNativeClient originalReadClient;
#endif
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
   ++uploads;return originalBundleService.uploadBundle(paths,relative,destination,primary,progress,done);
 }
})",QUrl("file:///explicit-assets-endpoints.qml"));
 QScopedPointer<QObject> service(helper.create());if(!service){qWarning()<<helper.errors();return 1;}
 for(const auto& name:QStringList{"Assets","Entities","MenuInterface","MyAvatar","Vec3","Quat","ApplicationInterface"})engine.rootContext()->setContextProperty(name,service.data());
 QUrl rootSource=QUrl::fromLocalFile(argv[2]);
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
 if(persistent)rootSource=PathUtils::qmlUrl("hifi/tablet/TabletRoot.qml");
#endif
 QQmlComponent component(&engine,rootSource);QScopedPointer<QObject> object(component.create());
 if(!object){qWarning()<<component.errors();return 2;}auto root=qobject_cast<QQuickItem*>(object.data());if(!root)return 3;
 QQuickWindow window;window.resize(900,1200);root->setParentItem(window.contentItem());root->setSize(QSizeF(900,1200));window.show();window.requestActivate();QTest::qWait(120);
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
 overte::e2e::AssetsPageObservation assetsPages;
 QPointer<QQuickItem> originalAssetsPage,originalAssetsLoader;
 QPointer<QQmlContext> originalAssetsContext;QPointer<QQuickWindow> originalAssetsWindow(&window);
 if(persistent) {
  loader->root=root;tablet=std::make_unique<TabletProxy>();tablet->_qmlTabletRoot=root;
  tablet->loadQMLSourceImpl(QUrl::fromLocalFile(argv[2]).toString(),false,false);QTest::qWait(120);
  originalAssetsPage=find(root,"AssetServer");originalAssetsLoader=find(root,"loader");
  auto filter=find(root,"assetFilter");
  for(auto context=filter ? qmlContext(filter) : nullptr;context;context=context->parentContext()) {
   if(context->baseUrl()==QUrl::fromLocalFile(argv[2]) && context->nameForObject(originalAssetsPage)=="root") {originalAssetsContext=context;break;}
  }
  if(!originalAssetsPage || !originalAssetsContext || !originalAssetsLoader)return 72;
  standard=std::make_unique<HostPicoStandardChannel>();
  engine.globalObject().setProperty("gTablet",engine.newQObject(tablet.get()));
  engine.globalObject().setProperty("standardEndpoint",engine.newQObject(standard.get()));
  const QString endpoints=R"(
   var Settings={getValue:function(name,fallback){if(name!=="deferTabletCreationUntilOpen")throw Error("Foreign setting");return true;}};
   var controllerStandard={LeftPrimaryThumb:501};
   var Controller={newMapping:function(name){if(name!=="pico-tablet-x-back")throw Error("Foreign mapping");return {
    from:function(channel){if(channel!==501)throw Error("Foreign channel");return {peek:function(){return {to:function(callback){standardEndpoint.install(callback);}};}};},enable:function(){}};}};
   function checkTablet() {} function print() {}
   var HMD={closeTablet:function(){throw Error("A second Home input is outside this host scope");}};
  )";
  QFile script(QString::fromLocal8Bit(argv[5])+"/scripts/system/tablet-ui/tabletUI.js");if(!script.open(QIODevice::ReadOnly))return 70;
  const QString original=QString::fromUtf8(script.readAll());const auto start=original.indexOf("    var picoBackMapping = null;");
  const auto end=original.indexOf("    var updateShowTabletTimer",start);
  if(start<0 || end<=start || engine.evaluate(endpoints+original.mid(start,end-start),"original-pico-x-mapping.js").isError() || !standard->callback.isCallable())return 71;
 }
#endif
 overte::pico::e2e::NavigationUi ui;OffscreenQmlSurface surface(root,&window);int pointers=0;
 QJsonObject lastNativeResult;QJsonArray observations;auto capture=[&]{auto value=ui.observe(root,&window,true);observations.append(value);return value;};
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
  auto result=ui.apply(root,&window,true,request,click,pointerAt);lastNativeResult=result;QTest::qWait(80);return result.value("performed").toBool();
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
 if(app.arguments().contains("--serve")) {
  QTemporaryDir privateInputs;TestScriptingInterface owner;owner._testResultsLocation=privateInputs.path();owner._featureLifecycle=std::make_shared<AssetsHostLifecycle>();
  std::string line;while(std::getline(std::cin,line)) {
   const auto request=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object();const auto action=request.value("action").toString();QJsonObject packet;
   if(action=="host-observe-original-ui") {packet=capture();}
#if defined(ASSETS_ORIGINAL_SERVER_QUERY)
   else if(action=="host-original-server-wire") {
    packet=QJsonObject{{"requestId",request.value("requestId")},{"wireBase64",QString::fromLatin1(server.originalWire().toBase64())},
     {"serverFiles",server.originalFiles()},{"serverInstance",server.instance},{"sourceSequence",static_cast<double>(server.queries)},
     {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())}};
   }
#endif
#if defined(ASSETS_PERSISTENT_TABLET_HOST)
   else if(action=="host-observe-assets-pages" && persistent) {
    packet=assetsPages.observe(root,&window,tablet->shown(),tablet->onHomeScreen(),loader->_featureQmlLoads->snapshot());
    if(!packet.isEmpty()){packet["commandId"]=request.value("commandId");packet["action"]="observe";}
   }
   else if(action=="host-normal-pico-x" && persistent) {
    const bool pressed=standard->publish(true),released=standard->publish(false);QTest::qWait(80);
    packet=QJsonObject{{"accepted",pressed && released},{"edges",standard->edges},{"held",standard->held}};
   }
   else if(action=="host-original-assets-pointers" && persistent) {
    packet=QJsonObject{{"pageAlive",!originalAssetsPage.isNull()},{"contextAlive",!originalAssetsContext.isNull()},
     {"contextValid",originalAssetsContext && originalAssetsContext->isValid()},
     {"loaderAlive",!originalAssetsLoader.isNull()},{"windowAlive",!originalAssetsWindow.isNull()}};
   }
#endif
   else if(action=="host-original-ui-input") {apply(request.value("original").toObject());packet=lastNativeResult;}
   else if(action=="feature-pico-assets-files") {packet=QJsonObject::fromVariantMap(owner.featurePicoAssetsFiles(request.toVariantMap()));}
   else if(action=="feature-pico-assets-uploads-observe") {packet=QJsonObject::fromVariantMap(owner.featurePicoAssetsUploadsObservation(request.toVariantMap()));}
   else if(action=="feature-pico-assets-observe" || action=="feature-pico-assets-download" || action=="feature-pico-assets-resolve" || action=="feature-pico-assets-read-retire") {
    QElapsedTimer elapsed;elapsed.start();QVariantMap actual;
    do{QCoreApplication::processEvents();actual=action=="feature-pico-assets-read-retire"?owner.featurePicoAssetsReadRetire(request.toVariantMap()):owner.featurePicoAssetsRead(request.toVariantMap());
     if(actual.value("pending")!=true)break;QThread::msleep(1);}while(elapsed.elapsed()<1000);packet=QJsonObject::fromVariantMap(actual);
   }
   std::cout<<QJsonDocument(packet).toJson(QJsonDocument::Compact).constData()<<std::endl;
  }return 0;
 }
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
 // Stage actual owned private files through the complete original getter.
 QTemporaryDir privateInputs;TestScriptingInterface inputOwner;inputOwner._testResultsLocation=privateInputs.path();
 inputOwner._featureLifecycle=std::make_shared<AssetsHostLifecycle>();
 QVariantMap fixedFiles;for(const auto& name:PrivateAssetsFiles::inputs()){fixedFiles[name]=QString::fromLatin1((name+"-actual-input").toUtf8().toBase64());}
 QVariantMap fileCommand{{"schemaVersion",1},{"commandId",QString(32,'c')},{"action","feature-pico-assets-files"},
  {"operation","stage"},{"runId",QString(32,'a')},{"ownerToken",QString(64,'b')},{"files",fixedFiles}};
 const auto stagedFiles=inputOwner.featurePicoAssetsFiles(fileCommand).value("source").toMap();if(stagedFiles.value("exists")!=true)return 56;
 const auto privateRoot=QUrl(stagedFiles.value("directory").toString()).toLocalFile();
 QVariantMap uploadCommand{{"schemaVersion",1},{"commandId",QString(32,'1')},{"action","feature-pico-assets-uploads-observe"},{"runId",QString(32,'a')}};
 const auto uploadsBefore=inputOwner.featurePicoAssetsUploadsObservation(uploadCommand);
 if(uploadsBefore.value("source").toMap().value("totalCalls")!=0||originalUploads->backendDispatches!=0)return 62;
 if(!navigate(privateRoot+"/gltf-bundle")||!pick(privateRoot+"/gltf-bundle/main.gltf"))return 57;
 // Original Cancel destroys actual picker/model; hidden objects stay live.
 auto browser=find(root,"nativeFileBrowser");if(!browser)return 49;
 QPointer<QQuickItem> originalBrowser(browser);QPointer<QObject> originalModel(createVariant(browser->property("model")).value<QObject*>());
 auto browserInventory=capture().value("assetsUiInventory").toObject();
 if(!browserInventory.value("complete").toBool()||browserInventory.value("browsers").toArray().size()!=1)return 50;
 const auto browserId=browserInventory.value("browsers").toArray()[0].toObject().value("id");
 browser->setVisible(false);auto hidden=capture().value("assetsUiInventory").toObject().value("browsers").toArray()[0].toObject();
 if(hidden.value("id")!=browserId||hidden.value("visible")!=false||hidden.value("rootAlive")!=true||hidden.value("modelAlive")!=true||!originalModel)return 51;
 browser->setVisible(true);if(!input("assets-file.cancel","activate"))return 52;
 auto canceled=capture().value("assetsUiInventory").toObject();
 if(!canceled.value("complete").toBool()||!originalBrowser.isNull()||!originalModel.isNull())return 53;
 auto retired=canceled.value("browsers").toArray()[0].toObject();
 if(retired.value("id")!=browserId||retired.value("rootAlive")!=false||retired.value("modelAlive")!=false
   ||retired.value("inCurrentTree")!=false||service->property("uploads").toInt()!=0)return 54;
 uploadCommand["commandId"]=QString(32,'2');const auto uploadsAfter=inputOwner.featurePicoAssetsUploadsObservation(uploadCommand);
 if(uploadsAfter.value("source")!=uploadsBefore.value("source")||originalUploads->backendDispatches!=0)return 63;
 fileCommand.remove("files");fileCommand["operation"]="observe";fileCommand["commandId"]=QString(32,'d');
 const auto filesAfterCancel=inputOwner.featurePicoAssetsFiles(fileCommand).value("source").toMap();
 if(filesAfterCancel.value("files")!=stagedFiles.value("files")||!QFileInfo::exists(privateRoot+"/gltf-bundle/main.gltf"))return 58;
 // Exact QObject/model death authorizes only staged-file release, not full
 // context/backend retirement. No upload endpoint was invoked by Cancel.
 fileCommand["operation"]="release";fileCommand["commandId"]=QString(32,'e');
 if(inputOwner.featurePicoAssetsFiles(fileCommand).value("source").toMap().value("retired")!=true||QFileInfo::exists(privateRoot))return 59;
 if(!input("assets.upload","activate"))return 55;
 if(!navigate(directory)||!pick(directory+"/main.gltf")||!navigate(directory+"/mesh")||!pick(directory+"/mesh/triangle.bin")
    ||!navigate(directory+"/textures")||!pick(directory+"/textures/checker.png")||!input("assets-file.accept","activate"))return 14;
 if(row("assets-file.primary").value("count")!=3||!input("assets-file.primary","activate")||!input("assets-file.primary","select-index",0)
   ||!input("assets-file.confirm","activate"))return 15;
 if(!replace("assets.destination.path","/e2e-test/gltf-bundle/")||!input("assets.destination.accept","activate"))return 16;
 auto receipt=createVariant(service->property("bundleOriginal")).toMap();
 uploadCommand["commandId"]=QString(32,'3');const auto called=inputOwner.featurePicoAssetsUploadsObservation(uploadCommand).value("source").toMap();
 if(called.value("totalCalls")!=1||called.value("originalActiveBundles")!=0||originalUploads->backendDispatches!=1)return 64;
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
 // A foreign same-name browser cannot enter the authoritative inventory.
 {QQuickItem foreignBrowser(root);foreignBrowser.setParentItem(root);foreignBrowser.setObjectName("nativeFileBrowser");
  foreignBrowser.setProperty("caption","Select an asset and its companion files");
  auto incomplete=capture().value("assetsUiInventory").toObject();
  if(incomplete.value("complete")!=false||!incomplete.value("browsers").toArray().isEmpty())return 60;}
 if(!capture().value("assetsUiInventory").toObject().value("complete").toBool())return 61;
 uploadCommand["commandId"]=QString(32,'4');
 if(inputOwner.featurePicoAssetsUploadsObservation(uploadCommand).value("source").toMap().value("totalCalls")!=1)return 65;
 // Even rejected/invalid original calls invalidate a no-upload comparison.
 originalUploads->uploadBundle({}, {}, "/invalid", "absent.gltf", {}, {});QTest::qWait(20);
 uploadCommand["commandId"]=QString(32,'5');const auto rejected=inputOwner.featurePicoAssetsUploadsObservation(uploadCommand).value("source").toMap();
 if(rejected.value("totalCalls")!=2||rejected.value("originalActiveBundles")!=0||originalUploads->backendDispatches!=1)return 66;
 QFile originals(argv[4]);if(!originals.open(QIODevice::WriteOnly)||originals.write(QJsonDocument(observations).toJson(QJsonDocument::Compact))<0)return 24;originals.close();
 if(pointers<20)return 45;
 std::cout<<"Original Pico Assets observer, pointer route, actual QML/files and counterexamples passed\n";return 0;
}
