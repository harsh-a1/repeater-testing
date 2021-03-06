# objects.py -- Acces to base git objects
# Copyright (C) 2007 James Westby <jw+debian@jameswestby.net>
# Copyright (C) 2008 Jelmer Vernooij <jelmer@samba.org>
# The header parsing code is based on that from git itself, which is
# Copyright (C) 2005 Linus Torvalds
# and licensed under v2 of the GPL.
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License.
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

import mmap
import os
import sha
import zlib

from errors import (NotCommitError,
                    NotTreeError,
                    NotBlobError,
                    )

BLOB_ID = "blob"
TAG_ID = "tag"
TREE_ID = "tree"
COMMIT_ID = "commit"
PARENT_ID = "parent"
AUTHOR_ID = "author"
COMMITTER_ID = "committer"
OBJECT_ID = "object"
TYPE_ID = "type"
TAGGER_ID = "tagger"

def _decompress(string):
    dcomp = zlib.decompressobj()
    dcomped = dcomp.decompress(string)
    dcomped += dcomp.flush()
    return dcomped

def sha_to_hex(sha):
  """Takes a string and returns the hex of the sha within"""
  hexsha = ''
  for c in sha:
    hexsha += "%02x" % ord(c)
  assert len(hexsha) == 40, "Incorrect length of sha1 string: %d" % \
         len(hexsha)
  return hexsha

def hex_to_sha(hex):
  """Takes a hex sha and returns a binary sha"""
  sha = ''
  for i in range(0, len(hex), 2):
    sha += chr(int(hex[i:i+2], 16))
  assert len(sha) == 20, "Incorrent length of sha1: %d" % len(sha)
  return sha

class ShaFile(object):
  """A git SHA file."""

  @classmethod
  def _parse_legacy_object(cls, map):
    """Parse a legacy object, creating it and setting object._text"""
    text = _decompress(map)
    object = None
    for posstype in type_map.keys():
      if text.startswith(posstype):
        object = type_map[posstype]()
        text = text[len(posstype):]
        break
    assert object is not None, "%s is not a known object type" % text[:9]
    assert text[0] == ' ', "%s is not a space" % text[0]
    text = text[1:]
    size = 0
    i = 0
    while text[0] >= '0' and text[0] <= '9':
      if i > 0 and size == 0:
        assert False, "Size is not in canonical format"
      size = (size * 10) + int(text[0])
      text = text[1:]
      i += 1
    object._size = size
    assert text[0] == "\0", "Size not followed by null"
    text = text[1:]
    object._text = text
    return object

  def as_raw_string(self):
    return self._num_type, self._text

  @classmethod
  def _parse_object(cls, map):
    """Parse a new style object , creating it and setting object._text"""
    used = 0
    byte = ord(map[used])
    used += 1
    num_type = (byte >> 4) & 7
    try:
      object = num_type_map[num_type]()
    except KeyError:
      assert False, "Not a known type: %d" % num_type
    while((byte & 0x80) != 0):
      byte = ord(map[used])
      used += 1
    raw = map[used:]
    object._text = _decompress(raw)
    return object

  @classmethod
  def _parse_file(cls, map):
    word = (ord(map[0]) << 8) + ord(map[1])
    if ord(map[0]) == 0x78 and (word % 31) == 0:
      return cls._parse_legacy_object(map)
    else:
      return cls._parse_object(map)

  def __init__(self):
    """Don't call this directly"""

  def _parse_text(self):
    """For subclasses to do initialisation time parsing"""

  @classmethod
  def from_file(cls, filename):
    """Get the contents of a SHA file on disk"""
    size = os.path.getsize(filename)
    f = open(filename, 'rb')
    try:
      map = mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ)
      shafile = cls._parse_file(map)
      shafile._parse_text()
      return shafile
    finally:
      f.close()

  @classmethod
  def from_raw_string(cls, type, string):
    """Creates an object of the indicated type from the raw string given.

    Type is the numeric type of an object. String is the raw uncompressed
    contents.
    """
    real_class = num_type_map[type]
    obj = real_class()
    obj._num_type = type
    obj._text = string
    obj._parse_text()
    return obj

  def _header(self):
    return "%s %lu\0" % (self._type, len(self._text))

  def crc32(self):
    return zlib.crc32(self._text)

  def sha(self):
    """The SHA1 object that is the name of this object."""
    ressha = sha.new()
    ressha.update(self._header())
    ressha.update(self._text)
    return ressha

  @property
  def id(self):
      return self.sha().hexdigest()

  def __repr__(self):
    return "<%s %s>" % (self.__class__.__name__, self.id)

  def __eq__(self, other):
    """Return true id the sha of the two objects match.

    The __le__ etc methods aren't overriden as they make no sense,
    certainly at this level.
    """
    return self.sha().digest() == other.sha().digest()


