import os
import time
import torch
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify
import base64
import io
from facenet_pytorch import MTCNN, InceptionResnetV1
import glob
import json  # 用于日志保存

# ===================== 配置 =====================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
TEST_DIR = "students photos"
DISTANCE_THRESHOLD = 0.9
LOG_FILE = "recognition_logs.json"  # 历史记录存在这里

# ===================== MTCNN + Facenet =====================
mtcnn = MTCNN(keep_all=False, device=DEVICE)
resnet = InceptionResnetV1(pretrained='vggface2').eval().to(DEVICE)

# ===================== 全局特征库 =====================
global_db = {}
user_info = {}
app = Flask(__name__)


# ===================== 加载学号 =====================
def load_user_info():
    global user_info
    user_info = {}
    try:
        with open("user_info.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "," not in line:
                    continue
                name, sid = line.split(",", 1)
                user_info[name.strip()] = sid.strip()
    except Exception as e:
        print("读取user_info.txt失败:", e)
    print("已加载用户信息:", user_info)


# ===================== 日志保存功能 =====================
def save_log(entry):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except:
                logs = []

    logs.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# ===================== 工具函数 =====================
def detect_and_align(img_pil):
    aligned = mtcnn(img_pil)
    if aligned is None:
        return None
    return aligned


def extract_feature(img_tensor):
    with torch.no_grad():
        feat = resnet(img_tensor.unsqueeze(0).to(DEVICE))
        feat = feat / feat.norm()
    return feat.cpu().numpy().squeeze()


def build_db():
    global global_db
    cache_file = "feature_cache.npy"
    if os.path.exists(cache_file):
        global_db = np.load(cache_file, allow_pickle=True).item()
        print(f"已从缓存加载特征库，人数：{len(global_db)}")
        return

    global_db = {}
    person_dirs = [d for d in os.listdir(TEST_DIR) if os.path.isdir(os.path.join(TEST_DIR, d))]
    for pd in person_dirs:
        name = pd.replace("pins_", "")
        imgs = glob.glob(os.path.join(TEST_DIR, pd, "*.jpg")) + glob.glob(os.path.join(TEST_DIR, pd, "*.png"))
        img_tensors = []
        for p in imgs:
            img = Image.open(p).convert('RGB')
            aligned = detect_and_align(img)
            if aligned is not None:
                img_tensors.append(aligned)
        if img_tensors:
            with torch.no_grad():
                feats = resnet(torch.stack(img_tensors).to(DEVICE))
                feats = feats / feats.norm(dim=1, keepdim=True)
                global_db[name] = feats.cpu().numpy()
    np.save(cache_file, global_db)
    print(f"特征库构建完成，人数：{len(global_db)}")


def euclidean_dist(f1, f2):
    return float(np.linalg.norm(f1 - f2))


# ===================== 识别接口（自动记录日志） =====================
@app.route('/api/recognize', methods=['POST'])
def recognize():
    start_time = time.time()
    result = {
        "name": "",
        "student_id": "",
        "distance": 0.0,
        "allow_open": False,
        "time_cost": 0.0,
        "message": "处理失败"
    }
    try:
        data = request.get_json()
        if not data or 'image_base64' not in data:
            result["message"] = "缺少 image_base64"
            return jsonify(result)

        b64 = data['image_base64']
        if ',' in b64:
            b64 = b64.split(',')[1]
        img_bytes = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        aligned = detect_and_align(img)
        if aligned is None:
            result["message"] = "未检测到人脸"
            return jsonify(result)

        feat = extract_feature(aligned)

        min_dist = float('inf')
        best_name = ""
        for name, feats in global_db.items():
            mean_feat = np.mean(feats, axis=0)
            mean_feat = mean_feat / np.linalg.norm(mean_feat)
            d = euclidean_dist(feat, mean_feat)
            if d < min_dist:
                min_dist = d
                best_name = name

        allow = min_dist <= DISTANCE_THRESHOLD
        student_id = user_info.get(best_name, "未录入")
        time_cost = round(time.time() - start_time, 4)
        msg = f"识别成功：{best_name}" if allow else f"陌生人，距离={min_dist:.2f}"

        # ===================== 自动保存日志 =====================
        log_entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "name": best_name,
            "student_id": student_id,
            "distance": round(min_dist, 4),
            "allow_open": allow,
            "time_cost": time_cost,
            "message": msg
        }
        save_log(log_entry)

        return jsonify({
            "name": best_name,
            "student_id": student_id,
            "distance": round(min_dist, 4),
            "allow_open": allow,
            "time_cost": time_cost,
            "message": msg
        })

    except Exception as e:
        result["message"] = f"错误：{str(e)}"
        return jsonify(result)


# ===================== 【新】历史记录接口 =====================
@app.route('/api/history', methods=['GET'])
def get_history():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            try:
                logs = json.load(f)
            except:
                logs = []
    # 倒序：最新的在最上面
    return jsonify(logs[::-1])


# ===================== 启动 =====================
if __name__ == '__main__':
    load_user_info()
    build_db()
    print("服务已启动：")
    print(" - 识别接口：http://0.0.0.0:5000/api/recognize")
    print(" - 历史记录：http://0.0.0.0:5000/api/history")
    app.run(host='0.0.0.0', port=5000, debug=True)