#include <QCoreApplication>
#include <QFile>
#include <cstdio>
int main(int argc,char **argv){QCoreApplication app(argc,argv);if(argc!=2)return 1;QFile f(QString(":/qml/")+QString::fromLocal8Bit(argv[1]));if(!f.open(QIODevice::ReadOnly))return 2;const auto bytes=f.readAll();return std::fwrite(bytes.constData(),1,bytes.size(),stdout)==size_t(bytes.size())?0:3;}
