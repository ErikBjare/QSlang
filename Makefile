run:
	pipenv run python3 main.py

test:
	pipenv run python3 -m pytest tests/*.py

test-integration:
	pipenv run python3 main.py doses Noopept
	pipenv run python3 main.py events
	pipenv run python3 main.py plot Noopept
	pipenv run python3 main.py plot --count Noopept
	pipenv run python3 main.py plot --days Noopept

typecheck:
	pipenv run python3 -m mypy --ignore-missing-import qslang/*.py tests/*.py

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

