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

"""An adapter between a Git Repository and a Bazaar Branch"""

import os
import time

import bzrlib
from bzrlib import (
    deprecated_graph,
    errors,
    graph,
    inventory,
    osutils,
    repository,
    revision,
    revisiontree,
    urlutils,
    versionedfile,
    )
from bzrlib.foreign import (
        ForeignRepository,
        )
from bzrlib.trace import mutter
from bzrlib.transport import get_transport

from bzrlib.plugins.git.foreign import (
    versionedfiles,
    )
from bzrlib.plugins.git.mapping import default_mapping

from bzrlib.plugins.git import git


class GitTags(object):

    def __init__(self, tags):
        self._tags = tags

    def __iter__(self):
        return iter(self._tags)


class GitRepository(ForeignRepository):
    """An adapter to git repositories for bzr."""

    _serializer = None

    def __init__(self, gitdir, lockfiles):
        ForeignRepository.__init__(self, GitFormat(), gitdir, lockfiles)
        from bzrlib.plugins.git import fetch
        repository.InterRepository.register_optimiser(fetch.InterGitRepository)
        repository.InterRepository.register_optimiser(fetch.InterGitNonGitRepository)

    def is_shared(self):
        return True

    def supports_rich_root(self):
        return True

    def _warn_if_deprecated(self):
        # This class isn't deprecated
        pass

    def get_mapping(self):
        return default_mapping

    def make_working_trees(self):
        return True


class LocalGitRepository(GitRepository):

    def __init__(self, gitdir, lockfiles):
        # FIXME: This also caches negatives. Need to be more careful 
        # about this once we start writing to git
        self._parents_provider = graph.CachingParentsProvider(self)
        GitRepository.__init__(self, gitdir, lockfiles)
        self.base = gitdir.root_transport.base
        self._git = gitdir._git
        self.texts = None
        self.signatures = versionedfiles.VirtualSignatureTexts(self)
        self.revisions = versionedfiles.VirtualRevisionTexts(self)
        self.tags = GitTags(self._git.get_tags())

    def all_revision_ids(self):
        ret = set([revision.NULL_REVISION])
        if self._git.heads() == []:
            return ret
        bzr_heads = [self.get_mapping().revision_id_foreign_to_bzr(h) for h in self._git.heads()]
        ret = set(bzr_heads)
        graph = self.get_graph()
        for rev, parents in graph.iter_ancestry(bzr_heads):
            ret.add(rev)
        return ret

    #def get_revision_delta(self, revision_id):
    #    parent_revid = self.get_revision(revision_id).parent_ids[0]
    #    diff = self._git.diff(ids.convert_revision_id_bzr_to_git(parent_revid),
    #                   ids.convert_revision_id_bzr_to_git(revision_id))

    def _make_parents_provider(self):
        """See Repository._make_parents_provider()."""
        return self._parents_provider

    def get_parent_map(self, revids):
        parent_map = {}
        mutter("get_parent_map(%r)", revids)
        for revision_id in revids:
            assert isinstance(revision_id, str)
            if revision_id == revision.NULL_REVISION:
                parent_map[revision_id] = ()
                continue
            hexsha = self.lookup_git_revid(revision_id, self.get_mapping())
            commit  = self._git.commit(hexsha)
            if commit is None:
                continue
            else:
                parent_map[revision_id] = [self.get_mapping().revision_id_foreign_to_bzr(p) for p in commit.parents]
        return parent_map

    def get_ancestry(self, revision_id, topo_sorted=True):
        """See Repository.get_ancestry().
        """
        if revision_id is None:
            return self._all_revision_ids()
        assert isinstance(revision_id, str)
        ancestry = []
        graph = self.get_graph()
        for rev, parents in graph.iter_ancestry([revision_id]):
            if rev == revision.NULL_REVISION:
                rev = None
            ancestry.append(rev)
        ancestry.reverse()
        return ancestry

    def get_signature_text(self, revision_id):
        raise errors.NoSuchRevision(self, revision_id)

    def lookup_revision_id(self, revid):
        """Lookup a revision id.
        
        :param revid: Bazaar revision id.
        :return: Tuple with git revisionid and mapping.
        """
        # Yes, this doesn't really work, but good enough as a stub
        return osutils.sha(rev_id).hexdigest(), self.get_mapping()

    def has_signature_for_revision_id(self, revision_id):
        return False

    def lookup_git_revid(self, bzr_revid, mapping):
        try:
            return mapping.revision_id_bzr_to_foreign(bzr_revid)
        except errors.InvalidRevisionId:
            raise errors.NoSuchRevision(self, bzr_revid)

    def get_revision(self, revision_id):
        git_commit_id = self.lookup_git_revid(revision_id, self.get_mapping())
        try:
            commit = self._git.commit(git_commit_id)
        except KeyError:
            raise errors.NoSuchRevision(self, revision_id)
        # print "fetched revision:", git_commit_id
        revision = self.get_mapping().import_commit(commit)
        assert revision is not None
        return revision

    def has_revision(self, revision_id):
        try:
            self.get_revision(revision_id)
        except errors.NoSuchRevision:
            return False
        else:
            return True

    def get_revisions(self, revids):
        return [self.get_revision(r) for r in revids]

    def revision_trees(self, revids):
        for revid in revids:
            yield self.revision_tree(revid)

    def revision_tree(self, revision_id):
        revision_id = revision.ensure_null(revision_id)

        if revision_id == revision.NULL_REVISION:
            inv = inventory.Inventory(root_id=None)
            inv.revision_id = revision_id
            return revisiontree.RevisionTree(self, inv, revision_id)

        return GitRevisionTree(self, self.get_mapping(), revision_id)

    def get_inventory(self, revision_id):
        assert revision_id != None
        return self.revision_tree(revision_id).inventory

    def set_make_working_trees(self, trees):
        pass

    def fetch_objects(self, determine_wants, graph_walker, progress=None):
        return self._git.fetch_objects(determine_wants, graph_walker, progress)


