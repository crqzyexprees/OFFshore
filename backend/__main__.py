import uvicorn

from backend.config import HOST, PORT


def main():
    uvicorn.run("backend.api:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
