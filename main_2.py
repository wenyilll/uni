# 导入os模块，用于与操作系统进行交互，如创建文件夹
import os
# 导入sys模块，用于访问与Python解释器相关的变量和函数，如此处用来检查是否处于调试模式
import sys
# 导入json模块，用于处理JSON数据格式，如此处用于保存最终的评估结果
import json
# 导入logging模块，用于记录程序运行时的信息，方便调试和追踪
import logging
# 导入time模块，提供时间相关的功能
import time
# 导入yaml模块，用于读取和解析YAML格式的配置文件
import yaml
# 从collections模块导入deque，它是一个双端队列，用于高效地在两端添加和删除元素，此处用于存储评估指标
from collections import deque, defaultdict
# 从types模块导入SimpleNamespace，它提供了一种创建简单对象的方式，属性可以通过点操作符访问，用于存储配置参数
from types import SimpleNamespace
# 导入numpy库，并使用别名np，它是Python中科学计算的核心库，用于处理大型多维数组和矩阵
import numpy as np
# 导入torch库，它是PyTorch深度学习框架，用于张量计算和神经网络
import torch
# 导入argparse模块，用于从命令行解析参数
import argparse
# 从本地的src.envs模块导入construct_envs函数，该函数负责构建模拟环境
from src.envs import construct_envs
# 从本地的src.agent.unigoal.agent模块导入UniGoal_Agent类，这是导航智能体的实现
from src.agent.unigoal.agent import UniGoal_Agent
# 从本地的src.map.bev_mapping模块导入BEV_Map类，用于创建和管理鸟瞰图（BEV）
from src.map.bev_mapping import BEV_Map
# 从本地的src.graph.graph模块导入Graph类，用于构建环境的图表示，以支持探索和规划
from src.graph.graph import Graph
# 导入gzip模块，用于读写gzip压缩文件，如此处用于加载文本目标数据集
import gzip

def get_config():
    """
    此函数用于解析命令行参数和配置文件，并将它们合并为一个配置对象。
    """
    # 创建一个ArgumentParser对象，用于处理命令行参数
    parser = argparse.ArgumentParser()
    # 添加命令行参数定义  解析命令行
    # --config-file: 指定配置文件的路径
    parser.add_argument("--config-file", default="configs/config_habitat.yaml",
                        metavar="FILE", help="path to config file", type=str)
    # --goal_type: 指定目标的类型，如 'ins-image' (实例图像) 或 'text' (文本)
    parser.add_argument("--goal_type", default="ins-image", type=str)
    # --episode_id: 指定要运行的单个剧集的ID，-1表示按顺序运行所有剧集
    parser.add_argument("--episode_id", default=-1, type=int, help="episode id, 0~999")
    # --goal: 字符串形式的特定目标
    parser.add_argument("--goal", default="", type=str)
    # --real_world: 一个开关参数，如果使用则表示在真实世界环境中运行
    parser.add_argument("--real_world", action="store_true")

    # 解析命令行传入的参数 转换成 argparse.Namespace 对象 命名空间类别的对象
    # argparse.Namespace 对象是一个简单的对象，它的属性可以通过点操作符访问，
    # 例如 args.config_file, args.goal_type 等等。
  
    args = parser.parse_args()

    # 打开配置文件并加载内容
    with open(args.config_file, 'r') as file:
        config = yaml.safe_load(file)
    # 将解析出的命令行参数对象转换为字典
    args = vars(args)
    # 将从配置文件加载的参数更新到args字典中，如果存在同名参数，则命令行参数会保留（因为是后更新）
    args.update(config)
        
    # 将最终的参数字典转换为SimpleNamespace对象，方便通过点操作符访问 (e.g., args.map_size)
    args = SimpleNamespace(**args)

    # 检查是否处于调试模式（例如在VSCode或PyCharm中打断点运行）
    args.is_debugging = sys.gettrace() is not None
    if args.is_debugging:
        # 如果是调试模式，将实验ID设置为'debug'，避免覆盖正常的实验结果
        args.experiment_id = "debug"
    
    # 根据配置中的dump_location和experiment_id构建日志和可视化结果的存储路径
    args.log_dir = os.path.join(args.dump_location, args.experiment_id, 'log')
    args.visualization_dir = os.path.join(args.dump_location, args.experiment_id, 'visualization')

    # 根据物理尺寸(cm)和分辨率计算地图的网格尺寸。  map_resolution (例如 5 厘米/格)。这是栅格地图的标志性特征。它定义了现实世界和数字地图之间的“换算比例”
    args.map_size = args.map_size_cm // args.map_resolution
    # 设置全局地图的宽度和高度
    args.global_width, args.global_height = args.map_size, args.map_size
    # 根据全局地图尺寸和下采样因子计算局部地图的尺寸
    args.local_width = int(args.global_width / args.global_downscaling)
    args.local_height = int(args.global_height / args.global_downscaling)

    # 设置PyTorch使用的计算设备，如果配置中args.cuda为True并且有可用的GPU，则使用cuda:0，否则使用CPU
    args.device = torch.device("cuda:0" if args.cuda else "cpu")

    # 设置同时运行的场景数量
    args.num_scenes = args.num_processes
    # 设置要评估的总剧集数
    args.num_episodes = int(args.num_eval_episodes)

    # 返回最终构建好的配置对象
    return args


