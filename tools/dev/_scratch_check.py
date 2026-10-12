from ui.widgets import registry as W
spec = W.REGISTRY['launchbutton']
w = spec.component()
print(spec.title, w)
print(w.get_config())
