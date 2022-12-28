install:
	python -m pip install --user --upgrade setuptools wheel
	python -m pip install --user --upgrade twine pdoc3 colorama

bump:
	sed -i "1s/.*/__version__ = '$(VERSION)'/" scrapfly/__init__.py
	git add scrapfly/__init__.py
	git commit -m "bump version to $(VERSION)"
	git push

generate-docs:
	sudo pdoc --html scrapfly --force --output-dir docs

release:
	python -m twine upload --config-file .pypirc dist/*
	git push --tags
	$(MAKE) bump VERSION=$(NEXT_VERSION)

dev:
	rm -Rf $(shell python -m site --user-site )/scrapfly*
	python setup.py develop --user
