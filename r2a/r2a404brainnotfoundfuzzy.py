from player.parser import *
from r2a.ir2a import IR2A
import random
import datetime

import json
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
        self.config_parameters = {}
        self.medium_buffer = 40
        self.qualities_len = 20
        self.duration = 0

    def add_time(self, time_to_add):
        self.time_of_request += [time_to_add]

    def add_speed(self, speed_to_add):
        self.connection_speed_arr += [speed_to_add]

    def add_bit_len(self, bit_to_add):
        self.bit_len += [bit_to_add]

    def add_qualities_len(self, len_to_add):
        self.qualities_len = len_to_add

    def add_duration(self, duration):
        self.duration = int(duration['duration'])

    def handle_xml_request(self, msg):
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # getting qi list
        self.parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = self.parsed_mpd.get_qi()
        self.add_qualities_len(len(self.qi))
        self.add_duration(self.parsed_mpd.get_segment_template())
        self.send_up(msg)

    def handle_segment_size_request(self, msg):

        moving_avarage_factor = 5 # Usado para fazer média das últimas 5 qualidades para não variar bruscamente
        buffer_now = self.whiteboard.get_playback_buffer_size()
        speed_now = 0
        time_stop = datetime.datetime.now()
        max_speed = 2
        quality_moving_avg = 0
        medium_quality = 8 # Valor inicial já que a qualidade média é calculada em tempo real usando os últimos 20 items
        medium_conn_speed = -1
        self.add_time(time_stop.timestamp())
        if len(self.time_of_request) > 2:
            time_to_request = self.time_of_request[-1] - self.time_of_request[-2]
            speed_now = self.bit_len[-1] / (time_to_request)
            self.add_speed(speed_now)
            max_speed = max(self.connection_speed_arr)
            medium_conn_speed = avg(self.connection_speed_arr[-20:])
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
            medium_quality = medium_quality[-20:]
            medium_quality = [item[1] for item in medium_quality]
            medium_quality = avg_the_last_is_the_most_significant(medium_quality)
        else:
            quality_moving_avg = 0

        max_buffer_size = self.config_parameters["max_buffer_size"]
        if len(self.time_of_request) < 4:
            medium_buffer_size = 0.5 * max_buffer_size
        else:
            medium_buffer_size =  0.6 * max_buffer_size - (1 * max_buffer_size*(self.time_of_request[-1] - self.time_of_request[0]) / self.duration)
            if medium_buffer_size < 0.2 * max_buffer_size:
                medium_buffer_size = 0.2 * max_buffer_size
            print('buffer -----------', medium_buffer_size)

        max_speed_step = 1
        if max_speed > 100:
            max_speed_step = max_speed / 40
        connection_speed = ctrl.Antecedent(np.arange(0, max_speed, max_speed_step), 'connection_speed')
        buffer = ctrl.Antecedent(np.arange(0, max_buffer_size + 1, 1), 'buffer')
        quality = ctrl.Consequent(np.arange(0, self.qualities_len, 1), 'quality')
        # connection_speed.automf(3)

        if medium_conn_speed == -1:
            medium_conn_speed = max_speed / 2
        connection_speed['poor'] = fuzz.trimf(connection_speed.universe, [0, 0, round(max_speed)])
        connection_speed['average'] = fuzz.trimf(connection_speed.universe, [0, round(medium_conn_speed), round(max_speed)])
        connection_speed['good'] = fuzz.trimf(connection_speed.universe, [round(medium_conn_speed), round(max_speed), round(max_speed)])

        buffer['low'] = fuzz.trimf(buffer.universe, [0, 0, round(medium_buffer_size)])
        buffer['medium'] = fuzz.trimf(buffer.universe, [0, round(medium_buffer_size), max_buffer_size])
        buffer['high'] = fuzz.trimf(buffer.universe, [round(medium_buffer_size), max_buffer_size, max_buffer_size])

        quality['low'] = fuzz.trimf(quality.universe, [0, 0, round(medium_quality)])
        quality['medium'] = fuzz.trimf(quality.universe, [0, round(medium_quality), self.qualities_len - 1])
        quality['high'] = fuzz.trimf(quality.universe, [round(medium_quality), self.qualities_len - 1, self.qualities_len - 1])

        # quality.view()
        # wait = input("Press Enter to continue.")
        rule1 = ctrl.Rule(connection_speed['poor'] | buffer['low'], quality['low'])
        rule2 = ctrl.Rule(connection_speed['average'], quality['medium'])
        # rule2 = ctrl.Rule(connection_speed['average'] & buffer['medium'], quality['medium'])
        rule3 = ctrl.Rule(connection_speed['good'] & buffer['low'], quality['medium'])
        # rule4 = ctrl.Rule(connection_speed['good'] & buffer['medium'], quality['high'])
        rule4 = ctrl.Rule(connection_speed['good'] & buffer['high'], quality['high'])

        quality_ctrl = ctrl.ControlSystem([rule1, rule2, rule3, rule4])
        new_quality = ctrl.ControlSystemSimulation(quality_ctrl)

        new_quality.input['buffer'] = buffer_now
        new_quality.input['connection_speed'] = speed_now
        new_quality.compute()
        quality_moving_avg = avg([quality_moving_avg, new_quality.output['quality']])
        print('new quality---->', quality_moving_avg)
        # msg.add_quality_id(self.qi[int(quality_moving_avg)])
        msg.add_quality_id(self.qi[round(quality_moving_avg)])
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        bit_length = msg.get_bit_length()
        self.add_bit_len(bit_length)
        self.send_up(msg)

    def initialize(self):
        with open('dash_client.json') as f:
            self.config_parameters = json.load(f)
        

    def finalization(self):
        pass
