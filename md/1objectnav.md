# UniGoal 接入 ObjectNav 改动记录

> 日期：2026-06-15  
> 目标：在现有 UniGoal 项目上支持 HM3D **ObjectNav-v1** 任务（6 类物体导航）  
> 运行命令：`--goal_type object --config-file configs/config_habitat_objectnav.yaml`

---

## 1. 背景：为什么不能只拷数据？

UniGoal 原版只支持：

| 任务 | goal_type | 数据集 |
|------|-----------|--------|
| Instance-ImageNav | `ins-image` | `data/datasets/instance_imagenav/` |
| TextNav | `text` | `data/datasets/textnav/` |

ObjectNav 需要额外三处适配：

1. **Habitat 任务类型**不同（`ObjectNav-v1` vs `InstanceImageNav-v1`）
2. **场景路径前缀**不同（`hm3d/val/...` vs `hm3d_v0.2/val/...`）
3. **代码逻辑**需新增 `goal_type == 'object'` 分支（用类别名如 `bed` 建 goal graph）

---

## 2. 数据准备（本地，不进 Git）

### 2.1 拷贝 ObjectNav 任务集

来源：VLFM 项目中的官方 HM3D ObjectNav v1 数据。

```bash
mkdir -p ~/zz/Unigoal/UniGoal/data/datasets
cp -a /mnt/disk1/zz/Object_goal/VLFM/vlfm/data/datasets/objectnav \
      ~/zz/Unigoal/UniGoal/data/datasets/
```

拷贝后目录结构：

```
data/datasets/objectnav/hm3d/v1/
├── train/
│   ├── train.json.gz
│   └── content/*.json.gz
└── val/
    ├── val.json.gz
    └── content/*.json.gz    # val 共 2000 条 episode，20 个场景
```

### 2.2 场景软链（关键）

InstanceImageNav 的 episode 写 `hm3d_v0.2/val/...`，ObjectNav 写 `hm3d/val/...`。  
底层是**同一套 HM3D v0.2 val 场景**，只需软链，**不必再拷场景**。

```bash
cd ~/zz/Unigoal/UniGoal/data/scene_datasets
ln -sfn hm3d_v0.2 hm3d
```

验证：

```bash
ls -la data/scene_datasets/hm3d   # 应指向 hm3d_v0.2
```

> 注意：`data/` 已在 `.gitignore` 中，任务集和软链**不会**被 push 到 GitHub。换机器需按本节重新操作。

### 2.3 ObjectNav 支持的 6 个类别

`chair`, `bed`, `plant`, `toilet`, `tv_monitor`, `sofa`

与 `configs/categories.py` 中 `name2index` 一致。

---

## 3. 新增配置文件

### 3.1 `configs/tasks/objectnav.yaml`

基于 `instance_imagenav.yaml` 修改：

- 任务：`/habitat/task: objectnav`（ObjectNav-v1）
- 数据集：`/habitat/dataset/objectnav: hm3d`
- 传感器：保留 `rgbds_agent`（rgb + depth + semantic，与 ins-image 一致）
- split：`val`

### 3.2 `configs/config_habitat_objectnav.yaml`

基于 `config_habitat.yaml` 修改：

| 字段 | 值 | 说明 |
|------|-----|------|
| `task_config` | `tasks/objectnav.yaml` | ObjectNav 任务 |
| `experiment_id` | `objectnav_0` | 输出目录名 |
| `split` | `val` | 使用 val 划分 |
| `num_eval_episodes` | `1`（可调） | 评测 episode 数 |
| `visualize` | `0`（可调为 `1`） | 是否保存 mp4 |
| `version` | `v1` | 对应 objectnav hm3d v1 |

---

## 4. 代码改动（按文件）

### 4.1 `main.py`

在两处设置 goal 的位置（首次与 episode 结束后）增加 `object` 分支：

```python
elif args.goal_type == 'object':
    graph.set_text_goal(infos['goal_name'])
```

逻辑：ObjectNav 的目标就是物体类别名（如 `bed`），直接作为 text goal 交给 LLM 做 goal graph 分解，**不需要** VLM 从图像转文本。

### 4.2 `src/envs/instanceimagegoal_env.py`

