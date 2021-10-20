#!/usr/bin/env python3
# COPYRIGHT (C) 2020-2021 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2009-2010 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2008-2009 eL_vErDe <gandalf@le-vert.net>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
    To install Nicotine+ on a GNU/Linux distribution, run:
    pip3 install .
"""

import glob

from setuptools import setup
from pkgutil import walk_packages

import pynicotine

from pynicotine.config import config
from pynicotine.i18n import generate_translations


if __name__ == '__main__':

    # Specify a description for the PyPi project page
    LONG_DESCRIPTION = """Nicotine+ is a graphical client for the Soulseek peer-to-peer
network.

Nicotine+ aims to be a pleasant, free and open source (FOSS)
alternative to the official Soulseek client, providing additional
functionality while keeping current with the Soulseek protocol."""

    # Specify included files
    PACKAGES = ["pynicotine"] + \
        [name for importer, name, ispkg in walk_packages(path=pynicotine.__path__, prefix="pynicotine.") if ispkg]

    PACKAGE_DATA = dict((package, ["*.bin", "*.md", "*.py", "*.svg", "*.ui", "PLUGININFO"]) for package in PACKAGES)

    DATA_FILES = [
        ("share/applications", glob.glob("data/*.desktop")),
        ("share/metainfo", glob.glob("data/*.metainfo.xml")),
        ("share/icons/hicolor/scalable/apps", glob.glob("pynicotine/gtkgui/icons/hicolor/scalable/apps/*.svg")),
        ("share/icons/hicolor/symbolic/apps", glob.glob("pynicotine/gtkgui/icons/hicolor/symbolic/apps/*.svg")),
        ("share/doc/nicotine", glob.glob("[!404.md]*.md") + glob.glob("doc/*.md") + ["COPYING"]),
        ("share/man/man1", glob.glob("data/*.1"))
    ] + generate_translations()[0]

    # Run setup
    setup(
        name="nicotine-plus",
        version=config.version,
        license="GPLv3+",
        description="Graphical client for the Soulseek peer-to-peer network",
        long_description=LONG_DESCRIPTION,
        author="Nicotine+ Team",
        author_email="nicotine-team@lists.launchpad.net",
        url="https://nicotine-plus.org/",
        platforms="any",
        packages=PACKAGES,
        package_data=PACKAGE_DATA,
        scripts=["nicotine"],
        data_files=DATA_FILES,
        python_requires=">=3.5",
        install_requires=["PyGObject>=3.18"]
    )
