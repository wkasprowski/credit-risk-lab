"""Write complete CSVs before exposing their final filenames."""
import os
import tempfile
from pathlib import Path


def write_csv(frame, path, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".build-",suffix=".part",dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        frame.to_csv(temporary,**kwargs)
        os.replace(temporary,path)
    finally:
        if temporary.exists():
            temporary.unlink()
