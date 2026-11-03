#include "distributor.h"
#include <QCoreApplication>
#include <QTemporaryDir>
#include <QStandardPaths>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <cstdio>
int main(int argc,char **argv){
 QTemporaryDir temp;if(!temp.isValid())return 1;
 qputenv("XDG_CACHE_HOME",temp.path().toUtf8());QCoreApplication app(argc,argv);
 const QString folder=QStandardPaths::writableLocation(QStandardPaths::CacheLocation)+"/ethershell";QDir().mkpath(folder);
 QFile cache(folder+"/catalog.json");if(!cache.open(QIODevice::WriteOnly))return 2;
 // A catalogue predating EtherLocation, with a real-shaped cached release.
 QJsonObject old{{"name","EtherHardware"},{"family","etherhardware"},{"variants",QJsonArray{QJsonObject{{"slug","etherhardware-linux-arm64"},{"version","0.1.0"}}}}};
 cache.write(QJsonDocument(QJsonObject{{"schema",1},{"catalog",QJsonArray{old}}}).toJson());cache.close();
 bool preserved=false,newFamily=false,maps=false;
 {Distributor distributor;for(auto v:distributor.catalog()){auto row=v.toMap();if(row["family"]=="etherhardware")preserved=row["variants"].toList().size()==1;if(row["family"]=="etherlocation")newFamily=true;if(row["family"]=="ethermap")maps=true;}}
 // No event loop: pending catalogue HTTP calls are destroyed without delivery.
 if(!preserved||!newFamily||!maps)return 3;std::puts("PASS: existing cached releases survive EtherLocation and EtherMAP catalogue families");return 0;
}
