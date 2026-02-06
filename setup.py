from setuptools import setup, find_packages

setup(
    name="mst_gis",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "geopandas",
        "pandas",
        "numpy",
        "shapely",
        "rasterio",
        "requests",
        "SRTM.py",
    ],
)
