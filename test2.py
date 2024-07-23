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
import itertools
from animate import animate

class RealTimePlotter:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Plotter")
        self.root.state('zoomed')

        self.running = False
        self.paused = False
        self.start_time = None
        self.time_list = []
        self.time_list_plot = deque(maxlen=1000)
        self.data_list = []
        self.data_list_plot = deque(maxlen=1000)
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
        self.dataQueue = deque(maxlen=3)
        self.puncLabel = 0
        self.start_puncture_time = None
        self.event_list = []

        self.serial_port = self.find_arduino_port()
        if self.serial_port:
            print(f"Connected to {self.serial_port.port}")
        else:
            print("Arduino not found")

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

        self.line, = self.ax.plot([], [], 'r-')
        self.background = None  # This will hold the background image for blitting

        self.setup_animation()

    def find_arduino_port(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if "Arduino" in port.description:
                return serial.Serial(port.device, 2400, timeout=1)
        return None

    def setup_animation(self):
        self.ani = animation.FuncAnimation(self.fig, self.animate_wrapper, init_func=self.init_plot, interval=200, blit=True)

    def init_plot(self):
        self.ax.set_xlim(0, 10)
        self.ax.set_ylim(6000, self.chart_threshold)
        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.line.set_data([], [])
        # Capture the background once for blitting
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)
        return self.line,

    def animate_wrapper(self, i):
        return animate(self, i)

    def start_sequence(self):
        self.calibrate_threshold()
        self.start_countdown()

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
            self.countdown_label.config(text=f"Elapsed Time: {int(elapsed_time)} seconds")
            self.root.after(1000, self.update_countdown_label)

    def start_animation(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.start_time = time.time()
            self.ani.event_source.start()

    def stop_animation(self):
        self.running = False
        self.paused = False
        self.ani.event_source.stop()

    def reset_graph(self):
        self.time_list.clear()
        self.time_list_plot.clear()
        self.data_list.clear()
        self.data_list_plot.clear()
        self.line.set_data([], [])
        self.fig.canvas.draw()

    def export_data(self):
        data = zip(self.time_list, self.data_list)
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            with open(file_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Value"])
                writer.writerows(data)
            messagebox.showinfo("Export Data", "Data exported successfully")

    def calibrate_threshold(self):
        arduino_data_list = []
        start_time = time.time()
        while time.time() - start_time < 5:
            self.serial_port.write(b'g')
            arduino_data_string = self.serial_port.readline().decode('ascii').strip()
            try:
                arduino_data_float = float(arduino_data_string)
                arduino_data_list.append(arduino_data_float)
            except ValueError as e:
                print(f"Error parsing data during calibration: {e}")

        if arduino_data_list:
            self.threshold = np.mean(arduino_data_list) + 3 * np.std(arduino_data_list)
            self.chart_threshold = self.threshold * 1.5
            self.puncThreshold = np.mean(arduino_data_list) + np.std(arduino_data_list)
            self.highThreshold = np.mean(arduino_data_list) + 2 * np.std(arduino_data_list)
            self.threshold_label.config(text=f"Threshold: {self.threshold}")
            self.calibration_label.config(text='calibration complete')
        else:
            print("No data received during calibration.")

if __name__ == "__main__":
    root = tk.Tk()
    plotter = RealTimePlotter(root)
    root.mainloop()
