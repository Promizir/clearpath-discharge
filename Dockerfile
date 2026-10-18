FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser *.py mock_ehr.json ./
COPY --chown=appuser:appuser static ./static
RUN mkdir -p /app/runtime && chown appuser:appuser /app/runtime
USER appuser
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
