
import time
import csv
import argparse
from pathlib import Path


def cpu_work(iterations):
    """Perform CPU-intensive calculations."""
    result = 0

    for i in range(iterations):
        result += i * i

    return result


def batch_worker(worker_id, duration, iterations, writer):
    """Continuously perform CPU work."""

    start_time = time.monotonic()
    completed_tasks = 0

    while time.monotonic() - start_time < duration:
        cpu_work(iterations)
        completed_tasks += 1

    writer.writerow([
        worker_id,
        completed_tasks,
        time.monotonic() - start_time
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Batch workload generator"
    )

    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--iterations", type=int, default=100000)
    parser.add_argument("--output", default="batch_results.csv")

    args = parser.parse_args()

    if args.workers < 1 or args.duration <= 0 or args.iterations < 1:
        parser.error("Workers, duration and iterations must be positive.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "worker_id",
            "completed_tasks",
            "duration_seconds"
        ])

        import threading
        workers = []

        for worker_id in range(1, args.workers + 1):
            thread = threading.Thread(
                target=batch_worker,
                args=(worker_id, args.duration, args.iterations, writer)
            )

            workers.append(thread)
            thread.start()

        for thread in workers:
            thread.join()

    print("Batch workload completed.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
