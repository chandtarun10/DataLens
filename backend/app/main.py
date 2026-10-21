from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
import os
import re

from .analysis import analyze_dataframe, load_dataframe
from .reports import build_pdf, build_excel, build_csv


app = FastAPI(title='DataLens API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'https://datalens-vercel.app',
        'https://data-lens-jm2iqnf5r-chandtarun1234-7695.vercel.app',
        'https://data-lens-tawny.vercel.app',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

ALLOWED = {'.csv', '.xlsx', '.xls'}


def safe_name(name: str) -> str:
    base = os.path.splitext(
        os.path.basename(name or 'dataset')
    )[0]

    return (
        re.sub(r'[^A-Za-z0-9_-]+', '_', base)[:60]
        or 'dataset'
    )


async def read_upload(file: UploadFile):
    ext = os.path.splitext(file.filename or '')[1].lower()

    if ext not in ALLOWED:
        raise HTTPException(
            400,
            'Unsupported file type. Please upload a .csv, .xlsx, or .xls file.'
        )

    data = await file.read()

    if not data:
        raise HTTPException(
            400,
            'The uploaded file is empty.'
        )

    try:
        df = load_dataframe(data, ext)
    except Exception as e:
        raise HTTPException(
            400,
            f'Unable to read the uploaded file: {e}'
        )

    if df.empty:
        raise HTTPException(
            400,
            'The uploaded file contains no readable tabular data.'
        )

    return df, safe_name(file.filename)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.post('/api/analyze')
async def analyze(file: UploadFile = File(...)):
    df, _ = await read_upload(file)

    try:
        return analyze_dataframe(df)
    except Exception as e:
        raise HTTPException(
            500,
            f'Analysis failed: {e}'
        )


@app.post('/api/report/{format}')
async def report(format: str, file: UploadFile = File(...)):
    format = format.lower()

    if format not in {'pdf', 'xlsx', 'csv'}:
        raise HTTPException(
            400,
            'Report format must be pdf, xlsx, or csv.'
        )

    df, name = await read_upload(file)

    try:
        result = analyze_dataframe(df)

        if format == 'pdf':
            content = build_pdf(result, name)
            media = 'application/pdf'
            filename = f'{name}_DataLens_Report.pdf'

        elif format == 'xlsx':
            content = build_excel(result, name)
            media = (
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            )
            filename = f'{name}_DataLens_Analysis.xlsx'

        else:
            content = build_csv(result, name)
            media = 'text/csv'
            filename = f'{name}_DataLens_Analysis.csv'

    except Exception as e:
        raise HTTPException(
            500,
            f'Report generation failed: {e}'
        )

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )
