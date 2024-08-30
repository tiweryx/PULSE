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
import tkinter.simpledialog as simpledialog
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
        self.time_list_plot = deque([], maxlen=50)
        self.data_list = []
        self.data_list_plot = deque([], maxlen=50)
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
        self.dataQueue = deque([], maxlen=4)
        self.puncLabel = 0
        self.puncEvent = False
        self.startpuncflag = None
        self.Mawindow = 50
        self.malist = deque([], maxlen=50)

        self.punctureStateList = []
        self.punctureStateTime = []

        self.event_list = []  # List to store important events
        self.puncture_state_active = False
        self.last_data_value = 0
        self.stable_data_count = 0
        self.stable_data_threshold = 5

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

        self.calibration_label = tk.Label(frame, text='', font=('Courier', 16))
        self.calibration_label.pack(side=tk.BOTTOM, padx=10, pady=10)

        self.state_label = tk.Label(root , text="State : waiting" , font=('Courier' , 20))
        self.state_label.place(x=10 , y=50)

        self.stablecountlabel = tk.Label(root , text=f'Stable data count : {self.stable_data_count}' , font=('Courier' , 20))
        self.stablecountlabel.place(x=10 , y=20)

        self.setup_animation()

    def find_arduino_port(self):
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if "Arduino" in port.description:
                return serial.Serial(port.device, 57600, timeout=1)
        return None

    def setup_animation(self):
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=50)

    def animate(self, i):
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
            self.malist.append(arduino_data_int)

            if len(self.malist) == self.Mawindow:
                Mavg = np.mean(self.malist)
                self.threshold = Mavg - (0.0015 * Mavg)
                self.highThreshold = Mavg + (0.00025 * Mavg)
                self.puncThreshold = Mavg - (0.00029 * Mavg)

            if len(self.dataQueue) >= 3 and self.dataQueue[-3] < self.puncThreshold:
                if self.dataQueue[-2] <= self.highThreshold and self.dataQueue[-1] <= self.highThreshold:
                    self.puncCount += 1
                    self.updatePuncCount()
                    if self.startpuncflag is None:
                        self.startpuncflag = time.time() - self.start_time
                        self.event_list.append(self.startpuncflag)
            # check state
            if arduino_data_int < self.threshold:
                if self.last_below_threshold_time is None:
                    self.last_below_threshold_time = time.time()
                else:
                    elapsed_time = time.time() - self.last_below_threshold_time
                    if elapsed_time >= 3:
                        self.puncture_state()
                    elif elapsed_time < 3:
                        self.touch_state()
            else:
                if self.last_below_threshold_time is not None:
                    elapsed_time = time.time() - self.last_below_threshold_time
                    if elapsed_time < 3:
                        self.touch_state()
                    self.last_below_threshold_time = None
                    #self.puncture_state_active = False
                    #print('reset puncture state')


            # detect data in puncture state
            if self.puncture_state_active:
                self.punctureStateList.append(arduino_data_int)
                self.punctureStateTime.append(current_time)
                if arduino_data_int > self.threshold:
                    if arduino_data_int == self.last_data_value:
                        self.stable_data_count += 1
                        self.updatestable()
                        if self.stable_data_count >= self.stable_data_threshold:
                            self.stop_animation()  # Stop the animation if data is stable

                    else:
                        self.stable_data_count = 0
                        print('reset stable count')
                    self.last_data_value = arduino_data_int
                    print('record last data')
            #else: #puncture state false
                    # if data goes above threshold, reset puncture state
                    #print('reset puncture state')
                    #self.puncture_state_active = False
                    #self.last_data_value = 0

        except ValueError as e:
            print(f"Error parsing data: {e}")
            return

        # while self.time_list_plot and (current_time - self.time_list_plot[0]) > 10:
        # self.time_list_plot.pop(0)
        # self.data_list_plot.pop(0)

        self.ax.clear()
        self.ax.plot(self.time_list_plot, self.data_list_plot)

        if len(self.data_list_plot) >= 50:
            slicedata = list(islice(self.data_list_plot, len(self.data_list_plot) - 50, len(self.data_list_plot)))
            mean = np.mean(slicedata)
            self.ax.set_ylim([mean - 0.002 * mean, mean + 0.002 * mean])
        else:
            mean = np.mean(self.data_list_plot)
            self.ax.set_ylim([mean - 0.002 * mean, mean + 0.002 * mean])
        self.ax.set_xlim([max(0, current_time - 10), current_time])

        self.ax.axhline(y=self.threshold, color='r', linestyle='--', label=f'Threshold: {self.threshold}')
        self.ax.axhline(y=self.highThreshold, color='k', linestyle='--', label=f'High Threshold :{self.highThreshold}')
        self.ax.axhline(y=self.puncThreshold, color='m', linestyle='--',
                        label=f'Puncture Threshold : {self.puncThreshold}')
        self.ax.legend()

        self.ax.set_title("Arduino Data")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.canvas.draw()

    def touch_state(self):
        print("Touch State detected")
        self.puncture_state_active = False
        self.state_label.config(text=f'State : {self.puncture_state_active}')

    def puncture_state(self):
        print("Puncture State detected")
        self.puncture_state_active = True
        self.state_label.config(text=f'State : {self.puncture_state_active}')

    def start_sequence(self):
        self.calibrate_threshold()
        self.start_countdown()
        # self.start_animation()

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

    def updatestable(self):
        self.stablecountlabel.config(text=f'Stable punc count : {self.stable_data_count}')

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
            # port flushing
            self.serial_port.close()
            time.sleep(0.5)
            self.serial_port = self.find_arduino_port()
            if self.serial_port:
                print(f"Connected to {self.serial_port.port}")
            else:
                print("Arduino not found")
            # finish port flushing
            self.running = True
            self.paused = False

    def stop_animation(self):
        self.running = False
        self.paused = True
        self.last_below_threshold_time = None
        puncture_start_time = self.punctureStateTime[0]
        min_value = min(self.punctureStateList)
        min_value_index = self.punctureStateList.index(min_value)
        min_value_time = self.punctureStateTime[min_value_index]
        elapsed_time = min_value_time - puncture_start_time
        if elapsed_time > 6 :
            self.event_list.append((time.time() - self.start_time, "Great blood drawing finished"))
            messagebox.showinfo('Result', 'Great blood drawing!!!')
            self.great_flag = False
        else:
            messagebox.showinfo('Result', 'Try again')

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
                initial_data.append(arduino_data_int)
            except ValueError:
                pass
        if initial_data:
            mean = np.mean(initial_data)
            self.threshold = mean - 0.0012 * mean
            self.highThreshold = mean + 0.00035 * mean
            self.puncThreshold = mean - 0.0003 * mean
            self.threshold_label.config(text=f'Threshold: {self.threshold:.2f}')
        else:
            self.threshold = 1500
            self.threshold_label.config(text=f"Threshold: {self.threshold}")
        self.calibration_label.config(text='')

    import tkinter.simpledialog as simpledialog

    def export_data(self):
        # Prompt the user to enter a file name
        file_name = simpledialog.askstring("Input", "Enter file name for export (without extension):")

        if not file_name:
            messagebox.showwarning("Export Canceled", "No file name provided. Export canceled.")
            return

        export_path = filedialog.askdirectory(title="Select Export Directory")
        if export_path:
            try:
                combined_data_path = os.path.join(export_path, f"{file_name}.csv")
                with open(combined_data_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write header
                    writer.writerow(['Time (s)', 'Value', 'Puncture Time (s)', 'Puncture Value'])

                    # Determine the maximum length among the lists
                    max_length = max(len(self.time_list), len(self.data_list), len(self.punctureStateTime),
                                     len(self.punctureStateList))

                    # Pad lists to ensure they all have the same length
                    time_list_padded = self.time_list + [None] * (max_length - len(self.time_list))
                    data_list_padded = self.data_list + [None] * (max_length - len(self.data_list))
                    punctureStateTime_padded = self.punctureStateTime + [None] * (
                                max_length - len(self.punctureStateTime))
                    punctureStateList_padded = self.punctureStateList + [None] * (
                                max_length - len(self.punctureStateList))

                    # Write rows
                    for t, d, pt, pd in zip(time_list_padded, data_list_padded, punctureStateTime_padded,
                                            punctureStateList_padded):
                        writer.writerow([t, d, pt, pd])

                messagebox.showinfo("Export Successful", f"Data exported to {os.path.join(export_path, file_name)}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    plotter = RealTimePlotter(root)
    root.mainloop()