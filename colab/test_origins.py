import sys
sys.path.append('backend')
from geometry_util import resolve_zone_origins

zones = [
    {'name': 'Office', 'length': 6, 'width': 8, 'height': 4},
    {'name': 'Meeting Room', 'length': 6, 'width': 4, 'height': 4, 'relative_to': 'Office', 'direction': 'North'},
    {'name': 'Lobby', 'length': 5, 'width': 8, 'height': 4, 'relative_to': 'Office', 'direction': 'East'},
    {'name': 'Rest Room', 'length': 5, 'width': 4, 'height': 4, 'relative_to': 'Lobby', 'direction': 'North'},
]

origins = resolve_zone_origins(zones)
print('\nOrigins:', origins)
print('\nExpected layout (top-down view):')
zone_map = {z['name']: z for z in zones}
for name, (ox, oy, oz) in origins.items():
    z = zone_map[name]
    L, W = z['length'], z['width']
    print(f'  {name}: X=[{ox:.1f}, {ox+L:.1f}]  Y=[{oy:.1f}, {oy+W:.1f}]')
