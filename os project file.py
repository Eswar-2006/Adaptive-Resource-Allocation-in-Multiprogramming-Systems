import psutil
import time
import random
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

DEFAULT_DB_NAME = "allocation_logs.db"
DEFAULT_TICK_COUNT = 15
DEFAULT_TICK_DELAY_SECONDS = 1
MIN_PREDICTION_POINTS = 5
DEFAULT_PROCESS_SPECS = [
    (1, 'CPU-Intensive'),
    (2, 'Memory-Intensive'),
    (3, 'Balanced'),
    (4, 'CPU-Intensive'),
    (5, 'Balanced')
]

class VirtualProcess:
    """Simulates a process with specific resource demands."""
    def __init__(self, pid, workload_type):
        self.pid = pid
        self.workload_type = workload_type # 'CPU-Intensive', 'Memory-Intensive', 'Balanced'
        self.priority = 5 # 1 (Highest) to 10 (Lowest)
        self.allocated_cpu = 0.0
        self.allocated_mem = 0.0 # in MB
        self.wait_time = 0

    def generate_requests(self):
        # Generate resource requests based on workload profile
        if self.workload_type == 'CPU-Intensive':
            req_cpu = random.uniform(15.0, 40.0) # High CPU demand
            req_mem = random.uniform(10.0, 50.0)
        elif self.workload_type == 'Memory-Intensive':
            req_cpu = random.uniform(1.0, 10.0)
            req_mem = random.uniform(200.0, 800.0) # High Mem demand
        else: # Balanced
            req_cpu = random.uniform(5.0, 20.0)
            req_mem = random.uniform(50.0, 300.0)
            
        return req_cpu, req_mem

