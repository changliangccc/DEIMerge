import os
from openai import OpenAI
import tiktoken
from tqdm import tqdm
import argparse
import json
import hashlib
from typing import Dict, List
from merge_evl_prompt import SYSTEM_PROMPT,MERGE_PROMPT_TEMPLATE
from utils import (
    extract_gpt4_tag,
    get_before_after_code_with_context,
    get_full_data
)

# 初始化OpenAI客户端
#client = OpenAI(
#    base_url="https://api.chatanywhere.tech/v1",
#    api_key="sk-hDfFEMpU4uWhcv25GlmKhOpKAFw59ikHcpGALl613gDvmGnA"
#)

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-fake"  # 关键点：必须给个字符串，不能是 None
)

parser = argparse.ArgumentParser()
parser.add_argument("output_dir", type=str)
parser.add_argument("--merge_output", type=str, default="merged_patches.jsonl")
parser.add_argument("--processed_span_path", type=str, default="resource/relevant_context")
parser.add_argument("--preds_to_eval", type=str, default=None)
parser.add_argument("--model", type=str, default="skywork-swe-32b")
args = parser.parse_args()

# 初始化tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")

# 将 messages 拼成连续文本，统计 tokens 数，防止上下文过长
def count_tokens(messages):
    """使用tiktoken计算消息的token数量"""
    text = ""
    for message in messages:
        content = message["content"]
        if isinstance(content, list):
            for item in content:
                text += item["text"] + "\n"
        else:
            text += content + "\n"
    return len(tokenizer.encode(text))

# 封装 API 调用，自动捕获并打印异常
def get_completion(messages, model, temperature=0.7, max_tokens=4096):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response
    except Exception as e:
        print(f"API调用失败: {str(e)}")
        return None

preds = {}

# 修改 preds 加载逻辑
if args.preds_to_eval:
    preds_paths = args.preds_to_eval.split(",")
    for preds_path in preds_paths:
        print(f"\n=== 正在加载文件 {preds_path} ===")
        try:
            with open(preds_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"文件包含 {len(data)} 条记录")

                for idx, rec in enumerate(data):
                    print(f"\n处理记录 #{idx}:")
                    # 动态获取 instance_id：优先 rec 顶层，其次 patch 内
                    instance_id = rec.get("instance_id") or rec.get("patch", {}).get("instance_id")
                    if not instance_id:
                        instance_id = f"auto_{hash(str(rec)) & 0xffffffff:08x}"
                        print(f"!! 缺失 instance_id，生成 {instance_id}")

                    patch_info = rec.get("patch", {})
                    model = patch_info.get("model_name_or_path", "unknown_model")
                    patch_content = patch_info.get("model_patch", "")

                    explanation = rec.get("explanation", [])
                    if not isinstance(explanation, list):
                        print("!! explanation 格式错误，跳过该条")
                        continue

                    # 构造单模型的 evaluations 结构
                    single_eval = {
                        model: {
                            "patch": patch_info,
                            "explanation": explanation
                        }
                    }

                    print(f"实例 {instance_id}，模型 {model}，解释条目数 {len(explanation)}")

                    # 存入 preds：每个 instance_id 下 append 一个 patch-entry
                    preds.setdefault(instance_id, []).append({
                        "model_patch": patch_content,
                        "model_name_or_path": model,
                        "evaluations": single_eval
                    })

        except Exception as e:
            print(f"!! 文件加载失败: {str(e)}")
            continue

print(f"成功加载实例数: {len(preds)}")
print(f"示例实例ID: {list(preds.keys())[:5]}")

def get_patch_signature(instance_id, patch_content):
    return f"{instance_id}_{hashlib.md5(patch_content.encode()).hexdigest()[:6]}"

dataset = get_full_data()

# 输出目录
evaluations_dir = "./swecomm_runs"
evaluation_dir = f"{evaluations_dir}/{args.output_dir}"
model = args.model

# 将从 JSON 中读取的 identified_spans 列表拼接成
# "<code_span=文件 路径 span_id>…</code_span>" 的字符串
def organize_identified_spans(identified_spans):
    concat_spans = ""
    for identified_span in identified_spans:
        file_path = identified_span["file_path"]
        for span in identified_span["content"]:
            content = span["content"]
            span_id = span["span_id"]
            start_line = span["start_line"]
            # pad the line numbers to 4 digits
            line_numbered_content = ''.join([f"({start_line + i:04d}) {line}" for i, line in enumerate(content)])
            wrapped_code_span = f"<code_span={file_path} span_id={span_id}>\n{line_numbered_content}\n</code_span>"
            if not concat_spans:
                concat_spans = wrapped_code_span
            else:
                concat_spans += f"\n\n{wrapped_code_span}"
    return concat_spans

# 新增解释提取函数（约第150行）
def build_explanations(evaluations: Dict) -> str:
    """构造解释的Markdown格式"""
    explanations = []
    for model_name, eval_data in evaluations.items():
        exp_group = [
            f"### {model_name} 的修复说明",
            f"**问题分析**: {eval_data['explanation'][0]['issue_exp']}",
            f"**代码影响**: {eval_data['explanation'][0]['code_span_exp']}",
            f"**补丁意图**: {eval_data['explanation'][0]['patch_exp']}",
            f"**潜在问题**: {eval_data['explanation'][0]['new_issues_exp']}"
        ]
        explanations.append("\n".join(exp_group))
    return "\n\n".join(explanations)

