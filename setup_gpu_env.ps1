$uv = "C:\Users\huynh\AppData\Roaming\Python\Python314\Scripts\uv.exe"
& $uv venv --python 3.12 .venv
& $uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
& $uv pip install -r ai_training/requirements.txt
