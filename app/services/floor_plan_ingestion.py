"""Floor plan ingestion — DXF and vision (PDF/image) pipelines.

Processes architectural floor plan files into venue zones, zone connections,
and candidate perch points.
"""

import logging
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

ROOM_TYPE_BY_AREA = [
    (6.0, "closet"),
    (15.0, "room"),
    (30.0, "corridor"),
    (60.0, "room"),
    (120.0, "lobby"),
]

ZONE_PRIORITY = {
    "entrance": 9,
    "lobby": 8,
    "corridor": 6,
    "stairwell": 5,
    "room": 4,
    "custom": 3,
    "closet": 2,
}


@dataclass
class IngestedZone:
    id: str
    name: str
    type: str
    environment: str
    floor_level: int
    polygon: list[list[float]]
    centroid_lat: float
    centroid_lon: float
    area_sq_m: float
    tier_requirement: str
    coverage_priority: int


@dataclass
class IngestedConnection:
    id: str
    from_zone_id: str
    to_zone_id: str
    connection_type: str
    position: list[float] | None = None


@dataclass
class IngestedPerchPoint:
    id: str
    zone_id: str
    surface_class: str
    surface_orientation: str
    tier_required: str
    position_lat: float
    position_lon: float
    height_m: float
    wall_normal: list[float] | None = None
    coverage_value: float = 0.5


@dataclass
class IngestionResult:
    zones: list[IngestedZone] = field(default_factory=list)
    connections: list[IngestedConnection] = field(default_factory=list)
    perch_points: list[IngestedPerchPoint] = field(default_factory=list)


def detect_format(file_path: str) -> str:
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext in (".dxf", ".dwg"):
        return "dxf"
    if ext == ".pdf":
        return "pdf"
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return "image"
    with open(file_path, "rb") as f:
        header = f.read(16)
    if b"SECTION" in header or b"AutoCAD" in header:
        return "dxf"
    if header[:4] == b"%PDF":
        return "pdf"
    return "image"


def get_pdf_page_count(file_path: str) -> int:
    """Return the number of pages in a PDF without fully rendering them."""
    from pdf2image import pdfinfo_from_path

    try:
        info = pdfinfo_from_path(file_path)
        return info.get("Pages", 1)
    except Exception:
        return 1


def ingest(
    file_path: str,
    fmt: str,
    venue_lat: float,
    venue_lon: float,
    floor_level: int = 0,
    scale_m_per_unit: float | None = None,
    page_number: int | None = None,
) -> IngestionResult:
    if fmt == "dxf":
        return _ingest_dxf(file_path, venue_lat, venue_lon, floor_level, scale_m_per_unit)
    elif fmt == "pdf":
        return _ingest_pdf(
            file_path, venue_lat, venue_lon, floor_level,
            scale_m_per_unit, page_number=page_number,
        )
    else:
        return _ingest_image(file_path, venue_lat, venue_lon, floor_level, scale_m_per_unit)


# ---------------------------------------------------------------------------
# DXF Pipeline
# ---------------------------------------------------------------------------

def _ingest_dxf(
    file_path: str,
    venue_lat: float,
    venue_lon: float,
    floor_level: int,
    scale: float | None,
) -> IngestionResult:
    import ezdxf

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    if scale is None:
        scale = _calibrate_scale_dxf(doc, msp)

    wall_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    door_positions: list[tuple[float, float]] = []
    room_polygons: list[Polygon] = []

    wall_layers = {"wall", "a-wall", "walls", "a-walls", "s-wall"}

    for entity in msp:
        layer = entity.dxf.layer.lower()

        if any(wl in layer for wl in wall_layers):
            if entity.dxftype() == "LINE":
                wall_segments.append((
                    (entity.dxf.start.x * scale, entity.dxf.start.y * scale),
                    (entity.dxf.end.x * scale, entity.dxf.end.y * scale),
                ))
            elif entity.dxftype() == "LWPOLYLINE":
                pts = list(entity.get_points(format="xy"))
                for i in range(len(pts) - 1):
                    wall_segments.append((
                        (pts[i][0] * scale, pts[i][1] * scale),
                        (pts[i + 1][0] * scale, pts[i + 1][1] * scale),
                    ))
                if entity.closed:
                    coords = [(p[0] * scale, p[1] * scale) for p in pts]
                    if len(coords) >= 3:
                        room_polygons.append(Polygon(coords))

        if "door" in layer or "opening" in layer:
            if entity.dxftype() == "INSERT":
                door_positions.append((
                    entity.dxf.insert.x * scale,
                    entity.dxf.insert.y * scale,
                ))
            elif entity.dxftype() == "LINE":
                mx = (entity.dxf.start.x + entity.dxf.end.x) / 2 * scale
                my = (entity.dxf.start.y + entity.dxf.end.y) / 2 * scale
                door_positions.append((mx, my))

        if "room" in layer or "space" in layer or "area" in layer:
            if entity.dxftype() == "LWPOLYLINE" and entity.closed:
                pts = list(entity.get_points(format="xy"))
                coords = [(p[0] * scale, p[1] * scale) for p in pts]
                if len(coords) >= 3:
                    room_polygons.append(Polygon(coords))
            elif entity.dxftype() == "HATCH":
                for path in entity.paths:
                    if hasattr(path, "vertices"):
                        coords = [(v[0] * scale, v[1] * scale) for v in path.vertices]
                        if len(coords) >= 3:
                            room_polygons.append(Polygon(coords))

    if not room_polygons and wall_segments:
        room_polygons = _rooms_from_walls(wall_segments)

    return _assemble(
        room_polygons, door_positions, wall_segments,
        venue_lat, venue_lon, floor_level,
    )


