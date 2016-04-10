# Copyright (C) 2007 Jelmer Vernooij <jelmer@samba.org>
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

from bzrlib.plugins.git import tests
from bzrlib.plugins.git.mapping import default_mapping


class TestRevidConversion(tests.TestCase):

    def test_simple_git_to_bzr_revision_id(self):
        self.assertEqual("git-experimental:"
                         "c6a4d8f1fa4ac650748e647c4b1b368f589a7356",
                         default_mapping.convert_revision_id_git_to_bzr(
                            "c6a4d8f1fa4ac650748e647c4b1b368f589a7356"))

    def test_simple_bzr_to_git_revision_id(self):
        self.assertEqual("c6a4d8f1fa4ac650748e647c4b1b368f589a7356",
                         default_mapping.convert_revision_id_bzr_to_git(
                            "git-experimental:"
                            "c6a4d8f1fa4ac650748e647c4b1b368f589a7356"))
