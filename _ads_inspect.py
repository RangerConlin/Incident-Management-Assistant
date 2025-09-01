import sys
print('Python:', sys.version)
try:
    import PySide6QtAds as ads
    print('PySide6QtAds file:', getattr(ads, '__file__', None))
    print('Has CDockWidget:', hasattr(ads, 'CDockWidget'))
    if hasattr(ads, 'CDockWidget'):
        import inspect
        cls = ads.CDockWidget
        print('CDockWidget init signature:', end=' ')
        try:
            print(inspect.signature(cls.__init__))
        except Exception as e:
            print('inspect failed:', e)
        print('CDockWidget doc:', inspect.getdoc(cls) or 'No doc')
        try:
            from inspect import getmembers
            print('Members:', [n for n, _ in getmembers(cls) if n.startswith('__init__')])
        except Exception:
            pass
except Exception as e:
    print('Import error:', e)
