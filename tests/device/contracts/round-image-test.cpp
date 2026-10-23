// SPDX-License-Identifier: Apache-2.0
#include <QGuiApplication>
#include <QQuickView>
#include <QQuickItem>
#include <QQmlProperty>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QQuickRenderControl>
#include <QQuickRenderTarget>
#include <QQmlContext>
#include <QTest>
#include <QImage>
#include <cassert>
#include <iostream>
struct CountedImages : QQuickImageProvider {
 int requests {0};
 QSize requested;
 CountedImages():QQuickImageProvider(QQuickImageProvider::Image){}
 QImage requestImage(const QString& id,QSize* size,const QSize& request) override {
  ++requests;requested=request;
  if(id=="missing"){*size=QSize();return {};}
  QImage image(24,16,QImage::Format_ARGB32_Premultiplied);image.fill(request.width()>0 ? Qt::green : Qt::cyan);*size=image.size();return image;
 }
};
struct ProxyRenderControl : QQuickRenderControl {
 QWindow* proxy;
 explicit ProxyRenderControl(QWindow* window):proxy(window){}
 QWindow* renderWindow(QPoint* offset) override {
  if(offset)*offset=QPoint();
  return proxy;
 }
};
static void checkRenderControlPixels(const char* qml) {
 QWindow proxy;proxy.resize(64,64);proxy.show();
 ProxyRenderControl control(&proxy);QQuickWindow window(&control);
 window.resize(64,64);window.setColor(Qt::transparent);
 QImage image(64,64,QImage::Format_ARGB32_Premultiplied);image.fill(Qt::transparent);
 window.setRenderTarget(QQuickRenderTarget::fromPaintDevice(&image));
 QQmlEngine engine;engine.rootContext()->setContextProperty("offscreenWindow",&window);
 engine.rootContext()->setContextProperty("offscreenRenderWindow",&proxy);
 auto provider=new CountedImages;engine.addImageProvider("counted",provider);
 QQmlComponent component(&engine,QUrl::fromLocalFile(qml));
 auto root=qobject_cast<QQuickItem*>(component.create());assert(root);
 root->setParentItem(window.contentItem());root->setWidth(64);root->setHeight(64);
 assert(QQmlProperty(root,"border.width").write(0));root->setProperty("radius",16);
 root->setProperty("source",QUrl("image://counted/proxy"));
 auto render=[&]{for(int i=0;i<30;++i){QTest::qWait(5);control.polishItems();control.sync();control.render();}};
 render();assert(!window.isVisible()&&proxy.isVisible());
 assert(provider->requests==1&&root->property("status").toInt()==1);
 if(image.pixelColor(32,32)!=QColor(Qt::cyan)) {
  std::cerr<<"proxy center="<<image.pixelColor(32,32).name(QColor::HexArgb).toStdString()
   <<" rootVisible="<<root->isVisible()<<" contentVisible="<<window.contentItem()->isVisible()
   <<" captureBusy="<<root->property("captureBusy").toBool()
   <<" captureAgain="<<root->property("captureAgain").toBool()<<std::endl;
  for(auto child:root->childItems())std::cerr<<child->metaObject()->className()<<" visible="<<child->isVisible()<<" size="<<child->width()<<","<<child->height()<<std::endl;
 }
 assert(image.pixelColor(32,32)==QColor(Qt::cyan));assert(image.pixelColor(0,0).alpha()==0);
 proxy.hide();assert(QQmlProperty(root,"sourceSize.width").write(12));render();
 assert(provider->requests==2);proxy.show();render();
 assert(provider->requests==2&&image.pixelColor(32,32)==QColor(Qt::green));
 root->setProperty("source",QUrl("image://counted/missing"));render();
 assert(image.pixelColor(32,32).alpha()==0);
 delete root;control.invalidate();
}
int main(int argc,char**argv){
 QGuiApplication app(argc,argv);assert(argc==4);
 QQuickView rounded,reference;rounded.setColor(Qt::transparent);reference.setColor(Qt::transparent);
 rounded.setSource(QUrl::fromLocalFile(argv[1]));reference.setSource(QUrl::fromLocalFile(argv[2]));
 assert(rounded.status()==QQuickView::Ready&&reference.status()==QQuickView::Ready);
 auto r=rounded.rootObject();auto ref=reference.rootObject();r->setWidth(64);r->setHeight(64);rounded.resize(64,64);reference.resize(64,64);
 assert(QQmlProperty(r,"border.width").write(0));r->setProperty("radius",0);
 auto source=QUrl::fromLocalFile(argv[3]);r->setProperty("source",source);ref->setProperty("source",source);QTest::qWait(150);assert(r->property("status").toInt()==1);rounded.show();reference.show();
 for(int mode=0;mode<=6;++mode){
  r->setProperty("fillMode",mode);ref->setProperty("fillMode",mode);QTest::qWait(100);
  assert(r->property("status").toInt()==1);assert(r->property("progress").toReal()==1);
  auto actual=rounded.grabWindow(),expected=reference.grabWindow();assert(!actual.isNull()&&!expected.isNull());
  // Compare interior color regions; Qt Image and Canvas filtering at source
  // color discontinuities differs and is not asserted pixel-identical.
  for(int y:{6,18,26,42,54})for(int x:{6,18,26,42,54}){auto a=actual.pixelColor(x,y),b=expected.pixelColor(x,y);if(abs(a.red()-b.red())>4||abs(a.green()-b.green())>4||abs(a.blue()-b.blue())>4||abs(a.alpha()-b.alpha())>4){std::cerr<<"mode="<<mode<<" x="<<x<<" y="<<y<<" actual="<<a.name(QColor::HexArgb).toStdString()<<" expected="<<b.name(QColor::HexArgb).toStdString()<<std::endl;return 2;}}
 }
 r->setProperty("fillMode",0);r->setProperty("radius",24);QTest::qWait(100);auto image=rounded.grabWindow();assert(image.pixelColor(0,0).alpha()==0);assert(image.pixelColor(32,32).alpha()>240);
 assert(QQmlProperty(r,"border.width").write(3));assert(QQmlProperty(r,"border.color").write(QColor("magenta")));QTest::qWait(100);image=rounded.grabWindow();assert(image.pixelColor(32,1).red()>240&&image.pixelColor(32,1).blue()>240);
 auto provider=new CountedImages;rounded.engine()->addImageProvider("counted",provider);
 r->setProperty("source",QUrl("image://counted/one"));QTest::qWait(100);
 assert(provider->requests==1&&r->property("status").toInt()==1);
 r->setProperty("radius",20);QTest::qWait(100);image=rounded.grabWindow();assert(image.pixelColor(32,32)==QColor(Qt::cyan));assert(provider->requests==1);
 r->setVisible(false);QTest::qWait(100);assert(rounded.grabWindow().pixelColor(32,32).alpha()==0);
 assert(QQmlProperty(r,"sourceSize.width").write(12));QTest::qWait(100);assert(provider->requests==2&&provider->requested.width()==12);
 r->setVisible(true);QTest::qWait(100);assert(provider->requests==2);image=rounded.grabWindow();assert(image.pixelColor(32,32)==QColor(Qt::green));
 r->setProperty("radius",18);QTest::qWait(100);assert(provider->requests==2);image=rounded.grabWindow();assert(image.pixelColor(32,32)==QColor(Qt::green));
 // Canvas resize and window visibility must not strand a ready image.
 r->setWidth(0);r->setHeight(0);QTest::qWait(100);r->setWidth(64);r->setHeight(64);QTest::qWait(100);assert(rounded.grabWindow().pixelColor(32,32)==QColor(Qt::green));
 rounded.hide();assert(QQmlProperty(r,"sourceSize.width").write(8));QTest::qWait(100);assert(provider->requests==3);rounded.show();QTest::qWait(100);assert(rounded.grabWindow().pixelColor(32,32)==QColor(Qt::green));
 assert(r->setProperty("mipmap",true));assert(r->property("mipmap").toBool());assert(r->setProperty("smooth",false));assert(!r->property("smooth").toBool());
 r->setProperty("source",QUrl("image://counted/missing"));QTest::qWait(100);assert(provider->requests==4&&r->property("status").toInt()==3);image=rounded.grabWindow();assert(image.pixelColor(32,32).alpha()==0);
 r->setProperty("source",QUrl());QTest::qWait(100);assert(r->property("status").toInt()==0);image=rounded.grabWindow();assert(image.pixelColor(32,32).alpha()==0);
 checkRenderControlPixels(argv[1]);
}
