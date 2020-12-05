from player.parser import *
from r2a.ir2a import IR2A
import random
import datetime

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def normalize(min, max, x):
    return (x - min)/(max - min)


def normalize_negative(min, max, x):
    return(2*(x - min)/(max - min) - 1)


def avg(my_list):
    return sum(my_list)/len(my_list)

def avg_the_last_is_the_most_significant(my_list):
  total_weight = 0
  average = 0
  for i in range(len(my_list)):
    total_weight += i + 1
    average += (i+1)*my_list[i]
  average = average / total_weight
  return average


class R2A404BrainNotFoundFuzzy(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id)
        self.parsed_mpd = ''
        self.qi = []
        self.time_of_request = []
        self.bit_len = []
        self.connection_speed_arr = []

    def add_time(self, time_to_add):
        self.time_of_request += [time_to_add]

    def add_speed(self, speed_to_add):
        self.connection_speed_arr += [speed_to_add]

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

        # Fórmula usada

        moving_avarage_factor = 5
        buffer_now = self.whiteboard.get_playback_buffer_size()
        speed_now = 0
        time_stop = datetime.datetime.now()
        max_speed = 1
        quality_moving_avg = 0
        medium_quality = 8
        self.add_time(time_stop.timestamp())
        if len(self.time_of_request) > 2:
            time_to_request = self.time_of_request[-1] - self.time_of_request[-2]
            speed_now = self.bit_len[-1] / \
                (time_to_request)
            self.add_speed(speed_now)
            max_speed = max(self.connection_speed_arr)
        if len(buffer_now) > 0:
            buffer_now = buffer_now[-1][1]
        else:
            buffer_now = 0
        qualityArr = self.whiteboard.get_playback_qi()
        if len(qualityArr) > 0:
            medium_quality = qualityArr
            qualityArr = qualityArr[-moving_avarage_factor:]
            qualityArr = [item[1] for item in qualityArr]
            quality_moving_avg = avg(qualityArr)
            medium_quality = medium_quality[-10:]
            medium_quality = [item[1] for item in medium_quality]
            medium_quality = avg_the_last_is_the_most_significant(medium_quality)
        else:
            quality_moving_avg = 0


        connection_speed = ctrl.Antecedent(np.arange(0, max_speed, 1), 'connection_speed')
        buffer = ctrl.Antecedent(np.arange(0, 61, 1), 'buffer')
        quality = ctrl.Consequent(np.arange(0, 20, 1), 'quality')
        connection_speed.automf(3)

        buffer['low'] = fuzz.trimf(buffer.universe, [0, 0, 30])
        buffer['medium'] = fuzz.trimf(buffer.universe, [0, 30, 60])
        buffer['high'] = fuzz.trimf(buffer.universe, [30, 60, 60])

        quality['low'] = fuzz.trimf(quality.universe, [0, 0, medium_quality])
        quality['medium'] = fuzz.trimf(quality.universe, [0, medium_quality, 19])
        quality['high'] = fuzz.gaussmf(quality.universe, 19, 3)

        # quality.view()
        # wait = input("Press Enter to continue.")

        rule1 = ctrl.Rule(connection_speed['poor'] | buffer['low'], quality['low'])
        rule2 = ctrl.Rule(connection_speed['average'], quality['medium'])
        rule3 = ctrl.Rule(connection_speed['good'] & buffer['medium'], quality['high'])

        quality_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
        new_quality = ctrl.ControlSystemSimulation(quality_ctrl)

        new_quality.input['buffer'] = buffer_now
        new_quality.input['connection_speed'] = speed_now
        new_quality.compute()
        quality_moving_avg = avg([quality_moving_avg, new_quality.output['quality']])
        print('new quality---->', quality_moving_avg)
        msg.add_quality_id(self.qi[int(quality_moving_avg)])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        bit_length = msg.get_bit_length()
        self.add_bit_len(bit_length)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
