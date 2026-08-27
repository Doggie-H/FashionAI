import traceback
import runpy

try:
    print("Starting script...")
    runpy.run_path("ai_training/vlm_finetune_lora.py", run_name="__main__")
    print("Script finished!")
except Exception as e:
    print("Caught exception:")
    traceback.print_exc()
except SystemExit as e:
    print(f"System exit: {e.code}")
