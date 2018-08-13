run:
	python3 main.py

test:
	python3 -m pytest *.py

test-integration:
	python3 main.py doses Noopept
	python3 main.py events

typecheck:
	python3 -m mypy --ignore-missing-import *.py

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

