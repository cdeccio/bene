from .ip import Subnet

class ForwardingTable(object):
    def __init__(self):
        self.entries = {}

    def add_entry(self, subnet, link, next_hop):
        self.entries[subnet] = (link, next_hop)

    def remove_entry(self, subnet):
        if subnet in self.entries:
            del self.entries[subnet]

    def get_forwarding_entry(self, subnet):
        '''
        Return the entry having the longest prefix match of ip_address.  If
        there is no match, return (None, None).
        '''
        #FIXME
        if subnet in self.entries:
            return self.entries[subnet]
        else:
            return None, None