**问题**：ObjectNav episode 没有 `goal_object_id` 字段（InstanceImageNav 才有）。

**改法**：在 `update_after_reset()` 中兼容两种 episode：

```python
if hasattr(episode, 'goal_object_id') and episode.goal_object_id is not None:
    self.goal_object_id = int(episode.goal_object_id)
elif getattr(episode, 'goals', None):
    self.goal_object_id = int(episode.goals[0].object_id)
else:
    self.goal_object_id = None
```

在 `reset()` 中增加 object 分支，设置 `text_goal`：

```python
if self.args.goal_type == 'object':
    if self.args.goal:
        self.info['text_goal'] = self.args.goal
    else:
        self.info['text_goal'] = self.goal_name
    self.text_goal = self.info['text_goal']
```

### 4.3 `src/agent/unigoal/agent.py`

| 位置 | 改动 |
|------|------|
| `reset()` | `goal_type == 'object'` 时 `self.text_goal = self.envs.text_goal` |
| `get_goal_cat_id()` | object 模式直接 `return self.envs.gt_goal_idx`（不经过 LLM 猜类别） |
| `instance_discriminator()` | 将原 `'text'` 条件扩展为 `in ('text', 'object')`（距离阈值、匹配逻辑与 text 相同） |
| `visualize()` | object 模式在左上角显示类别名文字 |

---

## 5. 依赖与环境

与 ins-image 相同：

```bash
conda activate unigoal
ollama serve                    # 另开终端，若未作为服务运行
ollama pull llama3.2-vision     # 首次需要
```

`configs/config_habitat_objectnav.yaml` 中 LLM/VLM 默认：

```yaml
llm_model: "llama3.2-vision"
base_url: "http://localhost:11434/v1/"
```

---

## 6. 运行方式

### 6.1 单个 episode 冒烟

```bash
cd ~/zz/Unigoal/UniGoal
conda activate unigoal

python main.py --goal_type object \
  --config-file configs/config_habitat_objectnav.yaml \
  --episode_id 0
```

### 6.2 多 episode 评测

修改 `configs/config_habitat_objectnav.yaml` 中 `num_eval_episodes`（如 `100`），然后：

```bash
python main.py --goal_type object \
  --config-file configs/config_habitat_objectnav.yaml
```

### 6.3 开可视化

`config_habitat_objectnav.yaml` 中设 `visualize: 1`，视频输出：

```
outputs/experiments/objectnav_0/visualization/videos/eps_000000.mp4
```

日志与指标：

```
outputs/experiments/objectnav_0/log/eval.log
outputs/experiments/objectnav_0/log/total.json
```

---

## 7. 本机验证结果（2026-06-15）

| 项 | 结果 |
|----|------|
| 数据集加载 | ObjectNav-v1，2000 episodes |
| 场景 | `data/scene_datasets/hm3d/val/00877-4ok3usBNeis/...` 正常 |
| Episode 0 | 目标 `bed`，`cat_id: 3` |
| 导航 | 跑通约 40+ 步，无崩溃 |
| SR/SPL | 0.0 / 0.0（单 episode 短跑正常，不代表方法失败） |

---

## 8. 与 ins-image 的差异小结

| 项目 | ins-image | object |
|------|-----------|--------|
| 任务集 | instance_imagenav hm3d v3 | objectnav hm3d v1 |
| 任务配置 | `tasks/instance_imagenav.yaml` | `tasks/objectnav.yaml` |
| 目标来源 | 图像 → VLM → 文本 | 直接用 `object_category` 字符串 |
| 场景路径 | `hm3d_v0.2/val/...` | `hm3d/val/...`（软链解决） |
| 命令 | `--goal_type ins-image` | `--goal_type object --config-file configs/config_habitat_objectnav.yaml` |

---

## 9. 新机器快速复现清单

1. `conda activate unigoal`
2. 拷贝 objectnav 任务集到 `data/datasets/objectnav/`
3. 创建软链 `data/scene_datasets/hm3d` → `hm3d_v0.2`
4. 确认 HM3D val 场景在 `data/scene_datasets/hm3d_v0.2/val/`
5. 启动 Ollama + `llama3.2-vision`
6. 运行第 6 节命令
