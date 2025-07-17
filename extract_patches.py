import json
import argparse


def extract_fields(input_path: str, output_path: str):

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    extracted = []
    for rec in data:
        # 从顶层和 patch 字段中获取 instance_id
        instance_id = rec.get('instance_id') or rec.get('patch', {}).get('instance_id')
        model_info = rec.get('patch', {})
        model_name = model_info.get('model_name_or_path')
        model_patch = model_info.get('model_patch')

        extracted.append({
            'instance_id': instance_id,
            'model_name_or_path': model_name,
            'model_patch': model_patch
        })

    # 写入 JSONL 文件，每行一个 JSON 对象
    with open(output_path, 'w', encoding='utf-8') as fout:
        for item in extracted:
            fout.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"提取完成，共处理 {len(extracted)} 条记录，结果写入 {output_path}")


def main():
    parser = argparse.ArgumentParser(description="提取补丁字段：instance_id, model_name_or_path, model_patch")
    parser.add_argument('input', help='输入 JSON 文件路径')
    parser.add_argument('output', help='输出 JSONL 文件路径')
    args = parser.parse_args()

    extract_fields(args.input, args.output)


if __name__ == '__main__':
    main()
