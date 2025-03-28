#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial.tools.list_ports, sys, time
global ser

def Find_comport_of_USB_TTL_Adapter():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(port.name,port.manufacturer,port.serial_number, port.description)
        comport=port.name
        ser=Open_serial_communication(comport)
        print (ser)
        found_com_port=""
        if ser !="No connection" and found_com_port=="":
            time.sleep(0.5)
            ser.flush()
            packet = ser.readline().decode()[:-1]
            print(packet)
            if "X|" in packet and "|X" in packet:
                print ("Hoorah, comport is",comport )
                found_com_port=comport
            time.sleep(.5)
            ser.close()
    return found_com_port

def Open_serial_communication(port):
    print("Opening comport:"+str(port))
    ser="No connection"
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0)
    except:
        print ("Error by pass")
        return (ser)
    return (ser)

import os
from os.path import exists
#application_directory=os.getcwd()
#config_file=application_directory+"/telemeter_config.txt"
config_file="telemeter_config.txt"
# checking if config file exists
if exists(config_file):
    print ("Config file exists.. reading config")
else:
    print("Config file does not exist... will search for com port")
    comport_found=Find_comport_of_USB_TTL_Adapter()
    if comport_found!="":
        print (comport_found)
        f=open(config_file, 'w')
        f.write(comport_found)
        f.write('\n')
        f.close()
        os.system("attrib +h " + config_file)

sys.exit()




#


Find_comport_of_USB_TTL_Adapter()

packet = ser.readline().decode()[:-1]
print (packet)
ser.close()

