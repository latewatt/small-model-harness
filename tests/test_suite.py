import shutil
import pytest
from harness import ROOT
from harness.bench import load_tasks, grade

_, TASKS = load_tasks('mini10')


@pytest.mark.parametrize('task', TASKS, ids=[t['id'] for t in TASKS])
@pytest.mark.parametrize('oracle',[False,True],ids=['broken','oracle'])
def test_grader_rejects_broken_and_accepts_oracle(tmp_path, task, oracle):
    source=ROOT/task['path'];work=tmp_path/'work'
    shutil.copytree(source/'initial',work)
    if oracle: shutil.copytree(source/'oracle',work,dirs_exist_ok=True)
    result=grade(work,source)
    assert result['passed'] is oracle,result
