run:
	python3 main.py

test:
	python3 -m mypy main.py
	python3 -m pytest main.py
