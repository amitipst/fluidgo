"""Check fga_approval.py source in container"""
import inspect, sys
sys.path.insert(0, '/app')
# Force reload
import importlib
import app.routers.fga_approval as m
importlib.reload(m)
src = open('/app/app/routers/fga_approval.py').read()
# Find the freeze_period function and show the fix
idx = src.find('limit(1)')
print("Has .limit(1):", idx > 0)
print("Context:", src[max(0,idx-100):idx+50])
