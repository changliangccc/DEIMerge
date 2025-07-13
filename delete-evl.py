import json
import argparse
import os


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="JSON数据清洗脚本")
    parser.add_argument("--input")
    parser.add_argument("--output")
    return parser.parse_args()

def transform_structure(data):
    """执行数据结构转换和过滤"""
    processed = []

    for item in data:
        # 删除顶层字段
        item.pop("best_choice", None)
        item.pop("best_choice_resolved", None)
        item.pop("top 1 pass", None)
        item.pop("top 3 pass", None)
        item.pop("top 5 pass", None)

        # 处理评估记录
        valid = True
        for model_name, evaluation in item.get("evaluations", {}).items():
            # 删除不需要的字段
            evaluation.pop("score", None)
            evaluation.pop("resolved", None)

            # 过滤avg_score为-1的记录
            if evaluation.get("avg_score", 0) < 3:
                valid = False
                break
            evaluation.pop("avg_score", None)
            
            # 处理说明字段
            explanations = evaluation.get("explanation", [])
            for exp in explanations:
                exp.pop("msg", None)  # 删除msg字段
                exp.pop("fixes_issue_exp", None)
        if valid:
            processed.append(item)

    return processed


def main():
    args = parse_arguments()

    try:
        # 读取输入文件
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 验证数据结构
        if not isinstance(data, list):
            raise ValueError("JSON根元素必须是数组")

        # 执行转换和过滤
        processed_data = transform_structure(data)

        # 保存结果
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)

        print(f"处理完成！原始记录数：{len(data)}，保留记录数：{len(processed_data)}")
        print(f"输出文件已保存至：{os.path.abspath(args.output)}")

    except Exception as e:
        print(f"处理失败：{str(e)}")


if __name__ == "__main__":
    main()