# pip install pyvisa-py
import pyvisa as visa
CONNECTSTRING = "TCPIP0::192.168.1.60::INSTR"
class DP83X(object):
    def __init__(self):
        pass

    def conn(self, constr):#="TCPIP0::192.168.1.60::INSTR"):# "USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR"):
        """Attempt to connect to instrument"""
        rm = visa.ResourceManager()
        self.inst = rm.open_resource(constr)

    def identify(self):
        """Return identify string which has serial number"""
        resp = self.inst.query("*IDN?").rstrip("\n").split(',')
        dr = {"company":resp[0], "model":resp[1], "serial":resp[2], "ver":resp[3]}
        
        return dr

    def readings(self, channel="CH1"):
        """Read voltage/current/power from CH1/CH2/CH3"""       
        resp = self.inst.query("MEAS:ALL? %s"%channel)
        resp = resp.split(',')
        dr = {"v":float(resp[0]), "i":float(resp[1]), "p":float(resp[2])}
        return dr

    def dis(self):
        del self.inst
    
    def applyVoltage(self,channel, voltage):
        self.inst.write(":APPL %s,%s"% (channel, voltage))
        
    def applyCurrent(self,channel, current):
        print(":SOURce %s :CURRent %s"%(channel, current))
        self.inst.write(":SOURce%s:CURRent %s"%(channel, current))

    def queryVolt(self, channel):
        return(float((self.inst.query(":APPL? %s ,VOLTage"%channel)).rstrip("\n")))
    
    def queryCurr(self, channel):
        return(float((self.inst.query(":APPL? %s ,CURRent"%channel)).rstrip("\n")))

    def off(self,channels=["Ch1","CH2","CH3"]):
        for channel in channels:
            self.inst.write("OUTP " + channel + ",OFF")
            
    def eStop(self):
        self.inst.write("OUTP ALL ,OFF")
        
    def allOn(self):
        self.inst.write("OUTP ALL ,ON")
            
    def on(self,channel="CH1"):
        self.inst.write("OUTP " + channel + ",on")
        print(channel)
            
    def state(self,channel="CH1"):
        return((self.inst.query("OUTP? " + channel )).rstrip("\n"))
        
    def applyState(self,channel="CH1",state="OFF"):
        print(channel)
        print(state)
        self.inst.write("OUTP %s,%s"%(channel, state))

    def writing(self, command=""):
        self.inst.write(command)
        
    def temperature(self):
        return((self.inst.query(":SYSTem:SELF:TEST:TEMP?")).rstrip("\n"))
        
if __name__ == '__main__':
    test = DP83X()

    #Insert your serial number here / confirm via Ultra Sigma GUI
    test.conn(CONNECTSTRING)#"TCPIP0::192.168.1.60::INSTR")#"USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR")
    
    print (test.readings())
