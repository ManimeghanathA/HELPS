import sqlite3
import struct
import math

def utm_to_latlon(easting, northing, zone=43, northern=True):
    # WGS84 parameters
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = (a*a - b*b) / (a*a)
    e_prime_sq = (a*a - b*b) / (b*b)
    k0 = 0.9996
    
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    
    M = y / k0
    mu = M / (a * (1.0 - e_sq/4.0 - 3.0*e_sq*e_sq/64.0 - 5.0*e_sq**3/256.0))
    
    e1 = (1.0 - math.sqrt(1.0 - e_sq)) / (1.0 + math.sqrt(1.0 - e_sq))
    
    J1 = (3.0*e1/2.0 - 27.0*e1**3/32.0)
    J2 = (21.0*e1**2/16.0 - 55.0*e1**4/32.0)
    J3 = (151.0*e1**3/96.0)
    J4 = (1097.0*e1**4/512.0)
    
    fp = mu + J1*math.sin(2.0*mu) + J2*math.sin(4.0*mu) + J3*math.sin(6.0*mu) + J4*math.sin(8.0*mu)
    
    sin_fp = math.sin(fp)
    cos_fp = math.cos(fp)
    tan_fp = math.tan(fp)
    
    C1 = e_prime_sq * cos_fp * cos_fp
    T1 = tan_fp * tan_fp
    N1 = a / math.sqrt(1.0 - e_sq * sin_fp * sin_fp)
    R1 = a * (1.0 - e_sq) / ((1.0 - e_sq * sin_fp * sin_fp) ** 1.5)
    D = x / (N1 * k0)
    
    # Latitude
    fact1 = N1 * tan_fp / R1
    fact2 = D*D / 2.0
    fact3 = (5.0 + 3.0*T1 + 10.0*C1 - 4.0*C1*C1 - 9.0*e_prime_sq) * (D**4) / 24.0
    fact4 = (61.0 + 90.0*T1 + 298.0*C1 + 45.0*T1*T1 - 252.0*e_prime_sq - 3.0*C1*C1) * (D**6) / 720.0
    
    lat = fp - fact1 * (fact2 - fact3 + fact4)
    
    # Longitude
    fact2 = D
    fact3 = (1.0 + 2.0*T1 + C1) * (D**3) / 6.0
    fact4 = (5.0 - 2.0*C1 + 28.0*T1 - 3.0*C1*C1 + 8.0*e_prime_sq + 24.0*T1*T1) * (D**5) / 120.0
    
    lon = lon0 + (fact2 - fact3 + fact4) / cos_fp
    
    return math.degrees(lat), math.degrees(lon)

def latlon_to_utm(lat_deg, lon_deg, zone=43):
    # WGS84 parameters
    a = 6378137.0
    f = 1.0 / 298.257223563
    b = a * (1.0 - f)
    e_sq = (a*a - b*b) / (a*a)
    e_prime_sq = (a*a - b*b) / (b*b)
    k0 = 0.9996
    
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    tan_lat = math.tan(lat)
    
    N = a / math.sqrt(1.0 - e_sq * sin_lat * sin_lat)
    T = tan_lat * tan_lat
    C = e_prime_sq * cos_lat * cos_lat
    A = (lon - lon0) * cos_lat
    
    M = a * (
        (1.0 - e_sq/4.0 - 3.0*e_sq*e_sq/64.0 - 5.0*e_sq**3/256.0) * lat
        - (3.0*e_sq/8.0 + 3.0*e_sq*e_sq/32.0 + 45.0*e_sq**3/1024.0) * math.sin(2*lat)
        + (15.0*e_sq*e_sq/256.0 + 45.0*e_sq**3/1024.0) * math.sin(4*lat)
        - (35.0*e_sq**3/3072.0) * math.sin(6*lat)
    )
    
    easting = k0 * N * (
        A + (1.0 - T + C) * (A**3)/6.0
        + (5.0 - 18.0*T + T*T + 72.0*C - 58.0*e_prime_sq) * (A**5)/120.0
    ) + 500000.0
    
    northing = k0 * (
        M + N * tan_lat * (
            (A**2)/2.0
            + (5.0 - T + 9.0*C + 4.0*C*C) * (A**4)/24.0
            + (61.0 - 58.0*T + T*T + 600.0*C - 330.0*e_prime_sq) * (A**6)/720.0
        )
    )
    
    return easting, northing

def parse_gpkg_geom(blob):
    if not blob or len(blob) < 8:
        return None
    # Header: magic 'GP' (2 bytes), version (1 byte), flags (1 byte), srs_id (4 bytes, int32)
    flags = blob[3]
    envelope_type = (flags >> 1) & 0x07
    byte_order = flags & 0x01 # 1 = little endian, 0 = big endian
    header_len = 8
    if envelope_type == 1:
        header_len += 32 # minx, maxx, miny, maxy
    elif envelope_type in (2, 3):
        header_len += 48
    elif envelope_type == 4:
        header_len += 64
        
    wkb = blob[header_len:]
    if len(wkb) < 5:
        return None
    
    wkb_order = '<' if wkb[0] == 1 else '>'
    geom_type = struct.unpack(f'{wkb_order}I', wkb[1:5])[0]
    
    # 1 = Point, 3 = Polygon, 6 = MultiPolygon
    if geom_type % 1000 == 1: # Point
        x, y = struct.unpack(f'{wkb_order}dd', wkb[5:21])
        return ('Point', x, y)
    elif geom_type % 1000 == 3: # Polygon
        # Read num_rings
        num_rings = struct.unpack(f'{wkb_order}I', wkb[5:9])[0]
        offset = 9
        rings = []
        for _ in range(min(num_rings, 1)): # exterior ring
            num_points = struct.unpack(f'{wkb_order}I', wkb[offset:offset+4])[0]
            offset += 4
            pts = []
            for _ in range(num_points):
                px, py = struct.unpack(f'{wkb_order}dd', wkb[offset:offset+16])
                offset += 16
                pts.append((px, py))
            rings.append(pts)
        return ('Polygon', rings)
    return None

def test():
    gpkg = r"c:\Users\Nehar\Desktop\HELPS\Codes\data\processed\Bhadra\sentinel2\2026-06-01\bhadra_final_open_land_zones.gpkg"
    conn = sqlite3.connect(gpkg)
    c = conn.cursor()
    c.execute("SELECT fid, geom, parent_candidate_id, zone_number, max_clear_radius_m, max_clear_diameter_m FROM maximum_clearance_centers LIMIT 5")
    rows = c.fetchall()
    for r in rows:
        fid, blob, parent_id, zone_no, radius, dia = r
        geom = parse_gpkg_geom(blob)
        if geom and geom[0] == 'Point':
            easting, northing = geom[1], geom[2]
            lat, lon = utm_to_latlon(easting, northing)
            print(f"FID {fid}: easting={easting:.1f}, northing={northing:.1f} -> lat={lat:.5f}, lon={lon:.5f}, max_dia={dia:.1f}m")
            # verify roundtrip
            e2, n2 = latlon_to_utm(lat, lon)
            print(f"   roundtrip diff: {abs(easting-e2):.4f}m, {abs(northing-n2):.4f}m")

if __name__ == "__main__":
    test()
