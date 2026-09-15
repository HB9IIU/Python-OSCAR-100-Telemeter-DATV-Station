#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import os
import random
import socket  # for Minitiouner control
import sys
import threading
import time
import webbrowser
# TkINTER PART
from tkinter import *
from tkinter import messagebox

import psutil
import serial.tools.list_ports
from flask import Flask, render_template, request, jsonify

##########################################################################################
Version = "Ver. 1.9"

Callsign = "G7VHG"
Callsign = "HB9IIU"
http_port = 9999

debug = False
DemoMode = False

TTL_Adapter_manufacturer = "FTDI"  # for ttl-usb Daniel adapter
TTL_Adapter_manufacturer = "Prolific"  # for ttl-usb Steve adapter
TTL_Adapter_manufacturer = "Silicon Labs"  # for ttl-usb dongle adapter


Voltage_Calibration_Factor = 1
Current_Calibration_Factor = 1

# HTML Interface
Show_Link_to_Pluto = True
Show_PTT_Button = True
Show_Link_to_Overlays = True

Pluto_IP = "192.168.0.40"  # this is for the link on the webpage Daniel
Pluto_IP = "192.168.0.41"  # this is for the link on the webpage Steve
Pluto_IP = "192.168.2.1"  # this is for the link on the webpage Daniel ElALbir

# MINITIOUNER
minitiouner_host = "232.0.0.11"
minitiouner_port = 6789

##########################################################################################

global Voltage_28V_Line, Amperage_28V_Line, Temperature_heatsink, Temperature_ambient, PTT_status
global Heatsink_Temperature_List, Ambient_Temperature_List, Time_array

global received_packets

Voltage_28V_Line = 0
Amperage_28V_Line = 0
Temperature_heatsink = -99  # we do this to detect a 1st measure in Temperature_and_current_recording_Thread
Temperature_ambient = 0
PTT_status = "OFF"

received_packets = 0
hhmmss_tot_up_tx = "00:00:00"

# opening socket to minitiouner
try:
    minitiouner_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print('Minitiouner socket is ok')
except socket.error:
    print('Failed to create socket')


# The magic class to allow compiling with attachments
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# The magic class to kill threads
class Thread(threading.Thread):
    def __init__(self, *args, **keywords):
        threading.Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, why, arg):
        if why == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, why, arg):
        if self.killed:
            if why == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True


def Start_Flask_Server():
    print("Starting Falsk server...")
    app.run(debug=False, host="localhost", port=http_port)


def Random_Values_Generator_For_Demo_Mode():
    global Voltage_28V_Line, Amperage_28V_Line, Temperature_heatsink, Temperature_ambient, PTT_status
    print("Demode values generator has started")
    while True:
        time.sleep(1)
        Voltage_28V_Line = random.randint(220, 320) / 10
        Amperage_28V_Line = random.randint(0, 120) / 10
        Temperature_heatsink = random.randint(200, 500) / 10
        Temperature_ambient = random.randint(-50, 330) / 10
        try:  # This is required to by pass an error at launch due to non readiness of the tkinter window
            Ambient_Air_Value.config(text=str(Temperature_ambient) + " " + "°C")
            Heatsink_Value.config(text=str(Temperature_heatsink) + " " + "°C")
            Voltage_Value.config(text=str(Voltage_28V_Line) + " V")
            Ampere_Value.config(text=str(Amperage_28V_Line) + " A")
        except:
            pass


def Uptime_Label_Updater_thread():
    while True:
        global hhmmss_tot_up
        current_time = time.time()
        elapsedseconds = int(current_time - satrtup_time)
        hhmmss_tot_up = time.strftime('%H:%M:%S', time.gmtime(elapsedseconds))
        if elapsedseconds > 2:
            try:  # This is required to by pass an error at launch due to non readiness of the tkinter window
                Uptime_TX_RX_Value.config(text=hhmmss_tot_up)

            except:
                pass
        time.sleep(1)