class AdaptiveAllocator:
    """
    Simulates an OS scheduler that adaptively allocates real available 
    system resources to virtual processes.
    """
    def __init__(self, db_name=DEFAULT_DB_NAME):
        self.db_name = db_name
        self.processes = self._create_default_processes()
        self.conn = None
        self.cursor = None
        self._setup_db()
        psutil.cpu_percent(interval=0.1) # Prime the CPU monitor

    def _create_default_processes(self):
        return [VirtualProcess(pid, workload_type) for pid, workload_type in DEFAULT_PROCESS_SPECS]

    def _setup_db(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self._initialize_allocation_stats_table()
        self.conn.commit()

    def _initialize_allocation_stats_table(self):
        self.cursor.execute("DROP TABLE IF EXISTS AllocationStats")
        self.cursor.execute("""
            CREATE TABLE AllocationStats (
                timestamp TEXT,
                real_avail_cpu REAL,
                real_avail_mem REAL,
                total_requested_cpu REAL,
                total_requested_mem REAL,
                total_allocated_cpu REAL,
                total_allocated_mem REAL
            )
        """)

    def _measure_system_capacity(self):
        real_used_cpu = psutil.cpu_percent(interval=None)
        real_avail_cpu = max(0.0, 100.0 - real_used_cpu)

        mem_info = psutil.virtual_memory()
        real_avail_mem_mb = mem_info.available / (1024 * 1024)

        return real_avail_cpu, real_avail_mem_mb

    def _collect_requests(self):
        requests = []
        total_req_cpu = 0
        total_req_mem = 0

        for process in self.processes:
            if process.wait_time > 2:
                process.priority = max(1, process.priority - 2)
                process.wait_time = 0

            req_cpu, req_mem = process.generate_requests()
            requests.append({'process': process, 'req_cpu': req_cpu, 'req_mem': req_mem})
            total_req_cpu += req_cpu
            total_req_mem += req_mem

        requests.sort(key=lambda item: item['process'].priority)
        return requests, total_req_cpu, total_req_mem

    def _apply_request_allocation(self, request, avail_cpu_pool, avail_mem_pool):
        process = request['process']
        cpu_needed = request['req_cpu']
        mem_needed = request['req_mem']

        if avail_cpu_pool >= cpu_needed:
            process.allocated_cpu = cpu_needed
            avail_cpu_pool -= cpu_needed
        else:
            process.allocated_cpu = avail_cpu_pool
            avail_cpu_pool = 0

        if avail_mem_pool >= mem_needed:
            process.allocated_mem = mem_needed
            avail_mem_pool -= mem_needed
        else:
            process.allocated_mem = avail_mem_pool
            avail_mem_pool = 0

        if process.allocated_cpu < cpu_needed or process.allocated_mem < mem_needed:
            process.wait_time += 1
        else:
            process.priority = min(10, process.priority + 1)
            process.wait_time = 0

        return avail_cpu_pool, avail_mem_pool

    def _print_request_status(self, process, cpu_needed, mem_needed):
        now_ts = pd.Timestamp.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{now_ts}] PID {process.pid} ({process.workload_type[:4]:^4}) | Prio: {process.priority:2d} | "
              f"Req: {cpu_needed:4.1f}% CPU, {mem_needed:4.1f}MB Mem | "
              f"Alloc: {process.allocated_cpu:4.1f}% CPU, {process.allocated_mem:4.1f}MB Mem")

    def _record_telemetry(self, real_avail_cpu, real_avail_mem_mb, total_req_cpu, total_req_mem,
                          total_alloc_cpu, total_alloc_mem):
        timestamp = pd.Timestamp.now().strftime("%H:%M:%S")
        try:
            self.cursor.execute("INSERT INTO AllocationStats VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (timestamp, real_avail_cpu, real_avail_mem_mb,
                                 total_req_cpu, total_req_mem, total_alloc_cpu, total_alloc_mem))
            self.conn.commit()
        except sqlite3.Error as error:
            print(f"Telemetry write failed: {error}")

    def _describe_trend(self, slope):
        if slope > 0.05:
            return "increasing"
        if slope < -0.05:
            return "decreasing"
        return "stable"

    def allocate_resources(self, tick):
        real_avail_cpu, real_avail_mem_mb = self._measure_system_capacity()
        requests, total_req_cpu, total_req_mem = self._collect_requests()

        avail_cpu_pool = real_avail_cpu
        avail_mem_pool = real_avail_mem_mb
        total_alloc_cpu = 0
        total_alloc_mem = 0

        print(f"\n--- Tick {tick} | Real Avail: [CPU: {real_avail_cpu:.1f}%] [Mem: {real_avail_mem_mb:.1f} MB] ---")
        
        for request in requests:
            process = request['process']
            cpu_needed = request['req_cpu']
            mem_needed = request['req_mem']

            avail_cpu_pool, avail_mem_pool = self._apply_request_allocation(
                request, avail_cpu_pool, avail_mem_pool
            )

            total_alloc_cpu += process.allocated_cpu
            total_alloc_mem += process.allocated_mem
            self._print_request_status(process, cpu_needed, mem_needed)

        self._record_telemetry(
            real_avail_cpu,
            real_avail_mem_mb,
            total_req_cpu,
            total_req_mem,
            total_alloc_cpu,
            total_alloc_mem,
        )

    def get_data(self):
        try:
            return pd.read_sql("SELECT * FROM AllocationStats", self.conn)
        except (sqlite3.Error, ValueError) as error:
            print(f"Unable to read allocation data: {error}")
            return pd.DataFrame()

    def predict_next_tick(self):
        """Uses ML to predict system resource availability trend for next tick."""
        df = self.get_data()
        if len(df) < MIN_PREDICTION_POINTS:
            print("\n[ML Predict] Not enough data to generate a trend prediction.")
            return
        
        X = np.arange(len(df)).reshape(-1, 1)
        model_cpu = LinearRegression().fit(X, df["real_avail_cpu"].values)
        model_mem = LinearRegression().fit(X, df["real_avail_mem"].values)
        
        next_t = np.array([[len(df)]])
        pred_cpu = max(0, min(100, model_cpu.predict(next_t)[0]))
        pred_mem = max(0, model_mem.predict(next_t)[0])
        cpu_trend = self._describe_trend(model_cpu.coef_[0])
        mem_trend = self._describe_trend(model_mem.coef_[0])

        print(
            "\n[ML Predict] Trend for Next Tick -> "
            f"Est. Avail CPU: {pred_cpu:.1f}% ({cpu_trend}), "
            f"Est. Avail Mem: {pred_mem:.1f} MB ({mem_trend})"
        )

    def plot_analytics(self):
        df = self.get_data()
        if df.empty:
            print("No telemetry data available for plotting.")
            return

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # CPU Subplot
        ax1.plot(df.index, df["real_avail_cpu"], label="Real Avail CPU Capacity", linestyle="--", color="grey", linewidth=2)
        ax1.plot(df.index, df["total_requested_cpu"], label="Requested CPU (All Procs)", color="orange", marker='o')
        ax1.plot(df.index, df["total_allocated_cpu"], label="Allocated CPU (All Procs)", color="blue", marker='s')
        ax1.set_ylabel("CPU (%)")
        ax1.set_title("Adaptive CPU Allocation vs Real Constraints")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Memory Subplot
        ax2.plot(df.index, df["real_avail_mem"], label="Real Avail Mem Capacity", linestyle="--", color="grey", linewidth=2)
        ax2.plot(df.index, df["total_requested_mem"], label="Requested Mem (All Procs)", color="red", marker='o')
        ax2.plot(df.index, df["total_allocated_mem"], label="Allocated Mem (All Procs)", color="green", marker='s')
        ax2.set_ylabel("Memory (MB)")
        ax2.set_title("Adaptive Memory Allocation vs Real Constraints")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.xlabel("Simulation Tick")
        fig.suptitle("Adaptive Resource Allocation Analysis", fontsize=12, fontweight="bold")
        plt.tight_layout()
        plt.show()

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None
                self.cursor = None

def main():
    print("Initializing Adaptive OS Resource Allocation Simulation...")
    print("Binding simulated requests to REAL system availability bounds.\n")
    
    allocator = AdaptiveAllocator()
    try:
        for tick in range(1, DEFAULT_TICK_COUNT + 1):
            allocator.allocate_resources(tick)
            time.sleep(DEFAULT_TICK_DELAY_SECONDS)
            
        allocator.predict_next_tick()
        
        print("\nOpening analytical plot (Close the plot window to exit program)...")
        allocator.plot_analytics()
    except Exception as e:
        print(f"Error during simulation: {e}")
    finally:
        allocator.close()

if __name__ == "__main__":
    main()