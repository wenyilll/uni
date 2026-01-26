import os
import sys
import json
import logging
import time
import yaml
from collections import deque, defaultdict
from types import SimpleNamespace
import numpy as np
import torch
import argparse
from src.envs import construct_envs
from src.agent.unigoal.agent import UniGoal_Agent
from src.map.bev_mapping import BEV_Map
from src.graph.graph import Graph
import gzip

parser = argparse.ArgumentParser()#创建一个参数解析器
parser.add_argument("--config-file", default="configs/config_habitat.yaml",
                    metavar="FILE", help="path to config file", type=str)
parser.add_argument("--goal_type", default="ins-image", type=str)
parser.add_argument("--episode_id", default=-1, type=int, help="episode id, 0~999")
parser.add_argument("--goal", default="", type=str)
parser.add_argument("--real_world", action="store_true")

print(parser)

def get_config():

    parser = argparse.ArgumentParser()#创建一个参数解析器
    parser.add_argument("--config-file", default="configs/config_habitat.yaml",
                        metavar="FILE", help="path to config file", type=str)
    parser.add_argument("--goal_type", default="ins-image", type=str)
    parser.add_argument("--episode_id", default=-1, type=int, help="episode id, 0~999")
    parser.add_argument("--goal", default="", type=str)
    parser.add_argument("--real_world", action="store_true")

    args = parser.parse_args()

    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)
    args = vars(args)
    args.update(config)
        
    args = SimpleNamespace(**args)

    args.is_debugging = sys.gettrace() is not None
    if args.is_debugging:
        args.experiment_id = "debug"
    
    args.log_dir = os.path.join(args.dump_location, args.experiment_id, 'log')
    args.visualization_dir = os.path.join(args.dump_location, args.experiment_id, 'visualization')

    args.map_size = args.map_size_cm // args.map_resolution
    args.global_width, args.global_height = args.map_size, args.map_size
    args.local_width = int(args.global_width / args.global_downscaling)
    args.local_height = int(args.global_height / args.global_downscaling)

    args.device = torch.device("cuda:1" if args.cuda else "cpu")

    args.num_scenes = args.num_processes
    args.num_episodes = int(args.num_eval_episodes)

    


def main():
    print(args)