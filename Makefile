.PHONY: install hindsight demo demo-offline serve test
install:
	pip install -r requirements.txt
hindsight:  ## self-hosted Hindsight (needs GROQ_API_KEY exported)
	docker run --rm -it -p 8888:8888 -p 9999:9999 \
	  -e HINDSIGHT_API_LLM_PROVIDER=groq -e HINDSIGHT_API_LLM_API_KEY=$$GROQ_API_KEY \
	  -e HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-20b \
	  -v $$HOME/.hindsight-docker:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest
demo:
	APP_ENV=development python -m scripts.demo --fresh
demo-offline:
	APP_ENV=development MEMORY_BACKEND=local LLM_BACKEND=mock GROQ_API_KEY= python -m scripts.demo --fresh
serve:
	uvicorn app.server:app --host 127.0.0.1 --port 8000
test:
	python -m unittest discover -s tests -v
