#include "audio.h"
#include <QJsonDocument>
#include <QJsonArray>
#include <QTimer>
#include <QStandardPaths>
#include <QJsonObject>
Audio::Audio(QObject *parent):QObject(parent){}
void Audio::run(const QStringList &args,std::function<void(int,QByteArray)> done){
    auto p=new QProcess(this);
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[p,done](int code,QProcess::ExitStatus){auto data=p->readAllStandardOutput();if(code)data=p->readAllStandardError();done(code,data);p->deleteLater();});
    connect(p,&QProcess::errorOccurred,this,[p,done](QProcess::ProcessError e){if(e==QProcess::FailedToStart){done(-1,p->errorString().toUtf8());p->deleteLater();}});
    QTimer::singleShot(8000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});p->start("pactl",args);
}
void Audio::refresh(){
    if(refreshing)return;refreshing=true;pending=4;
    for(const auto &kind:QStringList{"sinks","sources","cards"})run({"--format=json","list",kind},[this,kind](int code,QByteArray bytes){
        QVariantList result;if(!code){auto document=QJsonDocument::fromJson(bytes);if(document.isArray())result=document.array().toVariantList();else status="Audio server returned an unsupported response.";}else status="Audio server unavailable: "+QString::fromUtf8(bytes).left(300);
        if(kind=="sinks")outputs=result;else if(kind=="sources")inputs=result;else cards=result;
        if(--pending==0)refreshing=false;emit changed();
    });
    run({"info"},[this](int code,QByteArray bytes){status=code?"Audio server unavailable: "+QString::fromUtf8(bytes).left(300):QString::fromUtf8(bytes).section('\n',0,13);if(--pending==0)refreshing=false;emit changed();});
}
void Audio::mutate(const QStringList &args){
    if(!QStandardPaths::findExecutable("etheraudio").isEmpty()){
        QString action,target;QJsonObject values;const auto verb=args.value(0);
        if(verb=="set-default-sink"||verb=="set-default-source"){action="select";target=verb.mid(12);values["name"]=args.value(1);}
        else if(verb=="set-sink-volume"){action="volume";target="sink";values["id"]=args.value(1);auto percent=args.value(2);percent.remove('%');values["percent"]=percent.toInt();}
        else if(verb=="set-sink-mute"){action="mute";target="sink";values["id"]=args.value(1);values["muted"]=args.value(2)=="1";}
        else if(verb=="set-card-profile"){action="card-profile";target=args.value(1);values["profile"]=args.value(2);}
        if(action.isEmpty()){status="Unsupported managed audio action";emit changed();return;}
        auto *p=new QProcess(this);connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int code,QProcess::ExitStatus){if(code){status=QString::fromUtf8(p->readAllStandardError()).left(1000);emit changed();}else refresh();p->deleteLater();});
        connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){status="EtherAudio helper unavailable";emit changed();p->deleteLater();}});
        QTimer::singleShot(45000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});
        p->start("etheraudio",{"command",action,target,QString::fromUtf8(QJsonDocument(values).toJson(QJsonDocument::Compact))});return;
    }
    run(args,[this](int code,QByteArray bytes){if(code){status=QString::fromUtf8(bytes).left(1000);emit changed();}else refresh();});
}
void Audio::select(const QString &kind,const QString &name){
    const auto list=kind=="output"?outputs:inputs;
    for(auto entry:list)if(entry.toMap().value("name").toString()==name){mutate({kind=="output"?"set-default-sink":"set-default-source",name});return;}
}
void Audio::volume(const QString &name,int percent){for(auto entry:outputs)if(entry.toMap().value("name").toString()==name){mutate({"set-sink-volume",name,QString::number(qBound(0,percent,100))+"%"});return;}}
void Audio::mute(const QString &name,bool enabled){for(auto entry:outputs)if(entry.toMap().value("name").toString()==name){mutate({"set-sink-mute",name,enabled?"1":"0"});return;}}
void Audio::profile(const QString &card,const QString &profile){
    for(auto entry:cards){auto c=entry.toMap();if(c.value("name").toString()!=card)continue;auto p=c.value("profiles").toMap();auto available=p[profile].toMap().value("available");if(p.contains(profile)&&available.toString()!="no"&&available.toString()!="false")mutate({"set-card-profile",card,profile});}
}
void Audio::controlPanel(){if(!QProcess::startDetached("pavucontrol",{})){status="Install pavucontrol to use advanced audio routing.";emit changed();}}
