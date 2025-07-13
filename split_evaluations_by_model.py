import os
import json
import argparse
import re


def sanitize_filename(name: str) -> str:
    """将模型名称转换为文件名友好的格式"""
    # 替换不安全字符为下划线
    return re.sub(r'[^\w\-\.]', '_', name)


def split_evaluations_by_model(input_path: str, output_dir: str):
    # 读取输入 JSON
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    grouped = {}

    for instance in data:
        instance_id = instance.get("instance_id", "")
        evaluations = instance.get("evaluations", {})

        for eval_name, eval_record in evaluations.items():
            patch_info = eval_record.get("patch", {})
            model = patch_info.get("model_name_or_path", "unknown_model")
            entry = {
                "instance_id": instance_id,
                "eval_name": eval_name,
                "patch": patch_info,
                "explanation": eval_record.get("explanation", [])
            }
            grouped.setdefault(model, []).append(entry)

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 写入每个模型对应的 JSON 文件
    for model_name, records in grouped.items():
        filename = sanitize_filename(model_name) + ".json"
        out_path = os.path.join(output_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as wf:
            json.dump(records, wf, ensure_ascii=False, indent=2)
        print(f"Wrote {len(records)} records to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="按模型名称拆分 evaluations 并保存为多个 JSON 文件"
    )
    parser.add_argument(
        "input_json",
        help="输入 JSON 文件路径（应为包含 evaluations 的列表）"
    )
    parser.add_argument(
        "output_dir",
        help="输出目录，按模型名称生成分别的 JSON 文件"
    )
    args = parser.parse_args()

    split_evaluations_by_model(args.input_json, args.output_dir)