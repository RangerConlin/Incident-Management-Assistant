"""Tkinter demo showcasing incident theme switching."""
import tkinter as tk
from tkinter import ttk

from styles.adapters.tkinter_adapter import apply_theme, set_mode, apply_treeview_status

root = tk.Tk()
root.title('Incident — Theme Demo')

apply_theme(root, 'light')

# toggle
mode = tk.StringVar(value='light')

def _toggle():
    set_mode(mode.get())

ttk.Radiobutton(root, text='Light', value='light', variable=mode, command=_toggle).pack(anchor='w')
ttk.Radiobutton(root, text='Dark', value='dark', variable=mode, command=_toggle).pack(anchor='w')

frame = ttk.Frame(root)
frame.pack(padx=10, pady=10, fill='both', expand=True)

ttk.Button(frame, text='Accent Button').grid(row=0, column=0, padx=4)
ttk.Entry(frame).grid(row=0, column=1, padx=4)

nb = ttk.Notebook(frame)
nb.grid(row=1, column=0, columnspan=2, pady=4, sticky='ew')
nb.add(ttk.Frame(nb), text='One')
nb.add(ttk.Frame(nb), text='Two')

columns = ('kind', 'status')
Tree = ttk.Treeview(frame, columns=columns, show='headings', height=4)
for col in columns:
    Tree.heading(col, text=col.title())
Tree.grid(row=2, column=0, columnspan=2, sticky='nsew')

rows = [
    ('TEAM', 'AVAILABLE'),
    ('TEAM', 'ASSIGNED'),
    ('TASK', 'IN PROGRESS'),
    ('TASK', 'COMPLETE'),
]

for item in rows:
    iid = Tree.insert('', 'end', values=item)
    apply_treeview_status(Tree, iid, item[0], item[1])

root.mainloop()
