import os
import tkinter as tk
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from tkinter import messagebox
from typing import Dict

# File path for auto-saving input history
HISTORY_FILE = "shifts_history.txt"


# --- Entity Layer ---
class Shift:
    """Represents a single work shift."""

    def __init__(
            self, day: int, month: int, start_time: str, end_time: str, tip: float = 0.0
    ):
        self.day = day
        self.month = month
        self.start_time = start_time
        self.end_time = end_time
        self.tip = tip

    @property
    def gross_hours(self) -> float:
        """Calculates shift duration in hours, handling overnight shifts."""
        start_h, start_m = map(int, self.start_time.split(":"))
        end_h, end_m = map(int, self.end_time.split(":"))

        start_dt = datetime(2026, self.month, self.day, start_h, start_m)
        end_dt = datetime(2026, self.month, self.day, end_h, end_m)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        return (end_dt - start_dt).total_seconds() / 3600.0


class BaseBreakCalculator(ABC):
    @abstractmethod
    def calculate_net_hours(self, gross_hours: float) -> float:
        pass


class ThresholdBreakCalculator(BaseBreakCalculator):
    """Deducts break time if gross hours reach or exceed a given threshold."""

    def __init__(
            self, threshold_hours: float = 9.0, break_minutes: float = 45.0
    ):
        self.threshold_hours = threshold_hours
        self.break_hours = break_minutes / 60.0

    def calculate_net_hours(self, gross_hours: float) -> float:
        if gross_hours >= self.threshold_hours:
            return gross_hours - self.break_hours
        return gross_hours


class ShiftParser:
    """Parses raw input lines into Shift entities."""

    @staticmethod
    def parse_line(line: str) -> Shift:
        tip = 0.0
        # Support both English ("tip") and Hebrew ("טיפ") keywords
        if "+" in line:
            parts = line.split("+")
            line_main = parts[0].strip()
            tip_part = (
                parts[1]
                .lower()
                .replace("tip", "")
                .replace("טיפ", "")
                .strip()
            )
            tip = float(tip_part)
        else:
            line_main = line.strip()

        date_str, start_str, end_str = [p.strip() for p in line_main.split("-")]
        day, month = [int(x) for x in date_str.split(".")]

        return Shift(
            day=day,
            month=month,
            start_time=start_str,
            end_time=end_str,
            tip=tip,
        )


# --- Service Layer ---
class MonthlyAggregator:
    """Processes shifts and aggregates statistics per month."""

    def __init__(
            self, hourly_rate: float, break_calculator: BaseBreakCalculator
    ):
        self.hourly_rate = hourly_rate
        self.break_calculator = break_calculator

    def process_raw_text(self, raw_text: str) -> Dict[int, Dict[str, float]]:
        shifts = []
        for line in raw_text.strip().split("\n"):
            if line.strip():
                try:
                    shift = ShiftParser.parse_line(line)
                    shifts.append(shift)
                except Exception:
                    continue

        stats = {}
        for shift in shifts:
            net_hours = self.break_calculator.calculate_net_hours(
                shift.gross_hours
            )
            if shift.month not in stats:
                stats[shift.month] = {"hours": 0.0, "tips": 0.0}

            stats[shift.month]["hours"] += net_hours
            stats[shift.month]["tips"] += shift.tip

        return stats


class StorageManager:
    """Handles saving and loading shift history to a local file."""

    @staticmethod
    def save_history(text: str, file_path: str = HISTORY_FILE):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

    @staticmethod
    def load_history(file_path: str = HISTORY_FILE) -> str:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""


# --- GUI Layer (Tkinter) ---
class SalaryAppGUI(tk.Tk):
    def __init__(self, hourly_rate: float = 40.22):
        super().__init__()
        self.title("Shift & Salary Calculator")
        self.geometry("850x650")

        self.hourly_rate = hourly_rate
        self.break_calc = ThresholdBreakCalculator(
            threshold_hours=9.0, break_minutes=45.0
        )
        self.aggregator = MonthlyAggregator(self.hourly_rate, self.break_calc)

        self._build_ui()
        self._load_saved_data()

    def _build_ui(self):
        # Header
        header = tk.Label(
            self,
            text="Monthly Salary & Shift Calculator",
            font=("Helvetica", 16, "bold"),
            fg="#2C3E50",
        )
        header.pack(pady=10)

        # Main Layout Frame
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        # Left Column: Input Box
        input_frame = tk.LabelFrame(
            main_frame, text=" Shift Input ", font=("Helvetica", 11, "bold")
        )
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.txt_input = tk.Text(input_frame, font=("Consolas", 10), width=35)
        self.txt_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Right Column: Output Box & Visual Bar Chart
        output_frame = tk.LabelFrame(
            main_frame,
            text=" Monthly Summary & Chart ",
            font=("Helvetica", 11, "bold"),
        )
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        self.txt_output = tk.Text(
            output_frame, font=("Consolas", 10), state=tk.DISABLED
        )
        self.txt_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bottom Action Bar
        btn_calc = tk.Button(
            self,
            text="Calculate & Save",
            font=("Helvetica", 12, "bold"),
            bg="#27AE60",
            fg="white",
            command=self._on_calculate,
        )
        btn_calc.pack(fill=tk.X, padx=20, pady=10)

    def _load_saved_data(self):
        """Loads persistent data into the input text area on startup."""
        saved_text = StorageManager.load_history()
        if saved_text:
            self.txt_input.insert(tk.END, saved_text)

    def _on_calculate(self):
        raw_text = self.txt_input.get("1.0", tk.END)
        monthly_data = self.aggregator.process_raw_text(raw_text)

        if not monthly_data:
            messagebox.showwarning(
                "Warning", "No valid shift data found in the input box."
            )
            return

        StorageManager.save_history(raw_text)

        max_hours = max(data["hours"] for data in monthly_data.values())

        report = ""
        for month in sorted(monthly_data.keys()):
            hours = monthly_data[month]["hours"]
            tips = monthly_data[month]["tips"]
            salary = hours * self.hourly_rate
            total = salary + tips

            h = int(hours)
            m = round((hours - h) * 60)

            # Generate visual text bar chart
            bar_length = (
                int((hours / max_hours) * 18) if max_hours > 0 else 0
            )
            bar_chart = "█" * bar_length

            report += f"=== Month {month} ===\n"
            report += f"Chart:        [{bar_chart:<18}] {hours:.1f}h\n"
            report += f"Net Hours:    {h}h {m}m\n"
            report += f"Base Salary:  ₪{salary:,.2f}\n"
            if tips > 0:
                report += f"Tips:         ₪{tips:,.2f}\n"
            report += f"Total Pay:    ₪{total:,.2f}\n\n"

        self.txt_output.config(state=tk.NORMAL)
        self.txt_output.delete("1.0", tk.END)
        self.txt_output.insert(tk.END, report)
        self.txt_output.config(state=tk.DISABLED)


if __name__ == "__main__":
    app = SalaryAppGUI(hourly_rate=40.22)
    app.mainloop()