class Blob(ShaFile):
  """A Git Blob object."""

  _type = BLOB_ID
  _num_type = 3

  @property
  def data(self):
    """The text contained within the blob object."""
    return self._text

  @classmethod
  def from_file(cls, filename):
    blob = ShaFile.from_file(filename)
    if blob._type != cls._type:
      raise NotBlobError(filename)
    return blob

  @classmethod
  def from_string(cls, string):
    """Create a blob from a string."""
    shafile = cls()
    shafile._text = string
    return shafile


class Tag(ShaFile):
  """A Git Tag object."""

  _type = TAG_ID

  @classmethod
  def from_file(cls, filename):
    blob = ShaFile.from_file(filename)
    if blob._type != cls._type:
      raise NotBlobError(filename)
    return blob

  @classmethod
  def from_string(cls, string):
    """Create a blob from a string."""
    shafile = cls()
    shafile._text = string
    return shafile

  def _parse_text(self):
    """Grab the metadata attached to the tag"""
    text = self._text
    count = 0
    assert text.startswith(OBJECT_ID), "Invalid tag object, " \
         "must start with %s" % OBJECT_ID
    count += len(OBJECT_ID)
    assert text[count] == ' ', "Invalid tag object, " \
         "%s must be followed by space not %s" % (OBJECT_ID, text[count])
    count += 1
    self._object_sha = text[count:count+40]
    count += 40
    assert text[count] == '\n', "Invalid tag object, " \
         "%s sha must be followed by newline" % OBJECT_ID
    count += 1
    assert text[count:].startswith(TYPE_ID), "Invalid tag object, " \
         "%s sha must be followed by %s" % (OBJECT_ID, TYPE_ID)
    count += len(TYPE_ID)
    assert text[count] == ' ', "Invalid tag object, " \
        "%s must be followed by space not %s" % (TAG_ID, text[count])
    count += 1
    self._object_type = ""
    while text[count] != '\n':
        self._object_type += text[count]
        count += 1
    count += 1
    assert self._object_type in (COMMIT_ID, BLOB_ID, TREE_ID, TAG_ID), "Invalid tag object, " \
        "unexpected object type %s" % self._object_type
    self._object_type = type_map[self._object_type]

    assert text[count:].startswith(TAG_ID), "Invalid tag object, " \
        "object type must be followed by %s" % (TAG_ID)
    count += len(TAG_ID)
    assert text[count] == ' ', "Invalid tag object, " \
        "%s must be followed by space not %s" % (TAG_ID, text[count])
    count += 1
    self._name = ""
    while text[count] != '\n':
        self._name += text[count]
        count += 1
    count += 1

    assert text[count:].startswith(TAGGER_ID), "Invalid tag object, " \
        "%s must be followed by %s" % (TAG_ID, TAGGER_ID)
    count += len(TAGGER_ID)
    assert text[count] == ' ', "Invalid tag object, " \
        "%s must be followed by space not %s" % (TAGGER_ID, text[count])
    count += 1
    self._tagger = ""
    while text[count] != '>':
        assert text[count] != '\n', "Malformed tagger information"
        self._tagger += text[count]
        count += 1
    self._tagger += text[count]
    count += 1
    assert text[count] == ' ', "Invalid tag object, " \
        "tagger information must be followed by space not %s" % text[count]
    count += 1
    self._tag_time = int(text[count:count+10])
    while text[count] != '\n':
        count += 1
    count += 1
    assert text[count] == '\n', "There must be a new line after the headers"
    count += 1
    self._message = text[count:]

  @property
  def object(self):
    """Returns the object pointed by this tag, represented as a tuple(type, sha)"""
    return (self._object_type, self._object_sha)

  @property
  def name(self):
    """Returns the name of this tag"""
    return self._name

  @property
  def tagger(self):
    """Returns the name of the person who created this tag"""
    return self._tagger

  @property
  def tag_time(self):
    """Returns the creation timestamp of the tag.

    Returns it as the number of seconds since the epoch"""
    return self._tag_time

  @property
  def message(self):
    """Returns the message attached to this tag"""
    return self._message


