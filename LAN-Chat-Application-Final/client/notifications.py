
import tkinter as tk

def toast(root, title, message):
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    f = tk.Frame(win, bg="#102A56", padx=16, pady=10)
    f.pack()
    tk.Label(f,text=title,bg="#102A56",fg="white",font=("Segoe UI",10,"bold")).pack(anchor="w")
    tk.Label(f,text=message,bg="#102A56",fg="#D8E5FA",font=("Segoe UI",9)).pack(anchor="w")
    root.update_idletasks()
    x=root.winfo_x()+root.winfo_width()-win.winfo_reqwidth()-20
    y=root.winfo_y()+60
    win.geometry(f"+{x}+{y}")
    root.after(2500, win.destroy)
