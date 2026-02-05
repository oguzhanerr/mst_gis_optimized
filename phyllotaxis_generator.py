import math
import argparse
import json

def generate_phyllotaxis(lat0, lon0, num_points, scale=1.0):
    """
    Generate a phyllotaxis pattern of points starting from a given latitude and longitude.

    Parameters:
    lat0 (float): Starting latitude in degrees.
    lon0 (float): Starting longitude in degrees.
    num_points (int): Number of points to generate.
    scale (float): Scaling factor for the radius (in meters).

    Returns:
    list: List of tuples (latitude, longitude) in degrees.
    """
    golden_angle = 2 * math.pi * (1 - 1 / math.sqrt(5))  # Golden angle in radians (~137.5 degrees)
    points = []

    for i in range(num_points):
        angle = i * golden_angle
        radius = scale * math.sqrt((i + 0.5) / num_points)  # Improved distribution to minimize clustering

        # Calculate Cartesian coordinates
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        # Convert to latitude and longitude offsets (approximate for small areas)
        delta_lat = y / 111320  # Approximate meters per degree latitude
        delta_lon = x / (111320 * math.cos(math.radians(lat0)))  # Adjust for longitude

        lat = lat0 + delta_lat
        lon = lon0 + delta_lon

        points.append((lat, lon))

    return points

def generate_geojson(points):
    """
    Generate a GeoJSON FeatureCollection from a list of (latitude, longitude) points.

    Parameters:
    points (list): List of tuples (latitude, longitude).

    Returns:
    str: GeoJSON string.
    """
    features = []
    for lon, lat in points:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]  # GeoJSON uses [longitude, latitude]
            },
            "properties": {}
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return json.dumps(geojson, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate phyllotaxis pattern points from a geospatial point.")
    parser.add_argument("lat", type=float, help="Starting latitude in degrees")
    parser.add_argument("lon", type=float, help="Starting longitude in degrees")
    parser.add_argument("num_points", type=int, help="Number of points to generate")
    parser.add_argument("--scale", type=float, default=1.0, help="Scaling factor for radius (in meters)")
    parser.add_argument("--geojson", action="store_true", help="Output as GeoJSON instead of CSV")
    parser.add_argument("--output", type=str, help="Output file path to save results")

    args = parser.parse_args()

    points = generate_phyllotaxis(args.lat, args.lon, args.num_points, args.scale)

    if args.geojson:
        geojson_str = generate_geojson(points)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(geojson_str)
            print(f"GeoJSON saved to {args.output}")
        else:
            print(geojson_str)
    else:
        # Output points in lat,lon format
        if args.output:
            with open(args.output, 'w') as f:
                for lat, lon in points:
                    f.write(f"{lat},{lon}\n")
            print(f"CSV saved to {args.output}")
        else:
            for lat, lon in points:
                print(f"{lat},{lon}")