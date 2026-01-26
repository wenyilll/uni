import habitat
import cv2 # 我们需要OpenCV来显示图像和接收键盘输入
import argparse

def main():
    # --- 设置部分 ---
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfg", type=str, required=True, help="Path to the config file")
    args = parser.parse_args()
    config = habitat.get_config(args.cfg)

    # 用我们精简的配置创建环境，这里不会加载任何任务
    env = habitat.Env(config=config)

    print("="*50)
    print("环境加载成功！现在您可以自由探索场景。")
    print("控制按键:")
    print(" W - 前进")
    print(" A - 左转")
    print(" D - 右转")
    print(" F - 停止 (在任务模式下有用)")
    print(" Q - 退出")
    print("="*50)

    # --- 交互循环 ---
    # 重置环境，获取初始观测值
    observations = env.reset()

    while True:
        # 从环境中获取RGB图像并在窗口中显示
        rgb_image = observations["rgb"]
        # Habitat输出的是RGB，OpenCV需要BGR，所以转换一下颜色通道
        bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
        cv2.imshow("Habitat Viewer", bgr_image)

        # 等待键盘输入
        key = cv2.waitKey(0) # 等待直到有按键

        action = None
        if key == ord('w') or key == ord('W'):
            action = env.task.actions['move_forward']
        elif key == ord('a') or key == ord('A'):
            action = env.task.actions['turn_left']
        elif key == ord('d') or key == ord('D'):
            action = env.task.actions['turn_right']
        elif key == ord('f') or key == ord('F'):
            action = env.task.actions['stop']
        elif key == ord('q') or key == ord('Q'):
            print("正在退出...")
            break # 退出循环

        # 如果按了有效按键，就执行动作
        if action is not None:
            observations = env.step(action)

    # 清理工作
    env.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()