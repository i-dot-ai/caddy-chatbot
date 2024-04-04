from setuptools import setup, find_packages

setup(
    name="caddy_core",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