class Tree(ShaFile):
  """A Git tree object"""

  _type = TREE_ID
  _num_type = 2

  def __init__(self):
    self._entries = []

  @classmethod
  def from_file(cls, filename):
    tree = ShaFile.from_file(filename)
    if tree._type != cls._type:
      raise NotTreeError(filename)
    return tree

  def add(self, mode, name, hexsha):
    self._entries.append((mode, name, hexsha))

  def entries(self):
    """Return a list of tuples describing the tree entries"""
    return self._entries

  def _parse_text(self):
    """Grab the entries in the tree"""
    count = 0
    while count < len(self._text):
      mode = 0
      chr = self._text[count]
      while chr != ' ':
        assert chr >= '0' and chr <= '7', "%s is not a valid mode char" % chr
        mode = (mode << 3) + (ord(chr) - ord('0'))
        count += 1
        chr = self._text[count]
      count += 1
      chr = self._text[count]
      name = ''
      while chr != '\0':
        name += chr
        count += 1
        chr = self._text[count]
      count += 1
      chr = self._text[count]
      sha = self._text[count:count+20]
      hexsha = sha_to_hex(sha)
      self.add(mode, name, hexsha)
      count = count + 20

  def serialize(self):
    self._text = ""
    for mode, name, hexsha in self._entries:
        self._text += "%04o %s\0%s" % (mode, name, hex_to_sha(hexsha))


class Commit(ShaFile):
  """A git commit object"""

  _type = COMMIT_ID
  _num_type = 1

  def __init__(self):
    self._parents = []

  @classmethod
  def from_file(cls, filename):
    commit = ShaFile.from_file(filename)
    if commit._type != cls._type:
      raise NotCommitError(filename)
    return commit

  def _parse_text(self):
    text = self._text
    count = 0
    assert text.startswith(TREE_ID), "Invalid commit object, " \
         "must start with %s" % TREE_ID
    count += len(TREE_ID)
    assert text[count] == ' ', "Invalid commit object, " \
         "%s must be followed by space not %s" % (TREE_ID, text[count])
    count += 1
    self._tree = text[count:count+40]
    count = count + 40
    assert text[count] == "\n", "Invalid commit object, " \
         "tree sha must be followed by newline"
    count += 1
    self._parents = []
    while text[count:].startswith(PARENT_ID):
      count += len(PARENT_ID)
      assert text[count] == ' ', "Invalid commit object, " \
           "%s must be followed by space not %s" % (PARENT_ID, text[count])
      count += 1
      self._parents.append(text[count:count+40])
      count += 40
      assert text[count] == "\n", "Invalid commit object, " \
           "parent sha must be followed by newline"
      count += 1
    self._author = None
    if text[count:].startswith(AUTHOR_ID):
      count += len(AUTHOR_ID)
      assert text[count] == ' ', "Invalid commit object, " \
           "%s must be followed by space not %s" % (AUTHOR_ID, text[count])
      count += 1
      self._author = ''
      while text[count] != '>':
        assert text[count] != '\n', "Malformed author information"
        self._author += text[count]
        count += 1
      self._author += text[count]
      count += 1
      while text[count] != '\n':
        count += 1
      count += 1
    self._committer = None
    if text[count:].startswith(COMMITTER_ID):
      count += len(COMMITTER_ID)
      assert text[count] == ' ', "Invalid commit object, " \
           "%s must be followed by space not %s" % (COMMITTER_ID, text[count])
      count += 1
      self._committer = ''
      while text[count] != '>':
        assert text[count] != '\n', "Malformed committer information"
        self._committer += text[count]
        count += 1
      self._committer += text[count]
      count += 1
      assert text[count] == ' ', "Invalid commit object, " \
           "commiter information must be followed by space not %s" % text[count]
      count += 1
      self._commit_time = int(text[count:count+10])
      while text[count] != '\n':
        count += 1
      count += 1
    assert text[count] == '\n', "There must be a new line after the headers"
    count += 1
    # XXX: There can be an encoding field.
    self._message = text[count:]

  def serialize(self):
    self._text = ""
    self._text += "%s %s\n" % (TREE_ID, self._tree)
    for p in self._parents:
      self._text += "%s %s\n" % (PARENT_ID, p)
    self._text += "%s %s %s +0000\n" % (AUTHOR_ID, self._author, str(self._commit_time))
    self._text += "%s %s %s +0000\n" % (COMMITTER_ID, self._committer, str(self._commit_time))
    self._text += "\n" # There must be a new line after the headers
    self._text += self._message

  @property
  def tree(self):
    """Returns the tree that is the state of this commit"""
    return self._tree

  @property
  def parents(self):
    """Return a list of parents of this commit."""
    return self._parents

  @property
  def author(self):
    """Returns the name of the author of the commit"""
    return self._author

  @property
  def committer(self):
    """Returns the name of the committer of the commit"""
    return self._committer

  @property
  def message(self):
    """Returns the commit message"""
    return self._message

  @property
  def commit_time(self):
    """Returns the timestamp of the commit.
    
    Returns it as the number of seconds since the epoch.
    """
    return self._commit_time


type_map = {
  BLOB_ID : Blob,
  TREE_ID : Tree,
  COMMIT_ID : Commit,
  TAG_ID: Tag,
}

num_type_map = {
  0: None,
  1: Commit,
  2: Tree,
  3: Blob,
  4: Tag,
  # 5 Is reserved for further expansion
}

