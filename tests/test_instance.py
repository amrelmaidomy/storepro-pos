import pytest
from storepro.instance import InstanceLock

def test_second_instance_is_rejected(tmp_path):
    first=InstanceLock(tmp_path/'app.lock')
    with first:
        with pytest.raises(ValueError):
            with InstanceLock(tmp_path/'app.lock'): pass
    with InstanceLock(tmp_path/'app.lock'): pass
