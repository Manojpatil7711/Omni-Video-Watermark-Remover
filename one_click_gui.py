import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def select_input():
    path = filedialog.askopenfilename(
        filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm")]
    )
    if path:
        input_var.set(path)
        p = Path(path)
        output_var.set(str(p.with_name(f"{p.stem}_clean.mp4")))


def start_processing():
    inp, out = input_var.get().strip(), output_var.get().strip()
    if not inp or not out:
        messagebox.showerror("Error", "Please select input and output files.")
        return

    btn.config(state="disabled", text="Processing...")
    progress.start(10)

    def worker():
        try:
            root_dir = Path(__file__).resolve().parent
            cmd = [
                sys.executable, "-m", "omni_watermark.cli",
                "--input", inp, "--output", out,
                "--mode", mode_var.get(), "--engine", engine_var.get(),
            ]
            subprocess.run(cmd, cwd=root_dir, check=True)
            root.after(0, lambda: messagebox.showinfo("Success", f"Clean video saved:\n{out}"))
        except subprocess.CalledProcessError as exc:
            root.after(0, lambda: messagebox.showerror("Error", f"Processing failed (exit {exc.returncode}). Check the terminal for details."))
        except Exception as exc:
            root.after(0, lambda: messagebox.showerror("Error", str(exc)))
        finally:
            root.after(0, lambda: (progress.stop(), btn.config(state="normal", text="Start Processing")))

    threading.Thread(target=worker, daemon=True).start()


root = tk.Tk()
root.title("Omni Video Watermark Remover")
root.geometry("560x330")
root.resizable(False, False)

input_var = tk.StringVar()
output_var = tk.StringVar()
mode_var = tk.StringVar(value="static")
engine_var = tk.StringVar(value="fast")

frame = ttk.Frame(root, padding=16)
frame.pack(fill="both", expand=True)

ttk.Label(frame, text="Input Video").pack(anchor="w")
row = ttk.Frame(frame)
row.pack(fill="x", pady=(4, 12))
ttk.Entry(row, textvariable=input_var).pack(side="left", fill="x", expand=True)
ttk.Button(row, text="Browse", command=select_input).pack(side="left", padx=(8, 0))

ttk.Label(frame, text="Output Video").pack(anchor="w")
ttk.Entry(frame, textvariable=output_var).pack(fill="x", pady=(4, 12))

ttk.Label(frame, text="Watermark Mode").pack(anchor="w")
mode_row = ttk.Frame(frame)
mode_row.pack(anchor="w", pady=4)
tk.Radiobutton(mode_row, text="Static", variable=mode_var, value="static").pack(side="left")
tk.Radiobutton(mode_row, text="Dynamic", variable=mode_var, value="dynamic").pack(side="left", padx=16)

ttk.Label(frame, text="Processing Engine").pack(anchor="w", pady=(8, 0))
engine_row = ttk.Frame(frame)
engine_row.pack(anchor="w", pady=4)
tk.Radiobutton(engine_row, text="Fast / CPU", variable=engine_var, value="fast").pack(side="left")
tk.Radiobutton(engine_row, text="AI / GPU", variable=engine_var, value="ai").pack(side="left", padx=16)

progress = ttk.Progressbar(frame, mode="indeterminate")
progress.pack(fill="x", pady=14)
btn = ttk.Button(frame, text="Start Processing", command=start_processing)
btn.pack(fill="x", ipady=7)

root.mainloop()
