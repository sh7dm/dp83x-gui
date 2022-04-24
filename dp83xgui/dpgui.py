
# Date 2022/02/26 
# Ultra Crappy DP83x GUI based on Colin O'Flynn's and kudl4t4's github repository by Justin Richards
# Colin O'Flynn's - https://github.com/colinoflynn/dp83X-gui  https://www.youtube.com/watch?v=Mwu7hfbYQjk
# kudl4t4 - https://github.com/kudl4t4/RIGOL-DP83X-GUI
#
# Python 3.10.0
# pip install pyside6
# pip install PyQt5 
# pip install pyqtgraph
# pip install pyvisa-py
# pip install matplotlib

#TCPIP0::192.168.1.60::INSTR  <- If using TCPIP then point browser to your IP address and it will reveal the "VISA TCP/IP String"

# ToDo
# 1. Use the fetched model number to set the channel limits
# 2. start plot at Zero - two? samples so it clears the buffer and does a better job of auto ranging
CONNECTSTRING = "TCPIP0::192.168.1.60::INSTR"
import os
import sys
import time

import math
import matplotlib.pyplot as plt

import numpy as np


from PySide6.QtCore import *
from PySide6.QtGui import *

from PyQt5.QtWidgets import * #QApplication, QWidget, QMainWindow, QPushButton, QMessageBox, QBoxLayout
from PyQt5 import QtCore, QtGui

try:
    import pyqtgraph as pg
    import pyqtgraph.parametertree.parameterTypes as pTypes
    from pyqtgraph.parametertree import Parameter, ParameterTree, ParameterItem, registerParameterType
except ImportError:
    print ("Install pyqtgraph from http://www.pyqtgraph.org")
    raise

from dp83x import DP83X

class GraphWidget(QWidget):
    """
    This GraphWidget holds a pyqtgraph PlotWidget, and adds a toolbar for the user to control it.
    """

    def __init__(self):
        #pg.setConfigOption('background', 'w')
        #pg.setConfigOption('foreground', 'k')

        QWidget.__init__(self)
        layout = QVBoxLayout()

        self.pw = pg.PlotWidget(name="Power Trace View")
        self.pw.setLabel('top', 'Power Trace View')
        self.pw.setLabel('bottom', 'Samples')
        self.pw.setLabel('left', 'Data')
        vb = self.pw.getPlotItem().getViewBox()
        vb.setMouseMode(vb.RectMode)

        layout.addWidget(self.pw)

        self.setLayout(layout)

        self.setDefaults()

    def setDefaults(self):
        self.defaultYRange = None

    def VBStateChanged(self, obj):
        """Called when ViewBox state changes, used to sync X/Y AutoScale buttons"""
        arStatus = self.pw.getPlotItem().getViewBox().autoRangeEnabled()

        #X Axis
        if arStatus[0]:
            self.XLockedAction.setChecked(False)
        else:
            self.XLockedAction.setChecked(True)

        #Y Axis
        if arStatus[1]:
            self.YLockedAction.setChecked(False)
        else:
            self.YLockedAction.setChecked(True)

    def VBXRangeChanged(self, vb, range):
        """Called when X-Range changed"""
        self.xRangeChanged.emit(range[0], range[1])

    def xRange(self):
        """Returns the X-Range"""
        return self.pw.getPlotItem().getViewBox().viewRange()[0]

    def YDefault(self, extraarg=None):
        """Copy default Y range axis to active view"""
        if self.defaultYRange is not None:
            self.setYRange(self.defaultYRange[0], self.defaultYRange[1])

    def setDefaultYRange(self, lower, upper):
        """Set default Y-Axis range, for when user clicks default button"""
        self.defaultYRange = [lower, upper]

    def setXRange(self, lower, upper):
        """Set the X Axis to extend from lower to upper"""
        self.pw.getPlotItem().getViewBox().setXRange(lower, upper)

    def setYRange(self, lower, upper):
        """Set the Y Axis to extend from lower to upper"""
        self.pw.getPlotItem().getViewBox().setYRange(lower, upper)

    def xAutoScale(self, enabled):
        """Auto-fit X axis to data"""
        vb = self.pw.getPlotItem().getViewBox()
        bounds = vb.childrenBoundingRect(None)
        vb.setXRange(bounds.left(), bounds.right())

    def yAutoScale(self, enabled):
        """Auto-fit Y axis to data"""
        vb = self.pw.getPlotItem().getViewBox()
        bounds = vb.childrenBoundingRect(None)
        vb.setYRange(bounds.top(), bounds.bottom())

    def xLocked(self, enabled):
        """Lock X axis, such it doesn't change with new data"""
        self.pw.getPlotItem().getViewBox().enableAutoRange(pg.ViewBox.XAxis, ~enabled)

    def yLocked(self, enabled):
        """Lock Y axis, such it doesn't change with new data"""
        self.pw.getPlotItem().getViewBox().enableAutoRange(pg.ViewBox.YAxis, ~enabled)

    def passTrace(self, trace, startoffset=0, pen='b', clear=True):
        if clear:
            self.pw.clear()
        xaxis = range(startoffset, len(trace)+startoffset)
        self.pw.plot(xaxis, trace, pen=pen)

