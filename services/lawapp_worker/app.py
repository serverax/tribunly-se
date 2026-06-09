import time
import os

def main():
    print({"service": "lawapp-worker", "status": "started"})
    while True:
        time.sleep(int(os.getenv("WORKER_SLEEP_SECONDS", "60")))

if __name__ == "__main__":
    main()
