import os
def python_files(root):
    return [f for f in os.listdir(root) if f.endswith(".py")]
