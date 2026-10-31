from fastapi import FastAPI

app = FastAPI(title="LeadFlow")


@app.get("/")
def home():
    return {"message": "LeadFlow is running"}


@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"Hello, {name}!"}

@app.get("/hell")
def fn(name: str):
    return True