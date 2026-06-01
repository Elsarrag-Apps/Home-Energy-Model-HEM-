import os
import shutil

from Cython.Build import cythonize
from setuptools import setup
from setuptools.command.build_ext import build_ext

root_path = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(root_path, "src")
build_path = os.path.join(root_path, "build_directory")
cythonize_files = [
    os.path.join(build_path, "hem_core", "space_heat_demand", "zone.py"),
]


class BuildExtCustom(build_ext):
    def finalize_options(self):
        super().finalize_options()
        # Location of the lib / temp files that are created during the setup process
        self.build_lib = os.path.join(build_path, "cython_build_directory")
        self.build_temp = os.path.join(build_path, "cython_build_directory")


def copy_files_to_build_dir():
    # If build_path exists, remove it for shutil.copytree to work
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    shutil.copytree(src_path, build_path)

    # Removing all __pycache__ folders and .pyc files
    for root, dirs, files in os.walk(build_path):
        for dir in dirs:
            if dir == "__pycache__":
                pycache_path = os.path.join(root, dir)
                shutil.rmtree(pycache_path)
        for file in files:
            if file.endswith(".pyc"):
                pyc_file = os.path.join(root, file)
                os.remove(pyc_file)


if __name__ == "__main__":
    print("Create build folder, converting to C")

    copy_files_to_build_dir()

    os.chdir(build_path)

    setup(
        name="sap",
        cmdclass={"build_ext": BuildExtCustom},
        ext_modules=cythonize(cythonize_files, language_level=3, exclude=["**/__init__.py"]),
    )
