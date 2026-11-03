import struct
import unittest
from module_profile import decode,ProfileError

def fixture():
    # Synthetic schema values only. No manufacturer binary is distributed.
    symbols=[];values=bytearray()
    def add(ident,name,data):
        offset=len(values);values.extend(data);symbols.append(struct.pack('<Q32sQQQQ',ident,name.encode(),1,0,offset,len(data)))
    def words(v):return struct.pack('<'+'Q'*len(v),*v)
    add(1,'cameraModuleData',words([1,0,0,1,8]));s=[0]*103;s[:16]=[1,0,0,7,31,52,2,2,22,1414,65535,3,7,32,7,33];add(2,'sensorDriverData',words(s))
    m=[0]*38;add(8,'moduleConfiguration',words(m));add(31,'sensorName',b'imx586\0\0')
    add(32,'powerSetting',words([1,0,1,10,1,0,2,0,1,11,1,0,3,0,1,0,19200000,1,8,1,1]));add(33,'powerSetting',words([8,0,1,0,0,1,3,0,0,2,0,0,11,0,0,1,0,0,10,0,0]))
    table=b''.join(symbols);header=bytearray(232);magic=b'QTI Chromatix Header\0';header[:len(magic)]=magic;text=b'Parameter Parser V1.3.2 (fixture)';header[38:38+len(text)]=text
    struct.pack_into('<II',header,152,160,3);end=232+len(table)+len(values)
    for index,row in enumerate([(0,232,len(table)),(1,232+len(table),len(values)),(2,end,0)]):struct.pack_into('<QQQ',header,160+index*24,*row)
    return bytes(header)+table+values

class ModuleTests(unittest.TestCase):
    def test_exact_probe_and_power_facts(self):
        data=decode(fixture());self.assertEqual(data['expectedId'],0x586);self.assertEqual(data['slot'],0);self.assertEqual(data['powerUp'][5]['value'],19200000);self.assertFalse(data['physicalFrameVerified'])
    def test_truncation_and_section_bounds(self):
        blob=fixture()
        for length in [0,22,159,231,len(blob)-1]:
            with self.assertRaises(ProfileError):decode(blob[:length])
        bad=bytearray(blob);struct.pack_into('<Q',bad,168,999999)
        with self.assertRaises(ProfileError):decode(bytes(bad))
    def test_wrong_sensor_front_slot_and_power_value_are_rejected(self):
        blob=fixture()
        for before,after in [(b'imx586\0\0',b'imx471\0\0'),(struct.pack('<Q',19200000),struct.pack('<Q',24000000))]:
            with self.assertRaises(ProfileError):decode(blob.replace(before,after))
        bad=bytearray(blob);offset=232+6*72+40+103*8;struct.pack_into('<Q',bad,offset,2)
        with self.assertRaises(ProfileError):decode(bytes(bad))

if __name__=='__main__':unittest.main()
