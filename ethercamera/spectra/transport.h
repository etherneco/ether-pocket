#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <vector>
#include <media/cam_defs.h>
#include <media/cam_req_mgr.h>
#include <media/cam_isp.h>
#include <media/cam_sensor.h>

namespace spectra {
static_assert(__BYTE_ORDER__==__ORDER_LITTLE_ENDIAN__,"This downstream packet ABI requires little endian");
// Actual running-kernel UAPI, not V4L2 QUERYCAP or a guessed Android ABI.
static_assert(sizeof(cam_control)==24);
static_assert(offsetof(cam_control,handle)==16);
static_assert(sizeof(cam_req_mgr_session_info)==8);
static_assert(sizeof(cam_mem_mgr_alloc_cmd)==104);
static_assert(sizeof(cam_cmd_probe)==20);
static_assert(sizeof(cam_power_settings)==12);

using Ioctl=std::function<int(int,unsigned long,void*)>;
class Transport {
 int fd;Ioctl invoke;
public:
 explicit Transport(int descriptor,Ioctl callback={});
 void control(uint32_t opcode,void *payload,uint32_t bytes);
 cam_isp_query_cap_cmd queryIsp();
 cam_sensor_query_cap querySensor();
 void probeMemory(uint32_t packetHandle);
};

class Session {
 Transport &transport;cam_req_mgr_session_info info{};bool owned=false;
public:
 explicit Session(Transport&);
 ~Session();
 Session(const Session&)=delete;Session &operator=(const Session&)=delete;
 void close();int32_t handle()const{return info.session_hdl;}
};

class Buffer {
 Transport &transport;uint32_t hdl=0;int fd=-1;void *memory=nullptr;size_t bytes=0;
public:
 Buffer(Transport&,size_t bytes,const std::vector<int32_t>& iommu={},bool pixel=false);
 ~Buffer();
 Buffer(const Buffer&)=delete;Buffer &operator=(const Buffer&)=delete;
 void close();void *data()const{return memory;}size_t size()const{return bytes;}
 uint32_t handle()const{return hdl;}
};

struct Register {uint32_t address;uint32_t value;};
struct PowerStep {uint16_t type;uint32_t value;int16_t delayMs;};
std::vector<uint8_t> encodePower(const std::vector<PowerStep>& up,const std::vector<PowerStep>& down);
// Rear-main, exact handset profile only. Powers up, matches ID, powers down.
// Does not stream, initialize tuning, acquire an actuator or move a motor.
void probeRearImx586(Transport &crm,Transport &sensor);
// Encoder only. No register access occurs here. The mode/profile must be
// derived and validated separately before a sensor may receive this payload.
std::vector<uint8_t> encodeI2c(const std::vector<Register>&,uint8_t addressBytes,uint8_t dataBytes);
}
