import sys
import threading
import time
import builtins
import os

class MultiProjectParseProgress:
    def __init__(self, max_slots=4):
        self.max_slots = max_slots
        self.slots = [{"label": "", "done": 0, "total": 0, "status": "idle", "rate": 0.0, "eta": 0.0, "last_print_time": 0} for _ in range(max_slots)]
        self.lock = threading.Lock()
        self.is_tty = sys.stderr.isatty()
        self.primed = False
        self._original_print = None

    def __enter__(self):
        if self.is_tty:
            try:
                if os.name == 'nt':
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    kernel32.SetConsoleMode(kernel32.GetStdHandle(-12), 7)
                    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                pass
                
        self._original_print = builtins.print
        builtins.print = self.print_log
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        builtins.print = self._original_print
        if self.is_tty and self.primed:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def print_log(self, *args, **kwargs):
        """Intercepts print calls to render them above the progress block."""
        with self.lock:
            if not self.is_tty or not self.primed:
                self._original_print(*args, **kwargs)
                return
                
            # Erase the fixed block
            sys.stderr.write(f"\033[{self.max_slots}A")
            for _ in range(self.max_slots):
                sys.stderr.write("\033[K\n")
            sys.stderr.write(f"\033[{self.max_slots}A")
            sys.stderr.flush()
            
            # Print the actual message
            self._original_print(*args, **kwargs)
            sys.stdout.flush()
            
            # Redraw the block below
            self.primed = False
            self._redraw_unlocked()

    def acquire_slot(self, project_label: str, total: int) -> int:
        with self.lock:
            for i, slot in enumerate(self.slots):
                if slot["status"] in ("idle", "done"):
                    slot["label"] = project_label
                    slot["total"] = total
                    slot["done"] = 0
                    slot["rate"] = 0.0
                    slot["eta"] = 0.0
                    slot["status"] = "active"
                    slot["last_print_time"] = time.time()
                    self._redraw_unlocked()
                    return i
            return -1

    def update(self, slot_idx: int, done: int, total: int, rate: float, eta_s: float):
        if slot_idx < 0 or slot_idx >= self.max_slots:
            return
            
        with self.lock:
            slot = self.slots[slot_idx]
            slot["done"] = done
            slot["total"] = total
            slot["rate"] = rate
            slot["eta"] = eta_s
            
            now = time.time()
            if self.is_tty:
                # Throttle redraw to ~200ms
                if now - slot["last_print_time"] >= 0.2 or done == total:
                    slot["last_print_time"] = now
                    self._redraw_unlocked()
            else:
                # Fallback non-TTY: max once every 5 seconds
                if now - slot["last_print_time"] >= 5.0 or done == total:
                    slot["last_print_time"] = now
                    pct = (done * 100) // total if total else 100
                    sys.stderr.write(f"[{slot['label']}] {pct}% ({done}/{total})\n")
                    sys.stderr.flush()

    def finish(self, slot_idx: int, message: str = ""):
        if slot_idx < 0 or slot_idx >= self.max_slots:
            return
        with self.lock:
            slot = self.slots[slot_idx]
            slot["status"] = "done"
            if self.is_tty:
                self._redraw_unlocked()
            else:
                sys.stderr.write(f"[{slot['label']}] 100% DONE\n")
                sys.stderr.flush()

    def _redraw_unlocked(self):
        if not self.is_tty:
            return
            
        if not self.primed:
            for _ in range(self.max_slots):
                sys.stderr.write("\n")
            self.primed = True
            
        sys.stderr.write(f"\033[{self.max_slots}A")
        
        for slot in self.slots:
            if slot["status"] == "idle":
                sys.stderr.write("\033[K\n")
            else:
                label = slot["label"]
                if len(label) > 65:
                    label = "..." + label[-62:]
                
                total = slot["total"]
                done = slot["done"]
                pct = (done * 100) // total if total else 0
                
                if slot["status"] == "done":
                    line = f"{label} {pct}% DONE"
                else:
                    line = f"{label} {pct}% ({done}/{total}) | {slot['rate']:.1f} files/s | ETA {slot['eta']:.0f}s"
                
                sys.stderr.write(f"{line}\033[K\n")
        sys.stderr.flush()
