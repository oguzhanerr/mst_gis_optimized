import ast
import csv
import time
import psutil
from pathlib import Path

import Py1812.P1812
import geojson

import numpy as np
import matplotlib

# Steps to follow
# 1. Check csv file location
# 2. Check csv file format
# 3. Read csv file line-by-line
# 3.1. Execute P1812 loss
# 3.1.a if success then:
#   store loss value
#
#
#
# 3.1.b else:
#   skip the line
#
#
# 4. Create the GeoJSON


def load_profiles():
    folder = Path(__file__).parent / 'profiles'
    profiles = []
    for file in folder.glob("*.csv"):

        with file.open(newline="", encoding="utf-8") as f:
            profiles += list(csv.reader(f, delimiter=";"))[1:]

    return profiles


def generate_geojson_from_profile(profile):
    parameters = process_loss_parameters(profile)
    print(len(parameters[2]))
    start_P1812 = time.perf_counter()
    basic_transmission_lost, electric_field_strength = Py1812.P1812.bt_loss(*parameters)
    print("P1812_loss processing time: " + str(round(time.perf_counter() - start_P1812, 4)))
    transmitter = geojson.Point((parameters[12],parameters[10]))
    feature_t = geojson.Feature(geometry=transmitter, properties={
        "name": "Transmitter",
        "frequency": parameters[0],
        "htg": parameters[7],
        "polarization": parameters[9],
    })
    receiver = geojson.Point((parameters[13],parameters[11]))
    feature_r = geojson.Feature(geometry=receiver, properties={
        "name": "Receiver",
        "Lb": basic_transmission_lost,
        "Ep": electric_field_strength,
        "hfg": parameters[8],
        "distance": parameters[2][-1],
    })
    line = geojson.LineString([[parameters[12],parameters[10]],[parameters[13],parameters[11]]])
    feature_line = geojson.Feature(geometry=line)
    feature_collection = geojson.FeatureCollection([feature_t, feature_r, feature_line])
    # with open("./geojson/" + str(time.time()) + ".geojson", "w") as f:
    #     geojson.dump(feature_collection, f)

def add_calculated_fields_from_profile(profile):
    parameters = process_loss_parameters(profile)
    basic_transmission_lost, electric_field_strength = Py1812.P1812.bt_loss(*parameters)
    print(str(round(basic_transmission_lost,3)) + "," + str(round(electric_field_strength,3)))

def process_loss_parameters(profile):
    parameters = [ast.literal_eval(parameter) for parameter in profile[0:15]]
    return [
        float(parameters[0])
        ,float(parameters[1])
        ,np.array([float(value) for value in parameters[2]])
        ,np.array([float(value) for value in parameters[3]])
        ,np.array([float(value) for value in parameters[4]])
        ,np.array([int(value) for value in parameters[5]])
        ,np.array([int(value) for value in parameters[6]])
        ,float(parameters[7])
        ,float(parameters[8])
        ,int(parameters[9])
        ,float(parameters[10])
        ,float(parameters[11])
        ,float(parameters[12])
        ,float(parameters[13])
    ]

def generate_geojson_point_from_profile(parameters, number):
    basic_transmission_lost, electric_field_strength = Py1812.P1812.bt_loss(*parameters)

    rx_lon, rx_lat = parameters[13], parameters[11]
    receiver = geojson.Point((rx_lon, rx_lat))

    return geojson.Feature(geometry=receiver, properties={
        "name": "Receiver_" + str(number),
        "Lb": basic_transmission_lost,
        "Ep": electric_field_strength,
        "hrg": parameters[8],
        "distance": parameters[2][-1],
        "lon": rx_lon,
        "lat": rx_lat,
    })


def generate_geojson_point_transmitter(parameters):
    tx_lon, tx_lat = parameters[12], parameters[10]
    transmitter = geojson.Point((tx_lon, tx_lat))
    return geojson.Feature(geometry=transmitter, properties={
        "name": "Transmitter",
        "frequency": parameters[0],
        "htg": parameters[7],
        "polarization": parameters[9],
        "lon": tx_lon,
        "lat": tx_lat,
    })


def main():
    # Keep ORIGINAL behavior: ./geojson relative to where you run python
    out_dir = Path("./geojson")
    out_dir.mkdir(parents=True, exist_ok=True)

    points = []
    lines = []
    polygon_coords = []

    for index, profile in enumerate(load_profiles()):
        parameters = process_loss_parameters(profile)

        # transmitter once
        if index == 0:
            points.append(generate_geojson_point_transmitter(parameters))

        # receiver
        points.append(generate_geojson_point_from_profile(parameters, index + 1))

        # line TX->RX
        tx_lon, tx_lat = parameters[12], parameters[10]
        rx_lon, rx_lat = parameters[13], parameters[11]

        lines.append(
            geojson.Feature(
                geometry=geojson.LineString([[tx_lon, tx_lat], [rx_lon, rx_lat]]),
                properties={
                    "name": f"Link_{index+1}",
                    "rx_id": index+1,
                    "tx_lon": tx_lon,
                    "tx_lat": tx_lat,
                    "rx_lon": rx_lon,
                    "rx_lat": rx_lat,
                    "distance_km": float(parameters[2][-1]),
                },
            )
        )


        polygon_coords.append([rx_lon, rx_lat])

    # Close ring (GeoJSON polygon should be closed)
    if polygon_coords and polygon_coords[0] != polygon_coords[-1]:
        polygon_coords.append(polygon_coords[0])

    polygon_fc = geojson.FeatureCollection([
        geojson.Feature(
            geometry=geojson.Polygon([polygon_coords]) if polygon_coords else geojson.Polygon([[]]),
            properties={"name": "Coverage area"},
        )
    ])

    ts = time.strftime("%Y%m%d_%H%M%S")

    # Use the maximum distance among profiles (km) for naming
    # (usually identical across all profiles)
    max_d_km = 0.0
    for profile in load_profiles():
        p = process_loss_parameters(profile)
        max_d_km = max(max_d_km, float(p[2][-1]))

    # Format for filename: 11.0 -> "11p0km"
    d_tag = f"{max_d_km:.1f}".replace(".", "p") + "km"

    points_path  = out_dir / f"points_{d_tag}_{ts}.geojson"
    lines_path   = out_dir / f"lines_{d_tag}_{ts}.geojson"
    polygon_path = out_dir / f"polygon_{d_tag}_{ts}.geojson"

    with open(points_path, "w", encoding="utf-8") as f:
        geojson.dump(geojson.FeatureCollection(points), f)

    with open(lines_path, "w", encoding="utf-8") as f:
        geojson.dump(geojson.FeatureCollection(lines), f)

    with open(polygon_path, "w", encoding="utf-8") as f:
        geojson.dump(polygon_fc, f)

    print("Saved GeoJSON files:")
    print(" -", points_path.resolve())
    print(" -", lines_path.resolve())
    print(" -", polygon_path.resolve())


if __name__ == "__main__":
    main()