#pin 2 = out pin 3 = clock
import time
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
from tkinter import messagebox
import numpy as np
import csv
import os
from collections import deque
from itertools import islice

class RealTimePlotter:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Plotter")
        self.root.state('zoomed')

        self.running = False
        self.paused = False
        self.start_time = None
        self.time_list = []
        self.time_list_plot = deque([] , maxlen=100)
        self.data_list = []
        self.data_list_plot = deque([] , maxlen=100)
        self.threshold = 15000
        self.chart_threshold = 650000
        self.first_exceeding_time = None
        self.notified = False
        self.great_threshold_seconds = 3
        self.exceeding_start_time = None
        self.countdown_label = None
        self.highThreshold = 0
        self.puncThreshold = 0
        self.countdown_time = 60
        self.countdown_start_time = None
        self.last_below_threshold_time = None
        self.great_flag = False
        self.puncCount = 0
        self.dataQueue = deque([] , maxlen=4)
        self.puncLabel = 0
        self.puncEvent = False
        self.startpuncflag = None

        self.event_list = []  # List to store important events


        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack()

        frame = tk.Frame(root)
        frame.pack()

        tk.Label(frame, text="Real-Time Graph", font=("Courier", 32)).pack()

        tk.Button(frame, text="Start", command=self.start_sequence).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Reset Graph", command=self.reset_graph).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Export Data", command=self.export_data).pack(side=tk.LEFT, padx=10, pady=10)

        self.threshold_label = tk.Label(frame, text=f"Threshold: {self.threshold}", font=("Courier", 16))
        self.threshold_label.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.puncCount_label = tk.Label(root, text='', font=("Courier", 16))
        self.puncCount_label.place(x=10, y=10)

        self.calibration_label = tk.Label(frame , text='' , font = ('Courier' , 16))
        self.calibration_label.pack(side=tk.BOTTOM , padx = 10 , pady = 10 )

        self.setup_animation()

    def find_arduino_port(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if "Arduino" in port.description:
                return serial.Serial(port.device, 57600, timeout=1)
        return None

    def setup_animation(self):
        self.ani = animation.FuncAnimation(self.fig, self.animate , interval=50)

    def animate(self , i):
        if not self.running or self.paused or not self.serial_port:
            return

        self.serial_port.write(b'g')
        arduino_data_string = self.serial_port.readline().decode('ascii').strip()
        current_time = time.time() - self.start_time
        print(f"Received data: {arduino_data_string}")

        try:
            arduino_data_int = int(arduino_data_string)
            self.time_list.append(current_time)
            self.time_list_plot.append(current_time)
            self.data_list.append(arduino_data_int)
            self.data_list_plot.append(arduino_data_int)
            self.dataQueue.append(arduino_data_int)

            if len(self.dataQueue) >= 3 and self.dataQueue[-3] < self.puncThreshold:
                if self.dataQueue[-2] <= self.highThreshold and self.dataQueue[-1] <= self.highThreshold:
                    self.puncCount += 1
                    self.updatePuncCount()
                    if self.startpuncflag is None:
                        self.startpuncflag = time.time() - self.start_time
                        self.event_list.append(self.startpuncflag)


            if arduino_data_int < self.threshold:
                if self.last_below_threshold_time is None:
                    self.last_below_threshold_time = time.time()
                else:
                    elapsed_time = time.time() - self.last_below_threshold_time
                    if elapsed_time >= 3:
                        self.great_flag = True
            else:
                self.great_flag = False
                self.last_below_threshold_time = None

        except ValueError as e:
            print(f"Error parsing data: {e}")
            return

        #while self.time_list_plot and (current_time - self.time_list_plot[0]) > 10:
            #self.time_list_plot.pop(0)
            #self.data_list_plot.pop(0)

        self.ax.clear()
        self.ax.plot(self.time_list_plot, self.data_list_plot)

        if len(self.data_list_plot) >= 50:
            slicedata = list(islice(self.data_list_plot , len(self.data_list_plot)-50 , len(self.data_list_plot)))
            mean = np.mean(slicedata)
            self.ax.set_ylim([mean - 0.002 * mean, mean + 0.002 * mean])
        else:
            mean = np.mean(self.data_list_plot)
            self.ax.set_ylim([mean - 0.002 * mean, mean + 0.002 * mean])
        self.ax.set_xlim([max(0, current_time - 10), current_time])

        self.ax.axhline(y=self.threshold, color='r', linestyle='--', label=f'Threshold: {self.threshold}')
        self.ax.axhline(y=self.highThreshold, color='k', linestyle='--', label=f'High Threshold :{self.highThreshold}')
        self.ax.axhline(y=self.puncThreshold, color='m', linestyle='--', label=f'Puncture Threshold : {self.puncThreshold}')
        self.ax.legend()

        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def start_sequence(self):
        self.calibrate_threshold()
        self.start_countdown()
        #self.start_animation()

    def start_countdown(self):
        if self.countdown_label is None:
            self.countdown_label = tk.Label(self.root, font=("Courier", 36))
        elif self.countdown_label.winfo_ismapped():
            self.countdown_label.pack_forget()

        self.countdown_label.pack()
        self.countdown_seconds = 5
        self.countdown_start_time = time.time()
        self.countdown_tick()

    def countdown_tick(self):
        if self.countdown_label and self.countdown_seconds > 0:
            self.countdown_label.config(text=f"Starting in {self.countdown_seconds} seconds")
            self.countdown_seconds -= 1
            self.root.after(1000, self.countdown_tick)
        elif self.countdown_seconds <= 0:
            print('finish countdown')
            self.countdown_label.pack_forget()
            self.start_animation()
            self.countdown_animation()
            print('start animation')

    def countdown_animation(self):
        if self.countdown_label is None:
            self.countdown_label = tk.Label(self.root, font=("Courier", 36))
        elif self.countdown_label.winfo_ismapped():
            self.countdown_label.pack_forget()

        self.countdown_label.pack()
        self.countdown_start_time = time.time()
        self.update_countdown_label()

    def updatePuncCount(self):
        self.puncCount_label.config(text=f"Puncture Count: {self.puncCount}")

    def update_countdown_label(self):
        if self.running:
            elapsed_time = time.time() - self.countdown_start_time
            self.countdown_time = 60 - int(elapsed_time)
            if self.countdown_time >= 0:
                minutes = self.countdown_time // 60
                seconds = self.countdown_time % 60
                self.countdown_label.config(text=f"Countdown: {minutes:02}:{seconds:02}")
                self.root.after(1000, self.update_countdown_label)
            else:
                self.countdown_label.config(text="Countdown Finished")

    def start_animation(self):
        if not self.running:
            self.start_time = time.time() - (self.time_list_plot[-1] if self.time_list_plot else 0)
            #port flushing
            self.serial_port.close()
            time.sleep(0.5)
            self.serial_port = self.find_arduino_port()
            if self.serial_port:
                print(f"Connected to {self.serial_port.port}")
            else:
                print("Arduino not found")
            #finish port flushing
            self.running = True
            self.paused = False



    def stop_animation(self):
        self.running = False
        self.paused = True
        self.last_below_threshold_time = None
        if self.great_flag:
            self.event_list.append((time.time() - self.start_time, "Great blood drawing finished"))
            messagebox.showinfo('Result' , 'Great blood drawing!!!')
            self.great_flag = False
        else:
            messagebox.showinfo('Result' , 'Not fall below threshold')

    def reset_graph(self):
        self.running = False
        self.paused = False
        self.time_list_plot.clear()
        self.data_list_plot.clear()
        self.first_exceeding_value = None
        self.notified = False
        self.ax.clear()
        self.ax.set_ylim([6000, self.chart_threshold])
        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def calibrate_threshold(self):
        self.calibration_label.config(text='Calibrating threshold')
        self.root.update_idletasks()

        self.serial_port = self.find_arduino_port()
        if self.serial_port:
            print(f"Connected to {self.serial_port.port}")
        else:
            print("Arduino not found")

        initial_data = []
        start_time = time.time()
        while time.time() - start_time < 10:
            self.serial_port.write(b'g')
            arduino_data_string = self.serial_port.readline().decode('ascii').strip()
            try:
                arduino_data_int = int(arduino_data_string)
                initial_data.append(arduino_data_int )
            except ValueError:
                pass
        if initial_data:
            mean = np.mean(initial_data)
            self.threshold = mean - 0.0012 * mean
            self.highThreshold = mean + 0.00035 * mean
            self.puncThreshold = mean - 0.0003 * mean
            self.threshold_label.config(text=f'Threshold: {self.threshold:.2f}')
        else:
            self.threshold = 15000
            self.threshold_label.config(text=f"Threshold: {self.threshold}")
        self.calibration_label.config(text='')

    def schedule_auto_calibration(self):
        self.root.after(30000, self.auto_calibrate)

    def auto_calibrate(self):
        if self.running and not self.paused:
            self.calibrate_threshold()
        self.schedule_auto_calibration()

    def export_data(self):
        export_path = filedialog.askdirectory(title="Select Export Directory")
        if export_path:
            try:
                raw_data_path = os.path.join(export_path, "raw_data.csv")
                with open(raw_data_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Time (s)', 'Value', 'Event'])
                    for t, v in zip(self.time_list, self.data_list):
                        event = ''
                        for event_time, event_desc in self.event_list:
                            if t == event_time:
                                event = event_desc
                                break
                        writer.writerow([t, v, event])

                graph_path = os.path.join(export_path, "graph.png")
                self.fig.savefig(graph_path)

                messagebox.showinfo("Export Successful", f"Data exported to {export_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    plotter = RealTimePlotter(root)
    root.mainloop()