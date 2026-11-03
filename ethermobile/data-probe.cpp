// Explicit hardware acceptance client. Never reads or changes APN secrets.
#include "mobile.h"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <cstdio>

int main(int argc,char **argv){
    QCoreApplication app(argc,argv);Mobile mobile;
    const bool start=app.arguments().contains("--connect"),stop=app.arguments().contains("--disconnect");
    bool requested=false;int seconds=0;
    QTimer timer;
    QObject::connect(&timer,&QTimer::timeout,&app,[&]{
        ++seconds;auto status=mobile.snapshot();
        if(seconds>=4&&!requested&&(start||stop)&&status.value("dataProvider")=="downstream-ipa"){
            requested=true;
            if(stop)mobile.disconnectData();
            else{QString path;for(const auto &v:mobile.profiles())if(v.toMap().value("apn").toString()=="giffgaff.com"){path=v.toMap().value("path").toString();break;}mobile.connectProfile(path);}
        }
        const auto output=QJsonObject{{"status",QJsonObject::fromVariantMap(status)},{"operation",QJsonObject::fromVariantMap(mobile.operation())},{"busy",mobile.busy()}};
        printf("%s\n",QJsonDocument(output).toJson(QJsonDocument::Compact).constData());fflush(stdout);
        if((!start&&!stop&&seconds>=5)||(requested&&!mobile.busy()&&seconds>=6)||seconds>175){
            const bool expected=!start&&!stop?status.value("dataProvider")=="downstream-ipa":start?status.value("dataActive").toBool():!status.value("dataActive").toBool()&&!status.value("dataPending").toBool();
            app.exit(expected?0:1);
        }
    });timer.start(1000);return app.exec();
}
