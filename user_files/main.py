import time
import sys

print("Bot starting up...")
sys.stdout.flush()

for i in range(10):
    print(f"Bot heartbeat {i+1}/10")
    sys.stdout.flush()
    time.sleep(2)

print("Bot has finished its task.")
sys.stdout.flush()
