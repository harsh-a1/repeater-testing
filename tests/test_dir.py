# Copyright (C) 2007 Canonical Ltd
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Test the GitDir class"""

from bzrlib import bzrdir, errors

from bzrlib.plugins.git import dir, tests, workingtree


class TestGitDir(tests.TestCaseInTempDir):

    _test_needs_features = [tests.GitCommandFeature]

    def test_open_existing(self):
        tests.run_git('init')

        gd = bzrdir.BzrDir.open('.')
        self.assertIsInstance(gd, dir.LocalGitDir)

    def test_open_workingtree(self):
        tests.run_git('init')

        gd = bzrdir.BzrDir.open('.')
        wt = gd.open_workingtree()
        self.assertIsInstance(wt, workingtree.GitWorkingTree)

    def test_open_workingtree_bare(self):
        tests.run_git('--bare', 'init')

        gd = bzrdir.BzrDir.open('.')
        self.assertRaises(errors.NoWorkingTree, gd.open_workingtree)


class TestGitDirFormat(tests.TestCaseInTempDir):

    _test_needs_features = [tests.GitCommandFeature]

    def setUp(self):
        super(TestGitDirFormat, self).setUp()
        self.format = dir.LocalGitBzrDirFormat()

    def test_get_format_description(self):
        self.assertEquals("Local Git Repository",
                          self.format.get_format_description())

