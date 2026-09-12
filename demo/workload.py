import time
from demo.app.recommendations import generate_feed

def run():
    start = time.perf_counter()
    # Exercise target function with dummy user IDs
    feed = generate_feed([1, 2, 3, 4, 5] * 100)
    elapsed = time.perf_counter() - start
    print(f"Workload completed in {elapsed:.4f}s")
    return feed

if __name__ == "__main__":
    run()