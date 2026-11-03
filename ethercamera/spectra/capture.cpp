// Native rear-main RAW10 acquisition on the exact downstream SM8150 ABI.
// No vendor HAL, motor, actuator, EEPROM programming or kernel replacement.
#include "transport.h"
#include "image.h"
#include <media/cam_sync.h>
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <sys/ioctl.h>
#include <sys/utsname.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <memory>
#include <functional>
#include <cstring>
#include <cstdio>
#include <system_error>
#include <csignal>
#include <chrono>
#include <cmath>

using spectra::Buffer;using spectra::Transport;
namespace {
volatile std::sig_atomic_t stopping=0;
void stopped(int){stopping=1;}
void writeAll(int fd,const void *data,size_t size){auto *p=static_cast<const uint8_t*>(data);while(size){ssize_t n=::write(fd,p,size);if(n<0&&errno==EINTR){if(stopping)return;continue;}if(n<=0)throw std::system_error(errno,std::generic_category(),"Frame output");p+=n;size-=n;}}

size_t aligned(size_t n){return (n+4095)&~size_t(4095);}
void stage(const char *text){std::fprintf(stderr,"Spectra: %s\n",text);}
QString read(const QString &path){QFile f(path);if(!f.open(QIODevice::ReadOnly))throw std::runtime_error("Cannot read "+path.toStdString());return QString::fromUtf8(f.readAll()).remove(QChar('\0')).trimmed();}
struct Fd {int fd=-1;explicit Fd(int n=-1):fd(n){}~Fd(){if(fd>=0)::close(fd);}Fd(const Fd&)=delete;Fd&operator=(const Fd&)=delete;};
int openRole(const QString &leaf,const QString &role){
 if(read("/sys/class/video4linux/"+leaf+"/name")!=role)throw std::runtime_error("Device role changed");
 int fd=::open(("/dev/"+leaf).toLocal8Bit(),O_RDWR|O_CLOEXEC|O_NONBLOCK|O_NOFOLLOW);
 if(fd<0)throw std::system_error(errno,std::generic_category(),"Open "+leaf.toStdString());return fd;
}
int role(const QString &name){for(const auto &leaf:QDir("/sys/class/video4linux").entryList(QDir::Dirs|QDir::NoDotAndDotDot))if(read("/sys/class/video4linux/"+leaf+"/name")==name)return openRole(leaf,name);throw std::runtime_error("Missing "+name.toStdString());}
int slot(const QString &name,uint32_t wanted,bool sensor){
 for(const auto &leaf:QDir("/sys/class/video4linux").entryList(QDir::Dirs|QDir::NoDotAndDotDot)){
  if(read("/sys/class/video4linux/"+leaf+"/name")!=name)continue;
  int fd=openRole(leaf,name);Transport transport(fd);
  try{uint32_t index;if(sensor){auto c=transport.querySensor();index=c.slot_info;if(index==wanted&&(c.pos_yaw!=180||c.csiphy_slot_id!=1))throw std::runtime_error("Not the rear main sensor");}
   else{cam_csiphy_query_cap caps{};transport.control(CAM_QUERY_CAP,&caps,sizeof(caps));index=caps.slot_info;}
   if(index==wanted)return fd;
  }catch(...){::close(fd);throw;}::close(fd);
 }throw std::runtime_error("Required rear camera slot absent");
}
void syncCall(int fd,uint32_t id,void *payload,uint32_t size){
 cam_private_ioctl_arg arg{};arg.id=id;arg.size=size;arg.ioctl_ptr=reinterpret_cast<uintptr_t>(payload);
 if(ioctl(fd,CAM_PRIVATE_IOCTL_CMD,&arg)<0)throw std::system_error(errno,std::generic_category(),"Camera sync ioctl "+std::to_string(id));
 if(int32_t(arg.result))throw std::runtime_error("Camera sync result "+std::to_string(int32_t(arg.result)));
}
struct Device {
 Transport &transport;int32_t session,handle=-1;bool started=false;
 Device(Transport &t,int32_t s,void *resources=nullptr,uint32_t count=0):transport(t),session(s){
  cam_acquire_dev_cmd cmd{};cmd.session_handle=s;cmd.handle_type=CAM_HANDLE_USER_POINTER;cmd.num_resources=count;cmd.resource_hdl=reinterpret_cast<uintptr_t>(resources);
  transport.control(CAM_ACQUIRE_DEV,&cmd,sizeof(cmd));handle=cmd.dev_handle;if(handle<=0)throw std::runtime_error("Invalid device handle");
 }
 void config(Buffer &packet){cam_config_dev_cmd cmd{};cmd.session_handle=session;cmd.dev_handle=handle;cmd.packet_handle=packet.handle();transport.control(CAM_CONFIG_DEV,&cmd,sizeof(cmd));}
 void operation(uint32_t op){cam_start_stop_dev_cmd cmd{};cmd.session_handle=session;cmd.dev_handle=handle;transport.control(op,&cmd,sizeof(cmd));}
 void start(){operation(CAM_START_DEV);started=true;}
 void close(){if(handle<0)return;if(started){started=false;operation(CAM_STOP_DEV);}operation(CAM_RELEASE_DEV);handle=-1;}
 ~Device(){try{close();}catch(const std::exception &e){std::fprintf(stderr,"Device cleanup: %s\n",e.what());}}
};
struct Fence {int fd;int32_t id=0;explicit Fence(int descriptor):fd(descriptor){cam_sync_info cmd{};std::strcpy(cmd.name,"EtherCamera rear RAW output");syncCall(fd,CAM_SYNC_CREATE,&cmd,sizeof(cmd));id=cmd.sync_obj;if(id<=0)throw std::runtime_error("Invalid camera fence");}
 void wait(){cam_sync_wait cmd{};cmd.sync_obj=id;cmd.timeout_ms=5000;syncCall(fd,CAM_SYNC_WAIT,&cmd,sizeof(cmd));}
 ~Fence(){if(!id)return;try{cam_sync_info cmd{};cmd.sync_obj=id;syncCall(fd,CAM_SYNC_DESTROY,&cmd,sizeof(cmd));}catch(const std::exception &e){std::fprintf(stderr,"Fence cleanup: %s\n",e.what());}}
};
struct Guard {std::function<void()> cleanup;~Guard(){cleanup();}};
cam_packet *packet(Buffer &b,uint32_t opcode,uint64_t request,uint32_t commands){
 auto *p=static_cast<cam_packet*>(b.data());p->header.op_code=opcode;p->header.request_id=request;
 p->header.size=sizeof(cam_packet)+commands*sizeof(cam_cmd_buf_desc);p->num_cmd_buf=commands;p->kmd_cmd_buf_index=uint32_t(-1);return p;
}
void descriptor(cam_cmd_buf_desc &d,Buffer &b,uint32_t bytes,uint32_t type,uint32_t meta=0){d.mem_handle=b.handle();d.length=bytes;d.size=b.size();d.type=type;d.meta_data=meta;}
void sensorSettings(Transport &crm,Device &sensor,const QJsonArray &settings,uint32_t opcode){
 for(int offset=0;offset<settings.size();offset+=256){
  std::vector<spectra::Register> registers;
  for(int i=offset;i<qMin(offset+256,int(settings.size()));i++){auto row=settings[i].toArray();if(row.size()!=3||row[2].toInt()!=0)throw std::runtime_error("Unsupported sensor table delay");registers.push_back({uint32_t(row[0].toInt()),uint32_t(row[1].toInt())});}
  auto encoded=spectra::encodeI2c(registers,2,1);Buffer commands(crm,aligned(encoded.size())),control(crm,4096);std::memcpy(commands.data(),encoded.data(),encoded.size());
  auto *p=packet(control,opcode,0,1);auto *d=reinterpret_cast<cam_cmd_buf_desc*>(&p->payload);descriptor(*d,commands,encoded.size(),CAM_CMD_BUF_I2C);sensor.config(control);
 }
}
QJsonObject profile(const QString &path){
 QFile file(path);if(!file.open(QIODevice::ReadOnly)||file.size()>256*1024)throw std::runtime_error("Cannot read private sensor plan");auto p=QJsonDocument::fromJson(file.readAll()).object();
 if(p.value("slot")!=0||p.value("sensor")!="imx586"||p.value("width")!=4000||p.value("height")!=3000||p.value("laneCount")!=3||p.value("settle")!=14||p.value("is3Phase")!=true||p.value("laneAssign")!=528||p.value("outputPixelClock")!=577650000)throw std::runtime_error("Unsupported sensor mode");
 QByteArray bytes;
 for(auto field:{"initial","mode","streamOn","streamOff"}){
  const auto table=p.value(field).toArray();const int count=QString(field)=="initial"?1710:QString(field)=="mode"?100:1;if(table.size()!=count)throw std::runtime_error("Sensor table size changed");
  for(const auto &r:table){auto row=r.toArray();if(row.size()!=3)throw std::runtime_error("Malformed sensor row");for(const auto &v:row){double value=v.toDouble(-1);if(value<0||value>65535||value!=uint32_t(value))throw std::runtime_error("Invalid register data");uint32_t word=value;bytes.append(reinterpret_cast<const char*>(&word),4);}}
 }
 const auto hash=QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex();
 if(hash!="d9883c71a4327947d3be06abed7778e1695b34d7e0d937dba98b3accc1234658")throw std::runtime_error("Sensor table checksum is not the verified phone mode");return p;
}
QByteArray generic(){
 QByteArray blob;auto add=[&](uint32_t type,const void *value,uint32_t size){uint32_t header=type|(size<<8);blob.append(reinterpret_cast<const char*>(&header),4);blob.append(static_cast<const char*>(value),size);};
 cam_isp_resource_hfr_config hfr{};hfr.num_ports=1;hfr.port_hfr_config[0].resource_type=CAM_ISP_IFE_OUT_RES_RDI_0;hfr.port_hfr_config[0].subsample_pattern=1;hfr.port_hfr_config[0].framedrop_pattern=1;add(CAM_ISP_GENERIC_BLOB_TYPE_HFR_CONFIG,&hfr,sizeof(hfr));
 cam_isp_clock_config clock{};clock.num_rdi=1;clock.rdi_hz[0]=577650000;add(CAM_ISP_GENERIC_BLOB_TYPE_CLOCK_CONFIG,&clock,sizeof(clock));
 cam_isp_csid_clock_config csid{};csid.csid_clock=577650000;add(CAM_ISP_GENERIC_BLOB_TYPE_CSID_CLOCK_CONFIG,&csid,sizeof(csid));
 cam_isp_bw_config bandwidth{};bandwidth.num_rdi=1;bandwidth.rdi_vote[0].cam_bw_bps=1000000000;bandwidth.rdi_vote[0].ext_bw_bps=1000000000;add(CAM_ISP_GENERIC_BLOB_TYPE_BW_CONFIG,&bandwidth,sizeof(bandwidth));return blob;
}
}