class GitRevisionTree(revisiontree.RevisionTree):

    def __init__(self, repository, mapping, revision_id):
        self._repository = repository
        self.revision_id = revision_id
        assert isinstance(revision_id, str)
        self.mapping = mapping
        git_id = repository.lookup_git_revid(revision_id, self.mapping)
        try:
            commit = repository._git.commit(git_id)
        except KeyError, r:
            raise errors.NoSuchRevision(repository, revision_id)
        self.tree = commit.tree
        self._inventory = inventory.Inventory(revision_id=revision_id)
        self._inventory.root.revision = revision_id
        self._build_inventory(self.tree, self._inventory.root, "")

    def get_revision_id(self):
        return self.revision_id

    def get_file_text(self, file_id):
        entry = self._inventory[file_id]
        if entry.kind == 'directory': return ""
        return self._repository._git.get_blob(entry.text_id).data

    def _build_inventory(self, tree_id, ie, path):
        assert isinstance(path, str)
        tree = self._repository._git.tree(tree_id)
        for mode, name, hexsha in tree.entries():
            basename = name.decode("utf-8")
            if path == "":
                child_path = name
            else:
                child_path = urlutils.join(path, name)
            file_id = self.mapping.generate_file_id(child_path)
            entry_kind = (mode & 0700000) / 0100000
            if entry_kind == 0:
                child_ie = inventory.InventoryDirectory(file_id, basename, ie.file_id)
            elif entry_kind == 1:
                file_kind = (mode & 070000) / 010000
                b = self._repository._git.get_blob(hexsha)
                if file_kind == 0:
                    child_ie = inventory.InventoryFile(file_id, basename, ie.file_id)
                    child_ie.text_sha1 = osutils.sha_string(b.data)
                elif file_kind == 2:
                    child_ie = inventory.InventoryLink(file_id, basename, ie.file_id)
                    child_ie.text_sha1 = osutils.sha_string("")
                else:
                    raise AssertionError(
                        "Unknown file kind, perms=%o." % (mode,))
                child_ie.text_id = b.id
                child_ie.text_size = len(b.data)
            else:
                raise AssertionError(
                    "Unknown blob kind, perms=%r." % (mode,))
            fs_mode = mode & 0777
            child_ie.executable = bool(fs_mode & 0111)
            child_ie.revision = self.revision_id
            self._inventory.add(child_ie)
            if entry_kind == 0:
                self._build_inventory(hexsha, child_ie, child_path)


class GitFormat(object):

    supports_tree_reference = False
    rich_root_data = True

    def get_format_description(self):
        return "Git Repository"

    def initialize(self, url, shared=False, _internal=False):
        raise bzr_errors.UninitializableFormat(self)

    def check_conversion_target(self, target_repo_format):
        return target_repo_format.rich_root_data
