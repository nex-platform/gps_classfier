from setuptools import find_packages, setup

setup(
    name="gps_region_classifier",
    version="1.0.0",
    description="Real-time GPS region classification simulation (In A / In B / Outside)",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "setuptools",
        "shapely>=2.0",
    ],
    extras_require={
        "plot": ["matplotlib>=3.5"],
        "dev": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "gps-classifier=gps_classifier.main:main",
        ],
    },
)
