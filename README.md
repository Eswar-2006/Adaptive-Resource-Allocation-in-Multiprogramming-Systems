# 🚀 Adaptive Resource Allocation in Multiprogramming Systems

> 🧠 Simulating intelligent OS-level resource allocation with real-time logging & database tracking

---

## 📌 Overview

This project models how an operating system dynamically allocates resources in a multiprogramming environment.
It tracks process execution, resource usage, and allocation decisions using persistent storage.

✨ Designed to demonstrate:
- Efficient CPU & resource utilization
- Real-time allocation logging
- OS-level scheduling concepts

---

## 🧩 Project Structure

```
.
├── os project file.py # Main simulation script
├── allocation_logs.db # Stores allocation history
├── resource_logs.db # Stores resource usage logs
└── README.md # Documentation
```

---

## ⚙️ Features

- Dynamic resource allocation simulation
- Multiprogramming environment modeling
- Real-time pressure monitoring for CPU and memory
- Bottleneck detection using rolling pressure trends
- Two-pass adaptive reallocation to reduce starvation
- SQLite-based persistent logging
- Lightweight & easy to run
- Clean and extendable Python code

---

## 🛠️ Tech Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.9+ |
| Database | SQLite |
| Concept Domain | Operating Systems |

---

## ▶️ How to Run

```bash
# Clone the repository
git clone https://github.com/Eswar-2006/Adaptive-Resource-Allocation-in-Multiprogramming-Systems.git

# Navigate to project directory
cd Adaptive-Resource-Allocation-in-Multiprogramming-Systems

# Run the simulation
python "os project file.py"
```

## 🧪 Runtime Notes

- The simulation runs for 15 ticks by default.
- Runtime configuration is validated before execution begins.
- Allocation telemetry is written to SQLite on every tick.
- CPU and memory pressure are tracked each tick using EWMA smoothing.
- Bottleneck state is reported as `none`, `cpu`, `memory`, or `cpu+mem`.
- A second allocation pass redistributes remaining resources to unmet weighted demand.
- Trend prediction is shown after enough samples are collected.

## 💻 Interactive Terminal Mode (Real-Time + User Input)

You can now run a fully terminal-based real-time allocator with live demographs and manual control:

```bash
python nexus7_terminal.py
```

Supported commands inside terminal mode:

- `help`
- `mode manual` or `mode auto`
- `set <pid> <cpu%> <memMB>`
- `del <pid>`
- `clear`
- `quit`

Example:

```text
mode manual
set 1 30 400
set 3 15 220
```

In manual mode, only user-entered PID requests are used for allocation; any PID without an entry requests `0`.