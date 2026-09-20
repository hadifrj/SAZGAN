"""
This is PyInstaller hook file for CEF Python. This file
helps PyInstaller find CEF Python dependencies that are
required to run final executable.

Source: cztomczak/cefpython, examples/pyinstaller/hook-cefpython3.py
(vendored here so the SAZGAN client build is self-contained and does
not depend on downloading it separately).

See PyInstaller docs for hooks:
https://pyinstaller.readthedocs.io/en/stable/hooks.html
"""

import glob
import os
import platform
import re
import sys

import PyInstaller
from PyInstaller.utils.hooks import is_module_satisfies, get_package_paths
from PyInstaller.compat import is_win, is_darwin, is_linux
from PyInstaller import log as logging

try:
    # PyInstaller >= 4.0 doesn't support Python 2.7
    from PyInstaller.compat import is_py2
except ImportError:
    is_py2 = None

# Constants
CEFPYTHON_MIN_VERSION = "57.0"
PYINSTALLER_MIN_VERSION = "3.2.1"

CEFPYTHON3_DIR = get_package_paths("cefpython3")[1]
CYTHON_MODULE_EXT = ".pyd" if is_win else ".so"

logger = logging.getLogger(__name__)


def check_platforms():
    if not is_win and not is_darwin and not is_linux:
        raise SystemExit("Error: Currently only Windows, Linux and Darwin "
                          "platforms are supported, see Issue #135.")


def check_pyinstaller_version():
    version = PyInstaller.__version__
    match = re.search(r"^\d+\.\d+(\.\d+)?", version)
    if not (match.group(0) >= PYINSTALLER_MIN_VERSION):
        raise SystemExit("Error: pyinstaller %s or higher is required"
                          % PYINSTALLER_MIN_VERSION)


def check_cefpython3_version():
    if not is_module_satisfies("cefpython3 >= %s" % CEFPYTHON_MIN_VERSION):
        raise SystemExit("Error: cefpython3 %s or higher is required"
                          % CEFPYTHON_MIN_VERSION)


def get_cefpython_modules():
    """Get all cefpython Cython modules in the cefpython3 package.
    Returns a list of names without file extension, e.g. 'cefpython_py39'."""
    pyds = glob.glob(os.path.join(CEFPYTHON3_DIR,
                                   "cefpython_py*" + CYTHON_MODULE_EXT))
    assert len(pyds) > 1, "Missing cefpython3 Cython modules"
    modules = []
    for path in pyds:
        filename = os.path.basename(path)
        mod = filename.replace(CYTHON_MODULE_EXT, "")
        modules.append(mod)
    return modules


def get_excluded_cefpython_modules():
    """Exclude Cython modules for Python versions other than the one
    currently building, so pyinstaller doesn't pull in wrong-version
    dll dependencies. Returns fully qualified module names."""
    pyver = "".join(map(str, sys.version_info[:2]))
    pyver_string = "py%s" % pyver
    modules = get_cefpython_modules()
    excluded = []
    for mod in modules:
        if pyver_string in mod:
            continue
        excluded.append("cefpython3.%s" % mod)
        logger.info("Exclude cefpython3 module: %s" % excluded[-1])
    return excluded


def get_cefpython3_datas():
    """Return almost all cefpython binaries as DATAS (not BINARIES),
    because pyinstaller mangles .dll manifests and fails to load them
    otherwise. subprocess(.exe) is passed separately as BINARIES so its
    own dependencies get collected.

    DATAS are in format: tuple(full_path, dest_subdir).
    """
    ret = list()
    if is_win or is_darwin or is_linux:
        cefdatadir = "."
    else:
        assert False, "Unsupported system {}".format(platform.system())

    for filename in os.listdir(CEFPYTHON3_DIR):
        if filename[:-len(CYTHON_MODULE_EXT)] in get_cefpython_modules():
            continue
        extension = os.path.splitext(filename)[1]
        if extension in \
                [".exe", ".dll", ".pak", ".dat", ".bin", ".txt", ".so", ".plist"] \
                or filename.lower().startswith("license"):
            logger.info("Include cefpython3 data: {}".format(filename))
            ret.append((os.path.join(CEFPYTHON3_DIR, filename), cefdatadir))

    if is_darwin:
        resources_subdir = \
            os.path.join("Chromium Embedded Framework.framework", "Resources")
        base_path = os.path.join(CEFPYTHON3_DIR, resources_subdir)
        assert os.path.exists(base_path), \
            "{} dir not found in cefpython3".format(resources_subdir)
        for path, dirs, files in os.walk(base_path):
            for file in files:
                absolute_file_path = os.path.join(path, file)
                dest_path = os.path.relpath(path, CEFPYTHON3_DIR)
                ret.append((absolute_file_path, dest_path))
                logger.info("Include cefpython3 data: {}".format(dest_path))
    elif is_win or is_linux:
        locales_dir = os.path.join(CEFPYTHON3_DIR, "locales")
        assert os.path.exists(locales_dir), \
            "locales/ dir not found in cefpython3"
        for filename in os.listdir(locales_dir):
            logger.info("Include cefpython3 data: {}/{}".format(
                os.path.basename(locales_dir), filename))
            ret.append((os.path.join(locales_dir, filename),
                        os.path.join(cefdatadir, "locales")))

        swiftshader_dir = os.path.join(CEFPYTHON3_DIR, "swiftshader")
        if os.path.isdir(swiftshader_dir):
            for filename in os.listdir(swiftshader_dir):
                logger.info("Include cefpython3 data: {}/{}".format(
                    os.path.basename(swiftshader_dir), filename))
                ret.append((os.path.join(swiftshader_dir, filename),
                            os.path.join(cefdatadir, "swiftshader")))
    return ret


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
check_platforms()
check_pyinstaller_version()
check_cefpython3_version()

logger.info("CEF Python package directory: %s" % CEFPYTHON3_DIR)

hiddenimports = [
    "codecs", "copy", "datetime", "inspect", "json", "os", "platform",
    "random", "re", "sys", "time", "traceback", "types", "urllib", "weakref",
]
if is_py2:
    hiddenimports += ["urlparse"]

excludedimports = get_excluded_cefpython_modules()

if is_darwin or is_linux:
    binaries = [(os.path.join(CEFPYTHON3_DIR, "subprocess"), ".")]
elif is_win:
    binaries = [(os.path.join(CEFPYTHON3_DIR, "subprocess.exe"), ".")]
else:
    binaries = []

datas = get_cefpython3_datas()

os.environ["PYINSTALLER_CEFPYTHON3_HOOK_SUCCEEDED"] = "1"
