import json
import argparse
import os


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="JSON数据清洗脚本")
    parser.add_argument("--input")
    parser.add_argument("--output")
    return parser.parse_args()


def validate_file(path):
    """验证输入文件是否存在"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"输入文件 {path} 不存在")
    if not os.path.isfile(path):
        raise ValueError(f"{path} 不是有效文件")


def main():
    args = parse_arguments()

    try:
        validate_file(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{str(e)}")
        return

    try:
        # 读取整个JSON文件
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 验证是否为列表格式
        if not isinstance(data, list):
            raise ValueError("JSON根元素必须是数组")

        # 过滤数据
        filtered_data = [
            item for item in data
            if item.get("best_choice_resolved") is False
        ]

        # 保存结果
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)

        print(f"处理完成！原始记录数：{len(data)}，保留记录数：{len(filtered_data)}")
        print(f"输出文件已保存至：{os.path.abspath(args.output)}")

    except json.JSONDecodeError as e:
        print(f"JSON解析失败：{str(e)}")
        print("请检查输入文件是否为有效的JSON格式")
    except ValueError as e:
        print(f"数据结构错误：{str(e)}")
    except Exception as e:
        print(f"未知错误：{str(e)}")


if __name__ == "__main__":
    main()