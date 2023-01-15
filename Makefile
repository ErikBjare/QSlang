SRCFILES=qslang/*.py tests/*.py

run:
	python3 main.py

test:
	poetry run pytest --cov=qslang

test-integration:
	poetry run ./test-integration.sh

data/generated/effectspan-caffeine.csv:
	poetry run python3 -m qslang effectspan --substances caffeine > $@

data/generated/effectspan-cannabis.csv:
	# TODO: the 'cannabis oil' part doesn't work
	poetry run python3 -m qslang effectspan --substances 'weed,hash,cannabis oil' --normalize 'weed' > $@

typecheck:
	poetry run mypy --ignore-missing-import ${SRCFILES}

format:
	poetry run black qslang tests

pyupgrade:
	poetry run pyupgrade --py310-plus ${SRCFILES}

precommit:
	make format
	make pyupgrade
	make typecheck

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

