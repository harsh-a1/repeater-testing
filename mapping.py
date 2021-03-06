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

"""Converters, etc for going between Bazaar and Git ids."""

from bzrlib import errors, foreign
from bzrlib.inventory import ROOT_ID
from bzrlib.foreign import (
        ForeignRevision,
        )


def escape_file_id(file_id):
    return file_id.replace('_', '__').replace(' ', '_s')


def unescape_file_id(file_id):
    return file_id.replace("_s", " ").replace("__", "_")


class BzrGitMapping(foreign.VcsMapping):
    """Class that maps between Git and Bazaar semantics."""
    experimental = False

    def revision_id_foreign_to_bzr(self, git_rev_id):
        """Convert a git revision id handle to a Bazaar revision id."""
        return "%s:%s" % (self.revid_prefix, git_rev_id)

    def revision_id_bzr_to_foreign(self, bzr_rev_id):
        """Convert a Bazaar revision id to a git revision id handle."""
        if not bzr_rev_id.startswith("%s:" % self.revid_prefix):
            raise errors.InvalidRevisionId(bzr_rev_id, self)
        return bzr_rev_id[len(self.revid_prefix)+1:]

    def show_foreign_revid(self, foreign_revid):
        return { "git commit": foreign_revid }

    def generate_file_id(self, path):
        if path == "":
            return ROOT_ID
        return escape_file_id(path.encode('utf-8'))

    def import_commit(self, commit):
        """Convert a git commit to a bzr revision.

        :return: a `bzrlib.revision.Revision` object.
        """
        if commit is None:
            raise AssertionError("Commit object can't be None")
        rev = ForeignRevision(commit.id, self, self.revision_id_foreign_to_bzr(commit.id))
        rev.parent_ids = tuple([self.revision_id_foreign_to_bzr(p) for p in commit.parents])
        rev.message = commit.message.decode("utf-8", "replace")
        rev.committer = str(commit.committer).decode("utf-8", "replace")
        if commit.committer != commit.author:
            rev.properties['author'] = str(commit.author).decode("utf-8", "replace")
        rev.timestamp = commit.commit_time
        rev.timezone = 0
        return rev


class BzrGitMappingv1(BzrGitMapping):
    revid_prefix = 'git-v1'
    experimental = False


class BzrGitMappingExperimental(BzrGitMappingv1):
    revid_prefix = 'git-experimental'
    experimental = True


default_mapping = BzrGitMappingv1()