def TX_Uptime_counter_thread():
    global hhmmss_tot_up_tx
    TX_uptime_in_seconds = 0
    hhmmss_tot_up_tx = "00:00:00"
    while True:
        if PTT_status == "ON":
            TX_uptime_in_seconds = TX_uptime_in_seconds + 1
            hhmmss_tot_up_tx = time.strftime('%H:%M:%S', time.gmtime(TX_uptime_in_seconds))
            Uptime_TX_Value.config(text=hhmmss_tot_up_tx)
        # print ("TX uptime:", hhmmss_tot_up_tx)
        time.sleep(1)


def Find_comport_of_USB_TTL_Adapter(TTL_Adapter_manufacturer):
    ports = serial.tools.list_ports.comports()
    comport = "none"
    for port in ports:
        print(port.name, port.manufacturer, port.serial_number, port.description)
        if TTL_Adapter_manufacturer in port.manufacturer:
            comport = port.name
            break
    return comport


def Open_Serial_Communication(port):
    global ser
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1)
        return True
    except:
        return False


def HC12_RX_Thread():
    print("Data aquisition started...")
    global Voltage_28V_Line, Amperage_28V_Line, Temperature_heatsink, Temperature_ambient, PTT_status, received_packets
    while True:
        if ser.inWaiting() > 0:
            packet = ser.readline().decode()[:-1]
            # print("Received Packet: ", packet)
            # print("Checking Integrity (Should Start with 'X|' and end with an '|X' ")
            if packet[:2] == 'X|' and packet[len(packet) - 2:] == '|X':  # good packet
                # print("Packet seems Good, let's decode it")  # very basic way to check packet integrity not involving a ckecksum
                split_packet = packet.split("|")
                # print("Split packet with delimitator '|'    -->    ", split_packet)
                # print ("Decoded Values")
                # print ("--------------")
                received_packets = received_packets + 1
                current_time = time.time()
                elapsedseconds = int(current_time - satrtup_time)
                if elapsedseconds > 0:
                    per_Second = int(received_packets / elapsedseconds * 10) / 10

                try:
                    Packets_Label.config(text=str(per_Second) + " r/s")
                    Temperature_ambient = int(split_packet[1]) / 100
                    Temperature_heatsink = int(split_packet[2]) / 100
                    Voltage_28V_Line = int(split_packet[3]) / 1000 * Voltage_Calibration_Factor
                    Amperage_28V_Line = int(split_packet[4]) / 1000 * Current_Calibration_Factor
                    PTT_status = split_packet[5]

                    # For tkinter
                    Ambient_Air_Value.config(text=str("{:.1f}".format(Temperature_ambient)) + "°C")
                    Heatsink_Value.config(text=str("{:.1f}".format(Temperature_heatsink)) + "°C")
                    Voltage_Value.config(text=str("{:.1f}".format(Voltage_28V_Line)) + " V")
                    Ampere_Value.config(text=str("{:.1f}".format(Amperage_28V_Line)) + " A")

                    if debug == True:
                        print("Temperature_ambient:", Temperature_ambient, "[deg.C]")
                        print("Temperature_heatsink:", Temperature_heatsink, "[deg.C]")
                        print("Voltage_28V_Line:", Voltage_28V_Line, "[V]")
                        print("Amperage_28V_Line:", Amperage_28V_Line, "[A]")
                        print("PTT_status:", PTT_status)
                        print("")

                except:
                    pass  # to avoid blockage to non readiness of tkinter
            else:
                print("Strange Packet")


