.PHONY: format lint ci clean

format:
	uv run black .
	uv run ruff check . --fix

lint:
	uv run ruff check .

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	rm -rf .pytest_cache .coverage coverage.xml dist