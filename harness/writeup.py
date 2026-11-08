"""Short post generated from the same verified artifacts as RESULTS.md."""
import json


def writeup(root, runs, analysis):
    from .report import metric, taxonomy
    phase2 = [(p,m,rows) for p,m,rows in runs if m.get('phase')==2]
    if not phase2:
        return None
    reference = next((item for item in runs if item[1]['agent']=='baseline'), None)
    original = next((item for item in runs if item[1]['agent']=='v0'), None)
    if not reference or not original:
        raise ValueError('writeup requires the original measured baseline and v0')
    singles = [item for item in phase2 if len(item[1]['features'])==1]
    combinations = [item for item in phase2 if len(item[1]['features'])>1]
    def rank(item):
        s=item[1]['summary']
        tokens=(s['prompt_tokens']+s['completion_tokens']) if s['usage_complete'] else float('inf')
        return (s['passed'], -taxonomy(item[0],item[2])['parse'], -tokens, -s['task_wall_s'])
    best = max(phase2, key=rank)
    bm=best[1];bs=bm['summary'];rs=reference[1]['summary'];vs=original[1]['summary']
    comparison = 'beat' if bs['passed']>rs['passed'] else 'matched' if bs['passed']==rs['passed'] else 'did not beat'
    lines=['# Valid actions are only the start', '',
           f"We tested `{bm['model']}` on a frozen local coding suite. The original v0 passed {vs['passed']}/{vs['tasks']} tasks; the upstream mini-SWE-agent baseline passed {rs['passed']}/{rs['tasks']}. We then completed {len(singles)} single-change runs and {len(combinations)} combination run(s), keeping the model digest, suite and budgets fixed.", '',
           f"The best measured Phase 2 configuration, **{bm['agent']}**, passed **{bs['passed']}/{bs['tasks']} ({bs['pass_rate']:.0%})** and {comparison} the baseline. Its summed task wall time was **{bs['task_wall_s']:.2f} seconds**, with **{metric(bs['prompt_tokens'])} input tokens** and **{metric(bs['completion_tokens'])} output tokens**. This is an observed development-suite result, not a Terminal-Bench score or a statistical claim.", '',
           '| Configuration | Passed | Wall (s) | Input / output tokens |',
           '|---|---:|---:|---:|']
    for path,meta,rows in [reference,original]+phase2:
        s=meta['summary']
        lines.append(f"| [{meta['agent']}]({path.relative_to(root)}/run.json) | {s['passed']}/{s['tasks']} | {s['task_wall_s']:.2f} | {metric(s['prompt_tokens'])} / {metric(s['completion_tokens'])} |")
    lines += ['', 'The changes addressed action decoding, corrective feedback, reading/editing contracts, requirement-based self-tests and repetition after edits. Each was measured alone before any combination. No task-specific solution hints or hidden-grader content were used in development.']
    constrained = next((item for item in singles if item[1]['features']==['constrained']), None)
    if constrained:
        old=taxonomy(original[0],original[2]);new=taxonomy(constrained[0],constrained[2])
        lines += ['', f"Structured output changed a concrete failure mode: recorded malformed-action events went from {old['parse']} in the original v0 run to {new['parse']} in the constrained-only run. Format-budget exits changed from {old['format_exit']} to {new['format_exit']}. Those counts describe protocol reliability; the pass table shows whether it translated into correct programs."]
    lines += ['', ' '.join(analysis.get('post_findings', [])), '',
              '**What this experiment can establish.** These are actual, sequential local runs with provider-reported tokens and independent grading. The combination was selected on the same small development suite; there is no held-out result. All completed attempts, regressions, source snapshots and trace evidence are retained. Faster early exits are not successful-task efficiency.', '',
              'The next decision should come from a held-out evaluation and a real Terminal-Bench run once the required environment is available. The useful artifact here is an inspectable experiment: change one thing, preserve the failures, and measure correctness separately from valid tool syntax.', '',
              'See [RESULTS.md](RESULTS.md) for the complete ablation table, per-task logs and failure taxonomy, and [docs/design.md](docs/design.md) for the implementation. Regenerate both the numbers here and RESULTS.md with `make report`.', '']
    target=root/'WRITEUP.md';target.write_text('\n'.join(lines))
    return target