class DP83XGUI(QMainWindow):

    def __init__(self):
        super(DP83XGUI, self).__init__()
        self.setWindowIcon(QtGui.QIcon('frog1.bmp'))
        wid = QWidget()
        layout = QVBoxLayout()
        self.drawDone = False

        settings = QSettings()

        constr = settings.value('constring')
        if constr is None: constr = CONNECTSTRING#"TCPIP0::192.168.1.60::INSTR" #"TCPIP0::172.16.0.125::INSTR" #"USB0::0x1AB1::0x0E11::DPXXXXXXXXXXX::INSTR"

        self.constr = QLineEdit(constr)
        self.conpb = QPushButton("Connect")
        self.conpb.clicked.connect(self.tryConnect)

        self.dispb = QPushButton("Disconnect")
        self.dispb.clicked.connect(self.dis)

        self.loggingPushButton = QPushButton("Log On/Off")
        self.loggingPushButton.setCheckable(True)
        self.loggingPushButton.clicked.connect(self.setLogging)

        self.cbNumDisplays = QSpinBox()
        self.cbNumDisplays.setMinimum(1)
        self.cbNumDisplays.setMaximum(3)
        self.cbNumDisplays.setValue(3)

        self.sbReadingsInterval = QSpinBox()
        self.sbReadingsInterval.setAccelerated(True)
        self.sbReadingsInterval.setMinimum(1)
        self.sbReadingsInterval.setMaximum(600000)         #600 sec 10mins
        self.sbReadingsInterval.setValue(500)
        self.sbReadingsInterval.setSuffix(" mS")
        self.sbReadingsInterval.setPrefix("Update ")
        self.sbReadingsInterval.valueChanged.connect(lambda x: self.setInterval( x))
        
        self.pbPauseTimer = QPushButton("Pause Timer")
        self.pbPauseTimer.setCheckable(True)
        self.pbPauseTimer.clicked.connect(self.tryPauseTimer)


        
        self.leTemp = QLineEdit("---")
        self.leTemp.setObjectName("leTemp")
        
        self.leModel = QLineEdit("---")
        self.leModel.setObjectName("leModel")
     
        self.layoutcon = QHBoxLayout()
        self.layoutcon.addWidget(QLabel("Connect String:"))
        self.layoutcon.addWidget(self.constr)
        self.layoutcon.addWidget(self.conpb)
        self.layoutcon.addWidget(self.dispb)
        self.layoutcon.addWidget(self.cbNumDisplays)

        layout.addLayout(self.layoutcon)

        self.channelSpecsDP83x = []
        
        self.channelSpecsDP83x.append({'DP832':{'maxV':30,'maxI':3},'DP831':{'maxV':8 ,'maxI':5}})
        self.channelSpecsDP83x.append({'DP832':{'maxV':30,'maxI':3},'DP831':{'maxV':30,'maxI':2}})
        self.channelSpecsDP83x.append({'DP832':{'maxV':5 ,'maxI':3},'DP831':{'maxV':30,'maxI':2}})
        
        self.graphlist = []
        self.graphsettings = []
        self.chLineEdits =[]
        self.chConfig = []
        self.cbList = []
        
        self.vdata = [[],[],[]]
        self.idata = [[],[],[]]
        self.pdata = [[],[],[]]
        self.filename = ""
        self.startLogTime = time.time() 

        self.degree = 0
        self.temperatureWarningToggle = False
        
        # suspect it is 60mS is the fastest it can up date
        #pos slope 0 - 30V ~ 105mS
        #neg slope 30 - 0V ~ 355mS
        
        self.numSamples = 100  #100 samples equals a period of 6.002 sec
        A = 1
        F = 1
        P = (self.numSamples/2)/F
        x = np.arange(self.numSamples)

        self.sawX = []
        for i in range(self.numSamples):
            self.sawX.append((A/P) * (P - abs(i % (2*P) - P)) )

        sinX = np.sin((2*np.pi*F)*(x/self.numSamples))

        self.sqrX = np.where(x < self.numSamples/2, 0, 1)

        self.absSinX = (sinX +1)/2
        shiftedAbsSinX = (np.sin((2*np.pi*F)*((x+(3/4)*(self.numSamples))/self.numSamples) )+1)/2

        wid.setLayout(layout)

        self.setCentralWidget(wid)
        self.setWindowTitle("DP83X GUI")

    def addGraphs(self, graphnum):
        layout = self.centralWidget().layout()
        gb = QGroupBox()

        self.gridLayoutChannel = QGridLayout()

        self.lblChannel = QLabel()
        self.lblChannel.setObjectName("lblChannel")
        self.gridLayoutChannel.addWidget(self.lblChannel, 0, 0, 1, 1)

        self.cbChannel = QComboBox()
        self.cbChannel.setMaxVisibleItems(3)
        self.cbChannel.setObjectName("cbChannel")
        self.cbChannel.addItem("CH1")
        self.cbChannel.addItem("CH2")
        self.cbChannel.addItem("CH3")
        self.cbChannel.setCurrentText("CH%d"%(graphnum+1))
        self.gridLayoutChannel.addWidget(self.cbChannel, 0, 1, 1, 1)
        self.cbChannel.currentIndexChanged.connect(lambda x :self.setChannel(graphnum, "CH%d"%(x+1)))

        self.lblPoint = QLabel()
        self.lblPoint.setObjectName("lblPoint")
        self.gridLayoutChannel.addWidget(self.lblPoint, 0, 2, 1, 1)

        self.graphsettings.append({"channel":"CH%d"%(graphnum+1), "points":1024})

        self.vdata.append([-1])#*self.graphsettings[-1]["points"])
        self.idata.append([-1])#*self.graphsettings[-1]["points"])
        self.pdata.append([-1])#*self.graphsettings[-1]["points"])

        self.sbPoints = QSpinBox()
        self.sbPoints.setMinimum(10)
        self.sbPoints.setMaximum(30000)
        self.sbPoints.setObjectName("sbPoints")
        self.sbPoints.setValue(self.graphsettings[-1]["points"])
        self.sbPoints.valueChanged.connect(lambda x: self.setPoints(graphnum, x))
        self.gridLayoutChannel.addWidget(self.sbPoints, 0, 3, 1, 1)

        self.pbPlotV = QPushButton()
        self.pbPlotV.setObjectName("pbPlotV")
        self.pbPlotV.setCheckable(True)
        self.pbPlotV.setChecked(True)
        self.gridLayoutChannel.addWidget(self.pbPlotV, 1, 1, 1, 1)

        self.pbPlotI = QPushButton()
        self.pbPlotI.setObjectName("pbPlotI")
        self.pbPlotI.setCheckable(True)
        self.gridLayoutChannel.addWidget(self.pbPlotI, 1, 2, 1, 1)
 
        self.pbPlotP = QPushButton()
        self.pbPlotP.setObjectName("pbPlotP")
        self.pbPlotP.setCheckable(True)
        self.gridLayoutChannel.addWidget(self.pbPlotP, 1, 3, 1, 1)

        self.graphsettings[-1]["venabled"] = self.pbPlotV
        self.graphsettings[-1]["ienabled"] = self.pbPlotI
        self.graphsettings[-1]["penabled"] = self.pbPlotP


        self.pbEStop = QPushButton()
        self.pbEStop.setObjectName("pbEStop")
        self.pbEStop.clicked.connect(lambda : self.eStop(graphnum))
        self.gridLayoutChannel.addWidget(self.pbEStop, 1, 0, 1, 1)
        
        self.pbPause = QPushButton()
        self.pbPause.setObjectName("pbPause")
        self.pbPause.setCheckable(True)
        self.pbPause.clicked.connect(lambda : self.tryPausePlot(graphnum))
        
        self.pbClearPlot = QPushButton()
        self.pbPause.setObjectName("pbClearPlot")        
        self.pbClearPlot.clicked.connect(lambda : self.clearPlot(graphnum))


        self.lblState = QLabel()
        self.lblState.setObjectName("lblState")
        self.gridLayoutChannel.addWidget(self.lblState, 3, 0, 1, 1)
        
        self.cbState = QComboBox()
        self.cbState.setObjectName("cbState")
        self.cbState.addItem("ON")
        self.cbState.addItem("OFF")
        self.cbState.setCurrentText(self.inst.state("CH%s"%(graphnum+1)))

        self.cbFunction = QComboBox()
        self.cbFunction.setObjectName("cbFunction")
        self.cbFunction.addItem("SIN")
        self.cbFunction.addItem("SQR")
        self.cbFunction.addItem("SAW")

        self.sbVolts = QDoubleSpinBox()
        self.sbVolts.setAccelerated(True)
        self.sbVolts.setSuffix(" [V]")
        self.sbVolts.setDecimals(3)
        #print(self.leModel.text()) 
        
        
        self.sbVolts.setMaximum(self.channelSpecsDP83x[graphnum][self.leModel.text()]["maxV"])
        self.sbVolts.setSingleStep(0.01)
        self.sbVolts.setObjectName("sbVolts")
        self.sbVolts.setValue(self.inst.queryVolt("CH%d"% (graphnum+1)))
        self.sbVolts.valueChanged.connect(lambda x: self.setVolts(graphnum, x))

        self.sbCurrent = QDoubleSpinBox()
        self.sbCurrent.setAccelerated(True)
        self.sbCurrent.setSuffix(" [A]")
        self.sbCurrent.setDecimals(3)
        self.sbCurrent.setMaximum(self.channelSpecsDP83x[graphnum][self.leModel.text()]["maxI"])
        self.sbCurrent.setSingleStep(0.01)
        self.sbCurrent.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
        self.sbCurrent.setObjectName("sbCurrent")
        self.sbCurrent.setValue(self.inst.queryCurr("CH%d"% (graphnum+1)))
        self.sbCurrent.valueChanged.connect(lambda x: self.setCurr(graphnum, x))

        self.lblVoltage = QLabel()
        self.lblVoltage.setObjectName("lblVoltage")
        self.gridLayoutChannel.addWidget(self.lblVoltage, 4, 0, 1, 1)

        self.leState = QLineEdit()
        self.leState.setObjectName("leState")

        self.leVolts = QLineEdit()
        self.leVolts.setObjectName("leVolts")

        self.leCurrent = QLineEdit()
        self.leCurrent.setObjectName("leCurrent")

        self.lePower = QLineEdit()
        self.lePower.setObjectName("lePower")
        
        self.chLineEdits.append({"state":self.leState,"volts":self.leVolts,"current":self.leCurrent,"power":self.lePower})
        self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["state"], 3, 1, 1, 1)
        self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["volts"], 4, 1, 1, 1)
        self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["current"], 5, 1, 1, 1)
        self.gridLayoutChannel.addWidget(self.chLineEdits[-1]["power"], 6, 1, 1, 1)
        
        self.lblCurr = QLabel()
        self.lblCurr.setObjectName("lblCurr")
        self.gridLayoutChannel.addWidget(self.lblCurr, 5, 0, 1, 1)

        self.pbSet = QPushButton()
        self.pbSet.setObjectName("pbSet")
        self.gridLayoutChannel.addWidget(self.pbSet, 2, 2, 1, 2)
        self.pbSet.clicked.connect(lambda : self.setupChannel(graphnum))

        self.lblPower = QLabel()
        self.lblPower.setObjectName("lblPower")
        self.gridLayoutChannel.addWidget(self.lblPower, 6, 0, 1, 1)

        self.ckState = QCheckBox()
        self.ckState.setObjectName("ckState")
        self.ckVoltage = QCheckBox()
        self.ckVoltage.setObjectName("ckVoltage")
        self.ckCurrent = QCheckBox()
        self.ckCurrent.setObjectName("ckCurrent")
        self.ckFunction = QCheckBox()
        self.ckFunction.setObjectName("ckFunction")

        self.chConfig.append({"ckState":self.ckState,"ckVoltage":self.ckVoltage,"ckCurrent":self.ckCurrent,"ckFunction":self.ckFunction, \
        "cbState":self.cbState,"sbVolts":self.sbVolts,"sbCurrent":self.sbCurrent,"cbFunction":self.cbFunction,"pbPause":self.pbPause,"pbClearPlot":self.pbClearPlot})
        
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["pbPause"], 2, 0, 1, 1)
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["pbClearPlot"], 2, 1, 1, 1)
        
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckState"], 3, 2, 1, 1)
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckVoltage"], 4, 2, 1, 1)
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckCurrent"], 5, 2, 1, 1)
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["ckFunction"], 6, 2, 1, 1)
        
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["cbState"], 3, 3, 1, 1)        
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["sbVolts"], 4, 3, 1, 1)        
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["sbCurrent"], 5, 3, 1, 1)
        self.gridLayoutChannel.addWidget(self.chConfig[-1]["cbFunction"], 6, 3, 1, 1)
        
        self.graphlist.append(GraphWidget())
        self.gridLayoutChannel.addWidget(self.graphlist[-1], 0, 4,8,1)

        gb.setLayout(self.gridLayoutChannel)
        self.gridLayoutChannel.setColumnStretch(0, 1)
        self.gridLayoutChannel.setColumnStretch(1, 1)
        self.gridLayoutChannel.setColumnStretch(2, 1)
        self.gridLayoutChannel.setColumnStretch(3, 1)
        self.gridLayoutChannel.setColumnStretch(4, 10)
        layout.addWidget(gb)

        self.retranslateUi(QMainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        self.cbState.setItemText(0, _translate("MainWindow", "ON"))
        self.cbState.setItemText(1, _translate("MainWindow", "OFF"))
        self.lblState.setText(_translate("MainWindow", "State:"))
        self.leVolts.setText(_translate("MainWindow", "---"))
        self.ckState.setText(_translate("MainWindow", "State: "))
        self.pbEStop.setText(_translate("MainWindow", "E STOP"))
        self.lePower.setText(_translate("MainWindow", "---"))
        self.leCurrent.setText(_translate("MainWindow", "---"))
        self.lblCurr.setText(_translate("MainWindow", "Current [A]:"))
        self.lblVoltage.setText(_translate("MainWindow", "Voltage [V]:"))
        self.pbSet.setText(_translate("MainWindow", "SET"))
        self.pbPlotI.setText(_translate("MainWindow", "Plot I"))
        self.leState.setText(_translate("MainWindow", "---"))
        self.lblPoint.setText(_translate("MainWindow", "Points"))
        self.lblPower.setText(_translate("MainWindow", "Power [W]:"))
        self.pbPlotV.setText(_translate("MainWindow", "Plot V"))
        self.pbPause.setText(_translate("MainWindow", "PAUSE PLOT"))
        self.pbClearPlot.setText(_translate("MainWindow", "CLEAR PLOT"))
        self.lblChannel.setText(_translate("MainWindow", "Channel"))
        self.pbPlotP.setText(_translate("MainWindow", "Plot P"))
        self.ckVoltage.setText(_translate("MainWindow", "Voltage [V]:"))
        self.ckCurrent.setText(_translate("MainWindow", "Current [I]:"))
        self.ckFunction.setText(_translate("MainWindow", "Func [V]:"))

    def tryOn(self, channum, buttOn ):
        if buttOn:
            self.inst.writing(":OUTP "+self.graphsettings[channum]["channel"]+",ON")
        else:
            self.inst.writing(":OUTP "+self.graphsettings[channum]["channel"]+",OFF")

    def tryPausePlot(self, channum ):
        """
        """
        #print (channum)
    def clearPlot(self,graphnum):
        #arrayToClear = int(self.graphsettings[graphnum]["channel"][-1]) - 1
        self.vdata[graphnum] = []
        self.idata[graphnum] = []
        self.pdata[graphnum] = []
        
    def tryPauseTimer(self):
        if(self.pbPauseTimer.isChecked()):
            self.readtimer.stop()
        else:
            self.readtimer.start()

    def dis(self):
        #print (self.cbChannel.currentText())
        self.readtimer.stop()
        self.inst.dis()

    def tryConnect(self):
        constr = self.constr.text()
        QSettings().setValue('constring', constr)

        self.inst = DP83X()
        self.inst.conn(constr)
        self.leModel.setText(self.inst.identify()["model"]) 

        self.layoutcon.addWidget(self.loggingPushButton)
        self.layoutcon.addWidget(self.sbReadingsInterval)
        self.layoutcon.addWidget(self.pbPauseTimer)
        self.layoutcon.addWidget(QLabel("Temperature:"))
        self.layoutcon.addWidget(self.leTemp)
        self.layoutcon.addWidget(QLabel("Model:"))
        self.layoutcon.addWidget(self.leModel)

        if self.drawDone == False:
            #self.addGraphs(self.cbNumDisplays.value()) # <- it can not be done this way.  It results in all functions refering to CH3 only
            for i in range (0,self.cbNumDisplays.value()):
                self.addGraphs(i)
            self.cbNumDisplays.setEnabled(False)
            self.resize(1200,800)
            self.drawDone = True

        self.readtimer = QtCore.QTimer()
        self.readtimer.setInterval(self.sbReadingsInterval.value())

        self.readtimer.timeout.connect(self.updateReadings)
        self.readtimer.start()
        

        self.readDegCtimer = QtCore.QTimer()
        self.readDegCtimer.setInterval(1000)

        self.readDegCtimer.timeout.connect(self.updateSystTemperature)
        self.readDegCtimer.start()


        
        

    def setInterval(self, interval):
        self.readtimer.setInterval(self.sbReadingsInterval.value())

    def eStop(self, graphnum):
        self.inst.off()

    def setupChannel(self, graphnum):
        #self.chConfig.append({"ckState":self.ckState,"ckVoltage":self.ckVoltage,"ckCurrent":self.ckCurrent,"cbState":self.cbState,"sbVolts":self.sbVolts,"sbCurrent":self.sbCurrent})
        #so the channel we want to change is pointed to by -> self.graphsettings[graphnum]["channel"] 
        if(self.chConfig[graphnum]["ckVoltage"].isChecked()):
            self.inst.applyVoltage(self.graphsettings[graphnum]["channel"], self.chConfig[graphnum]["sbVolts"].value())
        if(self.chConfig[graphnum]["ckCurrent"].isChecked()):
            self.inst.applyCurrent(self.graphsettings[graphnum]["channel"][-1], self.chConfig[graphnum]["sbCurrent"].value())  #pass the chan number not the chan str. i.e send 2 not CH2

        if(self.chConfig[graphnum]["ckState"].isChecked()):
            self.inst.applyState(self.graphsettings[graphnum]["channel"],self.chConfig[graphnum]["cbState"].currentText())

    def setChannel(self, graphnum, channelstr):
        self.graphsettings[graphnum]["channel"] = channelstr

    def setPoints(self, graphnum, points):
        self.graphsettings[graphnum]["points"] = points

    def setVolts(self, graphnum, V):
        """
        """

    def doFunction(self):
        y = 0
        for ch in range(3):
            if((self.chConfig[ch]["ckFunction"].isChecked())):
                if(self.chConfig[ch]["cbFunction"].currentText() == "SIN"):
                    y = self.absSinX[self.degree] * self.chConfig[ch]["sbVolts"].value()

                if(self.chConfig[ch]["cbFunction"].currentText() == "SQR"):
                    y = self.sqrX[self.degree] * self.chConfig[ch]["sbVolts"].value()

                if(self.chConfig[ch]["cbFunction"].currentText() == "SAW"):
                    y = self.sawX[self.degree] * self.chConfig[ch]["sbVolts"].value()
                self.inst.applyVoltage("CH%d"% (ch+1),"%.3f"%y)

        self.degree += 1
        if(self.degree == self.numSamples):
            self.degree = 0


    def setCurr(self, graphnum, mA):
        """
        print(graphnum)
        print(mA)
        """

    def setLogging(self):
        """
        """
        #print(self.loggingPushButton.isChecked())

    def logData(self):#,readings,graphnum):
        path_to_log = "captures\\"
        file_format = "csv"
        try:
            os.makedirs(path_to_log)
        except FileExistsError:
            pass

        if (self.loggingPushButton.isChecked()):
            if(self.filename ==""):
                self.startLogTime = time.time() 
                
                # Prepare filename as C:\MODEL_SERIAL_YYYY-MM-DD_HH.MM.SS
                timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                self.filename = path_to_log + self.inst.identify()["model"] + "_" +  self.inst.identify()["serial"] + "_" + timestamp
                header = b"Timestamp,Volts,Curr,Power\n"

                for ch in ["CH1","CH2","CH3"]:
                    file = open(self.filename + "_" + ch + "." + file_format, "ab")
                    file.write(header) 
                    file.close
            for ch in ["CH1","CH2","CH3"]:
                readings = self.inst.readings(ch)
                file = open(self.filename + "_" + ch + "." + file_format, "ab")
                file.write(("%f,%f,%f,%f\n" % (time.time() - self.startLogTime,readings["v"], readings["i"], readings["p"])).encode("utf-8"))
                file.close
        else:
            self.filename = ""

    def updateSystTemperature(self):
        degC = self.inst.temperature()
        if(float(degC) > 40):
            if(self.temperatureWarningToggle):
                self.temperatureWarningToggle = False
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : pink;"
                                "}")
            else:
                self.temperatureWarningToggle = True
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : white;"
                                "}")
        else:
                self.leTemp.setStyleSheet("QLineEdit"
                                "{"
                                "background : lightgreen;"
                                "}")        
            
        self.leTemp.setText(degC)
    
    def updateReadings(self):
        #print(self.inst.state())
        #self.updateSystTemperature(self.inst.temperature())
        self.logData()
        self.doFunction()
        for i, gs in enumerate(self.graphsettings):
            readings = self.inst.readings(gs["channel"])
            self.vdata[i].append(readings["v"])
            self.idata[i].append(readings["i"])
            self.pdata[i].append(readings["p"])
        
            self.chLineEdits[i]["state"].setText(self.inst.state("CH%d"% (i+1)))
            self.chLineEdits[i]["volts"].setText(str(readings["v"]))
            self.chLineEdits[i]["current"].setText(str(readings["i"]))
            self.chLineEdits[i]["power"].setText(str(readings["p"]))
            while len(self.vdata[i]) > gs["points"]:
                self.vdata[i].pop(0)

            while len(self.idata[i]) > gs["points"]:
                self.idata[i].pop(0)

            while len(self.pdata[i]) > gs["points"]:
                self.pdata[i].pop(0)
        
        self.redrawGraphs()

    def redrawGraphs(self):
        for i,g in enumerate(self.graphlist):
            if not (self.chConfig[i]["pbPause"].isChecked()):
                clear = True
                
                if self.graphsettings[i]["venabled"].isChecked():
                    g.passTrace(self.vdata[i], pen='b')
                    clear = False

                if self.graphsettings[i]["ienabled"].isChecked():
                    g.passTrace(self.idata[i], pen='r', clear=clear)

                if self.graphsettings[i]["penabled"].isChecked():
                    g.passTrace(self.pdata[i], pen='g', clear=clear)

def makeApplication():
    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setOrganizationName("Kissing Frogs")
    app.setApplicationName("DP83X GUI")
    return app

if __name__ == '__main__':
    app = makeApplication()

    # Create and show the form
    window = DP83XGUI()
    window.show()

    # Run the main Qt loop
    sys.exit(app.exec_())
