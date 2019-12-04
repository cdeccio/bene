import logging
import random

from .tcp import sequence_logger
from .sim import Sim

logger = logging.getLogger(__name__)
queue_logger = logger.getChild('queue')


class Link(object):
    def __init__(self, mac_address=None, address=None, prefix_len=None, startpoint=None, endpoint=None, queue_size=None,
                 bandwidth=1000000.0, propagation=0.001, loss=0):
        self.running = True
        self.mac_address = mac_address
        self.address = address
        if address is not None:
            if prefix_len is None:
                prefix_len = address.address_len
            self.subnet = address.subnet(prefix_len)
        else:
            self.subnet = None
        self.startpoint = startpoint
        self.endpoint = endpoint
        self.queue_size = queue_size
        self.bandwidth = bandwidth
        self.propagation = propagation
        self.loss = loss
        self.busy = False
        self.queue = []
        if (self.startpoint.hostname == 'n1'):
            queue_logger.debug('Time,Queue Size,Event')

    # -- Handling packets --

    def send_packet(self, packet):
        # check if link is running
        if not self.running:
            return
        # drop packet due to queue overflow
        if self.queue_size and len(self.queue) == self.queue_size:
            logger.warning("%s dropped packet due to queue overflow" % self.address)
            if (self.startpoint.hostname == 'n1'):
                queue_logger.debug('%s,%s,%s' % (Sim.scheduler.current_time(),len(self.queue),'drop'))
            return
        # drop packet due to random loss
        if self.loss > 0 and random.random() < self.loss:
            logger.warning("%s dropped packet due to random loss" % self.address)
            return
        packet.enter_queue = Sim.scheduler.current_time()
        if len(self.queue) == 0 and not self.busy:
            # packet can be sent immediately
            self.busy = True
            self.transmit(packet)
        else:
            # add packet to queue
            self.queue.append(packet)
            if (self.startpoint.hostname == 'n1'):
                queue_logger.debug('%s,%s,%s' % (Sim.scheduler.current_time(),len(self.queue),'size'))


    def transmit(self, packet):
        if (self.startpoint.hostname == 'n1'):
            try:
                sequence_logger.debug('%s,%s,%s' % (Sim.scheduler.current_time(),packet.sequence,'transmit'))
            except:
                pass
        packet.queueing_delay += Sim.scheduler.current_time() - packet.enter_queue
        delay = (8.0 * packet.length) / self.bandwidth
        packet.transmission_delay += delay
        packet.propagation_delay += self.propagation

        receiver = self.endpoint
        receiving_link = receiver.get_link(self.startpoint.hostname)

        # schedule packet arrival at end of link
        Sim.scheduler.add(delay=delay + self.propagation, event=(packet, receiving_link), handler=receiver.receive_packet)
        # schedule next transmission
        Sim.scheduler.add(delay=delay, event='finish', handler=self.get_next_packet)

    def get_next_packet(self, event):
        if len(self.queue) > 0:
            packet = self.queue.pop(0)
            if (self.startpoint.hostname == 'n1'):
                queue_logger.debug('%s,%s,%s' % (Sim.scheduler.current_time(),len(self.queue),'size'))
            self.transmit(packet)
        else:
            self.busy = False

    def down(self, event):
        self.running = False

    def up(self, event):
        self.running = True
