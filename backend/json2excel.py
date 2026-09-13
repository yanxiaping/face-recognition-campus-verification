import json
import pandas as pd
# 日志文件路径
LOG_FILE = "recognition_logs.json"

# 读取 JSON
try:
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
except:
    logs = []

logs = logs[::-1]

# 导出 Excel
df = pd.DataFrame(logs)
df.to_excel("识别记录.xlsx", index=False)

print("生成文件：识别记录.xlsx")
input("按回车键退出...")