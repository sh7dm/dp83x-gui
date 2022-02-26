My python skills are very poor and have basically cut my teeth on this project, so keep that in mind when you discover the many mistakes or bad programming practices I have folllowed.

dp83x-gui
=========

Rigol DP83X GUI. This is a simple graphing GUI for the Rigol DP83X connected via VISA (tested over USB by colinoflynn, tested over TCPIP although other IO connections should work).

To use this you'll need to install:

 * Ultra Sigma from Rigol [OPTIONAL: Can also just copy/paste the address from the DP832 display]
 * Python 3.x with pyside6 PyQt5 pyqtgraph pyvisa-py install as follows
 * pip install pyside6
 * pip install PyQt5 
 * pip install pyqtgraph
 * pip install pyvisa-py
 
Once your system is running, just run dpgui.py via your installed Python. Supply the address string (open Ultra Sigma, make sure it finds your Power Supply, and copy-paste address string from that, OR just look in the 'utilities' menu, OR point your browser to its IP address). 

Will look something like 
 USB0::0x1AB1::0x0E11::DP8XXXXXXXX::INSTR
 TCPIP0::192.168.1.60::INSTR

If the address copied from the DP832 display doesn't work, install Ultra Sigma to confirm it is detected there. If Ultra Sigma didn't see the power supply something else is up...

Bugs
=======

 * Can only set number of windows before connecting
 * Doesn't validate instrument state before doing anything, so crashes are likely. Check python output for reasons.
 
Notes
========

Changes made to the original repo

1. ported to python3
2. Change settings on the fly
3. Making changes to graph settings did not previoulsy work for me.
4. poorly implemented SIN, SQR and SAW function to drive the output accordingly
5. Added Pause Plot
6. Added Pause Timer
7. Added Temperture
8. Added option to vary Update interval
9. Added Logging
10. Added ESTOP (Press any of the three buttons and it turn off all channels)
11. Added logo
12. Auto set channel limits based on the model (not yet implemented)
13. Zero plot at start for better auto ranging (not yet implemented)
