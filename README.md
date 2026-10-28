# Personal Assistant

Python version: **3.13.7**

## Run locally

```bash
poetry install
poetry run python homework8.py
```

## Build Docker image

```bash
docker build -t personal-assistant .
```

## Run with Docker

```bash
docker run -it personal-assistant
```

## Open shell in container

```bash
docker run -it personal-assistant /bin/bash
```

## Check containers

```bash
docker ps
docker ps -a
```
