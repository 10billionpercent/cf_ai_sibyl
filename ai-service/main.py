from fastapi import FastAPI, UploadFile, File
from resume_parser import parse_resume

app = FastAPI()


@app.post("/parse-resume")
async def parse_resume_endpoint(file: UploadFile = File(...)):

    content = await file.read()

    result = await parse_resume(content)

    return result