#include "transport.h"
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <system_error>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstdio>

namespace spectra {
Transport::Transport(int descriptor,Ioctl callback):fd(descriptor),invoke(callback){
 if(fd<0)throw std::invalid_argument("Invalid camera descriptor");
 if(!invoke)invoke=[](int fd,unsigned long request,void *arg){return ::ioctl(fd,request,arg);};
}
void Transport::control(uint32_t opcode,void *payload,uint32_t bytes){
 if(!payload||!bytes||bytes>1024*1024)throw std::invalid_argument("Invalid camera control payload");
 cam_control command{};command.op_code=opcode;command.size=bytes;
 command.handle_type=CAM_HANDLE_USER_POINTER;command.handle=reinterpret_cast<uintptr_t>(payload);
 // Never blindly retry state-changing ioctls after EINTR: completion may be
 // ambiguous. Let the owning session unwind and release its resources.
 int rc=invoke(fd,VIDIOC_CAM_CONTROL,&command);
 if(rc<0)throw std::system_error(errno,std::generic_category(),"Spectra opcode "+std::to_string(opcode));
 if(rc!=0&&opcode!=CAM_REQ_MGR_FLUSH_REQ)throw std::runtime_error("Unexpected Spectra status "+std::to_string(rc));
}
cam_isp_query_cap_cmd Transport::queryIsp(){
 cam_isp_query_cap_cmd caps{};cam_query_cap_cmd query{};
 query.size=sizeof(caps);query.handle_type=CAM_HANDLE_USER_POINTER;query.caps_handle=reinterpret_cast<uintptr_t>(&caps);
 control(CAM_QUERY_CAP,&query,sizeof(query));
 if(caps.num_dev<0||caps.num_dev>CAM_ISP_HW_MAX)throw std::runtime_error("Invalid ISP capability count");
 return caps;
}
cam_sensor_query_cap Transport::querySensor(){cam_sensor_query_cap caps{};control(CAM_QUERY_CAP,&caps,sizeof(caps));return caps;}
void Transport::probeMemory(uint32_t handle){
 if(!handle)throw std::invalid_argument("Missing probe packet handle");
 cam_control command{};command.op_code=CAM_SENSOR_PROBE_CMD;command.size=sizeof(uint64_t);
 command.handle_type=CAM_HANDLE_MEM_HANDLE;command.handle=handle;
 int rc=invoke(fd,VIDIOC_CAM_CONTROL,&command);
 if(rc<0)throw std::system_error(errno,std::generic_category(),"Rear IMX586 kernel probe");
 if(rc)throw std::runtime_error("Unexpected sensor probe result");
}
Session::Session(Transport &t):transport(t){
 info.session_hdl=-1;transport.control(CAM_REQ_MGR_CREATE_SESSION,&info,sizeof(info));
 if(info.session_hdl<=0)throw std::runtime_error("Kernel returned invalid session handle");
 owned=true;
}
void Session::close(){if(!owned)return;owned=false;transport.control(CAM_REQ_MGR_DESTROY_SESSION,&info,sizeof(info));}
Session::~Session(){try{close();}catch(const std::exception &e){std::fprintf(stderr,"Session cleanup: %s\n",e.what());}}
Buffer::Buffer(Transport &t,size_t length,const std::vector<int32_t> &iommu,bool pixel):transport(t),bytes(length){
 if(length<4096||length>(pixel?32*1024*1024:1024*1024)||length%4096||iommu.size()>2)throw std::invalid_argument("Invalid bounded camera buffer allocation");
 if(pixel&&iommu.empty())throw std::invalid_argument("Pixel output requires a validated device IOMMU");
 cam_mem_mgr_alloc_cmd command{};command.len=length;command.align=4096;
 command.flags=CAM_MEM_FLAG_KMD_ACCESS|CAM_MEM_FLAG_UMD_ACCESS|CAM_MEM_FLAG_CMD_BUF_TYPE;
 if(!iommu.empty()){command.flags|=CAM_MEM_FLAG_HW_READ_WRITE;command.num_hdl=iommu.size();for(size_t i=0;i<iommu.size();i++){if(iommu[i]<=0)throw std::invalid_argument("Invalid IOMMU handle");command.mmu_hdls[i]=iommu[i];}}
 if(pixel)command.flags=CAM_MEM_FLAG_HW_READ_WRITE|CAM_MEM_FLAG_UMD_ACCESS|CAM_MEM_FLAG_PIXEL_BUF_TYPE;
 command.out.fd=-1;transport.control(CAM_REQ_MGR_ALLOC_BUF,&command,sizeof(command));
 hdl=command.out.buf_handle;fd=command.out.fd;
 try{
  if(!hdl||fd<0)throw std::runtime_error("Kernel returned invalid buffer allocation");
  if(fcntl(fd,F_SETFD,FD_CLOEXEC)<0)throw std::system_error(errno,std::generic_category(),"Buffer CLOEXEC");
  memory=mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
  if(memory==MAP_FAILED){memory=nullptr;throw std::system_error(errno,std::generic_category(),"Map camera command buffer");}
  std::memset(memory,0,bytes);
 }catch(...){try{close();}catch(...){}throw;}
}
void Buffer::close(){
 if(memory){if(munmap(memory,bytes)<0)throw std::system_error(errno,std::generic_category(),"Unmap camera buffer");memory=nullptr;}
 if(fd>=0){::close(fd);fd=-1;}
 if(hdl){cam_mem_mgr_release_cmd command{};command.buf_handle=static_cast<int32_t>(hdl);hdl=0;transport.control(CAM_REQ_MGR_RELEASE_BUF,&command,sizeof(command));}
}
Buffer::~Buffer(){try{close();}catch(const std::exception &e){std::fprintf(stderr,"Buffer cleanup: %s\n",e.what());}}
std::vector<uint8_t> encodeI2c(const std::vector<Register> &registers,uint8_t addressBytes,uint8_t dataBytes){
 if(registers.empty()||registers.size()>1024||addressBytes<1||addressBytes>2||dataBytes<1||dataBytes>2)throw std::invalid_argument("Unsupported sensor register packet");
 const uint32_t maxAddress=addressBytes==1?255:65535,maxData=dataBytes==1?255:65535;
 for(const auto &reg:registers)if(reg.address>maxAddress||reg.value>maxData)throw std::invalid_argument("Sensor register exceeds selected width");
 std::vector<uint8_t> bytes(sizeof(i2c_rdwr_header)+registers.size()*sizeof(i2c_random_wr_payload));
 i2c_rdwr_header header{};header.count=registers.size();header.op_code=1;header.cmd_type=5;
 header.addr_type=addressBytes;header.data_type=dataBytes;
 std::memcpy(bytes.data(),&header,sizeof(header));size_t offset=sizeof(header);
 for(const auto &reg:registers){i2c_random_wr_payload value{reg.address,reg.value};std::memcpy(bytes.data()+offset,&value,sizeof(value));offset+=sizeof(value);}
 return bytes;
}
std::vector<uint8_t> encodePower(const std::vector<PowerStep> &up,const std::vector<PowerStep> &down){
 if(up.empty()||down.empty()||up.size()>16||down.size()>16)throw std::invalid_argument("Invalid power sequence length");
 std::vector<uint8_t> bytes;
 auto append=[&](const void *data,size_t length){const auto *p=static_cast<const uint8_t*>(data);bytes.insert(bytes.end(),p,p+length);};
 auto sequence=[&](const std::vector<PowerStep> &steps,uint8_t command){
  for(const auto &step:steps){
   if(step.type>11||step.delayMs<0||step.delayMs>100)throw std::invalid_argument("Invalid power sequence operation");
   cam_cmd_power power{};power.count=1;power.cmd_type=command;
   power.power_settings[0].power_seq_type=step.type;power.power_settings[0].config_val_low=step.value;
   append(&power,sizeof(power));
   if(step.delayMs){cam_cmd_unconditional_wait wait{};wait.cmd_type=9;wait.op_code=3;wait.delay=step.delayMs;append(&wait,sizeof(wait));}
  }
 };
 sequence(up,2);sequence(down,3);return bytes;
}
void probeRearImx586(Transport &crm,Transport &sensor){
 const auto caps=sensor.querySensor();
 if(caps.slot_info!=0||caps.pos_yaw!=180||caps.csiphy_slot_id!=1||caps.secure_camera)throw std::runtime_error("Probe is restricted to rear main slot 0 / CSIPHY 1");
 // Facts decoded independently from all three device-owned IMX586 modules;
 // see ethercamera-imx586-module-profiles.json. No other phone's sequence.
 const auto power=encodePower({{1,0,1},{10,1,0},{2,0,1},{11,1,0},{3,0,1},{0,19200000,1},{8,1,1}},
                              {{8,0,1},{0,0,1},{3,0,0},{2,0,0},{11,0,0},{1,0,0},{10,0,0}});
 Buffer packet(crm,4096),information(crm,4096),settings(crm,4096);
 cam_cmd_i2c_info i2c{};i2c.slave_addr=0x34;i2c.i2c_freq_mode=3;i2c.cmd_type=4;
 cam_cmd_probe probe{};probe.data_type=2;probe.addr_type=2;probe.cmd_type=1;
 probe.reg_addr=0x16;probe.expected_data=0x586;probe.data_mask=0xffff;probe.camera_id=0;
 std::memcpy(information.data(),&i2c,sizeof(i2c));
 std::memcpy(static_cast<uint8_t*>(information.data())+sizeof(i2c),&probe,sizeof(probe));
 // OEM kernel consumes a SECOND cam_cmd_probe for optional module EEPROM
 // matching. Explicit zero block requests sensor-ID-only identification;
 // no module vendor/EEPROM/tuning compatibility is claimed by this probe.
 const size_t informationSize=sizeof(i2c)+sizeof(probe)*2;
 std::memcpy(settings.data(),power.data(),power.size());
 auto *pkt=static_cast<cam_packet*>(packet.data());pkt->header.op_code=3;
 pkt->header.size=sizeof(cam_packet)+2*sizeof(cam_cmd_buf_desc);pkt->num_cmd_buf=2;pkt->kmd_cmd_buf_index=uint32_t(-1);
 cam_cmd_buf_desc descriptors[2]{};
 descriptors[0].mem_handle=information.handle();descriptors[0].size=descriptors[0].length=informationSize;descriptors[0].type=CAM_CMD_BUF_LEGACY;
 descriptors[1].mem_handle=settings.handle();descriptors[1].size=descriptors[1].length=power.size();descriptors[1].type=CAM_CMD_BUF_I2C;
 std::memcpy(&pkt->payload,descriptors,sizeof(descriptors));
 sensor.probeMemory(packet.handle());
 settings.close();information.close();packet.close();
}
}
