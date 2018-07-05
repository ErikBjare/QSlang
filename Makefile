run:
	python3 main.py

test:
	python3 -m mypy main.py
	python3 -m pytest main.py

data/private/Evernote:
	cd thirdparty/evernote-dump/source/ && \
		python run_script.py ../../../data/private/Evernote.enex && \
		mv Evernote/ ../../../data/private

