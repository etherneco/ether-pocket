#include "speech.h"
#include <QStandardPaths>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QDataStream>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <cmath>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <sys/resource.h>
Speech::Speech(QObject *parent):ISpeechRecognizer(parent){
 m_recognizer.setChildProcessModifier([]{struct rlimit memory{3ULL*1024*1024*1024,3ULL*1024*1024*1024};setrlimit(RLIMIT_AS,&memory);struct rlimit cpu{300,300};setrlimit(RLIMIT_CPU,&cpu);});
 m_models=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/models";QDir().mkpath(m_models);
 connect(&m_sources,&QProcess::finished,this,[this](int code,QProcess::ExitStatus){
  if(m_state!="Checking microphone")return;
  const auto sources=QJsonDocument::fromJson(m_sources.readAllStandardOutput()).array();m_sources.readAllStandardError();
  QString selected;
  for(const auto &source:sources){const auto object=source.toObject();const auto name=object.value("name").toString();
   // Never record the speaker monitor in place of a microphone.
   const auto monitor=object.value("monitor_of_sink");const bool isMonitor=name.endsWith(".monitor")||(!monitor.isNull()&&!monitor.isUndefined()&&monitor.toVariant().toString()!="4294967295");
   if(!isMonitor&&!name.isEmpty()&&(m_device.isEmpty()||m_device==name)){selected=name;break;}
  }
  if(code!=0||selected.isEmpty()){fail("No microphone source available. Speaker monitor capture is disabled.");return;}
  m_state="Recording";emit changed();
  if(!QStandardPaths::findExecutable("etheraudio").isEmpty())m_capture.start("etheraudio",{"capture","--consent","--seconds","60","--purpose","EtherSMS user-requested dictation","--source",selected});
  else m_capture.start("parec",{"--raw","--format=s16le","--rate=16000","--channels=1","--device="+selected});
  m_limit.start(60000);
 });
 connect(&m_sources,&QProcess::errorOccurred,this,[this](QProcess::ProcessError e){if(e==QProcess::FailedToStart)fail("Microphone discovery unavailable");});
 connect(&m_capture,&QProcess::readyReadStandardOutput,this,&Speech::consume);
 connect(&m_capture,&QProcess::readyReadStandardError,this,[this]{m_capture.readAllStandardError();});
 connect(&m_capture,&QProcess::errorOccurred,this,[this](QProcess::ProcessError e){if(e==QProcess::FailedToStart)fail("Microphone capture could not start");});
 connect(&m_capture,&QProcess::finished,this,[this](int,QProcess::ExitStatus){consume();m_limit.stop();if(m_stopping){m_stopping=false;recognize();}else if(m_state=="Recording")fail("Microphone disconnected or capture interrupted");});
 connect(&m_recognizer,&QProcess::readyReadStandardOutput,this,[this]{m_recognizer.readAllStandardOutput();});
 connect(&m_recognizer,&QProcess::readyReadStandardError,this,[this]{m_recognizer.readAllStandardError();});
 connect(&m_recognizer,&QProcess::errorOccurred,this,[this](QProcess::ProcessError e){if(e==QProcess::FailedToStart)fail("Offline recognition executable unavailable");});
 connect(&m_recognizer,&QProcess::finished,this,[this](int code,QProcess::ExitStatus status){
  m_deadline.stop();if(m_state!="Processing")return;
  QFile f(m_temp.path()+"/transcript.txt");if(code!=0||status!=QProcess::NormalExit||!f.open(QIODevice::ReadOnly)){fail("Offline transcription failed; check the installed multilingual model");return;}
  auto text=QString::fromUtf8(f.read(64000)).trimmed();f.close();f.remove();QFile::remove(m_temp.path()+"/capture.wav");
  if(text.isEmpty()){fail("No speech recognized");return;}m_state="Transcription ready";emit changed();emit transcribed(text);
 });
 m_limit.setSingleShot(true);connect(&m_limit,&QTimer::timeout,this,&Speech::stop);
 m_deadline.setSingleShot(true);connect(&m_deadline,&QTimer::timeout,this,[this]{fail("Recognition exceeded five minutes; try a smaller model");m_recognizer.kill();});
}
Speech::~Speech(){cancel();m_capture.waitForFinished(1000);m_recognizer.waitForFinished(1000);m_sources.waitForFinished(1000);}
bool Speech::available()const{return !QStandardPaths::findExecutable("parec").isEmpty()&&!QStandardPaths::findExecutable("whisper-cli").isEmpty()&&!models().isEmpty();}
QVariantList Speech::models()const{QVariantList out;for(const auto &f:QDir(m_models).entryInfoList({"*.bin"},QDir::Files))out<<QVariantMap{{"name",f.fileName()},{"bytes",f.size()},{"languages","Polish / English / Auto (multilingual models only)"}};return out;}
void Speech::fail(const QString &s){m_state=s;m_pcm.clear();m_level=0;emit changed();}
void Speech::start(const QString &language,const QString &model,const QString &device){
 if(m_capture.state()!=QProcess::NotRunning||m_recognizer.state()!=QProcess::NotRunning||m_sources.state()!=QProcess::NotRunning)return;
 if(!available()||!QFile::exists(m_models+"/"+QFileInfo(model).fileName())){fail("Install whisper-cli and a verified multilingual model in Settings");return;}
 if(language!="pl"&&language!="en"&&language!="auto"){fail("Unsupported language");return;}
 m_language=language;m_model=m_models+"/"+QFileInfo(model).fileName();m_pcm.clear();m_stopping=false;
 m_device=device;m_state="Checking microphone";emit changed();m_sources.start("pactl",{"-f","json","list","sources"});
 QTimer::singleShot(5000,this,[this]{if(m_state=="Checking microphone"){fail("Microphone discovery timed out");m_sources.kill();}});
}
void Speech::consume(){auto data=m_capture.readAllStandardOutput();if(m_state!="Recording")return;
 m_pcm+=data;double sum=0;for(qsizetype i=0;i+1<data.size();i+=2){auto sample=qint16(quint8(data[i])|(quint16(quint8(data[i+1]))<<8));sum+=double(sample)*sample;}
 m_level=data.size()>1?std::sqrt(sum/(data.size()/2))/32768.:0;emit changed();if(m_pcm.size()>1920000)stop();
}
void Speech::stop(){if(m_state!="Recording"||m_stopping)return;m_stopping=true;m_capture.terminate();QTimer::singleShot(1000,this,[this]{if(m_stopping&&m_capture.state()!=QProcess::NotRunning)m_capture.kill();});}
void Speech::recognize(){
 if(m_pcm.size()<8000){fail("Recording too short or empty");return;}
 // Reject silence to avoid hallucinated transcriptions.
 int peak=0;for(qsizetype i=0;i+1<m_pcm.size();i+=2)peak=qMax(peak,qAbs(int(qint16(quint8(m_pcm[i])|(quint16(quint8(m_pcm[i+1]))<<8)))));
 if(peak<150){fail("No microphone signal detected");return;}
 QFile f(m_temp.path()+"/capture.wav");if(!f.open(QIODevice::WriteOnly)){fail("Cannot create private recording");return;}
 QDataStream w(&f);w.setByteOrder(QDataStream::LittleEndian);w.writeRawData("RIFF",4);w<<quint32(36+m_pcm.size());w.writeRawData("WAVEfmt ",8);w<<quint32(16)<<quint16(1)<<quint16(1)<<quint32(16000)<<quint32(32000)<<quint16(2)<<quint16(16);w.writeRawData("data",4);w<<quint32(m_pcm.size());w.writeRawData(m_pcm.constData(),m_pcm.size());f.close();m_pcm.clear();
 QFile::remove(m_temp.path()+"/transcript.txt");m_state="Processing";m_level=0;emit changed();
 m_recognizer.start("whisper-cli",{"-m",m_model,"-f",f.fileName(),"-l",m_language,"-t","4","-otxt","-of",m_temp.path()+"/transcript","-nt"});m_deadline.start(300000);
}
void Speech::cancel(){m_stopping=false;m_limit.stop();m_deadline.stop();m_state="Ready";m_sources.kill();m_capture.kill();m_recognizer.kill();m_pcm.clear();m_level=0;QFile::remove(m_temp.path()+"/capture.wav");QFile::remove(m_temp.path()+"/transcript.txt");emit changed();}
