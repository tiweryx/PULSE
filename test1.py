#import neccessary module
import time
import serial
import serial.tools.list_ports
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
from tkinter import messagebox
import numpy as np
import csv
from datetime import datetime
import os

class RealTimePlotter:
    #define flags and variable
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Plotter")
        self.running = False
        self.paused = False
        self.start_time = None
        self.time_list = []
        self.data_list = []
        self.threshold = 15000
        self.chart_threshold = 650000  # Higher threshold for plotting
        self.first_exceeding_value = None  # First exceeding value in each round
        self.notified = False  # Flag to track if notification has been sent for current sequence

        self.serial_port = self.find_arduino_port() #arduino serial connection
        if self.serial_port:
            print(f"Connected to {self.serial_port.port}")
        else:
            print("Arduino not found")

        #plotting window
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack()

        frame = tk.Frame(root)
        frame.pack()

        tk.Label(frame, text="Real-Time Graph", font=("Courier", 32)).pack()

        #button packgage
        tk.Button(frame, text="Start", command=self.start_countdown).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Stop", command=self.stop_animation).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Reset Graph", command=self.reset_graph).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(frame, text="Export Data", command=self.export_data).pack(side=tk.LEFT, padx=10, pady=10)


        #thresold display
        self.threshold_label = tk.Label(frame, text=f"Threshold: {self.threshold}", font=("Courier", 16))
        self.threshold_label.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.setup_animation()

    #arduino autoconnect
    def find_arduino_port(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if "Arduino" in port.description:
                return serial.Serial(port.device, 57600, timeout=1)
        return None

    def setup_animation(self):
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=100)


    #graph plotting function
    def animate(self, i):
        if not self.running or self.paused or not self.serial_port:
            return

        self.serial_port.write(b'g')
        arduino_data_string = self.serial_port.readline().decode('ascii').strip()
        current_time = time.time() - self.start_time
        print(f"Received data: {arduino_data_string}")

        try:
            arduino_data_float = float(arduino_data_string)
            self.time_list.append(current_time)
            self.data_list.append(arduino_data_float)

        except ValueError as e:
            print(f"Error parsing data: {e}")
            return

        #display only last ten second
        while self.time_list and (current_time - self.time_list[0]) > 10:
            self.time_list.pop(0)
            self.data_list.pop(0)

        #setting graph parameter
        self.ax.clear()
        self.ax.plot(self.time_list, self.data_list)
        if len(self.data_list) >= 50:
            mean = np.mean(self.data_list[-50:])
            stdev = np.std(self.data_list[-50:])
            self.ax.set_ylim([mean - 2 * stdev, mean + 2 * stdev])
        else:
            mean = np.mean(self.data_list)
            stdev = np.std(self.data_list)
            self.ax.set_ylim([mean - 2 * stdev, mean + 2 * stdev])
        self.ax.set_xlim([max(0, current_time - 10), current_time])

        # Add the threshold line
        self.ax.axhline(y=self.threshold, color='r', linestyle='--', label=f'Threshold: {self.threshold}')
        self.ax.legend()

        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def start_countdown(self):
        self.countdown_label = tk.Label(self.root, font=("Courier", 36))
        self.countdown_label.pack()
        self.countdown_seconds = 5
        self.countdown_tick()

    def countdown_tick(self):
        if self.countdown_seconds > 0:
            self.countdown_label.config(text=f"Starting in {self.countdown_seconds} seconds")
            self.countdown_seconds -= 1
            self.root.after(1000, self.countdown_tick)
        else:
            self.countdown_label.pack_forget()
            self.calibrate_threshold()
            self.start_animation()

    def start_animation(self):
        if not self.running:
            self.start_time = time.time() - (self.time_list[-1] if self.time_list else 0)
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
        self.first_exceeding_value = None  # Reset stored value
        self.notified = False  # Reset notification flag
        self.ax.clear()
        self.ax.set_ylim([6000, self.chart_threshold])  # Reset y-axis limit
        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def calibrate_threshold(self):
        initial_data = []
        start_time = time.time()
        while time.time() - start_time < 10:  # Collect data for 10 seconds
            self.serial_port.write(b'g')
            arduino_data_string = self.serial_port.readline().decode('ascii').strip()
            try:
                arduino_data_float = float(arduino_data_string)
                initial_data.append(arduino_data_float)
            except ValueError:
                pass
        if initial_data:
            mean = np.mean(initial_data)
            std_dev = np.std(initial_data)
            self.threshold = mean + 3 * std_dev  # Example threshold calculation
            self.threshold_label.config(text=f'Threshold: {self.threshold:.2f}')
        else:
            self.threshold = 15000
            self.threshold_label.config(text=f"Threshold: {self.threshold}")

    def export_data(self):
        export_directory = "D:\Termproj\pythonProject1\.venv\data export"  # Set your desired export path here
        if not os.path.exists(export_directory):
            os.makedirs(export_directory)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Export raw data to CSV
        csv_filename = os.path.join(export_directory, f"data_{timestamp}.csv")
        with open(csv_filename, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['Time (s)', 'Value'])
            for time_val, data_val in zip(self.time_list, self.data_list):
                csvwriter.writerow([time_val, data_val])
        print(f"Raw data exported to {csv_filename}")
        # Export graph to image
        image_filename = os.path.join(export_directory, f"graph_{timestamp}.png")
        self.fig.savefig(image_filename)
        print(f"Graph exported to {image_filename}")

# Main execution
root = tk.Tk()
app = RealTimePlotter(root)
root.mainloop()