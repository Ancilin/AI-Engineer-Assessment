import os
import sys
import argparse
import subprocess
import time
from src.ingest import ingest_csv_to_sqlite

def main():
    parser = argparse.ArgumentParser(description="AI Support Ticket Analytics & Anomaly Detection System Launcher")
    parser.add_argument(
        "--mode",
        choices=["api", "ui", "all"],
        default="all",
        help="Mode to start: 'api' (FastAPI only), 'ui' (Streamlit only), or 'all' (Both API and UI)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="API Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="API Port (default: 8000)")
    parser.add_argument("--ui-port", type=int, default=8501, help="Streamlit UI Port (default: 8501)")

    args = parser.parse_args()

    print("===============================================================")
    print(" 🚀 AI Support Ticket System - Single Command Entrypoint")
    print("===============================================================")

    # Step 1: Execute Data Ingestion
    print("\n[Step 1/2] Ingesting CSV dataset into SQLite database...")
    count, db_path = ingest_csv_to_sqlite()
    print(f"✓ Data Ingestion Complete: {count} tickets stored in {db_path}\n")

    processes = []

    try:
        # Step 2: Start API and/or UI
        if args.mode in ["api", "all"]:
            print(f"[Launcher] Starting FastAPI REST API at http://{args.host}:{args.port}")
            print(f"[Launcher] OpenAPI Documentation available at http://{args.host}:{args.port}/docs")
            api_proc = subprocess.Popen([
                sys.executable, "-m", "uvicorn", "api.main:app",
                "--host", args.host,
                "--port", str(args.port),
                "--reload"
            ])
            processes.append(api_proc)

        if args.mode in ["ui", "all"]:
            # Give API a moment to spin up if starting both
            if args.mode == "all":
                time.sleep(2)
            print(f"[Launcher] Starting Streamlit Web UI at http://{args.host}:{args.ui_port}")
            ui_proc = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", "ui/app.py",
                "--server.port", str(args.ui_port),
                "--server.address", args.host
            ])
            processes.append(ui_proc)

        print("\n✓ System running successfully! Press Ctrl+C to stop.\n")
        
        # Keep main thread alive
        for proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\nShutting down services...")
        for proc in processes:
            proc.terminate()
        print("Done.")

if __name__ == "__main__":
    main()
