# server.py -- Implementation of the server side git protocols
# Copryight (C) 2008 John Carr <john.carr@unrouted.co.uk>
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

import SocketServer

class Backend(object):

    def get_refs(self):
        """
        Get all the refs in the repository

        :return: list of tuple(name, sha)
        """
        raise NotImplementedError

    def has_revision(self, sha):
        """
        Is a given sha in this repository?

        :return: True or False
        """
        raise NotImplementedError

    def apply_pack(self, refs, read):
        """ Import a set of changes into a repository and update the refs

        :param refs: list of tuple(name, sha)
        :param read: callback to read from the incoming pack
        """
        raise NotImplementedError

    def generate_pack(self, want, have, write, progress):
        """
        Generate a pack containing all commits a client is missing

        :param want: is a list of sha's the client desires
        :param have: is a list of sha's the client has (allowing us to send the minimal pack)
        :param write: is a callback to write pack data to the client
        :param progress: is a callback to send progress messages to the client
        """
        raise NotImplementedError


class Handler(object):

    def __init__(self, backend, read, write):
        self.backend = backend
        self.read = read
        self.write = write

    def read_pkt_line(self):
        """
        Reads a 'pkt line' from the remote git process

        :return: The next string from the stream
        """
        sizestr = self.read(4)
        if not sizestr:
            return None
        size = int(sizestr, 16)
        if size == 0:
            return None
        return self.read(size-4)

    def write_pkt_line(self, line):
        """
        Sends a 'pkt line' to the remote git process

        :param line: A string containing the data to send
        """
        self.write("%04x%s" % (len(line)+4, line))

    def write_sideband(self, channel, blob):
        """
        Write data to the sideband (a git multiplexing method)

        :param channel: int specifying which channel to write to
        :param blob: a blob of data (as a string) to send on this channel
        """
        # a pktline can be a max of 65535. a sideband line can therefore be
        # 65535-5 = 65530
        # WTF: Why have the len in ASCII, but the channel in binary.
        while blob:
            self.write_pkt_line("%s%s" % (chr(channel), blob[:65530]))
            blob = blob[65530:]

    def handle(self):
        """
        Deal with the request
        """
        raise NotImplementedError


class UploadPackHandler(Handler):

    def handle(self):
        refs = self.backend.get_refs()

        if refs:
            self.write_pkt_line("%s %s\x00multi_ack side-band-64k thin-pack ofs-delta\n" % (refs[0][1], refs[0][0]))
            for i in range(1, len(refs)):
                ref = refs[i]
                self.write_pkt_line("%s %s\n" % (ref[1], ref[0]))

        # i'm done...
        self.write("0000")

        # Now client will either send "0000", meaning that it doesnt want to pull.
        # or it will start sending want want want commands
        want = self.read_pkt_line()
        if want == None:
            return
       
        # Keep reading the list of demands until we hit another "0000" 
        want_revs = []
        while want and want[:4] == 'want':
            want_rev = want[5:40]
            # FIXME: This check probably isnt needed?
            if self.backend.has_revision(want_rev):
               want_revs.append(want_rev)
            want = self.read_pkt_line()
        
        # Client will now tell us which commits it already has - if we have them we ACK them
        # this allows client to stop looking at that commits parents (main reason why git pull is fast)
        last_sha = None
        have_revs = []
        have = self.read_pkt_line()
        while have and have[:4] == 'have':
            have_ref = have[6:40]
            if self.backend.has_revision(hav_rev):
                self.write_pkt_line("ACK %s continue\n" % sha)
                last_sha = sha
                have_revs.append(rev_id)
            have = self.read_pkt_line()

        # At some point client will stop sending commits and will tell us it is done
        assert(have[:4] == "done")

        # Oddness: Git seems to resend the last ACK, without the "continue" statement
        if last_sha:
            self.write_pkt_line("ACK %s\n" % last_sha)

        # The exchange finishes with a NAK
        self.write_pkt_line("NAK\n")
      
        #if True: # False: #self.no_progress == False:
        #    self.write_sideband(2, "Bazaar is preparing your pack, plz hold.\n")

        #    for x in range(1,200)
        #        self.write_sideband(2, "Counting objects: %d\x0d" % x*2)
        #    self.write_sideband(2, "Counting objects: 200, done.\n")

        #    for x in range(1,100):
        #        self.write_sideband(2, "Compressiong objects: %d (%d/%d)\x0d" % (x, x*2, 200))
        #    self.write_sideband(2, "Compressing objects: 100% (200/200), done.\n")

        self.backend.generate_pack(want_revs, have_revs, self.write, None)


class ReceivePackHandler(Handler):

    def handle(self):
        refs = self.backend.get_refs()

        if refs:
            self.write_pkt_line("%s %s\x00multi_ack side-band-64k thin-pack ofs-delta\n" % (refs[0][1], refs[0][0]))
            for i in range(1, len(refs)):
                ref = refs[i]
                self.write_pkt_line("%s %s\n" % (ref[1], ref[0]))

        self.write("0000")

        client_refs = []
        ref = self.read_pkt_line()
        while ref:
            client_refs.append(ref.split())
            ref = self.read_pkt_line()

        if len(client_refs) == 0:
            return None

        self.backend.apply_pack(client_refs, self.read)


class TCPGitRequestHandler(SocketServer.StreamRequestHandler, Handler):

    def __init__(self, request, client_address, server):
        SocketServer.StreamRequestHandler.__init__(self, request, client_address, server)

    def handle(self):
        #FIXME: StreamRequestHandler seems to be the thing that calls handle(),
        #so we can't call this in a sane place??
        Handler.__init__(self, self.server.backend, self.rfile.read, self.wfile.write)

        request = self.read_pkt_line()

        # up until the space is the command to run, everything after is parameters
        splice_point = request.find(' ')
        command, params = request[:splice_point], request[splice_point+1:]

        # params are null seperated
        params = params.split(chr(0))

        # switch case to handle the specific git command
        if command == 'git-upload-pack':
            cls = UploadPackHandler
        elif command == 'git-receive-pack':
            cls = ReceivePackHandler
        else:
            return

        h = cls(self.backend, self.read, self.write)
        h.handle()


class TCPGitServer(SocketServer.TCPServer):

    allow_reuse_address = True
    serve = SocketServer.TCPServer.serve_forever

    def __init__(self, backend, addr):
        self.backend = backend
        SocketServer.TCPServer.__init__(self, addr, TCPGitRequestHandler)


