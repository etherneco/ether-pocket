/* Populate the server address required by Qualcomm's downstream QRTR router. */
#include <errno.h>
#include <endian.h>
#include <stdint.h>
#include <sys/socket.h>
#include <libqrtr.h>

int qrtr_new_server(int fd, uint32_t service, uint16_t version, uint16_t instance)
{
    struct sockaddr_qrtr addr = {0};
    socklen_t length = sizeof(addr);
    struct qrtr_ctrl_pkt packet = {0};
    if (getsockname(fd, (void *)&addr, &length) < 0)
        return -1;
    if (!addr.sq_port) {
        if (bind(fd, (void *)&addr, sizeof(addr)) < 0)
            return -1;
        length = sizeof(addr);
        if (getsockname(fd, (void *)&addr, &length) < 0)
            return -1;
    }
    packet.cmd = htole32(QRTR_TYPE_NEW_SERVER);
    packet.server.service = htole32(service);
    packet.server.instance = htole32((uint32_t)instance << 8 | version);
    packet.server.node = htole32(addr.sq_node);
    packet.server.port = htole32(addr.sq_port);
    return qrtr_sendto(fd, addr.sq_node, QRTR_PORT_CTRL, &packet, sizeof(packet));
}

int qrtr_publish(int fd, uint32_t service, uint16_t version, uint16_t instance)
{
    return qrtr_new_server(fd, service, version, instance);
}