requests = []

# whitelist可根据需要指定
whitelist = []

dataset = [instance for instance in dataset if not whitelist or instance["instance_id"] in whitelist]

before_after_dict = {}
cache_path = "cache/before_after_dict.json"

if os.path.exists("cache/before_after_dict.json"):
    before_after_dict = json.load(open("cache/before_after_dict.json", "r"))

for instance in tqdm(dataset, desc="Preparing spans before and after patch"):
    with open(os.path.join(args.processed_span_path, f"{instance['instance_id']}.json")) as f:
        identified_spans = json.load(f)["identified_spans"]
        concat_spans = organize_identified_spans(identified_spans)

    instance_id = instance["instance_id"]
    if instance_id not in preds:
        continue

    for patch in preds[instance_id]:
        signature = get_patch_signature(instance_id, patch["model_patch"])
        if signature in before_after_dict:
            try:
                before, after = get_before_after_code_with_context(
                    instance,
                    patch["model_patch"],
                    f"{os.getcwd()}/agent_repos/repos",
                    5
                )
                before_after_dict[signature] = {"before": before, "after": after}
            except Exception as e:
                print(f"Error processing {instance_id}: {str(e)}")

if not os.path.exists("cache"):
    os.makedirs("cache")
with open("cache/before_after_dict.json", "w") as f:
    json.dump(before_after_dict, f)

# 理解补丁
for instance in tqdm(dataset, desc="Preparing requests"):
    with open(os.path.join(args.processed_span_path, f"{instance['instance_id']}.json")) as f:
        identified_spans = json.load(f)["identified_spans"]
        concat_spans = organize_identified_spans(identified_spans)

    instance_id = instance["instance_id"]
    if instance_id not in preds:
        continue
    # 获取所有需要合并的补丁，直接合并，无需选取基准
    patches = preds[instance_id]
    patch_contents = []
    for patch in patches:
        signature = get_patch_signature(instance_id, patch["model_patch"])
        ctx = before_after_dict.get(signature, {})
        if ctx:
            patch_contents.append(
                f"=== Patch from {patch.get('model_name_or_path', 'unknown')} ===\n"
                f"Original:\n{ctx['before']}\nModified:\n{ctx['after']}"
            )

    explanations= build_explanations(patch["evaluations"])

    # 构造合并提示：直接传入所有补丁，不再使用 base_model 和 explanations
    formatted_user_input = MERGE_PROMPT_TEMPLATE.format(
        issue_text = instance["problem_statement"],
        code_spans = concat_spans,
        patches = "\n\n".join(patch_contents),
        explanations=build_explanations(patch["evaluations"]),
        request_timeout = 30
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": formatted_user_input}
    ]
    requests.append((instance_id, messages))
    print(f"→ 有效请求数量：{len(requests)}")

tot_tokens = 0
for instance_id, messages in requests:
    cnt = count_tokens(messages)
    if cnt >= 100000:
        print(f"Error in response for instance {instance_id}")
    else:
        tot_tokens += cnt

print(f"Total tokens: {tot_tokens}")
print(f"Total requests: {len(requests)} to be sent to {args.model}")

# 发送 API 请求并抽取结果
print("即将开始发送请求，数量：", len(requests))
for request in tqdm(requests, desc="Processing requests"):
    instance_id, messages = request
    response = get_completion(messages, args.model)

    if response is None:
        print(f"Error in response for instance {instance_id}")
        continue

    msg = response.choices[0].message.content
    merged_patch = extract_gpt4_tag(msg, "merged_patch")

    # 立即写入结果
    if merged_patch:
        merged_entry = {
            "instance_id": instance_id,
            "model_patch": merged_patch.strip(),
            "model_name_or_path": f"merged_{len(patches)}_patches"
        }
        with open(args.merge_output, 'a') as f:
            f.write(json.dumps(merged_entry) + '\n')
        print(f"[存储] 已将合并补丁写入 {args.merge_output}（instance_id={instance_id}）")
    else:
        # 输出调试日志，方便后续排查
        snippet = msg[:200].replace('\n', '\\n')
        print(f"!! instance_id={instance_id} 没提取到 merged_patch 标签，前 200 chars: {snippet}")
print(f"Total tokens: {tot_tokens}")
print(f"Total requests: {len(requests)} to be sent to {args.model}")

os.makedirs(evaluation_dir, exist_ok=True)

processed_meta_info = []

for instance in dataset:
    with open("cache/before_after_dict.json", "w") as f:
        json.dump(before_after_dict, f)

if os.path.exists(args.merge_output):
    num = sum(1 for _ in open(args.merge_output))
    print(f"最终共写入 {num} 条合并补丁到 {args.merge_output}")
else:
    print(f"未找到输出文件 {args.merge_output}")