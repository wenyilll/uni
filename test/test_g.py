import habitat_sim
import cv2
import numpy as np
import os

# --- 1. 设置场景路径 (根据你的日志调整) ---
# 这里的路径是你日志里成功加载的那个场景
scene_path = "/home/ps/zz/Unigoal/UniGoal/data/scene_datasets/hm3d_v0.2/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb"

# 检查文件是否存在
if not os.path.exists(scene_path):
    # 尝试使用绝对路径作为备选
    scene_path = "/home/ps/zz/Unigoal/UniGoal/data/scene_datasets/hm3d_v0.2/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb"
    if not os.path.exists(scene_path):
        print(f"错误：找不到文件 {scene_path}")
        exit()

print(f"正在加载场景: {scene_path} ...")

# --- 2. 配置仿真器 ---
sim_cfg = habitat_sim.SimulatorConfiguration()
sim_cfg.scene_id = scene_path
sim_cfg.enable_physics = False  # 漫游模式不需要物理掉落，更流畅

# 配置 RGB 摄像头 (用于显示)
agent_cfg = habitat_sim.agent.AgentConfiguration()
rgb_sensor_spec = habitat_sim.CameraSensorSpec()
rgb_sensor_spec.uuid = "color_sensor"
rgb_sensor_spec.sensor_type = habitat_sim.SensorType.COLOR
rgb_sensor_spec.resolution = [600, 800] # 画面大小 (高, 宽)
rgb_sensor_spec.position = [0.0, 1.5, 0.0] # 摄像头高度 1.5米
agent_cfg.sensor_specifications = [rgb_sensor_spec]

cfg = habitat_sim.Configuration(sim_cfg, [agent_cfg])
try:
    sim = habitat_sim.Simulator(cfg)
except Exception as e:
    print(f"仿真器初始化失败: {e}")
    exit()

# 初始化 Agent 位置
agent = sim.initialize_agent(0)

# --- 3. 定义按键控制 ---
# OpenCV 的 waitKey 返回的是 ASCII 码
# 速度系数 (每次按键移动多少米)
move_step = 0.25 
turn_angle = 10 # 度

print("\n" + "="*50)
print("  交互模式已启动！(按 'Q' 退出)")
print("  操作说明:")
print("  [W] 前进   [S] 后退")
print("  [A] 左转   [D] 右转")
print("  [P] >>> 打印当前坐标 (Print)")
print("="*50 + "\n")

while True:
    # 1. 获取画面
    observations = sim.get_sensor_observations()
    rgb = observations["color_sensor"]
    # Habitat是RGBA格式，OpenCV需要BGR
    # 注意：如果画面颜色看起来是反的(蓝变红)，说明颜色通道转错了，通常如下转换即可：
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGBA2BGR)

    # 2. 显示画面
    cv2.imshow("Habitat Explorer (Press P to save coords)", bgr)

    # 3. 监听按键 (等待 10ms)
    key = cv2.waitKey(10) & 0xFF

    # 4. 处理按键
    if key == ord('q') or key == 27: # q 或 ESC 退出
        break
    
    elif key == ord('w'):
        sim.step("move_forward")
    elif key == ord('s'):
        # Habitat 默认动作空间可能不包含 move_backward，如果没有会报错或不动
        # 如果需要后退，通常只能转头再走，或者自定义 ActionSpace，这里先尝试默认
        try:
            sim.step("move_backward")
        except:
            print("当前配置不支持直接后退，请转身")
    elif key == ord('a'):
        sim.step("turn_left")
    elif key == ord('d'):
        sim.step("turn_right")
    
    elif key == ord('p'):
        # --- 核心功能：获取坐标 ---
        state = agent.get_state()
        pos = state.position
        rot = state.rotation
        # 格式化打印，方便你直接复制
        print("-" * 30)
        print(f"捕获点!")
        print(f"Position (XYZ): [{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]")
        print(f"Rotation (Quat): {rot}")
        print(f"JSON格式: \"position\": [{pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f}]")
        print("-" * 30)

# 退出清理
sim.close()
cv2.destroyAllWindows()