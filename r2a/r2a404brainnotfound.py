from player.parser import *
from r2a.ir2a import IR2A
import random

def normalize(min, max, x):
  return (x - min)/(max - min)

def normalize_negative(min, max, x):
  return(2*(x - min)/(max - min) -1)

class R2A404BrainNotFound(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.parsed_mpd = ''
        self.qi = []

    def handle_xml_request(self, msg):
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        buffer = self.whiteboard.get_playback_buffer_size()
        if len(buffer) > 0:
            buffer = buffer[-1][1]
        else:
            buffer = 0
        quality = self.whiteboard.get_playback_qi()
        if len(quality) > 0:
            quality = quality[-1][1]
        else:
            quality = 0
        score = 0
        quality_rate = 1
        buffer_rate = 1
        score_rate = 10
        q = quality
        if quality == 0:
            q = 0.1
        score += quality_rate * normalize(0, 19, 1/q)
        # score -= 3
        score += buffer_rate * normalize_negative(0, 60, buffer)
        print('-----', score_rate * score)

        quality += score_rate * score
        if quality > 19:
            quality = 19
        if quality < 0:
            quality = 0
        
        msg.add_quality_id(self.qi[int(quality)])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
