// Test-only read-only UI executable; never installed or linked into the app.
#include "phoneclient.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTest>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <functional>
int main(int argc,char **argv){
 qputenv("QT_QUICK_CONTROLS_STYLE","Basic");qputenv("ETHERSHELL_DEVELOPMENT","1");
 QGuiApplication app(argc,argv);const auto args=app.arguments();
 auto option=[&](const QString &key){int i=args.indexOf(key);return i>=0&&i+1<args.size()?args[i+1]:QString();};
 auto out=option("--output");QDir().mkpath(out);const auto size=option("--size").split('x');
 if(out.isEmpty()||size.size()!=2)return 2;
 PhoneClient phone;QQmlApplicationEngine engine;int warnings=0;
 QObject::connect(&engine,&QQmlEngine::warnings,&app,[&](const QList<QQmlError>& errors){warnings+=errors.size();});
 QFile snapshot(option("--snapshot"));if(snapshot.open(QIODevice::ReadOnly))QMetaObject::invokeMethod(&phone,"update",Q_ARG(QString,QString::fromUtf8(snapshot.readAll())));
 engine.rootContext()->setContextProperty("Phone",&phone);engine.rootContext()->setContextProperty("PocketDisplay",!args.contains("--desktop"));
 engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 3;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());window->resize(size[0].toInt(),size[1].toInt());QTest::qWait(150);
 int checks=0;
 auto check=[&](bool ok,const char *what){++checks;if(!ok)qFatal("UI check failed: %s",what);};
 std::function<QQuickItem*(QQuickItem*,const QString&)> find=[&](QQuickItem *item,const QString &name)->QQuickItem*{
  if(item->objectName()==name)return item;
  for(auto *child:item->childItems())if(auto *found=find(child,name))return found;
  return nullptr;
 };
 auto findItem=[&](const QString &name)->QQuickItem*{return find(window->contentItem(),name);};
 auto *key=findItem("key-1");check(key!=nullptr,"keypad exists");check(key->width()>=44&&key->height()>=44,"key touch target");
 QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,key->mapToScene(QPointF(key->width()/2,key->height()/2)).toPoint());QTest::qWait(50);
 auto *digits=findItem("dialNumber");check(digits&&digits->property("text").toString()=="1","tap enters a digit");
 check(!findItem("dialCall")->isEnabled(),"unavailable voice disables ordinary Call");
 for(int tab=0;tab<4;++tab){window->setProperty("tab",tab);QTest::qWait(120);check(window->grabWindow().save(out+"/tab-"+QString::number(tab)+".png"),"tab screenshot");}
 check(findItem("callPrivacy")&&findItem("callPrivacy")->isEnabled(),"ready service enables privacy settings");
 // Contact editor opening and layout, without writing any store.
 window->setProperty("tab",2);QVariant contact=QVariantMap{{"name","Test contact"},{"numbers",QStringList{"+441234567890"}}};
 check(QMetaObject::invokeMethod(window,"editContact",Q_ARG(QVariant,contact)),"open contact editor");QTest::qWait(120);
 auto *editor=window->findChild<QObject*>("contactEditor");check(editor!=nullptr,"contact dialog exists");
 const auto ex=editor->property("x").toDouble(),ey=editor->property("y").toDouble(),ew=editor->property("width").toDouble(),eh=editor->property("height").toDouble(),es=editor->property("scale").toDouble();
 check(ex>=0&&ey>=0&&ex+ew*es<=window->width()+1&&ey+eh*es<=window->height()+1,"contact dialog fits window");
 check(window->grabWindow().save(out+"/contact.png"),"contact editor screenshot");
 // Separate synthetic overlay test. The production app never receives fixtures.
 window->hide();
 const QString incoming=QString::fromUtf8(R"({"ready":true,"config":{"hideCallerOnLock":true},"calls":[{"state":"Incoming","name":"PRIVATE TEST CALLER","number":"+441234567890","key":"synthetic"}]})");
 QMetaObject::invokeMethod(&phone,"update",Q_ARG(QString,incoming));
 engine.load(QUrl("qrc:/tests/overlay-test.qml"));check(engine.rootObjects().size()==2,"overlay test loads");
 auto *lockWindow=qobject_cast<QQuickWindow*>(engine.rootObjects().last());QTest::qWait(120);
 auto *overlay=lockWindow->findChild<QObject*>("incomingTestOverlay");check(overlay&&overlay->property("visible").toBool(),"incoming overlay appears");
 check(overlay->property("privateCaller").toBool(),"caller is private while locked");
 check(lockWindow->grabWindow().save(out+"/incoming-locked-synthetic.png"),"locked overlay screenshot");
 auto active=incoming;active.replace("Incoming","Active");QMetaObject::invokeMethod(&phone,"update",Q_ARG(QString,active));QTest::qWait(100);
 check(overlay->property("visible").toBool(),"active call retains locked controls");
 check(lockWindow->property("locked").toBool(),"answer/active state never unlocks");
 const QString ended=QStringLiteral("{\"calls\":[],\"config\":{\"hideCallerOnLock\":true}}");
 QMetaObject::invokeMethod(&phone,"update",Q_ARG(QString,ended));QTest::qWait(100);
 check(!overlay->property("visible").toBool()&&lockWindow->property("locked").toBool(),"end returns to locked state");
 check(warnings==0,"no QML warnings");
 QFile result(out+"/result.json");check(result.open(QIODevice::WriteOnly),"result file");
 result.write(QJsonDocument(QJsonObject{{"checks",checks},{"warnings",warnings},{"width",window->width()},{"height",window->height()},{"writesDisabled",true}}).toJson());
 return 0;
}
