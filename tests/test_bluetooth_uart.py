"""Linux-only parser/configuration tests; never opens a hardware device."""
import importlib.util
import os
from pathlib import Path
import socket
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('uart', Path(__file__).resolve().parents[1]/'scripts/etherbluetooth-uart.py')
uart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uart)


class UartTests(unittest.TestCase):
    def test_vendor_completion_with_zero_opcode(self):
        host, controller = socket.socketpair()
        with host, controller:
            payload = bytes.fromhex('04 ff 0e 00 02 0a 00 00 00 99 66 01 10 24 02 01 40 04 0e 04 01 00 00 00')
            controller.sendall(payload)
            events = uart.HciUart(host.fileno()).command(0xfc00, b'\x19', vendor=True)
            self.assertEqual(events[0], payload[:17])
            self.assertEqual(controller.recv(20), bytes.fromhex('01 00 fc 01 19'))

    def test_sleep_wake_indication_is_acknowledged(self):
        host, controller = socket.socketpair()
        with host, controller:
            event = bytes.fromhex('04 0e 04 01 03 0c 00')
            controller.sendall(b'\xfd' + event)
            self.assertEqual(uart.HciUart(host.fileno()).event(), event)
            self.assertEqual(controller.recv(1), b'\xfc')

    def test_rejected_command_is_an_error(self):
        host, controller = socket.socketpair()
        with host, controller:
            controller.sendall(bytes.fromhex('04 0e 04 01 03 0c 01'))
            with self.assertRaises(RuntimeError):
                uart.HciUart(host.fileno()).command(0x0c03)

    def test_timeout_is_bounded(self):
        host, controller = socket.socketpair()
        with host, controller:
            with self.assertRaises(TimeoutError):
                uart.HciUart(host.fileno()).event(.01)

    def test_invalid_framing_is_rejected(self):
        host, controller = socket.socketpair()
        with host, controller:
            controller.sendall(b'\x33')
            with self.assertRaises(RuntimeError):
                uart.HciUart(host.fileno()).event()

    def test_address_is_stable_private_and_explicitly_local(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'controller-address'
            address = uart.identity(path)
            self.assertEqual(address, uart.identity(path))
            self.assertEqual(address[0], 2)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('00:00:00:00:00:00')
            with self.assertRaises(ValueError):
                uart.identity(path)


if __name__ == '__main__':
    unittest.main()
