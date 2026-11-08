from pathlib import Path
def python_files(root):
    root=Path(root);out=[]
    def walk(directory):
        for p in directory.iterdir():
            if p.name.startswith('.') or p.is_symlink(): continue
            if p.is_dir(): walk(p)
            elif p.is_file() and p.suffix=='.py': out.append(p.relative_to(root).as_posix())
    walk(root)
    return sorted(out)
