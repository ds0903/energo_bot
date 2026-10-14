.PHONY: run
run:
	python bot/bot.py

.PHONY: check
check:
	python -m ruff check . && python -m black --check . && python -m isort --check .

.PHONY: fix
fix:
	python -m black . && python -m isort .
