run:
	python3 main.py

test:
	poetry run pytest --cov=qslang

test-integration:
	qslang doses --substances Noopept
	qslang events --substances Noopept
	qslang plot --substances Noopept
	qslang plot --count --substances Noopept
	qslang plot --days --substances Noopept

data/generated/effectspan-caffeine.csv:
	poetry run python3 -m qslang effectspan --substances caffeine > $@

data/generated/effectspan-cannabis.csv:
	# TODO: the 'cannabis oil' part doesn't work
	poetry run python3 -m qslang effectspan --substances 'weed,hash,cannabis oil' --normalize 'weed' > $@

typecheck:
	poetry run mypy --ignore-missing-import qslang/*.py tests/*.py

format:
	poetry run black qslang tests

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

