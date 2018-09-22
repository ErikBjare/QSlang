run:
	pipenv run python3 main.py

test:
	pipenv run python3 -m pytest *.py

test-integration:
	pipenv run python3 main.py doses Noopept
	pipenv run python3 main.py plot Noopept
	pipenv run python3 main.py events

typecheck:
	pipenv run python3 -m mypy --ignore-missing-import *.py

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