def Temperature_and_current_recording_ThreadOLDl():
    print("Temperature & current recording has started")
    global Heatsink_Temperature_List
    global Ambient_Temperature_List
    global Amperage_28V_List
    global Time_array

    Heatsink_Temperature_List = []
    Ambient_Temperature_List = []
    Amperage_28V_List = []
    Time_array = []

    sampling_interval = 5
    logging_duration_in_minute = 5
    number_of_samples = int(logging_duration_in_minute * 60 / sampling_interval)
    # we wait to get a 1st measure
    while Temperature_heatsink == -99:
        pass
    # fill array with initial values
    current_time = int(time.time() * 1000)
    seconds_to_next_sample = (
            int(current_time / sampling_interval) * sampling_interval + sampling_interval - current_time)
    next_sample_time = current_time + seconds_to_next_sample
    first_sample_time = next_sample_time - number_of_samples * sampling_interval
    sample_time = first_sample_time

    for sample in range(0, number_of_samples, 1):
        Heatsink_Temperature_List.append(Temperature_heatsink)
        Ambient_Temperature_List.append(Temperature_ambient)
        Amperage_28V_List.append(Amperage_28V_Line)
        Time_array.append(sample_time)
        sample_time = sample_time + sampling_interval
    while True:
        current_time = datetime.datetime.now()
        if current_time.second % 5 == 0:  # is true if number is divisible by 5, i.e. 5,10,15,20, etc....
            # if current_time.second == 00 or current_time.second == 15 or current_time.second == 30 or current_time.second == 45:

            Heatsink_Temperature_List.pop(0)
            Heatsink_Temperature_List.append(Temperature_heatsink)
            Ambient_Temperature_List.pop(0)
            Ambient_Temperature_List.append(Temperature_ambient)
            Amperage_28V_List.pop(0)
            Amperage_28V_List.append(Amperage_28V_Line)
            Time_array.pop(0)
            now = int(time.time())  # current epoch in seconds
            aligned = now - (now % sampling_interval)  # e.g., 1743101185 becomes 1743101180
            Time_array.append(aligned * 1000)  # back to ms

            if debug == True:
                print("Heatsink_Temperature_List", Heatsink_Temperature_List)
                print("Ambient_Temperature_List", Ambient_Temperature_List)
                print("Amperage_28V_List", Amperage_28V_List)
                print("Time_array", Time_array)
            time.sleep(sampling_interval - 0.1)

def Temperature_and_current_recording_Thread():
    print("Temperature & current recording has started")
    global Heatsink_Temperature_List
    global Ambient_Temperature_List
    global Amperage_28V_List
    global Time_array

    Heatsink_Temperature_List = []
    Ambient_Temperature_List = []
    Amperage_28V_List = []
    Time_array = []

    sampling_interval = 5  # seconds
    logging_duration_minutes = 5
    number_of_samples = int(logging_duration_minutes * 60 / sampling_interval)

    # Wait for valid readings
    while Temperature_heatsink == -99:
        time.sleep(0.1)

    # Align first sample time to the past N * sampling_interval
    now = int(time.time())
    aligned_now = now - (now % sampling_interval)
    first_sample_time = aligned_now - number_of_samples * sampling_interval

    for i in range(number_of_samples):
        Heatsink_Temperature_List.append(Temperature_heatsink)
        Ambient_Temperature_List.append(Temperature_ambient)
        Amperage_28V_List.append(Amperage_28V_Line)
        Time_array.append((first_sample_time + i * sampling_interval) * 1000)

    while True:
        # Align current time to the nearest 5 seconds
        now = int(time.time())
        if now % sampling_interval == 0:
            # Update sliding window
            Heatsink_Temperature_List.pop(0)
            Ambient_Temperature_List.pop(0)
            Amperage_28V_List.pop(0)
            Time_array.pop(0)

            Heatsink_Temperature_List.append(Temperature_heatsink)
            Ambient_Temperature_List.append(Temperature_ambient)
            Amperage_28V_List.append(Amperage_28V_Line)
            Time_array.append(now * 1000)

            if debug:
                print("Time_array", Time_array)

            # wait until next tick
            while int(time.time()) == now:
                time.sleep(0.1)

def On_Closing_Tkinter_Window():
    try:
        print("Killing Uptime updater")
        Uptime_updater.kill()
        print("Success")
    except:
        print("Failed")

    try:
        print("Killing Flask Server")
        Flask_Server.kill()
        print("Success")
    except:
        print("Failed")

    try:
        print("Killing Data Recorder")
        Record_Data.kill()
        print("Success")
    except:
        print("Failed")

    try:
        print("Killing random value generator")
        Random_Values_Generator_For_Demo_Mode.kill()
        print("Success")
    except:
        print("Failed")

    try:
        print("Killing HC 12 receiver")
        HC12_Receiver.kill()
        print("Success")
    except:
        print("Failed")

    try:
        print("Closing serial port")
        ser.close()
        print("Success")
    except:
        print("Failed")

    try:
        print("Closing Minitiouner socket")
        minitiouner_socket.close()
        print("Success")
    except:
        print("Failed")

    window.destroy()
    print ("Exiting here")
    raise SystemExit

    p = psutil.Process(os.getpid())
    print ("Trying to kill main process")
    try:
        os.system("taskkill /f /im "+p.name())
    except:
        print("Failed")
    sys.exit()
    quit()