def _calibrate_scale_dxf(doc: Any, msp: Any) -> float:
    for entity in msp:
        if entity.dxftype() in ("DIMENSION", "ALIGNED_DIMENSION"):
            try:
                measurement = entity.dxf.actual_measurement
                if measurement and measurement > 0:
                    start = entity.dxf.defpoint
                    end = entity.dxf.defpoint2
                    dx = end.x - start.x
                    dy = end.y - start.y
                    drawing_dist = math.sqrt(dx * dx + dy * dy)
                    if drawing_dist > 0:
                        return measurement / drawing_dist
            except Exception:
                pass
    return 0.001  # default: millimeters to meters


# ---------------------------------------------------------------------------
# Vision Pipeline (PDF / Image)
# ---------------------------------------------------------------------------

def _ingest_pdf(
    file_path: str,
    venue_lat: float,
    venue_lon: float,
    floor_level: int,
    scale: float | None,
    page_number: int | None = None,
) -> IngestionResult:
    """Process a PDF floor plan.

    page_number=None (default): process ALL pages, each page = one floor
                                starting from floor_level.
    page_number=N:              process only page N (1-indexed), assigned to floor_level.
    """
    from pdf2image import convert_from_path

    if page_number is not None:
        images = convert_from_path(file_path, dpi=200, first_page=page_number, last_page=page_number)
        if not images:
            raise ValueError(f"Could not extract page {page_number} from PDF")

        img_bgr = cv2.cvtColor(np.array(images[0]), cv2.COLOR_RGB2BGR)
        return _process_image(img_bgr, venue_lat, venue_lon, floor_level, scale)

    images = convert_from_path(file_path, dpi=200)
    if not images:
        raise ValueError("Could not extract any pages from PDF")

    if len(images) == 1:
        img_bgr = cv2.cvtColor(np.array(images[0]), cv2.COLOR_RGB2BGR)
        return _process_image(img_bgr, venue_lat, venue_lon, floor_level, scale)

    combined = IngestionResult()
    for i, img in enumerate(images):
        current_floor = floor_level + i
        img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        page_result = _process_image(img_bgr, venue_lat, venue_lon, current_floor, scale)

        for z in page_result.zones:
            z.name = f"F{current_floor} {z.name}"
        combined.zones.extend(page_result.zones)
        combined.connections.extend(page_result.connections)
        combined.perch_points.extend(page_result.perch_points)

    logger.info("Multi-page PDF: processed %d pages → %d zones", len(images), len(combined.zones))
    return combined


def _ingest_image(
    file_path: str,
    venue_lat: float,
    venue_lon: float,
    floor_level: int,
    scale: float | None,
) -> IngestionResult:
    img = cv2.imread(file_path)
    if img is None:
        raise ValueError(f"Could not read image: {file_path}")
    return _process_image(img, venue_lat, venue_lon, floor_level, scale)


