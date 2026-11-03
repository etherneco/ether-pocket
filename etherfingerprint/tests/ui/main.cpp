// Isolated blocked-state UI fixture; never supplies an authentication result.
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQmlPropertyMap>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTimer>
#include <QImage>
#include <QDebug>
static bool fits(QQuickItem *root, qreal width) {
 for(auto *child:root->childItems()) {
  if(!child->isVisible())continue;
  if(child->property("text").isValid() && !child->property("text").toString().isEmpty()) {
   auto r=child->mapRectToScene(QRectF(0,0,child->width(),child->height()));
   if(r.left() < -1 || r.right() > width+1 || child->property("truncated").toBool()){qWarning()<<"Overflow"<<child->property("text")<<r<<width;return false;}
  }
  if(!fits(child,width))return false;
 }
 return true;
}
int main(int argc,char **argv) {
 QGuiApplication app(argc,argv);
 if(argc!=4)return 2;
 const bool dark=qEnvironmentVariableIntValue("FP_TEST_DARK");
 QQmlPropertyMap control;
 control.insert("state",QVariantMap{{"ready",true},{"detected",true},{"vendor","Goodix"},{"driver","goodix_fp"},{"deviceInterface","/dev/goodix_fp"},{"firmwareStatus","Not verified"},{"lastError","No verified trusted biometric adapter; PIN/password required"}});
 if(qEnvironmentVariableIsSet("FP_TEST_SERVICE_GONE"))control.insert("state",QVariantMap{{"ready",false}});
 if(qEnvironmentVariableIsSet("FP_TEST_NO_SENSOR"))control.insert("state",QVariantMap{{"ready",true},{"detected",false}});
 const auto initialState=control.value("state");
 QQmlApplicationEngine engine;
 engine.rootContext()->setContextProperty("FingerprintControl",&control);
 engine.rootContext()->setContextProperty("testWidth",QString(argv[2]).toInt());
 engine.rootContext()->setContextProperty("testHeight",QString(argv[3]).toInt());
 engine.rootContext()->setContextProperty("testDark",dark);
 engine.rootContext()->setContextProperty("testFontScale",qEnvironmentVariableIsSet("FP_TEST_LARGE_TEXT")?1.4:1.0);
 engine.rootContext()->setContextProperty("testMotion",qEnvironmentVariableIntValue("FP_TEST_MOTION")?150:0);
 engine.rootContext()->setContextProperty("testUiScale",qEnvironmentVariableIsSet("FP_TEST_SCALE")?qEnvironmentVariable("FP_TEST_SCALE").toDouble():1.0);
 bool warnings=false;
 QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[&](const QList<QQmlError>&){warnings=true;});
 engine.load(QUrl::fromLocalFile(QString(argv[1])+"/tests/ui/Page.qml"));
 if(engine.rootObjects().isEmpty())return 3;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
 QTimer::singleShot(1200,&app,[&]{
  auto *toggle=window->findChild<QQuickItem*>("fingerprintToggle");
  auto *enroll=window->findChild<QQuickItem*>("fingerprintEnroll");
  auto *test=window->findChild<QQuickItem*>("fingerprintTest");
  auto *count=window->findChild<QQuickItem*>("fingerprintCount");
  auto *manager=window->findChild<QQuickItem*>("fingerprintManager");
  auto *diagnostics=window->findChild<QQuickItem*>("fingerprintDiagnostics");
  auto *symbol=window->findChild<QQuickItem*>("fingerprintSymbol");
  bool safe=toggle && enroll && test && !toggle->isEnabled() && !enroll->isEnabled() && !test->isEnabled() && !toggle->property("checked").toBool();
  safe &= count && count->property("text").toString()=="Unknown" && fits(window->contentItem(),window->width());
  safe &= symbol && symbol->property("status").toInt()==1;
  if(diagnostics) { diagnostics->forceActiveFocus();QMetaObject::invokeMethod(diagnostics,"clicked"); }
  safe &= manager && manager->property("diagnosticsOpen").toBool();
  // Simulate loss of the read-only diagnostic owner in this isolated fixture.
  control.insert("state",QVariantMap{{"ready",false}});
  safe &= manager && manager->property("health").toString()=="Service unavailable";
  if(diagnostics)QMetaObject::invokeMethod(diagnostics,"clicked");
  // Restore only diagnostic data for the screenshot; never a match or enrollment.
  control.insert("state",initialState);
  auto image=window->grabWindow();
  bool saved=image.save(QString(argv[1])+"/tests/ui/preview-"+argv[2]+(dark?"-dark":"-light")+".png");
  if(!safe)qWarning()<<"Failed UI checks"<<toggle<<enroll<<test<<count<<manager<<diagnostics<<(manager?manager->property("health"):QVariant());
  app.exit(safe && saved && !warnings ? 0:4);
 });
 return app.exec();
}
