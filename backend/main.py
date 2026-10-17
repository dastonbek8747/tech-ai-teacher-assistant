from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()
app.mount("/creating_files", StaticFiles(directory="./creating_files"), name="creating_files")


@app.get("/")
def index():
    return {"Hello": "World"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000)
