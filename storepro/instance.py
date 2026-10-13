"""OS-backed lock held for the lifetime of the desktop process."""
import os
from pathlib import Path


class InstanceLock:
    def __init__(self,path): self.path=Path(path); self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0,2)
                if self.file.tell()==0: self.file.write(b'0'); self.file.flush()
                self.file.seek(0); msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close(); self.file=None
            raise ValueError('البرنامج مفتوح بالفعل على مجلد البيانات نفسه') from None
        return self
    def __exit__(self,*args):
        if self.file:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0); msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
            self.file.close(); self.file=None