int main(int argc,char **argv){
 QCoreApplication app(argc,argv);
 try{
  const auto args=app.arguments();if(args.size()!=3)throw std::runtime_error("Usage: ethercamera-spectra-capture PRIVATE_PROFILE_JSON PRIVATE_RAW_OUTPUT_OR_--rgb-stream");
  const bool streaming=args[2]=="--rgb-stream";std::signal(SIGTERM,stopped);std::signal(SIGINT,stopped);std::signal(SIGPIPE,SIG_IGN);
  utsname identity{};if(uname(&identity)||QString(identity.release)!="4.14.117-perf"||QString(identity.machine)!="aarch64"||read("/proc/device-tree/model")!="SDX50M MTP 18827 15")throw std::runtime_error("Unsupported board");
  const auto plan=profile(args[1]);stage("opening exact rear camera resources");
  Fd crmFd(role("cam-req-mgr")),ispFd(role("cam-isp")),syncFd(role("cam_sync")),sensorFd(slot("cam-sensor-driver",0,true)),phyFd(slot("cam-csiphy-driver",1,false));
  Transport crm(crmFd.fd),isp(ispFd.fd),sensor(sensorFd.fd),phy(phyFd.fd);const auto caps=isp.queryIsp();
  stage("probing rear sensor");spectra::probeRearImx586(crm,sensor);spectra::Session session(crm);
  std::vector<std::unique_ptr<Buffer>> keep;std::vector<std::unique_ptr<Fence>> fences;
  std::unique_ptr<Device> sensorDevice,ispDevice,phyDevice;int32_t link=-1;bool linked=false;
  Guard cleanup{[&]{
   auto safe=[](std::function<void()> fn){try{fn();}catch(const std::exception &e){std::fprintf(stderr,"Cleanup: %s\n",e.what());}};
   if(sensorDevice&&sensorDevice->started)safe([&]{sensorDevice->operation(CAM_STOP_DEV);sensorDevice->started=false;});
   if(linked){safe([&]{cam_req_mgr_flush_info f{};f.session_hdl=session.handle();f.link_hdl=link;f.flush_type=CAM_REQ_MGR_FLUSH_TYPE_ALL;crm.control(CAM_REQ_MGR_FLUSH_REQ,&f,sizeof(f));});}
   if(ispDevice&&ispDevice->started)safe([&]{ispDevice->operation(CAM_STOP_DEV);ispDevice->started=false;});
   if(phyDevice&&phyDevice->started)safe([&]{phyDevice->operation(CAM_STOP_DEV);phyDevice->started=false;});
   if(linked){safe([&]{cam_req_mgr_link_control c{};c.ops=CAM_REQ_MGR_LINK_DEACTIVATE;c.session_hdl=session.handle();c.num_links=1;c.link_hdls[0]=link;crm.control(CAM_REQ_MGR_LINK_CONTROL,&c,sizeof(c));});safe([&]{cam_req_mgr_unlink_info u{};u.session_hdl=session.handle();u.link_hdl=link;crm.control(CAM_REQ_MGR_UNLINK,&u,sizeof(u));});}
   if(ispDevice)safe([&]{ispDevice->close();});if(phyDevice)safe([&]{phyDevice->close();});if(sensorDevice)safe([&]{sensorDevice->close();});fences.clear();keep.clear();
  }};
  stage("acquiring sensor and applying pinned init/mode tables");sensorDevice=std::make_unique<Device>(sensor,session.handle());
  sensorSettings(crm,*sensorDevice,plan.value("initial").toArray(),2);sensorSettings(crm,*sensorDevice,plan.value("mode").toArray(),4);
  sensorSettings(crm,*sensorDevice,plan.value("streamOn").toArray(),0);sensorSettings(crm,*sensorDevice,plan.value("streamOff").toArray(),5);
  stage("acquiring RAW10 IFE RDI output");cam_isp_in_port_info in{};in.res_type=CAM_ISP_IFE_IN_RES_PHY_1;in.lane_type=CAM_ISP_LANE_TYPE_CPHY;in.lane_num=3;in.lane_cfg=0x210;in.dt=43;in.format=CAM_FORMAT_MIPI_RAW_10;
  in.left_stop=3999;in.left_width=4000;in.right_stop=3999;in.right_width=4000;in.line_stop=2999;in.height=3000;in.pixel_clk=577650000;in.num_out_res=1;
  in.data[0].res_type=CAM_ISP_IFE_OUT_RES_RDI_0;in.data[0].format=CAM_FORMAT_MIPI_RAW_10;in.data[0].width=4000;in.data[0].height=3000;
  cam_isp_resource resource{};resource.resource_id=CAM_ISP_RES_ID_PORT;resource.length=sizeof(in);resource.handle_type=CAM_HANDLE_USER_POINTER;resource.res_hdl=reinterpret_cast<uintptr_t>(&in);
  ispDevice=std::make_unique<Device>(isp,session.handle(),&resource,1);
  stage("acquiring/configuring three-trio C-PHY");cam_csiphy_acquire_dev_info acquire{};phyDevice=std::make_unique<Device>(phy,session.handle(),&acquire,1);
  {Buffer information(crm,4096),control(crm,4096);cam_csiphy_info c{};c.lane_mask=7;c.lane_assign=0x210;c.csiphy_3phase=1;c.lane_cnt=3;c.settle_time=14ULL*200000000;c.data_rate=577650000ULL*10/3;
   std::memcpy(information.data(),&c,sizeof(c));auto *p=packet(control,0,0,1);auto *d=reinterpret_cast<cam_cmd_buf_desc*>(&p->payload);descriptor(*d,information,sizeof(c),CAM_CMD_BUF_GENERIC);phyDevice->config(control);}
  auto alloc=[&](size_t size,const std::vector<int32_t> &mmu=std::vector<int32_t>{},bool pixels=false)->Buffer&{keep.push_back(std::make_unique<Buffer>(crm,aligned(size),mmu,pixels));return *keep.back();};
  auto &blob=alloc(4096);const auto init=generic();std::memcpy(blob.data(),init.constData(),init.size());
  std::vector<std::pair<Buffer*,Buffer*>> commands;
  auto configureIfe=[&](uint64_t id,bool initial,Buffer *pixels,Fence *fence,int reuse=-1){
   if(reuse<0){commands.push_back({&alloc(131072,{caps.device_iommu.non_secure,caps.cdm_iommu.non_secure}),&alloc(4096)});reuse=commands.size()-1;}
   auto &direct=*commands[reuse].first;auto &control=*commands[reuse].second;std::memset(direct.data(),0,direct.size());std::memset(control.data(),0,control.size());
   auto *p=packet(control,initial?0x0f000000:0x0f000001,id,initial?2:1);p->kmd_cmd_buf_index=0;p->kmd_cmd_buf_offset=0;
   auto *d=reinterpret_cast<cam_cmd_buf_desc*>(&p->payload);descriptor(d[0],direct,0,CAM_CMD_BUF_DIRECT,CAM_ISP_PACKET_META_COMMON);if(initial)descriptor(d[1],blob,init.size(),CAM_CMD_BUF_GENERIC,CAM_ISP_PACKET_META_GENERIC_BLOB_COMMON);
   if(!initial){p->num_io_configs=1;p->io_configs_offset=sizeof(cam_cmd_buf_desc);p->header.size+=sizeof(cam_buf_io_cfg);
    auto *io=reinterpret_cast<cam_buf_io_cfg*>(reinterpret_cast<uint8_t*>(&p->payload)+p->io_configs_offset);io->mem_handle[0]=pixels->handle();io->planes[0].width=4000;io->planes[0].height=3000;io->planes[0].plane_stride=5008;io->planes[0].slice_height=3000;
    io->format=CAM_FORMAT_MIPI_RAW_10;io->bpp=10;io->resource_type=CAM_ISP_IFE_OUT_RES_RDI_0;io->fence=fence->id;io->direction=CAM_BUF_OUTPUT;io->subsample_pattern=1;io->framedrop_pattern=1;
   }ispDevice->config(control);
  };
  stage("initializing IFE command/bandwidth/clock packet");configureIfe(1,true,nullptr,nullptr);
  cam_req_mgr_link_info connection{};connection.session_hdl=session.handle();connection.num_devices=2;connection.dev_hdls[0]=ispDevice->handle;connection.dev_hdls[1]=sensorDevice->handle;crm.control(CAM_REQ_MGR_LINK,&connection,sizeof(connection));link=connection.link_hdl;linked=true;
  cam_req_mgr_link_control activation{};activation.session_hdl=session.handle();activation.num_links=1;activation.link_hdls[0]=link;activation.ops=CAM_REQ_MGR_LINK_ACTIVATE;crm.control(CAM_REQ_MGR_LINK_CONTROL,&activation,sizeof(activation));
  stage("starting receiver and queuing three bounded frames");phyDevice->start();ispDevice->start();std::vector<Buffer*> images;
  auto queue=[&](uint64_t id,int index){
   cam_req_mgr_sched_request schedule{};schedule.session_hdl=session.handle();schedule.link_hdl=link;schedule.req_id=id;crm.control(CAM_REQ_MGR_SCHED_REQ,&schedule,sizeof(schedule));
   Buffer control(crm,4096);packet(control,127,id,0);sensorDevice->config(control);configureIfe(id,false,images[index],fences[index].get(),id<=3?-1:index+1);
  };
  for(int i=0;i<3;i++){
   auto &image=alloc(5008*3000,{caps.device_iommu.non_secure},true);std::memset(image.data(),0xa5,image.size());images.push_back(&image);fences.push_back(std::make_unique<Fence>(syncFd.fd));
   queue(i+1,i);
  }
  stage("starting physical sensor stream and waiting for first DMA fence");sensorDevice->start();fences[0]->wait();stage("frame fence signaled");
  auto *bytes=static_cast<const uint8_t*>(images[0]->data());size_t changed=0;for(size_t i=0;i<5008*3000;i++)changed+=bytes[i]!=0xa5;if(changed<4000*3000)throw std::runtime_error("DMA fence signaled without a populated image");
  if(streaming){
   const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(300);uint64_t request=1;double toneGain=0;
   while(!stopping&&std::chrono::steady_clock::now()<deadline){int index=(request-1)%3;if(request>1)fences[index]->wait();
    if(request%2){auto image=spectra::rgb(static_cast<const uint8_t*>(images[index]->data()),toneGain);writeAll(STDOUT_FILENO,image.constData(),image.size());}
    fences[index].reset();fences[index]=std::make_unique<Fence>(syncFd.fd);queue(request+3,index);request++;
   }return 0;
  }
  Fd output(::open(args[2].toLocal8Bit(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600));if(output.fd<0)throw std::system_error(errno,std::generic_category(),"Create private RAW output");
  size_t written=0;while(written<5008*3000){ssize_t n=::write(output.fd,bytes+written,5008*3000-written);if(n<=0)throw std::system_error(errno,std::generic_category(),"Save RAW frame");written+=n;}
  QJsonObject result{{"dmaFrameReceived",true},{"physicalFrameVerified",false},{"width",4000},{"height",3000},{"stride",5008},{"bits",10},{"changedBytes",qint64(changed)}};
  std::puts(QJsonDocument(result).toJson().constData());return 0;
 }catch(const std::exception &e){std::fprintf(stderr,"Native RAW capture: %s\n",e.what());return 1;}
}
