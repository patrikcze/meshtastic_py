"""Simple program to demo how to use meshtastic library.
   To run: python examples/info.py
"""

import meshtastic
import meshtastic.serial_interface
from meshtastic.util import findPorts

iface = meshtastic.serial_interface.SerialInterface()

# call showInfo() just to ensure values are populated
# info = iface.showInfo()



print(findPorts())

if iface.nodes:
    for n in iface.nodes.values():
        if n["num"] == iface.myInfo.my_node_num:
            
            print(n["user"]["hwModel"])
            break

iface.close()