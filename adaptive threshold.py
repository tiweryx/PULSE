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

class RealTimePlotter:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Plotter")
        self.root.geometry("1200x800")  # Set initial window size
        self.running = False
        self.paused = False
        self.start_time = None
        self.time_list = deque(maxlen=1000)
        self.data_list = deque(maxlen=1000)
        self.threshold = 15000
        self.chart_threshold = 650000

        self.serial_port = self.find_arduino_port()
        if self.serial_port:
            print(f"Connected to {self.serial_port.port}")
        else:
            print("Arduino not found")

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        frame = tk.Frame(root)
        frame.pack()

        tk.Label(frame, text="Real-Time Graph", font=("Courier", 32)).pack()

        tk.Button(frame, text="Start", command=self.start_sequence).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Reset Graph", command=self.reset_graph).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Export Data", command=self.export_data).pack(side=tk.LEFT, padx=10, pady=10)

        self.threshold_label = tk.Label(frame, text=f"Threshold: {self.threshold}", font=("Courier", 16))
        self.threshold_label.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.calibration_label = tk.Label(frame, text='', font=('Courier', 16))
        self.calibration_label.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.setup_animation()

    def find_arduino_port(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if "Arduino" in port.description:
                return serial.Serial(port.device, 57600, timeout=1)
        return None

    def setup_animation(self):
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=200, blit=True)

    def animate(self, i):
        if not self.running or self.paused or not self.serial_port:
            return

        self.serial_port.write(b'g')
        arduino_data_string = self.serial_port.readline().decode('ascii').strip()
        current_time = time.time() - self.start_time

        try:
            arduino_data_float = float(arduino_data_string)
            self.time_list.append(current_time)
            self.data_list.append(arduino_data_float)
        except ValueError as e:
            print(f"Error parsing data: {e}")
            return

        self.ax.clear()
        self.ax.plot(self.time_list, self.data_list)

        mean = np.mean(self.data_list)
        self.ax.set_ylim([mean - 0.002 * mean, mean + 0.002 * mean])
        self.ax.set_xlim([max(0, current_time - 10), current_time])

        self.ax.axhline(y=self.threshold, color='r', linestyle='--', label=f'Threshold: {self.threshold}')
        self.ax.legend()

        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def start_sequence(self):
        self.calibrate_threshold()
        self.start_animation()

    def start_animation(self):
        if not self.running:
            self.start_time = time.time()
            self.running = True
            self.paused = False

    def stop_animation(self):
        self.running = False
        self.paused = True

    def reset_graph(self):
        self.running = False
        self.paused = False
        self.time_list.clear()
        self.data_list.clear()
        self.ax.clear()
        self.ax.set_ylim([6000, self.chart_threshold])
        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def calibrate_threshold(self):
        self.calibration_label.config(text='Calibrating threshold')
        self.root.update_idletasks()

        initial_data = []
        start_time = time.time()
        while time.time() - start_time < 10:
            self.serial_port.write(b'g')
            arduino_data_string = self.serial_port.readline().decode('ascii').strip()
            try:
                arduino_data_float = float(arduino_data_string)
                initial_data.append(arduino_data_float)
            except ValueError:
                pass
        if initial_data:
            mean = np.mean(initial_data)
            self.threshold = mean - 0.0012 * mean
            self.threshold_label.config(text=f'Threshold: {self.threshold:.2f}')
        else:
            self.threshold = 15000
            self.threshold_label.config(text=f"Threshold: {self.threshold}")
        self.calibration_label.config(text='')

    def export_data(self):
        export_path = filedialog.askdirectory(title="Select Export Directory")
        if export_path:
            try:
                raw_data_path = os.path.join(export_path, "raw_data.csv")
                with open(raw_data_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Time (s)', 'Value'])
                    writer.writerows(zip(self.time_list, self.data_list))

                graph_path = os.path.join(export_path, "graph.png")
                self.fig.savefig(graph_path)

                messagebox.showinfo("Export Successful", f"Data exported to {export_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    plotter = RealTimePlotter(root)
    root.mainloop()
