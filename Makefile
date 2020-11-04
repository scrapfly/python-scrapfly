install:
	python -m pip install --user --upgrade setuptools wheel
	python -m pip install --user --upgrade twine

bump:
	sed -i "1s/.*/__version__ = '$(VERSION)'/" scrapfly/__init__.py
	git add scrapfly/__init__.py
	git commit -m "bump version to $(VERSION)"
	git push

release:
	git tag -a $(VERSION) -m "Version $(VERSION)"
	python setup.py sdist bdist_wheel
	python -m twine upload --config-file .pypirc dist/*
	git push --tags
