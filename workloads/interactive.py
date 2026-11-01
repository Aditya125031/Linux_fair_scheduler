import time
import csv
import argparse
from pathlib import Path


def cpu_work(iterations):
    """Perform a small amount of CPU-intensive work."""
    result = 0

    for i in range(iterations):
        result += i * i

    return result


def interactive_worker(worker_id, duration, sleep_time, iterations, writer):
    """Generate repeated interactive requests."""

    start_time = time.monotonic()
    request_id = 0

    while time.monotonic() - start_time < duration:
        request_id += 1

        # Record when the request's CPU work begins
        request_start = time.monotonic()

        # Simulate a small CPU request
        cpu_work(iterations)

        # Record when the request completes
        request_end = time.monotonic()

        # Calculate request execution time
        response_time_ms = (request_end - request_start) * 1000

        writer.writerow([
            worker_id,
            request_id,
            request_start,
            request_end,
            response_time_ms
        ])

        # Wait briefly before generating the next request
        time.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive workload generator"
    )

    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--output", default="interactive_results.csv")

    args = parser.parse_args()

    if args.workers < 1 or args.duration <= 0:
        parser.error("Workers and duration must be positive.")

    if args.sleep < 0 or args.iterations < 1:
        parser.error("Sleep must be non-negative and iterations positive.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "worker_id",
            "request_id",
            "start_time",
            "completion_time",
            "response_time_ms"
        ])

        workers = []

        import threading

        for worker_id in range(1, args.workers + 1):
            thread = threading.Thread(
                target=interactive_worker,
                args=(
                    worker_id,
                    args.duration,
                    args.sleep,
                    args.iterations,
                    writer
                )
            )

            workers.append(thread)
            thread.start()

        for thread in workers:
            thread.join()

    print(f"Interactive workload completed.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
