import logging

from .buffer import SendBuffer, ReceiveBuffer
from .connection import Connection
from .sim import Sim
from .tcppacket import TCPPacket

logger = logging.getLogger(__name__)
sender_logger = logger.getChild('sender')
receiver_logger = logger.getChild('receiver')
sequence_logger = logger.getChild('sequence')
cwnd_logger = logger.getChild('cwnd')


class TCP(Connection):
    """ A TCP connection between two hosts."""

    def __init__(self, transport, source_address, source_port,
                 destination_address, destination_port, app=None, window=1000,drop=[]):
        Connection.__init__(self, transport, source_address, source_port,
                            destination_address, destination_port, app)

        # -- Sender functionality

        # send window; represents the total number of bytes that may
        # be outstanding at one time
        self.cwnd = window
        # send buffer
        self.send_buffer = SendBuffer()
        # maximum segment size, in bytes
        self.mss = 1000
        # largest sequence number that has been ACKed so far; represents
        # the next sequence number the client expects to receive
        self.sequence = 1
        # plot sequence numbers
        self.plot_sequence_header()
        # plot cwnd numbers
        self.plot_cwnd_header()
        self.plot_cwnd()
        # packets to drop
        self.drop = drop
        self.dropped = []
        # retransmission timer
        self.timer = None
        # timeout duration in seconds
        self.timeout = 1

        # -- Receiver functionality

        # receive buffer
        self.receive_buffer = ReceiveBuffer()
        # ack number to send; represents the largest in-order sequence
        # number not yet received
        self.ack = 1

    def plot_sequence_header(self):
        if self.node.hostname =='n1':
            sequence_logger.debug('Time,Sequence Number,Event')

    def plot_sequence(self,sequence,event):
        if self.node.hostname =='n1':
            sequence_logger.debug('%s,%s,%s' % (Sim.scheduler.current_time(),sequence,event))

    def plot_cwnd_header(self):
        if self.node.hostname =='n1':
            cwnd_logger.debug('Time,Congestion Window')

    def plot_cwnd(self):
        ''' Print plotting messages. '''
        if self.node.hostname =='n1':
            cwnd_logger.debug('%s,%s' % (Sim.scheduler.current_time(), self.cwnd))

    def receive_packet(self, packet, **kwargs):
        """ Receive a packet from the network layer. """
        if packet.ack_number > 0:
            # handle ACK
            self.handle_ack(packet)
        if packet.length > 0:
            # handle data
            self.handle_data(packet)

    ''' Sender '''

    def send(self, data):
        """ Send data on the connection. Called by the application. This
            code currently sends all data immediately. """
        self.send_packet(data, self.sequence)
        self.timer = Sim.scheduler.add(delay=self.timeout, event='retransmit', handler=self.retransmit)

    def send_packet(self, data, sequence, ack=0):
        packet = TCPPacket(source_address=self.source_address,
                           source_port=self.source_port,
                           destination_address=self.destination_address,
                           destination_port=self.destination_port,
                           body=data,
                           sequence=sequence, ack_number=ack)

        if sequence in self.drop and not sequence in self.dropped:
            # drop the packet
            self.dropped.append(sequence)
            self.plot_sequence(sequence,'drop')
            sender_logger.warning("%s (%s) dropping TCP segment to %s for %d" % (
                self.node.hostname, self.source_address, self.destination_address, packet.sequence))
        else:
            # send the packet
            self.plot_sequence(sequence,'send')
            sender_logger.debug("%s (%s) sending TCP segment to %s for %d" % (
                self.node.hostname, self.source_address, self.destination_address, packet.sequence))
            self.transport.send_packet(packet)

        # set a timer
        if not self.timer:
            self.timer = Sim.scheduler.add(delay=self.timeout, event='retransmit', handler=self.retransmit)

    def handle_ack(self, packet):
        """ Handle an incoming ACK. """
        self.plot_sequence(packet.ack_number - packet.length,'ack')
        sender_logger.debug("%s (%s) received ACK from %s for %d" % (
            self.node.hostname, packet.destination_address, packet.source_address, packet.ack_number))
        self.cancel_timer()

    def retransmit(self, event):
        """ Retransmit data. """
        sender_logger.warning("%s (%s) retransmission timer fired" % (self.node.hostname, self.source_address))

    def cancel_timer(self):
        """ Cancel the timer. """
        if not self.timer:
            return
        sender_logger.debug("%s (%s) canceled timer" % (self.node.hostname, self.source_address))
        Sim.scheduler.cancel(self.timer)
        self.timer = None

    ''' Receiver '''

    def handle_data(self, packet):
        """ Handle incoming data. This code currently gives all data to
            the application, regardless of whether it is in order, and sends
            an ACK."""
        sender_logger.debug("%s (%s) received TCP segment from %s for %d" % (
            self.node.hostname, packet.destination_address, packet.source_address, packet.sequence))
        self.app.receive_data(packet.body)
        self.send_ack()

    def send_ack(self):
        """ Send an ack. """
        packet = TCPPacket(source_address=self.source_address,
                           source_port=self.source_port,
                           destination_address=self.destination_address,
                           destination_port=self.destination_port,
                           sequence=self.sequence, ack_number=self.ack)
        # send the packet
        receiver_logger.debug("%s (%s) sending TCP ACK to %s for %d" % (
            self.node.hostname, self.source_address, self.destination_address, packet.ack_number))
        self.transport.send_packet(packet)
