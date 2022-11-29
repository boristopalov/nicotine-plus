# COPYRIGHT (C) 2020-2022 Nicotine+ Contributors
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

import datetime

from unittest import TestCase

from pynicotine.config import config
from pynicotine.updatechecker import UpdateChecker


class VersionTest(TestCase):

    def test_dev_version(self):

        # Test a sample dev version to ensure it's older than the stable counterpart
        sample_stable_version = UpdateChecker.create_integer_version("2.1.0")
        sample_dev_version = UpdateChecker.create_integer_version("2.1.0.dev1")
        self.assertGreater(sample_stable_version, sample_dev_version)

    def test_update_check(self):

        # Validate local version
        local_version = UpdateChecker.create_integer_version(config.version)
        self.assertIsInstance(local_version, int)

        # Validate version of latest release
        _hlatest_version, latest_version, date = UpdateChecker.retrieve_latest_version()
        self.assertIsInstance(latest_version, int)

        # Validate date of latest release
        date_format = "%Y-%m-%dT%H:%M:%S"
        datetime.datetime.strptime(date, date_format)