def main():
    """
    主函数，包含了整个评估流程的逻辑。
    """
    # 调用get_config()获取所有配置参数
    args = get_config()

    #print(f"配置参数:{args},tyepe:{type(args)}")

        # 创建日志和可视化结果的目录，exist_ok=True表示如果目录已存在则不报错
    os.makedirs(args.log_dir, exist_ok=True)
    os.makedirs(args.visualization_dir, exist_ok=True)

    # 配置logging模块，将日志信息写入到指定的文件中
    logging.basicConfig(
        filename=os.path.join(args.log_dir, 'eval.log'),
        level=logging.INFO)
    # 在日志中记录本次运行的配置参数
    logging.info(args)

    # 初始化评估指标的ID计数器
    eval_metrics_id = 0

    # 初始化两个双端队列，用于存储每个剧集的成功率(success)和SPL(success weighted by path length)
    # maxlen参数保证了队列只保留最近N个剧集的结果，N由args.num_episodes定义
    episode_success = deque(maxlen=args.num_episodes)
    episode_spl = deque(maxlen=args.num_episodes)

    # 初始化两个布尔标志，用于控制主循环
    finished = False    # 当所有剧集评估完成时，该标志为True
    wait_env = False    # 在一个剧集结束后，等待环境重置时，该标志为True

    # 如果目标类型是文本，则从gzip压缩文件中加载文本目标数据集
    if args.goal_type == 'text':
        with gzip.open(args.text_goal_dataset, 'rt') as f:
            text_goal_dataset = json.load(f)

    # 实例化各个核心组件
    BEV_map = BEV_Map(args)         # 鸟瞰图地图构建器
    graph = Graph(args)             # 场景图和探索决策模块
    envs = construct_envs(args)     # 模拟环境
    agent = UniGoal_Agent(args, envs) # 导航智能体

    # 初始化地图和智能体在地图上的姿态
    BEV_map.init_map_and_pose()
    # 重置环境和智能体，获取初始的观测值(obs)、RGBD图像(rgbd)和环境信息(infos)
    obs, rgbd, infos = agent.reset()

    # 使用初始的RGBD图像和姿态信息更新BEV地图
    BEV_map.mapping(rgbd, infos)

    # 初始化全局目标点，初始时通常设在局部地图的中心
    global_goals = [args.local_width // 2, args.local_height // 2]

    # 创建一个与局部地图同样大小的零矩阵，用于表示目标位置
    goal_maps = np.zeros((args.local_width, args.local_height))

    # 在目标地图上，将全局目标点的位置标记为1
    goal_maps[global_goals[0], global_goals[1]] = 1

    # 构建一个字典，作为导航智能体策略网络的输入
    agent_input = {}
    # 'map_pred': 预测的障碍物地图 (local_map的第0个通道)
    agent_input['map_pred'] = BEV_map.local_map[0, 0, :, :].cpu().numpy()
    # 'exp_pred': 预测的可探索区域地图 (local_map的第1个通道)
    agent_input['exp_pred'] = BEV_map.local_map[0, 1, :, :].cpu().numpy()
    # 'pose_pred': 规划器使用的智能体姿态输入
    agent_input['pose_pred'] = BEV_map.planner_pose_inputs[0]
    # 'goal': 全局目标在局部地图上的位置
    agent_input['goal'] = goal_maps
    # 'exp_goal': 探索目标地图，此处与goal_maps相同
    agent_input['exp_goal'] = goal_maps * 1
    # 'new_goal': 是否是一个新的全局目标，初始时为1(True)
    agent_input['new_goal'] = 1
    # 'found_goal': 是否找到了目标，初始为0(False)
    agent_input['found_goal'] = 0
    # 'wait': 是否需要等待，由wait_env或finished标志决定
    agent_input['wait'] = wait_env or finished
    # 'sem_map': 语义地图 (local_map的第4到10个通道)
    agent_input['sem_map'] = BEV_map.local_map[0, 4:11, :, :].cpu().numpy()
    
    # 如果开启了可视化
    if args.visualize:
        # 在local_map的第10通道上做一些标记，用于可视化
        BEV_map.local_map[0, 10, :, :] = 1e-5
        # 'sem_map_pred': 预测的语义地图，通过argmax在通道维度上取最大值得到每个像素的类别
        agent_input['sem_map_pred'] = BEV_map.local_map[0, 4:11, :, :].argmax(0).cpu().numpy()

    # 智能体根据第一次的输入在环境中执行一步动作
    obs, rgbd, done, infos = agent.step(agent_input)

    # 重置场景图模块，并设置当前剧集的目标
    graph.reset()
    graph.set_obj_goal(infos['goal_name']) # 设置物体名称目标
    if args.goal_type == 'ins-image':
        graph.set_image_goal(infos['instance_imagegoal']) # 如果是图像目标，设置图像
    elif args.goal_type == 'text':
        graph.set_text_goal(infos['text_goal']) # 如果是文本目标，设置文本

    # 初始化总步数计数器
    step = 0

    # 开始主循环，直到所有评估剧集完成
    while True:
        # 如果finished标志为True，则跳出循环
        if finished == True:
            break

        # 计算当前的全局规划步数和局部规划步数
        global_step = (step // args.num_local_steps) % args.num_global_steps
        local_step = step % args.num_local_steps

        # 如果上一步导致剧集结束 (done=True)
        if done:
            # 从环境信息中获取SPL和Success指标
            spl = infos['spl']
            success = infos['success']
            success = success if success is not None else 0.0 # 保证success是浮点数
            # 增加评估ID计数
            eval_metrics_id += 1
            # 将当前剧集的SR和SPL存入队列
            episode_success.append(success)
            episode_spl.append(spl)
            # 如果队列已满（即已完成所有评估剧集），设置finished标志
            if len(episode_success) == args.num_episodes:
                finished = True
            # 如果开启了可视化，保存上一剧集的视频
            if args.visualize:
                video_path = os.path.join(args.visualization_dir, 'videos', 'eps_{:0>6}.mp4'.format(infos['episode_no']))
                agent.save_visualization(video_path)
            # 设置wait_env标志，表示需要等待环境重置
            wait_env = True
            # 更新地图的内在奖励
            BEV_map.update_intrinsic_rew()
            # 为新剧集初始化地图和姿态
            BEV_map.init_map_and_pose_for_env()

            # 重置场景图模块，并为新剧集设置目标
            graph.reset()
            graph.set_obj_goal(infos['goal_name'])
            if args.goal_type == 'ins-image':
                graph.set_image_goal(infos['instance_imagegoal'])
            elif args.goal_type == 'text':
                graph.set_text_goal(infos['text_goal'])

        # 使用上一步的观测结果更新BEV地图
        BEV_map.mapping(rgbd, infos)

        # 计算总的导航步数
        navigate_steps = global_step * args.num_local_steps + local_step
        # 将导航步数设置到场景图模块中
        graph.set_navigate_steps(navigate_steps)
        # 如果不需要等待，并且是偶数步，则更新场景图
        if not agent_input['wait'] and navigate_steps % 2 == 0:
            graph.set_observations(obs) # 设置观测值
            graph.update_scenegraph()   # 更新场景图

        # ------------------------------------------------------------------
        # 全局路径规划逻辑 (Global Path-Planning)
        # ------------------------------------------------------------------
        # 当一个局部规划周期结束，或者智能体已经很接近当前的全局目标时
        if local_step == args.num_local_steps - 1 or np.linalg.norm(np.array([BEV_map.local_row, BEV_map.local_col]) - np.array(global_goals)) < 10:
            # 如果是剧集刚结束的状态，则清除等待标志
            if wait_env == True:
                wait_env = False
            else:
                # 否则，更新地图的内在奖励
                BEV_map.update_intrinsic_rew()

            # 移动局部地图窗口以将智能体置于中心
            BEV_map.move_local_map()

            # 将完整的全局地图和姿态信息传递给场景图模块
            graph.set_full_map(BEV_map.full_map)
            graph.set_full_pose(BEV_map.full_pose)
            # 调用场景图模块的探索方法，来决定下一个全局目标点 (frontier)
            goal = graph.explore()
            
            # --- 将全局坐标系下的目标点和边界点转换到局部地图坐标系 ---
            if hasattr(graph, 'frontier_locations_16'):
                graph.frontier_locations_16[:, 0] = graph.frontier_locations_16[:, 0] - BEV_map.local_map_boundary[0, 0]
                graph.frontier_locations_16[:, 1] = graph.frontier_locations_16[:, 1] - BEV_map.local_map_boundary[0, 2]
            
            if isinstance(goal, list) or isinstance(goal, np.ndarray):
                goal = list(goal)
                goal[0] = goal[0] - BEV_map.local_map_boundary[0, 0]
                goal[1] = goal[1] - BEV_map.local_map_boundary[0, 2]
                # 检查转换后的目标点是否在局部地图范围内
                if 0 <= goal[0] < args.local_width and 0 <= goal[1] < args.local_height:
                    # 如果在范围内，则更新全局目标
                    global_goals = goal


        # ------------------------------------------------------------------
        # 为下一步准备智能体输入 (Prepare Agent Input for the Next Step)
        # ------------------------------------------------------------------
        found_goal = False # 假设还未找到目标
        # 重新创建目标地图
        goal_maps = np.zeros((args.local_width, args.local_height))

        # 在目标地图上标记新的全局目标点
        goal_maps[global_goals[0], global_goals[1]] = 1

        # 复制一份作为探索目标地图
        exp_goal_maps = goal_maps.copy()

        # 构建下一步的智能体输入字典
        agent_input = {}
        agent_input['map_pred'] = BEV_map.local_map[0, 0, :, :].cpu().numpy()
        agent_input['exp_pred'] = BEV_map.local_map[0, 1, :, :].cpu().numpy()
        agent_input['pose_pred'] = BEV_map.planner_pose_inputs[0]
        agent_input['goal'] = goal_maps
        agent_input['exp_goal'] = exp_goal_maps
        # 'new_goal'标志：当一个局部规划周期结束时为True
        agent_input['new_goal'] = local_step == args.num_local_steps - 1
        agent_input['found_goal'] = found_goal
        agent_input['wait'] = wait_env or finished
        agent_input['sem_map'] = BEV_map.local_map[0, 4:11, :, :].cpu().numpy()

        # 如果开启了可视化，同样准备可视化的语义地图
        if args.visualize:
            BEV_map.local_map[0, 10, :, :] = 1e-5
            agent_input['sem_map_pred'] = BEV_map.local_map[0, 4:11, :, :].argmax(0).cpu().numpy()

        # 智能体执行一步，并获取新的观测、RGBD、完成标志和信息
        obs, rgbd, done, infos = agent.step(agent_input)

        # ------------------------------------------------------------------
        # 日志记录 (Logging)
        # ------------------------------------------------------------------
        # 每隔一定步数，打印一次日志
        if step % args.log_interval == 0:
            # 构建日志字符串
            log = " ".join([
                "num timesteps {},".format(step),
                "episode_id {}".format(infos['episode_no']),
            ])

            # 从队列中收集所有已完成剧集的SR和SPL
            total_success = []
            total_spl = []
            for acc in episode_success:
                total_success.append(acc)
            for spl in episode_spl:
                total_spl.append(spl)

            # 如果有已完成的剧集，则计算并记录平均SR和SPL
            if len(total_spl) > 0:
                log += " Average SR/SPL:"
                log += " {:.5f}/{:.5f},".format(
                    np.mean(total_success),
                    np.mean(total_spl))

            # 打印日志到控制台并写入日志文件
            print(log)
            logging.info(log)
        # ------------------------------------------------------------------
        # 步数加一
        step += 1

    # ----- 循环结束后，计算并保存最终结果 -----

    # 从队列中收集所有剧集的SR和SPL
    total_success = []
    total_spl = []
    for acc in episode_success:
        total_success.append(acc)
    for spl in episode_spl:
        total_spl.append(spl)

    # 计算最终的平均SR和SPL
    if len(total_spl) > 0:
        log = "Average SR/SPL:"
        log += " {:.5f}/{:.5f},".format(
            np.mean(total_success),
            np.mean(total_spl))

    # 打印最终结果到控制台并写入日志文件
    print(log)
    logging.info(log)
        
    # 将所有剧集的SR和SPL结果存成一个字典
    total = {'succ': total_success, 'spl': total_spl}

    # 将最终结果字典以JSON格式写入文件
    with open('{}/total.json'.format(
            args.log_dir), 'w') as f:
        json.dump(total, f)

# 这是一个Python的标准写法。
# 只有当这个脚本是作为主程序直接运行时，`__name__` 的值才是 "__main__"。
# 如果这个脚本被其他脚本作为模块导入，则 `__name__` 的值是模块名，此时下面的代码不会执行。
if __name__ == "__main__":
    main()
