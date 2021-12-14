install:
	python -m pip install --user --upgrade setuptools wheel
	python -m pip install --user --upgrade twine pdoc3 colorama

bump:
	sed -i "1s/.*/__version__ = '$(VERSION)'/" scrapfly/__init__.py
	git add scrapfly/__init__.py
	git commit -m "bump version to $(VERSION)"
	git push

generate-docs:
	pdoc --html scrapfly --force --output-dir docs

release:
	-rm dist/*
	$(MAKE)	generate-docs
	git add docs/*
	-git commit -m "Update API documentation for version $(VERSION)"
	-git push origin master
	git tag -a $(VERSION) -m "Version $(VERSION)"
	python setup.py sdist bdist_wheel
	python -m twine upload --config-file .pypirc dist/*
	git push --tags
	$(MAKE) bump VERSION=$(NEXT_VERSION)

dev:
	rm -Rf $(shell python -m site --user-site )/scrapfly*
	python setup.py develop --user
