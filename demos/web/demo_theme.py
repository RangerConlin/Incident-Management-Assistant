"""NiceGUI demo showcasing incident theme switching."""
from nicegui import ui
from styles.adapters.nicegui_adapter import init_theme, set_mode, status_css_class

init_theme('light')

with ui.header().classes('items-center justify-between'):
    ui.label('Incident — Theme Demo')
    ui.toggle(['light', 'dark'], value='light', on_change=lambda e: set_mode(e.value))

with ui.row().classes('gap-4 p-4'):
    with ui.card():
        ui.label('Card content')
    ui.button('Accent Button', on_click=lambda: None).classes('primary')
    ui.input('Sample input')
    with ui.tabs() as tabs:
        ui.tab('One')
        ui.tab('Two')

rows = [
    ('team', 'available'),
    ('team', 'assigned'),
    ('task', 'in progress'),
    ('task', 'complete'),
]

columns = [
    {'name': 'kind', 'label': 'Kind', 'field': 'kind'},
    {'name': 'status', 'label': 'Status', 'field': 'status'},
]

with ui.table(columns=columns, rows=[{'kind': k, 'status': s} for k, s in rows]) as table:
    for (k, s), row in zip(rows, table.rows):
        row.classes(status_css_class(k, s))

ui.run()
