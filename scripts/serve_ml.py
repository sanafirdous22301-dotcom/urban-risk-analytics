import os
import sys
from pathlib import Path
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))

    print("=" * 65)
    print(" Starting Urban Risk Analytics & ML Prediction Server")
    print("=" * 65)
    print(f" Bind Address:         http://{host}:{port}")
    print(f" Web Dashboard:        http://{host}:{port}/app")
    print(f" Interactive Docs:     http://{host}:{port}/docs")
    print(f" ML Predict Endpoint:  POST http://{host}:{port}/api/ml/predict")
    print(f" ML Info Endpoint:     GET  http://{host}:{port}/api/ml/info")
    print("=" * 65)
    uvicorn.run("backend.main:app", host=host, port=port, log_level="info")
