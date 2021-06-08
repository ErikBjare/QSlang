run:
	python3 main.py

test:
	pytest qslang/filter.py tests/*.py

test-integration:
	qslang doses --substances Noopept
	qslang events --substances Noopept
	qslang plot --substances Noopept
	qslang plot --count --substances Noopept
	qslang plot --days --substances Noopept

typecheck:
	mypy --ignore-missing-import qslang/*.py tests/*.py

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

