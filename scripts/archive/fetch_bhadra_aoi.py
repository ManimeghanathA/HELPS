#!/usr/bin/env python3
"""
HELPSs Phase 1 - AOI acquisition
Fetches the current OpenStreetMap relation for Bhadra WLS (relation 9329791)
and converts its multipolygon members into GeoJSON.

Run:
    python scripts/fetch_bhadra_aoi.py

Output:
    data/processed/aoi/bhadra_wls_osm.geojson
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen
from shapely.geometry import LineString, Polygon, MultiPolygon, mapping
from shapely.ops import unary_union, polygonize

RELATION_ID = 9329791
URL = f"https://api.openstreetmap.org/api/0.6/relation/{RELATION_ID}/full"
OUT = Path("data/processed/aoi/bhadra_wls_osm.geojson")

def fetch_xml():
    req = Request(URL, headers={"User-Agent": "HELPSs-Phase1/1.0"})
    with urlopen(req, timeout=60) as response:
        return response.read()

def parse_osm(xml_bytes):
    root = ET.fromstring(xml_bytes)
    nodes = {}
    ways = {}
    relation = None

    for el in root:
        if el.tag == "node":
            nodes[el.attrib["id"]] = (
                float(el.attrib["lon"]),
                float(el.attrib["lat"])
            )
        elif el.tag == "way":
            refs = [n.attrib["ref"] for n in el.findall("nd")]
            tags = {t.attrib["k"]: t.attrib["v"] for t in el.findall("tag")}
            ways[el.attrib["id"]] = {"refs": refs, "tags": tags}
        elif el.tag == "relation" and el.attrib["id"] == str(RELATION_ID):
            relation = el

    if relation is None:
        raise RuntimeError("Bhadra relation was not found in the OSM response.")

    members = []
    for m in relation.findall("member"):
        if m.attrib["type"] == "way":
            members.append((m.attrib["role"], m.attrib["ref"]))

    return nodes, ways, members

def build_polygons(nodes, ways, members):
    outers, inners = [], []

    for role, wid in members:
        way = ways.get(wid)
        if not way:
            continue
        coords = [nodes[r] for r in way["refs"] if r in nodes]
        if len(coords) < 2:
            continue
        line = LineString(coords)
        (inners if role == "inner" else outers).append(line)

    def rings(lines):
        if not lines:
            return []
        merged = unary_union(lines)
        return list(polygonize(merged))

    outer_polys = rings(outers)
    inner_polys = rings(inners)

    if not outer_polys:
        raise RuntimeError("No outer polygon could be reconstructed.")

    result = []
    for p in outer_polys:
        holes = [list(q.exterior.coords) for q in inner_polys
                 if p.contains(q.representative_point())]
        result.append(Polygon(p.exterior.coords, holes))

    geom = unary_union(result)
    return geom

def main():
    xml = fetch_xml()
    nodes, ways, members = parse_osm(xml)
    geom = build_polygons(nodes, ways, members)

    feature = {
        "type": "Feature",
        "properties": {
            "aoi_id": "bhadra_v1",
            "name": "Bhadra Wildlife Sanctuary / Tiger Reserve",
            "osm_relation_id": RELATION_ID,
            "source": "OpenStreetMap"
        },
        "geometry": mapping(geom)
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(feature, f, indent=2)

    print("AOI polygon written to:", OUT)
    print("Geometry type:", geom.geom_type)
    print("Valid:", geom.is_valid)
    print("Bounds:", geom.bounds)

if __name__ == "__main__":
    main()
