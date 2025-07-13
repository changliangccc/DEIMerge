# DEIMerge

## Project Overview

DeIMerge is an automated program repair (APR) framework that improves the repair capability of complex defects through multi-agent collaboration and intelligent patch fusion strategies. In this framework, multiple open-source agents (such as LLM-based repair models) generate candidate patches, and then the optimal patch is selected through scoring and voting. For instances that have not yet been repaired, DeIMerge collects all failed patches and uses LLM deep analysis to fuse scattered repair clues and generate high-quality merged patches. Experimental results show that this method increases the single-patch repair rate of open-source SWE agents from 27.3% to 37.0%, with a maximum overall repair rate of 57.3%. Key contributions include: establishing an end-to-end closed-loop process of ‘generation → scoring → voting → fusion → verification’; proposing a failed patch fusion strategy to deeply mine information from failed patches; and validating the effectiveness and general applicability of this strategy across various mainstream LLM models.


## Run command

Ensemble your own predictions by running the following command:

### 1. Integrate customised prediction results
```bash
python DEI.py
  --output_dir committee_out_1
  --submission_preds pred1.jsonl,pred2.jsonl,...
  --submission_results results1.json,results2.json,...
```

#### Parameter description:
- --submission_preds: Path to the prediction file to be integrated (JSONL format, comma-separated).
- --submission_results: (Optional) Path to the evaluation results file for the corresponding agent (JSON format, comma-separated).  
  - If this parameter is provided, the SWE Committee will only re-score resolved instances, saving time and costs.  
  - If not provided, the Committee will re-rank all instances (results remain unaffected).
  - ⚠️ Note: The accuracy of evaluation results depends on external tools (such as Moatless EvalTools) and may differ from the SWE-Bench rankings.
#### Result file format requirements:
- Each results.json file must contain the field resolved or resolved_ids, listing the IDs of resolved instances.

### 2.Cleaning patches
#### Extract failed instances:
```bash
python clean_evl.py
  --input output.json
  --output cleaned.json
```
- output.json: Original results after DEIBASE evaluation.
- cleaned.json: Only failed instances are retained.
  
#### Delete redundant structures:
```bash
python delete_evl.py
  --input cleaned.json
  --output deleted.json
```
- Remove unnecessary structures (such as duplicate scores) from failed instances.

### 3.Split evaluation files
#### Split DEIBASE evaluation results into separate files by agent:
```bash
python split_evaluations_by_model.py
  --input deleted.json
  --output mergedata.json
```
- mergedata.json: Evaluation data for each instance for each agent.

### 4. Merge failed patches
#### Run the failed patch merge module:
bash
```python merge_evl_patches.py ./merged
  --preds_to_eval preds1.json,preds2.json,preds3.json...
  --merge_output merged.jsonl
```
- preds_to_eval: Evaluation files for each agent (comma-separated).
- merged.jsonl: The merged failed patch file.

### 5. Final evaluation
Use the SWE-bench evaluator to verify the DEIBASE results and merged patches separately:
#### Evaluate DEIBASE results:
```bash
sb-cli submit swe-bench_lite test
  --predictions_path result.jsonl
  --run_id ‘deibase_eval’
  --gen_report 1
```

#### valuate merged patches:
```bash
sb-cli submit swe-bench_lite test
  --predictions_path merged.jsonl
  --run_id ‘merged_eval’
  --gen_report 1
```

## Output results
- Compare the resolution rates of deibase_eval and merged_eval to verify the effectiveness of DeIMerge's fixes (in the paper, the resolution rate increased from 27.3% to 37.0%, with a maximum of 57.3%).
For further assistance, please refer to the SWE-bench official documentation or submit an issue.