def define_flask_app():
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(sys._MEIPASS, 'templates')
        static_folder = os.path.join(sys._MEIPASS, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        app = Flask(__name__)

    @app.route('/digital.html')
    def digital_displays():
        return render_template('digital.html')

    @app.route('/')
    def index0():
        return render_template('index.html')

    @app.route('/index.html')
    def index1():
        return render_template('index.html')

    @app.route('/linear.html')
    def linear():
        return render_template('linear.html')

    @app.route('/graph.html')
    def graph():
        return render_template('graph.html')

    @app.route('/obs_overlays.html')
    def obs_overlays():
        return render_template('obs_overlays.html')

    @app.route('/obs_overlay_test.html')
    def obs_overlay_test():
        return render_template('obs_overlay_test.html')

    @app.route('/obs.html')
    def obs():
        return render_template('obs.html')

    @app.route('/obs_voltmeter.html')
    def obs_voltmeter():
        return render_template('obs_voltmeter.html')

    @app.route('/obs_ammeter.html')
    def obs_ammeter():
        return render_template('obs_ammeter.html')

    @app.route('/obs_PA_thermometer.html')
    def obs_PA_thermometer():
        return render_template('obs_PA_thermometer.html')

    @app.route('/obs_air_thermometer.html')
    def obs_air_thermometer():
        return render_template('obs_air_thermometer.html')

    @app.route('/obs_graph.html')
    def obs_graph():
        return render_template('obs_graph.html')

    @app.route('/obs_javatime_white.html')
    def obs_javatime_white():
        return render_template('obs_javatime_white.html')

    @app.route('/obs_javatime_black.html')
    def obs_javatime_black():
        return render_template('obs_javatime_black.html')

    @app.route('/askpython', methods=['GET', 'POST'])
    def process_request():
        global PTT_status
        Request = request.json["Instruction"]
        Arg1 = request.json["Argument_1"]
        Arg2 = request.json["Argument_2"]
        print (Request)

        if Request == "get_data":
            # print ("will return:",Voltage_28V_Line,Amperage_28V_Line,Temperature_heatsink,Temperature_ambient)
            return jsonify(Voltage=Voltage_28V_Line, \
                           Current=Amperage_28V_Line, \
                           Temperature_Ambient=Temperature_ambient, \
                           Temperature_PA=Temperature_heatsink, \
                           RX_Uptime_duration=hhmmss_tot_up, \
                           TX_Uptime_duration=hhmmss_tot_up_tx, \
                           PTT_status=PTT_status
                           )

        if Request == "get_callsign":
            return (Callsign + " DATV Station Monitor")

        if Request == "Control_PTT_Relay":
            if Arg1 == "ON":
                print("Sending 'ON' to Arduino")
                while PTT_status == "OFF":
                    ser.write("ON".encode())
                    time.sleep(.1)
                return "PTT Relay switched to ON"
            else:
                print("Sending 'OFF' to Arduino")
                while PTT_status == "ON":
                    ser.write("OFF".encode())
                    time.sleep(.1)

                return "PTT Relay switched to OFF"
        if Request == "get_data_for_chart":
            Time_array_int = [round(t) for t in Time_array]

            PA_Temperatures_XY = [list(a) for a in zip(Time_array_int, Heatsink_Temperature_List)]
            AIR_Temperatures_XY = [list(a) for a in zip(Time_array_int, Ambient_Temperature_List)]
            Current_XY = [list(a) for a in zip(Time_array_int, Amperage_28V_List)]

            PA_Temperatures_XY.sort(key=lambda x: x[0])
            AIR_Temperatures_XY.sort(key=lambda x: x[0])
            Current_XY.sort(key=lambda x: x[0])
            return jsonify(PA_Temperatures_XY, AIR_Temperatures_XY, Current_XY)

        if Request == "get_webinterface_settings":
            return jsonify(Callsign=Callsign, \
                           Show_PTT_Button=Show_PTT_Button, \
                           Show_Link_to_Pluto=Show_Link_to_Pluto, \
                           Show_Link_to_Overlays=Show_Link_to_Pluto, \
                           Pluto_IP=Pluto_IP)

        if Request == "Set_Minitiouner":
            print("Arg1", Arg1)
            print("Arg2", Arg2)
            control_minitiouner(Arg1, Arg2)

            return ("OK")

    return app


def Open_Browser():
    webbrowser.open_new("http://localhost:" + str(http_port))


def Start_All_Threads_In_Demo():
    Flask_Server.start()
    Uptime_updater.start()
    Random_Values_Generator_For_Demo_Mode.start()
    Record_Data.start()
    Open_Browser()


def Start_All_Threads_Live():
    Flask_Server.start()
    Uptime_updater.start()
    TX_Uptime_counter.start()
    HC12_Receiver.start()
    Record_Data.start()
    Open_Browser()


def control_minitiouner(freq, sr):
    freq = freq + 8089.5
    print("a ", freq)
    frequ = str(int(freq * 1000))  # 2403.25 -> 2403250
    print("b ", freq)

    l = len(frequ)
    nzero = 8 - l
    Freq = frequ.rjust(nzero + l, '0')
    print("c ", freq)

    SRrate = str(int(sr))
    l = len(SRrate)
    nzero = 5 - l
    Srate = SRrate.rjust(nzero + l, '0')
    Offset = "08089500"  # in local
    Offset = "09750000"  # on sat
    Doppler = "0"
    WideScan = "0"
    LowSR = "0"
    DVBmode = "Auto"
    FPlug = "A"
    Voltage = "0"
    kHz = "Off"
    msg = "[GlobalMsg],Freq=%s,Offset=%s,Doppler=%s,Srate=%s,WideScan=%s,LowSR=%s,DVBmode=%s,FPlug=%s,Voltage=%s,22kHz=%s" % (
        Freq, Offset, Doppler, Srate, WideScan, LowSR, DVBmode, FPlug, Voltage, kHz)
    msg = msg.encode()
    print("Sending Message to Minitiouner", msg)
    minitiouner_socket.sendto(msg, (minitiouner_host, minitiouner_port))


if __name__ == '__main__':
    app = define_flask_app()

    window = Tk()
    window.title(Callsign + " DATV Telemeter")
    w = 300
    h = 155
    window.geometry('%dx%d+%d+%d' % (w, h, 20, 20))  # to position the window at opening
    window.resizable(False, False)
    window.attributes('-topmost', 1)

    # window.iconbitmap('./static/img/favicon.ico')
    # window.iconbitmap(default=resource_path(datafile))
    window.iconbitmap(default=resource_path("./static/img/favicon.ico"))
    frame = Frame(window)
    frame.pack(pady=5, padx=5)

    label_width = 15
    Ambient_Air_temperature_label = Label(frame, text="Ambient Air Temp.:", font=("Helvetica 12"), anchor="e", width=15)
    Ambient_Air_temperature_label.grid(column=1, row=1)
    Heatsink_temperature_label = Label(frame, text="Heatsink Temp.:", font=("Helvetica 12"), anchor="e", width=15)
    Heatsink_temperature_label.grid(column=1, row=2)
    Voltage_label = Label(frame, text="Voltage:", font=("Helvetica 12"), anchor="e", width=15)
    Voltage_label.grid(column=1, row=3)
    Ampere_label = Label(frame, text="Ampere:", font=("Helvetica 12"), anchor="e", width=15)
    Ampere_label.grid(column=1, row=4)
    Ambient_Air_Value = Label(frame, text="N.A.", font=("Helvetica 12"), anchor="e", width=7)
    Ambient_Air_Value.grid(column=2, row=1)
    Heatsink_Value = Label(frame, text="N.A.", font=("Helvetica 12"), anchor="e", width=7)
    Heatsink_Value.grid(column=2, row=2)
    Voltage_Value = Label(frame, text="N.A.", font=("Helvetica 12"), anchor="e", width=7)
    Voltage_Value.grid(column=2, row=3)
    Ampere_Value = Label(frame, text="N.A.", font=("Helvetica 12"), anchor="e", width=7)
    Ampere_Value.grid(column=2, row=4)
    Uptime_TX_RX_Label = Label(frame, text="Uptime RX&TX:", font=("Helvetica 12"), anchor="e", width=15)
    Uptime_TX_RX_Label.grid(column=1, row=5)
    Uptime_TX_RX_Value = Label(frame, text="00:00:00", font=("Helvetica 12"), anchor="e", width=7)
    Uptime_TX_RX_Value.grid(column=2, row=5)

    Uptime_TX_Label = Label(frame, text="Uptime TX:", font=("Helvetica 12"), anchor="e", width=15)
    Uptime_TX_Label.grid(column=1, row=6)
    Uptime_TX_Value = Label(frame, text="00:00:00", font=("Helvetica 12"), anchor="e", width=7)
    Uptime_TX_Value.grid(column=2, row=6)

    Version_Label = Label(frame, text=Version + "\nby HB9IIU", font=("Helvetica 9"), width=8)
    Version_Label.grid(column=0, row=4, rowspan=2)
    Packets_Label = Label(frame, text="6.5 r/s", font=("Helvetica 10"), width=8)
    Packets_Label.grid(column=0, row=6)

    # Uptime_Label.bind("<Button-1>", lambda e: Open_Browser())

    # Received_Packet_Label = Label(frame, text="Received packet: ", font=("Helvetica 12"), width=30)
    # Received_Packet_Label.grid(column=0, row=6, columnspan=3)

    # Create an object of tkinter ImageTk
    image_string = b'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'
    render = PhotoImage(data=image_string)
    # img = ImageTk.PhotoImage(Image.open(os.path.abspath(os.getcwd())+"/static/img/favicon.gif"))
    image_label = Label(frame, image=render, anchor='e')
    # image_label = Label(frame, image=img,anchor='e')
    # label.pack()
    image_label.grid(column=0, row=0, rowspan=4)
    image_label.bind("<Button-1>", lambda e: Open_Browser())

    window.protocol("WM_DELETE_WINDOW", On_Closing_Tkinter_Window)

    Flask_Server = Thread(target=Start_Flask_Server)
    Random_Values_Generator_For_Demo_Mode = Thread(target=Random_Values_Generator_For_Demo_Mode)
    HC12_Receiver = Thread(target=HC12_RX_Thread)
    Record_Data = Thread(target=Temperature_and_current_recording_Thread)
    Uptime_updater = Thread(target=Uptime_Label_Updater_thread)
    TX_Uptime_counter = Thread(target=TX_Uptime_counter_thread)
    satrtup_time = time.time()

    if DemoMode == True:
        print("Starting in DEMO mode....")
        Start_All_Threads_In_Demo()
    else:
        port = Find_comport_of_USB_TTL_Adapter(TTL_Adapter_manufacturer)
        if Open_Serial_Communication(port) == True:
            print("Checking if alive.....")
            check_counter = 0
            Is_alive = False
            while check_counter < 5:
                if ser.inWaiting() > 0:
                    packet = ser.readline().decode()[:-1]
                    print("Received Packet: ", packet)
                    # print("Checking Integrity (Should Start with 'X|' and end with an '|X' ")
                    if packet[:2] == 'X|' and packet[len(packet) - 2:] == '|X':  # good packet
                        Is_alive = True
                        check_counter = 100  # to escape the while loop
                time.sleep(.5)
                print("Trying...")
                check_counter = check_counter + 1
            if Is_alive == False:
                x = messagebox.askyesno('DATV Telemeter', 'Not receiving any data...\n\nStart in Demo Mode?')
                if x == True:
                    print("Starting in DEMO mode....")
                    Start_All_Threads_In_Demo()
            else:
                print("Starting in LIVE mode....")
                Start_All_Threads_Live()
        else:
            x = messagebox.askyesno('DATV Telemeter', 'Could not find PC HC12 adapter \n\nStart in Demo Mode?')
            if x == True:
                print("Starting in DEMO mode....")
                Start_All_Threads_In_Demo()
            else:
                sys.exit()

    window.mainloop()
    quit()
