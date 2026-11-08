import os
import shlex
import socket
import time
from pathlib import Path

import pytest
from harness import ROOT
from harness.sandbox import Sandbox


def test_shell_can_work_but_cannot_escape(tmp_path):
    work=tmp_path/'work';s=Sandbox(work)
    outside=tmp_path/'outside';outside.write_text('private')
    assert s.run('python3 -c "print(4)"')["output"].strip()=='4'
    assert s.run('echo okay > file && cat file')["returncode"]==0
    assert s.run('cat ../outside')["returncode"]!=0
    assert s.run('echo bad > ../outside')["returncode"]!=0
    assert outside.read_text()=='private'
    # A real listener on the host's loopback must be unreachable from inside.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0)); listener.listen()
        port = listener.getsockname()[1]
        network_code = f'import socket;socket.create_connection(("127.0.0.1",{port}),timeout=1)'
        network_result = s.run('python3 -c ' + shlex.quote(network_code))
    assert network_result["returncode"]!=0
    blocked = ('PermissionError', 'Operation not permitted', 'ConnectionRefusedError', 'Network is unreachable')
    assert any(marker in network_result['output'] for marker in blocked)
    assert s.run(f'cat {shlex.quote(str(ROOT / "suites/mini-v1/merge-config/verify.py"))}')["returncode"]!=0


def test_safe_patch_rejects_ambiguous_and_symlink_paths(tmp_path):
    s=Sandbox(tmp_path/'work')
    s.patch('new.py','','x = 1\n')
    s.patch('new.py','x = 1','x = 2')
    assert 'x = 2' in s.read('new.py')
    with pytest.raises(ValueError): s.patch('new.py','','overwrite')
    s.patch('duplicates','','same same')
    with pytest.raises(ValueError): s.patch('duplicates','same','bad')
    (s.work/'escape').symlink_to(tmp_path)
    with pytest.raises(ValueError): s.patch('escape/nope','','bad')
    with pytest.raises(ValueError): s.read('../outside')
    with pytest.raises(ValueError): s.read('/etc/passwd')
    assert not (tmp_path/'nope').exists()


def test_timeout_kills_background_children(tmp_path):
    s=Sandbox(tmp_path/'work')
    r=s.run('(sleep 1; echo escaped > orphan) & sleep 20',timeout=0.15)
    assert r['exception_info']=='command timeout'
    time.sleep(1.1)
    assert not (s.work/'orphan').exists()


def test_output_limit_is_bounded(tmp_path):
    s=Sandbox(tmp_path/'work')
    r=s.run('yes x',max_output=1000)
    assert r['exception_info']=='command output limit'
    assert len(r['output'])<=1000
