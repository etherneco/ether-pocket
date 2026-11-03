#include "settings.h"
#include <QStandardPaths>
#include <QFileInfo>
#include <QDir>
SmsSettings::SmsSettings(QObject *parent):QObject(parent),m_settings("Etherneco","EtherSMS"){
 connect(&m_probe,&QProcess::finished,this,[this](int code,QProcess::ExitStatus){m_diagnostics["microphones"]=code==0?QString::fromUtf8(m_probe.readAllStandardOutput()).trimmed():"PulseAudio source discovery unavailable";m_probe.readAllStandardError();emit changed();});connect(&m_model,&QProcess::finished,this,[this](int code,QProcess::ExitStatus){m_model.readAllStandardOutput();m_model.readAllStandardError();m_diagnostics["modelOperation"]=code==0?"Model operation completed":"Model operation failed: check filename, checksum, permissions or active model";m_diagnostics["models"]=QDir(QDir::homePath()+"/.local/share/Etherneco/EtherSMS/models").entryList({"*.bin"},QDir::Files).join(", ");emit changed();});refresh();
}
QVariantMap SmsSettings::values()const{
 QVariantMap v{{"notifications",true},{"preview","sender"},{"deliveryReports",false},{"confirmSend",true},{"dictation",true},{"language","pl"},{"microphone",""},{"speechModel","ggml-base.bin"},{"aiEnabled",false},{"aiModel",""},{"ttsEnabled",false},{"ttsVoice","pl"},{"ttsRate",165},{"outputDevice",""}};
 for(auto it=v.begin();it!=v.end();++it)it.value()=m_settings.value(it.key(),it.value());
 return v;
}
void SmsSettings::set(const QString &key,const QVariant &v){
 const auto defaults=values();if(!defaults.contains(key))return;
 if(key=="language"&&!QStringList{"pl","en","auto"}.contains(v.toString()))return;
 if(key=="preview"&&!QStringList{"full","sender","hidden"}.contains(v.toString()))return;
 if(key=="ttsVoice"&&!QStringList{"pl","en"}.contains(v.toString()))return;
 if(key=="ttsRate"&&(v.toInt()<80||v.toInt()>300))return;
 if(v.toString().size()>512)return;
 m_settings.setValue(key,v);m_settings.sync();emit changed();
}
void SmsSettings::refresh(){
 m_settings.sync();
 m_diagnostics={{"speechEngine",QStandardPaths::findExecutable("whisper-cli").isEmpty()?"Not installed":"whisper.cpp (offline)"},
 {"tts",QStandardPaths::findExecutable("espeak-ng").isEmpty()?"Not installed":"eSpeak NG"},
 {"audioCapture",QStandardPaths::findExecutable("parec").isEmpty()?"Unavailable":"PulseAudio / PipeWire compatibility"},
 {"models",QDir(QDir::homePath()+"/.local/share/Etherneco/EtherSMS/models").entryList({"*.bin"},QDir::Files).join(", ")},{"modelDirectory",QDir::homePath()+"/.local/share/Etherneco/EtherSMS/models"},
 {"aiEndpoint","http://127.0.0.1:11434 (Ollama; connection checked on request)"},
 {"microphones","Reading…"}};
 if(m_probe.state()==QProcess::NotRunning)m_probe.start("pactl",{"list","short","sources"});
 emit changed();
}

void SmsSettings::launch(){QProcess::startDetached("ethersms",{});}
void SmsSettings::installModel(const QString &source,const QString &sha){if(m_model.state()==QProcess::NotRunning)m_model.start("/usr/libexec/ethersms/ethersms-model",{"install",source,sha});}
void SmsSettings::removeModel(const QString &name){if(m_model.state()==QProcess::NotRunning)m_model.start("/usr/libexec/ethersms/ethersms-model",{"remove",name});}

SmsSettings::~SmsSettings(){m_probe.kill();m_model.kill();m_probe.waitForFinished(1000);m_model.waitForFinished(1000);}

void SmsSettings::downloadModel(const QString &variant,const QString &sha){if(m_model.state()==QProcess::NotRunning)m_model.start("/usr/libexec/ethersms/ethersms-model",{"download",variant,sha,"--approved"});}
