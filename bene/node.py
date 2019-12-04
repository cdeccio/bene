import copy
import logging

from .forward import ForwardingTable
from .ip import BROADCAST_IP_ADDRESS, IPAddress, Subnet
from .sim import Sim

logger = logging.getLogger(__name__)


class Node(object):
    _allow_forward = True

    def __init__(self, hostname, default_gateway=None):
        self.hostname = hostname
        self.default_gateway = default_gateway
        self.links = []
        self.protocols = {}
        self.forwarding_table = ForwardingTable()
        self.arp_table = {}

    # -- Links --

    def add_link(self, link):
        self.links.append(link)

    def delete_link(self, link):
        if link not in self.links:
            return
        self.links.remove(link)

    def get_link(self, name):
        for link in self.links:
            if link.endpoint.hostname == name:
                return link
        return None

    def get_address(self, name):
        for link in self.links:
            if link.endpoint.hostname == name:
                return link.address
        return None

    # -- Protocols --

    def add_protocol(self, protocol, handler):
        self.protocols[protocol] = handler

    def delete_protocol(self, protocol):
        if protocol not in self.protocols:
            return
        del self.protocols[protocol]

    # -- Forwarding table --

    def add_forwarding_entry(self, subnet, link, next_hop=None, ptp=True):
        # if an IP address was passed, then convert it to a subnet with
        # maximum-length prefix
        if isinstance(subnet, IPAddress):
            subnet = Subnet(subnet, subnet.address_len)
        if next_hop is None and ptp:
            next_hop = link.endpoint.get_link(self.hostname)
        self.forwarding_table.add_entry(subnet, link, next_hop)

    def delete_forwarding_entry(self, subnet):
        self.forwarding_table.remove_entry(subnet)

    # -- ARP table --

    def add_arp_entry(self, address, mac_address):
        self.arp_table[address] = mac_address

    def delete_arp_entry(self, address):
        if address not in self.arp_table:
            return
        del self.arp_table[address]

    # -- Handling packets --

    def send_packet(self, packet):
        # if this is the first time we have seen this packet, set its
        # creation timestamp
        if packet.created is None:
            packet.created = Sim.scheduler.current_time()

        # forward the packet
        self.forward_packet(packet)

    def receive_packet(self, packet_link):
        packet, incoming_link = packet_link
        # handle broadcast packets
        if packet.destination_address == BROADCAST_IP_ADDRESS:
            logger.debug("%s received broadcast packet" % self.hostname)
            self.deliver_packet(packet, incoming_link)
        else:
            # check if unicast packet is for me
            for link in self.links:
                if link.address == packet.destination_address:
                    logger.info("%s received packet" % self.hostname)
                    self.deliver_packet(packet, incoming_link)
                    return

        if self._allow_forward:
            # decrement the TTL and drop if it has reached the last hop
            packet.ttl -= 1
            if packet.ttl <= 0:
                logger.debug("%s dropping packet due to TTL expired" % self.hostname)
                return

            # forward the packet
            self.forward_packet(packet)

    def deliver_packet(self, packet, link):
        if packet.protocol not in self.protocols:
            return
        self.protocols[packet.protocol].receive_packet(packet, link=link)

    def forward_packet(self, packet):
        if packet.destination_address == BROADCAST_IP_ADDRESS:
            # broadcast the packet
            self.forward_broadcast_packet(packet)
        else:
            # forward the packet
            self.forward_unicast_packet(packet)

    def get_forwarding_entry(self, packet):
        link, next_hop_address = self.forwarding_table.get_forwarding_entry(packet.destination_address)

        return link, next_hop_address

    def send_packet_on_link(self, packet, link, next_hop_address):
        link.send_packet(packet)

    def forward_unicast_packet(self, packet):
        link, next_hop_address = self.get_forwarding_entry(packet)
        if link is None:
            logger.warn("%s no routing entry for %s" % (self.hostname, packet.destination_address))
            return
        logger.info("%s forwarding packet to %s (Next hop: %s)" % (self.hostname, packet.destination_address, next_hop_address))
        self.send_packet_on_link(packet, link, next_hop_address)

    def forward_broadcast_packet(self, packet):
        for link in self.links:
            logger.debug("%s forwarding broadcast packet to %s" % (self.hostname, link.endpoint.hostname))
            packet_copy = copy.deepcopy(packet)
            link.send_packet(packet_copy)

class Host(Node):
    _allow_forward = False
