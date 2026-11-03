#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickImageProvider>
#include <QTimer>
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QDateTime>
class Fixture:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap banner READ banner NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 QVariantMap m_state,m_banner;
 Fixture(){
  QVariantList cards;
  for(int i=0;i<5;++i)cards.append(QVariantMap{{"id",i+1},{"appId",i<3?"ethersms-verified":"etherpower-verified"},{"appName",i<3?"EtherSMS":"EtherPower"},{"groupKey",i<3?"sms:conversation":"power:system"},{"title",i<3?"New message from a contact":"Battery warning"},{"body","A plain-text preview with a longer sentence to check wrapping at narrow phone widths."},{"icon","mail-unread"},{"timestamp",QDateTime::currentSecsSinceEpoch()},{"active",true},{"read",i==0},{"persistent",i>=3},{"priority",i<3?2:3},{"actions",QVariantList{QVariantMap{{"key","default"},{"label","Open"}},QVariantMap{{"key","mark-read"},{"label","Mark as read"}}}}});
  QVariantMap schedule{{"enabled",false},{"start",1320},{"end",420},{"days",QVariantList{0,1,2,3,4}}};
  QVariantMap config{{"enabled",true},{"silent",true},{"dnd","off"},{"manualDnd",false},{"lockPrivacy","sensitive"},{"retentionDays",7},{"apps",QVariantMap{}},{"schedule",schedule}};
  m_state={{"ready",true},{"cards",cards},{"unread",4},{"locked",false},{"dnd","off"},{"config",config}};
  m_banner=cards[0].toMap();
 }
 QVariantMap state()const{return m_state;}QVariantMap banner()const{return m_banner;}QString message()const{return {};}
 Q_INVOKABLE void command(const QString&,uint=0,const QVariantMap& ={}){}
 Q_INVOKABLE void configure(const QVariantMap&){}
 Q_INVOKABLE void appPolicy(const QString&,const QVariantMap&){}
 Q_INVOKABLE void nextBanner(){}
 Q_INVOKABLE void configureWindow(QObject*,const QString&,int=0){}
signals:void changed();
};
class Images:public QQuickImageProvider{public:Images():QQuickImageProvider(Pixmap){}QPixmap requestPixmap(const QString&,QSize*s,const QSize&size)override{QPixmap p(size.isValid()?size:QSize(24,24));p.fill(QColor("#3878d0"));if(s)*s=p.size();return p;}};
int main(int argc,char**argv){
 qputenv("QT_QUICK_BACKEND","software");qputenv("QT_QUICK_CONTROLS_STYLE","Basic");qputenv("QT_ENABLE_HIGHDPI_SCALING","0");
 QGuiApplication app(argc,argv);Fixture fixture;QQmlApplicationEngine engine;QStringList errors;
 QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[&](const QList<QQmlError>&list){for(auto e:list){if(!e.toString().contains("QML Settings:"))errors<<e.toString();}});
 engine.rootContext()->setContextProperty("Notifications",&fixture);engine.rootContext()->setContextProperty("Core",&fixture);engine.addImageProvider("icons",new Images);
 engine.load(QUrl("qrc:/tests/ui-test.qml"));if(engine.rootObjects().isEmpty())return 2;
 auto*w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());const auto args=app.arguments();w->setWidth(args.value(1,"360").toInt());w->setHeight(args.value(2,"900").toInt());
 w->setProperty("unit",args.value(5,"1").toDouble());
 if(args.value(4)=="settings")w->setProperty("settingsMode",true);
 if(args.value(4)=="banner")w->setProperty("bannerMode",true);
 QTimer::singleShot(1200,&app,[&]{
  auto filename=args.value(3,"notification-ui.png");auto *capture=args.value(4)=="banner"?w->findChild<QQuickWindow*>("notificationBanner"):w;bool ok=capture&&capture->grabWindow().save(filename);
  QFile log(filename+".json");if(log.open(QIODevice::WriteOnly))log.write(QJsonDocument::fromVariant(QVariantMap{{"errors",errors},{"width",w->width()},{"height",w->height()},{"saved",ok}}).toJson());
  app.exit(ok&&errors.isEmpty()?0:3);
 });
 return app.exec();
}
#include "ui-test.moc"
