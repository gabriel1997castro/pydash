from player.parser import *
from r2a.ir2a import IR2A
import random
import datetime


def normalize(min, max, x):
    return (x - min)/(max - min)


def normalize_negative(min, max, x):
    return(2*(x - min)/(max - min) - 1)


def avg(my_list):
    return sum(my_list)/len(my_list)


class R2A404BrainNotFound(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id)
        self.parsed_mpd = ''
        self.qi = []
        self.time_of_request = []
        self.bit_len = []
        self.connection_speed = []
        self.quality_id = []

    def add_q_id(self, q_id):
        self.quality_id += [q_id]

    def add_time(self, time_to_add):
        self.time_of_request += [time_to_add]

    def add_bit_len(self, bit_to_add):
        self.bit_len += [bit_to_add]

    def handle_xml_request(self, msg):
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        moving_avarage_factor = 4
        datetime.datetime.now()
        buffer = self.whiteboard.get_playback_buffer_size()
        speed = 0
        if len(buffer) > 0:
            buffer = buffer[-1][1]
            time_stop = datetime.datetime.now()
            self.add_time(time_stop.timestamp())
            if len(self.time_of_request) > 2:
                time_to_request = self.time_of_request[-1] - self.time_of_request[-2]
                speed = self.bit_len[-1] / \
                    (time_to_request)
        else:
            buffer = 0
        qualityArr = self.whiteboard.get_playback_qi()
        if len(qualityArr) > 0:
            qualityArr = qualityArr[-moving_avarage_factor:]
            qualityArr = [item[1] for item in qualityArr]
            quality = avg(qualityArr)
        else:
            quality = 0
        score = 0
        quality_rate = 1.2
        buffer_rate = 1
        speed_rate = 5
        time_rate = 2
        score_rate = 4
        q = quality
        if quality == 0:
            q = 0.05
        # score += quality_rate * normalize(0, 19, q)
        if len(self.connection_speed) > 2:
            # score += 1/normalize_negative(0, 1.8, time_to_request)
            score += speed_rate * \
                normalize_negative(min(self.connection_speed),
                                   max(self.connection_speed), speed)
        # score -= 3
        score += buffer_rate * normalize_negative(0, 30, buffer)


        score_total = score_rate * score
        if len(qualityArr) > 2:
            new_quality = avg(qualityArr+[qualityArr[-1] + score_total])
        else:
            new_quality = score_total
        print('new quality', new_quality)
        if new_quality > 19:
            new_quality = 19
        if new_quality < 0:
            new_quality = 0

        msg.add_quality_id(self.qi[round(new_quality)])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        bit_length = msg.get_bit_length()
        self.add_bit_len(bit_length)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
