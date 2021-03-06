# __init__.py -- The tests for dulwich
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License or (at your option) any later version of 
# the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

import unittest
import test_objects
import test_repository
import test_pack

def test_suite():
  test_modules = [test_objects, test_repository, test_pack]
  loader = unittest.TestLoader()
  suite = unittest.TestSuite()
  for mod in test_modules:
    suite.addTest(loader.loadTestsFromModule(mod))
  return suite

if __name__ == '__main__':
  suite = test_suite()
  from unittest import TextTestRunner
  TextTestRunner().run(suite)

