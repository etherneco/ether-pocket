#include "transport.h"
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <map>
void check(bool ok){if(!ok)throw std::runtime_error("Transport assertion failed");}
template<class F>void fails(F fn){bool failed=false;try{fn();}catch(const std::exception&){failed=true;}check(failed);}
int main(){try{
 int allocations=0,releases=0,created=0,destroyed=0,returnedFd=-1;
 spectra::Transport camera(9,[&](int fd,unsigned long request,void *payload){
  check(fd==9&&request==VIDIOC_CAM_CONTROL);auto &cmd=*static_cast<cam_control*>(payload);check(cmd.reserved==0&&cmd.handle_type==CAM_HANDLE_USER_POINTER);
  auto *arg=reinterpret_cast<void*>(cmd.handle);
  if(cmd.op_code==CAM_REQ_MGR_CREATE_SESSION){check(cmd.size==8);static_cast<cam_req_mgr_session_info*>(arg)->session_hdl=123;++created;}
  else if(cmd.op_code==CAM_REQ_MGR_DESTROY_SESSION){check(static_cast<cam_req_mgr_session_info*>(arg)->session_hdl==123);++destroyed;}
  else if(cmd.op_code==CAM_REQ_MGR_ALLOC_BUF){auto &a=*static_cast<cam_mem_mgr_alloc_cmd*>(arg);check(a.len==4096&&a.num_hdl==0&&a.align==4096);returnedFd=memfd_create("OFFLINE transport test",MFD_CLOEXEC);check(returnedFd>=0);check(ftruncate(returnedFd,a.len)==0);a.out.fd=returnedFd;a.out.buf_handle=5;++allocations;}
  else if(cmd.op_code==CAM_REQ_MGR_RELEASE_BUF){check(static_cast<cam_mem_mgr_release_cmd*>(arg)->buf_handle==5);++releases;}
  else check(false);return 0;
 });
 {spectra::Session session(camera);check(session.handle()==123);{spectra::Buffer buffer(camera,4096);check(buffer.handle()==5);std::memset(buffer.data(),42,4096);}session.close();session.close();}
 check(created==1&&destroyed==1&&allocations==1&&releases==1);check(fcntl(returnedFd,F_GETFD)==-1&&errno==EBADF);
 fails([&]{spectra::Buffer invalid(camera,1);});check(allocations==1);
 try{spectra::Session session(camera);spectra::Buffer buffer(camera,4096);throw std::runtime_error("unwind");}catch(const std::runtime_error&){}
 check(created==2&&destroyed==2&&allocations==2&&releases==2);
 int attempts=0;spectra::Transport interrupted(4,[&](int,unsigned long,void*){++attempts;errno=EINTR;return -1;});
 fails([&]{spectra::Session session(interrupted);});check(attempts==1);
 int destroyAttempts=0;
 spectra::Transport ambiguous(4,[&](int,unsigned long,void *p){auto *command=static_cast<cam_control*>(p);if(command->op_code==CAM_REQ_MGR_CREATE_SESSION){reinterpret_cast<cam_req_mgr_session_info*>(command->handle)->session_hdl=4;return 0;}++destroyAttempts;errno=EINTR;return -1;});
 {spectra::Session session(ambiguous);fails([&]{session.close();});}check(destroyAttempts==1);
 spectra::Transport badIsp(4,[](int,unsigned long,void *p){auto &c=*static_cast<cam_control*>(p);auto *q=reinterpret_cast<cam_query_cap_cmd*>(c.handle);auto *caps=reinterpret_cast<cam_isp_query_cap_cmd*>(q->caps_handle);caps->num_dev=CAM_ISP_HW_MAX+1;return 0;});fails([&]{badIsp.queryIsp();});
 auto packet=spectra::encodeI2c({{0x0100,0},{0x0202,0x1234}},2,2);check(packet.size()==24);i2c_rdwr_header header{};std::memcpy(&header,packet.data(),sizeof(header));check(header.count==2&&header.cmd_type==5&&header.op_code==1&&header.addr_type==2&&header.data_type==2);
 fails([]{spectra::encodeI2c({{0x100,256}},2,1);});fails([]{spectra::encodeI2c({},2,1);});
 auto power=spectra::encodePower({{0,19200000,1},{8,1,1}},{{8,0,1},{0,0,0}});
 check(power.size()==4*sizeof(cam_cmd_power)+3*sizeof(cam_cmd_unconditional_wait));
 cam_cmd_power first{};std::memcpy(&first,power.data(),sizeof(first));check(first.cmd_type==2&&first.count==1&&first.power_settings[0].config_val_low==19200000);
 fails([]{spectra::encodePower({{8,1,-1}},{{8,0,1}});});
 int nextHandle=100;bool probed=false;std::map<uint32_t,int> descriptors;
 spectra::Transport rear(9,[&](int,unsigned long,void *arg){
  auto &command=*static_cast<cam_control*>(arg);
  if(command.op_code==CAM_QUERY_CAP){auto *c=reinterpret_cast<cam_sensor_query_cap*>(command.handle);c->slot_info=0;c->pos_yaw=180;c->csiphy_slot_id=1;}
  else if(command.op_code==CAM_REQ_MGR_ALLOC_BUF){auto *c=reinterpret_cast<cam_mem_mgr_alloc_cmd*>(command.handle);int fd=memfd_create("OFFLINE probe packet",MFD_CLOEXEC);check(fd>=0&&ftruncate(fd,4096)==0);c->out.fd=fd;c->out.buf_handle=++nextHandle;descriptors[c->out.buf_handle]=fd;}
  else if(command.op_code==CAM_REQ_MGR_RELEASE_BUF){auto *c=reinterpret_cast<cam_mem_mgr_release_cmd*>(command.handle);check(descriptors.erase(c->buf_handle)==1);}
  else if(command.op_code==CAM_SENSOR_PROBE_CMD){
   check(command.handle_type==CAM_HANDLE_MEM_HANDLE&&command.size==8);
   void *view=mmap(nullptr,4096,PROT_READ,MAP_SHARED,descriptors.at(command.handle),0);check(view!=MAP_FAILED);
   auto *packet=static_cast<cam_packet*>(view);check(packet->num_cmd_buf==2&&packet->header.op_code==3);
   auto *desc=reinterpret_cast<cam_cmd_buf_desc*>(&packet->payload);check(desc[0].length==44&&desc[1].length>0);
   void *info=mmap(nullptr,4096,PROT_READ,MAP_SHARED,descriptors.at(desc[0].mem_handle),0);check(info!=MAP_FAILED);
   cam_cmd_i2c_info i2c{};cam_cmd_probe probe{},vendor{};std::memcpy(&i2c,info,sizeof(i2c));std::memcpy(&probe,static_cast<uint8_t*>(info)+4,sizeof(probe));std::memcpy(&vendor,static_cast<uint8_t*>(info)+24,sizeof(vendor));
   check(i2c.slave_addr==0x34&&i2c.i2c_freq_mode==3&&probe.camera_id==0&&probe.reg_addr==0x16&&probe.expected_data==0x586&&vendor.expected_data==0);
   munmap(info,4096);munmap(view,4096);probed=true;
  }else check(false);return 0;
 });
 spectra::probeRearImx586(rear,rear);check(probed&&descriptors.empty());
 spectra::Transport front(9,[](int,unsigned long,void *arg){auto &command=*static_cast<cam_control*>(arg);check(command.op_code==CAM_QUERY_CAP);auto *c=reinterpret_cast<cam_sensor_query_cap*>(command.handle);c->slot_info=2;c->pos_yaw=0;return 0;});
 fails([&]{spectra::probeRearImx586(rear,front);});check(descriptors.empty());
 std::puts("PASS: exact ABI, real mapped command memory fixture, ownership/unwind, ioctl errors, bounds and register encoding. No sensor accessed.");return 0;
}catch(const std::exception &e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}}