def _process_image(
    img: np.ndarray,
    venue_lat: float,
    venue_lon: float,
    floor_level: int,
    scale: float | None,
) -> IngestionResult:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    if scale is None:
        scale = _estimate_scale_from_image(w, h)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2,
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    walls = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    floor_mask = cv2.bitwise_not(walls)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    floor_mask = cv2.morphologyEx(floor_mask, cv2.MORPH_OPEN, kernel_open, iterations=2)

    contours, _ = cv2.findContours(floor_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area_px = (w * h) * 0.002
    room_polygons: list[Polygon] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area_px:
            continue

        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            continue

        coords = [(pt[0][0] * scale, pt[0][1] * scale) for pt in approx]
        poly = Polygon(coords)
        if poly.is_valid and not poly.is_empty:
            room_polygons.append(poly)

    wall_segments = _extract_wall_segments(walls, scale)
    door_positions = _detect_doors(walls, wall_segments, scale)

    return _assemble(
        room_polygons, door_positions, wall_segments,
        venue_lat, venue_lon, floor_level,
    )


def _estimate_scale_from_image(width_px: int, height_px: int) -> float:
    """Assume a standard door width (~0.9m) maps to about 15-20 pixels at 200 DPI."""
    longer_side = max(width_px, height_px)
    estimated_real_m = 30.0
    return estimated_real_m / longer_side


def _extract_wall_segments(
    walls_mask: np.ndarray, scale: float,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    lines = cv2.HoughLinesP(walls_mask, 1, np.pi / 180, 50, minLineLength=30, maxLineGap=10)
    segments = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            segments.append((
                (x1 * scale, y1 * scale),
                (x2 * scale, y2 * scale),
            ))
    return segments


def _detect_doors(
    walls_mask: np.ndarray,
    wall_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    scale: float,
) -> list[tuple[float, float]]:
    """Detect gaps in walls that could be doors (0.7m - 1.5m wide)."""
    doors = []
    min_gap_m = 0.7
    max_gap_m = 1.5

    for i, seg_a in enumerate(wall_segments):
        for seg_b in wall_segments[i + 1:]:
            for end_a in seg_a:
                for end_b in seg_b:
                    dist = math.sqrt((end_a[0] - end_b[0]) ** 2 + (end_a[1] - end_b[1]) ** 2)
                    if min_gap_m <= dist <= max_gap_m:
                        mx = (end_a[0] + end_b[0]) / 2
                        my = (end_a[1] + end_b[1]) / 2
                        doors.append((mx, my))

    seen = set()
    deduped = []
    for d in doors:
        key = (round(d[0], 1), round(d[1], 1))
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    return deduped


def _rooms_from_walls(
    wall_segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[Polygon]:
    """Build room polygons from wall segments using buffered union approach."""
    from shapely.geometry import LineString

    if not wall_segments:
        return []

    lines = [LineString([s[0], s[1]]) for s in wall_segments]
    merged = unary_union(lines)
    buffered = merged.buffer(0.15)

    result = buffered.buffer(-0.15)
    if isinstance(result, MultiPolygon):
        return [p for p in result.geoms if p.area > 1.0]
    elif isinstance(result, Polygon) and result.area > 1.0:
        return [result]
    return []


# ---------------------------------------------------------------------------
# Shared output assembly
# ---------------------------------------------------------------------------

def _assemble(
    room_polygons: list[Polygon],
    door_positions: list[tuple[float, float]],
    wall_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    venue_lat: float,
    venue_lon: float,
    floor_level: int,
) -> IngestionResult:
    result = IngestionResult()

    if not room_polygons:
        logger.warning("No room polygons detected — returning empty result")
        return result

    all_coords = []
    for poly in room_polygons:
        all_coords.extend(poly.exterior.coords)
    xs = [c[0] for c in all_coords]
    ys = [c[1] for c in all_coords]
    origin_x = (min(xs) + max(xs)) / 2
    origin_y = (min(ys) + max(ys)) / 2

    zone_map: dict[str, IngestedZone] = {}

    for i, poly in enumerate(room_polygons):
        zone_id = str(uuid.uuid4())
        centroid = poly.centroid
        area = poly.area
        zone_type = _classify_room(area)
        environment = "indoor" if floor_level >= 0 else "indoor"

        geo_polygon = _meters_to_geo(
            list(poly.exterior.coords), origin_x, origin_y, venue_lat, venue_lon,
        )
        cen_lat, cen_lon = _meter_to_geo_point(
            centroid.x, centroid.y, origin_x, origin_y, venue_lat, venue_lon,
        )

        zone = IngestedZone(
            id=zone_id,
            name=f"Zone {i + 1} ({zone_type})",
            type=zone_type,
            environment=environment,
            floor_level=floor_level,
            polygon=geo_polygon,
            centroid_lat=cen_lat,
            centroid_lon=cen_lon,
            area_sq_m=round(area, 2),
            tier_requirement="tier_1" if environment == "indoor" else "either",
            coverage_priority=ZONE_PRIORITY.get(zone_type, 3),
        )
        result.zones.append(zone)
        zone_map[zone_id] = zone

    zone_list = list(zone_map.values())
    zone_polys = [(z, Polygon(_geo_to_meters(z.polygon, origin_x, origin_y, venue_lat, venue_lon))) for z in zone_list]

    for door_pos in door_positions:
        from shapely.geometry import Point
        dp = Point(door_pos)
        nearby = [(z, poly) for z, poly in zone_polys if poly.distance(dp) < 1.5]
        if len(nearby) >= 2:
            nearby.sort(key=lambda x: x[1].distance(dp))
            z_a, z_b = nearby[0][0], nearby[1][0]
            conn_id = str(uuid.uuid4())
            pos_lat, pos_lon = _meter_to_geo_point(
                door_pos[0], door_pos[1], origin_x, origin_y, venue_lat, venue_lon,
            )
            result.connections.append(IngestedConnection(
                id=conn_id,
                from_zone_id=z_a.id,
                to_zone_id=z_b.id,
                connection_type="door",
                position=[pos_lat, pos_lon],
            ))

    if not result.connections and len(zone_list) > 1:
        for i in range(len(zone_list) - 1):
            z_a = zone_list[i]
            z_b = zone_list[i + 1]
            result.connections.append(IngestedConnection(
                id=str(uuid.uuid4()),
                from_zone_id=z_a.id,
                to_zone_id=z_b.id,
                connection_type="adjacency",
            ))

    for zone in zone_list:
        num_perch = max(1, min(4, int(zone.area_sq_m / 15)))
        zone_poly = [zp for zp in zone_polys if zp[0].id == zone.id]
        if not zone_poly:
            continue
        poly = zone_poly[0][1]

        perch_positions = _generate_perch_positions(poly, num_perch)
        for pos in perch_positions:
            pp_lat, pp_lon = _meter_to_geo_point(
                pos[0], pos[1], origin_x, origin_y, venue_lat, venue_lon,
            )
            surface = "wall" if zone.environment == "indoor" else "ledge"
            orientation = "vertical" if surface == "wall" else "horizontal"
            height = 3.0 if zone.environment == "indoor" else 5.0

            result.perch_points.append(IngestedPerchPoint(
                id=str(uuid.uuid4()),
                zone_id=zone.id,
                surface_class=surface,
                surface_orientation=orientation,
                tier_required=zone.tier_requirement,
                position_lat=pp_lat,
                position_lon=pp_lon,
                height_m=height,
                coverage_value=round(0.4 + 0.3 * (zone.coverage_priority / 9), 2),
            ))

    return result


def _classify_room(area_sq_m: float) -> str:
    for threshold, room_type in ROOM_TYPE_BY_AREA:
        if area_sq_m < threshold:
            return room_type
    return "lobby"


def _generate_perch_positions(
    poly: Polygon, count: int,
) -> list[tuple[float, float]]:
    coords = list(poly.exterior.coords)[:-1]
    if len(coords) < 2:
        return [(poly.centroid.x, poly.centroid.y)]

    wall_midpoints = []
    for i in range(len(coords)):
        j = (i + 1) % len(coords)
        mx = (coords[i][0] + coords[j][0]) / 2
        my = (coords[i][1] + coords[j][1]) / 2
        wall_midpoints.append((mx, my))

    wall_midpoints.sort(
        key=lambda p: -math.sqrt((p[0] - poly.centroid.x) ** 2 + (p[1] - poly.centroid.y) ** 2),
    )

    return wall_midpoints[:count]


# ---------------------------------------------------------------------------
# Coordinate transforms (meters ↔ geographic)
# ---------------------------------------------------------------------------

METERS_PER_DEG_LAT = 111_320.0


def _meter_to_geo_point(
    x: float, y: float,
    origin_x: float, origin_y: float,
    venue_lat: float, venue_lon: float,
) -> tuple[float, float]:
    dx = x - origin_x
    dy = y - origin_y
    meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(math.radians(venue_lat))
    lat = venue_lat + dy / METERS_PER_DEG_LAT
    lon = venue_lon + dx / meters_per_deg_lon
    return (round(lat, 8), round(lon, 8))


def _meters_to_geo(
    coords: list[tuple[float, float]],
    origin_x: float, origin_y: float,
    venue_lat: float, venue_lon: float,
) -> list[list[float]]:
    return [
        list(_meter_to_geo_point(x, y, origin_x, origin_y, venue_lat, venue_lon))
        for x, y in coords
    ]


def _geo_to_meters(
    geo_coords: list[list[float]],
    origin_x: float, origin_y: float,
    venue_lat: float, venue_lon: float,
) -> list[tuple[float, float]]:
    meters_per_deg_lon = METERS_PER_DEG_LAT * math.cos(math.radians(venue_lat))
    result = []
    for lat, lon in geo_coords:
        x = origin_x + (lon - venue_lon) * meters_per_deg_lon
        y = origin_y + (lat - venue_lat) * METERS_PER_DEG_LAT
        result.append((x, y))
    return result
