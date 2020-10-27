install:
	python -m pip install --upgrade setuptools wheel
	python -m pip install --upgrade twine

release:
	python setup.py sdist bdist_wheel
	python -m twine upload --repository-url https://github.com/scrapfly/python-scrapfly dist/*

