import torch
print(torch.__version__)           # 应输出 2.0.1
print(torch.cuda.is_available())   # 应输出 True
print(torch.version.cuda)          # 应输出 11.8