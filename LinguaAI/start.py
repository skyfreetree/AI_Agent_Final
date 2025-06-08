import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    uvicorn.run("LinguaAI.app.app:app", host=args.host, port=args.port, workers=args.workers)