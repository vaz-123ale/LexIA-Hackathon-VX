"""Gera geometrias vetoriais de referência a partir do Natural Earth low-res.
As posições dos ativos são fictícias e não correspondem a instalações reais.
"""
from pathlib import Path
import json
try:
    import geopandas as gpd
except ImportError:
    raise SystemExit('Geopandas necessário apenas para regenerar o mapa; o JSON já acompanha o pacote.')
SOURCE=Path('/opt/pyvenv/lib/python3.13/site-packages/pyogrio/tests/fixtures/naturalearth_lowres/naturalearth_lowres.shp')
OUTPUT=Path(__file__).resolve().parents[1]/'web'/'map.json'
base=gpd.read_file(SOURCE)
base=base[(base.continent=='South America') | (base.name=='Brazil')]
W,H=690,560
lon_min,lon_max,lat_min,lat_max=-82,-30,-38,15

def point(x,y):return (round((x-lon_min)/(lon_max-lon_min)*W,1),round((lat_max-y)/(lat_max-lat_min)*H,1))
def polypath(coords):
    strings=[]
    for poly in coords:
        pp=[point(x,y) for x,y in poly]
        if not pp:continue
        strings.append('M'+'L'.join(f'{x},{y}' for x,y in pp)+'Z')
    return ' '.join(strings)
def polygons(geom):
    if geom.geom_type=='Polygon':geoms=[geom]
    elif geom.geom_type=='MultiPolygon':geoms=list(geom.geoms)
    else:return []
    return [[list(p.exterior.coords)] for p in geoms]
features=[]
for _,r in base.iterrows():
    for rings in polygons(r.geometry):
        features.append({'name':r['name'],'brazil':r['name']=='Brazil','path':polypath(rings)})
OUTPUT.write_text(json.dumps({'width':W,'height':H,'bounds':[lon_min,lat_min,lon_max,lat_max],'features':features},ensure_ascii=False),encoding='utf8')
print('Mapa gerado:',OUTPUT)
