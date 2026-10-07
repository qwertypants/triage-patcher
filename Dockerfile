FROM python:3.11-slim
WORKDIR /app
COPY repair_agent /app/repair_agent
COPY pyproject.toml /app/pyproject.toml
RUN useradd --create-home --uid 10001 runner
USER runner
ENTRYPOINT ["python", "-m", "repair_agent"]
