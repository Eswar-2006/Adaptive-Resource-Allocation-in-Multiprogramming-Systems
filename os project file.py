import psutil
import time
import random
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

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
    def __init__(self, db_name="allocation_logs.db"):
        self.db_name = db_name
        self.processes = [
            VirtualProcess(1, 'CPU-Intensive'),
            VirtualProcess(2, 'Memory-Intensive'),
            VirtualProcess(3, 'Balanced'),
            VirtualProcess(4, 'CPU-Intensive'),
            VirtualProcess(5, 'Balanced')
        ]
        self.conn = None
        self.cursor = None
        self._setup_db()
        psutil.cpu_percent(interval=0.1) # Prime the CPU monitor

    def _setup_db(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.cursor.execute("DROP TABLE IF EXISTS AllocationStats") # Reset for fresh simulation
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
        self.conn.commit()

    def allocate_resources(self, tick):
        # 1. Measure REAL time system resources constraints
        real_used_cpu = psutil.cpu_percent(interval=None)
        # Cap usable CPU to what's actually free on the real machine
        real_avail_cpu = max(0.0, 100.0 - real_used_cpu) 
        
        mem_info = psutil.virtual_memory()
        real_avail_mem_mb = mem_info.available / (1024 * 1024)

        requests = []
        total_req_cpu = 0
        total_req_mem = 0

        # 2. Gather process requests and apply Aging (prevent starvation)
        for p in self.processes:
            if p.wait_time > 2:
                # Priority boost if starved for multiple ticks
                p.priority = max(1, p.priority - 2)
                p.wait_time = 0
                
            req_cpu, req_mem = p.generate_requests()
            requests.append({'process': p, 'req_cpu': req_cpu, 'req_mem': req_mem})
            total_req_cpu += req_cpu
            total_req_mem += req_mem

        # 3. Priority-based Allocation
        requests.sort(key=lambda item: item['process'].priority)

        avail_cpu_pool = real_avail_cpu
        avail_mem_pool = real_avail_mem_mb
        
        total_alloc_cpu = 0
        total_alloc_mem = 0

        print(f"\n--- Tick {tick} | Real Avail: [CPU: {real_avail_cpu:.1f}%] [Mem: {real_avail_mem_mb:.1f} MB] ---")
        
        for req in requests:
            p = req['process']
            cpu_needed = req['req_cpu']
            mem_needed = req['req_mem']

            # CPU Allocation
            if avail_cpu_pool >= cpu_needed:
                p.allocated_cpu = cpu_needed
                avail_cpu_pool -= cpu_needed
            else:
                p.allocated_cpu = avail_cpu_pool
                avail_cpu_pool = 0

            # Memory Allocation
            if avail_mem_pool >= mem_needed:
                p.allocated_mem = mem_needed
                avail_mem_pool -= mem_needed
            else:
                p.allocated_mem = avail_mem_pool
                avail_mem_pool = 0

            total_alloc_cpu += p.allocated_cpu
            total_alloc_mem += p.allocated_mem

            # Feedback Loop: Modify priority based on allocation success
            if p.allocated_cpu < cpu_needed or p.allocated_mem < mem_needed:
                p.wait_time += 1 # Starved
            else:
                p.priority = min(10, p.priority + 1) # Fully satisfied, lower priority
                p.wait_time = 0

            now_ts = pd.Timestamp.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{now_ts}] PID {p.pid} ({p.workload_type[:4]:^4}) | Prio: {p.priority:2d} | "
                  f"Req: {cpu_needed:4.1f}% CPU, {mem_needed:4.1f}MB Mem | "
                  f"Alloc: {p.allocated_cpu:4.1f}% CPU, {p.allocated_mem:4.1f}MB Mem")

        # 4. Record Telemetry
        timestamp = pd.Timestamp.now().strftime("%H:%M:%S")
        self.cursor.execute("INSERT INTO AllocationStats VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (timestamp, real_avail_cpu, real_avail_mem_mb, 
                             total_req_cpu, total_req_mem, total_alloc_cpu, total_alloc_mem))
        self.conn.commit()

    def get_data(self):
        return pd.read_sql("SELECT * FROM AllocationStats", self.conn)

    def predict_next_tick(self):
        """Uses ML to predict system resource availability trend for next tick."""
        df = self.get_data()
        if len(df) < 5: return
        
        X = np.arange(len(df)).reshape(-1, 1)
        model_cpu = LinearRegression().fit(X, df["real_avail_cpu"].values)
        model_mem = LinearRegression().fit(X, df["real_avail_mem"].values)
        
        next_t = np.array([[len(df)]])
        pred_cpu = max(0, min(100, model_cpu.predict(next_t)[0]))
        pred_mem = max(0, model_mem.predict(next_t)[0])

        print(f"\n[ML Predict] Trend for Next Tick -> Est. Avail CPU: {pred_cpu:.1f}%, Est. Avail Mem: {pred_mem:.1f} MB")

    def plot_analytics(self):
        df = self.get_data()
        if df.empty: return

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
        plt.tight_layout()
        plt.show()

    def close(self):
        if self.conn: self.conn.close()

def main():
    print("Initializing Adaptive OS Resource Allocation Simulation...")
    print("Binding simulated requests to REAL system availability bounds.\n")
    
    allocator = AdaptiveAllocator()
    try:
        for tick in range(1, 16): # 15 ticks of simulation
            allocator.allocate_resources(tick)
            time.sleep(1) # Simulate real-time delay
            
        allocator.predict_next_tick()
        
        print("\nOpening analytical plot (Close the plot window to exit program)...")
        allocator.plot_analytics()
    except Exception as e:
        print(f"Error during simulation: {e}")
    finally:
        allocator.close()

if __name__ == "__main__":
    main()