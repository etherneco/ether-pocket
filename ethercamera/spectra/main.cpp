#include "transport.h"
#include <QCoreApplication>
#include <QJsonObject>
#include <QJsonArray>
#include <QJsonDocument>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <sys/utsname.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <stdexcept>
#include <system_error>

QString text(const QString &path){QFile file(path);if(!file.open(QIODevice::ReadOnly))throw std::runtime_error("Cannot read "+path.toStdString());return QString::fromUtf8(file.readAll()).remove(QChar('\0')).trimmed();}
int openNode(const QString &node,const QString &expected){
 const QString leaf=QFileInfo(node).fileName();
 if(text("/sys/class/video4linux/"+leaf+"/name")!=expected)throw std::runtime_error("Wrong camera node role");
 const int fd=::open(node.toLocal8Bit().constData(),O_RDWR|O_CLOEXEC|O_NONBLOCK|O_NOFOLLOW);
 if(fd<0)throw std::system_error(errno,std::generic_category(),"Open "+node.toStdString());
 struct stat st{};const auto dev=text("/sys/class/video4linux/"+leaf+"/dev").split(':');
 if(fstat(fd,&st)||!S_ISCHR(st.st_mode)||dev.size()!=2||major(st.st_rdev)!=dev[0].toUInt()||minor(st.st_rdev)!=dev[1].toUInt()){
  ::close(fd);throw std::runtime_error("Camera identity changed while opening");
 }return fd;
}
QString findNode(const QString &name){
 QString found;
 for(const auto &leaf:QDir("/sys/class/video4linux").entryList(QDir::Dirs|QDir::NoDotAndDotDot)){
  if(text("/sys/class/video4linux/"+leaf+"/name")==name){if(!found.isEmpty())throw std::runtime_error("Ambiguous camera node role");found="/dev/"+leaf;}
 }if(found.isEmpty())throw std::runtime_error("Required Spectra node absent");return found;
}
// CRM close calls ALL vendor subdevice close callbacks in this downstream
// kernel. Refuse to run while any process owns a camera node. The kernel
// additionally enforces single-open CRM; no Android HAL is started here.
void requireIdle(){
 for(const auto &pid:QDir("/proc").entryList(QDir::Dirs|QDir::NoDotAndDotDot)){
  bool ok=false;pid.toInt(&ok);if(!ok||pid==QString::number(getpid()))continue;
  QDir fds("/proc/"+pid+"/fd");
  for(const auto &file:fds.entryList(QDir::AllEntries|QDir::NoDotAndDotDot)){
   const auto target=QFileInfo(fds.filePath(file)).symLinkTarget();
   if(target.startsWith("/dev/video")||target.startsWith("/dev/v4l-subdev")||target.startsWith("/dev/media"))throw std::runtime_error("Another process owns a camera/media node");
  }
 }
}
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);int crm=-1,isp=-1,sensor=-1;
 try{
  const bool rear=app.arguments()==QStringList{app.arguments()[0],"--probe-rear-imx586"};
  if(!rear&&app.arguments()!=QStringList{app.arguments()[0],"--transport-self-test"})throw std::runtime_error("Usage: ethercamera-spectra --transport-self-test | --probe-rear-imx586 (no frame capture)");
  struct utsname kernel{};if(uname(&kernel)||QString(kernel.release)!="4.14.117-perf"||QString(kernel.machine)!="aarch64"||text("/proc/device-tree/model")!="SDX50M MTP 18827 15")throw std::runtime_error("Unsupported board/kernel; do not send private camera ioctls");
  if(geteuid()!=0)throw std::runtime_error("Run the bounded bring-up test through the root device test harness");
  requireIdle();const auto crmNode=findNode("cam-req-mgr"),ispNode=findNode("cam-isp");
  crm=openNode(crmNode,"cam-req-mgr");isp=openNode(ispNode,"cam-isp");
  spectra::Transport request(crm),image(isp);const auto caps=image.queryIsp();
  QJsonArray hardware;for(int i=0;i<caps.num_dev;i++){const auto &d=caps.dev_caps[i];hardware.append(QJsonObject{{"type",int(d.hw_type)},{"major",int(d.hw_version.major)},{"minor",int(d.hw_version.minor)},{"increment",int(d.hw_version.incr)}});}
  {
   spectra::Session session(request);
   for(int cycle=0;cycle<3;cycle++){
    spectra::Buffer buffer(request,4096);auto *bytes=static_cast<uint8_t*>(buffer.data());
    for(size_t i=0;i<buffer.size();i++)bytes[i]=uint8_t((i+cycle)&255);
    for(size_t i=0;i<buffer.size();i++)if(bytes[i]!=uint8_t((i+cycle)&255))throw std::runtime_error("Command memory verification failed");
    buffer.close();
   }session.close();
  }
  if(rear){
   for(const auto &leaf:QDir("/sys/class/video4linux").entryList(QDir::Dirs|QDir::NoDotAndDotDot)){
    if(text("/sys/class/video4linux/"+leaf+"/name")!="cam-sensor-driver")continue;
    int candidate=openNode("/dev/"+leaf,"cam-sensor-driver");spectra::Transport node(candidate);cam_sensor_query_cap c{};
    try{c=node.querySensor();}catch(...){::close(candidate);throw;}
    if(c.slot_info==0){sensor=candidate;break;}::close(candidate);
   }
   if(sensor<0)throw std::runtime_error("Rear-main sensor slot absent");
   spectra::Transport node(sensor);spectra::probeRearImx586(request,node);
   ::close(sensor);sensor=-1;
  }
  ::close(isp);isp=-1;::close(crm);crm=-1;
  QJsonObject result{{"schemaVersion",1},{"transportVerified",true},{"ispCapabilities",hardware},{"deviceIommu",caps.device_iommu.non_secure},{"cdmIommu",caps.cdm_iommu.non_secure},{"bufferCycles",3},{"sessionReleased",true},{"physicalFrameVerified",false},{"sensorCommandsSent",false},{"captureImplemented",false}};
  result["sensorCommandsSent"]=rear;result["sensorIdentityMatchedByKernel"]=rear;
  if(rear){result["sensorId"]=int(0x586);result["slot"]=0;result["moduleVendorIdentified"]=false;result["sensorPoweredDown"]=true;}
  std::puts(QJsonDocument(result).toJson().constData());return 0;
 }catch(const std::exception &e){if(sensor>=0)::close(sensor);if(isp>=0)::close(isp);if(crm>=0)::close(crm);std::fprintf(stderr,"Spectra bring-up: %s\n",e.what());return 1;}
}
