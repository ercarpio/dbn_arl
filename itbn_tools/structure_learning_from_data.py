import os
import numpy as np
import pandas as pd
import networkx as nx
from pgmpy.models import IntervalTemporalBayesianNetwork as ITBN
from pgmpy.estimators import HillClimbSearchITBN, BicScore

EVENT_LABEL_IX = 0
VALUE_IX = 1

sessions = dict()
# events that are found in the label files
actions_dict = {'command_s': 0,     'command_e': 1,     'command': 2,
                'noise_0_s': 0,     'noise_0_e': 1,     'noise_0': 2,
                'prompt_s': 3,      'prompt_e': 4,      'prompt': 5,
                'noise_1_s': 3,     'noise_1_e': 4,     'noise_1': 5,
                'reward_s': 6,      'reward_e': 7,      'reward': 8,
                'abort_s': 9,       'abort_e': 10,      'abort': 11,
                'audio_0_s': 12,    'audio_0_e': 13,    'audio_0': 14,
                'audio_1_s': 12,    'audio_1_e': 13,    'audio_1': 14,
                'gesture_0_s': 12,  'gesture_0_e': 13,  'gesture_0': 14,
                'gesture_1_s': 12,  'gesture_1_e': 13,  'gesture_1': 14,
                'response_s': 12,  'response_e': 13,  'response': 14}
# some sessions need to be corrected to deliver a reward after a correct response
files_to_shorten = {'01': ['a0', 'g0', 'ga0', 'za0', 'zg0', 'zga0'],
                    '02': ['a0', 'g0', 'ga0', 'za0', 'zg0', 'zga0'],
                    '03': ['a0', 'ga0', 'za0', 'zg0', 'zga0'],
                    '04': ['a0', 'g0', 'ga0', 'za0', 'zg0', 'zga0']}
# some sessions need to be corrected to remove a correct response before the prompt
files_to_correct = {'01': ['a1', 'g1', 'ga1', 'za1', 'zg1', 'zga1'],
                    '02': ['a1', 'g1', 'ga1', 'za1', 'zg1', 'zga1']}

data_set_file = open("../data/data_sets.txt", 'r')
validation_set = list()
training_set = list()
for line in data_set_file:
    line = line.replace('\n', '').replace('../../../ITBN_tfrecords', '../labels').replace('.tfrecord', '.txt')
    if '_validation' in line:
        line = line.replace('_validation', '')
        validation_set.append(line)
    else:
        training_set.append(line)
data_set_file.close()

# go over all the files in the label directory
for root, subFolders, files in os.walk('../labels/'):
    for f in files:
        shorten = False
        correct = False
        n_times = dict()
        # open each file and read line by line
        file_path = root + '/' + f
        if file_path in training_set:
            rewarded = False
            session_dict = dict()
            session_file = open(file_path, 'r')
            # check if the session needs to be shortened
            if f.replace('.txt', '') in files_to_shorten.get(root.split('_')[1], []):
                shorten = True
            # check if the session needs to be corrected
            elif f.replace('.txt', '') in files_to_correct.get(root.split('_')[1], []):
                correct = True
            for line in session_file:
                if 'command' not in line and 'prompt' not in line:
                    line = line.replace('\n', '')
                    if 'noise_0' in line:
                        line = line.replace('noise_0', 'command')
                    if 'noise_1' in line:
                        line = line.replace('noise_1', 'prompt')
                    # assign the reward_s the time of noise_1_s, fix reward_e accordingly
                    # and remove times of noise_1, audio_1 and gesture_1
                    if shorten:
                        if 'prompt_s' in line:
                            n_times['prompt_s'] = float(line.split(' ')[VALUE_IX])
                            session_dict['reward_s'] = n_times['prompt_s']
                            session_dict['reward_e'] = n_times['prompt_s'] + n_times['reward_e'] - n_times['reward_s']
                            continue
                        elif '_1' in line or 'reward_e' in line or 'abort_s' in line or 'prompt_e' in line:
                            continue
                        elif 'reward_s' in line:
                            n_times['reward_s'] = float(line.split(' ')[VALUE_IX])
                            continue
                        elif 'abort_e' in line:
                            n_times['reward_e'] = float(line.split(' ')[VALUE_IX])
                            continue
                    # remove the times of audio_0 and gesture_0
                    elif correct:
                        if '_0' in line:
                            continue
                    if '_1' in line or '_0' in line:
                        if '_s' in line:
                            n_time = float(line.split(' ')[VALUE_IX])
                            line = 'response_s'
                            if session_dict.get(line, None) is not None:
                                line = line + ' ' + str(min(n_time, session_dict[line]))
                            else:
                                line = line + ' ' + str(n_time)
                        else:
                            n_time = float(line.split(' ')[VALUE_IX])
                            line = 'response_e'
                            if session_dict.get(line, None) is not None:
                                line = line + ' ' + str(max(n_time, session_dict[line]))
                            else:
                                line = line + ' ' + str(n_time)
                    if 'reward_s' in line:
                        rewarded = True
                    elif rewarded:
                        if 'reward_e' in line or 'abort_s' in line:
                            continue
                        elif 'abort_e' in line:
                            line = 'reward_e ' + str(float(line.split(' ')[VALUE_IX]))
                    data = line.split(' ')
                    session_dict[data[EVENT_LABEL_IX]] = float(data[VALUE_IX])
            sessions[file_path] = session_dict
            session_file.close()

# create an empty array to store the final data
counter = 0
data_array = np.full((len(sessions) + int(np.ceil(len(sessions) * 0.25)), len(actions_dict) - 18), -1.0)
for f, events in sessions.items():
    for event, value in events.items():
        data_array[counter][actions_dict[event]] = value
        if event.endswith(ITBN.start_time_marker):
            data_array[counter][actions_dict[event.replace(ITBN.start_time_marker, '')]] = 1
    counter += 1

# Create DataFrame to hold data
data = pd.DataFrame(data_array, columns=['command_s', 'command_e', 'command',
                                         'prompt_s', 'prompt_e', 'prompt',
                                         'reward_s', 'reward_e', 'reward',
                                         'abort_s', 'abort_e', 'abort',
                                         'response_s', 'response_e', 'response'])

# Create empty model and add event nodes
model = ITBN()
model.add_nodes_from(data.columns.values)

# Learn temporal relations from data
model.learn_temporal_relationships(data)

# Delete columns with temporal information
data.fillna(0, inplace=True)
for col in list(data.columns.values):
    if col.endswith(ITBN.start_time_marker) or col.endswith(ITBN.end_time_marker):
        data.drop(col, axis=1, inplace=True)
    elif not col.startswith(ITBN.temporal_node_marker):
        data[col] = data[col].map({1: 'Y', -1: 'N'})

# Learn model structure from data and temporal relations
hc = HillClimbSearchITBN(data, scoring_method=BicScore(data))
model = hc.estimate(start=model, max_indegree=2)

# Learn model parameters
# model.fit(list(data[model.nodes()]))
for cpd in model.get_cpds():
    print(cpd)

# Draws and outputs resulting network
model.draw_to_file("../output/itbn.png")
os.system('gnome-open ../output/itbn.png')
nx.write_gpickle(model, "../output/itbn.nx")
