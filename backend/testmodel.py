import os
from dotenv import load_dotenv
from modelscope.hub.snapshot_download import snapshot_download

load_dotenv()

MODEL_ID = "Qwen/Qwen3-Reranker-0.6B"
REVISION = "master"
print(f"🔖 MODEL_ID: {MODEL_ID}")
def main():
    save_dir = os.getenv("RERANKER_MODEL_PATH")

    if not save_dir:
        raise ValueError("❌ 请先设置环境变量 RERANKER_MODEL_PATH")

    os.makedirs(save_dir, exist_ok=True)

    print(f"📦 模型: {MODEL_ID}")
    print(f"📁 保存目录: {save_dir}")
    print(f"🔖 revision: {REVISION}")

    model_dir = snapshot_download(
        model_id=MODEL_ID,
        cache_dir=save_dir,
        revision=REVISION
    )

    print("✅ 下载完成")
    print(f"📂 模型路径: {model_dir}")

if __name__ == "__main__":
    main()